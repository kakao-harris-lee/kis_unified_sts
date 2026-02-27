"""VR Composite Entry Strategy.

일봉(Daily) VR + RSI + MA 복합 신호 기반 진입 전략.

VR(Volume Ratio)이 침체/바닥권에 진입하고 RSI 과매도 + MA 추세가
반등을 시사할 때 매수 신호를 생성한다.

매수 조건 (우선순위순):
  1. VR <= 60 (바닥권) + RSI <= 30 (과매도) + 하락 둔화/횡보 → STRONG_BUY (0.85)
  2. VR <= 75 (침체권) + RSI <= 30 (과매도)               → STRONG_BUY (0.80)
  3. VR <= 60 (바닥권) + RSI <= 40 + close > MA5           → BUY (0.75)
  4. VR <= 75 (침체권) + RSI <= 40 + close > MA20          → BUY (0.70)
  5. VR <= 75 (침체권) + 30 < RSI <= 50 + 상승/횡보        → BUY (0.60)

이 전략은 일봉 전용(timeframe: daily)이며, indicators dict에
VR, RSI, MA 값이 포함되어야 한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from shared.config.mixins import ConfigMixin
from shared.indicators.volume_ratio import (
    MATrend,
    VolumeRatioCalculator,
    VRZone,
)
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator, get_series_from_context

logger = logging.getLogger(__name__)


@dataclass
class VRCompositeConfig(ConfigMixin):
    """VR Composite 진입 전략 설정"""

    # VR 파라미터
    vr_period: int = 20

    # VR 구간 임계값
    vr_bottom_threshold: float = 60.0  # 바닥권 상한
    vr_depression_threshold: float = 75.0  # 침체권 상한

    # RSI 파라미터
    rsi_period: int = 14
    rsi_oversold: float = 30.0  # 과매도 기준
    rsi_weak_oversold: float = 40.0  # 약한 과매도 기준
    rsi_neutral_upper: float = 50.0  # 중립 상한

    # MA 파라미터
    ma_short: int = 5
    ma_mid: int = 20
    ma_long: int = 60

    # 신호 신뢰도 (우선순위별)
    confidence_strong_buy_1: float = 0.85
    confidence_strong_buy_2: float = 0.80
    confidence_buy_3: float = 0.75
    confidence_buy_4: float = 0.70
    confidence_buy_5: float = 0.60

    # 거래량 경고
    volume_warning_short_window: int = 5
    volume_warning_long_window: int = 20
    volume_warning_threshold: float = 0.5

    # Risk hint
    stop_loss_pct: float = 7.0

    # Cooldown (일 단위)
    signal_cooldown_days: int = 3

    # RSI 과매수 기준 (경고용)
    rsi_overbought: float = 70.0

    # 경고 표시
    show_warnings: bool = True

    # 사용할 일봉 데이터 키 (indicators dict 내)
    daily_closes_key: str = "daily_closes"
    daily_volumes_key: str = "daily_volumes"


class VRCompositeEntry(EntrySignalGenerator[VRCompositeConfig]):
    """VR + RSI + MA 복합 진입 전략.

    일봉 기반 VR 지표가 침체/바닥 구간에 진입하고,
    RSI 과매도 + MA 추세 반등 조건을 만족하면 매수 신호를 생성한다.
    """

    CONFIG_CLASS = VRCompositeConfig

    def __init__(self, config: VRCompositeConfig):
        super().__init__(config)
        self._vr_calc = VolumeRatioCalculator(period=config.vr_period)
        self._last_signal_at: dict[str, datetime] = {}

    def _validate_config(self):
        assert self.config.vr_period >= 2, "vr_period must be >= 2"
        assert self.config.rsi_period > 0, "rsi_period must be > 0"
        assert 0 < self.config.rsi_oversold < 50, "rsi_oversold must be in (0, 50)"
        assert (
            self.config.rsi_oversold <= self.config.rsi_weak_oversold
        ), "rsi_oversold must be <= rsi_weak_oversold"
        assert self.config.ma_short > 0, "ma_short must be > 0"
        assert self.config.ma_mid > 0, "ma_mid must be > 0"
        assert self.config.ma_long > 0, "ma_long must be > 0"
        assert (
            self.config.ma_short < self.config.ma_mid < self.config.ma_long
        ), "ma_short < ma_mid < ma_long required"
        assert (
            self.config.vr_bottom_threshold < self.config.vr_depression_threshold
        ), "vr_bottom_threshold must be < vr_depression_threshold"
        assert self.config.stop_loss_pct > 0, "stop_loss_pct must be > 0"

    @property
    def name(self) -> str:
        return "vr_composite"

    @property
    def required_indicators(self) -> list[str]:
        return ["daily_closes", "daily_volumes"]

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        """VR 복합 진입 신호 생성.

        indicators dict에 일봉 시계열 데이터가 있어야 한다:
          - daily_closes: list[float]  (최소 vr_period + ma_long 이상)
          - daily_volumes: list[int]
        """
        data = context.market_data or {}
        indicators = context.indicators or {}

        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or code)
        if not code:
            return None

        # --- 쿨다운 체크 ---
        if self.config.signal_cooldown_days > 0 and code in self._last_signal_at:
            elapsed = (context.timestamp - self._last_signal_at[code]).days
            if elapsed < self.config.signal_cooldown_days:
                return None

        # --- 일봉 데이터 추출 ---
        closes = get_series_from_context(indicators, data, self.config.daily_closes_key)
        volumes = get_series_from_context(indicators, data, self.config.daily_volumes_key)

        if closes is None or volumes is None:
            logger.debug("VRComposite: 일봉 데이터 없음 (%s)", code)
            return None

        min_required = max(
            self.config.vr_period + 1,
            self.config.rsi_period + 1,
            self.config.ma_long,
        )
        if len(closes) < min_required:
            logger.debug(
                "VRComposite: 데이터 부족 (%s, %d < %d)", code, len(closes), min_required
            )
            return None

        # --- 지표 계산 ---
        vr_values = self._vr_calc.calculate(closes, volumes)
        vr = vr_values[-1] if vr_values else None

        if vr is None:
            return None

        rsi_values = VolumeRatioCalculator.calculate_rsi(closes, self.config.rsi_period)
        rsi = rsi_values[-1] if rsi_values else None
        if rsi is None:
            return None

        ma5_values = VolumeRatioCalculator.calculate_sma(closes, self.config.ma_short)
        ma20_values = VolumeRatioCalculator.calculate_sma(closes, self.config.ma_mid)
        ma60_values = VolumeRatioCalculator.calculate_sma(closes, self.config.ma_long)

        ma5 = ma5_values[-1] if ma5_values else None
        ma20 = ma20_values[-1] if ma20_values else None
        ma60 = ma60_values[-1] if ma60_values else None

        if ma5 is None or ma20 is None or ma60 is None:
            return None

        close = closes[-1]
        ma_trend = VolumeRatioCalculator.get_ma_trend(close, ma5, ma20, ma60)
        vr_zone = self._vr_calc.get_zone(vr)
        vr_zone_name = vr_zone.zone.value if vr_zone else "unknown"

        # --- 복합 신호 판단 (우선순위순) ---
        signal_type = None
        confidence = 0.0
        reasons: list[str] = []

        # Rule 1: VR <= 60 + RSI <= 30 + 하락 둔화/횡보
        if (
            vr <= self.config.vr_bottom_threshold
            and rsi <= self.config.rsi_oversold
            and ma_trend in (MATrend.SIDEWAYS, MATrend.UPTREND)
        ):
            signal_type = SignalType.ENTRY
            confidence = self.config.confidence_strong_buy_1
            reasons = [
                f"VR {vr:.1f}%: 바닥권 ({self.config.vr_bottom_threshold}% 이하)",
                f"RSI {rsi:.1f}: 과매도 ({self.config.rsi_oversold} 이하)",
                f"MA 추세: 하락 둔화/횡보 ({ma_trend.value})",
            ]
        # Rule 2: VR <= 75 + RSI <= 30
        elif (
            vr <= self.config.vr_depression_threshold and rsi <= self.config.rsi_oversold
        ):
            signal_type = SignalType.ENTRY
            confidence = self.config.confidence_strong_buy_2
            reasons = [
                f"VR {vr:.1f}%: 침체권 ({self.config.vr_depression_threshold}% 이하)",
                f"RSI {rsi:.1f}: 과매도 ({self.config.rsi_oversold} 이하)",
            ]
        # Rule 3: VR <= 60 + RSI <= 40 + close > MA5
        elif (
            vr <= self.config.vr_bottom_threshold
            and rsi <= self.config.rsi_weak_oversold
            and close > ma5
        ):
            signal_type = SignalType.ENTRY
            confidence = self.config.confidence_buy_3
            reasons = [
                f"VR {vr:.1f}%: 바닥권 ({self.config.vr_bottom_threshold}% 이하)",
                f"RSI {rsi:.1f}: 약한 과매도 ({self.config.rsi_weak_oversold} 이하)",
                f"단기 반등: 종가 > MA{self.config.ma_short}",
            ]
        # Rule 4: VR <= 75 + RSI <= 40 + close > MA20
        elif (
            vr <= self.config.vr_depression_threshold
            and rsi <= self.config.rsi_weak_oversold
            and close > ma20
        ):
            signal_type = SignalType.ENTRY
            confidence = self.config.confidence_buy_4
            reasons = [
                f"VR {vr:.1f}%: 침체권 ({self.config.vr_depression_threshold}% 이하)",
                f"RSI {rsi:.1f}: 약한 과매도 ({self.config.rsi_weak_oversold} 이하)",
                f"중기 지지: 종가 > MA{self.config.ma_mid}",
            ]
        # Rule 5: VR <= 75 + 30 < RSI <= 50 + 상승/횡보
        elif (
            vr <= self.config.vr_depression_threshold
            and self.config.rsi_oversold < rsi <= self.config.rsi_neutral_upper
            and ma_trend in (MATrend.UPTREND, MATrend.STRONG_UPTREND, MATrend.SIDEWAYS)
        ):
            signal_type = SignalType.ENTRY
            confidence = self.config.confidence_buy_5
            reasons = [
                f"VR {vr:.1f}%: 침체권 ({self.config.vr_depression_threshold}% 이하)",
                f"RSI {rsi:.1f}: 중립하단 ({self.config.rsi_oversold}~{self.config.rsi_neutral_upper})",
                f"추세: 상승 또는 횡보 ({ma_trend.value})",
            ]
        else:
            # 관망
            return None

        # --- 경고 체크 ---
        warnings: list[str] = []
        if self.config.show_warnings:
            warnings = self._check_warnings(vr, rsi, ma_trend, volumes)

        # --- 신호 생성 ---
        self._last_signal_at[code] = context.timestamp

        metadata: dict[str, Any] = {
            "vr": vr,
            "vr_zone": vr_zone_name,
            "rsi": rsi,
            "ma_trend": ma_trend.value,
            "ma5": ma5,
            "ma20": ma20,
            "ma60": ma60,
            "reasons": reasons,
            "warnings": warnings,
            "stop_loss_pct": self.config.stop_loss_pct,
            "strategy_type": "daily",
        }

        signal = Signal(
            code=code,
            name=name,
            signal_type=signal_type,
            strategy=self.name,
            price=close,
            confidence=confidence,
            timestamp=context.timestamp,
            metadata=metadata,
        )

        logger.info(
            "VRComposite BUY signal: %s %.0f원, VR=%.1f%% RSI=%.1f MA=%s conf=%.2f | %s",
            code,
            close,
            vr,
            rsi,
            ma_trend.value,
            confidence,
            "; ".join(reasons),
        )

        return signal

    def _check_warnings(
        self,
        vr: float,
        rsi: float,
        ma_trend: MATrend,
        volumes: list,
    ) -> list[str]:
        """경고 플래그 체크"""
        warnings: list[str] = []

        # VR 바닥인데 강한 하락 추세
        if vr <= self.config.vr_bottom_threshold and ma_trend == MATrend.STRONG_DOWNTREND:
            warnings.append(
                "⚠️ VR 바닥권이나 강한 하락 추세. 추가 하락 가능성. 분할 매수 권장."
            )

        # VR-RSI 다이버전스: VR은 매수 시그널인데 RSI는 70 이상
        vr_zone = self._vr_calc.get_zone(vr)
        if vr_zone and vr_zone.zone in (VRZone.DEPRESSION, VRZone.BOTTOM, VRZone.EXTREME_BOTTOM):
            if rsi >= self.config.rsi_overbought:
                warnings.append("⚠️ VR과 RSI 신호 불일치. 신호 신뢰도 하락.")

        # 거래량 급감
        if VolumeRatioCalculator.check_volume_warning(
            volumes,
            short_window=self.config.volume_warning_short_window,
            long_window=self.config.volume_warning_long_window,
            threshold=self.config.volume_warning_threshold,
        ):
            warnings.append("⚠️ 거래량 급감. VR 신뢰도 저하 가능성.")

        return warnings

