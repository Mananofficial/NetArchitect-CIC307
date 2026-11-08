"""VLSM allocator: wildcard/mask math across all prefixes, overlap, exhaustion, edge subnets."""
import ipaddress
import random

import pytest

from netarchitect.errors import AddressSpaceExhaustedError, InvalidParameterError
from netarchitect.explain import RationaleLog
from netarchitect.vlsm import (allocate, allocate_hierarchical, int_to_ip, ip_to_int,
                               mask_str, parse_cidr, prefix_for_hosts, prefix_to_mask,
                               usable_hosts, wildcard, wildcard_str)


@pytest.mark.parametrize("p", range(0, 33))
def test_mask_and_wildcard_every_prefix(p):
    net = ipaddress.ip_network(f"0.0.0.0/{p}")
    assert mask_str(p) == str(net.netmask)
    assert wildcard_str(p) == str(net.hostmask)
    assert wildcard(p) >= 0                        # never a negative Python int
    assert prefix_to_mask(p) | wildcard(p) == 0xFFFFFFFF
    assert prefix_to_mask(p) & wildcard(p) == 0


@pytest.mark.parametrize("p,wc", [(0, "255.255.255.255"), (8, "0.255.255.255"),
                                   (23, "0.0.1.255"), (30, "0.0.0.3"),
                                   (31, "0.0.0.1"), (32, "0.0.0.0")])
def test_wildcard_known_values(p, wc):
    assert wildcard_str(p) == wc


@pytest.mark.parametrize("bad", [-1, 33])
def test_prefix_out_of_range(bad):
    with pytest.raises(InvalidParameterError):
        prefix_to_mask(bad)


def test_ip_roundtrip():
    for ip in ["0.0.0.0", "10.0.0.1", "192.168.255.254", "255.255.255.255"]:
        assert int_to_ip(ip_to_int(ip)) == ip


@pytest.mark.parametrize("bad", ["10.0.0", "10.0.0.256", "a.b.c.d", "10.0.0.01"])
def test_bad_ip(bad):
    with pytest.raises(InvalidParameterError):
        ip_to_int(bad)


@pytest.mark.parametrize("cidr", ["10.0.0.1/16", "192.168.1.128/24", "10.0.0.0"])
def test_root_with_host_bits_or_no_prefix_rejected(cidr):
    with pytest.raises(InvalidParameterError):
        parse_cidr(cidr)


@pytest.mark.parametrize("hosts,prefix", [(1, 30), (2, 30), (3, 29), (6, 29), (7, 28),
                                           (62, 26), (63, 25), (126, 25), (127, 24),
                                           (254, 24), (255, 23), (450, 23), (510, 23),
                                           (511, 22)])
def test_prefix_for_hosts_boundaries(hosts, prefix):
    assert prefix_for_hosts(hosts) == prefix
    assert usable_hosts(prefix) >= hosts


def test_p2p_and_loopback_prefixes():
    assert prefix_for_hosts(2, point_to_point=True) == 31
    assert prefix_for_hosts(1, point_to_point=True) == 32


def test_slash31_and_slash32_have_no_broadcast():
    subs = allocate("10.0.0.0/29", [{"name": "p2p", "hosts": 2, "role": "p2p"},
                                    {"name": "lo", "hosts": 1, "role": "loopback"}])
    p2p = next(s for s in subs if s.name == "p2p")
    lo = next(s for s in subs if s.name == "lo")
    assert p2p.prefix == 31 and p2p.broadcast is None and p2p.usable == 2
    assert p2p.host(0) == "10.0.0.0" and p2p.host(1) == "10.0.0.1"
    assert lo.prefix == 32 and lo.usable == 1


def test_largest_first_and_fields():
    subs = allocate("192.168.0.0/24", [{"name": "A", "hosts": 20}, {"name": "B", "hosts": 100},
                                       {"name": "C", "hosts": 50}])
    by = {s.name: s for s in subs}
    assert by["B"].cidr == "192.168.0.0/25"
    assert by["C"].cidr == "192.168.0.128/26"
    assert by["A"].cidr == "192.168.0.192/27"
    assert by["B"].gateway == "192.168.0.1" and by["B"].broadcast == "192.168.0.127"
    assert by["A"].wildcard == "0.0.0.31"


def test_exact_fit_then_exhaustion():
    allocate("10.0.0.0/24", [{"name": "a", "hosts": 126}, {"name": "b", "hosts": 126}])
    with pytest.raises(AddressSpaceExhaustedError, match="exhausted"):
        allocate("10.0.0.0/24", [{"name": "a", "hosts": 126}, {"name": "b", "hosts": 126},
                                 {"name": "c", "hosts": 1}])


def test_single_request_larger_than_root():
    with pytest.raises(AddressSpaceExhaustedError):
        allocate("10.0.0.0/24", [{"name": "big", "hosts": 300}])


def test_slash32_root_cannot_hold_a_lan():
    with pytest.raises(AddressSpaceExhaustedError):
        allocate("10.0.0.1/32", [{"name": "x", "hosts": 1}])


@pytest.mark.parametrize("bad", [0, -3, "ten"])
def test_invalid_host_count(bad):
    with pytest.raises(InvalidParameterError):
        allocate("10.0.0.0/24", [{"name": "x", "hosts": bad}])


@pytest.mark.parametrize("seed", range(40))
def test_random_allocations_never_overlap_and_match_ipaddress(seed):
    rng = random.Random(seed)
    reqs = [{"name": f"n{i}", "hosts": rng.choice([1, 2, 5, 13, 30, 60, 100, 250, 500, 1000, 3000])}
            for i in range(rng.randint(1, 25))]
    reqs += [{"name": f"p{i}", "hosts": 2, "role": "p2p"} for i in range(rng.randint(0, 5))]
    root = "10.0.0.0/16"
    try:
        subs = allocate(root, reqs)
    except AddressSpaceExhaustedError:
        total = sum(1 << (32 - prefix_for_hosts(r["hosts"], r.get("role") == "p2p")) for r in reqs)
        assert total > 65536
        return
    root_net = ipaddress.ip_network(root)
    nets = [ipaddress.ip_network(s.cidr) for s in subs]
    for i, a in enumerate(nets):
        assert a.subnet_of(root_net)
        for b in nets[i + 1:]:
            assert not a.overlaps(b), (a, b)
    for s, n in zip(subs, nets):
        assert s.mask == str(n.netmask) and s.wildcard == str(n.hostmask)
        if s.prefix < 31:
            assert s.broadcast == str(n.broadcast_address)
            assert s.gateway == str(n.network_address + 1)
        assert s.usable >= s.hosts_requested


def test_hierarchical_site_blocks_contain_their_subnets():
    sites = [{"name": "HQ", "subnets": [{"name": "h1", "hosts": 200}, {"name": "h2", "hosts": 50}]},
             {"name": "BR", "subnets": [{"name": "b1", "hosts": 100}, {"name": "lo", "hosts": 1, "role": "loopback"}]}]
    blocks, subs = allocate_hierarchical("10.1.0.0/16", sites)
    for s in subs:
        blk = ipaddress.ip_network(blocks[s.site].cidr)
        assert ipaddress.ip_network(s.cidr).subnet_of(blk)
    b = [ipaddress.ip_network(x.cidr) for x in blocks.values()]
    assert not b[0].overlaps(b[1])


def test_rationale_contains_utilization():
    log = RationaleLog()
    allocate("10.0.0.0/24", [{"name": "users", "hosts": 100}], log)
    assert any("Utilization 100/126" in e.justification for e in log.entries)
