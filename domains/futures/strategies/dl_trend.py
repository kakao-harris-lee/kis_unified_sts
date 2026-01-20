"""DL Trend Entry Strategy

선물 전용 딥러닝 기반 추세 추종 전략.
CNN-LSTM 모델의 예측을 기반으로 진입 시그널 생성.

Ensemble Filter: 3가지 조건 모두 충족 시 진입
1. Deep Learning: P(Up) > threshold or P(Down) > threshold
2. Moving Average: MA(20) > MA(60) for long, MA(20) < MA(60) for short
3. Ichimoku: Price above cloud for long, price below cloud for short

Multi-Horizon Mode ("Shortest Confirms Longest"):
- h10 sets direction (z-score > threshold)
- h1/h3 confirms timing with lower threshold

Usage:
    @EntryRegistry.register("futures_dl_trend")
    class DLTrendEntry:
        ...
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.registry import EntryRegistry

logger = logging.getLogger(__name__)


# =============================================================================
# Technical Indicators
# =============================================================================


@dataclass
class TechnicalData:
    """기술적 지표 값"""

    ma_fast: float  # MA(20)
    ma_slow: float  # MA(60)
    ichimoku_span_a: float  # Senkou Span A
    ichimoku_span_b: float  # Senkou Span B
    atr: float  # Average True Range
    is_ready: bool  # 계산 준비 완료 여부
    current_price: float = 0.0

    @property
    def cloud_top(self) -> float:
        """Ichimoku cloud 상단"""
        return max(self.ichimoku_span_a, self.ichimoku_span_b)

    @property
    def cloud_bottom(self) -> float:
        """Ichimoku cloud 하단"""
        return min(self.ichimoku_span_a, self.ichimoku_span_b)

    @property
    def is_bullish_ma(self) -> bool:
        """MA fast > slow (상승 추세)"""
        return self.ma_fast > self.ma_slow

    @property
    def is_above_cloud(self) -> bool:
        """가격이 구름 위"""
        return self.current_price > self.cloud_top

    @property
    def is_below_cloud(self) -> bool:
        """가격이 구름 아래"""
        return self.current_price < self.cloud_bottom


@dataclass
class BarInput:
    """바 데이터"""

    high: float
    low: float
    close: float


class TechnicalCalculator:
    """기술적 지표 계산기

    SMA, Ichimoku Cloud, ATR 계산.
    """

    TENKAN_PERIOD = 9
    KIJUN_PERIOD = 26
    SENKOU_B_PERIOD = 52

    def __init__(
        self,
        ma_fast_period: int = 20,
        ma_slow_period: int = 60,
        atr_period: int = 14,
    ):
        self.ma_fast_period = ma_fast_period
        self.ma_slow_period = ma_slow_period
        self.atr_period = atr_period

        max_period = max(ma_slow_period, self.SENKOU_B_PERIOD)
        self.price_history: deque[BarInput] = deque(maxlen=max_period + 10)

        self._prev_close: Optional[float] = None
        self._atr_values: deque[float] = deque(maxlen=atr_period)

        self._last_data: Optional[TechnicalData] = None

    def update(self, high: float, low: float, close: float) -> TechnicalData:
        """새 바 데이터로 업데이트"""
        bar = BarInput(high=high, low=low, close=close)
        self.price_history.append(bar)

        # ATR 계산
        if self._prev_close is not None:
            tr = self._calc_true_range(high, low, self._prev_close)
            self._atr_values.append(tr)
        self._prev_close = close

        is_ready = len(self.price_history) >= self.ma_slow_period

        ma_fast = self._calc_sma(self.ma_fast_period)
        ma_slow = self._calc_sma(self.ma_slow_period)
        span_a, span_b = self._calc_ichimoku()
        atr = self._calc_atr()

        self._last_data = TechnicalData(
            ma_fast=ma_fast,
            ma_slow=ma_slow,
            ichimoku_span_a=span_a,
            ichimoku_span_b=span_b,
            atr=atr,
            is_ready=is_ready,
            current_price=close,
        )

        return self._last_data

    def _calc_sma(self, period: int) -> float:
        """Simple Moving Average"""
        if len(self.price_history) < period:
            return 0.0
        closes = [bar.close for bar in list(self.price_history)[-period:]]
        return sum(closes) / period

    def _calc_ichimoku(self) -> tuple[float, float]:
        """Ichimoku Senkou Span A, B"""
        if len(self.price_history) < self.SENKOU_B_PERIOD:
            return 0.0, 0.0

        def highest_high(period: int) -> float:
            return max(bar.high for bar in list(self.price_history)[-period:])

        def lowest_low(period: int) -> float:
            return min(bar.low for bar in list(self.price_history)[-period:])

        tenkan = (
            highest_high(self.TENKAN_PERIOD) + lowest_low(self.TENKAN_PERIOD)
        ) / 2
        kijun = (
            highest_high(self.KIJUN_PERIOD) + lowest_low(self.KIJUN_PERIOD)
        ) / 2

        span_a = (tenkan + kijun) / 2
        span_b = (
            highest_high(self.SENKOU_B_PERIOD) + lowest_low(self.SENKOU_B_PERIOD)
        ) / 2

        return span_a, span_b

    def _calc_true_range(
        self, high: float, low: float, prev_close: float
    ) -> float:
        """True Range"""
        return max(high - low, abs(high - prev_close), abs(low - prev_close))

    def _calc_atr(self) -> float:
        """Average True Range"""
        if len(self._atr_values) < self.atr_period:
            return 0.0
        return sum(self._atr_values) / len(self._atr_values)

    @property
    def last_data(self) -> Optional[TechnicalData]:
        return self._last_data


# =============================================================================
# Probability Calibrator
# =============================================================================


class ProbabilityCalibrator:
    """확률 캘리브레이터

    예측 분포를 추적하고 z-score 계산.
    모델 바이어스를 정규화하여 상대적 신호 강도 측정.
    """

    def __init__(self, window_size: int = 200, min_samples: int = 50):
        self.window_size = window_size
        self.min_samples = min_samples
        self._history: dict[int, deque] = {}  # horizon -> recent predictions

    def update(self, horizon: int, prob: float) -> None:
        """새 예측 추가"""
        if horizon not in self._history:
            self._history[horizon] = deque(maxlen=self.window_size)
        self._history[horizon].append(prob)

    def get_zscore(self, horizon: int, prob: float) -> Optional[float]:
        """예측의 z-score 계산"""
        if horizon not in self._history:
            return None

        history = self._history[horizon]
        if len(history) < self.min_samples:
            return None

        mean = np.mean(list(history))
        std = np.std(list(history))

        if std < 0.001:
            return None

        return (prob - mean) / std

    def get_stats(self, horizon: int) -> dict[str, float]:
        """horizon 통계"""
        if horizon not in self._history or len(self._history[horizon]) == 0:
            return {"mean": 0.5, "std": 0.1, "count": 0}

        history = self._history[horizon]
        return {
            "mean": float(np.mean(list(history))),
            "std": float(np.std(list(history))),
            "count": len(history),
        }

    def reset(self) -> None:
        """히스토리 초기화"""
        self._history.clear()


# =============================================================================
# Filter Result
# =============================================================================


@dataclass
class FilterResult:
    """앙상블 필터 결과"""

    can_enter: bool
    direction: Optional[str]  # "LONG", "SHORT", or None
    rejection_reason: Optional[str]
    dl_passed: bool
    ma_passed: bool
    ichimoku_passed: bool
    trigger_horizon: int = 0
    confirm_horizon: int = 0

    @property
    def all_passed(self) -> bool:
        return self.dl_passed and self.ma_passed and self.ichimoku_passed


# =============================================================================
# Ensemble Filter
# =============================================================================


class EnsembleFilter:
    """앙상블 필터

    3가지 조건 모두 충족 시 진입 허용:
    1. DL: P(Up) > threshold or P(Down) > threshold
    2. MA: MA(20) > MA(60) for long
    3. Ichimoku: Price > Cloud for long
    """

    def __init__(
        self,
        dl_threshold: float = 0.85,
        max_atr_threshold: float = 1.5,
        zscore_trigger_threshold: float = 1.0,
        zscore_long_confirm_threshold: float = 0.5,
        zscore_short_confirm_threshold: float = 0.0,
    ):
        self.dl_threshold = dl_threshold
        self.max_atr_threshold = max_atr_threshold
        self.zscore_trigger_threshold = zscore_trigger_threshold
        self.zscore_long_confirm_threshold = zscore_long_confirm_threshold
        self.zscore_short_confirm_threshold = zscore_short_confirm_threshold

        self.calibrator = ProbabilityCalibrator(window_size=200, min_samples=60)

        self._stats = {
            "total_checks": 0,
            "long_signals": 0,
            "short_signals": 0,
            "rejected_dl": 0,
            "rejected_ma": 0,
            "rejected_ichimoku": 0,
            "rejected_not_ready": 0,
            "calibrated_signals": 0,
            "uncalibrated_signals": 0,
        }

    def check_entry(self, up_prob: float, tech: TechnicalData) -> FilterResult:
        """진입 조건 확인 (단일 horizon)"""
        self._stats["total_checks"] += 1
        down_prob = 1.0 - up_prob

        if not tech.is_ready:
            self._stats["rejected_not_ready"] += 1
            return FilterResult(
                can_enter=False,
                direction=None,
                rejection_reason="Technical indicators warming up",
                dl_passed=False,
                ma_passed=False,
                ichimoku_passed=False,
            )

        # LONG 체크
        long_result = self._check_long(up_prob, tech)
        if long_result.can_enter:
            self._stats["long_signals"] += 1
            return long_result

        # SHORT 체크
        short_result = self._check_short(down_prob, tech)
        if short_result.can_enter:
            self._stats["short_signals"] += 1
            return short_result

        return long_result

    def _check_long(self, up_prob: float, tech: TechnicalData) -> FilterResult:
        """LONG 진입 조건"""
        dl_passed = up_prob > self.dl_threshold
        ma_passed = tech.ma_fast > tech.ma_slow
        ichimoku_passed = tech.current_price > tech.cloud_top

        rejection_reason = None
        if not dl_passed:
            rejection_reason = f"DL probability {up_prob:.1%} <= {self.dl_threshold:.0%}"
            self._stats["rejected_dl"] += 1
        elif not ma_passed:
            rejection_reason = f"MA bearish: {tech.ma_fast:.2f} <= {tech.ma_slow:.2f}"
            self._stats["rejected_ma"] += 1
        elif not ichimoku_passed:
            rejection_reason = (
                f"Price {tech.current_price:.2f} not above cloud {tech.cloud_top:.2f}"
            )
            self._stats["rejected_ichimoku"] += 1

        can_enter = dl_passed and ma_passed and ichimoku_passed

        return FilterResult(
            can_enter=can_enter,
            direction="LONG" if can_enter else None,
            rejection_reason=rejection_reason,
            dl_passed=dl_passed,
            ma_passed=ma_passed,
            ichimoku_passed=ichimoku_passed,
        )

    def _check_short(self, down_prob: float, tech: TechnicalData) -> FilterResult:
        """SHORT 진입 조건"""
        dl_passed = down_prob > self.dl_threshold
        ma_passed = tech.ma_fast < tech.ma_slow
        ichimoku_passed = tech.current_price < tech.cloud_bottom

        rejection_reason = None
        if not dl_passed:
            rejection_reason = (
                f"DL down probability {down_prob:.1%} <= {self.dl_threshold:.0%}"
            )
            self._stats["rejected_dl"] += 1
        elif not ma_passed:
            rejection_reason = (
                f"MA bullish: {tech.ma_fast:.2f} >= {tech.ma_slow:.2f}"
            )
            self._stats["rejected_ma"] += 1
        elif not ichimoku_passed:
            rejection_reason = (
                f"Price {tech.current_price:.2f} not below cloud {tech.cloud_bottom:.2f}"
            )
            self._stats["rejected_ichimoku"] += 1

        can_enter = dl_passed and ma_passed and ichimoku_passed

        return FilterResult(
            can_enter=can_enter,
            direction="SHORT" if can_enter else None,
            rejection_reason=rejection_reason,
            dl_passed=dl_passed,
            ma_passed=ma_passed,
            ichimoku_passed=ichimoku_passed,
        )

    def check_entry_multi_horizon(
        self,
        horizon_probs: dict[int, float],
        tech: TechnicalData,
    ) -> FilterResult:
        """Multi-horizon 진입 확인 ("Shortest Confirms Longest")

        h10 sets direction, h1/h3 confirms timing.
        """
        self._stats["total_checks"] += 1

        h1 = horizon_probs.get(1, 0.5)
        h3 = horizon_probs.get(3, 0.5)
        h10 = horizon_probs.get(10, 0.5)

        if not tech.is_ready:
            self._stats["rejected_not_ready"] += 1
            return FilterResult(
                can_enter=False,
                direction=None,
                rejection_reason="Technical indicators warming up",
                dl_passed=False,
                ma_passed=False,
                ichimoku_passed=False,
            )

        # ATR 필터
        if tech.atr > self.max_atr_threshold:
            return FilterResult(
                can_enter=False,
                direction=None,
                rejection_reason=f"ATR {tech.atr:.2f} > max {self.max_atr_threshold:.2f}",
                dl_passed=False,
                ma_passed=False,
                ichimoku_passed=False,
            )

        # Z-score 계산
        z10 = self.calibrator.get_zscore(10, h10)
        z1 = self.calibrator.get_zscore(1, h1)
        z3 = self.calibrator.get_zscore(3, h3)

        if z10 is not None and z1 is not None and z3 is not None:
            return self._check_calibrated(h1, h3, h10, z1, z3, z10, tech)
        else:
            return self._check_uncalibrated(tech)

    def _check_calibrated(
        self,
        h1: float,
        h3: float,
        h10: float,
        z1: float,
        z3: float,
        z10: float,
        tech: TechnicalData,
    ) -> FilterResult:
        """캘리브레이션된 z-score 기반 진입 확인"""
        # LONG: h10 z-score가 충분히 높고 h1/h3가 확인
        if z10 > self.zscore_trigger_threshold:
            confirm_z1 = z1 > self.zscore_long_confirm_threshold
            confirm_z3 = z3 > self.zscore_long_confirm_threshold

            if confirm_z1 or confirm_z3:
                ma_passed = tech.ma_fast > tech.ma_slow
                ichimoku_passed = tech.current_price > tech.cloud_top

                if ma_passed and ichimoku_passed:
                    self._stats["long_signals"] += 1
                    self._stats["calibrated_signals"] += 1
                    logger.info(
                        f"LONG (calibrated): z10={z10:.2f}, z1={z1:.2f}, z3={z3:.2f}, "
                        f"confirm={'z1' if confirm_z1 else 'z3'}"
                    )
                    return FilterResult(
                        can_enter=True,
                        direction="LONG",
                        rejection_reason=None,
                        dl_passed=True,
                        ma_passed=True,
                        ichimoku_passed=True,
                        trigger_horizon=10,
                        confirm_horizon=1 if confirm_z1 else 3,
                    )

        # SHORT: h10 z-score가 충분히 낮고 h1/h3가 확인
        if z10 < -self.zscore_trigger_threshold:
            confirm_z1 = z1 < -self.zscore_short_confirm_threshold
            confirm_z3 = z3 < -self.zscore_short_confirm_threshold

            if confirm_z1 or confirm_z3:
                ma_passed = tech.ma_fast < tech.ma_slow
                ichimoku_passed = tech.current_price < tech.cloud_bottom

                if ma_passed and ichimoku_passed:
                    self._stats["short_signals"] += 1
                    self._stats["calibrated_signals"] += 1
                    logger.info(
                        f"SHORT (calibrated): z10={z10:.2f}, z1={z1:.2f}, z3={z3:.2f}, "
                        f"confirm={'z1' if confirm_z1 else 'z3'}"
                    )
                    return FilterResult(
                        can_enter=True,
                        direction="SHORT",
                        rejection_reason=None,
                        dl_passed=True,
                        ma_passed=True,
                        ichimoku_passed=True,
                        trigger_horizon=10,
                        confirm_horizon=1 if confirm_z1 else 3,
                    )

        self._stats["rejected_dl"] += 1
        return FilterResult(
            can_enter=False,
            direction=None,
            rejection_reason=f"No z-score signal: z10={z10:.2f}, z1={z1:.2f}, z3={z3:.2f}",
            dl_passed=False,
            ma_passed=False,
            ichimoku_passed=False,
        )

    def _check_uncalibrated(self, tech: TechnicalData) -> FilterResult:
        """캘리브레이션 워밍업 중 (신호 없음)"""
        self._stats["uncalibrated_signals"] += 1
        self._stats["rejected_dl"] += 1

        samples = self.calibrator.get_stats(10).get("count", 0)
        return FilterResult(
            can_enter=False,
            direction=None,
            rejection_reason=f"Calibration warm-up: {samples}/{self.calibrator.min_samples} samples",
            dl_passed=False,
            ma_passed=False,
            ichimoku_passed=False,
        )

    def update_calibrator(self, horizon_probs: dict[int, float]) -> None:
        """캘리브레이터 업데이트"""
        for horizon, prob in horizon_probs.items():
            self.calibrator.update(horizon, prob)

    def get_stats(self) -> dict[str, Any]:
        """통계 조회"""
        total = self._stats["total_checks"]
        signals = self._stats["long_signals"] + self._stats["short_signals"]
        return {
            **self._stats,
            "signal_rate": signals / total if total > 0 else 0.0,
        }

    def reset_stats(self) -> None:
        """통계 초기화"""
        for key in self._stats:
            self._stats[key] = 0
        self.calibrator.reset()


# =============================================================================
# DL Trend Entry Config
# =============================================================================


@dataclass
class DLTrendConfig:
    """DL Trend Entry 설정"""

    # DL 임계값
    dl_threshold: float = 0.85
    max_atr_threshold: float = 1.5

    # Z-score 임계값
    zscore_trigger_threshold: float = 1.0
    zscore_long_confirm_threshold: float = 0.5
    zscore_short_confirm_threshold: float = 0.0

    # MA 기간
    ma_fast_period: int = 20
    ma_slow_period: int = 60

    # Multi-horizon 사용
    use_multi_horizon: bool = True
    horizons: list[int] = field(default_factory=lambda: [1, 3, 5, 10])


# =============================================================================
# DL Trend Entry Strategy
# =============================================================================


@EntryRegistry.register("futures_dl_trend")
class DLTrendEntry(EntrySignalGenerator[DLTrendConfig]):
    """DL Trend Following Entry Strategy

    CNN-LSTM 예측 + MA + Ichimoku 앙상블 필터.

    Usage:
        entry = DLTrendEntry(config)
        signal = await entry.generate(context)
    """

    CONFIG_CLASS = DLTrendConfig

    def __init__(self, config: DLTrendConfig):
        super().__init__(config)

        self.filter = EnsembleFilter(
            dl_threshold=config.dl_threshold,
            max_atr_threshold=config.max_atr_threshold,
            zscore_trigger_threshold=config.zscore_trigger_threshold,
            zscore_long_confirm_threshold=config.zscore_long_confirm_threshold,
            zscore_short_confirm_threshold=config.zscore_short_confirm_threshold,
        )

        self.tech_calc = TechnicalCalculator(
            ma_fast_period=config.ma_fast_period,
            ma_slow_period=config.ma_slow_period,
        )

    def _validate_config(self) -> None:
        """설정 검증"""
        assert 0 < self.config.dl_threshold < 1, "dl_threshold must be between 0 and 1"
        assert self.config.max_atr_threshold > 0, "max_atr_threshold must be positive"

    @property
    def name(self) -> str:
        return "futures_dl_trend"

    @property
    def required_indicators(self) -> list[str]:
        return ["prediction", "ohlcv"]

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        """진입 시그널 생성

        Args:
            context: 진입 컨텍스트 (market_data, indicators 포함)

        Returns:
            Signal if entry condition met, None otherwise
        """
        market_data = context.market_data
        indicators = context.indicators

        # OHLCV로 기술적 지표 업데이트
        if "high" in market_data and "low" in market_data and "close" in market_data:
            tech = self.tech_calc.update(
                market_data["high"],
                market_data["low"],
                market_data["close"],
            )
        else:
            tech = self.tech_calc.last_data
            if tech is None:
                return None

        # 예측 확률
        prediction = indicators.get("prediction", {})

        if self.config.use_multi_horizon:
            # Multi-horizon mode
            horizon_probs = {}
            for h in self.config.horizons:
                key = f"up_prob_h{h}"
                if key in prediction:
                    horizon_probs[h] = prediction[key]

            if not horizon_probs:
                # 단일 horizon 폴백
                up_prob = prediction.get("up_prob", 0.5)
                result = self.filter.check_entry(up_prob, tech)
            else:
                # 캘리브레이터 업데이트
                self.filter.update_calibrator(horizon_probs)
                result = self.filter.check_entry_multi_horizon(horizon_probs, tech)
        else:
            # 단일 horizon mode
            up_prob = prediction.get("up_prob", 0.5)
            result = self.filter.check_entry(up_prob, tech)

        if not result.can_enter:
            logger.debug(f"Entry rejected: {result.rejection_reason}")
            return None

        # Signal 생성
        return Signal(
            code=market_data.get("symbol", ""),
            name=market_data.get("name", ""),
            signal_type=SignalType.ENTRY,
            strategy=self.name,
            price=market_data.get("close", 0.0),
            direction=result.direction,
            confidence=prediction.get("up_prob", 0.5)
            if result.direction == "LONG"
            else prediction.get("down_prob", 0.5),
            metadata={
                "trigger_horizon": result.trigger_horizon,
                "confirm_horizon": result.confirm_horizon,
                "ma_fast": tech.ma_fast,
                "ma_slow": tech.ma_slow,
                "atr": tech.atr,
            },
        )

    def get_stats(self) -> dict[str, Any]:
        """통계 조회"""
        return self.filter.get_stats()
