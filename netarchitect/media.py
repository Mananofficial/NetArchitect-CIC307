"""L1/L2 Media Engine: distance- and bandwidth-driven media + transceiver selection.

Rules (from the CIC-307 specification):
    run <= 100 m           -> Cat6a, 10GBASE-T           (IEEE 802.3an channel limit)
    100 m < run <= 400 m   -> OM4 MMF, 10GBASE-SR        (850 nm modal-dispersion limit)
    run > 400 m            -> OS2 SMF, 10GBASE-LR/ER(/ZR) chosen by optical power budget
    copper requested > 100 m -> PhysicalDistanceViolationError

Optical values are typical SFP+ datasheet / IEEE 802.3ae figures and are kept in
one table so they can be audited (see ai_audit_log.md).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .errors import (InvalidParameterError, OpticalBudgetError,
                     PhysicalDistanceViolationError)
from .explain import RationaleLog

COPPER_MAX_M = 100.0          # IEEE 802.3an: 90 m permanent link + 10 m patch cords
OM4_SR_MAX_M = 400.0          # IEEE 802.3ae 10GBASE-SR over OM4 (4700 MHz*km EMB)
FIBER_DELAY_US_PER_KM = 4.9   # c / n (n ~= 1.468) -> ~204,000 km/s
COPPER_DELAY_US_PER_KM = 5.3  # NVP ~0.63c for Cat6a

# Plant loss model
OM4_ATTEN_DB_PER_KM = 3.0     # @850 nm (TIA-568.3-D allows 3.0 dB/km for OM4)
OM4_SR_CHANNEL_LOSS_DB = 2.9  # 10GBASE-SR max channel insertion loss on OM4 @400 m
SMF_ATTEN_DB_PER_KM = {1310: 0.35, 1550: 0.25}  # ITU-T G.652.D cabled, typical
CONNECTOR_LOSS_DB = 0.5       # mated LC/UPC pair, typical
SPLICE_LOSS_DB = 0.1          # fusion splice
SPLICE_INTERVAL_KM = 5.0      # one fusion splice per cable reel (~5 km)
DEFAULT_MARGIN_DB = 3.0       # ageing, repairs, temperature


@dataclass(frozen=True)
class Optic:
    name: str
    standard: str
    wavelength_nm: int
    reach_km: float
    tx_min_dbm: float
    tx_max_dbm: float
    rx_sens_dbm: float
    rx_overload_dbm: float

    @property
    def budget_db(self) -> float:
        # Worst case: weakest transmitter vs. least sensitive receiver.
        return round(self.tx_min_dbm - self.rx_sens_dbm, 2)


SMF_OPTICS = [
    Optic("10GBASE-LR", "IEEE 802.3ae cl.52", 1310, 10, -8.2, 0.5, -14.4, 0.5),
    Optic("10GBASE-ER", "IEEE 802.3ae cl.52", 1550, 40, -4.7, 4.0, -15.8, -1.0),
    Optic("10G-ZR", "SFF MSA (non-IEEE)", 1550, 80, 0.0, 4.0, -24.0, -7.0),
]


@dataclass
class MediaDecision:
    link: str
    distance_m: float
    media: str
    transceiver: str
    standard: str
    wavelength_nm: int | None
    lanes: int
    bandwidth_gbps: float
    loss_db: float | None = None
    budget_db: float | None = None
    margin_db: float | None = None
    attenuator_db: int = 0
    latency_ms: float = 0.0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def _validate(link: dict) -> tuple[str, float, float, str | None]:
    name = str(link.get("name", "unnamed-link"))
    try:
        dist = float(link["distance_m"])
    except (KeyError, TypeError, ValueError):
        raise InvalidParameterError(f"Link '{name}': distance_m is missing or not numeric")
    if not math.isfinite(dist) or dist <= 0:
        raise InvalidParameterError(f"Link '{name}': distance_m must be > 0 (got {dist})")
    bw = float(link.get("bandwidth_gbps", 10))
    if not math.isfinite(bw) or bw <= 0:
        raise InvalidParameterError(f"Link '{name}': bandwidth_gbps must be > 0 (got {bw})")
    req = link.get("media_request")
    if req is not None:
        req = str(req).lower()
        if req not in {"copper", "mmf", "smf"}:
            raise InvalidParameterError(
                f"Link '{name}': media_request must be copper|mmf|smf (got {req})")
    return name, dist, bw, req


def smf_link_loss(distance_km: float, wavelength_nm: int, connectors: int = 2,
                  splices: int | None = None) -> float:
    """Total passive loss of an OS2 span in dB."""
    if splices is None:
        splices = max(0, math.ceil(distance_km / SPLICE_INTERVAL_KM) - 1)
    loss = (distance_km * SMF_ATTEN_DB_PER_KM[wavelength_nm]
            + connectors * CONNECTOR_LOSS_DB + splices * SPLICE_LOSS_DB)
    return round(loss, 2)


def propagation_ms(distance_m: float, fiber: bool = True) -> float:
    per_km = FIBER_DELAY_US_PER_KM if fiber else COPPER_DELAY_US_PER_KM
    return round(distance_m / 1000.0 * per_km / 1000.0, 4)


def _lanes(bw: float) -> int:
    return max(1, math.ceil(bw / 10.0))


def decide_media(link: dict, log: RationaleLog | None = None) -> MediaDecision:
    log = log if log is not None else RationaleLog()
    name, dist, bw, req = _validate(link)
    lanes = _lanes(bw)
    connectors = int(link.get("connectors", 2))
    margin = float(link.get("margin_db", DEFAULT_MARGIN_DB))

    # ---- explicit-request boundary checks -------------------------------
    if req == "copper" and dist > COPPER_MAX_M:
        raise PhysicalDistanceViolationError(
            f"Link '{name}': copper requested for {dist:g} m, but IEEE 802.3an limits a "
            f"10GBASE-T channel to {COPPER_MAX_M:g} m. Beyond this, insertion loss and "
            f"alien crosstalk degrade SNR below the PAM-16 receiver threshold (signal "
            f"attenuation warning). Use OM4 MMF (<=400 m) or OS2 SMF instead.")
    if req == "mmf" and dist > OM4_SR_MAX_M:
        raise PhysicalDistanceViolationError(
            f"Link '{name}': OM4 multimode requested for {dist:g} m, but modal dispersion "
            f"limits 10GBASE-SR on OM4 to {OM4_SR_MAX_M:g} m. Use OS2 single-mode fiber.")

    # ---- carrier service (EVPL / EPL / MPLS) ---------------------------
    service = link.get("service")
    if service:
        optic = "1000BASE-LX SFP" if bw <= 1 else "10GBASE-LR SFP+"
        carrier_ms = float(link.get("carrier_latency_ms", 0.5))
        d = MediaDecision(name, dist, f"Carrier {service} (MEF E-Line)",
                          f"{optic} to carrier NID", "MEF 6.2 / IEEE 802.3", 1310, lanes, bw,
                          latency_ms=round(propagation_ms(dist) + carrier_ms, 4))
        log.add("L1 Media", name, f"Carrier {service} handoff ({optic})",
                f"This path is a carrier {service} (Ethernet Virtual Private Line, MEF E-Line) "
                f"over {dist / 1000:g} km of provider fiber, chosen as the physically diverse "
                f"secondary path so a single dark-fiber cut cannot isolate the site. The provider "
                f"owns the optical budget; the enterprise only needs a short single-mode "
                f"{optic} handoff to the carrier NID. EVPL is VLAN-aware, so the service can "
                f"carry 802.1Q-tagged traffic. Estimated one-way latency "
                f"{d.latency_ms} ms ({propagation_ms(dist)} ms propagation + {carrier_ms} ms "
                f"carrier switching).", ["MEF 6.2", "MEF 10.4", "IEEE 802.1Q"])
        _lag_note(d, log)
        return d

    # ---- copper ---------------------------------------------------------
    if req == "copper" or (req is None and dist <= COPPER_MAX_M):
        d = MediaDecision(name, dist, "Cat6a U/FTP", "10GBASE-T (RJ45)", "IEEE 802.3an",
                          None, lanes, bw, latency_ms=propagation_ms(dist, fiber=False))
        log.add("L1 Media", name, "Cat6a / 10GBASE-T",
                f"Run of {dist:g} m is within the {COPPER_MAX_M:g} m 10GBASE-T channel limit "
                f"(90 m permanent link + 10 m cords). Cat6a's 500 MHz rating supports 10 Gb/s "
                f"over the full length and carries IEEE 802.3bt PoE (up to 90 W) for APs, "
                f"phones and cameras; fiber would add transceiver cost with no reach benefit.",
                ["IEEE 802.3an", "IEEE 802.3bt", "ANSI/TIA-568.2-D"])
        _lag_note(d, log)
        return d

    # ---- multimode ------------------------------------------------------
    if req == "mmf" or (req is None and dist <= OM4_SR_MAX_M):
        loss = round(dist / 1000 * OM4_ATTEN_DB_PER_KM + connectors * CONNECTOR_LOSS_DB, 2)
        if loss <= OM4_SR_CHANNEL_LOSS_DB:
            d = MediaDecision(name, dist, "OM4 MMF (50/125 um)", "10GBASE-SR SFP+",
                              "IEEE 802.3ae cl.52", 850, lanes, bw, loss_db=loss,
                              budget_db=OM4_SR_CHANNEL_LOSS_DB,
                              margin_db=round(OM4_SR_CHANNEL_LOSS_DB - loss, 2),
                              latency_ms=propagation_ms(dist))
            log.add("L1 Media", name, "OM4 MMF / 10GBASE-SR",
                    f"Run of {dist:g} m exceeds the {COPPER_MAX_M:g} m copper limit "
                    f"(IEEE 802.3an) but is within the {OM4_SR_MAX_M:g} m reach of 10GBASE-SR "
                    f"on OM4. At 850 nm the low-cost VCSEL source is limited by modal "
                    f"dispersion, not loss; OM4's 4700 MHz*km effective modal bandwidth "
                    f"sustains 10 Gb/s to 400 m. Channel loss {loss} dB "
                    f"({dist/1000:.3f} km x {OM4_ATTEN_DB_PER_KM} dB/km + {connectors} x "
                    f"{CONNECTOR_LOSS_DB} dB connectors) <= {OM4_SR_CHANNEL_LOSS_DB} dB "
                    f"SR budget.", ["IEEE 802.3ae", "TIA-492AAAD (OM4)", "TIA-568.3-D"])
            _lag_note(d, log)
            return d
        if req == "mmf":
            raise OpticalBudgetError(
                f"Link '{name}': OM4 channel loss {loss} dB exceeds the 10GBASE-SR budget of "
                f"{OM4_SR_CHANNEL_LOSS_DB} dB (too many connectors). Reduce patch points or use OS2.")
        log.add("L1 Media", name, "Escalated to OS2",
                f"OM4 loss of {loss} dB exceeds the {OM4_SR_CHANNEL_LOSS_DB} dB SR budget "
                f"because of {connectors} connectors, so the link is escalated to single-mode.",
                ["IEEE 802.3ae"])

    # ---- single-mode ----------------------------------------------------
    km = dist / 1000.0
    for optic in SMF_OPTICS:
        if km > optic.reach_km:
            continue
        loss = smf_link_loss(km, optic.wavelength_nm, connectors, link.get("splices"))
        if loss + margin > optic.budget_db:
            log.add("L1 Media", name, f"Rejected {optic.name}",
                    f"{optic.name} reach ({optic.reach_km:g} km) covers {km:g} km, but loss "
                    f"{loss} dB + {margin} dB safety margin = {loss + margin:.2f} dB exceeds its "
                    f"{optic.budget_db} dB power budget.", [optic.standard])
            continue
        rx_max = optic.tx_max_dbm - loss
        atten = 0
        if rx_max > optic.rx_overload_dbm:
            atten = math.ceil(rx_max - optic.rx_overload_dbm + 1)
        d = MediaDecision(name, dist, "OS2 SMF (9/125 um)", f"{optic.name} SFP+",
                          optic.standard, optic.wavelength_nm, lanes, bw, loss_db=loss,
                          budget_db=optic.budget_db,
                          margin_db=round(optic.budget_db - loss, 2),
                          attenuator_db=atten, latency_ms=propagation_ms(dist))
        why = (f"Selected OS2 Single-Mode Fiber because link distance ({km:g} km) exceeds the "
               f"{OM4_SR_MAX_M:g} m attenuation/dispersion limit of OM4 Multimode Fiber. "
               f"Optical budget for {optic.name} @{optic.wavelength_nm} nm: Tx(min) "
               f"{optic.tx_min_dbm} dBm - Rx sensitivity {optic.rx_sens_dbm} dBm = "
               f"{optic.budget_db} dB. Plant loss = {km:g} km x "
               f"{SMF_ATTEN_DB_PER_KM[optic.wavelength_nm]} dB/km + {connectors} connectors x "
               f"{CONNECTOR_LOSS_DB} dB + splices = {loss} dB, leaving "
               f"{optic.budget_db - loss:.2f} dB (>= {margin} dB required margin).")
        if atten:
            why += (f" Receiver overload check: Tx(max) {optic.tx_max_dbm} dBm - {loss} dB = "
                    f"{rx_max:.2f} dBm exceeds the {optic.rx_overload_dbm} dBm overload "
                    f"point, so a {atten} dB inline attenuator is required.")
        log.add("L1 Media", name, f"OS2 SMF / {optic.name}", why,
                [optic.standard, "ITU-T G.652.D", "TIA-568.3-D"])
        _lag_note(d, log)
        return d

    # ---- beyond self-owned dark fiber ----------------------------------
    if req == "smf":
        raise OpticalBudgetError(
            f"Link '{name}': {km:g} km of OS2 cannot be closed by any un-amplified 10G optic "
            f"(max 80 km ZR). Requires DWDM with EDFA amplification or a carrier circuit.")
    handoff = "1000BASE-LX SFP" if bw <= 1 else "10GBASE-LR SFP+"
    d = MediaDecision(name, dist, "Carrier WAN circuit (MEF E-Line / Internet)",
                      f"{handoff} at carrier NID", "MEF 6.2 / IEEE 802.3", 1310,
                      lanes, bw, latency_ms=round(propagation_ms(dist) * 1.3, 3))
    log.add("L1 Media", name, "Carrier-leased circuit",
            f"At {km:g} km no un-amplified 10G single-mode optic closes the power budget "
            f"(10G-ZR tops out at 80 km), and private dark fiber with DWDM amplification is not "
            f"cost-justified. A carrier circuit is used, with a short OS2 {handoff} "
            f"handoff at the carrier NID. Expected one-way delay ~{d.latency_ms} ms (fiber route x1.3).",
            ["MEF 6.2", "ITU-T G.652.D"])
    _lag_note(d, log)
    return d


def _lag_note(d: MediaDecision, log: RationaleLog) -> None:
    if d.lanes > 1:
        d.notes.append(f"{d.lanes} x 10G members in an LACP bundle")
        log.add("L2 Bundling", d.link, f"LACP {d.lanes} x 10G",
                f"Required bandwidth {d.bandwidth_gbps:g} Gb/s exceeds a single 10G lane; "
                f"ceil({d.bandwidth_gbps:g}/10) = {d.lanes} member links are bundled with LACP "
                f"so traffic is hashed across them and a member failure only reduces capacity.",
                ["IEEE 802.1AX"])
