"""Unit tests for Daily Pullback + Chandelier Exit strategy.

Tests cover:
- DailyPullbackEntry signal generation
- ChandelierExit exit logic
- DailyBacktestAdapter indicator pre-computation
- Registry integration
- BacktestEngine integration with daily data
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from shared.backtest.engine import BacktestEngine, SignalType
from shared.models.signal import ExitReason as ModelExitReason, SignalType as ModelSignalType
from shared.strategy.base import EntryContext, ExitContext
from shared.strategy.entry.daily_pullback import DailyPullbackConfig, DailyPullbackEntry
from shared.strategy.exit.chandelier_exit import ChandelierExitConfig, ChandelierExit


# ── Fixtures ──


@pytest.fixture
def entry_config():
    return DailyPullbackConfig(
        sma_long_period=200,
        sma_short_period=20,
        sma_mid_period=60,
        rsi_period=5,
        rsi_oversold=45.0,
        require_mid_trend=True,
        mid_trend_lookback=5,
        stop_loss_pct=7.0,
        signal_cooldown_days=5,
    )


@pytest.fixture
def entry_strategy(entry_config):
    return DailyPullbackEntry(entry_config)


@pytest.fixture
def exit_config():
    return ChandelierExitConfig(
        atr_period=22,
        atr_multiplier=3.0,
        lookback_period=22,
        hard_stop_pct=-0.07,
        max_hold_days=60,
    )


@pytest.fixture
def exit_strategy(exit_config):
    return ChandelierExit(exit_config)


def _make_entry_context(
    code: str = "005930",
    close: float = 70000,
    sma_200: float = 65000,
    sma_20: float = 71000,
    sma_60: float = 68000,
    sma_60_prev: float = 67000,
    rsi_5: float = 35.0,
    timestamp: datetime | None = None,
) -> EntryContext:
    """Helper to build EntryContext for entry tests."""
    return EntryContext(
        market_data={"code": code, "name": "삼성전자", "close": close},
        indicators={
            "sma_200": sma_200,
            "sma_20": sma_20,
            "sma_60": sma_60,
            "sma_60_prev": sma_60_prev,
            "rsi_5": rsi_5,
        },
        current_positions=[],
        timestamp=timestamp or datetime(2026, 2, 20, 0, 0),
        metadata={},
    )


# ── DailyPullbackEntry Tests ──


class TestDailyPullbackEntry:
    """Test entry signal generation."""

    def test_signal_generated_on_valid_pullback(self, entry_strategy):
        """All conditions met → BUY signal."""
        context = _make_entry_context(
            close=70000,      # > SMA200 (65000) ✓
            sma_200=65000,
            sma_20=71000,     # close <= SMA20 ✓
            rsi_5=35.0,       # < 45 ✓
            sma_60=68000,     # > sma_60_prev ✓
            sma_60_prev=67000,
        )
        signal = asyncio.get_event_loop().run_until_complete(
            entry_strategy.generate(context)
        )
        assert signal is not None
        assert signal.strategy == "daily_pullback"
        assert signal.metadata["signal_direction"] == "long"
        assert signal.metadata["stop_loss"] == pytest.approx(70000 * 0.93)  # -7%

    def test_no_signal_below_sma200(self, entry_strategy):
        """close < SMA200 → no signal (not in uptrend)."""
        context = _make_entry_context(close=64000, sma_200=65000)
        signal = asyncio.get_event_loop().run_until_complete(
            entry_strategy.generate(context)
        )
        assert signal is None

    def test_no_signal_above_sma20(self, entry_strategy):
        """close > SMA20 → no signal (not a pullback)."""
        context = _make_entry_context(close=72000, sma_20=71000)
        signal = asyncio.get_event_loop().run_until_complete(
            entry_strategy.generate(context)
        )
        assert signal is None

    def test_no_signal_rsi_too_high(self, entry_strategy):
        """RSI >= 45 → no signal."""
        context = _make_entry_context(rsi_5=50.0)
        signal = asyncio.get_event_loop().run_until_complete(
            entry_strategy.generate(context)
        )
        assert signal is None

    def test_no_signal_mid_trend_declining(self, entry_strategy):
        """SMA60 declining → no signal (require_mid_trend=True)."""
        context = _make_entry_context(
            sma_60=67000,      # < sma_60_prev
            sma_60_prev=68000,
        )
        signal = asyncio.get_event_loop().run_until_complete(
            entry_strategy.generate(context)
        )
        assert signal is None

    def test_signal_without_mid_trend_filter(self):
        """With require_mid_trend=False, declining SMA60 still triggers."""
        config = DailyPullbackConfig(require_mid_trend=False)
        strategy = DailyPullbackEntry(config)
        context = _make_entry_context(
            sma_60=67000,
            sma_60_prev=68000,
        )
        signal = asyncio.get_event_loop().run_until_complete(
            strategy.generate(context)
        )
        assert signal is not None

    def test_cooldown_prevents_repeat_signal(self, entry_strategy):
        """Signal within cooldown_days → no signal."""
        context1 = _make_entry_context(timestamp=datetime(2026, 2, 20))
        signal1 = asyncio.get_event_loop().run_until_complete(
            entry_strategy.generate(context1)
        )
        assert signal1 is not None

        # Same code, 2 days later (within 5-day cooldown)
        context2 = _make_entry_context(timestamp=datetime(2026, 2, 22))
        signal2 = asyncio.get_event_loop().run_until_complete(
            entry_strategy.generate(context2)
        )
        assert signal2 is None

    def test_signal_after_cooldown_expires(self, entry_strategy):
        """Signal after cooldown expires → new signal."""
        context1 = _make_entry_context(timestamp=datetime(2026, 2, 20))
        asyncio.get_event_loop().run_until_complete(entry_strategy.generate(context1))

        # 6 days later (cooldown expired)
        context2 = _make_entry_context(timestamp=datetime(2026, 2, 26))
        signal2 = asyncio.get_event_loop().run_until_complete(
            entry_strategy.generate(context2)
        )
        assert signal2 is not None

    def test_confidence_increases_with_deeper_oversold(self, entry_strategy):
        """Deeper RSI oversold → higher confidence."""
        ctx_mild = _make_entry_context(rsi_5=42.0, timestamp=datetime(2026, 1, 1))
        sig_mild = asyncio.get_event_loop().run_until_complete(
            entry_strategy.generate(ctx_mild)
        )

        ctx_deep = _make_entry_context(rsi_5=20.0, timestamp=datetime(2026, 2, 1))
        sig_deep = asyncio.get_event_loop().run_until_complete(
            entry_strategy.generate(ctx_deep)
        )

        assert sig_mild is not None and sig_deep is not None
        assert sig_deep.confidence > sig_mild.confidence

    def test_config_from_dict(self):
        """ConfigMixin.from_dict() works correctly."""
        config = DailyPullbackConfig.from_dict({
            "sma_long_period": 100,
            "rsi_oversold": 30.0,
            "unknown_field": "ignored",
        })
        assert config.sma_long_period == 100
        assert config.rsi_oversold == 30.0
        assert config.sma_short_period == 20  # default

    def test_config_from_dict_with_params_key(self):
        """ConfigMixin.from_dict() unwraps 'params' key."""
        config = DailyPullbackConfig.from_dict({
            "params": {"sma_long_period": 100}
        })
        assert config.sma_long_period == 100


# ── ChandelierExit Tests ──


class TestChandelierExit:
    """Test exit signal generation."""

    def _make_exit_context(
        self,
        entry_price: float = 70000,
        close: float = 72000,
        atr: float = 1500,
        highest_high: float = 75000,
        holding_days: int = 10,
    ) -> ExitContext:
        from shared.models.position import Position, PositionSide

        position = Position(
            id="bt_005930",
            code="005930",
            name="삼성전자",
            strategy="daily_pullback",
            side=PositionSide.LONG,
            entry_price=entry_price,
            quantity=100,
            current_price=close,
        )
        return ExitContext(
            position=position,
            market_data={"code": "005930", "close": close},
            indicators={
                "atr": atr,
                "highest_high": highest_high,
                "holding_days": holding_days,
            },
            timestamp=datetime(2026, 3, 1),
            metadata={"is_backtest": True},
        )

    def test_no_exit_within_chandelier(self, exit_strategy):
        """Price above chandelier stop → no exit."""
        # chandelier = 75000 - 1500*3 = 70500. close=72000 > 70500
        context = self._make_exit_context(close=72000)
        should_exit, signal = asyncio.get_event_loop().run_until_complete(
            exit_strategy.should_exit(context)
        )
        assert not should_exit

    def test_chandelier_exit_triggered(self, exit_strategy):
        """Price below chandelier stop → trailing stop exit."""
        # chandelier = 75000 - 1500*3 = 70500. close=70000 < 70500
        context = self._make_exit_context(close=70000)
        should_exit, signal = asyncio.get_event_loop().run_until_complete(
            exit_strategy.should_exit(context)
        )
        assert should_exit
        assert signal.reason == ModelExitReason.TRAILING_STOP
        assert signal.metadata["exit_type"] == "chandelier"

    def test_hard_stop_exit(self, exit_strategy):
        """Price drops > 7% → hard stop (priority over chandelier)."""
        # entry=70000, -7% = 65100. close=64000 → loss=-8.6%
        context = self._make_exit_context(
            entry_price=70000,
            close=64000,
            highest_high=70000,
            atr=1000,  # chandelier=70000-3000=67000 > 64000 too, but hard stop is priority 1
        )
        should_exit, signal = asyncio.get_event_loop().run_until_complete(
            exit_strategy.should_exit(context)
        )
        assert should_exit
        assert signal.reason == ModelExitReason.STOP_LOSS
        assert signal.priority == 1

    def test_max_hold_exit(self, exit_strategy):
        """Holding > 60 days → time cut."""
        context = self._make_exit_context(
            close=72000,  # price is fine
            holding_days=61,
        )
        should_exit, signal = asyncio.get_event_loop().run_until_complete(
            exit_strategy.should_exit(context)
        )
        assert should_exit
        assert signal.reason == ModelExitReason.TIME_CUT

    def test_config_from_dict(self):
        """ChandelierExitConfig.from_dict() works."""
        config = ChandelierExitConfig.from_dict({
            "atr_multiplier": 2.5,
            "max_hold_days": 30,
        })
        assert config.atr_multiplier == 2.5
        assert config.max_hold_days == 30


# ── DailyBacktestAdapter Tests ──


class TestDailyBacktestAdapter:
    """Test adapter indicator pre-computation and signal routing."""

    def _make_daily_df(self, n_bars: int = 250) -> pd.DataFrame:
        """Generate synthetic daily OHLCV data with an uptrend + pullback."""
        np.random.seed(42)
        dates = [datetime(2025, 1, 2) + timedelta(days=i) for i in range(n_bars)]

        # Uptrend with noise
        base_price = 60000
        trend = np.linspace(0, 20000, n_bars)
        noise = np.random.normal(0, 500, n_bars).cumsum()
        closes = base_price + trend + noise

        # Create OHLCV
        highs = closes + np.random.uniform(100, 1000, n_bars)
        lows = closes - np.random.uniform(100, 1000, n_bars)
        opens = closes + np.random.uniform(-500, 500, n_bars)
        volumes = np.random.randint(100000, 5000000, n_bars)

        return pd.DataFrame({
            "code": "005930",
            "datetime": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        })

    def test_prescan_computes_indicators(self):
        """prescan_data() fills SMA/RSI/ATR for all bars."""
        from shared.backtest.daily_adapter import DailyBacktestAdapter
        from shared.strategy.registry import StrategyFactory, register_builtin_components

        register_builtin_components()

        from shared.config.loader import ConfigLoader
        strategy_config = ConfigLoader.load_strategy("stock", "daily_pullback")
        strategy = StrategyFactory.create(strategy_config)
        adapter = DailyBacktestAdapter(strategy, strategy_config)

        df = self._make_daily_df(250)
        adapter.prescan_data(df)

        # After SMA200 warmup (bar 199), indicators should be valid
        assert len(adapter._precomputed) == 250

        # Check bar 220 has all indicators
        bar_220 = adapter._precomputed[220]
        assert not np.isnan(bar_220["sma_200"])
        assert not np.isnan(bar_220["sma_20"])
        assert not np.isnan(bar_220["rsi_5"])
        assert not np.isnan(bar_220["atr"])
        assert not np.isnan(bar_220["highest_high"])

    def test_on_bar_returns_hold_during_warmup(self):
        """During SMA200 warmup, on_bar() returns HOLD."""
        from shared.backtest.daily_adapter import DailyBacktestAdapter
        from shared.strategy.registry import StrategyFactory, register_builtin_components

        register_builtin_components()

        from shared.config.loader import ConfigLoader
        strategy_config = ConfigLoader.load_strategy("stock", "daily_pullback")
        strategy = StrategyFactory.create(strategy_config)
        adapter = DailyBacktestAdapter(strategy, strategy_config)

        df = self._make_daily_df(250)
        adapter.prescan_data(df)

        # Bar 10 (way before SMA200 warmup)
        bar = df.iloc[10].to_dict()
        signal = adapter.on_bar(bar)
        assert signal == SignalType.HOLD


# ── Registry Integration Test ──


class TestRegistryIntegration:
    """Test that strategies are properly registered."""

    def test_daily_pullback_registered(self):
        from shared.strategy.registry import (
            EntryRegistry,
            ExitRegistry,
            register_builtin_components,
        )

        register_builtin_components()

        assert EntryRegistry.is_registered("daily_pullback")
        assert ExitRegistry.is_registered("chandelier_exit")

    def test_strategy_factory_creates_from_config(self):
        from shared.config.loader import ConfigLoader
        from shared.strategy.registry import StrategyFactory, register_builtin_components

        register_builtin_components()

        strategy = StrategyFactory.create_from_file("stock", "daily_pullback")
        assert strategy.name == "daily_pullback"
        assert strategy.entry.name == "daily_pullback"
        assert strategy.exit.name == "chandelier_exit"
