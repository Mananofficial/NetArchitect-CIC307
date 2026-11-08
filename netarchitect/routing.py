"""L3 routing-protocol and topology-tier selection with rationale."""

from __future__ import annotations

from dataclasses import dataclass, field

from .explain import RationaleLog

SINGLE_AREA_SUBNET_LIMIT = 50


@dataclass
class RoutingPlan:
    igp: str                       # "OSPF single-area" | "OSPF multi-area"
    areas: dict[str, int]          # site name -> OSPF area id
    ebgp: bool = False
    local_asn: int | None = None
    peer_asn: int | None = None
    summarize: bool = False
    bfd: bool = False
    notes: list[str] = field(default_factory=list)


def select_routing(params: dict, subnet_count: int, log: RationaleLog) -> RoutingPlan:
    sites = params["sites"]
    site_names = [s["name"] for s in sites]
    cloud = params.get("cloud")
    multi_site = len(sites) > 1

    if not multi_site and subnet_count < SINGLE_AREA_SUBNET_LIMIT and not cloud:
        plan = RoutingPlan("OSPF single-area", {site_names[0]: 0})
        log.add("L3 Routing", "Interior gateway protocol", "OSPFv2 Area 0 (single area)",
                f"One site / one autonomous system with {subnet_count} subnets "
                f"(< {SINGLE_AREA_SUBNET_LIMIT}). A single backbone area keeps every router's "
                f"LSDB identical and small, so SPF (Dijkstra) runs in milliseconds and link-state "
                f"flooding gives sub-second convergence after a failure. Multi-area design would "
                f"add ABR complexity with no scaling benefit at this size; distance-vector "
                f"protocols (RIP) were rejected for slow, hop-count-limited convergence.",
                ["RFC 2328"])
        return plan

    # ---- multi-area: first site with role hq is the backbone ------------
    hq = next((s["name"] for s in sites if s.get("role") == "hq"), site_names[0])
    areas: dict[str, int] = {}
    next_area = 1
    for s in sites:
        if s["name"] == hq or s.get("area") == 0:
            areas[s["name"]] = 0
        else:
            areas[s["name"]] = int(s.get("area", next_area))
            next_area = max(next_area, areas[s["name"]]) + 1
    plan = RoutingPlan("OSPF multi-area", areas, summarize=True,
                       bfd=params.get("resiliency") == "dual-homed")
    reason = (f"{len(sites)} geographically separate sites" if multi_site else
              f"{subnet_count} subnets (>= {SINGLE_AREA_SUBNET_LIMIT})")
    area_txt = ", ".join(f"{k}=Area {v}" for k, v in areas.items())
    log.add("L3 Routing", "Interior gateway protocol", "OSPFv2 multi-area",
            f"Design spans {reason}. Each remote site gets its own area ({area_txt}) attached "
            f"to backbone Area 0 at {hq}. This isolates routing domains: a flapping metro/WAN "
            f"link only triggers SPF inside its own area, while other areas receive a single "
            f"Type-3 summary LSA from the ABR. Combined with per-site summary blocks this keeps "
            f"LSDB size and SPF cost bounded as sites grow.", ["RFC 2328 s.3", "RFC 3101"])
    log.add("L3 Routing", "Route summarization", "ABR 'area range' per site block",
            "Hierarchical VLSM gave every site one contiguous power-of-two block, so the ABR "
            "advertises exactly one summary per area instead of every VLAN. Summaries hide "
            "internal flaps from the rest of the network and shrink every routing table.",
            ["RFC 4632", "RFC 2328 s.12.4.3"])
    if plan.bfd:
        log.add("L3 Routing", "Failure detection", "BFD 300 ms x 3 on WAN/MAN links",
                "Resiliency is 'dual-homed': OSPF's default dead interval (40 s) is far too "
                "slow for a FinTech/latency-sensitive network. BFD detects a dead path in "
                "<= 900 ms and tells OSPF to reconverge onto the secondary path immediately.",
                ["RFC 5880", "RFC 5882"])

    if cloud:
        plan.ebgp = True
        plan.local_asn = int(params.get("asn", 65001))
        plan.peer_asn = int(cloud.get("asn", 64512))
        log.add("L3 Routing", f"Cloud boundary ({cloud.get('name', 'cloud')})",
                f"eBGP AS{plan.local_asn} <-> AS{plan.peer_asn} over IPsec",
                f"The cloud VPC is a separate administrative/routing domain; OSPF must not "
                f"extend into a provider's network. eBGP gives policy control (prefix-lists, "
                f"AS-path) and is what cloud VPN gateways speak natively. Only the enterprise "
                f"aggregate is advertised (anchored with a Null0 route so it is always in the "
                f"RIB), and only the VPC CIDR {cloud['cidr']} is accepted. Private ASNs from "
                f"RFC 6996 are used.", ["RFC 4271", "RFC 6996", "RFC 4301"])
    return plan


def select_topology(params: dict, log: RationaleLog) -> str:
    profile = params.get("profile", "custom")
    endpoints = sum(int(s.get("endpoints", 0)) for s in params["sites"])
    buildings = sum(len(s.get("buildings", [])) for s in params["sites"])
    sites = len(params["sites"])
    if sites == 1:
        if buildings <= 3 and endpoints <= 2000:
            tier = "Collapsed core (2-tier: core/distribution + access)"
            why = (f"{buildings} buildings and {endpoints} endpoints on one campus: a separate "
                   f"distribution layer would add a switch pair per building without improving "
                   f"fault isolation. The L3 core switch acts as distribution, terminating every "
                   f"VLAN's SVI, while access switches stay pure L2 with RSTP.")
        else:
            tier = "Three-tier (core / distribution / access)"
            why = (f"{buildings} buildings / {endpoints} endpoints exceeds collapsed-core "
                   f"limits; per-building distribution contains broadcast and STP domains.")
    elif params.get("cloud"):
        tier = "Hub-and-spoke WAN with cloud transit at hub"
        why = (f"{sites} cities plus a cloud VPC: HQ is the OSPF backbone and the single "
               f"controlled egress to the cloud (IPsec + eBGP), so security policy is enforced "
               f"in one place and remote areas only need a path to the hub.")
    elif params.get("resiliency") != "dual-homed":
        tier = "Hub-and-spoke MAN (single-homed)"
        why = (f"{sites} metro sites with resiliency='standard': each remote site has one path "
               f"to the HQ hub. A fiber cut isolates that site until repair; set "
               f"resiliency='dual-homed' and add a second diverse link to remove that risk.")
    else:
        tier = "Dual-homed hub-and-spoke MAN"
        why = (f"{sites} metro sites: each remote site is dual-homed to the HQ hub over two "
               f"physically diverse paths (primary dark fiber, secondary carrier EVPL) so a "
               f"single fiber cut never isolates a site.")
    log.add("Topology", f"Profile '{profile}'", tier, why, ["Cisco SAFE/Campus design guides"])
    return tier
