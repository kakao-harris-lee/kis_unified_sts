"""Tests for Phase 4 metrics — services/monitoring/metrics.py §7.1 additions."""

from services.monitoring.metrics import (
    HAS_PROMETHEUS,
    record_kill_switch_condition_value,
    record_kill_switch_triggered,
    record_order_filled,
    record_order_latency_ms,
    record_order_missed,
    record_order_placed,
    record_order_slippage_ticks,
    record_risk_state_daily_pnl_krw,
    record_risk_state_weekly_pnl_krw,
)


def test_order_placed_counter_does_not_raise():
    record_order_placed("A_gap_reversion", "limit_passive")


def test_order_filled_counter_supports_venue_label():
    record_order_filled("A_gap_reversion", "limit_passive", "KRX")


def test_order_missed_counter():
    record_order_missed("C_event_reaction", "passive_not_filled")


def test_order_slippage_histogram():
    record_order_slippage_ticks("A_gap_reversion", 0.5)
    record_order_slippage_ticks("A_gap_reversion", 1.2)


def test_order_latency_histogram_both_stages():
    record_order_latency_ms("A_gap_reversion", "request", 25.0)
    record_order_latency_ms("A_gap_reversion", "fill", 1250.0)


def test_kill_switch_metrics():
    record_kill_switch_triggered("daily_loss")
    record_kill_switch_condition_value("daily_loss", 0.025)


def test_risk_state_pnl_gauges():
    record_risk_state_daily_pnl_krw(-1_500_000.0)
    record_risk_state_weekly_pnl_krw(2_300_000.0)


def test_metrics_no_op_without_prometheus(monkeypatch):
    """When prometheus_client isn't available, recorders must silently no-op."""
    if not HAS_PROMETHEUS:
        # Already running without prometheus — calls just need to not raise.
        record_order_placed("test", "limit")
        record_kill_switch_triggered("test")
        return

    # When prometheus IS available, the recorders should still be safe to
    # call (this also exercises the labels() path).
    for _ in range(3):
        record_order_placed("A_gap_reversion", "limit_passive")
