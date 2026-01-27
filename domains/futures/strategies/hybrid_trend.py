"""Hybrid Trend Strategy - DL + Technical Fallback

DL 예측이 있으면 Multi-horizon Ensemble을 사용하고,
없으면 MA + Ichimoku 기술적 지표로 합성 확률을 생성하는 하이브리드 전략.

Features:
- Multi-horizon DL 예측 (h1, h3, h5, h10) 지원
- DL 없을 때 기술적 지표 기반 자동 대체 (fallback)
- MA(20/60) + Ichimoku Cloud 확인
- 완화된 임계값 (0.60) - 신호 빈도 vs 정확도 트레이드오프

Migrated from kospi_mini_sts/src/strategy/strategies/dual_mode.py
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from shared.models.signal import Signal as SignalModel, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.registry import EntryRegistry
from .dl_trend import TechnicalCalculator, EnsembleFilter

logger = logging.getLogger(__name__)


class Signal(Enum):
    """Internal signal enum"""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class HybridTrendConfig:
    """Configuration for Hybrid Trend Strategy"""

    # Triple Barrier Classification (optional)
    triple_barrier_threshold: float = 0.60
    triple_barrier_buffer_size: int = 100
    triple_barrier_cache_bars: int = 3

    # Trend settings
    trend_dl_threshold: float = 0.60  # 완화된 임계값
    trend_ma_fast: int = 20
    trend_ma_slow: int = 60
    trend_atr_period: int = 14
    trend_atr_multiplier: float = 2.0
    trend_time_cut_minutes: int = 45
    trend_max_stop_points: float = 1.5
    trend_time_cut_atr_threshold: float = 0.3

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


class HybridTrendStrategy:
    """Hybrid Trend Strategy - DL + Technical Fallback

    DL 예측이 있으면 Multi-horizon Ensemble을 사용하고,
    없으면 MA + Ichimoku 기술적 지표로 합성 확률을 생성.

    Approach:
    1. Multi-horizon DL 예측 확인 (h1, h3, h5, h10)
    2. 있으면 "Shortest Confirms Longest" 전략 적용
    3. 없으면 MA + Ichimoku로 합성 확률 생성 (fallback)
    4. MA(20) > MA(60) + Price > Cloud = LONG
    5. MA(20) < MA(60) + Price < Cloud = SHORT

    Migrated from kospi_mini_sts.
    """

    def __init__(self, config: Optional[HybridTrendConfig] = None):
        self.config = config or HybridTrendConfig()

        # Initialize ensemble filter
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

        # Rolling OHLCV buffer
        self._ohlcv_buffer: deque = deque(maxlen=self.config.triple_barrier_buffer_size)

        self.active_engine: Optional[str] = None

        # Statistics
        self._stats = {
            "total_bars": 0,
            "dl_signals": 0,  # DL 예측 기반 신호
            "fallback_signals": 0,  # 기술적 지표 fallback 신호
            "long_signals": 0,
            "short_signals": 0,
        }

        # Triple Barrier prediction cache
        self._tb_cache_result: Optional[dict[str, Any]] = None
        self._tb_cache_bar_count: int = 0

        logger.info(
            f"HybridTrendStrategy initialized: "
            f"dl_threshold={self.config.trend_dl_threshold}"
        )

    def generate_signal(self, bar: BarData) -> Signal:
        """Generate signal using hybrid DL + technical approach."""
        self._stats["total_bars"] += 1

        # Update technical indicators
        self.tech_calc.update(
            high=bar.high,
            low=bar.low,
            close=bar.close,
        )

        # Update calibrator with ensemble predictions if available
        if bar.up_prob_h10 != 0.5:
            self.ensemble_filter.calibrator.update(1, bar.up_prob_h1)
            self.ensemble_filter.calibrator.update(3, bar.up_prob_h3)
            self.ensemble_filter.calibrator.update(5, bar.up_prob_h5)
            self.ensemble_filter.calibrator.update(10, bar.up_prob_h10)

        return self._generate_hybrid_signal(bar)

    def _generate_hybrid_signal(self, bar: BarData) -> Signal:
        """Hybrid signal generation: DL first, technical fallback.

        Entry Flow:
        1. Check if multi-horizon predictions are available
        2. If yes, use ensemble filter with calibrated z-scores
        3. If no, generate synthetic probability from technicals
        4. Apply MA + Ichimoku confirmation
        """
        tech = self.tech_calc.last_data
        if tech is None or not tech.is_ready:
            return Signal.HOLD

        # Check if multi-horizon predictions are available
        has_dl_prediction = (
            bar.up_prob_h10 != 0.5
            or bar.up_prob_h1 != 0.5
            or bar.up_prob_h3 != 0.5
            or bar.up_prob_h5 != 0.5
        )

        if has_dl_prediction:
            # Use multi-horizon "Shortest Confirms Longest" strategy
            horizon_probs = {
                1: bar.up_prob_h1,
                3: bar.up_prob_h3,
                5: bar.up_prob_h5,
                10: bar.up_prob_h10,
            }
            result = self.ensemble_filter.check_entry_multi_horizon(horizon_probs, tech)
            signal_source = "dl"
        else:
            # Fallback: Generate synthetic probability from technicals
            up_prob = bar.up_prob
            if up_prob == 0.5:
                # No DL prediction - use technical only
                ma_bullish = tech.is_bullish_ma
                above_cloud = tech.current_price > tech.cloud_top
                below_cloud = tech.current_price < tech.cloud_bottom

                if ma_bullish and above_cloud:
                    up_prob = 0.75  # Strong bullish
                elif ma_bullish:
                    up_prob = 0.65  # Moderate bullish
                elif not ma_bullish and below_cloud:
                    up_prob = 0.25  # Strong bearish
                elif not ma_bullish:
                    up_prob = 0.35  # Moderate bearish

                logger.debug(f"Technical fallback: synthetic prob={up_prob:.1%}")

            result = self.ensemble_filter.check_entry(up_prob, tech)
            signal_source = "fallback"

        if not result.can_enter:
            return Signal.HOLD

        # Generate signal
        if result.direction == "LONG":
            self._stats["long_signals"] += 1
            if signal_source == "dl":
                self._stats["dl_signals"] += 1
                self.active_engine = "dl_ensemble"
                logger.info("LONG: DL ensemble confirmed")
            else:
                self._stats["fallback_signals"] += 1
                self.active_engine = "technical_fallback"
                logger.info("LONG: Technical fallback")
            return Signal.BUY

        elif result.direction == "SHORT":
            self._stats["short_signals"] += 1
            if signal_source == "dl":
                self._stats["dl_signals"] += 1
                self.active_engine = "dl_ensemble"
                logger.info("SHORT: DL ensemble confirmed")
            else:
                self._stats["fallback_signals"] += 1
                self.active_engine = "technical_fallback"
                logger.info("SHORT: Technical fallback")
            return Signal.SELL

        return Signal.HOLD

    def get_stats(self) -> dict[str, Any]:
        """Get strategy statistics."""
        total = self._stats["total_bars"]
        signals = self._stats["long_signals"] + self._stats["short_signals"]
        return {
            **self._stats,
            "active_engine": self.active_engine,
            "signal_rate": signals / total if total > 0 else 0,
            "dl_ratio": self._stats["dl_signals"] / signals if signals > 0 else 0,
            "fallback_ratio": self._stats["fallback_signals"] / signals if signals > 0 else 0,
            "filter_stats": self.ensemble_filter.get_stats(),
        }

    def reset(self):
        """Reset strategy state."""
        self.active_engine = None
        for key in self._stats:
            if isinstance(self._stats[key], int):
                self._stats[key] = 0
        self.ensemble_filter.reset_stats()
        self._tb_cache_result = None
        self._tb_cache_bar_count = 0


# =============================================================================
# Entry Generator Wrapper for Registry
# =============================================================================


@EntryRegistry.register("futures_hybrid_trend")
class HybridTrendEntry(EntrySignalGenerator[HybridTrendConfig]):
    """Hybrid Trend Entry Strategy wrapper for registry integration.

    DL 예측 + 기술적 지표 Fallback 하이브리드 전략.
    """

    CONFIG_CLASS = HybridTrendConfig

    def __init__(self, config: HybridTrendConfig):
        super().__init__(config)
        self.strategy = HybridTrendStrategy(config)

    def _validate_config(self) -> None:
        """Validate configuration."""
        assert 0 < self.config.trend_dl_threshold < 1, "trend_dl_threshold must be between 0 and 1"

    @property
    def name(self) -> str:
        return "futures_hybrid_trend"

    @property
    def required_indicators(self) -> list[str]:
        return ["prediction", "ohlcv", "orderbook"]

    async def generate(self, context: EntryContext) -> Optional[SignalModel]:
        """Generate entry signal."""
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
                "active_engine": self.strategy.active_engine,
                "ofi_zscore": bar.ofi_zscore,
            },
        )

    def get_stats(self) -> dict[str, Any]:
        """Get strategy statistics."""
        return self.strategy.get_stats()
