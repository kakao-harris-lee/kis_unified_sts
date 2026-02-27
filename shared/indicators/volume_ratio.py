"""Volume Ratio (VR) 지표 계산기

일봉(Daily) 데이터 기반 VR 지표를 계산한다.

VR(%) = (상승일 거래량 합 + 보합일 거래량 × 0.5) /
        (하락일 거래량 합 + 보합일 거래량 × 0.5) × 100

해석 기준:
  - VR >= 400%: 극단적 과열 → STRONG_SELL
  - VR >= 300%: 과열권 → SELL
  - VR 150~300%: 보통~과열 → NEUTRAL
  - VR 100~150%: 보통 → NEUTRAL
  - VR 75~100%: 보통~침체 → NEUTRAL
  - VR 60~75%: 침체권 → BUY
  - VR 40~60%: 바닥권 → STRONG_BUY
  - VR < 40%: 극단적 바닥 → STRONG_BUY

Usage:
    calc = VolumeRatioCalculator(period=20)
    vr = calc.calculate(closes, volumes)
    zone = calc.get_zone(vr)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class VRZone(str, Enum):
    """VR 구간 분류"""

    EXTREME_OVERHEAT = "extreme_overheat"  # >= 400%
    OVERHEAT = "overheat"  # 300~400%
    MODERATE_HIGH = "moderate_high"  # 150~300%
    NORMAL = "normal"  # 100~150%
    MODERATE_LOW = "moderate_low"  # 75~100%
    DEPRESSION = "depression"  # 60~75%
    BOTTOM = "bottom"  # 40~60%
    EXTREME_BOTTOM = "extreme_bottom"  # < 40%


class VRSignal(str, Enum):
    """VR 기반 매매 신호"""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class MATrend(str, Enum):
    """이동평균선 추세 분류"""

    STRONG_UPTREND = "strong_uptrend"  # close > ma5 > ma20 > ma60 (정배열)
    UPTREND = "uptrend"  # close > ma20 and ma20 > ma60
    SIDEWAYS = "sideways"  # 그 외
    DOWNTREND = "downtrend"  # close < ma20 and ma20 < ma60
    STRONG_DOWNTREND = "strong_downtrend"  # close < ma5 < ma20 < ma60 (역배열)


@dataclass
class VRZoneInfo:
    """VR 구간 상세 정보"""

    zone: VRZone
    label: str
    signal: VRSignal
    min_value: float
    max_value: float


def _default_zone_definitions() -> list[VRZoneInfo]:
    """기본 VR 구간 정의 (오름차순으로 판별)"""
    return [
        VRZoneInfo(VRZone.EXTREME_BOTTOM, "극단적 바닥", VRSignal.STRONG_BUY, 0.0, 40.0),
        VRZoneInfo(VRZone.BOTTOM, "바닥권", VRSignal.STRONG_BUY, 40.0, 60.0),
        VRZoneInfo(VRZone.DEPRESSION, "침체권", VRSignal.BUY, 60.0, 75.0),
        VRZoneInfo(VRZone.MODERATE_LOW, "보통~침체", VRSignal.NEUTRAL, 75.0, 100.0),
        VRZoneInfo(VRZone.NORMAL, "보통", VRSignal.NEUTRAL, 100.0, 150.0),
        VRZoneInfo(VRZone.MODERATE_HIGH, "보통~과열", VRSignal.NEUTRAL, 150.0, 300.0),
        VRZoneInfo(VRZone.OVERHEAT, "과열권", VRSignal.SELL, 300.0, 400.0),
        VRZoneInfo(
            VRZone.EXTREME_OVERHEAT,
            "극단적 과열",
            VRSignal.STRONG_SELL,
            400.0,
            float("inf"),
        ),
    ]


class VolumeRatioCalculator:
    """Volume Ratio (VR) 지표 계산기

    일봉 OHLCV 데이터에서 VR, MA 추세, RSI 구간을 계산하고
    복합 매매 신호를 생성한다.

    Args:
        period: VR 계산 기간 (기본 20 거래일)
        zone_definitions: VR 구간 정의 (None이면 기본값 사용)
    """

    def __init__(
        self,
        period: int = 20,
        zone_definitions: list[VRZoneInfo] | None = None,
    ):
        if period < 2:
            raise ValueError("VR period must be >= 2")
        self.period = period
        self.zone_definitions = zone_definitions or _default_zone_definitions()

    def calculate(
        self,
        closes: np.ndarray | list[float],
        volumes: np.ndarray | list[int],
    ) -> list[Optional[float]]:
        """VR 값 시계열 계산.

        Args:
            closes: 종가 배열 (시간순 정렬)
            volumes: 거래량 배열 (시간순 정렬)

        Returns:
            VR(%) 리스트. 계산 불가 구간은 None.
        """
        closes_arr = np.asarray(closes, dtype=float)
        volumes_arr = np.asarray(volumes, dtype=float)

        if len(closes_arr) != len(volumes_arr):
            raise ValueError("closes and volumes must have the same length")
        if len(closes_arr) < 2:
            return [None] * len(closes_arr)

        # 전일 대비 변화: close[i] vs close[i-1]
        changes = np.diff(closes_arr)  # length = n - 1

        n = len(closes_arr)
        vr_values: list[Optional[float]] = [None] * n

        for i in range(n):
            # VR을 계산하려면 changes 인덱스 기준으로 period 개의 변화가 필요.
            # changes[j] = closes[j+1] - closes[j], 0-indexed.
            # i번째 bar의 VR은 changes[i-period:i] 구간을 사용.
            # changes의 최대 인덱스는 i-1 (왜냐하면 changes[i-1] = closes[i] - closes[i-1]).
            if i < self.period:
                continue

            up_vol = 0.0
            down_vol = 0.0
            unch_vol = 0.0

            for j in range(i - self.period, i):
                change = changes[j]  # closes[j+1] - closes[j]
                vol = volumes_arr[j + 1]  # 해당 일의 거래량

                if change > 0:
                    up_vol += vol
                elif change < 0:
                    down_vol += vol
                else:
                    unch_vol += vol

            denominator = down_vol + unch_vol * 0.5
            if denominator <= 0:
                vr_values[i] = None
            else:
                numerator = up_vol + unch_vol * 0.5
                vr_values[i] = (numerator / denominator) * 100.0

        return vr_values

    def get_zone(self, vr_value: Optional[float]) -> Optional[VRZoneInfo]:
        """VR 값의 구간을 판별한다.

        Args:
            vr_value: VR(%) 값

        Returns:
            VRZoneInfo 또는 None (VR 값이 None인 경우)
        """
        if vr_value is None:
            return None

        for zone_info in self.zone_definitions:
            if zone_info.min_value <= vr_value < zone_info.max_value:
                return zone_info

        # 음수 등 예외 상황
        return self.zone_definitions[0]

    @staticmethod
    def get_ma_trend(
        close: float,
        ma5: float,
        ma20: float,
        ma60: float,
    ) -> MATrend:
        """이동평균선 기반 추세를 판별한다.

        Args:
            close: 현재 종가
            ma5: 5일 이동평균
            ma20: 20일 이동평균
            ma60: 60일 이동평균

        Returns:
            MATrend enum
        """
        if close > ma5 > ma20 > ma60:
            return MATrend.STRONG_UPTREND
        elif close < ma5 < ma20 < ma60:
            return MATrend.STRONG_DOWNTREND
        elif close > ma20 and ma20 > ma60:
            return MATrend.UPTREND
        elif close < ma20 and ma20 < ma60:
            return MATrend.DOWNTREND
        else:
            return MATrend.SIDEWAYS

    @staticmethod
    def calculate_sma(
        closes: np.ndarray | list[float],
        period: int,
    ) -> list[Optional[float]]:
        """단순 이동평균(SMA) 계산.

        Args:
            closes: 종가 배열
            period: 이동평균 기간

        Returns:
            SMA 리스트. 계산 불가 구간은 None.
        """
        arr = np.asarray(closes, dtype=float)
        n = len(arr)
        result: list[Optional[float]] = [None] * n

        if n < period or period < 1:
            return result

        # Cumulative sum trick for O(n) SMA
        cumsum = np.cumsum(arr)
        for i in range(period - 1, n):
            if i == period - 1:
                result[i] = float(cumsum[i] / period)
            else:
                result[i] = float((cumsum[i] - cumsum[i - period]) / period)

        return result

    @staticmethod
    def calculate_rsi(
        closes: np.ndarray | list[float],
        period: int = 14,
    ) -> list[Optional[float]]:
        """RSI (Relative Strength Index) - Wilder's smoothing 방식.

        Args:
            closes: 종가 배열
            period: RSI 기간 (기본 14)

        Returns:
            RSI (0~100) 리스트. 계산 불가 구간은 None.
        """
        arr = np.asarray(closes, dtype=float)
        n = len(arr)
        result: list[Optional[float]] = [None] * n

        if n < period + 1:
            return result

        deltas = np.diff(arr)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # 초기 평균 (SMA)
        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))

        for i in range(period, len(deltas)):
            if i == period:
                # 첫 번째 RSI
                if avg_loss == 0:
                    result[i + 1] = 100.0
                else:
                    rs = avg_gain / avg_loss
                    result[i + 1] = 100.0 - (100.0 / (1.0 + rs))
            else:
                # Wilder's smoothing
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period

                if avg_loss == 0:
                    result[i + 1] = 100.0
                else:
                    rs = avg_gain / avg_loss
                    result[i + 1] = 100.0 - (100.0 / (1.0 + rs))

        # 첫 RSI 포인트도 계산
        if avg_loss == 0:
            result[period] = 100.0
        else:
            rs = float(np.mean(gains[:period])) / float(np.mean(losses[:period]))
            result[period] = 100.0 - (100.0 / (1.0 + rs))

        return result

    @staticmethod
    def check_volume_warning(
        recent_volumes: list[int] | np.ndarray,
        short_window: int = 5,
        long_window: int = 20,
        threshold: float = 0.5,
    ) -> bool:
        """거래량 급감 경고 여부 판단.

        최근 short_window일 평균 거래량 < long_window일 평균 × threshold 이면 True.

        Args:
            recent_volumes: 최근 거래량 (최소 long_window 길이)
            short_window: 단기 평균 기간
            long_window: 장기 평균 기간
            threshold: 급감 판단 비율

        Returns:
            True if 거래량 급감
        """
        vols = np.asarray(recent_volumes, dtype=float)
        if len(vols) < long_window:
            return False

        avg_short = float(np.mean(vols[-short_window:]))
        avg_long = float(np.mean(vols[-long_window:]))

        if avg_long <= 0:
            return False

        return avg_short < avg_long * threshold
