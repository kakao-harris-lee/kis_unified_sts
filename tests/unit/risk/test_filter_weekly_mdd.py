# tests/unit/risk/test_filter_weekly_mdd.py
"""TDD tests for WeeklyMDDFilter.

Written BEFORE implementation (red phase).
"""

from __future__ import annotations

from shared.decision.signal import Signal
from shared.risk.filters.weekly_mdd import WeeklyMDDFilter
from shared.risk.state import RiskStateSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signal() -> Signal:
    return Signal(
        setup_type="test_setup",
        direction="long",
        symbol="A05603",
        entry_price=360.0,
        stop_loss=355.0,
        take_profit=370.0,
        confidence=0.8,
    )


def _make_snapshot(weekly_pnl_krw: float = 0.0) -> RiskStateSnapshot:
    return RiskStateSnapshot(weekly_pnl_krw=weekly_pnl_krw)


# ---------------------------------------------------------------------------
# Filter instantiation
# ---------------------------------------------------------------------------


def test_weekly_mdd_filter_name():
    f = WeeklyMDDFilter(account_equity_krw=5_000_000.0, weekly_mdd_limit_pct=0.06)
    assert f.name == "weekly_mdd"


def test_weekly_mdd_filter_stores_params():
    f = WeeklyMDDFilter(account_equity_krw=5_000_000.0, weekly_mdd_limit_pct=0.06)
    assert f.account_equity_krw == 5_000_000.0
    assert f.weekly_mdd_limit_pct == 0.06


# ---------------------------------------------------------------------------
# Pass case: weekly loss within limit
# ---------------------------------------------------------------------------


def test_pass_weekly_pnl_positive():
    """Positive weekly P&L → trivially within limit → passed=True."""
    f = WeeklyMDDFilter(account_equity_krw=5_000_000.0, weekly_mdd_limit_pct=0.06)
    snap = _make_snapshot(weekly_pnl_krw=20_000.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is True
    assert result.filter_name == "weekly_mdd"
    assert result.skip_reason is None


def test_pass_weekly_pnl_zero():
    f = WeeklyMDDFilter(account_equity_krw=5_000_000.0, weekly_mdd_limit_pct=0.06)
    snap = _make_snapshot(weekly_pnl_krw=0.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is True


def test_pass_weekly_loss_well_below_limit():
    """Loss of -100,000 on 5M equity = -2% < 6% limit → pass."""
    f = WeeklyMDDFilter(account_equity_krw=5_000_000.0, weekly_mdd_limit_pct=0.06)
    snap = _make_snapshot(weekly_pnl_krw=-100_000.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is True


# ---------------------------------------------------------------------------
# Reject case: weekly loss exceeds limit
# ---------------------------------------------------------------------------


def test_reject_weekly_loss_exceeds_limit():
    """Loss of -300,001 on 5M equity = >6% → rejected."""
    f = WeeklyMDDFilter(account_equity_krw=5_000_000.0, weekly_mdd_limit_pct=0.06)
    snap = _make_snapshot(weekly_pnl_krw=-300_001.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is False
    assert result.filter_name == "weekly_mdd"
    assert result.skip_reason == "weekly_mdd_exceeded"


def test_reject_weekly_loss_far_exceeds_limit():
    """Loss of -600,000 on 5M equity = -12% >> 6% → rejected."""
    f = WeeklyMDDFilter(account_equity_krw=5_000_000.0, weekly_mdd_limit_pct=0.06)
    snap = _make_snapshot(weekly_pnl_krw=-600_000.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is False
    assert result.skip_reason == "weekly_mdd_exceeded"


# ---------------------------------------------------------------------------
# Edge case: exactly at the limit (strict < comparison → equality passes)
# ---------------------------------------------------------------------------


def test_pass_weekly_loss_exactly_at_limit():
    """Loss of exactly -300,000 on 5M equity = exactly -6%.

    Strict comparison (< -limit_pct) means equality does NOT trigger reject
    → passed=True.
    """
    f = WeeklyMDDFilter(account_equity_krw=5_000_000.0, weekly_mdd_limit_pct=0.06)
    snap = _make_snapshot(weekly_pnl_krw=-300_000.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is True


def test_reject_one_krw_over_weekly_limit():
    """-300,001 KRW is one KRW beyond -6% threshold → rejected."""
    f = WeeklyMDDFilter(account_equity_krw=5_000_000.0, weekly_mdd_limit_pct=0.06)
    snap = _make_snapshot(weekly_pnl_krw=-300_001.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is False


# ---------------------------------------------------------------------------
# Different equity / limit combinations
# ---------------------------------------------------------------------------


def test_pass_with_different_equity_and_limit():
    """20M equity, 5% limit → threshold = -1,000,000. -999,999 passes."""
    f = WeeklyMDDFilter(account_equity_krw=20_000_000.0, weekly_mdd_limit_pct=0.05)
    snap = _make_snapshot(weekly_pnl_krw=-999_999.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is True


def test_reject_with_different_equity_and_limit():
    """20M equity, 5% limit → threshold = -1,000,000. -1,000,001 rejected."""
    f = WeeklyMDDFilter(account_equity_krw=20_000_000.0, weekly_mdd_limit_pct=0.05)
    snap = _make_snapshot(weekly_pnl_krw=-1_000_001.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is False
    assert result.skip_reason == "weekly_mdd_exceeded"
