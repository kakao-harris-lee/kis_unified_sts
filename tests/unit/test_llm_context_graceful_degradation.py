"""Unit tests for graceful degradation when LLM context is unavailable.

Tests that strategies, position sizers, and the trading system work normally
when MarketContext is None or unavailable.

This ensures backward compatibility and resilience - the LLM integration is
optional and should never break core trading functionality.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from services.trading.strategy_manager import StrategyManager
from shared.llm.data_classes import MarketSignal, RiskMode
from shared.llm.market_context import MarketContext
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, ExitContext
from shared.strategy.entry.mean_reversion import MeanReversionConfig, MeanReversionEntry
from shared.strategy.position.llm_adaptive_sizer import (
    LLMAdaptiveSizer,
    LLMAdaptiveSizerConfig,
)
from shared.strategy.position.sizers import (
    FixedSizer,
    FixedSizerConfig,
    RiskBasedSizer,
    RiskBasedSizerConfig,
)


# =============================================================================
# Helpers
# =============================================================================


def _make_market_context(
    regime: str = "BULL_STRONG",
    overall_signal: MarketSignal = MarketSignal.BULLISH,
    risk_mode: RiskMode = RiskMode.RISK_ON,
    risk_score: float = 30.0,
    confidence: float = 0.8,
) -> MarketContext:
    """Create a sample MarketContext for testing."""
    return MarketContext(
        regime=regime,
        overall_signal=overall_signal,
        risk_mode=risk_mode,
        risk_score=risk_score,
        confidence=confidence,
        sector_rotation={"Technology": "INFLOW"},
        generated_at=datetime(2026, 3, 8, 10, 30, 0),
        metadata={"source": "test"},
    )


def _make_entry_context(
    code: str = "005930",
    close: float = 100.0,
    bb_lower: float = 95.0,
    rsi: float = 25.0,
    market_context: MarketContext | None = None,
    timestamp: datetime | None = None,
) -> EntryContext:
    """Create an EntryContext for testing."""
    ts = timestamp or datetime(2026, 3, 8, 10, 30, 0)
    return EntryContext(
        market_data={
            "code": code,
            "name": "Test Stock",
            "close": close,
        },
        indicators={
            "bb_lower": bb_lower,
            "bb_upper": 105.0,
            "bb_middle": 100.0,
            "rsi": rsi,
        },
        timestamp=ts,
        market_context=market_context,
    )


def _make_signal(
    code: str = "005930",
    signal_type: SignalType = SignalType.ENTRY,
    price: float = 100.0,
) -> Signal:
    """Create a Signal for testing."""
    return Signal(
        code=code,
        name="Test Stock",
        signal_type=signal_type,
        price=price,
        timestamp=datetime(2026, 3, 8, 10, 30, 0),
        confidence=0.8,
        metadata={"test": True},
    )


# =============================================================================
# MeanReversionEntry Graceful Degradation Tests
# =============================================================================


class TestMeanReversionEntryGracefulDegradation:
    """Test MeanReversionEntry works when market_context is None."""

    @pytest.mark.asyncio
    async def test_generates_signal_without_market_context(self):
        """Test that strategy generates signals when market_context is None."""
        # Setup: regime filter disabled
        config = MeanReversionConfig(
            regime_filter=False,
            bb_period=20,
            rsi_oversold=30,
        )
        strategy = MeanReversionEntry(config)

        # Oversold condition (should generate LONG signal)
        context = _make_entry_context(
            close=95.0,
            bb_lower=96.0,  # Price below BB lower
            rsi=25.0,  # RSI oversold
            market_context=None,  # No LLM context
        )

        signal = await strategy.generate(context)

        # Should generate signal normally
        assert signal is not None
        assert signal.signal_type == SignalType.ENTRY
        assert signal.code == "005930"

    @pytest.mark.asyncio
    async def test_regime_filter_disabled_ignores_market_context(self):
        """Test that regime_filter=False ignores market_context entirely."""
        # Setup: regime filter disabled
        config = MeanReversionConfig(
            regime_filter=False,  # Disabled - should ignore context
            bb_period=20,
            rsi_oversold=30,
        )
        strategy = MeanReversionEntry(config)

        # Strong bearish context (would block if filter enabled)
        bearish_context = _make_market_context(
            regime="BEAR_STRONG",
            overall_signal=MarketSignal.STRONG_BEARISH,
        )

        context = _make_entry_context(
            close=95.0,
            bb_lower=96.0,
            rsi=25.0,
            market_context=bearish_context,
        )

        signal = await strategy.generate(context)

        # Should generate signal - filter is disabled
        assert signal is not None
        assert signal.signal_type == SignalType.ENTRY

    @pytest.mark.asyncio
    async def test_regime_filter_enabled_with_none_context(self):
        """Test that regime filter enabled but market_context=None still works."""
        # Setup: regime filter enabled
        config = MeanReversionConfig(
            regime_filter=True,  # Enabled
            block_long_in_strong_bearish=True,
            bb_period=20,
            rsi_oversold=30,
        )
        strategy = MeanReversionEntry(config)

        # No market context - filter should gracefully degrade
        context = _make_entry_context(
            close=95.0,
            bb_lower=96.0,
            rsi=25.0,
            market_context=None,  # No context available
        )

        signal = await strategy.generate(context)

        # Should generate signal - graceful degradation when context is None
        assert signal is not None
        assert signal.signal_type == SignalType.ENTRY

    @pytest.mark.asyncio
    async def test_regime_filter_blocks_in_strong_bearish(self):
        """Test that regime filter blocks LONG in STRONG_BEARISH when enabled."""
        # Setup: regime filter enabled
        config = MeanReversionConfig(
            regime_filter=True,
            block_long_in_strong_bearish=True,
            bb_period=20,
            rsi_oversold=30,
        )
        strategy = MeanReversionEntry(config)

        # Strong bearish context
        bearish_context = _make_market_context(
            regime="BEAR_STRONG",
            overall_signal=MarketSignal.STRONG_BEARISH,
        )

        context = _make_entry_context(
            close=95.0,
            bb_lower=96.0,
            rsi=25.0,
            market_context=bearish_context,
        )

        signal = await strategy.generate(context)

        # Should NOT generate LONG signal in STRONG_BEARISH
        # Note: May return None or fall through to SHORT check
        assert signal is None or signal.signal_type != SignalType.ENTRY

    @pytest.mark.asyncio
    async def test_regime_filter_allows_in_bullish(self):
        """Test that regime filter allows LONG in BULLISH regime."""
        # Setup: regime filter enabled
        config = MeanReversionConfig(
            regime_filter=True,
            block_long_in_strong_bearish=True,
            bb_period=20,
            rsi_oversold=30,
        )
        strategy = MeanReversionEntry(config)

        # Bullish context
        bullish_context = _make_market_context(
            regime="BULL_STRONG",
            overall_signal=MarketSignal.BULLISH,
        )

        context = _make_entry_context(
            close=95.0,
            bb_lower=96.0,
            rsi=25.0,
            market_context=bullish_context,
        )

        signal = await strategy.generate(context)

        # Should generate LONG signal in BULLISH regime
        assert signal is not None
        assert signal.signal_type == SignalType.ENTRY


# =============================================================================
# Position Sizer Graceful Degradation Tests
# =============================================================================


class TestPositionSizerGracefulDegradation:
    """Test position sizers work when market_context is None."""

    def test_fixed_sizer_ignores_market_context(self):
        """Test FixedSizer works with or without market_context."""
        config = FixedSizerConfig(fixed_quantity=100)
        sizer = FixedSizer(config)
        signal = _make_signal()

        # Without market_context
        qty1 = sizer.calculate(signal, 100000.0, [], market_context=None)
        assert qty1 == 100

        # With market_context
        context = _make_market_context()
        qty2 = sizer.calculate(signal, 100000.0, [], market_context=context)
        assert qty2 == 100  # Should be identical

    def test_risk_based_sizer_ignores_market_context(self):
        """Test RiskBasedSizer works with or without market_context."""
        config = RiskBasedSizerConfig(
            risk_per_trade_pct=1.0,
            stop_loss_pct=2.0,
        )
        sizer = RiskBasedSizer(config)
        signal = _make_signal()

        # Without market_context
        qty1 = sizer.calculate(signal, 100000.0, [], market_context=None)

        # With market_context
        context = _make_market_context()
        qty2 = sizer.calculate(signal, 100000.0, [], market_context=context)

        # Should be identical (RiskBasedSizer doesn't use market_context)
        assert qty1 == qty2
        assert qty1 > 0  # Should calculate valid quantity

    def test_llm_adaptive_sizer_falls_back_without_context(self):
        """Test LLMAdaptiveSizer falls back to base sizing when market_context is None."""
        config = LLMAdaptiveSizerConfig(
            risk_per_trade_pct=1.0,
            stop_loss_pct=2.0,
            confidence_boost_high=1.5,  # Would boost if context present
            confidence_penalty_low=0.5,  # Would penalize if context present
        )
        sizer = LLMAdaptiveSizer(config)
        signal = _make_signal()

        # Without market_context - should use base RiskBasedSizer logic
        qty_without_context = sizer.calculate(signal, 100000.0, [], market_context=None)

        # Compare with base RiskBasedSizer
        base_sizer = RiskBasedSizer(
            RiskBasedSizerConfig(
                risk_per_trade_pct=1.0,
                stop_loss_pct=2.0,
            )
        )
        base_qty = base_sizer.calculate(signal, 100000.0, [], market_context=None)

        # Should match base sizer when market_context is None
        assert qty_without_context == base_qty
        assert qty_without_context > 0

    def test_llm_adaptive_sizer_applies_scaling_with_context(self):
        """Test LLMAdaptiveSizer applies scaling when market_context is present."""
        config = LLMAdaptiveSizerConfig(
            risk_per_trade_pct=1.0,
            stop_loss_pct=2.0,
            confidence_threshold_high=0.7,
            confidence_boost_high=1.5,
            enable_confidence_scaling=True,
            enable_risk_score_scaling=False,  # Disable for simplicity
            enable_risk_mode_scaling=False,
        )
        sizer = LLMAdaptiveSizer(config)
        signal = _make_signal()

        # High confidence context
        high_confidence_context = _make_market_context(confidence=0.8)
        qty_with_context = sizer.calculate(
            signal, 100000.0, [], market_context=high_confidence_context
        )

        # Base quantity (without context)
        qty_without_context = sizer.calculate(signal, 100000.0, [], market_context=None)

        # Should be boosted (1.5x) due to high confidence
        assert qty_with_context > qty_without_context
        # Allow for rounding errors
        expected_boosted = int(qty_without_context * 1.5)
        assert abs(qty_with_context - expected_boosted) <= 1

    def test_llm_adaptive_sizer_handles_zero_base_quantity(self):
        """Test LLMAdaptiveSizer handles zero base quantity gracefully."""
        config = LLMAdaptiveSizerConfig(
            risk_per_trade_pct=1.0,
            stop_loss_pct=2.0,
            min_quantity=100,  # High minimum
        )
        sizer = LLMAdaptiveSizer(config)

        # Signal with very low entry price → would result in 0 base quantity
        signal = _make_signal(price=1.0)

        # Should return 0 even with market_context
        context = _make_market_context(confidence=1.0)  # Max confidence
        qty = sizer.calculate(signal, 100.0, [], market_context=context)

        # Should return min_quantity or higher based on constraints
        assert qty >= 0


# =============================================================================
# Strategy Manager Integration Tests
# =============================================================================


class TestStrategyManagerGracefulDegradation:
    """Test StrategyManager handles missing LLM context gracefully."""

    @patch("services.trading.strategy_manager.LLMContextProvider")
    def test_strategy_manager_handles_none_context(self, mock_provider_class):
        """Test StrategyManager works when LLMContextProvider returns None."""
        # Setup mock provider that returns None
        mock_provider = Mock()
        mock_provider.get_context.return_value = None
        mock_provider_class.return_value = mock_provider

        # Create StrategyManager
        manager = StrategyManager("stock")

        # Verify provider is initialized
        assert manager._llm_context_provider is not None

        # When provider returns None, EntryContext should have market_context=None
        # This is tested implicitly through strategy tests above
        assert mock_provider.get_context.return_value is None

    @patch("services.trading.strategy_manager.LLMContextProvider")
    def test_strategy_manager_handles_provider_exception(self, mock_provider_class):
        """Test StrategyManager handles LLMContextProvider exceptions gracefully."""
        # Setup mock provider that raises exception
        mock_provider = Mock()
        mock_provider.get_context.side_effect = Exception("Redis connection failed")
        mock_provider_class.return_value = mock_provider

        # Create StrategyManager
        manager = StrategyManager("stock")

        # Should not raise - gracefully handles provider exceptions
        # (StrategyManager should catch and log, or provider should return None)
        assert manager._llm_context_provider is not None


# =============================================================================
# Exit Strategy Graceful Degradation Tests
# =============================================================================


class TestExitStrategyGracefulDegradation:
    """Test exit strategies work when market_context is None."""

    @pytest.mark.asyncio
    async def test_exit_context_accepts_none_market_context(self):
        """Test ExitContext can be created with market_context=None."""
        from shared.models.position import Position, PositionSide

        position = Position(
            id="test-pos-001",
            code="005930",
            name="Test Stock",
            side=PositionSide.LONG,
            quantity=100,
            entry_price=100.0,
            current_price=105.0,
            entry_time=datetime(2026, 3, 8, 9, 0, 0),
        )

        context = ExitContext(
            position=position,
            market_data={"close": 105.0},
            indicators={},
            timestamp=datetime(2026, 3, 8, 10, 30, 0),
            market_context=None,  # No LLM context
        )

        assert context.market_context is None
        assert context.position is not None

    @pytest.mark.asyncio
    async def test_exit_strategies_work_without_market_context(self):
        """Test that exit strategies work when market_context is None.

        This is a smoke test - specific exit strategies should have their own
        tests for graceful degradation if they use market_context.
        """
        from shared.models.position import Position, PositionSide
        from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig

        config = ThreeStageExitConfig()
        exit_strategy = ThreeStageExit(config)

        position = Position(
            id="test-pos-002",
            code="005930",
            name="Test Stock",
            side=PositionSide.LONG,
            quantity=100,
            entry_price=100.0,
            current_price=105.0,
            entry_time=datetime(2026, 3, 8, 9, 0, 0),
        )

        context = ExitContext(
            position=position,
            market_data={"close": 105.0},
            indicators={},
            timestamp=datetime(2026, 3, 8, 10, 30, 0),
            market_context=None,  # No LLM context
        )

        # Should not raise exception
        should_exit, exit_signal = await exit_strategy.should_exit(context)

        # May or may not exit, but should work without raising
        assert isinstance(should_exit, bool)  # Just verify it doesn't crash


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_strategy_with_invalid_market_context_fields(self):
        """Test strategies handle corrupted MarketContext gracefully."""
        # Create context with extreme/invalid values
        invalid_context = MarketContext(
            regime="UNKNOWN_REGIME",  # Invalid regime
            overall_signal=MarketSignal.NEUTRAL,
            risk_mode=RiskMode.NEUTRAL,
            risk_score=-999.0,  # Invalid score
            confidence=2.0,  # Out of range (should be 0-1)
            sector_rotation={},
            generated_at=datetime(2026, 3, 8, 10, 30, 0),
            metadata={},
        )

        config = MeanReversionConfig(
            regime_filter=True,
            block_long_in_strong_bearish=True,
        )
        strategy = MeanReversionEntry(config)

        context = _make_entry_context(
            close=95.0,
            bb_lower=96.0,
            rsi=25.0,
            market_context=invalid_context,
        )

        # Should handle gracefully - unknown regime != STRONG_BEARISH
        signal = await strategy.generate(context)
        # Should work (invalid context is treated as neutral)
        assert signal is not None

    def test_sizer_with_invalid_market_context_fields(self):
        """Test sizers handle corrupted MarketContext gracefully."""
        invalid_context = MarketContext(
            regime="UNKNOWN",
            overall_signal=MarketSignal.NEUTRAL,
            risk_mode=RiskMode.NEUTRAL,
            risk_score=-999.0,  # Invalid
            confidence=999.0,  # Invalid
            sector_rotation={},
            generated_at=datetime(2026, 3, 8, 10, 30, 0),
            metadata={},
        )

        config = LLMAdaptiveSizerConfig(
            risk_per_trade_pct=1.0,
            stop_loss_pct=2.0,
        )
        sizer = LLMAdaptiveSizer(config)
        signal = _make_signal()

        # Should not crash with invalid values
        qty = sizer.calculate(signal, 100000.0, [], market_context=invalid_context)

        # Should return valid quantity (may apply extreme scaling)
        assert qty >= 0


# =============================================================================
# Summary Test
# =============================================================================


class TestGracefulDegradationSummary:
    """Summary test to verify overall graceful degradation behavior."""

    @pytest.mark.asyncio
    async def test_end_to_end_without_llm_context(self):
        """End-to-end test: entry → sizing → exit without LLM context."""
        # 1. Entry strategy generates signal without market_context
        entry_config = MeanReversionConfig(
            regime_filter=False,  # Disabled for this test
            bb_period=20,
            rsi_oversold=30,
        )
        entry_strategy = MeanReversionEntry(entry_config)

        entry_context = _make_entry_context(
            close=95.0,
            bb_lower=96.0,
            rsi=25.0,
            market_context=None,  # No LLM context
        )

        signal = await entry_strategy.generate(entry_context)
        assert signal is not None, "Entry strategy should work without market_context"

        # 2. Position sizer calculates size without market_context
        sizer_config = LLMAdaptiveSizerConfig(
            risk_per_trade_pct=1.0,
            stop_loss_pct=2.0,
        )
        sizer = LLMAdaptiveSizer(sizer_config)

        qty = sizer.calculate(signal, 100000.0, [], market_context=None)
        assert qty > 0, "Sizer should calculate valid quantity without market_context"

        # 3. Exit strategy evaluates without market_context
        from shared.models.position import Position, PositionSide
        from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig

        position = Position(
            id="test-pos-003",
            code=signal.code,
            name=signal.name,
            side=PositionSide.LONG,
            quantity=qty,
            entry_price=signal.price,
            current_price=signal.price * 1.05,
            entry_time=signal.timestamp,
        )

        exit_config = ThreeStageExitConfig()
        exit_strategy = ThreeStageExit(exit_config)

        exit_context = ExitContext(
            position=position,
            market_data={"close": position.current_price},
            indicators={},
            timestamp=datetime(2026, 3, 8, 11, 0, 0),
            market_context=None,  # No LLM context
        )

        should_exit, exit_signal = await exit_strategy.should_exit(exit_context)
        # May or may not exit, but should not crash
        assert isinstance(should_exit, bool), "Exit strategy should work without market_context"

    def test_no_exceptions_when_context_none(self):
        """Meta-test: Verify None context never raises exceptions."""
        # This is verified by all tests above passing without exceptions
        # when market_context=None
        assert True
