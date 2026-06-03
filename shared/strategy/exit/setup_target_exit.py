"""Strategy-native exit for Setup A/C futures entries.

Uses absolute stop/target prices emitted by the decision-engine setup adapters.
This replaces the legacy RL exit dependency while keeping deterministic,
auditable stop-loss and target behavior.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import time
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
class SetupTargetExitConfig(ConfigMixin):
    """Exit config for setup-generated absolute stop/target prices."""

    eod_close_enabled: bool = True
    eod_close_hour: int = 15
    eod_close_minute: int = 15
    default_exit_confidence: float = 0.9

    @property
    def eod_close_time(self) -> time:
        return time(self.eod_close_hour, self.eod_close_minute)

    def validate(self) -> None:
        if not (0.0 < self.default_exit_confidence <= 1.0):
            raise ValueError("default_exit_confidence must be in (0, 1]")


class SetupTargetExit(ExitSignalGenerator[SetupTargetExitConfig]):
    """Exit when setup stop/target price is reached.

    The entry adapters emit absolute ``stop_loss`` and ``take_profit`` prices.
    ``PositionTracker`` stores the stop on ``position.stop_price`` and preserves
    the target in ``position.metadata['take_profit']``.
    """

    CONFIG_CLASS = SetupTargetExitConfig
    NAME = "SETUP_TARGET_EXIT"

    def __init__(self, config: SetupTargetExitConfig):
        super().__init__(config)

    @property
    def name(self) -> str:
        return "setup_target_exit"

    def _validate_config(self) -> None:
        self.config.validate()

    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        signal = self._check_position(
            context.position,
            context.market_data or {},
        )
        return (signal is not None, signal)

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
    ) -> list[ExitSignal]:
        signals: list[ExitSignal] = []
        for position in positions:
            snapshot = get_symbol_snapshot(market_data, position.code)
            signal = self._check_position(position, snapshot)
            if signal is not None:
                signals.append(signal)
        return signals

    def _check_position(
        self, position: Position, snapshot: dict[str, Any]
    ) -> ExitSignal | None:
        current_price = get_price_from_snapshot(snapshot)
        if current_price is None:
            current_price = (
                position.current_price if position.current_price > 0 else None
            )
        if current_price is None or position.entry_price <= 0:
            return None

        now = now_kst()
        profit_pct = self._calc_profit_pct(position, current_price)
        profit_amount = self._calc_profit_amount(position, current_price)
        holding_minutes = int(
            (to_kst(now) - to_kst(position.entry_time)).total_seconds() / 60
        )

        stop_price = self._read_positive_float(
            position.stop_price or (position.metadata or {}).get("stop_loss")
        )
        take_profit = self._read_positive_float(
            (position.metadata or {}).get("take_profit")
        )

        if stop_price is not None and self._price_crossed(
            side=position.side,
            current_price=current_price,
            trigger_price=stop_price,
            trigger="stop",
        ):
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.STOP_LOSS,
                priority=1,
                holding_minutes=holding_minutes,
                metadata={"stop_price": stop_price},
            )

        if take_profit is not None and self._price_crossed(
            side=position.side,
            current_price=current_price,
            trigger_price=take_profit,
            trigger="target",
        ):
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.TARGET_REACHED,
                priority=2,
                holding_minutes=holding_minutes,
                metadata={"take_profit": take_profit},
            )

        if self._should_eod_close(now):
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.EOD_CLOSE,
                priority=3,
                holding_minutes=holding_minutes,
                metadata={"eod_close_time": self.config.eod_close_time.isoformat()},
            )

        return None

    def _should_eod_close(self, now) -> bool:
        if not self.config.eod_close_enabled:
            return False
        now_local = to_kst(now)
        if not is_trading_day_kst(now_local.date()):
            return False
        close_time = effective_close_time(now_local.date(), self.config.eod_close_time)
        return now_local.time() >= close_time

    @staticmethod
    def _read_positive_float(value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _price_crossed(
        *,
        side: PositionSide,
        current_price: float,
        trigger_price: float,
        trigger: str,
    ) -> bool:
        if side == PositionSide.LONG:
            return (
                current_price <= trigger_price
                if trigger == "stop"
                else current_price >= trigger_price
            )
        return (
            current_price >= trigger_price
            if trigger == "stop"
            else current_price <= trigger_price
        )

    @staticmethod
    def _calc_profit_pct(position: Position, current_price: float) -> float:
        if position.side == PositionSide.SHORT:
            return (position.entry_price - current_price) / position.entry_price
        return (current_price - position.entry_price) / position.entry_price

    @staticmethod
    def _calc_profit_amount(position: Position, current_price: float) -> float:
        if position.side == PositionSide.SHORT:
            return (position.entry_price - current_price) * position.quantity
        return (current_price - position.entry_price) * position.quantity

    def _create_exit_signal(
        self,
        *,
        position: Position,
        current_price: float,
        profit_pct: float,
        profit_amount: float,
        reason: ExitReason,
        priority: int,
        holding_minutes: int,
        metadata: dict[str, Any],
    ) -> ExitSignal:
        logger.info(
            "[%s] Exit signal: %s reason=%s price=%.2f pnl=%+.2f%%",
            self.name,
            position.code,
            reason.value,
            current_price,
            profit_pct * 100,
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
            timestamp=now_kst(),
            stage=PositionState.SURVIVAL.value,
            high_since_entry=position.highest_price,
            holding_minutes=holding_minutes,
            quantity=position.quantity,
            metadata=metadata,
        )
