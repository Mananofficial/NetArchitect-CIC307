"""Static packet-flow audit of ACLs before configs are emitted.

An ACL applied to a VLAN gateway interface only ever sees packets travelling in one
direction relative to that VLAN:

* ``in``  -> packets *sourced from* hosts in the VLAN (src must be inside the VLAN)
* ``out`` -> packets *destined to* hosts in the VLAN (dst must be inside the VLAN)

A rule whose src (for ``in``) or dst (for ``out``) cannot fall inside the VLAN subnet
can never match - it is dead code that silently changes the policy. This checker
caught a real AI-generated bug in this project (see ai_audit_log.md, Incident 1).
"""

from __future__ import annotations

from .errors import InvalidParameterError
from .vlsm import overlaps, parse_cidr


def _net(ref: str, plan) -> tuple[int, int] | None:
    if ref == "any":
        return None
    if ref == "ROOT":
        return parse_cidr(plan.params["root_prefix"])
    if ref == "CLOUD":
        return parse_cidr(plan.params["cloud"]["cidr"])
    s = plan.subnet(ref)
    return s.network, s.prefix


def audit_acls(plan) -> list[str]:
    findings: list[str] = []
    for acl in plan.params.get("acls", []):
        site = acl.get("site")
        vlan_sn = next((s for s in plan.subnets if s.vlan == acl["apply_vlan"]
                        and (site is None or s.site == site)), None)
        if vlan_sn is None:
            raise InvalidParameterError(
                f"ACL {acl['name']}: apply_vlan {acl['apply_vlan']} has no subnet")
        side = "src" if acl["direction"] == "in" else "dst"
        other = "dst" if side == "src" else "src"
        for i, r in enumerate(acl["rules"], 1):
            n = _net(r[side], plan)
            if n is not None and not overlaps(n[0], n[1], vlan_sn.network, vlan_sn.prefix):
                findings.append(
                    f"ACL {acl['name']} rule {i} ({r['action']} {r['src']} -> {r['dst']}) is dead: "
                    f"applied '{acl['direction']}' on VLAN {acl['apply_vlan']} ({vlan_sn.cidr}) it only "
                    f"sees packets whose {side} is in {vlan_sn.cidr}, but {side}={r[side]}.")
                continue
            o = _net(r[other], plan)
            if o is not None and o[1] >= vlan_sn.prefix and overlaps(o[0], o[1], vlan_sn.network,
                                                                     vlan_sn.prefix):
                findings.append(
                    f"ACL {acl['name']} rule {i} ({r['action']} {r['src']} -> {r['dst']}) is dead: "
                    f"{other}={r[other]} is inside VLAN {acl['apply_vlan']} itself, and intra-VLAN "
                    f"traffic is switched at L2 - it never crosses the gateway interface.")
        last = acl["rules"][-1]
        default_deny = last["action"] == "deny" and last["src"] == "any" and last["dst"] == "any"
        if acl["direction"] == "out" and default_deny:
            returns = any(r["action"] == "permit" and (r.get("established") or "sport" in r)
                          for r in acl["rules"])
            if not returns:
                findings.append(
                    f"ACL {acl['name']}: default-deny outbound on VLAN {acl['apply_vlan']} has no "
                    f"'established'/source-port rule, so replies to sessions opened BY hosts in the "
                    f"VLAN are dropped on the way back in.")
        if acl["direction"] == "in" and default_deny:
            dns_ok = any(r["action"] == "permit" and r.get("proto") in {"udp", "ip"}
                         and r.get("dport", 53) == 53 for r in acl["rules"][:-1])
            if not dns_ok:
                findings.append(
                    f"ACL {acl['name']}: default-deny inbound on VLAN {acl['apply_vlan']} with no "
                    f"UDP/53 permit - hosts cannot resolve names, so FQDN-based permits never match.")
    return findings
