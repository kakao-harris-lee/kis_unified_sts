"""기술적 지표 계산기

SMA, ATR, Ichimoku Cloud 등 기본 기술적 지표.

kospi_mini_sts의 TechnicalCalculator를 마이그레이션.

Usage:
    calc = TechnicalCalculator(ma_fast_period=20, ma_slow_period=60)

    for bar in bars:
        data = calc.update(bar.high, bar.low, bar.close)

    if data.is_bullish_ma and data.is_above_cloud:
        # 상승 추세
        ...
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BarInput:
    """지표 계산용 바 데이터"""

    high: float
    low: float
    close: float


@dataclass
class TechnicalData:
    """기술적 지표 값"""

    ma_fast: float  # 단기 이동평균
    ma_slow: float  # 장기 이동평균
    ichimoku_span_a: float  # Senkou Span A
    ichimoku_span_b: float  # Senkou Span B
    atr: float  # Average True Range
    is_ready: bool  # 계산 가능 여부
    current_price: float = 0.0  # 현재가

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
        """MA 골든크로스 (단기 > 장기)"""
        return self.ma_fast > self.ma_slow

    @property
    def is_above_cloud(self) -> bool:
        """가격이 cloud 위"""
        return self.current_price > self.cloud_top

    @property
    def is_below_cloud(self) -> bool:
        """가격이 cloud 아래"""
        return self.current_price < self.cloud_bottom


class TechnicalCalculator:
    """기술적 지표 계산기

    계산 지표:
    - SMA(fast), SMA(slow): 추세 방향
    - Ichimoku Cloud: 지지/저항
    - ATR: 변동성 기반 손절폭

    Usage:
        calc = TechnicalCalculator(ma_fast_period=20, ma_slow_period=60)
        data = calc.update(high=100, low=99, close=99.5)

        if data.is_bullish_ma:
            print("상승 추세")
    """

    # Ichimoku 표준 기간
    TENKAN_PERIOD = 9
    KIJUN_PERIOD = 26
    SENKOU_B_PERIOD = 52

    def __init__(
        self,
        ma_fast_period: int = 20,
        ma_slow_period: int = 60,
        atr_period: int = 14,
    ):
        """
        Args:
            ma_fast_period: 단기 이동평균 기간
            ma_slow_period: 장기 이동평균 기간
            atr_period: ATR 기간
        """
        self.ma_fast_period = ma_fast_period
        self.ma_slow_period = ma_slow_period
        self.atr_period = atr_period

        # 가장 긴 기간 + 여유분
        max_period = max(ma_slow_period, self.SENKOU_B_PERIOD)
        self.price_history: Deque[BarInput] = deque(maxlen=max_period + 10)

        # ATR 계산용
        self._prev_close: Optional[float] = None
        self._atr_values: Deque[float] = deque(maxlen=atr_period)

        self._last_data: Optional[TechnicalData] = None

    def update(self, high: float, low: float, close: float) -> TechnicalData:
        """새 바 데이터로 업데이트

        Args:
            high: 고가
            low: 저가
            close: 종가

        Returns:
            TechnicalData 현재 지표 값
        """
        bar = BarInput(high=high, low=low, close=close)
        self.price_history.append(bar)

        # True Range 계산 (ATR용)
        if self._prev_close is not None:
            tr = self._calc_true_range(high, low, self._prev_close)
            self._atr_values.append(tr)
        self._prev_close = close

        # 계산 가능 여부
        is_ready = len(self.price_history) >= self.ma_slow_period

        # 지표 계산
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
        """단순 이동평균 계산"""
        if len(self.price_history) < period:
            return 0.0

        closes = [bar.close for bar in list(self.price_history)[-period:]]
        return float(np.mean(closes))

    def _calc_ichimoku(self) -> tuple[float, float]:
        """Ichimoku Senkou Span 계산

        Senkou Span A = (Tenkan + Kijun) / 2
        Senkou Span B = (52기간 고가 + 52기간 저가) / 2
        """
        bars = list(self.price_history)

        # Tenkan-sen (전환선) - 9기간
        if len(bars) >= self.TENKAN_PERIOD:
            recent = bars[-self.TENKAN_PERIOD:]
            tenkan = (max(b.high for b in recent) + min(b.low for b in recent)) / 2
        else:
            tenkan = bars[-1].close if bars else 0.0

        # Kijun-sen (기준선) - 26기간
        if len(bars) >= self.KIJUN_PERIOD:
            recent = bars[-self.KIJUN_PERIOD:]
            kijun = (max(b.high for b in recent) + min(b.low for b in recent)) / 2
        else:
            kijun = bars[-1].close if bars else 0.0

        # Senkou Span A
        span_a = (tenkan + kijun) / 2

        # Senkou Span B - 52기간
        if len(bars) >= self.SENKOU_B_PERIOD:
            recent = bars[-self.SENKOU_B_PERIOD:]
            span_b = (max(b.high for b in recent) + min(b.low for b in recent)) / 2
        else:
            span_b = bars[-1].close if bars else 0.0

        return span_a, span_b

    def _calc_true_range(
        self, high: float, low: float, prev_close: float
    ) -> float:
        """True Range 계산

        TR = max(H-L, |H-PC|, |L-PC|)
        """
        return max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )

    def _calc_atr(self) -> float:
        """Average True Range 계산"""
        if len(self._atr_values) < self.atr_period:
            if self.price_history:
                recent = list(self.price_history)[
                    -min(len(self.price_history), 14):
                ]
                ranges = [b.high - b.low for b in recent]
                return float(np.mean(ranges)) if ranges else 0.0
            return 0.0

        return float(np.mean(list(self._atr_values)))

    def get_current_data(self) -> Optional[TechnicalData]:
        """현재 지표 데이터"""
        return self._last_data

    def get_atr(self) -> float:
        """현재 ATR 값"""
        return self._last_data.atr if self._last_data else 0.0

    def is_ready(self) -> bool:
        """계산 가능 여부"""
        return len(self.price_history) >= self.ma_slow_period

    def reset(self):
        """상태 초기화"""
        self.price_history.clear()
        self._atr_values.clear()
        self._prev_close = None
        self._last_data = None

    def get_stats(self) -> dict:
        """진단 통계"""
        return {
            "bars_count": len(self.price_history),
            "is_ready": self.is_ready(),
            "ma_fast": self._last_data.ma_fast if self._last_data else 0.0,
            "ma_slow": self._last_data.ma_slow if self._last_data else 0.0,
            "atr": self._last_data.atr if self._last_data else 0.0,
            "cloud_top": self._last_data.cloud_top if self._last_data else 0.0,
            "cloud_bottom": self._last_data.cloud_bottom if self._last_data else 0.0,
        }
