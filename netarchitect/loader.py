"""Input ingestion: preset loading and custom-parameter validation."""

from __future__ import annotations

import json
from pathlib import Path

from .errors import AddressOverlapError, InvalidParameterError
from .vlsm import overlaps, parse_cidr

PRESET_DIR = Path(__file__).parent / "presets"
PRESETS = {
    "campus": "campus_lan.json",
    "man": "metro_man.json",
    "wan": "global_wan.json",
}
PROFILES = {"campus_lan", "metro_man", "global_wan"}
RESILIENCY = {"standard", "dual-homed"}
RESERVED_VLANS = {1, 1002, 1003, 1004, 1005}


def load_preset(name: str) -> dict:
    key = name.lower()
    if key not in PRESETS:
        raise InvalidParameterError(
            f"Unknown preset '{name}'. Choose one of: {', '.join(PRESETS)}")
    return load_json(PRESET_DIR / PRESETS[key])


def load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise InvalidParameterError(f"Parameter file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvalidParameterError(f"{p}: invalid JSON ({exc})") from exc
    validate(data)
    return data


def _int(value, what: str, lo: int | None = None, hi: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise InvalidParameterError(f"{what} must be an integer (got {value!r})")
    v = int(value)
    if lo is not None and v < lo:
        raise InvalidParameterError(f"{what} must be >= {lo} (got {v})")
    if hi is not None and v > hi:
        raise InvalidParameterError(f"{what} must be <= {hi} (got {v})")
    return v


def validate(p: dict) -> None:
    """Validate a parameter set in place. Raises InvalidParameterError on any problem."""
    if not isinstance(p, dict):
        raise InvalidParameterError("Parameter file must be a JSON object")
    for key in ("name", "profile", "root_prefix", "sites"):
        if key not in p:
            raise InvalidParameterError(f"Missing required parameter '{key}'")
    if p["profile"] not in PROFILES:
        raise InvalidParameterError(
            f"profile must be one of {sorted(PROFILES)} (got '{p['profile']}')")
    root_net, root_pfx = parse_cidr(p["root_prefix"])
    if root_pfx < 8 or root_pfx > 30:
        raise InvalidParameterError(f"root_prefix /{root_pfx} must be between /8 and /30")

    res = p.setdefault("resiliency", "standard")
    if res not in RESILIENCY:
        raise InvalidParameterError(f"resiliency must be one of {sorted(RESILIENCY)}")

    sites = p["sites"]
    if not isinstance(sites, list) or not sites:
        raise InvalidParameterError("'sites' must be a non-empty list")
    site_names: set[str] = set()
    subnet_names: set[str] = set()
    native = p.get("native_vlan", 999)
    _int(native, "native_vlan", 2, 4094)
    for s in sites:
        name = s.get("name")
        if not name or name in site_names:
            raise InvalidParameterError(f"Site names must be unique and non-empty ({name!r})")
        site_names.add(name)
        _int(s.get("endpoints", 0), f"site {name}: endpoints (density)", 0, 1_000_000)
        subnets = s.get("subnets")
        if not isinstance(subnets, list) or not subnets:
            raise InvalidParameterError(f"Site {name}: 'subnets' must be a non-empty list")
        vlans: set[int] = set()
        for sn in subnets:
            sname = sn.get("name")
            if not sname or sname in subnet_names:
                raise InvalidParameterError(f"Subnet names must be globally unique ({sname!r})")
            subnet_names.add(sname)
            _int(sn.get("hosts"), f"subnet {sname}: hosts", 1, 16_777_214)
            if "vlan" in sn:
                v = _int(sn["vlan"], f"subnet {sname}: vlan", 2, 4094)
                if v in RESERVED_VLANS:
                    raise InvalidParameterError(f"subnet {sname}: VLAN {v} is reserved")
                if v == native:
                    raise InvalidParameterError(
                        f"subnet {sname}: VLAN {v} collides with the unused native VLAN")
                if v in vlans:
                    raise InvalidParameterError(f"Site {name}: duplicate VLAN {v}")
                vlans.add(v)
        for b in s.get("buildings", []):
            _int(b.get("endpoints", 0), f"building {b.get('name')}: endpoints", 0, 100_000)
            _int(b.get("aps", 0), f"building {b.get('name')}: aps", 0, 10_000)
            for k in ("drop_distance_m",):
                if k in b and (not isinstance(b[k], (int, float)) or b[k] <= 0):
                    raise InvalidParameterError(f"building {b.get('name')}: {k} must be > 0")

    if p["profile"] == "campus_lan":
        if len(sites) != 1 or not sites[0].get("buildings"):
            raise InvalidParameterError("campus_lan profile needs exactly one site with 'buildings'")
        if sum(1 for b in sites[0]["buildings"] if b.get("core")) != 1:
            raise InvalidParameterError("campus_lan: exactly one building must have core=true")
    else:
        links = p.get("links", [])
        if not links:
            raise InvalidParameterError(f"{p['profile']}: at least one inter-site link is required")
        for ln in links:
            for end in ("a", "b"):
                if ln.get(end) not in site_names:
                    raise InvalidParameterError(
                        f"link {ln.get('name')}: endpoint '{ln.get(end)}' is not a defined site")
        if res == "dual-homed":
            hq = next((s["name"] for s in sites if s.get("role") == "hq"), sites[0]["name"])
            for s in sites:
                if s["name"] == hq:
                    continue
                n = sum(1 for ln in links if s["name"] in (ln["a"], ln["b"]))
                if n < 2:
                    raise InvalidParameterError(
                        f"resiliency=dual-homed but site {s['name']} has only {n} uplink(s); "
                        f"two diverse paths are required")

    if "latency_budget_ms" in p:
        lb = p["latency_budget_ms"]
        if not isinstance(lb, (int, float)) or lb <= 0:
            raise InvalidParameterError("latency_budget_ms must be > 0")

    cloud = p.get("cloud")
    if cloud:
        c_net, c_pfx = parse_cidr(cloud["cidr"])
        if overlaps(root_net, root_pfx, c_net, c_pfx):
            raise AddressOverlapError(
                f"Cloud VPC {cloud['cidr']} overlaps enterprise root {p['root_prefix']}; "
                f"overlapping space cannot be routed over the IPsec tunnel without NAT.")
        if cloud.get("hub") not in site_names:
            raise InvalidParameterError("cloud.hub must name a defined site")
