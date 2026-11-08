"""Explainable Exporter: config bundle, per-device files, rationale report, plan JSON."""

from __future__ import annotations

import json
from pathlib import Path

from .engine import Plan
from .vlsm import int_to_ip


def report_markdown(plan: Plan) -> str:
    p = plan.params
    L: list[str] = [f"# NetArchitect Design Report - {p['name']}", "",
                    f"- **Profile:** {p['profile']}", f"- **Root prefix:** {p['root_prefix']}",
                    f"- **Topology tier:** {plan.topology}",
                    f"- **Routing:** {plan.routing.igp}"
                    + (f" + eBGP AS{plan.routing.local_asn}<->AS{plan.routing.peer_asn}"
                       if plan.routing.ebgp else ""),
                    f"- **Devices configured:** {', '.join(plan.configs)}", ""]
    if plan.warnings:
        L += ["> **Warnings:** " + "; ".join(plan.warnings), ""]

    L += ["## Physical media & transceivers", "",
          "| Link | Distance | Media | Transceiver | Lanes | Loss / Budget (dB) | Attenuator |",
          "|---|---|---|---|---|---|---|"]
    for m in plan.media:
        lb = f"{m.loss_db} / {m.budget_db}" if m.loss_db is not None else "-"
        dist = f"{m.distance_m / 1000:,.1f} km" if m.distance_m >= 1000 else f"{m.distance_m:g} m"
        L.append(f"| {m.link} | {dist} | {m.media} | {m.transceiver} | {m.lanes} | "
                 f"{lb} | {str(m.attenuator_db) + ' dB' if m.attenuator_db else '-'} |")
    L.append("")

    if plan.site_blocks:
        L += ["## Site summary blocks", "", "| Site | Block | OSPF area |", "|---|---|---|"]
        for name, b in plan.site_blocks.items():
            L.append(f"| {name} | {b.cidr} | {plan.routing.areas.get(name, '-')} |")
        L.append("")

    L += ["## VLSM allocation", "",
          "| Name | Site | VLAN | CIDR | Mask | Wildcard | Gateway | Broadcast | Hosts req/usable | Util % |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for s in sorted(plan.subnets, key=lambda x: x.network):
        L.append(f"| {s.name} | {s.site or '-'} | {s.vlan or '-'} | {s.cidr} | {s.mask} | "
                 f"{s.wildcard} | {s.gateway} | {s.broadcast or '-'} | "
                 f"{s.hosts_requested}/{s.usable} | {s.utilization * 100:.1f} |")
    L.append("")

    if plan.latency:
        L += ["## Latency verification", "", "| Link | Path | One-way ms | RTT ms | Budget | OK |",
              "|---|---|---|---|---|---|"]
        for r in plan.latency:
            L.append(f"| {r['link']} | {r['path']} | {r['one_way_ms']} | {r['rtt_ms']} | "
                     f"{r['budget_ms'] or '-'} | {'yes' if r['ok'] else 'NO'} |")
        L.append("")

    if plan.links:
        L += ["## Interface map", "", "| Link | A side | B side | Transit |", "|---|---|---|---|"]
        for lp in plan.links:
            L.append(f"| {lp.name} | {lp.a} {lp.a_if} | {lp.b} {lp.b_if} | "
                     f"{lp.transit.cidr if lp.transit else '802.1Q trunk'} |")
        L.append("")

    L += ["## Architectural rationale log", "", plan.log.to_markdown()]
    return "\n".join(L)


def plan_json(plan: Plan) -> dict:
    return {
        "name": plan.params["name"], "profile": plan.params["profile"],
        "topology": plan.topology,
        "routing": {"igp": plan.routing.igp, "areas": plan.routing.areas,
                    "ebgp": plan.routing.ebgp, "local_asn": plan.routing.local_asn,
                    "peer_asn": plan.routing.peer_asn, "summarize": plan.routing.summarize,
                    "bfd": plan.routing.bfd},
        "site_blocks": {k: v.cidr for k, v in plan.site_blocks.items()},
        "media": [m.as_dict() for m in plan.media],
        "subnets": [s.as_dict() for s in sorted(plan.subnets, key=lambda x: x.network)],
        "latency": plan.latency, "warnings": plan.warnings,
        "rationale": [e.as_dict() for e in plan.log.entries],
    }


def export(plan: Plan, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    prof = plan.params["profile"]
    dev_dir = out / prof
    dev_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    bundle = [f"! ===================================================================",
              f"! NetArchitect configuration export - {plan.params['name']}",
              f"! Profile: {prof}   Root: {plan.params['root_prefix']}",
              f"! Topology: {plan.topology}",
              f"! Routing: {plan.routing.igp}" + (" + eBGP" if plan.routing.ebgp else ""),
              f"! Devices: {', '.join(plan.configs)}",
              f"! ==================================================================="]
    for host, cfg in plan.configs.items():
        f = dev_dir / f"{host}.cfg"
        f.write_text(cfg + "\n", encoding="utf-8")
        written.append(f)
        bundle += ["", f"! ######## DEVICE: {host} ########", cfg]
    bf = out / f"{prof}_configs.txt"
    bf.write_text("\n".join(bundle) + "\n", encoding="utf-8")
    written.insert(0, bf)

    rf = out / f"{prof}_report.md"
    rf.write_text(report_markdown(plan), encoding="utf-8")
    jf = out / f"{prof}_plan.json"
    jf.write_text(json.dumps(plan_json(plan), indent=2), encoding="utf-8")
    written += [rf, jf]
    return written
