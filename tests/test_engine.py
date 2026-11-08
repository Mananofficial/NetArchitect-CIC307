"""Presets, parameter validation, routing selection, and generated-config invariants."""
import copy
import json
from pathlib import Path
import ipaddress
import re

import pytest

from netarchitect.cli import main
from netarchitect.engine import build_plan
from netarchitect.errors import AddressOverlapError, InvalidParameterError, NetArchitectError
from netarchitect.explain import RationaleLog
from netarchitect.exporter import export
from netarchitect.loader import PRESETS, load_preset, validate
from netarchitect.routing import select_routing


@pytest.fixture(scope="module", params=list(PRESETS))
def plan(request):
    return build_plan(load_preset(request.param))


# ---------------------------------------------------------------- presets
def test_three_presets_build(plan):
    assert plan.configs and len(plan.log) > 10


def test_every_link_has_media_rationale(plan):
    names = {e.subject for e in plan.log.by_domain("L1 Media")}
    for m in plan.media:
        assert m.link in names


def test_every_subnet_has_rationale(plan):
    names = {e.subject for e in plan.log.by_domain("VLSM")}
    for s in plan.subnets:
        assert s.name in names


def test_rationale_covers_required_domains(plan):
    domains = {e.domain for e in plan.log.entries}
    assert {"L1 Media", "VLSM", "L3 Routing", "Topology"} <= domains


def test_no_overlap_in_presets(plan):
    nets = [ipaddress.ip_network(s.cidr) for s in plan.subnets]
    root = ipaddress.ip_network(plan.params["root_prefix"])
    for i, a in enumerate(nets):
        assert a.subnet_of(root)
        for b in nets[i + 1:]:
            assert not a.overlaps(b)


def test_configs_have_no_unconstrained_trunks(plan):
    for host, cfg in plan.configs.items():
        assert "allowed vlan all" not in cfg
        for block in cfg.split("!"):
            if "switchport mode trunk" in block:
                assert "switchport trunk allowed vlan" in block, host
                assert "switchport nonegotiate" in block, host


def test_ospf_network_wildcards_match_subnets(plan):
    known = {(str(ipaddress.ip_network(s.cidr).network_address),
              str(ipaddress.ip_network(s.cidr).hostmask)) for s in plan.subnets}
    for cfg in plan.configs.values():
        for net, wc in re.findall(r"^ network (\S+) (\S+) area \d+$", cfg, re.M):
            assert (net, wc) in known, (net, wc)


def test_gateway_addresses_are_inside_their_subnets(plan):
    for cfg in plan.configs.values():
        for ip, mask in re.findall(r"^ ip address (\d+\.\d+\.\d+\.\d+) (\d+\.\d+\.\d+\.\d+)$", cfg, re.M):
            iface = ipaddress.ip_interface(f"{ip}/{mask}")
            if iface.network.prefixlen < 31:
                assert iface.ip not in (iface.network.network_address,
                                        iface.network.broadcast_address)


def test_acl_wildcards_are_valid_inverse_masks(plan):
    for cfg in plan.configs.values():
        for net, wc in re.findall(r"(?:permit|deny) \w+ (\d+\.\d+\.\d+\.\d+) (\d+\.\d+\.\d+\.\d+)", cfg):
            ipaddress.ip_network(f"{net}/{wc}")     # raises if wildcard not contiguous/host bits set


def test_export_writes_bundle(plan, tmp_path):
    files = export(plan, tmp_path)
    bundle = files[0].read_text()
    for host in plan.configs:
        assert f"DEVICE: {host}" in bundle
    assert (tmp_path / f"{plan.params['profile']}_report.md").exists()


# ---------------------------------------------------------------- routing
def test_campus_selects_single_area():
    p = build_plan(load_preset("campus"))
    assert p.routing.igp == "OSPF single-area" and set(p.routing.areas.values()) == {0}


def test_man_selects_multi_area_with_bfd_and_summaries():
    p = build_plan(load_preset("man"))
    assert p.routing.igp == "OSPF multi-area" and p.routing.bfd
    hq = p.configs["HQ-RTR1"]
    assert "area 1 range" in hq and "area 2 range" in hq
    assert all(r["ok"] for r in p.latency)


def test_wan_selects_ebgp_and_ipsec():
    p = build_plan(load_preset("wan"))
    assert p.routing.ebgp and p.routing.peer_asn == 64512
    hub = p.configs["DEL-RTR1"]
    assert "tunnel protection ipsec profile" in hub
    assert re.search(r"ip route 10\.50\.0\.0 255\.255\.0\.0 Null0", hub)   # BGP network anchor
    assert "prefix-list FROM-CLOUD in" in hub


def test_single_site_with_50_subnets_goes_multi_area():
    params = {"sites": [{"name": "S", "subnets": []}]}
    plan = select_routing(params, 50, RationaleLog())
    assert plan.igp == "OSPF multi-area"
    plan = select_routing(params, 49, RationaleLog())
    assert plan.igp == "OSPF single-area"


# ---------------------------------------------------------------- validation
def test_cloud_overlap_rejected():
    p = load_preset("wan")
    p["cloud"]["cidr"] = "10.50.128.0/17"
    with pytest.raises(AddressOverlapError):
        validate(p)


def test_dual_homed_requires_two_links():
    p = load_preset("man")
    p["links"] = [l for l in p["links"] if l["name"] != "HQ-REMB-SECONDARY"]
    with pytest.raises(InvalidParameterError, match="dual-homed"):
        validate(p)


@pytest.mark.parametrize("mutate,msg", [
    (lambda p: p.pop("root_prefix"), "root_prefix"),
    (lambda p: p.update(profile="mesh"), "profile"),
    (lambda p: p.update(root_prefix="10.10.0.1/16"), "host bits"),
    (lambda p: p["sites"][0]["subnets"][0].update(vlan=1002), "reserved"),
    (lambda p: p["sites"][0]["subnets"][0].update(vlan=999), "native"),
    (lambda p: p["sites"][0]["subnets"][0].update(hosts=0), "hosts"),
    (lambda p: p["sites"][0].update(endpoints=-1), "density"),
    (lambda p: p.update(resiliency="triple"), "resiliency"),
])
def test_invalid_custom_parameters(mutate, msg):
    p = load_preset("campus")
    mutate(p)
    with pytest.raises(InvalidParameterError, match=msg):
        validate(p)


def test_campus_too_small_root_exhausts():
    p = load_preset("campus")
    p["root_prefix"] = "10.10.0.0/22"
    with pytest.raises(NetArchitectError, match="exhausted|larger than"):
        build_plan(p)


def test_copper_request_in_custom_campus_raises():
    p = load_preset("campus")
    p["sites"][0]["buildings"][1]["uplink"]["media_request"] = "copper"   # 180 m
    with pytest.raises(NetArchitectError, match="100 m"):
        build_plan(p)


# ---------------------------------------------------------------- CLI
def test_cli_check_link_violation_exit_code(capsys):
    assert main(["--check-link", "150", "--media", "copper"]) == 1
    assert "PhysicalDistanceViolationError" in capsys.readouterr().err


def test_cli_vlsm(capsys):
    assert main(["--vlsm", "192.168.0.0/24", "--hosts", "100", "50", "20", "2"]) == 0
    assert "192.168.0.0/25" in capsys.readouterr().out


def test_cli_custom_json(tmp_path, capsys):
    import json
    p = load_preset("man")
    f = tmp_path / "custom.json"
    f.write_text(json.dumps(p))
    assert main(["--config", str(f)]) == 0
    assert main(["--config", str(tmp_path / "missing.json")]) == 1


# ---------------------------------------------------------------- ACL packet-flow audit
def test_ai_v1_mgmt_acl_is_flagged_dead(tmp_path):
    """Regression for ai_audit_log.md Incident 1: outbound SVI ACL matching on src."""
    p = load_preset("campus")
    v1 = json.loads((Path(__file__).parent / "fixtures" / "ai_v1_protect_mgmt.json").read_text())
    p["acls"][1]["rules"] = v1
    with pytest.raises(InvalidParameterError) as exc:
        build_plan(p)
    assert "rule 1" in str(exc.value) and "never crosses the gateway" in str(exc.value)
    assert "replies to sessions opened BY hosts" in str(exc.value)


def test_ai_v1_iot_acl_without_dns_is_flagged():
    """Regression for ai_audit_log.md Incident 2: default-deny IoT ACL with no DNS."""
    p = load_preset("wan")
    p["acls"][0]["rules"] = [r for r in p["acls"][0]["rules"] if r.get("dport") != 53]
    with pytest.raises(InvalidParameterError, match="UDP/53"):
        build_plan(p)


def test_presets_pass_acl_audit(plan):
    assert not [w for w in plan.warnings if "ACL" in w]


def test_custom_example_and_invalid_example():
    from netarchitect.loader import load_json
    root = Path(__file__).resolve().parents[1] / "examples"
    p = build_plan(load_json(root / "custom_two_site.json"))
    assert "single-homed" in p.topology
    from netarchitect.errors import PhysicalDistanceViolationError
    with pytest.raises(PhysicalDistanceViolationError):
        build_plan(load_json(root / "invalid_copper_150m.json"))
