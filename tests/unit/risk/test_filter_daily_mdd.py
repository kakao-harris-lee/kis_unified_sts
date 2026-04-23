# tests/unit/risk/test_filter_daily_mdd.py
"""TDD tests for DailyMDDFilter.

Written BEFORE implementation (red phase).
"""

from __future__ import annotations

from shared.decision.signal import Signal
from shared.risk.filters.daily_mdd import DailyMDDFilter
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


def _make_snapshot(daily_pnl_krw: float = 0.0) -> RiskStateSnapshot:
    return RiskStateSnapshot(daily_pnl_krw=daily_pnl_krw)


# ---------------------------------------------------------------------------
# Filter instantiation
# ---------------------------------------------------------------------------


def test_daily_mdd_filter_name():
    f = DailyMDDFilter(account_equity_krw=5_000_000.0, daily_mdd_limit_pct=0.03)
    assert f.name == "daily_mdd"


def test_daily_mdd_filter_stores_params():
    f = DailyMDDFilter(account_equity_krw=5_000_000.0, daily_mdd_limit_pct=0.03)
    assert f.account_equity_krw == 5_000_000.0
    assert f.daily_mdd_limit_pct == 0.03


# ---------------------------------------------------------------------------
# Pass case: daily loss within limit
# ---------------------------------------------------------------------------


def test_pass_daily_pnl_positive():
    """Positive P&L is trivially within limit → passed=True."""
    f = DailyMDDFilter(account_equity_krw=5_000_000.0, daily_mdd_limit_pct=0.03)
    snap = _make_snapshot(daily_pnl_krw=10_000.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is True
    assert result.filter_name == "daily_mdd"
    assert result.skip_reason is None


def test_pass_daily_pnl_zero():
    """Zero P&L → within limit → passed=True."""
    f = DailyMDDFilter(account_equity_krw=5_000_000.0, daily_mdd_limit_pct=0.03)
    snap = _make_snapshot(daily_pnl_krw=0.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is True


def test_pass_daily_loss_well_below_limit():
    """Loss of -50,000 on 5M equity = -1% < 3% limit → pass."""
    f = DailyMDDFilter(account_equity_krw=5_000_000.0, daily_mdd_limit_pct=0.03)
    snap = _make_snapshot(daily_pnl_krw=-50_000.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is True


# ---------------------------------------------------------------------------
# Reject case: daily loss exceeds limit
# ---------------------------------------------------------------------------


def test_reject_daily_loss_exceeds_limit():
    """Loss of -150,001 on 5M equity = >3% → rejected."""
    f = DailyMDDFilter(account_equity_krw=5_000_000.0, daily_mdd_limit_pct=0.03)
    snap = _make_snapshot(daily_pnl_krw=-150_001.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is False
    assert result.filter_name == "daily_mdd"
    assert result.skip_reason == "daily_mdd_exceeded"


def test_reject_daily_loss_far_exceeds_limit():
    """Loss of -300,000 on 5M equity = -6% >> 3% limit → rejected."""
    f = DailyMDDFilter(account_equity_krw=5_000_000.0, daily_mdd_limit_pct=0.03)
    snap = _make_snapshot(daily_pnl_krw=-300_000.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is False
    assert result.skip_reason == "daily_mdd_exceeded"


# ---------------------------------------------------------------------------
# Edge case: exactly at the limit (strict < comparison → equality passes)
# ---------------------------------------------------------------------------


def test_pass_daily_loss_exactly_at_limit():
    """Loss of exactly -150,000 on 5M equity = exactly -3%.

    The comparison is strict (< -limit_pct) so equality does NOT trigger
    the reject → passed=True.
    """
    f = DailyMDDFilter(account_equity_krw=5_000_000.0, daily_mdd_limit_pct=0.03)
    snap = _make_snapshot(daily_pnl_krw=-150_000.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is True


def test_reject_one_krw_over_limit():
    """-150,001 KRW is one KRW beyond the -3% threshold → rejected."""
    f = DailyMDDFilter(account_equity_krw=5_000_000.0, daily_mdd_limit_pct=0.03)
    snap = _make_snapshot(daily_pnl_krw=-150_001.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is False


# ---------------------------------------------------------------------------
# Different equity / limit combinations
# ---------------------------------------------------------------------------


def test_pass_with_different_equity():
    """10M equity, 2% limit → threshold = -200,000. -199,999 passes."""
    f = DailyMDDFilter(account_equity_krw=10_000_000.0, daily_mdd_limit_pct=0.02)
    snap = _make_snapshot(daily_pnl_krw=-199_999.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is True


def test_reject_with_different_equity():
    """10M equity, 2% limit → threshold = -200,000. -200,001 rejected."""
    f = DailyMDDFilter(account_equity_krw=10_000_000.0, daily_mdd_limit_pct=0.02)
    snap = _make_snapshot(daily_pnl_krw=-200_001.0)
    result = f.check(_make_signal(), snap)
    assert result.passed is False
    assert result.skip_reason == "daily_mdd_exceeded"
