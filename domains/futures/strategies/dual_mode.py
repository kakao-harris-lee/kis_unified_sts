"""Dual Mode Strategy - Combines MODE_A and MODE_B with State Machine

MODE_A: OFI Mean Reversion (extreme z-scores)
MODE_B: Triple Barrier + TrendEngine (Combined Approach)
        - Triple Barrier CNN-LSTM for direction signal (BUY/SELL)
        - TrendEngine for technical confirmation (MA + Ichimoku)
        - TrendEngine PositionManager for risk management (ATR stops, time cuts)

State Machine:
1. Check liquidity - if below threshold, AVOID
2. Check basis gap - if extreme, MODE_A (arbitrage opportunity)
3. Otherwise, MODE_B (combined triple barrier + trend engine)

Migrated from kospi_mini_sts/src/strategy/strategies/dual_mode.py
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from shared.models.signal import Signal as SignalModel, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.registry import EntryRegistry
from .dl_trend import TechnicalCalculator, TechnicalData, EnsembleFilter

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Trading mode for state machine"""

    AVOID = "AVOID"  # Low liquidity - avoid trading
    MODE_A = "MODE_A"  # Arbitrage opportunity (OFI mean reversion)
    MODE_B = "MODE_B"  # Trend following (Triple Barrier + TrendEngine)


class Signal(Enum):
    """Internal signal enum"""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class DualModeConfig:
    """Configuration for Dual Mode Strategy"""

    # Liquidity thresholds
    liquidity_avoid_threshold: float = 40.0  # Below this = AVOID
    liquidity_mode_a_threshold: float = 50.0  # Above this = MODE_A eligible

    # Basis thresholds for MODE_A
    basis_threshold: float = 1.5  # Z-score threshold for arbitrage

    # MODE_A: Arbitrage settings
    arb_max_spread_ticks: int = 4  # Allow wider spreads
    arb_depth_multiplier: float = 3.0

    # MODE_B: Triple Barrier Classification
    triple_barrier_threshold: float = 0.70  # Confidence threshold for BUY/SELL
    triple_barrier_buffer_size: int = 100  # Rolling OHLCV buffer size

    # MODE_B: Trend settings (legacy - used as fallback)
    trend_dl_threshold: float = 0.60  # Lowered to 0.60~0.65 range
    trend_ma_fast: int = 20
    trend_ma_slow: int = 60
    trend_atr_period: int = 14
    trend_atr_multiplier: float = 2.0  # Reduced for tighter stops
    trend_time_cut_minutes: int = 45  # Extended to let winners run
    trend_max_stop_points: float = 1.5  # Cap max loss at 1.5 points = 75K KRW
    trend_time_cut_atr_threshold: float = 0.3  # Lower bar for favorable movement

    # Order size
    order_size: float = 1.0

    # Decision logging
    enable_decision_logging: bool = True
    enable_telegram: bool = True
    enable_clickhouse: bool = True


@dataclass
class BarData:
    """Bar data for strategy processing"""

    datetime: Optional[datetime] = None
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    spread: float = 0.0
    best_bid: float = 0.0
    best_ask: float = 0.0
    bid_qty1: float = 0.0
    bid_qty2: float = 0.0
    bid_qty3: float = 0.0
    ask_qty1: float = 0.0
    ask_qty2: float = 0.0
    ask_qty3: float = 0.0
    ofi_zscore: float = 0.0
    regime: Optional[str] = None

    # Prediction probabilities
    up_prob: float = 0.5
    down_prob: float = 0.5
    up_prob_h1: float = 0.5
    up_prob_h3: float = 0.5
    up_prob_h5: float = 0.5
    up_prob_h10: float = 0.5

    @classmethod
    def from_dict(cls, data: dict) -> BarData:
        """Create BarData from dictionary"""
        return cls(
            datetime=data.get("datetime"),
            open=float(data.get("open", 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            close=float(data.get("close", 0)),
            volume=float(data.get("volume", 0)),
            spread=float(data.get("spread", 0)),
            best_bid=float(data.get("best_bid", data.get("bid_price_1", 0))),
            best_ask=float(data.get("best_ask", data.get("ask_price_1", 0))),
            bid_qty1=float(data.get("bid_qty1", data.get("bid_qty_1", 0))),
            bid_qty2=float(data.get("bid_qty2", data.get("bid_qty_2", 0))),
            bid_qty3=float(data.get("bid_qty3", data.get("bid_qty_3", 0))),
            ask_qty1=float(data.get("ask_qty1", data.get("ask_qty_1", 0))),
            ask_qty2=float(data.get("ask_qty2", data.get("ask_qty_2", 0))),
            ask_qty3=float(data.get("ask_qty3", data.get("ask_qty_3", 0))),
            ofi_zscore=float(data.get("ofi_zscore", data.get("ofi_z_score", 0))),
            regime=data.get("regime"),
            up_prob=float(data.get("up_prob", 0.5)),
            down_prob=float(data.get("down_prob", 0.5)),
            up_prob_h1=float(data.get("up_prob_h1", 0.5)),
            up_prob_h3=float(data.get("up_prob_h3", 0.5)),
            up_prob_h5=float(data.get("up_prob_h5", 0.5)),
            up_prob_h10=float(data.get("up_prob_h10", 0.5)),
        )


class DualModeStrategy:
    """Dual Mode Strategy with State Machine

    Automatically switches between:
    - MODE_A: Pure Basis Arbitrage (when OFI z-score is extreme)
    - MODE_B: Combined Triple Barrier + TrendEngine
        - Triple Barrier (CNN-LSTM) provides direction signal
        - TrendEngine provides technical confirmation (MA + Ichimoku)
        - TrendEngine PositionManager handles risk (ATR stops, time cuts)
    - AVOID: When liquidity is too low

    Migrated from kospi_mini_sts with bug fixes:
    - Unified strategy delegation instead of separate engines
    - Proper ensemble probability support (h1, h3, h5, h10)
    - Simplified process_message flow
    """

    def __init__(self, config: Optional[DualModeConfig] = None):
        self.config = config or DualModeConfig()

        # Initialize ensemble filter for MODE_B
        self.ensemble_filter = EnsembleFilter(
            dl_threshold=self.config.trend_dl_threshold,
            max_atr_threshold=self.config.trend_max_stop_points,
        )

        # Technical calculator
        self.tech_calc = TechnicalCalculator(
            ma_fast_period=self.config.trend_ma_fast,
            ma_slow_period=self.config.trend_ma_slow,
            atr_period=self.config.trend_atr_period,
        )

        # Rolling OHLCV buffer for triple barrier predictor
        self._ohlcv_buffer: deque = deque(maxlen=self.config.triple_barrier_buffer_size)

        # Current mode
        self.current_mode = TradingMode.AVOID
        self._prev_mode = TradingMode.AVOID  # Track mode changes
        self.active_engine: Optional[str] = None  # "arb", "triple_barrier+trend", or "trend"

        # Statistics
        self._stats = {
            "total_bars": 0,
            "mode_a_bars": 0,
            "mode_b_bars": 0,
            "avoid_bars": 0,
            "mode_a_signals": 0,
            "mode_b_signals": 0,
            "triple_barrier_signals": 0,  # Signals where TB+Trend agreed
            "trend_fallback_signals": 0,  # Signals from legacy trend engine fallback
        }

        # Last notification time to avoid spam
        self._last_mode_notify = 0
        self._mode_notify_cooldown = 60  # seconds

        logger.info(
            f"DualModeStrategy initialized: "
            f"basis_threshold={self.config.basis_threshold}, "
            f"trend_dl_threshold={self.config.trend_dl_threshold}"
        )

    def _determine_mode(self, bar: BarData) -> TradingMode:
        """Determine trading mode based on current conditions."""
        # Check spread (if spread is too wide, avoid)
        spread = bar.spread if bar.spread > 0 else (bar.best_ask - bar.best_bid)

        # If spread is too wide, avoid (but allow in backtest mode where spread=0)
        if spread > 0.5:
            return TradingMode.AVOID

        # Check OFI z-score for arbitrage opportunity
        if abs(bar.ofi_zscore) > self.config.basis_threshold:
            return TradingMode.MODE_A

        # Default to MODE_B (trend following)
        return TradingMode.MODE_B

    def generate_signal(self, bar: BarData) -> Signal:
        """Generate signal using state machine logic."""
        self._stats["total_bars"] += 1

        # ALWAYS update technical indicators, regardless of mode
        # This ensures proper warm-up for when we do enter MODE_B
        self.tech_calc.update(
            high=bar.high,
            low=bar.low,
            close=bar.close,
        )

        # Update calibrator with ensemble predictions
        if bar.up_prob_h10 != 0.5:  # Has ensemble predictions
            self.ensemble_filter.calibrator.update(1, bar.up_prob_h1)
            self.ensemble_filter.calibrator.update(3, bar.up_prob_h3)
            self.ensemble_filter.calibrator.update(5, bar.up_prob_h5)
            self.ensemble_filter.calibrator.update(10, bar.up_prob_h10)

        # Determine current mode
        mode = self._determine_mode(bar)
        self.current_mode = mode

        # Notify on mode change (with cooldown to avoid spam)
        now = time.time()
        if mode != self._prev_mode and (now - self._last_mode_notify) > self._mode_notify_cooldown:
            self._notify_mode_change(self._prev_mode, mode, bar)
            self._last_mode_notify = now
        self._prev_mode = mode

        if mode == TradingMode.AVOID:
            self._stats["avoid_bars"] += 1
            return Signal.HOLD

        elif mode == TradingMode.MODE_A:
            self._stats["mode_a_bars"] += 1
            return self._process_mode_a(bar)

        else:  # MODE_B
            self._stats["mode_b_bars"] += 1
            return self._process_mode_b(bar)

    def _notify_mode_change(self, prev: TradingMode, curr: TradingMode, bar: BarData) -> None:
        """Log mode change event."""
        logger.info(f"Mode change: {prev.value} -> {curr.value} @ {bar.close:.2f}")

    def _process_mode_a(self, bar: BarData) -> Signal:
        """Process MODE_A: Arbitrage based on OFI z-score extremes."""
        ofi_z = bar.ofi_zscore

        # Check spread is acceptable
        spread = bar.spread if bar.spread > 0 else (bar.best_ask - bar.best_bid)
        if spread > self.config.arb_max_spread_ticks * 0.05:  # 0.05 point per tick
            return Signal.HOLD

        # Check depth is sufficient
        total_bid_qty = bar.bid_qty1 + bar.bid_qty2 + bar.bid_qty3
        total_ask_qty = bar.ask_qty1 + bar.ask_qty2 + bar.ask_qty3
        min_depth = self.config.order_size * self.config.arb_depth_multiplier
        if total_bid_qty < min_depth or total_ask_qty < min_depth:
            return Signal.HOLD

        # Arbitrage signal: extreme OFI z-score suggests mean reversion
        if ofi_z < -self.config.basis_threshold:
            # Oversold - expect bounce (BUY)
            self._stats["mode_a_signals"] += 1
            self.active_engine = "arb"
            logger.info(f"MODE_A BUY: OFI oversold (z={ofi_z:.2f})")
            return Signal.BUY
        elif ofi_z > self.config.basis_threshold:
            # Overbought - expect pullback (SELL)
            self._stats["mode_a_signals"] += 1
            self.active_engine = "arb"
            logger.info(f"MODE_A SELL: OFI overbought (z={ofi_z:.2f})")
            return Signal.SELL

        return Signal.HOLD

    def _process_mode_b(self, bar: BarData) -> Signal:
        """Process MODE_B: Combined Triple Barrier + TrendEngine.

        Entry Flow:
        1. Check if multi-horizon predictions are available
        2. Use ensemble filter for entry confirmation
        3. MA + Ichimoku technical confirmation
        """
        tech = self.tech_calc.last_data
        if tech is None or not tech.is_ready:
            return Signal.HOLD

        # Check if multi-horizon predictions are available
        has_ensemble = (
            bar.up_prob_h10 != 0.5
            or bar.up_prob_h1 != 0.5
            or bar.up_prob_h3 != 0.5
            or bar.up_prob_h5 != 0.5
        )

        if has_ensemble:
            # Use multi-horizon "Shortest Confirms Longest" strategy
            horizon_probs = {
                1: bar.up_prob_h1,
                3: bar.up_prob_h3,
                5: bar.up_prob_h5,
                10: bar.up_prob_h10,
            }
            result = self.ensemble_filter.check_entry_multi_horizon(horizon_probs, tech)
        else:
            # Fallback: Use single up_prob or MA + Ichimoku-based momentum
            up_prob = bar.up_prob
            if up_prob == 0.5:
                # No DL prediction - use technical only
                ma_bullish = tech.is_bullish_ma
                above_cloud = tech.current_price > tech.cloud_top
                below_cloud = tech.current_price < tech.cloud_bottom

                if ma_bullish and above_cloud:
                    up_prob = 0.80
                elif ma_bullish:
                    up_prob = 0.70
                elif not ma_bullish and below_cloud:
                    up_prob = 0.20
                elif not ma_bullish:
                    up_prob = 0.30

            result = self.ensemble_filter.check_entry(up_prob, tech)

        if not result.can_enter:
            return Signal.HOLD

        # Generate signal
        if result.direction == "LONG":
            self._stats["mode_b_signals"] += 1
            self._stats["trend_fallback_signals"] += 1
            self.active_engine = "trend"
            logger.info(f"MODE_B LONG: prob confirmed, MA/Ichimoku passed")
            return Signal.BUY
        elif result.direction == "SHORT":
            self._stats["mode_b_signals"] += 1
            self._stats["trend_fallback_signals"] += 1
            self.active_engine = "trend"
            logger.info(f"MODE_B SHORT: prob confirmed, MA/Ichimoku passed")
            return Signal.SELL

        return Signal.HOLD

    def get_stats(self) -> dict[str, Any]:
        """Get strategy statistics."""
        total = self._stats["total_bars"]
        return {
            **self._stats,
            "current_mode": self.current_mode.value,
            "active_engine": self.active_engine,
            "mode_a_ratio": self._stats["mode_a_bars"] / total if total > 0 else 0,
            "mode_b_ratio": self._stats["mode_b_bars"] / total if total > 0 else 0,
            "avoid_ratio": self._stats["avoid_bars"] / total if total > 0 else 0,
            "filter_stats": self.ensemble_filter.get_stats(),
        }

    def reset(self):
        """Reset strategy state."""
        self.current_mode = TradingMode.AVOID
        self.active_engine = None
        for key in self._stats:
            if isinstance(self._stats[key], int):
                self._stats[key] = 0
        self.ensemble_filter.reset_stats()


# =============================================================================
# Entry Generator Wrapper for Registry
# =============================================================================


@EntryRegistry.register("futures_dual_mode")
class DualModeEntry(EntrySignalGenerator[DualModeConfig]):
    """Dual Mode Entry Strategy wrapper for registry integration.

    Wraps DualModeStrategy for use with the shared strategy framework.
    """

    CONFIG_CLASS = DualModeConfig

    def __init__(self, config: DualModeConfig):
        super().__init__(config)
        self.strategy = DualModeStrategy(config)

    def _validate_config(self) -> None:
        """Validate configuration."""
        assert self.config.basis_threshold > 0, "basis_threshold must be positive"
        assert 0 < self.config.trend_dl_threshold < 1, "trend_dl_threshold must be between 0 and 1"

    @property
    def name(self) -> str:
        return "futures_dual_mode"

    @property
    def required_indicators(self) -> list[str]:
        return ["prediction", "ohlcv", "orderbook"]

    async def generate(self, context: EntryContext) -> Optional[SignalModel]:
        """Generate entry signal.

        Args:
            context: Entry context with market_data and indicators

        Returns:
            Signal if entry condition met, None otherwise
        """
        market_data = context.market_data
        indicators = context.indicators

        # Build BarData from context
        bar = BarData(
            datetime=context.timestamp,
            open=float(market_data.get("open", 0)),
            high=float(market_data.get("high", 0)),
            low=float(market_data.get("low", 0)),
            close=float(market_data.get("close", 0)),
            volume=float(market_data.get("volume", 0)),
            spread=float(market_data.get("spread", 0)),
            best_bid=float(market_data.get("best_bid", market_data.get("bid_price_1", 0))),
            best_ask=float(market_data.get("best_ask", market_data.get("ask_price_1", 0))),
            bid_qty1=float(market_data.get("bid_qty1", market_data.get("bid_qty_1", 0))),
            bid_qty2=float(market_data.get("bid_qty2", 0)),
            bid_qty3=float(market_data.get("bid_qty3", 0)),
            ask_qty1=float(market_data.get("ask_qty1", market_data.get("ask_qty_1", 0))),
            ask_qty2=float(market_data.get("ask_qty2", 0)),
            ask_qty3=float(market_data.get("ask_qty3", 0)),
            ofi_zscore=float(market_data.get("ofi_zscore", market_data.get("ofi_z_score", 0))),
        )

        # Add prediction probabilities
        prediction = indicators.get("prediction", {})
        bar.up_prob = float(prediction.get("up_prob", 0.5))
        bar.down_prob = float(prediction.get("down_prob", 0.5))
        bar.up_prob_h1 = float(prediction.get("up_prob_h1", 0.5))
        bar.up_prob_h3 = float(prediction.get("up_prob_h3", 0.5))
        bar.up_prob_h5 = float(prediction.get("up_prob_h5", 0.5))
        bar.up_prob_h10 = float(prediction.get("up_prob_h10", bar.up_prob))

        # Generate signal
        signal = self.strategy.generate_signal(bar)

        if signal == Signal.HOLD:
            return None

        direction = "LONG" if signal == Signal.BUY else "SHORT"
        confidence = bar.up_prob if direction == "LONG" else bar.down_prob

        return SignalModel(
            code=market_data.get("symbol", ""),
            name=market_data.get("name", ""),
            signal_type=SignalType.ENTRY,
            strategy=self.name,
            price=bar.close,
            direction=direction,
            confidence=confidence,
            metadata={
                "mode": self.strategy.current_mode.value,
                "active_engine": self.strategy.active_engine,
                "ofi_zscore": bar.ofi_zscore,
            },
        )

    def get_stats(self) -> dict[str, Any]:
        """Get strategy statistics."""
        return self.strategy.get_stats()
