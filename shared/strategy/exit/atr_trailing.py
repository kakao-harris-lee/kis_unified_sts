"""ATR Trailing Stop Exit Strategy.

ATR 기반 트레일링 스탑 청산 전략.
선물 및 고빈도 트레이딩에 적합.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from shared.models.position import PositionState
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator
from shared.strategy.registry import ExitRegistry

if TYPE_CHECKING:
    from shared.models.position import Position

logger = logging.getLogger(__name__)


@dataclass
class ATRTrailingConfig:
    """ATR Trailing Stop 설정.

    Attributes:
        atr_multiplier: 트레일링 스탑 ATR 배수 (default: 2.0)
        initial_stop_atr: 초기 스탑 ATR 배수 (default: 1.5)
        max_hold_minutes: 최대 보유 시간(분) (default: 30)
        stop_loss_ticks: 고정 손절 틱 (default: 10)
        take_profit_ticks: 고정 익절 틱 (default: 20)
        tick_size: 틱 크기 (default: 0.05)
    """

    atr_multiplier: float = 2.0
    initial_stop_atr: float = 1.5
    max_hold_minutes: int = 30
    stop_loss_ticks: int = 10
    take_profit_ticks: int = 20
    tick_size: float = 0.05

    @classmethod
    def from_dict(cls, data: dict) -> "ATRTrailingConfig":
        """dict에서 설정 생성."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@ExitRegistry.register("atr_trailing")
class ATRTrailingExit(ExitSignalGenerator[ATRTrailingConfig]):
    """ATR 기반 트레일링 스탑 청산 전략.

    Features:
        - 시간 기반 청산 (max_hold_minutes)
        - 고정 손절/익절 (ticks 단위)
        - ATR 기반 트레일링 스탑

    Usage:
        exit_strategy = ATRTrailingExit(config)
        should_exit, reason = await exit_strategy.should_exit(context)
    """

    NAME = "ATR_TRAILING"
    VERSION = "1.0"
    CONFIG_CLASS = ATRTrailingConfig

    def __init__(self, config: ATRTrailingConfig | dict):
        if isinstance(config, dict):
            config = ATRTrailingConfig.from_dict(config)
        super().__init__(config)
        self._entry_times: dict[str, datetime] = {}
        self._trailing_stops: dict[str, float] = {}

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def version(self) -> str:
        return self.VERSION

    def _validate_config(self) -> None:
        """설정 유효성 검증."""
        c = self.config
        assert c.atr_multiplier > 0, "atr_multiplier must be positive"
        assert c.initial_stop_atr > 0, "initial_stop_atr must be positive"
        assert c.max_hold_minutes > 0, "max_hold_minutes must be positive"
        assert c.tick_size > 0, "tick_size must be positive"

    @property
    def required_indicators(self) -> list[str]:
        """필요한 지표 목록."""
        return ["atr"]

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, Optional[ExitSignal]]:
        """청산 여부 판단.

        Args:
            context: 청산 판단 컨텍스트

        Returns:
            (should_exit, signal) 튜플
        """
        position = context.position
        current_price = context.market_data.get("close", 0)
        atr = context.indicators.get("atr", 0)

        # 1. Time-based exit
        if position.id in self._entry_times:
            elapsed = context.timestamp - self._entry_times[position.id]
            hold_minutes = elapsed.total_seconds() / 60
            if hold_minutes >= self.config.max_hold_minutes:
                signal = self._create_exit_signal(
                    position, current_price, ExitReason.TIME_CUT
                )
                return True, signal

        # 2. Fixed stop loss (ticks)
        tick_pnl = self._calc_tick_pnl(position, current_price)
        if tick_pnl <= -self.config.stop_loss_ticks:
            signal = self._create_exit_signal(
                position, current_price, ExitReason.STOP_LOSS
            )
            return True, signal

        # 3. Fixed take profit (ticks)
        if tick_pnl >= self.config.take_profit_ticks:
            signal = self._create_exit_signal(
                position, current_price, ExitReason.TRAILING_STOP
            )
            return True, signal

        # 4. ATR trailing stop
        if atr > 0:
            if position.id not in self._trailing_stops:
                # Initialize trailing stop
                if position.side == "long":
                    self._trailing_stops[position.id] = (
                        position.entry_price - atr * self.config.initial_stop_atr
                    )
                else:
                    self._trailing_stops[position.id] = (
                        position.entry_price + atr * self.config.initial_stop_atr
                    )

            # Update trailing stop
            trailing_stop = self._trailing_stops[position.id]
            if position.side == "long":
                new_stop = current_price - atr * self.config.atr_multiplier
                if new_stop > trailing_stop:
                    self._trailing_stops[position.id] = new_stop
                    trailing_stop = new_stop

                if current_price <= trailing_stop:
                    signal = self._create_exit_signal(
                        position, current_price, ExitReason.TRAILING_STOP
                    )
                    return True, signal
            else:
                new_stop = current_price + atr * self.config.atr_multiplier
                if new_stop < trailing_stop:
                    self._trailing_stops[position.id] = new_stop
                    trailing_stop = new_stop

                if current_price >= trailing_stop:
                    signal = self._create_exit_signal(
                        position, current_price, ExitReason.TRAILING_STOP
                    )
                    return True, signal

        return False, None

    async def scan_positions(
        self,
        positions: list["Position"],
        market_data: dict[str, Any],
        market_state: Optional[Any] = None,
    ) -> list[ExitSignal]:
        """여러 포지션에 대해 청산 시그널 스캔.

        Args:
            positions: 현재 보유 포지션 리스트
            market_data: 시장 데이터
            market_state: 시장 상태 (사용 안 함)

        Returns:
            ExitSignal 리스트
        """
        signals = []
        for position in positions:
            context = ExitContext(
                position=position,
                market_data=market_data,
                indicators={},
                timestamp=datetime.now(),
                market_state=market_state,
            )
            should_exit, signal = await self.should_exit(context)
            if should_exit and signal:
                signals.append(signal)
        return signals

    def _calc_tick_pnl(self, position: "Position", current_price: float) -> float:
        """틱 단위 손익 계산."""
        if position.side == "long":
            return (current_price - position.entry_price) / self.config.tick_size
        return (position.entry_price - current_price) / self.config.tick_size

    def _create_exit_signal(
        self, position: "Position", current_price: float, reason: ExitReason
    ) -> ExitSignal:
        """청산 시그널 생성."""
        profit_pct = (current_price - position.entry_price) / position.entry_price
        profit_amount = (current_price - position.entry_price) * position.quantity

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
            confidence=0.9,
            priority=2,
            timestamp=datetime.now(),
            stage=PositionState.SURVIVAL.value,
            high_since_entry=position.highest_price or position.entry_price,
            holding_minutes=0,
            quantity=position.quantity,
        )

    def update_state(self, context: ExitContext) -> None:
        """상태 업데이트."""
        if context.position.id not in self._entry_times:
            self._entry_times[context.position.id] = context.timestamp

    def cleanup(self, position_id: str) -> None:
        """포지션 종료 시 상태 정리."""
        self._entry_times.pop(position_id, None)
        self._trailing_stops.pop(position_id, None)
