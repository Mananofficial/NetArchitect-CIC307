"""Bitwise VLSM allocator.

All address math is done on 32-bit unsigned integers with explicit masking
(``& 0xFFFFFFFF``) because Python ints are unbounded: ``~mask`` on its own yields
a *negative* number, and ``0xFFFFFFFF << n`` grows past 32 bits. Both are classic
generated-code bugs documented in ai_audit_log.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import (AddressOverlapError, AddressSpaceExhaustedError,
                     InvalidParameterError)
from .explain import RationaleLog

MASK32 = 0xFFFFFFFF


# --------------------------------------------------------------------------
# primitive helpers
# --------------------------------------------------------------------------
def ip_to_int(ip: str) -> int:
    parts = ip.strip().split(".")
    if len(parts) != 4:
        raise InvalidParameterError(f"'{ip}' is not a dotted-quad IPv4 address")
    value = 0
    for p in parts:
        if not p.isdigit() or int(p) > 255 or (len(p) > 1 and p[0] == "0"):
            raise InvalidParameterError(f"'{ip}' has an invalid octet '{p}'")
        value = (value << 8) | int(p)
    return value


def int_to_ip(value: int) -> str:
    value &= MASK32
    return ".".join(str((value >> s) & 0xFF) for s in (24, 16, 8, 0))


def prefix_to_mask(prefix: int) -> int:
    if not 0 <= prefix <= 32:
        raise InvalidParameterError(f"prefix length /{prefix} outside 0..32")
    return (MASK32 << (32 - prefix)) & MASK32


def wildcard(prefix: int) -> int:
    """Inverse mask used by ACLs and OSPF network statements."""
    return ~prefix_to_mask(prefix) & MASK32


def mask_str(prefix: int) -> str:
    return int_to_ip(prefix_to_mask(prefix))


def wildcard_str(prefix: int) -> str:
    return int_to_ip(wildcard(prefix))


def block_size(prefix: int) -> int:
    return 1 << (32 - prefix)


def parse_cidr(cidr: str) -> tuple[int, int]:
    """Return (network_int, prefix). Rejects host bits set (e.g. 10.0.0.1/16)."""
    if "/" not in cidr:
        raise InvalidParameterError(f"'{cidr}' is not in CIDR notation (a.b.c.d/nn)")
    ip, _, plen = cidr.partition("/")
    if not plen.isdigit():
        raise InvalidParameterError(f"'{cidr}' has an invalid prefix length")
    prefix = int(plen)
    net = ip_to_int(ip)
    mask = prefix_to_mask(prefix)
    if net & ~mask & MASK32:
        raise InvalidParameterError(
            f"'{cidr}' has host bits set; the network address is "
            f"{int_to_ip(net & mask)}/{prefix}")
    return net, prefix


def prefix_for_hosts(hosts: int, point_to_point: bool = False) -> int:
    """Smallest prefix whose usable host count >= hosts.

    /31 is allowed only for point-to-point links (RFC 3021) and /32 for a single
    host route (loopback). Otherwise usable = 2^(32-p) - 2 (network + broadcast).
    """
    if hosts < 1:
        raise InvalidParameterError(f"host request must be >= 1 (got {hosts})")
    if point_to_point and hosts <= 2:
        return 31 if hosts == 2 else 32
    if hosts == 1 and point_to_point:
        return 32
    needed = hosts + 2
    bits = (needed - 1).bit_length()          # ceil(log2(needed))
    prefix = 32 - bits
    if prefix < 0:
        raise AddressSpaceExhaustedError(f"{hosts} hosts exceeds the IPv4 address space")
    return min(prefix, 30)


def usable_hosts(prefix: int) -> int:
    if prefix == 32:
        return 1
    if prefix == 31:
        return 2
    return block_size(prefix) - 2


def overlaps(a_net: int, a_pfx: int, b_net: int, b_pfx: int) -> bool:
    a_end = a_net + block_size(a_pfx) - 1
    b_end = b_net + block_size(b_pfx) - 1
    return a_net <= b_end and b_net <= a_end


# --------------------------------------------------------------------------
# allocation
# --------------------------------------------------------------------------
@dataclass
class Subnet:
    name: str
    hosts_requested: int
    network: int
    prefix: int
    vlan: int | None = None
    role: str = "lan"
    site: str | None = None

    @property
    def size(self) -> int:
        return block_size(self.prefix)

    @property
    def mask(self) -> str:
        return mask_str(self.prefix)

    @property
    def wildcard(self) -> str:
        return wildcard_str(self.prefix)

    @property
    def broadcast_int(self) -> int:
        return self.network | wildcard(self.prefix)

    @property
    def broadcast(self) -> str | None:
        return None if self.prefix >= 31 else int_to_ip(self.broadcast_int)

    @property
    def first_host_int(self) -> int:
        return self.network if self.prefix >= 31 else self.network + 1

    @property
    def last_host_int(self) -> int:
        return self.broadcast_int if self.prefix >= 31 else self.broadcast_int - 1

    @property
    def gateway(self) -> str:
        return int_to_ip(self.first_host_int)

    @property
    def usable(self) -> int:
        return usable_hosts(self.prefix)

    @property
    def utilization(self) -> float:
        return self.hosts_requested / self.usable

    @property
    def cidr(self) -> str:
        return f"{int_to_ip(self.network)}/{self.prefix}"

    def host(self, offset: int) -> str:
        """offset 0 = first usable host."""
        addr = self.first_host_int + offset
        if addr > self.last_host_int:
            raise AddressSpaceExhaustedError(f"{self.name}: host offset {offset} out of range")
        return int_to_ip(addr)

    def as_dict(self) -> dict:
        return {
            "name": self.name, "site": self.site, "vlan": self.vlan, "role": self.role,
            "cidr": self.cidr, "mask": self.mask, "wildcard": self.wildcard,
            "gateway": self.gateway, "first_host": int_to_ip(self.first_host_int),
            "last_host": int_to_ip(self.last_host_int), "broadcast": self.broadcast,
            "hosts_requested": self.hosts_requested, "usable": self.usable,
            "utilization_pct": round(self.utilization * 100, 1),
        }


def allocate(root_cidr: str, requests: list[dict], log: RationaleLog | None = None,
             label: str = "root") -> list[Subnet]:
    """Allocate non-overlapping subnets for ``requests`` inside ``root_cidr``.

    Each request: {"name", "hosts", optional "vlan", "role", "p2p", "site"}.
    Largest-first ordering guarantees every block lands on its natural boundary
    with no fragmentation; alignment is still enforced explicitly.
    """
    log = log if log is not None else RationaleLog()
    root_net, root_pfx = parse_cidr(root_cidr)
    root_end = root_net + block_size(root_pfx) - 1

    sized: list[tuple[int, int, dict]] = []
    for idx, r in enumerate(requests):
        if "name" not in r or "hosts" not in r:
            raise InvalidParameterError(f"subnet request #{idx} needs 'name' and 'hosts'")
        try:
            hosts = int(r["hosts"])
        except (TypeError, ValueError):
            raise InvalidParameterError(f"subnet '{r['name']}': hosts must be an integer")
        p2p = bool(r.get("p2p", False)) or r.get("role") in {"p2p", "loopback"}
        pfx = prefix_for_hosts(hosts, point_to_point=p2p)
        if pfx < root_pfx:
            raise AddressSpaceExhaustedError(
                f"subnet '{r['name']}' needs a /{pfx} ({hosts} hosts) which is larger than "
                f"the {label} block {root_cidr}")
        sized.append((pfx, idx, r))

    # descending block size, stable on input order
    sized.sort(key=lambda t: (t[0], t[1]))

    cursor = root_net
    out: list[Subnet] = []
    for pfx, _, r in sized:
        size = block_size(pfx)
        cursor = (cursor + size - 1) & ~(size - 1) & MASK32   # align to boundary
        if cursor + size - 1 > root_end:
            used = cursor - root_net
            raise AddressSpaceExhaustedError(
                f"Address space exhausted in {label} {root_cidr}: cannot place "
                f"'{r['name']}' (/{pfx}, {size} addresses); {used} of "
                f"{block_size(root_pfx)} addresses already allocated.")
        sn = Subnet(r["name"], int(r["hosts"]), cursor, pfx, r.get("vlan"),
                    r.get("role", "lan"), r.get("site"))
        out.append(sn)
        cursor += size

    _assert_no_overlap(out)
    for sn in out:
        _explain_subnet(sn, log)
    total = sum(s.size for s in out)
    req_hosts = sum(s.hosts_requested for s in out)
    log.add("VLSM", f"{label} {root_cidr}", f"{len(out)} subnets, {total} addresses",
            f"Requests were sorted by required block size (largest first) and placed "
            f"sequentially on their natural bit boundaries, which guarantees zero overlap and no "
            f"fragmentation. {total} of {block_size(root_pfx)} addresses consumed "
            f"({total / block_size(root_pfx) * 100:.1f}% of the block); host efficiency "
            f"{req_hosts}/{sum(s.usable for s in out)} usable = "
            f"{req_hosts / max(1, sum(s.usable for s in out)) * 100:.1f}%. Remaining "
            f"{block_size(root_pfx) - total} addresses are contiguous at the top of the block "
            f"for growth.", ["RFC 1878", "RFC 4632", "RFC 1918"])
    return out


def _explain_subnet(sn: Subnet, log: RationaleLog) -> None:
    if sn.prefix == 31:
        why = (f"Point-to-point link: RFC 3021 /31 uses both addresses as hosts (no network/"
               f"broadcast needed on a 2-node link), saving 50% vs a /30.")
        refs = ["RFC 3021"]
    elif sn.prefix == 32:
        why = "Router loopback / router-ID: a /32 host route is stable and always up."
        refs = ["RFC 2328 s.C.1"]
    else:
        why = (f"{sn.hosts_requested} hosts + 2 (network, broadcast) = "
               f"{sn.hosts_requested + 2} addresses; smallest power of two >= that is "
               f"2^{32 - sn.prefix} = {sn.size} -> /{sn.prefix} (mask {sn.mask}, wildcard "
               f"{sn.wildcard}). Gateway {sn.gateway} (first usable), broadcast "
               f"{sn.broadcast}. Utilization {sn.hosts_requested}/{sn.usable} = "
               f"{sn.utilization * 100:.1f}%.")
        refs = ["RFC 950", "RFC 1878"]
    log.add("VLSM", sn.name, sn.cidr, why, refs)


def _assert_no_overlap(subnets: list[Subnet]) -> None:
    ordered = sorted(subnets, key=lambda s: s.network)
    for a, b in zip(ordered, ordered[1:]):
        if a.broadcast_int >= b.network:
            raise AddressOverlapError(f"{a.cidr} ({a.name}) overlaps {b.cidr} ({b.name})")


def round_up_block(addresses: int) -> int:
    """Smallest prefix whose block holds ``addresses`` addresses."""
    bits = max(0, (addresses - 1).bit_length())
    return 32 - bits


def allocate_hierarchical(root_cidr: str, sites: list[dict], log: RationaleLog | None = None
                          ) -> tuple[dict[str, Subnet], list[Subnet]]:
    """Two-level VLSM: carve one summarizable block per site, then VLSM inside it.

    Returns (site_blocks, all_subnets). Each site block is a single prefix that
    can be advertised as one summary route (OSPF ``area range`` / BGP aggregate).
    """
    log = log if log is not None else RationaleLog()
    site_reqs = []
    for s in sites:
        need = sum(block_size(prefix_for_hosts(int(r["hosts"]),
                   bool(r.get("p2p")) or r.get("role") in {"p2p", "loopback"}))
                   for r in s["subnets"])
        pfx = round_up_block(need)
        # express the site block as a host request that maps to exactly that prefix
        site_reqs.append({"name": s["name"], "hosts": max(1, block_size(pfx) - 2),
                          "_need": need})
    blocks_list = allocate(root_cidr, site_reqs, RationaleLog(), label="root")
    blocks = {b.name: b for b in blocks_list}
    for b, req in zip(sorted(blocks_list, key=lambda x: x.name),
                      sorted(site_reqs, key=lambda x: x["name"])):
        log.add("VLSM", f"Site block {b.name}", b.cidr,
                f"Site subnets need {req['_need']} addresses in total; rounded up to one "
                f"power-of-two block (/{b.prefix}, {b.size} addresses) so the whole site can be "
                f"advertised as a single summary route {b.cidr}.", ["RFC 4632"])
    all_subnets: list[Subnet] = []
    for s in sites:
        reqs = [dict(r, site=s["name"]) for r in s["subnets"]]
        all_subnets += allocate(blocks[s["name"]].cidr, reqs, log, label=f"site {s['name']}")
    _assert_no_overlap(all_subnets)
    return blocks, all_subnets
