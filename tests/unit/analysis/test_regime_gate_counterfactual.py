import datetime as dt
import importlib.util
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "rgcf", _REPO / "scripts" / "analysis" / "regime_gate_counterfactual.py")
rgcf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rgcf)


def test_group_decisions_by_strategy_and_allow():
    decisions = [
        (dt.datetime(2026, 5, 20, 9, 0), "setup_a_gap_reversion", "long", 1),
        (dt.datetime(2026, 5, 20, 9, 5), "setup_a_gap_reversion", "long", 0),
        (dt.datetime(2026, 5, 20, 10, 0), "setup_c_event_reaction", "short", 1),
    ]
    grouped = rgcf.group_decisions(decisions)
    assert ("setup_a_gap_reversion", True) in grouped
    assert ("setup_a_gap_reversion", False) in grouped
    assert len(grouped[("setup_a_gap_reversion", True)]) == 1
    assert len(grouped[("setup_a_gap_reversion", False)]) == 1
    assert ("setup_c_event_reaction", True) in grouped


def test_estimate_pnl_returns_zero_for_empty_cohort():
    assert rgcf.estimate_cohort_pnl_pct([], lookback_min=15, candles_df=None) == 0.0


def test_estimate_pnl_computes_signed_return_per_direction():
    """Mean P&L: long → close goes up = positive; short → close goes up = negative."""
    import pandas as pd
    df = pd.DataFrame({
        "close": [100.0, 100.0, 101.0, 102.0]
    }, index=pd.to_datetime([
        "2026-05-20 09:00", "2026-05-20 09:01",
        "2026-05-20 09:15", "2026-05-20 09:16",
    ]))
    cohort = [
        (dt.datetime(2026, 5, 20, 9, 0), "setup_a_gap_reversion", "long", 1),
        (dt.datetime(2026, 5, 20, 9, 0), "setup_a_gap_reversion", "short", 1),
    ]
    avg = rgcf.estimate_cohort_pnl_pct(cohort, lookback_min=15, candles_df=df)
    # long: +1% (100 → 101); short: -1% (signed). Mean = 0.0
    assert abs(avg - 0.0) < 1e-9


def test_format_telegram_digest_renders_per_strategy_summary():
    summary = {
        "setup_a_gap_reversion": {
            "blocked_count": 5, "blocked_mean_pnl_pct": -0.3,
            "allowed_count": 12, "allowed_mean_pnl_pct": +0.8,
        },
        "setup_c_event_reaction": {
            "blocked_count": 0, "blocked_mean_pnl_pct": 0.0,
            "allowed_count": 0, "allowed_mean_pnl_pct": 0.0,
        },
    }
    msg = rgcf.format_telegram_digest(
        summary, start=dt.date(2026, 5, 15), end=dt.date(2026, 5, 21))
    assert "setup_a_gap_reversion" in msg
    assert "setup_c_event_reaction" in msg
    assert "blocked" in msg.lower()
    # Setup C zero-signal note (per spec — known limitation)
    assert "0 / 0" in msg or "no signals" in msg.lower() or "no decisions" in msg.lower()
