"""Command-line interface.

Examples:
    python -m netarchitect --preset campus
    python -m netarchitect --preset all --export exports/
    python -m netarchitect --config my_network.json --export out/ --json
    python -m netarchitect --check-link 150 --media copper
    python -m netarchitect --vlsm 192.168.0.0/24 --hosts 100 50 20 2
"""

from __future__ import annotations

import argparse
import json
import sys

from .engine import build_plan
from .errors import NetArchitectError
from .explain import RationaleLog
from .exporter import export, plan_json, report_markdown
from .loader import PRESETS, load_json, load_preset
from .media import decide_media
from .vlsm import allocate


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="netarchitect",
        description="NetArchitect: algorithmic network planning & self-explaining config engine")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--preset", choices=list(PRESETS) + ["all"], help="built-in scenario")
    src.add_argument("--config", metavar="FILE", help="custom parameter JSON file")
    src.add_argument("--check-link", type=float, metavar="METERS",
                     help="run only the L1 media engine for one link distance")
    src.add_argument("--vlsm", metavar="CIDR", help="run only the VLSM allocator on a root prefix")
    src.add_argument("--list-presets", action="store_true")
    ap.add_argument("--media", choices=["copper", "mmf", "smf"], help="requested medium (--check-link)")
    ap.add_argument("--bandwidth", type=float, default=10, help="Gb/s (--check-link)")
    ap.add_argument("--hosts", type=int, nargs="+", help="host counts (--vlsm)")
    ap.add_argument("--export", metavar="DIR", help="write configs, report and plan JSON to DIR")
    ap.add_argument("--json", action="store_true", help="print plan JSON instead of text report")
    ap.add_argument("--show-config", action="store_true", help="print device configs to stdout")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.list_presets:
            for k, v in PRESETS.items():
                print(f"{k:7s} -> {load_preset(k)['name']}  ({v})")
            return 0
        if args.check_link is not None:
            log = RationaleLog()
            d = decide_media({"name": "cli-link", "distance_m": args.check_link,
                              "bandwidth_gbps": args.bandwidth, "media_request": args.media}, log)
            print(f"{d.media} | {d.transceiver} | lanes={d.lanes}")
            print(log.to_text())
            return 0
        if args.vlsm:
            if not args.hosts:
                print("error: --vlsm needs --hosts", file=sys.stderr)
                return 2
            log = RationaleLog()
            reqs = [{"name": f"NET{i + 1}", "hosts": h} for i, h in enumerate(args.hosts)]
            for s in allocate(args.vlsm, reqs, log):
                d = s.as_dict()
                print(f"{d['name']:6s} {d['cidr']:18s} mask {d['mask']:15s} wc {d['wildcard']:15s} "
                      f"gw {d['gateway']:15s} bc {d['broadcast'] or '-':15s} "
                      f"{d['hosts_requested']}/{d['usable']} ({d['utilization_pct']}%)")
            print()
            print(log.to_text())
            return 0

        params_list = ([load_preset(k) for k in PRESETS] if args.preset == "all"
                       else [load_preset(args.preset)] if args.preset
                       else [load_json(args.config)])
        for params in params_list:
            plan = build_plan(params)
            if args.json:
                print(json.dumps(plan_json(plan), indent=2))
            else:
                print(report_markdown(plan))
            if args.show_config:
                for host, cfg in plan.configs.items():
                    print(f"\n! ######## {host} ########\n{cfg}")
            if args.export:
                files = export(plan, args.export)
                print(f"\n[exported] {plan.params['profile']}: " + ", ".join(str(f) for f in files),
                      file=sys.stderr)
        return 0
    except NetArchitectError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
