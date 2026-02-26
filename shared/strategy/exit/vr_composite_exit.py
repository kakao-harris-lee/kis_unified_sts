"""VR Composite Exit Strategy.

일봉(Daily) VR + RSI + MA 복합 신호 기반 청산 전략.

VR 과열/극단과열 구간에서 RSI 과매수 + MA 하락 전환 시 매도 신호를 생성한다.
Hard stop loss 및 최대 보유일수 안전장치를 포함한다.

청산 조건 (우선순위):
  0. Hard stop loss → 즉시 청산
  1. VR >= 400 + RSI >= 70 → STRONG_SELL (0.85)
  2. VR >= 300 + RSI >= 70 → STRONG_SELL (0.80)
  3. VR >= 300 + RSI >= 60 + close < MA5 → SELL (0.75)
  4. VR >= 300 + 50 < RSI < 70 + 하락 전환 → SELL (0.65)
  5. Max hold days 초과 → 시간 기반 청산

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
)
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class VRCompositeExitConfig(ConfigMixin):
    """VR Composite 청산 전략 설정"""

    # VR 파라미터
    vr_period: int = 20

    # VR 과열 임계값
    vr_overheat_threshold: float = 300.0
    vr_extreme_overheat_threshold: float = 400.0

    # RSI 파라미터
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_moderate_high: float = 60.0
    rsi_sell_lower: float = 50.0

    # MA 파라미터
    ma_short: int = 5
    ma_mid: int = 20
    ma_long: int = 60

    # 안전장치
    hard_stop_pct: float = -0.07  # -7% 손절
    max_hold_days: int = 60

    # 신뢰도
    confidence_strong_sell_1: float = 0.85
    confidence_strong_sell_2: float = 0.80
    confidence_sell_3: float = 0.75
    confidence_sell_4: float = 0.65
    default_exit_confidence: float = 0.70

    # 경고 표시
    show_warnings: bool = True

    # 일봉 데이터 키
    daily_closes_key: str = "daily_closes"
    daily_volumes_key: str = "daily_volumes"


class VRCompositeExit(ExitSignalGenerator[VRCompositeExitConfig]):
    """VR + RSI + MA 복합 청산 전략.

    VR 과열 구간 + RSI 과매수 + MA 하락 전환 조건에서 청산 신호를 생성한다.
    Hard stop loss 및 최대 보유일수 안전장치를 포함.
    """

    CONFIG_CLASS = VRCompositeExitConfig

    def __init__(self, config: VRCompositeExitConfig):
        super().__init__(config)
        self._vr_calc = VolumeRatioCalculator(period=config.vr_period)

    def _validate_config(self):
        assert self.config.vr_period >= 2, "vr_period must be >= 2"
        assert self.config.rsi_period > 0, "rsi_period must be > 0"
        assert -1.0 < self.config.hard_stop_pct < 0.0, "hard_stop_pct must be in (-1.0, 0.0)"
        assert self.config.max_hold_days > 0, "max_hold_days must be > 0"
        assert (
            self.config.vr_overheat_threshold < self.config.vr_extreme_overheat_threshold
        ), "vr_overheat_threshold < vr_extreme_overheat_threshold required"

    @property
    def name(self) -> str:
        return "vr_composite_exit"

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, Optional[ExitSignal]]:
        """청산 여부 판단."""
        position = context.position
        data = context.market_data or {}
        indicators = context.indicators or {}

        close = float(data.get("close", 0) or 0)
        if close <= 0:
            return (False, None)

        entry_price = position.entry_price
        code = position.code
        now = context.timestamp

        # 수익률 계산 (Long only)
        profit_pct = (close - entry_price) / entry_price if entry_price > 0 else 0.0

        # --- Priority 0: Hard stop ---
        if profit_pct <= self.config.hard_stop_pct:
            logger.info(
                "VRCompositeExit HARD STOP: %s profit=%.2f%% <= %.2f%%",
                code,
                profit_pct * 100,
                self.config.hard_stop_pct * 100,
            )
            return (
                True,
                ExitSignal(
                    code=code,
                    reason=ExitReason.STOP_LOSS,
                    strategy="vr_composite_exit",
                    current_price=close,
                    exit_price=close,
                    entry_price=entry_price,
                    profit_pct=profit_pct,
                    confidence=0.95,
                    priority=1,
                    timestamp=now,
                    metadata={"trigger": "hard_stop"},
                ),
            )

        # --- Priority 5: Max hold days ---
        hold_days = 0
        if hasattr(position, "entry_time") and position.entry_time:
            hold_delta = now - position.entry_time
            hold_days = hold_delta.days

        if hold_days >= self.config.max_hold_days:
            logger.info(
                "VRCompositeExit MAX HOLD: %s hold=%d days >= %d",
                code,
                hold_days,
                self.config.max_hold_days,
            )
            return (
                True,
                ExitSignal(
                    code=code,
                    reason=ExitReason.TIME_CUT,
                    strategy="vr_composite_exit",
                    current_price=close,
                    exit_price=close,
                    entry_price=entry_price,
                    profit_pct=profit_pct,
                    confidence=self.config.default_exit_confidence,
                    priority=2,
                    timestamp=now,
                    metadata={"trigger": "max_hold_days", "hold_days": hold_days},
                ),
            )

        # --- VR/RSI/MA 기반 청산 신호 ---
        closes = self._get_series(indicators, data, self.config.daily_closes_key)
        volumes = self._get_series(indicators, data, self.config.daily_volumes_key)

        if closes is None or volumes is None:
            return (False, None)

        min_required = max(
            self.config.vr_period + 1,
            self.config.rsi_period + 1,
            self.config.ma_long,
        )
        if len(closes) < min_required:
            return (False, None)

        # 지표 계산
        vr_values = self._vr_calc.calculate(closes, volumes)
        vr = vr_values[-1] if vr_values else None
        if vr is None:
            return (False, None)

        rsi_values = VolumeRatioCalculator.calculate_rsi(closes, self.config.rsi_period)
        rsi = rsi_values[-1] if rsi_values else None
        if rsi is None:
            return (False, None)

        ma5_values = VolumeRatioCalculator.calculate_sma(closes, self.config.ma_short)
        ma20_values = VolumeRatioCalculator.calculate_sma(closes, self.config.ma_mid)
        ma60_values = VolumeRatioCalculator.calculate_sma(closes, self.config.ma_long)

        ma5 = ma5_values[-1]
        ma20 = ma20_values[-1]
        ma60 = ma60_values[-1]

        if ma5 is None or ma20 is None or ma60 is None:
            return (False, None)

        ma_trend = VolumeRatioCalculator.get_ma_trend(close, ma5, ma20, ma60)

        # --- 매도 조건 테이블 (우선순위순) ---
        exit_reason = None
        confidence = 0.0
        reasons: list[str] = []
        warnings: list[str] = []

        # Rule 1: VR >= 400 + RSI >= 70
        if (
            vr >= self.config.vr_extreme_overheat_threshold
            and rsi >= self.config.rsi_overbought
        ):
            exit_reason = ExitReason.INDICATOR_EXIT
            confidence = self.config.confidence_strong_sell_1
            reasons = [
                f"VR {vr:.1f}%: 극단적 과열 ({self.config.vr_extreme_overheat_threshold}% 이상)",
                f"RSI {rsi:.1f}: 과매수 ({self.config.rsi_overbought} 이상)",
            ]
        # Rule 2: VR >= 300 + RSI >= 70
        elif (
            vr >= self.config.vr_overheat_threshold
            and rsi >= self.config.rsi_overbought
        ):
            exit_reason = ExitReason.INDICATOR_EXIT
            confidence = self.config.confidence_strong_sell_2
            reasons = [
                f"VR {vr:.1f}%: 과열권 ({self.config.vr_overheat_threshold}% 이상)",
                f"RSI {rsi:.1f}: 과매수 ({self.config.rsi_overbought} 이상)",
            ]
        # Rule 3: VR >= 300 + RSI >= 60 + close < MA5
        elif (
            vr >= self.config.vr_overheat_threshold
            and rsi >= self.config.rsi_moderate_high
            and close < ma5
        ):
            exit_reason = ExitReason.INDICATOR_EXIT
            confidence = self.config.confidence_sell_3
            reasons = [
                f"VR {vr:.1f}%: 과열권 ({self.config.vr_overheat_threshold}% 이상)",
                f"RSI {rsi:.1f} >= {self.config.rsi_moderate_high}",
                f"단기 하락: 종가 < MA{self.config.ma_short}",
            ]
        # Rule 4: VR >= 300 + 50 < RSI < 70 + 하락 전환
        elif (
            vr >= self.config.vr_overheat_threshold
            and self.config.rsi_sell_lower < rsi < self.config.rsi_overbought
            and ma_trend in (MATrend.DOWNTREND, MATrend.STRONG_DOWNTREND)
        ):
            exit_reason = ExitReason.INDICATOR_EXIT
            confidence = self.config.confidence_sell_4
            reasons = [
                f"VR {vr:.1f}%: 과열권 ({self.config.vr_overheat_threshold}% 이상)",
                f"RSI {rsi:.1f}: 중립~과매수 ({self.config.rsi_sell_lower}~{self.config.rsi_overbought})",
                f"추세: 하락 전환 ({ma_trend.value})",
            ]

        if exit_reason is None:
            return (False, None)

        # --- 경고 체크 ---
        if self.config.show_warnings:
            # VR 과열이나 강한 상승 모멘텀 유지
            if vr >= self.config.vr_overheat_threshold and ma_trend == MATrend.STRONG_UPTREND:
                warnings.append(
                    "⚠️ VR 과열이나 강한 상승 모멘텀 유지 중. 분할 매도 권장."
                )

        logger.info(
            "VRCompositeExit SELL: %s VR=%.1f%% RSI=%.1f MA=%s conf=%.2f | %s",
            code,
            vr,
            rsi,
            ma_trend.value,
            confidence,
            "; ".join(reasons),
        )

        return (
            True,
            ExitSignal(
                code=code,
                reason=exit_reason,
                strategy="vr_composite_exit",
                current_price=close,
                exit_price=close,
                entry_price=entry_price,
                profit_pct=profit_pct,
                confidence=confidence,
                priority=3,
                timestamp=now,
                metadata={
                    "trigger": "vr_composite",
                    "vr": vr,
                    "rsi": rsi,
                    "ma_trend": ma_trend.value,
                    "reasons": reasons,
                    "warnings": warnings,
                },
            ),
        )

    async def scan_positions(
        self,
        positions: list,
        market_data: dict[str, Any],
        market_state: Optional[Any] = None,
    ) -> list[ExitSignal]:
        """여러 포지션에 대해 VR 기반 청산 시그널 스캔."""
        exit_signals: list[ExitSignal] = []

        for position in positions:
            ctx = ExitContext(
                position=position,
                market_data=market_data.get(position.code, {}),
                indicators=market_data.get(f"{position.code}_indicators", {}),
                timestamp=datetime.now(),
                market_state=market_state,
            )
            should, signal = await self.should_exit(ctx)
            if should and signal:
                exit_signals.append(signal)

        return exit_signals

    @staticmethod
    def _get_series(
        indicators: dict[str, Any],
        data: dict[str, Any],
        key: str,
    ) -> Optional[list]:
        """indicators 또는 data에서 시계열 데이터를 추출"""
        for source in (indicators, data):
            val = source.get(key)
            if val is not None and hasattr(val, "__len__") and len(val) > 0:
                return list(val)
        return None
