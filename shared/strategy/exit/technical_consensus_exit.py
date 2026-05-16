"""Exit strategy driven by RSI/Williams %R/MACD consensus."""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from datetime import time
from typing import Any

from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol
from shared.strategy.market_data import get_price_from_snapshot, get_symbol_snapshot
from shared.strategy.market_time import (
    effective_close_time,
    is_trading_day_kst,
    now_kst,
    to_kst,
)
from shared.strategy.technical_consensus import (
    TechnicalConsensusConfig,
    build_technical_consensus,
)

logger = logging.getLogger(__name__)


@dataclass
class TechnicalConsensusExitConfig:
    """Config for a stock swing exit based on technical vote overlap."""

    min_exit_votes: int = 2
    min_entry_votes: int = 2
    min_exit_core_votes: int = 2
    min_entry_core_votes: int = 2

    rsi_oversold: float = 35.0
    rsi_recovery: float = 40.0
    rsi_overbought: float = 70.0
    rsi_rollover: float = 60.0

    williams_oversold: float = -80.0
    williams_reversal: float = -65.0
    williams_overbought: float = -20.0
    williams_exit: float = -35.0

    macd_hist_threshold: float = 0.0
    include_trend_vote: bool = True
    trend_buffer_pct: float = 0.0
    include_volume_vote: bool = False
    min_volume_ratio: float = 1.2
    exit_retrace_from_high_pct: float = 0.03

    hard_stop_pct: float = -0.07
    time_cut_minutes: int = 0
    eod_close_enabled: bool = False
    eod_close_hour: int = 15
    eod_close_minute: int = 15
    default_exit_confidence: float = 0.85

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None
    ) -> TechnicalConsensusExitConfig:
        if not data:
            return cls()
        if isinstance(data.get("params"), dict):
            data = data["params"]
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        config = cls(**filtered)
        config.validate()
        return config

    @property
    def eod_close_time(self) -> time:
        return time(self.eod_close_hour, self.eod_close_minute)

    def validate(self) -> None:
        if self.hard_stop_pct >= 0:
            raise ValueError("hard_stop_pct must be negative")
        if self.time_cut_minutes < 0:
            raise ValueError("time_cut_minutes must be non-negative")
        if not 0 < self.default_exit_confidence <= 1:
            raise ValueError("default_exit_confidence must be in (0, 1]")
        self.to_consensus_config().validate()

    def to_consensus_config(self) -> TechnicalConsensusConfig:
        values = {
            field.name: getattr(self, field.name)
            for field in dataclasses.fields(TechnicalConsensusConfig)
            if hasattr(self, field.name)
        }
        return TechnicalConsensusConfig(**values)


class TechnicalConsensusExit(ExitSignalGenerator[TechnicalConsensusExitConfig]):
    """Signal-based stock swing exit using overlapping indicator votes."""

    CONFIG_CLASS = TechnicalConsensusExitConfig

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "technical_consensus_exit"

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, ExitSignal | None]:
        signal = self._check_position(context)
        return signal is not None, signal

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
    ) -> list[ExitSignal]:
        if not positions:
            return []

        signals: list[ExitSignal] = []
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
            if signal is not None:
                signals.append(signal)
        return signals

    def _check_position(self, context: ExitContext) -> ExitSignal | None:
        position = context.position
        market_data = context.market_data or {}
        indicators = context.indicators or {}
        now = context.timestamp
        current_price = self._get_current_price(position, market_data)
        if current_price is None:
            return None

        profit_pct = self._calc_profit_pct(position, current_price)
        profit_amount = self._calc_profit_amount(position, current_price)
        holding_minutes = int(
            (to_kst(now) - to_kst(position.entry_time)).total_seconds() / 60
        )
        high_since_entry = self._get_high_since_entry(position, current_price)

        if profit_pct <= self.config.hard_stop_pct:
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.STOP_LOSS,
                priority=1,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
                metadata={"stop_type": "technical_consensus_hard_stop"},
            )

        if self.config.eod_close_enabled and not context.metadata.get(
            "is_backtest", False
        ):
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
                    metadata={"exit_type": "technical_consensus_eod"},
                )

        if (
            self.config.time_cut_minutes > 0
            and holding_minutes >= self.config.time_cut_minutes
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
                metadata={"exit_type": "technical_consensus_time_cut"},
            )

        snapshot = {
            **market_data,
            **indicators,
            "close": current_price,
            "high_since_entry": high_since_entry,
        }
        consensus = build_technical_consensus(
            snapshot,
            position=position,
            config=self.config.to_consensus_config(),
        )
        if consensus.exit_signal:
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.INDICATOR_EXIT,
                priority=3,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
                metadata={"technical_consensus": consensus.to_dict()},
            )

        return None

    @staticmethod
    def _get_current_price(
        position: Position, market_data: dict[str, Any]
    ) -> float | None:
        snapshot = get_symbol_snapshot(market_data, position.code)
        price = get_price_from_snapshot(snapshot)
        if price is not None:
            return price
        price = get_price_from_snapshot(market_data)
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
    def _get_high_since_entry(position: Position, current_price: float) -> float:
        if position.side == PositionSide.SHORT:
            return min(position.lowest_price, current_price)
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
        consensus_meta = (metadata or {}).get("technical_consensus", {})
        extra_votes = max(
            0,
            int(consensus_meta.get("exit_vote_count", self.config.min_exit_votes))
            - self.config.min_exit_votes,
        )
        confidence = min(
            0.95,
            self.config.default_exit_confidence + (extra_votes * 0.05),
        )

        logger.info(
            "[%s] Exit signal: %s | reason=%s | pnl=%+.2f%%",
            self.name,
            position.code,
            reason.value,
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
            confidence=confidence,
            priority=priority,
            timestamp=now_kst(),
            stage=position.state.value,
            high_since_entry=high_since_entry,
            holding_minutes=holding_minutes,
            quantity=position.quantity,
            metadata=metadata or {},
        )
