"""L1 media engine: distance boundaries, explicit-request violations, optical budgets."""
import pytest

from netarchitect.errors import (InvalidParameterError, OpticalBudgetError,
                                 PhysicalDistanceViolationError)
from netarchitect.explain import RationaleLog
from netarchitect.media import SMF_OPTICS, decide_media, smf_link_loss


def media(d, **kw):
    return decide_media({"name": "t", "distance_m": d, **kw}, RationaleLog())


@pytest.mark.parametrize("d", [1, 50, 99.9, 100])
def test_copper_up_to_100m(d):
    m = media(d)
    assert m.media.startswith("Cat6a") and "10GBASE-T" in m.transceiver


@pytest.mark.parametrize("d", [100.01, 101, 250, 400])
def test_om4_between_100_and_400m(d):
    m = media(d)
    assert m.media.startswith("OM4") and "10GBASE-SR" in m.transceiver
    assert m.loss_db <= m.budget_db


@pytest.mark.parametrize("d", [400.01, 401, 2000, 22000])
def test_os2_beyond_400m(d):
    assert media(d).media.startswith("OS2")


def test_os2_justification_mentions_om4_limit():
    log = RationaleLog()
    decide_media({"name": "HQ-REMOTE", "distance_m": 22000}, log)
    text = log.to_text()
    assert "Selected OS2 Single-Mode Fiber because link distance (22 km) exceeds the 400 m" in text
    assert "Optical budget" in text


@pytest.mark.parametrize("d", [100.5, 101, 150, 5000])
def test_copper_request_beyond_100m_raises(d):
    with pytest.raises(PhysicalDistanceViolationError, match="attenuation"):
        media(d, media_request="copper")


def test_copper_request_at_exactly_100m_ok():
    assert media(100, media_request="copper").media.startswith("Cat6a")


def test_mmf_request_beyond_400m_raises():
    with pytest.raises(PhysicalDistanceViolationError):
        media(401, media_request="mmf")


def test_smf_request_beyond_unamplified_reach_raises():
    with pytest.raises(OpticalBudgetError):
        media(120000, media_request="smf")


def test_long_haul_becomes_carrier_circuit():
    m = media(1_400_000, bandwidth_gbps=1)
    assert m.media.startswith("Carrier") and "1000BASE-LX" in m.transceiver


@pytest.mark.parametrize("bad", [0, -5, "abc", None, float("nan"), float("inf")])
def test_invalid_distance(bad):
    with pytest.raises(InvalidParameterError):
        decide_media({"name": "x", "distance_m": bad}, RationaleLog())


def test_invalid_media_request():
    with pytest.raises(InvalidParameterError):
        media(50, media_request="coax")


def test_lr_for_short_smf_and_er_when_lr_budget_fails():
    assert "10GBASE-LR" in media(5000).transceiver
    m = media(15000)          # beyond LR's 10 km reach
    assert "10GBASE-ER" in m.transceiver


def test_budget_margin_respected_for_every_smf_choice():
    for d in range(500, 80001, 2500):
        m = media(d)
        if m.media.startswith("OS2"):
            assert m.budget_db - m.loss_db >= 3.0 - 1e-9, d


def test_zr_selected_when_er_budget_fails_and_attenuator_reported():
    log = RationaleLog()
    m = decide_media({"name": "35k", "distance_m": 35000}, log)
    assert "ZR" in m.transceiver
    assert any("Rejected 10GBASE-ER" in e.decision for e in log.entries)
    assert m.attenuator_db >= 1     # short-ish span would overload a ZR receiver


def test_optic_budgets_are_tx_min_minus_rx_sensitivity():
    for o in SMF_OPTICS:
        assert o.budget_db == pytest.approx(o.tx_min_dbm - o.rx_sens_dbm)


def test_smf_loss_model():
    # 20 km @1550: 20*0.25 + 2*0.5 + 3 splices*0.1 = 6.3 dB
    assert smf_link_loss(20, 1550) == pytest.approx(6.3)


def test_lacp_lanes_for_bandwidth_over_10g():
    m = media(180, bandwidth_gbps=20)
    assert m.lanes == 2
    assert media(180, bandwidth_gbps=25).lanes == 3


def test_too_many_connectors_escalates_mmf_to_smf():
    m = media(390, connectors=6)          # 1.17 + 3.0 = 4.17 dB > 2.9 dB SR budget
    assert m.media.startswith("OS2")


def test_evpl_service_is_carrier_handoff():
    m = media(18000, service="EVPL", bandwidth_gbps=1)
    assert "EVPL" in m.media and m.latency_ms > 0.5
