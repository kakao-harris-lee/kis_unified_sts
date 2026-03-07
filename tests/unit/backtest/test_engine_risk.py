"""Tests for BacktestEngine._check_risk() — verify risk management logic.

This module tests all risk management checks:
- Stop loss (fixed % and ATR-based)
- Take profit
- Trailing stop
- Time limits (max hold bars)
- Force close time
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shared.backtest.config import BacktestConfig, RiskConfig
from shared.backtest.engine import BacktestEngine, ExitReason, Position, SimpleMAStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_position(
    code: str = "005930",
    side: str = "BUY",
    entry_price: float = 100.0,
    quantity: int = 10,
    entry_time: datetime | None = None,
    bars_held: int = 0,
    highest_price: float = 0.0,
    lowest_price: float = 0.0,
    atr_at_entry: float = 0.0,
) -> Position:
    """Create a test position."""
    if entry_time is None:
        entry_time = datetime(2024, 1, 2, 9, 0)

    if highest_price == 0.0:
        highest_price = entry_price
    if lowest_price == 0.0:
        lowest_price = entry_price

    return Position(
        code=code,
        name=code,
        strategy="test",
        side=side,
        entry_time=entry_time,
        entry_price=entry_price,
        quantity=quantity,
        highest_price=highest_price,
        lowest_price=lowest_price,
        bars_held=bars_held,
        atr_at_entry=atr_at_entry,
    )


def _make_engine(risk_config: RiskConfig | None = None) -> BacktestEngine:
    """Create a test engine with custom risk config."""
    config = BacktestConfig()
    if risk_config:
        config.risk = risk_config
    return BacktestEngine(SimpleMAStrategy(), config)


# ---------------------------------------------------------------------------
# Stop Loss Tests
# ---------------------------------------------------------------------------


class TestStopLoss:
    """Test fixed percentage stop loss."""

    def test_buy_position_stop_loss_triggered(self):
        """BUY position should trigger stop loss when price drops by stop_loss_pct."""
        risk = RiskConfig(stop_loss_pct=2.0)
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0)
        current_price = 97.5  # -2.5% loss
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.STOP_LOSS

    def test_buy_position_stop_loss_exact_threshold(self):
        """BUY position should trigger at exact stop loss threshold."""
        risk = RiskConfig(stop_loss_pct=2.0)
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0)
        current_price = 98.0  # Exactly -2.0%
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.STOP_LOSS

    def test_buy_position_stop_loss_not_triggered(self):
        """BUY position should not trigger stop loss when within threshold."""
        risk = RiskConfig(stop_loss_pct=2.0)
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0)
        current_price = 98.5  # -1.5% loss (within threshold)
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result is None

    def test_sell_position_stop_loss_triggered(self):
        """SELL position should trigger stop loss when price rises by stop_loss_pct."""
        risk = RiskConfig(stop_loss_pct=2.0)
        engine = _make_engine(risk)

        pos = _make_position(side="SELL", entry_price=100.0)
        current_price = 102.5  # -2.5% loss for short
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.STOP_LOSS

    def test_sell_position_stop_loss_not_triggered(self):
        """SELL position should not trigger stop loss when within threshold."""
        risk = RiskConfig(stop_loss_pct=2.0)
        engine = _make_engine(risk)

        pos = _make_position(side="SELL", entry_price=100.0)
        current_price = 101.5  # -1.5% loss (within threshold)
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result is None


class TestATRStopLoss:
    """Test ATR-based stop loss."""

    def test_atr_stop_buy_position_triggered(self):
        """BUY position should trigger ATR stop when price drops below entry - (ATR × multiplier)."""
        risk = RiskConfig(use_atr_stop=True, atr_stop_multiplier=2.0)
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            atr_at_entry=1.5,  # ATR = 1.5
        )
        # Stop price = 100 - (1.5 × 2.0) = 97.0
        current_price = 96.5
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.STOP_LOSS

    def test_atr_stop_buy_position_exact_threshold(self):
        """BUY position should trigger at exact ATR stop price."""
        risk = RiskConfig(use_atr_stop=True, atr_stop_multiplier=2.0)
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            atr_at_entry=1.5,
        )
        current_price = 97.0  # Exactly at stop
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.STOP_LOSS

    def test_atr_stop_buy_position_not_triggered(self):
        """BUY position should not trigger ATR stop when above stop price."""
        risk = RiskConfig(use_atr_stop=True, atr_stop_multiplier=2.0)
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            atr_at_entry=1.5,
        )
        current_price = 97.5  # Above stop price
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result is None

    def test_atr_stop_sell_position_triggered(self):
        """SELL position should trigger ATR stop when price rises above entry + (ATR × multiplier)."""
        risk = RiskConfig(use_atr_stop=True, atr_stop_multiplier=2.0)
        engine = _make_engine(risk)

        pos = _make_position(
            side="SELL",
            entry_price=100.0,
            atr_at_entry=1.5,
        )
        # Stop price = 100 + (1.5 × 2.0) = 103.0
        current_price = 103.5
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.STOP_LOSS

    def test_atr_stop_sell_position_not_triggered(self):
        """SELL position should not trigger ATR stop when below stop price."""
        risk = RiskConfig(use_atr_stop=True, atr_stop_multiplier=2.0)
        engine = _make_engine(risk)

        pos = _make_position(
            side="SELL",
            entry_price=100.0,
            atr_at_entry=1.5,
        )
        current_price = 102.5  # Below stop price
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result is None

    def test_atr_stop_disabled_when_atr_zero(self):
        """ATR stop should be disabled if ATR at entry is 0."""
        risk = RiskConfig(
            use_atr_stop=True,
            atr_stop_multiplier=2.0,
            stop_loss_pct=2.0,  # Fallback to fixed stop
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            atr_at_entry=0.0,  # No ATR
        )
        current_price = 97.5  # -2.5% (should use fixed stop)
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        # Should use fixed stop loss instead
        assert result == ExitReason.STOP_LOSS

    def test_atr_stop_has_priority_over_fixed(self):
        """When ATR stop is enabled, it takes priority over fixed stop."""
        risk = RiskConfig(
            use_atr_stop=True,
            atr_stop_multiplier=2.0,
            stop_loss_pct=5.0,  # Wider stop
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            atr_at_entry=1.0,  # ATR stop at 98.0 (100 - 2×1.0)
        )
        current_price = 96.0  # Below both ATR stop (98.0) and fixed stop (95.0)
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        # Should trigger on ATR stop (checked first)
        assert result == ExitReason.STOP_LOSS


# ---------------------------------------------------------------------------
# Take Profit Tests
# ---------------------------------------------------------------------------


class TestTakeProfit:
    """Test take profit exit."""

    def test_buy_position_take_profit_triggered(self):
        """BUY position should trigger take profit when gain reaches threshold."""
        risk = RiskConfig(take_profit_pct=5.0)
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0)
        current_price = 105.5  # +5.5% gain
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.TAKE_PROFIT

    def test_buy_position_take_profit_exact_threshold(self):
        """BUY position should trigger at exact take profit threshold."""
        risk = RiskConfig(take_profit_pct=5.0)
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0)
        current_price = 105.0  # Exactly +5.0%
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.TAKE_PROFIT

    def test_buy_position_take_profit_not_triggered(self):
        """BUY position should not trigger take profit below threshold."""
        risk = RiskConfig(take_profit_pct=5.0)
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0)
        current_price = 104.5  # +4.5% (below threshold)
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result is None

    def test_sell_position_take_profit_triggered(self):
        """SELL position should trigger take profit when price drops by threshold."""
        risk = RiskConfig(take_profit_pct=5.0)
        engine = _make_engine(risk)

        pos = _make_position(side="SELL", entry_price=100.0)
        current_price = 94.5  # +5.5% profit for short
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.TAKE_PROFIT

    def test_sell_position_take_profit_not_triggered(self):
        """SELL position should not trigger take profit below threshold."""
        risk = RiskConfig(take_profit_pct=5.0)
        engine = _make_engine(risk)

        pos = _make_position(side="SELL", entry_price=100.0)
        current_price = 95.5  # +4.5% (below threshold)
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result is None


# ---------------------------------------------------------------------------
# Trailing Stop Tests
# ---------------------------------------------------------------------------


class TestTrailingStop:
    """Test trailing stop functionality."""

    def test_trailing_stop_buy_position_triggered(self):
        """BUY position should trigger trailing stop after price pulls back from high."""
        risk = RiskConfig(
            trailing_stop_enabled=True,
            trailing_stop_trigger_pct=3.0,  # Activates at +3%
            trailing_stop_distance_pct=1.5,  # Trails by 1.5%
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            highest_price=105.0,  # Reached +5% (above trigger)
        )
        # Trailing stop = 105.0 × (1 - 0.015) = 103.425
        current_price = 103.0  # Below trailing stop
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.TRAILING_STOP

    def test_trailing_stop_buy_position_exact_threshold(self):
        """BUY position should trigger at exact trailing stop price."""
        risk = RiskConfig(
            trailing_stop_enabled=True,
            trailing_stop_trigger_pct=3.0,
            trailing_stop_distance_pct=1.5,
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            highest_price=105.0,
        )
        current_price = 103.425  # Exactly at trailing stop
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.TRAILING_STOP

    def test_trailing_stop_buy_position_not_triggered(self):
        """BUY position should not trigger trailing stop when above stop price."""
        risk = RiskConfig(
            trailing_stop_enabled=True,
            trailing_stop_trigger_pct=3.0,
            trailing_stop_distance_pct=1.5,
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            highest_price=105.0,
        )
        current_price = 104.0  # Above trailing stop
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result is None

    def test_trailing_stop_not_activated_below_trigger(self):
        """Trailing stop should not activate if trigger threshold not reached."""
        risk = RiskConfig(
            trailing_stop_enabled=True,
            trailing_stop_trigger_pct=3.0,
            trailing_stop_distance_pct=1.5,
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            highest_price=102.0,  # Only +2% (below 3% trigger)
        )
        current_price = 100.5  # Below highest but above entry
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        # Trailing stop not activated yet
        assert result is None

    def test_trailing_stop_sell_position_triggered(self):
        """SELL position should trigger trailing stop after price rises from low."""
        risk = RiskConfig(
            trailing_stop_enabled=True,
            trailing_stop_trigger_pct=3.0,
            trailing_stop_distance_pct=1.5,
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="SELL",
            entry_price=100.0,
            lowest_price=95.0,  # Reached +5% profit (below trigger)
        )
        # Trailing stop = 95.0 × (1 + 0.015) = 96.425
        current_price = 97.0  # Above trailing stop
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.TRAILING_STOP

    def test_trailing_stop_sell_position_not_triggered(self):
        """SELL position should not trigger trailing stop when below stop price."""
        risk = RiskConfig(
            trailing_stop_enabled=True,
            trailing_stop_trigger_pct=3.0,
            trailing_stop_distance_pct=1.5,
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="SELL",
            entry_price=100.0,
            lowest_price=95.0,
        )
        current_price = 96.0  # Below trailing stop
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result is None

    def test_trailing_stop_disabled_by_config(self):
        """Trailing stop should not trigger when disabled in config."""
        risk = RiskConfig(
            trailing_stop_enabled=False,  # Disabled
            trailing_stop_trigger_pct=3.0,
            trailing_stop_distance_pct=1.5,
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            highest_price=105.0,
        )
        current_price = 103.0  # Would trigger if enabled
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        # Should not trigger
        assert result is None


# ---------------------------------------------------------------------------
# Time Limit Tests
# ---------------------------------------------------------------------------


class TestTimeLimit:
    """Test max hold bars time limit."""

    def test_time_limit_triggered(self):
        """Position should be closed when max_hold_bars is reached."""
        risk = RiskConfig(max_hold_bars=100)
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0, bars_held=100)
        current_price = 102.0
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.TIME_LIMIT

    def test_time_limit_exceeded(self):
        """Position should be closed when bars_held exceeds max_hold_bars."""
        risk = RiskConfig(max_hold_bars=100)
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0, bars_held=105)
        current_price = 102.0
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.TIME_LIMIT

    def test_time_limit_not_triggered(self):
        """Position should not be closed when below max_hold_bars."""
        risk = RiskConfig(max_hold_bars=100)
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0, bars_held=95)
        current_price = 102.0
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        assert result is None

    def test_time_limit_disabled_when_zero(self):
        """Time limit should be disabled when max_hold_bars is 0."""
        risk = RiskConfig(max_hold_bars=0)  # Disabled
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0, bars_held=1000)
        current_price = 102.0
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        # Should not trigger time limit
        assert result is None


# ---------------------------------------------------------------------------
# Force Close Time Tests
# ---------------------------------------------------------------------------


class TestForceCloseTime:
    """Test force close at specific time."""

    def test_force_close_time_triggered(self):
        """Position should be closed at force_close_time."""
        risk = RiskConfig(force_close_time="15:15")
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0)
        current_price = 102.0
        timestamp = datetime(2024, 1, 2, 15, 15)  # Exactly at force close

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.FORCE_CLOSE

    def test_force_close_time_after_specified(self):
        """Position should be closed after force_close_time."""
        risk = RiskConfig(force_close_time="15:15")
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0)
        current_price = 102.0
        timestamp = datetime(2024, 1, 2, 15, 20)  # After force close

        result = engine._check_risk(pos, current_price, timestamp)

        assert result == ExitReason.FORCE_CLOSE

    def test_force_close_time_not_triggered(self):
        """Position should not be closed before force_close_time."""
        risk = RiskConfig(force_close_time="15:15")
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0)
        current_price = 102.0
        timestamp = datetime(2024, 1, 2, 15, 10)  # Before force close

        result = engine._check_risk(pos, current_price, timestamp)

        assert result is None

    def test_force_close_time_disabled_when_none(self):
        """Force close should be disabled when force_close_time is None."""
        risk = RiskConfig(force_close_time=None)
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0)
        current_price = 102.0
        timestamp = datetime(2024, 1, 2, 23, 59)  # End of day

        result = engine._check_risk(pos, current_price, timestamp)

        # Should not trigger force close
        assert result is None


# ---------------------------------------------------------------------------
# Combined/Priority Tests
# ---------------------------------------------------------------------------


class TestRiskCheckPriority:
    """Test priority and combinations of risk checks."""

    def test_stop_loss_priority_over_take_profit(self):
        """Stop loss should be checked before take profit."""
        risk = RiskConfig(
            stop_loss_pct=2.0,
            take_profit_pct=5.0,
        )
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0)
        current_price = 97.5  # Triggers stop loss
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        # Should return stop loss (checked first in code)
        assert result == ExitReason.STOP_LOSS

    def test_take_profit_priority_over_trailing_stop(self):
        """Take profit should be checked before trailing stop."""
        risk = RiskConfig(
            take_profit_pct=5.0,
            trailing_stop_enabled=True,
            trailing_stop_trigger_pct=3.0,
            trailing_stop_distance_pct=1.5,
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            highest_price=106.0,  # Trailing stop would be ~104.5
        )
        current_price = 105.0  # Triggers both take profit and could trigger trailing
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        # Should return take profit (checked before trailing stop)
        assert result == ExitReason.TAKE_PROFIT

    def test_trailing_stop_priority_over_time_limit(self):
        """Trailing stop should be checked before time limit."""
        risk = RiskConfig(
            trailing_stop_enabled=True,
            trailing_stop_trigger_pct=3.0,
            trailing_stop_distance_pct=1.5,
            max_hold_bars=10,
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            highest_price=105.0,
            bars_held=10,  # At time limit
        )
        current_price = 103.0  # Below trailing stop
        timestamp = datetime(2024, 1, 2, 10, 0)

        result = engine._check_risk(pos, current_price, timestamp)

        # Should return trailing stop (checked before time limit)
        assert result == ExitReason.TRAILING_STOP

    def test_time_limit_priority_over_force_close(self):
        """Time limit should be checked before force close time."""
        risk = RiskConfig(
            max_hold_bars=10,
            force_close_time="15:15",
        )
        engine = _make_engine(risk)

        pos = _make_position(side="BUY", entry_price=100.0, bars_held=10)
        current_price = 102.0
        timestamp = datetime(2024, 1, 2, 15, 15)  # Both conditions met

        result = engine._check_risk(pos, current_price, timestamp)

        # Should return time limit (checked before force close)
        assert result == ExitReason.TIME_LIMIT

    def test_all_conditions_within_limits(self):
        """Position should continue when all conditions are within limits."""
        risk = RiskConfig(
            stop_loss_pct=2.0,
            take_profit_pct=5.0,
            trailing_stop_enabled=True,
            trailing_stop_trigger_pct=3.0,
            trailing_stop_distance_pct=1.5,
            max_hold_bars=100,
            force_close_time="15:15",
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            highest_price=102.5,  # +2.5% (below trigger)
            bars_held=50,  # Below max
        )
        current_price = 102.0  # +2% (within all limits)
        timestamp = datetime(2024, 1, 2, 14, 30)  # Before force close

        result = engine._check_risk(pos, current_price, timestamp)

        # No exit reason should be triggered
        assert result is None

    def test_multiple_violations_returns_first_check(self):
        """When multiple conditions are violated, return the first checked."""
        risk = RiskConfig(
            stop_loss_pct=2.0,
            take_profit_pct=5.0,
            max_hold_bars=10,
            force_close_time="15:15",
        )
        engine = _make_engine(risk)

        pos = _make_position(
            side="BUY",
            entry_price=100.0,
            bars_held=10,  # Time limit violated
        )
        current_price = 97.0  # Stop loss violated
        timestamp = datetime(2024, 1, 2, 15, 15)  # Force close violated

        result = engine._check_risk(pos, current_price, timestamp)

        # Stop loss is checked first
        assert result == ExitReason.STOP_LOSS
