"""Williams %R Exit Strategy.

Williams %R 과매수 반전 기반 청산 전략:
- Williams %R >= overbought_threshold 시 청산
- Hard stop, EOD, Time cut 안전장치

Exit Priority:
    1. Hard stop (STOP_LOSS): pnl < max_stop_loss_pct
    2. EOD close
    3. Time cut (TIME_CUT): N분 경과 + 수익 없음
    4. Williams %R overbought (INDICATOR_EXIT)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import time
from typing import Any, Optional

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
class WilliamsRExitConfig(ConfigMixin):
    """Williams %R Exit 설정"""

    # Williams %R indicator exit
    overbought_threshold: float = -20.0   # LONG position exits here
    oversold_exit_threshold: float = -80.0  # SHORT position exits here (mirror)

    # Hard stop
    max_stop_loss_pct: float = -0.03

    # Time cut
    time_cut_minutes: int = 120

    # EOD
    eod_close_hour: int = 15
    eod_close_minute: int = 15

    # Default confidence
    default_exit_confidence: float = 0.8

    @property
    def eod_close_time(self) -> time:
        return time(self.eod_close_hour, self.eod_close_minute)

    def validate(self):
        if self.max_stop_loss_pct >= 0:
            raise ValueError("max_stop_loss_pct must be negative")
        if self.time_cut_minutes <= 0:
            raise ValueError("time_cut_minutes must be positive")


class WilliamsRExit(ExitSignalGenerator[WilliamsRExitConfig]):
    """Williams %R 과매수 청산 전략.

    Exit conditions (priority order):
        1. Hard stop: pnl <= max_stop_loss_pct
        2. EOD close: 장 마감 시간
        3. Time cut: N분 초과 + 수익 없음
        4. Williams %R >= overbought_threshold
    """

    CONFIG_CLASS = WilliamsRExitConfig
    NAME = "WILLIAMS_R_EXIT"

    def __init__(self, config: WilliamsRExitConfig):
        super().__init__(config)

    def _validate_config(self):
        self.config.validate()

    @property
    def name(self) -> str:
        return "williams_r_exit"

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, Optional[ExitSignal]]:
        signal = self._check_position(context)
        return (signal is not None, signal)

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: Optional[MarketStateProtocol] = None,
    ) -> list[ExitSignal]:
        """Scan multiple positions for exit signals."""
        if not positions:
            return []

        signals = []
        now = now_kst()
        for position in positions:
            snapshot = get_symbol_snapshot(market_data, position.code)
            context = ExitContext(
                position=position,
                market_data=snapshot,
                indicators=snapshot,
                timestamp=now,
                market_state=market_state,
            )
            signal = self._check_position(context)
            if signal:
                signals.append(signal)

        if signals:
            logger.info(
                f"[{self.name}] {len(signals)}/{len(positions)} positions "
                f"triggered exit signals"
            )
        return signals

    def _check_position(self, context: ExitContext) -> Optional[ExitSignal]:
        """Check exit conditions for a single position."""
        position = context.position
        market_data = context.market_data
        indicators = context.indicators or {}
        now = context.timestamp
        is_backtest = context.metadata.get("is_backtest", False)

        current_price = self._get_current_price(position, market_data)
        if current_price is None:
            return None

        profit_pct = self._calc_profit_pct(position, current_price)
        profit_amount = self._calc_profit_amount(position, current_price)
        holding_minutes = int(
            (to_kst(now) - to_kst(position.entry_time)).total_seconds() / 60
        )
        high_since_entry = self._get_extreme_since_entry(position, current_price)

        # 1. Hard stop
        if profit_pct <= self.config.max_stop_loss_pct:
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.STOP_LOSS,
                priority=1,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
            )

        # 2. EOD close
        if not is_backtest:
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

        # 3. Time cut (no profit after N minutes)
        if (
            holding_minutes >= self.config.time_cut_minutes
            and profit_pct <= 0
        ):
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.TIME_CUT,
                priority=2,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
            )

        # 4. Williams %R indicator exit — direction-aware.
        #    LONG  position exits on overbought (%R >= overbought_threshold).
        #    SHORT position exits on oversold  (%R <= oversold_exit_threshold).
        #    P&L helpers already handle SHORT; only the indicator trigger was
        #    LONG-only before, leaving SHORT positions without an indicator exit.
        momentum = indicators.get("momentum_5m", {})
        if isinstance(momentum, dict):
            williams_r = momentum.get("williams_r")
        else:
            williams_r = indicators.get("williams_r")

        if williams_r is not None:
            wr = float(williams_r)
            if position.side == PositionSide.SHORT:
                indicator_hit = wr <= self.config.oversold_exit_threshold
            else:
                indicator_hit = wr >= self.config.overbought_threshold
            if indicator_hit:
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.INDICATOR_EXIT,
                    priority=3,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                    metadata={"williams_r": wr},
                )

        return None

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_current_price(
        position: Position, market_data: dict[str, Any]
    ) -> Optional[float]:
        snapshot = get_symbol_snapshot(market_data, position.code)
        price = get_price_from_snapshot(snapshot)
        if price is not None:
            return price
        if position.current_price > 0:
            return position.current_price
        return None

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

    @staticmethod
    def _get_extreme_since_entry(position: Position, current_price: float) -> float:
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
            f"Reason: {reason.value} | P/L: {profit_pct:+.2%}"
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
            stage=PositionState.SURVIVAL,
            high_since_entry=high_since_entry,
            holding_minutes=holding_minutes,
            quantity=position.quantity,
            metadata=metadata or {},
        )
