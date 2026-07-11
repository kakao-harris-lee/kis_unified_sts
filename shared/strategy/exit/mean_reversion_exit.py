"""Mean Reversion Exit Strategy.

MR 이론에 맞는 청산 전략:
- Primary target: BB middle band (20-SMA) 도달 시 청산
- Hard stop: Entry - N × ATR (동적 손절, cap 적용)
- Time cut: N분 내 미회복 시 청산
- BEAR exit: 시장 레짐 하락 전환 시 즉시 청산

Exit Priority:
    1. Hard stop (ATR-based, capped at max_stop_loss_pct)
    2. EOD close
    3. BEAR market regime → 즉시 청산
    4. Time cut (120분 초과)
    5. BB middle band 도달 → 청산 (primary target)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import time
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason, ExitSignal
from shared.risk.primitives import (
    extreme_since_entry,
    normalize_atr,
    profit_amount,
    profit_pct,
)
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol
from shared.strategy.market_classifier import is_bear_regime
from shared.strategy.market_data import get_price_from_snapshot, get_symbol_snapshot
from shared.strategy.market_time import (
    effective_close_time,
    is_trading_day_kst,
    now_kst,
    to_kst,
)

logger = logging.getLogger(__name__)


@dataclass
class MeanReversionExitConfig(ConfigMixin):
    """Mean Reversion Exit 설정"""

    # Hard stop (ATR-based)
    atr_stop_multiplier: float = 2.0  # Entry - 2.0×ATR
    max_stop_loss_pct: float = -0.03  # ATR stop cap (최대 -3%)

    # Primary target: BB middle band
    target_bb_middle: bool = True

    # Time cut
    time_cut_minutes: int = 120  # 2시간 내 미회복 → 청산

    # EOD
    eod_close_hour: int = 15
    eod_close_minute: int = 15

    # BEAR exit
    enable_bear_exit: bool = True

    # Fee
    fee_rate: float = 0.003  # 0.3%

    @property
    def eod_close_time(self) -> time:
        return time(self.eod_close_hour, self.eod_close_minute)

    def validate(self):
        if self.max_stop_loss_pct >= 0:
            raise ValueError("max_stop_loss_pct must be negative")
        if self.atr_stop_multiplier <= 0:
            raise ValueError("atr_stop_multiplier must be positive")
        if self.time_cut_minutes <= 0:
            raise ValueError("time_cut_minutes must be positive")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MeanReversionExitConfig:
        if "params" in data:
            data = data["params"]
        return cls(
            atr_stop_multiplier=data.get("atr_stop_multiplier", 2.0),
            max_stop_loss_pct=data.get("max_stop_loss_pct", -0.03),
            target_bb_middle=data.get("target_bb_middle", True),
            time_cut_minutes=data.get("time_cut_minutes", 120),
            eod_close_hour=data.get("eod_close_hour", 15),
            eod_close_minute=data.get("eod_close_minute", 15),
            enable_bear_exit=data.get("enable_bear_exit", True),
            fee_rate=data.get("fee_rate", 0.003),
        )


class MeanReversionExit(ExitSignalGenerator[MeanReversionExitConfig]):
    """Mean Reversion 전용 청산 전략.

    BB middle band를 primary target으로 사용하고,
    ATR 기반 동적 손절을 적용하는 MR 전용 청산 전략.
    """

    CONFIG_CLASS = MeanReversionExitConfig
    NAME = "MEAN_REVERSION_EXIT"

    def __init__(self, config: MeanReversionExitConfig):
        super().__init__(config)

    def _validate_config(self):
        self.config.validate()

    @property
    def name(self) -> str:
        return "mean_reversion_exit"

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, ExitSignal | None]:
        signal = self._check_position(context)
        return (signal is not None, signal)

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
    ) -> list[ExitSignal]:
        """여러 포지션에 대해 청산 시그널 스캔."""
        if not positions:
            return []

        signals = []
        now = now_kst()
        for position in positions:
            # Extract per-symbol snapshot (contains merged indicators from orchestrator)
            snapshot = get_symbol_snapshot(market_data, position.code)
            context = ExitContext(
                position=position,
                market_data=snapshot,
                indicators=snapshot,  # orchestrator merges indicators into snapshot
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

    def _check_position(self, context: ExitContext) -> ExitSignal | None:
        """개별 포지션 청산 조건 체크.

        Priority:
            1. Hard stop (ATR-based)
            2. EOD close
            3. BEAR market exit
            4. Time cut
            5. BB middle target reached
        """
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

        # 1. Hard stop (ATR-based, capped)
        atr = self._get_atr(indicators, market_data)
        stop_pct = self.config.max_stop_loss_pct  # default cap
        if atr > 0 and position.entry_price > 0:
            atr_stop_pct = -(atr * self.config.atr_stop_multiplier) / position.entry_price
            # Use ATR-derived stop, but cap at max_stop_loss_pct
            stop_pct = max(atr_stop_pct, self.config.max_stop_loss_pct)

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
                metadata={"stop_type": "atr", "stop_pct": stop_pct},
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

        # 3. BEAR market exit
        if self.config.enable_bear_exit and self._is_bear_market(context.market_state):
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.BEAR_EXIT,
                priority=1,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
            )

        # 4. Time cut (profit 없이 시간 초과)
        if (
            holding_minutes >= self.config.time_cut_minutes
            and profit_pct <= self.config.fee_rate
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

        # 5. BB middle band target reached
        if self.config.target_bb_middle:
            bb_middle = float(
                indicators.get("bb_middle", 0)
                or market_data.get("bb_middle", 0)
                or 0
            )
            if bb_middle > 0 and position.side == PositionSide.LONG:
                if current_price >= bb_middle:
                    return self._create_exit_signal(
                        position=position,
                        current_price=current_price,
                        profit_pct=profit_pct,
                        profit_amount=profit_amount,
                        reason=ExitReason.TARGET_REACHED,
                        priority=3,
                        high_since_entry=high_since_entry,
                        holding_minutes=holding_minutes,
                        metadata={"target": "bb_middle", "bb_middle": bb_middle},
                    )

        return None

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_atr(indicators: dict[str, Any], market_data: dict[str, Any]) -> float:
        """Get ATR value from indicators or market data.

        ATR can be either normalized (ratio) or absolute.
        If normalized (< 0.5), convert back using close price via the
        ``normalize_atr`` risk primitive.
        """
        atr = float(indicators.get("atr", 0) or 0)
        if atr <= 0:
            atr = float(market_data.get("atr", 0) or 0)
        if atr <= 0:
            return 0.0

        # Dict extraction / key fallback (atr, close) stays at this call site;
        # the normalized-ratio arithmetic lives in the ``normalize_atr``
        # primitive (threshold 0.5, reference == close).
        close = float(market_data.get("close", 0) or indicators.get("close", 0) or 0)
        return normalize_atr(atr, close, normalized_below=0.5)

    @staticmethod
    def _get_current_price(
        position: Position, market_data: dict[str, Any]
    ) -> float | None:
        snapshot = get_symbol_snapshot(market_data, position.code)
        price = get_price_from_snapshot(snapshot)
        if price is not None:
            return price
        if position.current_price > 0:
            return position.current_price
        return None

    @staticmethod
    def _calc_profit_pct(position: Position, current_price: float) -> float:
        return profit_pct(position, current_price)

    @staticmethod
    def _calc_profit_amount(position: Position, current_price: float) -> float:
        return profit_amount(position, current_price)

    @staticmethod
    def _get_extreme_since_entry(position: Position, current_price: float) -> float:
        return extreme_since_entry(position, current_price)

    @staticmethod
    def _is_bear_market(market_state: MarketStateProtocol | None) -> bool:
        """BEAR 시장 여부 체크 (단일 소스: market_classifier.BEAR_REGIMES)"""
        if market_state is None:
            return False
        return is_bear_regime(market_state.regime)

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
            confidence=0.8 if reason == ExitReason.TARGET_REACHED else 0.9,
            priority=priority,
            timestamp=now,
            stage=PositionState.SURVIVAL,
            high_since_entry=high_since_entry,
            holding_minutes=holding_minutes,
            quantity=position.quantity,
            metadata=metadata or {},
        )
