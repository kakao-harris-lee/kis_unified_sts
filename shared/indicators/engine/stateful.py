"""Stateful streaming indicators (session VWAP, tick-second volume acceleration).

The engine's :class:`~shared.indicators.engine.base.IndicatorBackend` is a *pure,
stateless* ``compute(spec, window) -> values`` function — the right model for
indicators that are a function of a bounded OHLCV window. But two runtime
indicators are fundamentally **stateful**: they accumulate raw ticks over a
session and cannot be reconstructed from a bar window without changing their
meaning:

* :class:`VWAPCalculator` — session VWAP: ``sum(price*volume)/sum(volume)`` over
  every tick since the session open, reset on the KST date boundary. (Distinct
  from the engine's window ``vwap`` in :mod:`~shared.indicators.engine.numpy_backend`,
  which is a cumulative-over-window typical-price VWAP — a different indicator.)
* :class:`VolumeAccelerationCalculator` — velocity/acceleration of volume over
  trailing *tick-second* windows. (Distinct from the bar-based ``volume_acceleration``.)

They are therefore a first-class *category* of their own — kept here, under the
engine package, so all indicator computation lives in one place, but with their
native ``add_tick`` / ``reset`` APIs rather than forced through the window
interface (their tick signatures differ, so a common ABC would be a fiction).
Relocated verbatim from ``shared/indicators/volume.py`` (value-preserving); that
module now re-exports them for backward compatibility.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any


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
        self._volume_windows: dict[str, deque[tuple[float, int]]] = {}
        self._prev_velocities: dict[str, float] = {}

    def add_tick(self, code: str, volume: int, timestamp: float):
        """틱 추가

        Args:
            code: 종목코드
            volume: 체결량
            timestamp: 타임스탬프 (Unix epoch)
        """
        if code not in self._volume_windows:
            self._volume_windows[code] = deque(maxlen=self.config.window_size * 10)

        self._volume_windows[code].append((timestamp, volume))

    def calculate(
        self,
        code: str,
        lookback_seconds: int | None = None,
        *,
        timestamps: list = None,
        context_timestamp=None,
        lookahead_guard=None,
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
            lookahead_guard.check(
                [v[1] for v in window],
                timestamps,
                context_timestamp,
                context_info or f"volume:{code}",
            )

        now = window[-1][0]
        cutoff_current = now - lookback_seconds
        cutoff_prev = cutoff_current - lookback_seconds

        # 현재 윈도우 거래량
        current_vol = sum(vol for ts, vol in window if ts > cutoff_current)

        # 이전 윈도우 거래량
        prev_vol = sum(vol for ts, vol in window if cutoff_prev < ts <= cutoff_current)

        # Velocity (1차 도함수)
        velocity = 0.0 if prev_vol == 0 else (current_vol - prev_vol) / prev_vol

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

    def add_tick(self, code: str, price: float, volume: int, date_str: str):
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
        price_vs_vwap = (current_price - vwap) / vwap * 100 if vwap > 0 else 0.0

        return VWAPData(
            vwap=vwap,
            price_vs_vwap=price_vs_vwap,
            is_above_vwap=current_price > vwap,
            cumulative_pv=data["pv"],
            cumulative_volume=data["volume"],
        )

    def calculate_from_list(self, prices: list[float], volumes: list[int]) -> VWAPData:
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
        price_vs_vwap = (current_price - vwap) / vwap * 100 if vwap > 0 else 0.0

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
