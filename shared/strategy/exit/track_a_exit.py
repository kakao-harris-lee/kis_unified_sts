"""Track A composed exit: ATR trailing + crash guard + catastrophic backstop + EOD.

Replaces ``setup_target_exit`` for futures Setup A/C.
Precedence: crash guard → catastrophic backstop → trail stop → EOD.
Long/short symmetric; all thresholds config-driven.
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
from shared.strategy.market_time import effective_close_time, is_trading_day_kst, now_kst, to_kst

logger = logging.getLogger(__name__)


def trail_stop_price(side: PositionSide, favorable_extreme: float, atr: float, trail_atr_mult: float) -> float:
    """LONG: extreme - mult*atr ; SHORT: extreme + mult*atr."""
    offset = trail_atr_mult * atr
    return favorable_extreme - offset if side == PositionSide.LONG else favorable_extreme + offset


def trail_activated(side: PositionSide, entry_price: float, favorable_extreme: float, atr: float, trail_activate_atr_mult: float) -> bool:
    """True when profit in ATR units >= trail_activate_atr_mult."""
    threshold = trail_activate_atr_mult * atr
    if side == PositionSide.LONG:
        return (favorable_extreme - entry_price) >= threshold
    return (entry_price - favorable_extreme) >= threshold


def crash_triggered(side: PositionSide, current_price: float, prev_price: float, atr: float, crash_atr_mult: float) -> bool:
    """True when a single adverse move >= crash_atr_mult*atr."""
    threshold = crash_atr_mult * atr
    if side == PositionSide.LONG:
        return (prev_price - current_price) >= threshold
    return (current_price - prev_price) >= threshold


def catastrophic_stop_hit(side: PositionSide, entry_price: float, current_price: float, atr: float, catastrophic_atr_mult: float) -> bool:
    """True when loss from entry >= catastrophic_atr_mult*atr."""
    threshold = catastrophic_atr_mult * atr
    if side == PositionSide.LONG:
        return (entry_price - current_price) >= threshold
    return (current_price - entry_price) >= threshold


@dataclass
class TrackAExitConfig(ConfigMixin):
    trail_atr_mult: float = 3.0
    trail_activate_atr_mult: float = 1.0
    crash_atr_mult: float = 3.5
    crash_cooldown_minutes: int = 30
    catastrophic_atr_mult: float = 6.0
    eod_close_enabled: bool = True
    eod_close_hour: int = 15
    eod_close_minute: int = 15
    default_exit_confidence: float = 0.9
    enabled: bool = True

    @property
    def eod_close_time(self) -> time:
        return time(self.eod_close_hour, self.eod_close_minute)

    def validate(self) -> None:
        assert self.trail_atr_mult > 0
        assert self.trail_activate_atr_mult >= 0
        assert self.crash_atr_mult > 0
        assert self.crash_cooldown_minutes >= 0
        assert self.catastrophic_atr_mult > 0
        assert 0.0 < self.default_exit_confidence <= 1.0


class TrackAExit(ExitSignalGenerator[TrackAExitConfig]):
    """Placeholder — full implementation in Task 2."""
    CONFIG_CLASS = TrackAExitConfig

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "track_a_exit"

    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        raise NotImplementedError

    async def scan_positions(self, positions: list[Position], market_data: dict[str, Any], market_state: MarketStateProtocol | None = None) -> list[ExitSignal]:
        raise NotImplementedError
