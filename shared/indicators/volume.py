"""거래량 지표 계산기

거래량 가속도, VWAP, OBV, RVOL 계산.

quant_moment_sts의 VolumeAccelerationCalculator, VWAPCalculator를 마이그레이션.

Usage:
    # 거래량 가속도
    vol_calc = VolumeAccelerationCalculator(window_size=60)
    vol_calc.add_tick("005930", volume=1000, timestamp=time.time())
    accel = vol_calc.calculate("005930")

    if accel.is_accelerating:
        print("거래량 가속 중!")

    # VWAP
    vwap_calc = VWAPCalculator()
    vwap_calc.add_tick("005930", price=50000, volume=100, date_str="20240115")
    vwap_data = vwap_calc.calculate("005930", current_price=50500)

    # OBV (On-Balance Volume)
    obv_calc = OBVCalculator()
    obv_data = obv_calc.calculate(prices=[100, 102, 101, 103], volumes=[1000, 1500, 800, 2000])
    if obv_data.is_accumulating:
        print("기관 매집 감지!")

    # RVOL (Relative Volume)
    rvol_calc = RVOLCalculator()
    rvol_data = rvol_calc.calculate(volumes=[100]*20 + [200]*5)
    print(f"RVOL: {rvol_data.rvol_ratio:.2f}x")
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Volume Acceleration
# =============================================================================


@dataclass
class VolumeAcceleration:
    """거래량 가속도 분석 결과

    Attributes:
        velocity: 거래량 변화율 (1차 도함수)
        acceleration: 가속도 (2차 도함수)
        is_accelerating: 가속 중 여부 (velocity > 0 AND acceleration > 0)
        current_window_volume: 현재 윈도우 거래량
        prev_window_volume: 이전 윈도우 거래량
    """

    velocity: float
    acceleration: float
    is_accelerating: bool
    current_window_volume: int
    prev_window_volume: int


@dataclass
class VolumeConfig:
    """거래량 분석 설정"""

    window_size: int = 60  # 윈도우 크기 (초)
    lookback_seconds: int = 60  # 계산 윈도우 (초)
    very_high_threshold: float = 0.5
    high_threshold: float = 0.3
    mid_threshold: float = 0.1
    max_score: float = 40.0
    high_score: float = 30.0
    mid_score: float = 20.0
    low_score: float = 10.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VolumeConfig:
        return cls(
            window_size=data.get("window_size", 60),
            lookback_seconds=data.get("lookback_seconds", 60),
            very_high_threshold=data.get("very_high_threshold", 0.5),
            high_threshold=data.get("high_threshold", 0.3),
            mid_threshold=data.get("mid_threshold", 0.1),
            max_score=data.get("max_score", 40.0),
            high_score=data.get("high_score", 30.0),
            mid_score=data.get("mid_score", 20.0),
            low_score=data.get("low_score", 10.0),
        )


class VolumeAccelerationCalculator:
    """거래량 가속도 계산기

    핵심 개념:
    - Velocity (속도): 거래량의 1차 도함수 (변화율)
    - Acceleration (가속도): 거래량의 2차 도함수 (변화율의 변화율)

    FOMO 신호:
    - velocity > 0.3: 거래량 30% 이상 증가
    - acceleration > 0: 증가 속도가 빨라지고 있음

    Usage:
        calc = VolumeAccelerationCalculator(window_size=60)
        calc.add_tick("005930", volume=1000, timestamp=time.time())
        result = calc.calculate("005930")
    """

    def __init__(self, config: VolumeConfig | None = None):
        """
        Args:
            config: 설정 (기본값 사용 시 None)
        """
        self.config = config or VolumeConfig()
        self._volume_windows: dict[str, Deque[tuple[float, int]]] = {}
        self._prev_velocities: dict[str, float] = {}

    def add_tick(self, code: str, volume: int, timestamp: float):
        """틱 추가

        Args:
            code: 종목코드
            volume: 체결량
            timestamp: 타임스탬프 (Unix epoch)
        """
        if code not in self._volume_windows:
            self._volume_windows[code] = deque(
                maxlen=self.config.window_size * 10
            )

        self._volume_windows[code].append((timestamp, volume))

    def calculate(
        self, code: str, lookback_seconds: int | None = None,
        *,
        timestamps: list = None,
        context_timestamp = None,
        lookahead_guard = None,
        context_info: str = None,
    ) -> VolumeAcceleration:
        """거래량 가속도 계산

        Args:
            code: 종목코드
            lookback_seconds: 계산 윈도우 (초), None이면 config 사용

        Returns:
            VolumeAcceleration
        """
        lookback_seconds = lookback_seconds or self.config.lookback_seconds

        if code not in self._volume_windows or not self._volume_windows[code]:
            return VolumeAcceleration(
                velocity=0.0,
                acceleration=0.0,
                is_accelerating=False,
                current_window_volume=0,
                prev_window_volume=0,
            )

        window = self._volume_windows[code]
        if not window:
            return VolumeAcceleration(0.0, 0.0, False, 0, 0)

        # LookaheadGuard: 시계열 입력이 배열이면 검사
        if lookahead_guard and timestamps is not None and context_timestamp is not None:
            lookahead_guard.check([v[1] for v in window], timestamps, context_timestamp, context_info or f"volume:{code}")

        now = window[-1][0]
        cutoff_current = now - lookback_seconds
        cutoff_prev = cutoff_current - lookback_seconds

        # 현재 윈도우 거래량
        current_vol = sum(vol for ts, vol in window if ts > cutoff_current)

        # 이전 윈도우 거래량
        prev_vol = sum(
            vol for ts, vol in window if cutoff_prev < ts <= cutoff_current
        )

        # Velocity (1차 도함수)
        if prev_vol == 0:
            velocity = 0.0
        else:
            velocity = (current_vol - prev_vol) / prev_vol

        # Acceleration (2차 도함수)
        prev_velocity = self._prev_velocities.get(code, 0.0)
        acceleration = velocity - prev_velocity
        self._prev_velocities[code] = velocity

        return VolumeAcceleration(
            velocity=velocity,
            acceleration=acceleration,
            is_accelerating=(velocity > 0 and acceleration > 0),
            current_window_volume=current_vol,
            prev_window_volume=prev_vol,
        )

    def get_velocity_score(self, velocity: float) -> float:
        """Velocity를 스코어로 변환

        Args:
            velocity: 거래량 변화율

        Returns:
            스코어 (0 ~ max_score)
        """
        c = self.config
        if velocity > c.very_high_threshold:
            return c.max_score
        elif velocity > c.high_threshold:
            return c.high_score
        elif velocity > c.mid_threshold:
            return c.mid_score
        elif velocity > 0:
            return c.low_score
        else:
            return 0.0

    def reset(self, code: str | None = None):
        """데이터 초기화

        Args:
            code: 특정 종목만 초기화 (None이면 전체)
        """
        if code:
            self._volume_windows.pop(code, None)
            self._prev_velocities.pop(code, None)
        else:
            self._volume_windows.clear()
            self._prev_velocities.clear()


# =============================================================================
# VWAP
# =============================================================================


@dataclass
class VWAPData:
    """VWAP 분석 결과

    Attributes:
        vwap: VWAP 값
        price_vs_vwap: 현재가 대비 VWAP 위치 (%)
        is_above_vwap: VWAP 위 여부
        cumulative_pv: 누적 (Price * Volume)
        cumulative_volume: 누적 거래량
    """

    vwap: float
    price_vs_vwap: float
    is_above_vwap: bool
    cumulative_pv: float
    cumulative_volume: int


@dataclass
class VWAPConfig:
    """VWAP 설정"""

    above_threshold_pct: float = 1.0  # VWAP 위 임계값 (%)
    max_score: float = 10.0
    mid_score: float = 5.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VWAPConfig:
        return cls(
            above_threshold_pct=data.get("above_threshold_pct", 1.0),
            max_score=data.get("max_score", 10.0),
            mid_score=data.get("mid_score", 5.0),
        )


class VWAPCalculator:
    """VWAP (Volume Weighted Average Price) 계산기

    VWAP = Sum(Price * Volume) / Sum(Volume)

    용도:
    - 일중 추세 기준선
    - VWAP 위에서 거래 = 강세
    - VWAP 아래에서 거래 = 약세

    Usage:
        calc = VWAPCalculator()
        calc.add_tick("005930", price=50000, volume=100, date_str="20240115")
        vwap_data = calc.calculate("005930", current_price=50500)
    """

    def __init__(self, config: VWAPConfig | None = None):
        """
        Args:
            config: 설정 (기본값 사용 시 None)
        """
        self.config = config or VWAPConfig()
        self._data: dict[str, dict] = {}

    def add_tick(
        self, code: str, price: float, volume: int, date_str: str
    ):
        """틱 추가

        Args:
            code: 종목코드
            price: 체결가
            volume: 체결량
            date_str: 날짜 문자열 (YYYYMMDD, 일자 변경 감지용)
        """
        if code not in self._data:
            self._data[code] = {"pv": 0.0, "volume": 0, "date": date_str}

        # 날짜 변경 시 초기화
        if self._data[code]["date"] != date_str:
            self._data[code] = {"pv": 0.0, "volume": 0, "date": date_str}

        # 누적
        self._data[code]["pv"] += price * volume
        self._data[code]["volume"] += volume

    def calculate(self, code: str, current_price: float) -> VWAPData:
        """VWAP 계산

        Args:
            code: 종목코드
            current_price: 현재가

        Returns:
            VWAPData
        """
        if code not in self._data or self._data[code]["volume"] == 0:
            return VWAPData(
                vwap=0.0,
                price_vs_vwap=0.0,
                is_above_vwap=False,
                cumulative_pv=0.0,
                cumulative_volume=0,
            )

        data = self._data[code]
        vwap = data["pv"] / data["volume"]

        # 현재가 vs VWAP
        if vwap > 0:
            price_vs_vwap = (current_price - vwap) / vwap * 100
        else:
            price_vs_vwap = 0.0

        return VWAPData(
            vwap=vwap,
            price_vs_vwap=price_vs_vwap,
            is_above_vwap=current_price > vwap,
            cumulative_pv=data["pv"],
            cumulative_volume=data["volume"],
        )

    def calculate_from_list(
        self, prices: list[float], volumes: list[int]
    ) -> VWAPData:
        """리스트 데이터로 VWAP 계산 (백테스트용)

        Args:
            prices: 가격 리스트
            volumes: 거래량 리스트

        Returns:
            VWAPData
        """
        if not prices or not volumes or len(prices) != len(volumes):
            return VWAPData(0.0, 0.0, False, 0.0, 0)

        total_pv = sum(p * v for p, v in zip(prices, volumes))
        total_volume = sum(volumes)

        if total_volume == 0:
            return VWAPData(0.0, 0.0, False, 0.0, 0)

        vwap = total_pv / total_volume
        current_price = prices[-1]
        price_vs_vwap = (
            (current_price - vwap) / vwap * 100 if vwap > 0 else 0.0
        )

        return VWAPData(
            vwap=vwap,
            price_vs_vwap=price_vs_vwap,
            is_above_vwap=current_price > vwap,
            cumulative_pv=total_pv,
            cumulative_volume=total_volume,
        )

    def get_vwap_score(self, price_vs_vwap: float) -> float:
        """VWAP 위치를 스코어로 변환

        Args:
            price_vs_vwap: 현재가 vs VWAP (%)

        Returns:
            스코어 (0 ~ max_score)
        """
        c = self.config
        if price_vs_vwap > c.above_threshold_pct:
            return c.max_score
        elif price_vs_vwap > 0.0:
            return c.mid_score
        else:
            return 0.0

    def reset(self, code: str | None = None):
        """데이터 초기화

        Args:
            code: 특정 종목만 초기화 (None이면 전체)
        """
        if code:
            self._data.pop(code, None)
        else:
            self._data.clear()


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
                obv_values=[], obv_sma=0.0,
                obv_trend=0.0, price_trend=0.0,
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
            obv_sma = float(np.mean(obv[-self.sma_period:]))
        else:
            obv_sma = float(np.mean(obv))

        # OBV 추세 (선형 회귀 기울기)
        tp = min(self.trend_period, len(obv))
        obv_trend = self._slope(obv[-tp:]) if tp >= 2 else 0.0

        # 가격 추세
        price_trend = self._slope(prices[-tp:]) if tp >= 2 else 0.0

        # 매집 판정: OBV 상승 + 가격 횡보
        price_range = (max(prices[-tp:]) - min(prices[-tp:])) / prices[-tp] if prices[-tp] > 0 else 0.0
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


# =============================================================================
# RVOL (Relative Volume)
# =============================================================================


@dataclass
class RVOLData:
    """RVOL 분석 결과

    Attributes:
        rvol_ratio: 상대 거래량 비율 (short_avg / long_avg)
        short_avg: 단기 평균 거래량
        long_avg: 장기 평균 거래량
        rvol_trend: RVOL 추세 (단기 거래량이 상승 중인지)
        is_unusual: 비정상적 거래량 여부 (rvol > threshold)
    """

    rvol_ratio: float
    short_avg: float
    long_avg: float
    rvol_trend: float
    is_unusual: bool


class RVOLCalculator:
    """Relative Volume (상대 거래량) 계산기

    RVOL = 단기 평균 거래량 / 장기 평균 거래량

    RVOL > 1.5 = 비정상적 활동
    RVOL이 며칠에 걸쳐 상승 = 관심 증가 (매집 가능성)

    Usage:
        calc = RVOLCalculator()
        data = calc.calculate(volumes=[100]*20 + [200]*5)
        print(f"RVOL: {data.rvol_ratio:.2f}x")
    """

    def __init__(
        self,
        short_window: int = 5,
        long_window: int = 20,
        unusual_threshold: float = 1.5,
    ):
        self.short_window = short_window
        self.long_window = long_window
        self.unusual_threshold = unusual_threshold

    def calculate(
        self,
        volumes: list[int],
        short_window: int | None = None,
        long_window: int | None = None,
    ) -> RVOLData:
        """RVOL 계산

        Args:
            volumes: 거래량 리스트 (oldest first)
            short_window: 단기 윈도우 (None이면 기본값)
            long_window: 장기 윈도우 (None이면 기본값)

        Returns:
            RVOLData
        """
        sw = short_window or self.short_window
        lw = long_window or self.long_window

        if len(volumes) < max(sw, lw):
            return RVOLData(
                rvol_ratio=1.0, short_avg=0.0, long_avg=0.0,
                rvol_trend=0.0, is_unusual=False,
            )

        short_avg = float(np.mean(volumes[-sw:]))
        long_avg = float(np.mean(volumes[-lw:]))

        if long_avg == 0:
            return RVOLData(
                rvol_ratio=1.0, short_avg=short_avg, long_avg=0.0,
                rvol_trend=0.0, is_unusual=False,
            )

        rvol_ratio = short_avg / long_avg

        # RVOL 추세: 슬라이딩 윈도우로 RVOL이 상승 중인지 확인
        rvol_trend = 0.0
        if len(volumes) >= lw + sw:
            rvol_series = []
            for i in range(min(sw, len(volumes) - lw + 1)):
                end = len(volumes) - sw + i + 1
                if end > sw and end <= len(volumes):
                    s_avg = float(np.mean(volumes[end - sw:end]))
                    l_avg = float(np.mean(volumes[end - lw:end]))
                    if l_avg > 0:
                        rvol_series.append(s_avg / l_avg)
            if len(rvol_series) >= 2:
                rvol_trend = rvol_series[-1] - rvol_series[0]

        return RVOLData(
            rvol_ratio=rvol_ratio,
            short_avg=short_avg,
            long_avg=long_avg,
            rvol_trend=rvol_trend,
            is_unusual=rvol_ratio >= self.unusual_threshold,
        )
