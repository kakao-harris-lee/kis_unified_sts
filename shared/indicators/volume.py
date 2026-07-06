"""거래량 지표 계산기 — OBV (batch) + stateful re-exports.

The stateful streaming calculators (session ``VWAPCalculator``, tick-second
``VolumeAccelerationCalculator``) were relocated into the engine package
(``shared/indicators/engine/stateful.py``) so all indicator computation lives
under the engine. They are re-exported here unchanged for backward compatibility.

This module now owns only the stateless batch ``OBVCalculator`` (list-based OBV +
accumulation detection), used by the off-hours accumulation scanner.

Usage:
    # OBV (On-Balance Volume)
    obv_calc = OBVCalculator()
    obv_data = obv_calc.calculate(prices=[100, 102, 101, 103], volumes=[1000, 1500, 800, 2000])
    if obv_data.is_accumulating:
        print("기관 매집 감지!")

    # VWAP / VolumeAcceleration (stateful) — see shared.indicators.engine.stateful
    from shared.indicators.volume import VWAPCalculator, VolumeAccelerationCalculator
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Stateful streaming indicators now live in the engine package; re-exported here
# so existing `from shared.indicators.volume import VWAPCalculator, ...` keeps working.
from shared.indicators.engine.stateful import (  # noqa: F401
    VolumeAcceleration,
    VolumeAccelerationCalculator,
    VolumeConfig,
    VWAPCalculator,
    VWAPConfig,
    VWAPData,
)

# =============================================================================
# OBV (On-Balance Volume)
# =============================================================================


@dataclass
class OBVData:
    """OBV 분석 결과

    Attributes:
        obv_values: OBV 시계열 값
        obv_sma: OBV의 SMA (sma_period일 이동평균)
        obv_trend: OBV 추세 기울기 (최근 trend_period일)
        price_trend: 가격 추세 기울기 (최근 trend_period일)
        is_accumulating: 매집 패턴 여부 (OBV 상승 + 가격 횡보)
    """

    obv_values: list[float]
    obv_sma: float
    obv_trend: float
    price_trend: float
    is_accumulating: bool


class OBVCalculator:
    """On-Balance Volume 계산기

    OBV = 누적(가격 상승일 거래량 - 가격 하락일 거래량)

    핵심 용도:
    - OBV 상승 + 가격 횡보 = 기관 매집 (accumulation)
    - OBV 하락 + 가격 횡보 = 기관 분배 (distribution)

    Usage:
        calc = OBVCalculator()
        data = calc.calculate(prices=[100, 102, 101, 103], volumes=[1000, 1500, 800, 2000])
        if data.is_accumulating:
            print("Accumulation detected!")
    """

    def __init__(self, sma_period: int = 20, trend_period: int = 10):
        self.sma_period = sma_period
        self.trend_period = trend_period

    def calculate(
        self,
        prices: list[float],
        volumes: list[int],
        price_flat_threshold: float = 0.02,
    ) -> OBVData:
        """OBV 계산

        Args:
            prices: 종가 리스트 (oldest first)
            volumes: 거래량 리스트
            price_flat_threshold: 가격 횡보 판정 임계값 (변동률)

        Returns:
            OBVData
        """
        n = min(len(prices), len(volumes))
        if n < 2:
            return OBVData(
                obv_values=[],
                obv_sma=0.0,
                obv_trend=0.0,
                price_trend=0.0,
                is_accumulating=False,
            )

        # OBV 계산
        obv = [0.0]
        for i in range(1, n):
            if prices[i] > prices[i - 1]:
                obv.append(obv[-1] + volumes[i])
            elif prices[i] < prices[i - 1]:
                obv.append(obv[-1] - volumes[i])
            else:
                obv.append(obv[-1])

        # OBV SMA
        if len(obv) >= self.sma_period:
            obv_sma = float(np.mean(obv[-self.sma_period :]))
        else:
            obv_sma = float(np.mean(obv))

        # OBV 추세 (선형 회귀 기울기)
        tp = min(self.trend_period, len(obv))
        obv_trend = self._slope(obv[-tp:]) if tp >= 2 else 0.0

        # 가격 추세
        price_trend = self._slope(prices[-tp:]) if tp >= 2 else 0.0

        # 매집 판정: OBV 상승 + 가격 횡보
        price_range = (
            (max(prices[-tp:]) - min(prices[-tp:])) / prices[-tp]
            if prices[-tp] > 0
            else 0.0
        )
        is_accumulating = obv_trend > 0 and price_range < price_flat_threshold

        return OBVData(
            obv_values=obv,
            obv_sma=obv_sma,
            obv_trend=obv_trend,
            price_trend=price_trend,
            is_accumulating=is_accumulating,
        )

    def is_accumulating(
        self,
        prices: list[float],
        volumes: list[int],
        threshold: float = 0.02,
    ) -> bool:
        """매집 패턴 여부 간편 체크"""
        data = self.calculate(prices, volumes, price_flat_threshold=threshold)
        return data.is_accumulating

    @staticmethod
    def _slope(values: list[float]) -> float:
        """간단한 선형 회귀 기울기 (정규화)"""
        n = len(values)
        if n < 2:
            return 0.0
        arr = np.array(values, dtype=np.float64)
        x = np.arange(n, dtype=np.float64)
        # 정규화: 평균 대비 변화율
        denom = np.std(arr)
        if denom == 0:
            return 0.0
        coeffs = np.polyfit(x, arr, 1)
        return float(coeffs[0] / denom)
