"""ATR Dynamic Exit Strategy.

ATR 기반 동적 손절/트레일링 스탑 청산 전략:
- Hard stop: loss > ATR × stop_multiplier
- Trailing stop: profit > ATR × trail_activation → trail at ATR × trail_multiplier from high
- Momentum decay: retracement > ATR and volume_velocity < 0 (optional)
- Max hold days: 보유 기간 초과 시 청산 (optional)
- EOD close: 장 마감 시 청산 (optional)

Exit Priority:
    1. Hard stop (ATR-based stop loss)
    2. EOD close (if enabled)
    3. Trailing stop (if profit > trail_activation_atr × ATR)
    4. Momentum decay (if momentum_decay_exit=True)
    5. Max hold days (if max_hold_days > 0)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol
from shared.strategy.market_data import get_price_from_snapshot, get_symbol_snapshot
from shared.strategy.market_time import (
    effective_close_time,
    is_trading_day_kst,
    now_kst,
    to_kst,
)

logger = logging.getLogger(__name__)


@dataclass
class ATRDynamicExitConfig(ConfigMixin):
    """ATR Dynamic Exit 설정"""

    # ATR 계산 기간
    atr_period: int = 14

    # Hard stop: loss > ATR × stop_atr_multiplier
    stop_atr_multiplier: float = 2.5

    # Trailing stop activation: profit > ATR × trail_activation_atr
    trail_activation_atr: float = 1.0

    # Trailing stop distance: trail at ATR × trail_atr_multiplier from high_since_entry
    trail_atr_multiplier: float = 2.0

    # Momentum decay exit (optional)
    momentum_decay_exit: bool = False

    # Max hold days (0 = disabled)
    max_hold_days: int = 0

    # Percentage-based hard stop fallback (safety net when ATR is unavailable).
    # Triggers when loss exceeds this percentage regardless of ATR data.
    # 0 = disabled (not recommended).
    max_loss_pct: float = 5.0

    # EOD close
    eod_close_enabled: bool = False
    eod_close_hour: int = 15
    eod_close_minute: int = 15

    # Exit signal confidence
    default_exit_confidence: float = 0.85

    @property
    def eod_close_time(self) -> time:
        return time(self.eod_close_hour, self.eod_close_minute)

    def validate(self) -> None:
        if self.stop_atr_multiplier <= 0:
            raise ValueError("stop_atr_multiplier must be positive")
        if self.trail_activation_atr <= 0:
            raise ValueError("trail_activation_atr must be positive")
        if self.trail_atr_multiplier <= 0:
            raise ValueError("trail_atr_multiplier must be positive")
        if self.atr_period <= 0:
            raise ValueError("atr_period must be positive")
        if self.max_hold_days < 0:
            raise ValueError("max_hold_days must be non-negative")
        if not (0.0 < self.default_exit_confidence <= 1.0):
            raise ValueError("default_exit_confidence must be in (0, 1]")
        if self.max_loss_pct < 0:
            raise ValueError("max_loss_pct must be non-negative")


class ATRDynamicExit(ExitSignalGenerator[ATRDynamicExitConfig]):
    """ATR 기반 동적 청산 전략.

    ATR 절대값을 사용하여 손절 및 트레일링 스탑을 동적으로 계산한다.
    선물/주식 모두 사용 가능하며, 롱/숏 양방향 지원.
    """

    CONFIG_CLASS = ATRDynamicExitConfig
    NAME = "ATR_DYNAMIC_EXIT"

    def __init__(self, config: ATRDynamicExitConfig):
        super().__init__(config)

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "atr_dynamic"

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, ExitSignal | None]:
        """단일 포지션 청산 여부 판단 (scan_positions가 primary)."""
        signal = self._check_position(context.position, context.market_data, context.timestamp)
        return (signal is not None, signal)

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
    ) -> list[ExitSignal]:
        """여러 포지션에 대해 ATR 동적 청산 시그널 스캔."""
        _ = market_state
        if not positions:
            return []

        signals = []
        now = now_kst()

        for position in positions:
            snapshot = get_symbol_snapshot(market_data, position.code)
            signal = self._check_position(position, snapshot, now)
            if signal:
                signals.append(signal)

        if signals:
            logger.info(
                f"[{self.name}] {len(signals)}/{len(positions)} positions "
                f"triggered exit signals"
            )
        return signals

    def _check_position(
        self,
        position: Position,
        market_data_for_symbol: dict[str, Any],
        now: datetime,
    ) -> ExitSignal | None:
        """개별 포지션 청산 조건 체크.

        Priority:
            1. Hard stop (ATR-based)
            2. EOD close (if enabled)
            3. Trailing stop (if profit exceeds trail activation threshold)
            4. Momentum decay (if enabled)
            5. Max hold days (if > 0)
        """
        snapshot = market_data_for_symbol

        current_price = self._get_current_price(position, snapshot)
        if current_price is None:
            return None

        atr = self._get_atr(snapshot, current_price)
        profit_pct = self._calc_profit_pct(position, current_price)
        profit_amount = self._calc_profit_amount(position, current_price)
        holding_minutes = int(
            (to_kst(now) - to_kst(position.entry_time)).total_seconds() / 60
        )
        high_since_entry = self._get_extreme_since_entry(position, current_price)

        # Read per-position exit parameter overrides (from trend mode entry signal)
        pos_meta = position.metadata or {}
        stop_mult = pos_meta.get("exit_stop_atr_multiplier", self.config.stop_atr_multiplier)
        trail_act = pos_meta.get("exit_trail_activation_atr", self.config.trail_activation_atr)
        trail_mult = pos_meta.get("exit_trail_atr_multiplier", self.config.trail_atr_multiplier)
        max_hold = pos_meta.get("exit_max_hold_days", self.config.max_hold_days)
        max_loss = pos_meta.get("exit_max_loss_pct", self.config.max_loss_pct)

        # 0. Safety net: percentage-based hard stop (ATR-independent).
        #    Catches positions when indicator data is stale/unavailable.
        #    Runs before ATR stop (step 1) — keep max_loss_pct >= typical ATR stop
        #    to avoid shadowing the ATR-based stop. Per-position overrides from
        #    metadata can tighten this, which is intentional for trend mode.
        if max_loss > 0 and profit_pct <= -max_loss / 100:
            logger.warning(
                "[%s] max_loss_pct safety stop triggered for %s: "
                "profit=%.2f%%, limit=-%.1f%%, atr=%.4f",
                self.name, position.code, profit_pct * 100, max_loss, atr,
            )
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.STOP_LOSS,
                priority=0,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
                metadata={
                    "stop_type": "max_loss_pct_safety",
                    "max_loss_pct": max_loss,
                    "atr": atr,
                },
            )

        # 1. Hard stop: loss > ATR × stop_multiplier
        if atr > 0 and position.entry_price > 0:
            stop_distance = atr * stop_mult
            stop_pct = -stop_distance / position.entry_price
            if profit_pct <= stop_pct:
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.STOP_LOSS,
                    priority=1,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                    metadata={
                        "stop_type": "atr_hard_stop",
                        "atr": atr,
                        "stop_pct": stop_pct,
                        "stop_atr_multiplier": stop_mult,
                    },
                )

        # 2. EOD close (if enabled)
        if self.config.eod_close_enabled:
            close_time = effective_close_time(self.config.eod_close_time)
            if is_trading_day_kst(now) and to_kst(now).time() >= close_time:
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.EOD_CLOSE,
                    priority=1,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                )

        # 3. Trailing stop: if position ever reached trail_activation_atr × ATR profit
        #    (check peak/trough reached, not current profit — position may have retraced)
        if atr > 0 and position.entry_price > 0:
            trail_activation_distance = atr * trail_act
            trail_distance = atr * trail_mult

            if position.side == PositionSide.LONG:
                # Activation: best price ever achieved >= entry + trail_activation_distance
                best_price = high_since_entry
                if best_price >= position.entry_price + trail_activation_distance:
                    trail_stop_price = best_price - trail_distance
                    if current_price <= trail_stop_price:
                        return self._create_exit_signal(
                            position=position,
                            current_price=current_price,
                            profit_pct=profit_pct,
                            profit_amount=profit_amount,
                            reason=ExitReason.TRAILING_STOP,
                            priority=2,
                            high_since_entry=high_since_entry,
                            holding_minutes=holding_minutes,
                            metadata={
                                "trail_stop_price": trail_stop_price,
                                "high_since_entry": high_since_entry,
                                "atr": atr,
                                "trail_atr_multiplier": trail_mult,
                            },
                        )
            else:  # SHORT
                # For short, high_since_entry actually holds the lowest price reached
                best_price = high_since_entry  # lowest price seen
                if best_price <= position.entry_price - trail_activation_distance:
                    trail_stop_price = best_price + trail_distance
                    if current_price >= trail_stop_price:
                        return self._create_exit_signal(
                            position=position,
                            current_price=current_price,
                            profit_pct=profit_pct,
                            profit_amount=profit_amount,
                            reason=ExitReason.TRAILING_STOP,
                            priority=2,
                            high_since_entry=high_since_entry,
                            holding_minutes=holding_minutes,
                            metadata={
                                "trail_stop_price": trail_stop_price,
                                "high_since_entry": high_since_entry,
                                "atr": atr,
                                "trail_atr_multiplier": trail_mult,
                            },
                        )

        # 4. Momentum decay (if enabled)
        if self.config.momentum_decay_exit and atr > 0:
            volume_velocity = float(snapshot.get("volume_velocity", 0) or 0)
            retracement = high_since_entry - current_price if position.side == PositionSide.LONG else current_price - high_since_entry
            if retracement > atr and volume_velocity < 0:
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.MOMENTUM_DECAY,
                    priority=2,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                    metadata={
                        "retracement": retracement,
                        "atr": atr,
                        "volume_velocity": volume_velocity,
                    },
                )

        # 5. Max hold days (if > 0)
        if max_hold > 0:
            holding_days = holding_minutes / (60 * 24)
            if holding_days >= max_hold:
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.TIME_CUT,
                    priority=3,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                    metadata={
                        "holding_days": holding_days,
                        "max_hold_days": max_hold,
                    },
                )

        return None

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_atr(snapshot: dict[str, Any], current_price: float) -> float:
        """Get ATR absolute value from snapshot.

        If ATR is normalized (ratio < 0.5), convert to absolute using current_price.
        """
        atr = float(snapshot.get("atr", 0) or 0)
        if atr <= 0:
            return 0.0

        # Detect normalized ATR (ratio form, typically 0.001~0.05)
        # KRX stocks/futures have absolute ATR >= 1 (min tick 0.01~0.05).
        # Use 0.5 threshold to safely distinguish normalized from absolute.
        if atr < 0.5 and current_price > 0:
            atr = atr * current_price

        return atr

    @staticmethod
    def _get_current_price(
        position: Position, snapshot: dict[str, Any]
    ) -> float | None:
        price = get_price_from_snapshot(snapshot)
        if price is not None:
            return price
        if position.current_price > 0:
            return position.current_price
        return None

    @staticmethod
    def _calc_profit_pct(position: Position, current_price: float) -> float:
        if position.entry_price <= 0:
            return 0.0
        if position.side == PositionSide.SHORT:
            return (position.entry_price - current_price) / position.entry_price
        return (current_price - position.entry_price) / position.entry_price

    @staticmethod
    def _calc_profit_amount(position: Position, current_price: float) -> float:
        if position.side == PositionSide.SHORT:
            return (position.entry_price - current_price) * position.quantity
        return (current_price - position.entry_price) * position.quantity

    @staticmethod
    def _get_extreme_since_entry(position: Position, current_price: float) -> float:
        """Return high_since_entry for LONG, low_since_entry for SHORT."""
        if position.side == PositionSide.SHORT:
            return min(
                position.lowest_price
                if position.lowest_price < float("inf")
                else position.entry_price,
                current_price,
            )
        return max(position.highest_price or position.entry_price, current_price)

    def _create_exit_signal(
        self,
        position: Position,
        current_price: float,
        profit_pct: float,
        profit_amount: float,
        reason: ExitReason,
        priority: int,
        high_since_entry: float,
        holding_minutes: int,
        metadata: dict[str, Any] | None = None,
    ) -> ExitSignal:
        now = now_kst()
        logger.info(
            f"[{self.name}] Exit signal: {position.code} | "
            f"Reason: {reason.value} | P/L: {profit_pct:+.2%} | "
            f"price={current_price:.0f} | held={holding_minutes}min"
        )
        return ExitSignal(
            code=position.code,
            name=position.name,
            position_id=position.id,
            reason=reason,
            strategy=self.name,
            current_price=current_price,
            exit_price=current_price,
            entry_price=position.entry_price,
            profit_amount=profit_amount,
            profit_pct=profit_pct,
            confidence=self.config.default_exit_confidence,
            priority=priority,
            timestamp=now,
            stage=PositionState.SURVIVAL.value,
            high_since_entry=high_since_entry,
            holding_minutes=holding_minutes,
            quantity=position.quantity,
            metadata=metadata or {},
        )
