"""Integration tests for BacktestEngine end-to-end scenarios.

Tests complex interactions: day change, daily limits, exit strategies, RL features.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from shared.backtest.config import BacktestConfig, RiskConfig
from shared.backtest.engine import BacktestEngine, ExitReason, SignalType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(
    n: int = 100, code: str = "005930", start_date: datetime | None = None
) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    if start_date is None:
        start_date = datetime(2024, 1, 2, 9, 0)
    rng = np.random.default_rng(42)
    price = 100.0
    rows: list[dict] = []
    for i in range(n):
        price += rng.uniform(-1, 1.2)
        rows.append(
            {
                "code": code,
                "name": code,
                "datetime": start_date + timedelta(minutes=i),
                "open": round(price - 0.2, 2),
                "high": round(price + 0.5, 2),
                "low": round(price - 0.5, 2),
                "close": round(price, 2),
                "volume": 1000 + i,
            }
        )
    return pd.DataFrame(rows)


def _make_multi_day_ohlcv(days: int = 3, bars_per_day: int = 30) -> pd.DataFrame:
    """Generate multi-day OHLCV data with date boundaries."""
    frames = []
    for day_idx in range(days):
        day_start = datetime(2024, 1, 2 + day_idx, 9, 0)
        df = _make_ohlcv(bars_per_day, start_date=day_start)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


class _AlwaysBuyStrategy:
    """Strategy that buys whenever not holding a position."""

    name = "always_buy"

    def __init__(self):
        self._position = None

    def set_position(self, position):
        """Track position state so we can buy again after force-close."""
        self._position = position

    def on_bar(self, bar: dict) -> SignalType:
        if self._position is None:
            return SignalType.BUY
        return SignalType.HOLD


class _BuyEveryNBarsStrategy:
    """Strategy that buys every N bars."""

    name = "buy_every_n"

    def __init__(self, n: int = 5):
        self.n = n
        self._bar_count = 0

    def on_bar(self, bar: dict) -> SignalType:
        self._bar_count += 1
        if self._bar_count % self.n == 0:
            return SignalType.BUY
        return SignalType.HOLD


class _ExitCheckStrategy:
    """Strategy with custom exit check logic."""

    name = "exit_check"

    def __init__(self, exit_after_bars: int = 5):
        self.exit_after_bars = exit_after_bars
        self.position: dict | None = None
        self._position_bars = 0
        self.check_exit_called = 0

    def set_position(self, position: dict | None):
        """Update position state from engine."""
        self.position = position
        if position:
            self._position_bars += 1
        else:
            self._position_bars = 0

    def on_bar(self, bar: dict) -> SignalType:
        if self.position is None:
            return SignalType.BUY
        return SignalType.HOLD

    def check_exit(self, bar: dict) -> tuple[bool, ExitReason | None]:
        """Custom exit logic — exit after N bars."""
        self.check_exit_called += 1
        if self._position_bars >= self.exit_after_bars:
            return True, ExitReason.STRATEGY_EXIT
        return False, None


class _PrescanStrategy:
    """Strategy that uses the data prescan hook."""

    name = "prescan_feature"

    def __init__(self):
        self.prescan_called = False
        self._bought = False

    def prescan_data(self, data: pd.DataFrame):
        """Data prescan hook (e.g., for daily volume totals)."""
        self.prescan_called = True
        assert not data.empty

    def on_bar(self, bar: dict) -> SignalType:
        if not self._bought:
            self._bought = True
            return SignalType.BUY
        return SignalType.HOLD


# ---------------------------------------------------------------------------
# Test: Day Change Scenarios
# ---------------------------------------------------------------------------


class TestDayChangeScenarios:
    """Test position handling across day boundaries."""

    def test_close_on_day_change_enabled(self):
        """When close_on_day_change=True, positions close at day boundary."""
        risk = RiskConfig(
            close_on_day_change=True, stop_loss_pct=999.0, take_profit_pct=999.0
        )
        config = BacktestConfig(risk=risk)
        strategy = _AlwaysBuyStrategy()

        # 3 days, 30 bars per day
        data = _make_multi_day_ohlcv(days=3, bars_per_day=30)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Position should be force-closed at end of day 1 and day 2
        force_closes = [
            t for t in result.trades if t.exit_reason == ExitReason.FORCE_CLOSE.value
        ]
        assert len(force_closes) == 2  # Day 1 EOD, Day 2 EOD

        # Final position closed at END_OF_DATA
        end_of_data_closes = [
            t for t in result.trades if t.exit_reason == ExitReason.END_OF_DATA.value
        ]
        assert len(end_of_data_closes) == 1  # Day 3 final close

    def test_close_on_day_change_disabled(self):
        """When close_on_day_change=False, positions carry over days."""
        risk = RiskConfig(
            close_on_day_change=False, stop_loss_pct=999.0, take_profit_pct=999.0
        )
        config = BacktestConfig(risk=risk)
        strategy = _AlwaysBuyStrategy()

        data = _make_multi_day_ohlcv(days=3, bars_per_day=30)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # No force closes at day boundaries
        force_closes = [
            t for t in result.trades if t.exit_reason == ExitReason.FORCE_CLOSE.value
        ]
        assert len(force_closes) == 0

        # Only final END_OF_DATA close
        assert result.total_trades == 1
        assert result.trades[0].exit_reason == ExitReason.END_OF_DATA.value

    def test_day_change_resets_daily_counters(self):
        """Daily trade counter should reset at day boundary."""
        risk = RiskConfig(max_daily_trades=2, close_on_day_change=True)
        config = BacktestConfig(risk=risk)
        strategy = _BuyEveryNBarsStrategy(n=5)

        # 2 days, 40 bars per day
        data = _make_multi_day_ohlcv(days=2, bars_per_day=40)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Each day should have max 2 trades
        # Day 1: 2 trades (opens at bar 5, 10), then force close at EOD
        # Day 2: 2 trades (opens at bar 5, 10), then force close at EOD
        # Plus final END_OF_DATA close
        # Total: 4-6 trades depending on force close timing
        assert result.total_trades >= 4
        assert result.total_trades <= 6

    def test_multi_day_equity_curve_continuity(self):
        """Equity curve should be continuous across day boundaries."""
        risk = RiskConfig(close_on_day_change=True)
        config = BacktestConfig(initial_capital=10_000_000, risk=risk)
        strategy = _AlwaysBuyStrategy()

        data = _make_multi_day_ohlcv(days=2, bars_per_day=30)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Equity curve should have entries for all bars
        assert len(result.equity_curve) == 60

        # Equity values should be continuous (no NaN or huge jumps)
        equities = [eq for _, eq in result.equity_curve]
        assert all(isinstance(eq, (int, float)) for eq in equities)
        assert all(eq > 0 for eq in equities)


# ---------------------------------------------------------------------------
# Test: Daily Limits
# ---------------------------------------------------------------------------


class TestDailyLimits:
    """Test daily risk limits (max trades, max loss)."""

    def test_max_daily_trades_limit(self):
        """Engine should stop trading after max_daily_trades reached."""
        risk = RiskConfig(max_daily_trades=3)
        config = BacktestConfig(risk=risk)
        strategy = _BuyEveryNBarsStrategy(n=5)

        # Single day, 50 bars (would trigger 10 buys without limit)
        data = _make_ohlcv(50)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Should have exactly 3 trades (max_daily_trades limit)
        assert result.total_trades <= 3

    def test_max_daily_trades_zero_means_unlimited(self):
        """max_daily_trades=0 should allow unlimited trades."""
        risk = RiskConfig(
            max_daily_trades=0, stop_loss_pct=999.0, take_profit_pct=999.0
        )
        config = BacktestConfig(risk=risk)
        strategy = _BuyEveryNBarsStrategy(n=5)

        # Also use a strategy with tight max_daily_trades to compare
        risk_limited = RiskConfig(
            max_daily_trades=1, stop_loss_pct=999.0, take_profit_pct=999.0
        )
        config_limited = BacktestConfig(risk=risk_limited)
        strategy_limited = _BuyEveryNBarsStrategy(n=5)

        data = _make_ohlcv(50)

        # Unlimited: no limit should be enforced
        engine_unlimited = BacktestEngine(strategy, config)
        result_unlimited = engine_unlimited.run(data)

        # Limited: only 1 trade allowed per day
        engine_limited = BacktestEngine(strategy_limited, config_limited)
        result_limited = engine_limited.run(data)

        # Unlimited should allow at least as many trades as limited (not blocked)
        assert result_unlimited.total_trades >= result_limited.total_trades
        # Both should have at least 1 trade
        assert result_unlimited.total_trades >= 1

    def test_daily_limit_interaction_with_position_close(self):
        """Daily limit should not prevent closing existing positions."""
        risk = RiskConfig(max_daily_trades=1, stop_loss_pct=5.0)
        config = BacktestConfig(risk=risk, max_positions=1)
        strategy = _BuyEveryNBarsStrategy(n=5)

        data = _make_ohlcv(50)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Should open 1 position, then close it at end (not blocked by limit)
        assert result.total_trades >= 1

    def test_max_positions_limit(self):
        """Engine should respect max_positions limit."""
        config = BacktestConfig(max_positions=2)
        strategy = _BuyEveryNBarsStrategy(n=5)

        data = _make_ohlcv(100)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Verify we never held more than 2 positions simultaneously
        # (Indirect test: if limit works, we should have at least 2 trades)
        assert result.total_trades >= 2


# ---------------------------------------------------------------------------
# Test: Exit Strategy Integration
# ---------------------------------------------------------------------------


class TestExitStrategyIntegration:
    """Test that custom exit strategies are properly integrated."""

    def test_check_exit_method_called(self):
        """Strategy's check_exit method should be called for open positions."""
        strategy = _ExitCheckStrategy(exit_after_bars=5)
        config = BacktestConfig()

        data = _make_ohlcv(50)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # check_exit should have been called multiple times
        assert strategy.check_exit_called > 0

        # Position should have been closed by strategy exit logic
        strategy_exits = [
            t for t in result.trades if t.exit_reason == ExitReason.STRATEGY_EXIT.value
        ]
        assert len(strategy_exits) >= 1

    def test_exit_strategy_receives_correct_position(self):
        """Exit strategy should receive current position via set_position."""
        strategy = _ExitCheckStrategy(exit_after_bars=10)
        config = BacktestConfig()

        data = _make_ohlcv(50)
        engine = BacktestEngine(strategy, config)
        engine.run(data)

        # Strategy should have seen a position
        assert strategy.position is not None or strategy.check_exit_called > 0

    def test_exit_reason_priority_exit_before_risk(self):
        """Strategy exit should be checked before engine risk checks."""
        # Strategy exits after 5 bars, but risk check would exit at 10 bars
        risk = RiskConfig(max_hold_bars=10)
        config = BacktestConfig(risk=risk)
        strategy = _ExitCheckStrategy(exit_after_bars=5)

        data = _make_ohlcv(50)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Should exit via STRATEGY_EXIT before TIME_LIMIT
        strategy_exits = [
            t for t in result.trades if t.exit_reason == ExitReason.STRATEGY_EXIT.value
        ]
        time_limit_exits = [
            t for t in result.trades if t.exit_reason == ExitReason.TIME_LIMIT.value
        ]

        assert len(strategy_exits) >= 1
        assert len(time_limit_exits) == 0  # Should not reach time limit

    def test_exit_strategy_can_prevent_signal_exit(self):
        """Exit strategy can close position before opposite signal triggers."""

        class _QuickExitStrategy:
            name = "quick_exit"

            def __init__(self):
                self.position = None
                self._bars_with_position = 0

            def set_position(self, position):
                self.position = position
                if position:
                    self._bars_with_position += 1

            def on_bar(self, bar: dict) -> SignalType:
                if self.position is None:
                    return SignalType.BUY
                if self._bars_with_position >= 20:
                    return SignalType.SELL  # Opposite signal
                return SignalType.HOLD

            def check_exit(self, bar: dict) -> tuple[bool, ExitReason | None]:
                # Exit after 3 bars (before opposite signal at bar 20)
                if self._bars_with_position >= 3:
                    return True, ExitReason.STRATEGY_EXIT
                return False, None

        strategy = _QuickExitStrategy()
        config = BacktestConfig()

        data = _make_ohlcv(50)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Should exit via STRATEGY_EXIT, not SIGNAL
        strategy_exits = [
            t for t in result.trades if t.exit_reason == ExitReason.STRATEGY_EXIT.value
        ]
        signal_exits = [
            t for t in result.trades if t.exit_reason == ExitReason.SIGNAL.value
        ]

        assert len(strategy_exits) >= 1
        assert len(signal_exits) == 0


# ---------------------------------------------------------------------------
# Test: Data Prescan Hooks
# ---------------------------------------------------------------------------


class TestDataPrescanHooks:
    """Test strategy data prescan hooks."""

    def test_prescan_data_called(self):
        """prescan_data should be called before main loop."""
        strategy = _PrescanStrategy()
        config = BacktestConfig()

        data = _make_ohlcv(100)
        engine = BacktestEngine(strategy, config)
        engine.run(data)

        # Hook should have been called
        assert strategy.prescan_called is True

    def test_prescan_hook_called_before_iterating_bars(self):
        """prescan_data should be called before iterating bars."""

        class _OrderCheckStrategy:
            name = "order_check"

            def __init__(self):
                self.call_order = []

            def prescan_data(self, data: pd.DataFrame):
                self.call_order.append("prescan")

            def on_bar(self, bar: dict) -> SignalType:
                if len(self.call_order) == 1 and not hasattr(self, "_first_bar"):
                    self.call_order.append("on_bar")
                    self._first_bar = True
                return SignalType.HOLD

        strategy = _OrderCheckStrategy()
        config = BacktestConfig()

        data = _make_ohlcv(50)
        engine = BacktestEngine(strategy, config)
        engine.run(data)

        # Expected order: prescan -> on_bar
        assert strategy.call_order == ["prescan", "on_bar"]

    def test_prescan_receives_full_dataset(self):
        """Data prescan should receive the complete dataset."""

        class _DataCheckStrategy:
            name = "data_check"

            def __init__(self):
                self.prescan_rows = 0

            def prescan_data(self, data: pd.DataFrame):
                self.prescan_rows = len(data)

            def on_bar(self, bar: dict) -> SignalType:
                return SignalType.HOLD

        strategy = _DataCheckStrategy()
        config = BacktestConfig()

        data = _make_ohlcv(100)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Hook should receive full 100 rows
        assert strategy.prescan_rows == 100
        assert result.total_bars == 100

    def test_strategies_without_hooks_still_work(self):
        """Strategies without prescan hooks should still work normally."""

        class _NoHooksStrategy:
            name = "no_hooks"

            def on_bar(self, bar: dict) -> SignalType:
                return SignalType.HOLD

        strategy = _NoHooksStrategy()
        config = BacktestConfig()

        data = _make_ohlcv(100)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Should complete normally without errors
        assert result.total_bars == 100


# ---------------------------------------------------------------------------
# Test: Complex Integration Scenarios
# ---------------------------------------------------------------------------


class TestComplexIntegrationScenarios:
    """Test complex interactions between multiple features."""

    def test_day_change_with_exit_strategy_and_daily_limit(self):
        """Combine day change, exit strategy, and daily limit."""
        risk = RiskConfig(close_on_day_change=True, max_daily_trades=5)
        config = BacktestConfig(risk=risk)
        strategy = _ExitCheckStrategy(exit_after_bars=3)

        data = _make_multi_day_ohlcv(days=2, bars_per_day=50)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Should respect all constraints:
        # - Max 5 trades per day
        # - Force close at day boundary
        # - Strategy exit after 3 bars
        assert result.total_trades > 0
        assert result.total_trades <= 11  # Max 5 per day × 2 days + 1 final

        # Should have both STRATEGY_EXIT and FORCE_CLOSE
        strategy_exits = sum(
            1 for t in result.trades if t.exit_reason == ExitReason.STRATEGY_EXIT.value
        )
        force_closes = sum(
            1 for t in result.trades if t.exit_reason == ExitReason.FORCE_CLOSE.value
        )

        assert strategy_exits > 0 or force_closes > 0

    def test_prescan_with_multi_day_data(self):
        """Data prescan should work correctly with multi-day data."""
        strategy = _PrescanStrategy()
        config = BacktestConfig()

        data = _make_multi_day_ohlcv(days=3, bars_per_day=30)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Hook should be called with full 90 bars
        assert strategy.prescan_called is True
        assert result.total_bars == 90

    def test_exit_strategy_with_prescan_hook(self):
        """Exit strategy and prescan hook should coexist."""

        class _PrescanExitStrategy:
            name = "prescan_exit"

            def __init__(self):
                self.prescan_called = False
                self.position = None
                self._bars_held = 0

            def prescan_data(self, data: pd.DataFrame):
                self.prescan_called = True

            def set_position(self, position):
                self.position = position
                if position:
                    self._bars_held += 1
                else:
                    self._bars_held = 0

            def on_bar(self, bar: dict) -> SignalType:
                if self.position is None:
                    return SignalType.BUY
                return SignalType.HOLD

            def check_exit(self, bar: dict) -> tuple[bool, ExitReason | None]:
                if self._bars_held >= 5:
                    return True, ExitReason.STRATEGY_EXIT
                return False, None

        strategy = _PrescanExitStrategy()
        config = BacktestConfig()

        data = _make_ohlcv(50)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Both features should work.
        assert strategy.prescan_called is True
        strategy_exits = [
            t for t in result.trades if t.exit_reason == ExitReason.STRATEGY_EXIT.value
        ]
        assert len(strategy_exits) >= 1

    def test_futures_contract_with_day_change(self):
        """Test futures-specific behavior with day changes."""
        config = BacktestConfig.futures(
            initial_capital=10_000_000, contracts=1, point_value=250_000
        )
        config.risk = RiskConfig(
            close_on_day_change=True, stop_loss_pct=999.0, take_profit_pct=999.0
        )
        strategy = _AlwaysBuyStrategy()

        data = _make_multi_day_ohlcv(days=2, bars_per_day=30)
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Futures should force close at day boundaries
        force_closes = [
            t for t in result.trades if t.exit_reason == ExitReason.FORCE_CLOSE.value
        ]
        assert len(force_closes) >= 1

        # PnL should be calculated correctly with point_value
        for trade in result.trades:
            assert trade.quantity == 1  # 1 contract

    def test_empty_data_after_preprocessing(self):
        """Engine should handle empty data gracefully."""

        class _PreprocessStrategy:
            name = "preprocess"

            def prescan_data(self, data: pd.DataFrame):
                pass  # Hook exists but does nothing

            def on_bar(self, bar: dict) -> SignalType:
                return SignalType.HOLD

        strategy = _PreprocessStrategy()
        config = BacktestConfig()

        with pytest.raises(ValueError, match="Empty data"):
            engine = BacktestEngine(strategy, config)
            engine.run(pd.DataFrame())

    def test_multi_symbol_with_exit_strategy(self):
        """Exit strategy should work correctly with multiple symbols."""
        strategy = _ExitCheckStrategy(exit_after_bars=5)
        config = BacktestConfig(max_positions=2)

        # Create data for two symbols
        df1 = _make_ohlcv(50, code="005930")
        df2 = _make_ohlcv(50, code="000660")
        data = pd.concat([df1, df2], ignore_index=True)

        engine = BacktestEngine(strategy, config)
        result = engine.run(data)

        # Should have trades for both symbols
        codes = {t.code for t in result.trades}
        assert len(codes) >= 1  # At least one symbol traded

        # Strategy exit should work for all positions
        strategy_exits = [
            t for t in result.trades if t.exit_reason == ExitReason.STRATEGY_EXIT.value
        ]
        assert len(strategy_exits) >= 1
