"""Tests for Phase 3 decision-engine Prometheus metric families.

Verifies:
- All 7 module-level metric objects are registered (not None).
- Each record_* helper can be called without raising.
- Prometheus REGISTRY reflects the increments/observations.
"""

from prometheus_client import REGISTRY

from services.monitoring.metrics import (
    record_risk_state_consecutive_losses,
    record_risk_state_daily_pnl_pct,
    record_risk_state_daily_trade_count,
    record_signal_candidate,
    record_signal_final,
    record_signal_generator_duration,
    record_signal_rejected,
    risk_state_consecutive_losses,
    risk_state_daily_pnl_pct,
    risk_state_daily_trade_count,
    signal_candidate_total,
    signal_final_total,
    signal_generator_duration_seconds,
    signal_rejected_total,
)


def _sample(name: str, labels: dict) -> float | None:
    """Return the current sample value for *name* with matching *labels*, or None."""
    for metric in REGISTRY.collect():
        for s in metric.samples:
            if s.name != name:
                continue
            if all(s.labels.get(k) == v for k, v in labels.items()):
                return s.value
    return None


# ---------------------------------------------------------------------------
# 1. Metric objects exist (not None)
# ---------------------------------------------------------------------------


def test_signal_candidate_total_is_registered():
    assert signal_candidate_total is not None


def test_signal_final_total_is_registered():
    assert signal_final_total is not None


def test_signal_rejected_total_is_registered():
    assert signal_rejected_total is not None


def test_signal_generator_duration_seconds_is_registered():
    assert signal_generator_duration_seconds is not None


def test_risk_state_daily_pnl_pct_is_registered():
    assert risk_state_daily_pnl_pct is not None


def test_risk_state_consecutive_losses_is_registered():
    assert risk_state_consecutive_losses is not None


def test_risk_state_daily_trade_count_is_registered():
    assert risk_state_daily_trade_count is not None


# ---------------------------------------------------------------------------
# 2. record_* helpers do not raise and update the registry
# ---------------------------------------------------------------------------


def test_record_signal_candidate_increments_counter():
    before = _sample("signal_candidate_total", {"setup": "bb_reversion"}) or 0
    record_signal_candidate(setup="bb_reversion")
    after = _sample("signal_candidate_total", {"setup": "bb_reversion"}) or 0
    assert after == before + 1


def test_record_signal_final_increments_counter():
    before = _sample("signal_final_total", {"setup": "setup_a_gap_reversion"}) or 0
    record_signal_final(setup="setup_a_gap_reversion")
    after = _sample("signal_final_total", {"setup": "setup_a_gap_reversion"}) or 0
    assert after == before + 1


def test_record_signal_rejected_increments_counter():
    before = (
        _sample(
            "signal_rejected_total",
            {"setup": "bb_reversion", "filter": "regime_block"},
        )
        or 0
    )
    record_signal_rejected(setup="bb_reversion", filter="regime_block")
    after = (
        _sample(
            "signal_rejected_total",
            {"setup": "bb_reversion", "filter": "regime_block"},
        )
        or 0
    )
    assert after == before + 1


def test_record_signal_generator_duration_observes_histogram():
    record_signal_generator_duration(setup="setup_a_gap_reversion", seconds=0.08)
    cnt = _sample(
        "signal_generator_duration_seconds_count", {"setup": "setup_a_gap_reversion"}
    )
    assert (cnt or 0) >= 1


def test_record_risk_state_daily_pnl_pct_sets_gauge():
    record_risk_state_daily_pnl_pct(value=-1.5)
    val = _sample("risk_state_daily_pnl_pct", {})
    assert val is not None
    assert abs(val - (-1.5)) < 1e-6


def test_record_risk_state_consecutive_losses_sets_gauge():
    record_risk_state_consecutive_losses(value=3)
    val = _sample("risk_state_consecutive_losses", {})
    assert val is not None
    assert val == 3


def test_record_risk_state_daily_trade_count_sets_gauge():
    record_risk_state_daily_trade_count(value=12)
    val = _sample("risk_state_daily_trade_count", {})
    assert val is not None
    assert val == 12
