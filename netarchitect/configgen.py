"""Cisco IOS / IOS-XE configuration generator.

Produces copy-paste-ready configuration for switches (VLANs, trunks, RSTP, LACP),
L3 SVIs, routers (OSPF, BGP, IPsec, QoS, NAT, DHCP) and named extended ACLs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import InvalidParameterError
from .vlsm import Subnet, int_to_ip, mask_str, parse_cidr, wildcard_str

if TYPE_CHECKING:
    from .engine import Plan

CLIENT_ROLES = {"data", "voice", "wireless", "guest", "ap", "iot", "scanners"}


def generate(plan: "Plan") -> dict[str, str]:
    if plan.params["profile"] == "campus_lan":
        return _campus(plan)
    return _routed(plan)


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------
def _header(hostname: str, model: str, profile: str) -> list[str]:
    return [
        f"! NetArchitect generated configuration - {profile}",
        f"! Device: {hostname}   Platform: {model}",
        "! Replace every CHANGE-ME secret before production use.",
        "!",
        "enable",
        "configure terminal",
        f"hostname {hostname}",
        "no ip domain-lookup",
        "ip domain-name netarchitect.local",
        "service password-encryption",
        "enable secret CHANGE-ME-enable",
        "username netadmin privilege 15 secret CHANGE-ME-admin",
        f"banner motd ^Authorized access only - {hostname}^",
        "!",
    ]


def _footer() -> list[str]:
    return [
        "!",
        "crypto key generate rsa modulus 2048",
        "ip ssh version 2",
        "line con 0",
        " logging synchronous",
        " login local",
        "line vty 0 4",
        " login local",
        " transport input ssh",
        "!",
        "end",
        "write memory",
    ]


def _addr(ref: str, plan: "Plan") -> str:
    """Turn an ACL reference into IOS address/wildcard syntax."""
    if ref == "any":
        return "any"
    if ref == "ROOT":
        net, pfx = parse_cidr(plan.params["root_prefix"])
        return f"{int_to_ip(net)} {wildcard_str(pfx)}"
    if ref == "CLOUD":
        cloud = plan.params.get("cloud")
        if not cloud:
            raise InvalidParameterError("ACL references CLOUD but no cloud block is defined")
        net, pfx = parse_cidr(cloud["cidr"])
        return f"{int_to_ip(net)} {wildcard_str(pfx)}"
    sn = plan.subnet(ref)
    if sn.prefix == 32:
        return f"host {int_to_ip(sn.network)}"
    return f"{int_to_ip(sn.network)} {sn.wildcard}"


def render_acl(acl: dict, plan: "Plan") -> list[str]:
    out = [f"ip access-list extended {acl['name']}"]
    for r in acl["rules"]:
        if r.get("remark"):
            out.append(f" remark {r['remark']}")
        proto = r.get("proto", "ip")
        line = f" {r['action']} {proto} {_addr(r['src'], plan)}"
        if "sport" in r:
            if proto not in {"tcp", "udp"}:
                raise InvalidParameterError(f"ACL {acl['name']}: ports need tcp/udp")
            line += f" eq {int(r['sport'])}"
        line += f" {_addr(r['dst'], plan)}"
        if "dport" in r:
            if proto not in {"tcp", "udp"}:
                raise InvalidParameterError(f"ACL {acl['name']}: ports need tcp/udp")
            line += f" eq {int(r['dport'])}"
        if r.get("established"):
            line += " established"
        if r.get("log"):
            line += " log"
        out.append(line)
    out.append("!")
    return out


def _vlan_list(vlans) -> str:
    return ",".join(str(v) for v in sorted(set(vlans)))


def _ospf_net(sn: Subnet, area: int) -> str:
    return f" network {int_to_ip(sn.network)} {sn.wildcard} area {area}"


# ---------------------------------------------------------------------------
# Campus LAN
# ---------------------------------------------------------------------------
def _campus(plan: "Plan") -> dict[str, str]:
    p = plan.params
    site = p["sites"][0]
    dev = p.get("devices", {})
    core = dev.get("core", {})
    acc = dev.get("access", {})
    edge = dev.get("edge", {})
    core_host = core.get("hostname", "CORE-SW1")
    edge_host = edge.get("hostname", "EDGE-RTR1")
    native = p.get("native_vlan", 999)
    parking = p.get("parking_vlan", 998)
    mgmt_vlan = p.get("mgmt_vlan", 99)
    vlan_subnets = [s for s in plan.subnets if s.vlan]
    all_vlans = [s.vlan for s in vlan_subnets]
    servers = next((s for s in vlan_subnets if s.role == "servers"), None)
    dhcp_ip = servers.host(9) if servers else None
    edge_link = next(lp for lp in plan.links if lp.transit is not None)
    acl_by_vlan = {a["apply_vlan"]: a for a in p.get("acls", [])}
    configs: dict[str, str] = {}

    def building_vlans(bname: str) -> list[int]:
        return [s["vlan"] for s in site["subnets"]
                if "vlan" in s and ("buildings" not in s or bname in s["buildings"])]

    # ---------------- core switch ----------------
    c = _header(core_host, core.get("model", "Catalyst 3650"), p["name"])
    c += ["ip routing", "spanning-tree mode rapid-pvst",
          f"spanning-tree vlan {_vlan_list(all_vlans + [native])} priority 4096", "!"]
    for s in vlan_subnets:
        c += [f"vlan {s.vlan}", f" name {s.name}"]
    c += [f"vlan {native}", " name NATIVE-UNUSED", f"vlan {parking}", " name PARKING-UNUSED", "!"]
    for acl in p.get("acls", []):
        c += render_acl(acl, plan)
    for s in vlan_subnets:
        c += [f"interface Vlan{s.vlan}", f" description {s.name} gateway {s.cidr}",
              f" ip address {s.gateway} {s.mask}"]
        if dhcp_ip and s.role in CLIENT_ROLES:
            c.append(f" ip helper-address {dhcp_ip}")
        if s.vlan in acl_by_vlan:
            a = acl_by_vlan[s.vlan]
            c.append(f" ip access-group {a['name']} {a['direction']}")
        c += [" no shutdown", "!"]

    port = 1
    up_tpl = core.get("uplink_ifs", "GigabitEthernet1/0/{n}")
    po = 1
    for b in site["buildings"]:
        lp = next(l for l in plan.links if l.b == f"{b['name']}-ACC1")
        vl = _vlan_list(building_vlans(b["name"]) + ([mgmt_vlan] if mgmt_vlan not in building_vlans(b["name"]) else []))
        members = [up_tpl.format(n=port + i) for i in range(lp.media.lanes)]
        port += lp.media.lanes
        trunk = [" switchport trunk encapsulation dot1q", " switchport mode trunk",
                 f" switchport trunk native vlan {native}", f" switchport trunk allowed vlan {vl}",
                 " switchport nonegotiate"]
        desc = f" description TRUNK to {b['name']}-ACC1 ({lp.media.media}, {lp.media.transceiver}, {lp.media.distance_m:g} m)"
        if len(members) > 1:
            c += [f"interface Port-channel{po}", desc] + trunk + ["!"]
            for m in members:
                c += [f"interface {m}", desc] + trunk + [f" channel-group {po} mode active", " no shutdown", "!"]
            lp.a_if = f"Port-channel{po}"
            po += 1
        else:
            c += [f"interface {members[0]}", desc] + trunk + [" no shutdown", "!"]
            lp.a_if = members[0]
    edge_if = core.get("edge_if", "GigabitEthernet1/0/24")
    edge_link.a_if = edge_if
    lo = plan.loopbacks[core_host]
    c += [f"interface {edge_if}", f" description L3 link to {edge_host}", " no switchport",
          f" ip address {edge_link.transit.host(0)} {edge_link.transit.mask}",
          " ip ospf network point-to-point", " no shutdown", "!",
          "interface Loopback0", f" ip address {lo.gateway} 255.255.255.255", "!",
          "router ospf 1", f" router-id {lo.gateway}", " auto-cost reference-bandwidth 100000",
          " passive-interface default", f" no passive-interface {edge_if}"]
    for s in vlan_subnets + [edge_link.transit, lo]:
        c.append(_ospf_net(s, 0))
    c += ["!"] + _footer()
    configs[core_host] = "\n".join(c)

    # ---------------- access switches (one template per building) ----------
    mgmt = next((s for s in vlan_subnets if s.vlan == mgmt_vlan), None)
    ap_sub = next((s for s in vlan_subnets if s.role == "ap"), None)
    voice = next((s for s in vlan_subnets if s.role == "voice"), None)
    for idx, b in enumerate(site["buildings"]):
        host = f"{b['name']}-ACC1"
        lp = next(l for l in plan.links if l.b == host)
        bv = building_vlans(b["name"])
        if mgmt_vlan not in bv:
            bv.append(mgmt_vlan)
        data_vlan = b.get("data_vlan", bv[0])
        a = _header(host, acc.get("model", "Catalyst 2960"), p["name"])
        a += ["spanning-tree mode rapid-pvst", "!"]
        for s in vlan_subnets:
            if s.vlan in bv:
                a += [f"vlan {s.vlan}", f" name {s.name}"]
        a += [f"vlan {native}", " name NATIVE-UNUSED", f"vlan {parking}", " name PARKING-UNUSED", "!"]
        a += [f"interface range {acc.get('access_range', 'FastEthernet0/1 - 20')}",
              " description USER PORTS (PC + IP phone)", " switchport mode access",
              f" switchport access vlan {data_vlan}"]
        if voice:
            a.append(f" switchport voice vlan {voice.vlan}")
        a += [" switchport nonegotiate", " spanning-tree portfast", " spanning-tree bpduguard enable",
              " no shutdown", "!"]
        if ap_sub:
            a += [f"interface range {acc.get('ap_range', 'FastEthernet0/21 - 22')}",
                  " description PoE ACCESS POINTS", " switchport mode access",
                  f" switchport access vlan {ap_sub.vlan}", " switchport nonegotiate",
                  " spanning-tree portfast", " spanning-tree bpduguard enable", " no shutdown", "!"]
        a += [f"interface range {acc.get('unused_range', 'FastEthernet0/23 - 24')}",
              " description UNUSED - parked and shut", " switchport mode access",
              f" switchport access vlan {parking}", " shutdown", "!"]
        tpl = acc.get("uplink_ifs", "GigabitEthernet0/{n}")
        members = [tpl.format(n=i + 1) for i in range(lp.media.lanes)]
        trunk = [" switchport mode trunk", f" switchport trunk native vlan {native}",
                 f" switchport trunk allowed vlan {_vlan_list(bv)}", " switchport nonegotiate"]
        desc = f" description UPLINK to {core_host} ({lp.media.media})"
        if len(members) > 1:
            a += ["interface Port-channel1", desc] + trunk + ["!"]
            for m in members:
                a += [f"interface {m}", desc] + trunk + [" channel-group 1 mode active", " no shutdown", "!"]
            lp.b_if = "Port-channel1"
        else:
            a += [f"interface {members[0]}", desc] + trunk + [" no shutdown", "!"]
            lp.b_if = members[0]
        if mgmt:
            a += [f"interface Vlan{mgmt.vlan}", " description switch management",
                  f" ip address {mgmt.host(10 + idx)} {mgmt.mask}", " no shutdown", "!",
                  f"ip default-gateway {mgmt.gateway}"]
        a += _footer()
        configs[host] = "\n".join(a)

    # ---------------- edge router ----------------
    root_net, root_pfx = parse_cidr(p["root_prefix"])
    elo = plan.loopbacks[edge_host]
    core_if = edge.get("core_if", "GigabitEthernet0/0/0")
    isp_if = edge.get("isp_if", "GigabitEthernet0/0/1")
    edge_link.b_if = core_if
    e = _header(edge_host, edge.get("model", "ISR4331"), p["name"])
    e += [f"interface {core_if}", f" description L3 link to {core_host}",
          f" ip address {edge_link.transit.host(1)} {edge_link.transit.mask}",
          " ip ospf network point-to-point", " ip nat inside", " no shutdown", "!",
          f"interface {isp_if}", " description ISP uplink",
          f" ip address {edge.get('isp_ip', '203.0.113.2')} {edge.get('isp_mask', '255.255.255.252')}",
          " ip nat outside", " no shutdown", "!",
          "interface Loopback0", f" ip address {elo.gateway} 255.255.255.255", "!",
          "ip access-list standard NAT-INSIDE",
          f" permit {int_to_ip(root_net)} {wildcard_str(root_pfx)}", "!",
          f"ip nat inside source list NAT-INSIDE interface {isp_if} overload",
          f"ip route 0.0.0.0 0.0.0.0 {edge.get('isp_gw', '203.0.113.1')}", "!",
          "router ospf 1", f" router-id {elo.gateway}", " auto-cost reference-bandwidth 100000",
          " passive-interface default", f" no passive-interface {core_if}",
          _ospf_net(edge_link.transit, 0), _ospf_net(elo, 0),
          " default-information originate", "!"]
    e += _footer()
    configs[edge_host] = "\n".join(e)
    return configs


# ---------------------------------------------------------------------------
# Metro MAN / Global WAN (routed)
# ---------------------------------------------------------------------------
def _routed(plan: "Plan") -> dict[str, str]:
    p = plan.params
    rdev = p.get("devices", {}).get("router", {})
    lan_if = rdev.get("lan_if", "GigabitEthernet0/0")
    tpl = rdev.get("link_ifs", "GigabitEthernet{n}/0")
    sites = p["sites"]
    hq = plan.inventory["hq"]
    hq_router = next(s["router"] for s in sites if s["name"] == hq)
    routing = plan.routing
    cloud = p.get("cloud")
    hq_servers = next((s for s in plan.subnets if s.site == hq and s.role == "servers"), None)
    dns = hq_servers.host(9) if hq_servers else "1.1.1.1"

    # interface assignment per router
    counters = {s["router"]: 1 for s in sites}
    for lp in plan.links:
        lp.a_if = tpl.format(n=counters[lp.a]); counters[lp.a] += 1
        lp.b_if = tpl.format(n=counters[lp.b]); counters[lp.b] += 1

    trading = [s for s in plan.subnets if s.role == "trading"]
    configs: dict[str, str] = {}
    for site in sites:
        r = site["router"]
        area = routing.areas[site["name"]]
        lo = plan.loopbacks[r]
        lans = [s for s in plan.subnets if s.site == site["name"] and s.vlan]
        c = _header(r, rdev.get("model", "ISR4331"), p["name"])

        # DHCP for client VLANs (router is the local DHCP server)
        for s in lans:
            if s.role in CLIENT_ROLES:
                c += [f"ip dhcp excluded-address {s.host(0)} {s.host(9)}",
                      f"ip dhcp pool {s.name}", f" network {int_to_ip(s.network)} {s.mask}",
                      f" default-router {s.gateway}", f" dns-server {dns}", "!"]

        if p.get("qos"):
            c += ["class-map match-any VOICE", " match dscp ef",
                  "class-map match-any TRADING", " match dscp af41",
                  " match access-group name TRADING-TRAFFIC", "!",
                  "policy-map METRO-EGRESS-QOS", " class VOICE", "  priority percent 20",
                  " class TRADING", "  bandwidth percent 40", " class class-default",
                  "  fair-queue", "!", "ip access-list extended TRADING-TRAFFIC"]
            for t in trading:
                c += [f" permit ip any {int_to_ip(t.network)} {t.wildcard}",
                      f" permit ip {int_to_ip(t.network)} {t.wildcard} any"]
            if not trading:
                c.append(" remark no trading subnets defined")
            c.append("!")

        site_acls = [a for a in p.get("acls", []) if a.get("site") == site["name"]]
        for acl in site_acls:
            c += render_acl(acl, plan)

        c += ["interface Loopback0", f" ip address {lo.gateway} 255.255.255.255", "!",
              f"interface {lan_if}", " description 802.1Q trunk to site LAN switch",
              " no ip address", " no shutdown", "!"]
        for s in lans:
            c += [f"interface {lan_if}.{s.vlan}", f" description {s.name} {s.cidr}",
                  f" encapsulation dot1Q {s.vlan}", f" ip address {s.gateway} {s.mask}"]
            for acl in site_acls:
                if acl["apply_vlan"] == s.vlan:
                    c.append(f" ip access-group {acl['name']} {acl['direction']}")
            c.append("!")

        my_links = [lp for lp in plan.links if r in (lp.a, lp.b)]
        for lp in my_links:
            is_a = lp.a == r
            ifname = lp.a_if if is_a else lp.b_if
            peer = lp.b if is_a else lp.a
            ip = lp.transit.host(0 if is_a else 1)
            cost = 10 if lp.path == "primary" else 100
            c += [f"interface {ifname}",
                  f" description {lp.path.upper()} to {peer} - {lp.media.media} / "
                  f"{lp.media.transceiver} / {lp.media.distance_m / 1000:g} km",
                  f" ip address {ip} {lp.transit.mask}", " ip ospf network point-to-point",
                  f" ip ospf cost {cost}"]
            if routing.bfd:
                c.append(" bfd interval 300 min_rx 300 multiplier 3")
            if p.get("qos"):
                c.append(" service-policy output METRO-EGRESS-QOS")
            c += [" no shutdown", "!"]

        # cloud edge (hub only)
        if cloud and cloud.get("hub") == site["name"]:
            c += _cloud_edge(plan, rdev)

        c += ["router ospf 1", f" router-id {lo.gateway}",
              " auto-cost reference-bandwidth 100000", " passive-interface default"]
        for lp in my_links:
            c.append(f" no passive-interface {lp.a_if if lp.a == r else lp.b_if}")
        for s in lans + [lo]:
            c.append(_ospf_net(s, area))
        for lp in my_links:
            c.append(_ospf_net(lp.transit, lp.area))
        if r == hq_router and routing.summarize:
            for sname, blk in plan.site_blocks.items():
                a = routing.areas.get(sname, 0)
                if a != 0:
                    c.append(f" area {a} range {int_to_ip(blk.network)} {blk.mask}")
        if routing.bfd:
            c.append(" bfd all-interfaces")
        if cloud and cloud.get("hub") == site["name"]:
            c.append(f" redistribute bgp {routing.local_asn} subnets route-map CLOUD-INTO-OSPF")
        c.append("!")
        c += _footer()
        configs[r] = "\n".join(c)
    return configs


def _cloud_edge(plan: "Plan", rdev: dict) -> list[str]:
    p = plan.params
    cloud = p["cloud"]
    routing = plan.routing
    inet = rdev.get("internet_if", "GigabitEthernet9/0")
    root_net, root_pfx = parse_cidr(p["root_prefix"])
    vpc_net, vpc_pfx = parse_cidr(cloud["cidr"])
    t_net, t_pfx = parse_cidr(cloud.get("tunnel_cidr", "169.254.10.0/30"))
    local_t, peer_t = int_to_ip(t_net + 2), int_to_ip(t_net + 1)
    peer = cloud["peer_public_ip"]
    return [
        f"interface {inet}", " description Internet uplink (IPsec underlay)",
        f" ip address {cloud['local_public_ip']} {cloud.get('local_public_mask', '255.255.255.252')}",
        " no shutdown", "!",
        f"ip route {peer} 255.255.255.255 {cloud['internet_gw']}",
        f"ip route {int_to_ip(root_net)} {mask_str(root_pfx)} Null0 254 name BGP-AGGREGATE-ANCHOR", "!",
        "crypto ikev2 proposal CLOUD-PROP", " encryption aes-cbc-256", " integrity sha256",
        " group 14", "crypto ikev2 policy CLOUD-POL", " proposal CLOUD-PROP", "!",
        "crypto ikev2 keyring CLOUD-KR", " peer CLOUD-VGW", f"  address {peer}",
        f"  pre-shared-key {cloud.get('psk', 'CHANGE-ME-PSK')}", "!",
        "crypto ikev2 profile CLOUD-IKEV2", f" match identity remote address {peer} 255.255.255.255",
        " authentication remote pre-share", " authentication local pre-share",
        " keyring local CLOUD-KR", "!",
        "crypto ipsec transform-set CLOUD-TS esp-aes 256 esp-sha256-hmac", " mode tunnel", "!",
        "crypto ipsec profile CLOUD-IPSEC", " set transform-set CLOUD-TS",
        " set ikev2-profile CLOUD-IKEV2", " set pfs group14", "!",
        "interface Tunnel100", f" description IPsec VTI to {cloud['name']}",
        f" ip address {local_t} {mask_str(t_pfx)}", " ip tcp adjust-mss 1379",
        f" tunnel source {inet}", " tunnel mode ipsec ipv4", f" tunnel destination {peer}",
        " tunnel protection ipsec profile CLOUD-IPSEC", " no shutdown", "!",
        f"ip prefix-list TO-CLOUD seq 5 permit {int_to_ip(root_net)}/{root_pfx}",
        f"ip prefix-list FROM-CLOUD seq 5 permit {int_to_ip(vpc_net)}/{vpc_pfx}", "!",
        "route-map CLOUD-INTO-OSPF permit 10", " match ip address prefix-list FROM-CLOUD", "!",
        f"router bgp {routing.local_asn}", " bgp log-neighbor-changes",
        f" neighbor {peer_t} remote-as {routing.peer_asn}",
        f" neighbor {peer_t} description {cloud['name']}",
        " address-family ipv4",
        f"  network {int_to_ip(root_net)} mask {mask_str(root_pfx)}",
        f"  neighbor {peer_t} activate",
        f"  neighbor {peer_t} prefix-list TO-CLOUD out",
        f"  neighbor {peer_t} prefix-list FROM-CLOUD in",
        " exit-address-family", "!",
    ]
