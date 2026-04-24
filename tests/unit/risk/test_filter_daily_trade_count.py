# tests/unit/risk/test_filter_daily_trade_count.py
"""TDD tests for DailyTradeCountFilter.

Written BEFORE / alongside implementation (TDD red-green cycle).
"""

from __future__ import annotations

import pytest

from shared.decision.signal import Signal
from shared.risk.filters.daily_trade_count import DailyTradeCountFilter
from shared.risk.state import RiskStateSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAX = 10


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


def _make_snapshot(daily_trade_count: int = 0) -> RiskStateSnapshot:
    return RiskStateSnapshot(daily_trade_count=daily_trade_count)


def _make_filter(max_daily_trades: int = _MAX) -> DailyTradeCountFilter:
    return DailyTradeCountFilter(max_daily_trades=max_daily_trades)


# ---------------------------------------------------------------------------
# Filter metadata
# ---------------------------------------------------------------------------


def test_filter_name():
    f = _make_filter()
    assert f.name == "daily_trade_count"


def test_filter_stores_max():
    f = _make_filter(max_daily_trades=7)
    assert f.max_daily_trades == 7


# ---------------------------------------------------------------------------
# Construction guard-rails
# ---------------------------------------------------------------------------


def test_raises_if_max_is_zero():
    with pytest.raises(ValueError, match="max_daily_trades"):
        DailyTradeCountFilter(max_daily_trades=0)


def test_raises_if_max_is_negative():
    with pytest.raises(ValueError, match="max_daily_trades"):
        DailyTradeCountFilter(max_daily_trades=-1)


# ---------------------------------------------------------------------------
# Pass — count < max
# ---------------------------------------------------------------------------


def test_pass_zero_trades():
    """No trades yet → pass."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(0))
    assert result.passed is True
    assert result.skip_reason is None
    assert result.filter_name == "daily_trade_count"


def test_pass_one_trade():
    """1 trade when max=10 → pass."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(1))
    assert result.passed is True


def test_pass_max_minus_one():
    """count = max - 1 (= 9) → pass."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(_MAX - 1))
    assert result.passed is True
    assert result.size_multiplier == 1.0


# ---------------------------------------------------------------------------
# Reject — count >= max
# ---------------------------------------------------------------------------


def test_reject_exactly_at_max():
    """count == max → rejected."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(_MAX))
    assert result.passed is False
    assert result.skip_reason == "max_daily_trades"
    assert result.filter_name == "daily_trade_count"


def test_reject_above_max():
    """count > max → rejected."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(_MAX + 1))
    assert result.passed is False
    assert result.skip_reason == "max_daily_trades"


def test_reject_well_above_max():
    """count far above max (pathological) → still rejected."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(100))
    assert result.passed is False
    assert result.skip_reason == "max_daily_trades"


# ---------------------------------------------------------------------------
# size_multiplier is default 1.0 in all cases (filter does not reduce size)
# ---------------------------------------------------------------------------


def test_pass_has_full_size_multiplier():
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(5))
    assert result.size_multiplier == 1.0


def test_rejected_has_default_size_multiplier():
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(_MAX))
    assert result.size_multiplier == 1.0
