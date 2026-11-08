"""Orchestrator: parameters -> media, VLSM, routing, topology -> Plan."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

from .errors import InvalidParameterError
from .explain import RationaleLog
from .loader import validate
from .media import MediaDecision, decide_media
from .routing import RoutingPlan, select_routing, select_topology
from .vlsm import Subnet, allocate, allocate_hierarchical, block_size, parse_cidr

DEVICE_LATENCY_MS = 0.01        # per-hop forwarding latency (store-and-forward, typical)
MTU_BITS = 1500 * 8


@dataclass
class LinkPlan:
    name: str
    a: str
    b: str
    path: str
    media: MediaDecision
    transit: Subnet | None = None
    area: int = 0
    a_if: str = ""
    b_if: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class Plan:
    params: dict
    log: RationaleLog
    topology: str
    media: list[MediaDecision]
    subnets: list[Subnet]
    site_blocks: dict[str, Subnet]
    routing: RoutingPlan
    links: list[LinkPlan]
    loopbacks: dict[str, Subnet]
    latency: list[dict]
    warnings: list[str]
    inventory: dict
    configs: dict[str, str] = field(default_factory=dict)

    def subnet(self, name: str) -> Subnet:
        for s in self.subnets:
            if s.name == name:
                return s
        raise InvalidParameterError(f"Unknown subnet reference '{name}'")


def build_plan(params: dict) -> Plan:
    params = copy.deepcopy(params)
    validate(params)
    log = RationaleLog()
    topology = select_topology(params, log)
    if params["profile"] == "campus_lan":
        plan = _build_campus(params, log, topology)
    else:
        plan = _build_routed(params, log, topology)
    from .acl_audit import audit_acls        # local imports avoid a cycle
    from .configgen import generate
    findings = audit_acls(plan)
    if findings and params.get("strict_acl_audit", True):
        raise InvalidParameterError("ACL packet-flow audit failed:\n  " + "\n  ".join(findings))
    plan.warnings += findings
    plan.configs = generate(plan)
    return plan


# ---------------------------------------------------------------------------
# Campus
# ---------------------------------------------------------------------------
def _build_campus(params: dict, log: RationaleLog, topology: str) -> Plan:
    site = params["sites"][0]
    dev = params.setdefault("devices", {})
    core_host = dev.get("core", {}).get("hostname", "CORE-SW1")
    edge = dev.get("edge", {})
    edge_host = edge.get("hostname", "EDGE-RTR1")

    media: list[MediaDecision] = []
    links: list[LinkPlan] = []
    inventory: dict = {"buildings": {}}
    for b in site["buildings"]:
        if "drop_distance_m" in b:
            m = decide_media({"name": f"{b['name']} horizontal drop", "distance_m": b["drop_distance_m"],
                              "bandwidth_gbps": 1, "media_request": b.get("drop_media")}, log)
            media.append(m)
        up = dict(b.get("uplink", {"distance_m": 50, "bandwidth_gbps": 10}))
        up["name"] = f"{core_host} <-> {b['name']} uplink"
        m = decide_media(up, log)
        media.append(m)
        links.append(LinkPlan(up["name"], core_host, f"{b['name']}-ACC1", "primary", m, raw=up))
        switches = max(1, math.ceil(int(b.get("endpoints", 0)) / 48))
        aps = int(b.get("aps", 0))
        poe_w = aps * 30
        inventory["buildings"][b["name"]] = {"access_switches": switches, "aps": aps, "poe_w": poe_w,
                                             "stacks": math.ceil(switches / 9)}
        log.add("Density", b["name"], f"{switches} x 48-port access switches",
                f"{b.get('endpoints', 0)} endpoints / 48 ports = {switches} switches "
                f"({math.ceil(switches / 9)} stack(s); StackWise max 9 members). {aps} PoE APs x "
                f"30 W (IEEE 802.3at Class 4) = {poe_w} W PoE budget, so PoE+ capable access "
                f"switches are required; IP phones share the PC port via the voice VLAN.",
                ["IEEE 802.3at", "IEEE 802.3bt"])

    edge_link = dict(edge.get("core_link", {"distance_m": 15, "bandwidth_gbps": 10}))
    edge_link["name"] = f"{core_host} <-> {edge_host}"
    m = decide_media(edge_link, log)
    media.append(m)

    reqs = [dict(s) for s in site["subnets"]]
    reqs += [{"name": "CORE-EDGE-P2P", "hosts": 2, "role": "p2p"},
             {"name": f"LO-{core_host}", "hosts": 1, "role": "loopback"},
             {"name": f"LO-{edge_host}", "hosts": 1, "role": "loopback"}]
    subnets = allocate(params["root_prefix"], reqs, log, label="campus root")
    by = {s.name: s for s in subnets}
    links.append(LinkPlan(edge_link["name"], core_host, edge_host, "primary", m,
                          transit=by["CORE-EDGE-P2P"], raw=edge_link))
    loopbacks = {core_host: by[f"LO-{core_host}"], edge_host: by[f"LO-{edge_host}"]}

    routing = select_routing(params, len(subnets), log)
    _campus_l2_rationale(params, log)
    _acl_rationale(params, log)
    return Plan(params, log, topology, media, subnets, {}, routing, links, loopbacks, [], [],
                inventory)


def _campus_l2_rationale(params: dict, log: RationaleLog) -> None:
    site = params["sites"][0]
    vlans = sorted(s["vlan"] for s in site["subnets"] if "vlan" in s)
    native = params.get("native_vlan", 999)
    log.add("L2 Switching", "VLAN segmentation", f"802.1Q VLANs {vlans}",
            "Each traffic class (per-building staff data, voice, corporate Wi-Fi, guest, AP "
            "management, servers, network management) gets its own VLAN/broadcast domain so "
            "broadcast load is contained and inter-VLAN traffic is forced through the L3 core "
            "where ACLs apply. Per-building data VLANs keep broadcast domains under ~500 hosts.",
            ["IEEE 802.1Q"])
    log.add("L2 Switching", "Trunk hardening", f"Pruned trunks, native VLAN {native}, DTP off",
            f"Every trunk carries only the VLANs that exist in that building "
            f"('switchport trunk allowed vlan <list>', never 'all'), uses unused native VLAN "
            f"{native} so untagged frames land nowhere (defeats double-tag VLAN hopping), and "
            f"disables DTP with 'switchport nonegotiate' so a host cannot negotiate a trunk.",
            ["IEEE 802.1Q", "Cisco SAFE"])
    log.add("L2 Switching", "Spanning tree", "Rapid PVST+ (802.1w), core = root bridge",
            "Redundant uplinks create L2 loops; RSTP's proposal/agreement handshake converges "
            "in < 1 s versus 30-50 s for legacy 802.1D. The core is pinned as root (priority "
            "4096) for every VLAN so traffic follows the designed path; edge ports use PortFast "
            "+ BPDU Guard so a rogue switch is err-disabled instead of moving the root.",
            ["IEEE 802.1w", "IEEE 802.1D-2004"])
    log.add("L2 Switching", "Link aggregation", "LACP (mode active) for multi-lane uplinks",
            "Uplinks needing > 10 Gb/s are bundled with LACP so STP sees one logical port "
            "(no blocked member) and all members carry traffic.", ["IEEE 802.1AX"])


def _acl_rationale(params: dict, log: RationaleLog) -> None:
    for acl in params.get("acls", []):
        log.add("Security", f"ACL {acl['name']}",
                f"Extended ACL {acl['direction']} on VLAN {acl['apply_vlan']}",
                f"Applied {acl['direction']}bound on the VLAN {acl['apply_vlan']} gateway "
                f"interface, i.e. it filters traffic "
                f"{'sourced from' if acl['direction'] == 'in' else 'destined to'} hosts in that "
                f"VLAN. {len(acl['rules'])} entries, most specific first, ending in an explicit "
                f"deny so denied flows are logged. Wildcard masks are computed bitwise from each "
                f"subnet prefix (wildcard = ~mask & 0xFFFFFFFF).", ["Cisco IOS ACL reference"])


# ---------------------------------------------------------------------------
# Metro / WAN
# ---------------------------------------------------------------------------
def _build_routed(params: dict, log: RationaleLog, topology: str) -> Plan:
    sites = params["sites"]
    site_by = {s["name"]: s for s in sites}
    hq = next((s["name"] for s in sites if s.get("role") == "hq"), sites[0]["name"])

    # attach loopbacks and transit /31s to a site block so each area summarises cleanly
    alloc_sites = []
    for s in sites:
        reqs = [dict(r) for r in s["subnets"]]
        reqs.append({"name": f"LO-{s['router']}", "hosts": 1, "role": "loopback"})
        for ln in params["links"]:
            owner = ln["b"] if ln["a"] == hq else ln["a"] if ln["b"] == hq else ln["b"]
            if owner == s["name"]:
                reqs.append({"name": f"{ln['name']}-P2P", "hosts": 2, "role": "p2p"})
        alloc_sites.append({"name": s["name"], "subnets": reqs})
    blocks, subnets = allocate_hierarchical(params["root_prefix"], alloc_sites, log)
    by = {s.name: s for s in subnets}
    lan_count = sum(len(s["subnets"]) for s in sites)
    routing = select_routing(params, lan_count, log)

    media: list[MediaDecision] = []
    links: list[LinkPlan] = []
    for ln in params["links"]:
        m = decide_media(ln, log)
        media.append(m)
        a_area, b_area = routing.areas[ln["a"]], routing.areas[ln["b"]]
        if a_area and b_area and a_area != b_area:
            raise InvalidParameterError(
                f"link {ln['name']} joins two non-backbone areas ({a_area}, {b_area}); "
                f"OSPF requires inter-area traffic to transit Area 0")
        area = a_area or b_area
        links.append(LinkPlan(ln["name"], site_by[ln["a"]]["router"], site_by[ln["b"]]["router"],
                              ln.get("path", "primary"), m, by[f"{ln['name']}-P2P"], area, raw=ln))

    loopbacks = {s["router"]: by[f"LO-{s['router']}"] for s in sites}
    latency = _latency(params, links, log)
    warnings = [f"Latency budget exceeded on {r['link']}" for r in latency if not r["ok"]]
    _routed_rationale(params, log, routing)
    _acl_rationale(params, log)
    inventory = {"routers": [s["router"] for s in sites], "hq": hq}
    return Plan(params, log, topology, media, subnets, blocks, routing, links, loopbacks,
                latency, warnings, inventory)


def _latency(params: dict, links: list[LinkPlan], log: RationaleLog) -> list[dict]:
    budget = params.get("latency_budget_ms")
    out = []
    for lp in links:
        bw_bps = min(lp.media.bandwidth_gbps, 10) * 1e9
        serial_ms = MTU_BITS / bw_bps * 1000
        one_way = lp.media.latency_ms + 2 * DEVICE_LATENCY_MS + serial_ms
        rtt = round(2 * one_way, 3)
        ok = budget is None or rtt <= budget
        out.append({"link": lp.name, "path": lp.path, "one_way_ms": round(one_way, 4),
                    "rtt_ms": rtt, "budget_ms": budget, "ok": ok})
        if budget is not None:
            log.add("Latency", lp.name, f"RTT {rtt} ms {'<=' if ok else '>'} {budget} ms",
                    f"One-way = propagation/carrier {lp.media.latency_ms} ms + 2 x "
                    f"{DEVICE_LATENCY_MS} ms forwarding + {serial_ms:.4f} ms serialization of a "
                    f"1500-byte frame at {lp.media.bandwidth_gbps:g} Gb/s = {one_way:.4f} ms; RTT = "
                    f"{rtt} ms. {'Within' if ok else 'VIOLATES'} the sub-{budget:g} ms budget "
                    f"{'on this ' + lp.path + ' path' if ok else '- re-route or shorten the path'}.",
                    ["ITU-T G.114 (delay planning)"])
    return out


def _routed_rationale(params: dict, log: RationaleLog, routing: RoutingPlan) -> None:
    if params.get("resiliency") == "dual-homed":
        log.add("Resiliency", "Dual-homed failover", "Primary cost 10 / secondary cost 100",
                "Every remote site has two physically diverse paths. Explicit OSPF costs make the "
                "dark-fiber path primary; the EVPL path stays in the LSDB as a hot standby. When "
                "BFD declares the primary down, SPF selects the secondary with no manual action.",
                ["RFC 2328", "RFC 5880"])
    if params.get("qos"):
        log.add("QoS", "Metro QoS policy", "LLQ: EF priority 20%, AF41 40%, fair-queue rest",
                "Voice (DSCP EF) gets a strict-priority queue capped at 20% so jitter stays low "
                "without starving other classes; FinTech trading flows (DSCP AF41 or any flow to "
                "the colo trading subnet) get a 40% bandwidth guarantee; everything else uses "
                "fair-queueing. Applied outbound on every metro interface because congestion "
                "happens at egress.", ["RFC 4594", "RFC 3246", "RFC 2597"])
    cloud = params.get("cloud")
    if cloud:
        log.add("Security", "Cloud VPN", "IKEv2 + IPsec VTI (AES-256, SHA-256, DH14, PFS)",
                f"Traffic to {cloud['name']} crosses the public Internet, so it is encrypted in an "
                f"IPsec tunnel. A route-based VTI (instead of a crypto-map) lets eBGP run over the "
                f"tunnel and fail over dynamically. TCP MSS is clamped to 1379 bytes so ESP + outer-IP "
                f"tunnel overhead never fragments 1500-byte packets.", ["RFC 7296", "RFC 4301", "RFC 4303"])
