"""CTA daily/swing exit: ATR chandelier trail + momentum-flip + time cap + backstop.

Daily-cadence exit for the :class:`CTAMomentumEntry` swing strategy. Holds across
days and only flattens on one of:

Precedence (highest priority first):
  1. **catastrophic backstop** — loss from entry >= ``catastrophic_atr_mult × ATR``
     (``STOP_LOSS``). A hard floor so a gap-through never compounds.
  2. **ATR chandelier trail** — exit LONG when ``close < highest_close − k×ATR``
     (symmetric for SHORT), once profit has reached the activation threshold
     (``TRAILING_STOP``). This is the primary profit-locking exit.
  3. **momentum flip** — the entry's own roll-aware TS-momentum sign reverses
     against the position (``STRATEGY_EXIT``). Regime is gone; stand aside.
  4. **time cap** — holding exceeds ``max_holding_days`` trading days
     (``TIME_CUT``). Bounds risk in a flat, signal-less drift.

Long/short symmetric; all thresholds config-driven. ATR and the trailing
favorable-extreme are read from the live snapshot / position state; the daily
close series for the momentum-flip check is read off the snapshot
(``daily_closes`` / ``daily_dates``), matching the entry's self-contained,
roll-aware contract. There is NO blanket EOD liquidation — this is a swing exit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol
from shared.strategy.entry.cta_momentum import roll_aware_log_returns
from shared.strategy.market_data import get_price_from_snapshot, get_symbol_snapshot
from shared.strategy.market_time import now_kst, to_kst

logger = logging.getLogger(__name__)


def chandelier_stop(
    side: PositionSide, favorable_extreme: float, atr: float, trail_atr_mult: float
) -> float:
    """LONG: extreme - mult*atr ; SHORT: extreme + mult*atr."""
    offset = trail_atr_mult * atr
    if side == PositionSide.LONG:
        return favorable_extreme - offset
    return favorable_extreme + offset


def trail_activated(
    side: PositionSide,
    entry_price: float,
    favorable_extreme: float,
    atr: float,
    activate_atr_mult: float,
) -> bool:
    """True when realised favorable excursion in ATR units >= activate_atr_mult."""
    threshold = activate_atr_mult * atr
    if side == PositionSide.LONG:
        return (favorable_extreme - entry_price) >= threshold
    return (entry_price - favorable_extreme) >= threshold


def catastrophic_hit(
    side: PositionSide,
    entry_price: float,
    current_price: float,
    atr: float,
    catastrophic_atr_mult: float,
) -> bool:
    """True when loss from entry >= catastrophic_atr_mult*atr."""
    threshold = catastrophic_atr_mult * atr
    if side == PositionSide.LONG:
        return (entry_price - current_price) >= threshold
    return (current_price - entry_price) >= threshold


@dataclass
class CTAMomentumExitConfig(ConfigMixin):
    """CTA daily swing exit settings. All thresholds config-driven."""

    # ATR chandelier trailing stop (primary profit-locking exit).
    trail_atr_mult: float = 4.0
    trail_activate_atr_mult: float = 1.0

    # Hard catastrophic backstop from entry.
    catastrophic_atr_mult: float = 5.0

    # Momentum-flip exit: re-evaluate the entry's roll-aware TS-momentum sign.
    use_momentum_flip: bool = True
    momentum_lookback: int = 60
    momentum_flip_deadband: float = 0.0

    # Time cap in trading days (bounds a flat, signal-less drift).
    max_holding_days: int = 60

    # Snapshot keys for the daily close/date series used by the flip check.
    close_series_key: str = "daily_closes"
    date_series_key: str = "daily_dates"

    default_exit_confidence: float = 0.85
    enabled: bool = True

    def validate(self) -> None:
        if self.trail_atr_mult <= 0:
            raise ValueError("trail_atr_mult must be positive")
        if self.trail_activate_atr_mult < 0:
            raise ValueError("trail_activate_atr_mult must be non-negative")
        if self.catastrophic_atr_mult <= 0:
            raise ValueError("catastrophic_atr_mult must be positive")
        if self.use_momentum_flip and self.momentum_lookback <= 0:
            raise ValueError("momentum_lookback must be positive")
        if self.momentum_flip_deadband < 0:
            raise ValueError("momentum_flip_deadband must be non-negative")
        if self.max_holding_days <= 0:
            raise ValueError("max_holding_days must be positive")
        if not (0.0 < self.default_exit_confidence <= 1.0):
            raise ValueError("default_exit_confidence must be in (0, 1]")


class CTAMomentumExit(ExitSignalGenerator[CTAMomentumExitConfig]):
    """Daily ATR-trail + momentum-flip + time-cap + catastrophic exit."""

    CONFIG_CLASS = CTAMomentumExitConfig

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "cta_momentum_exit"

    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        signal = self._check_position(
            context.position, context.market_data or {}, context.timestamp
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
            signal = self._check_position(position, snapshot, None)
            if signal is not None:
                signals.append(signal)
        return signals

    # -- core -------------------------------------------------------------

    def _check_position(
        self,
        position: Position,
        snapshot: dict[str, Any],
        bar_ts: datetime | None,
    ) -> ExitSignal | None:
        if not self.config.enabled:
            return None

        current_price = get_price_from_snapshot(snapshot)
        if current_price is None:
            current_price = (
                position.current_price if position.current_price > 0 else None
            )
        if current_price is None or position.entry_price <= 0:
            return None

        atr = self._get_atr(snapshot, position)
        side = position.side
        favorable_extreme = (
            position.highest_price
            if side == PositionSide.LONG
            else position.lowest_price
        )
        if favorable_extreme <= 0:
            favorable_extreme = position.entry_price

        # 1. Catastrophic backstop (hard floor).
        if atr > 0 and catastrophic_hit(
            side,
            position.entry_price,
            current_price,
            atr,
            self.config.catastrophic_atr_mult,
        ):
            return self._build(
                position, current_price, ExitReason.STOP_LOSS, priority=1
            )

        # 2. ATR chandelier trailing stop (once activated).
        if atr > 0 and trail_activated(
            side,
            position.entry_price,
            favorable_extreme,
            atr,
            self.config.trail_activate_atr_mult,
        ):
            stop = chandelier_stop(
                side, favorable_extreme, atr, self.config.trail_atr_mult
            )
            if (side == PositionSide.LONG and current_price <= stop) or (
                side == PositionSide.SHORT and current_price >= stop
            ):
                return self._build(
                    position, current_price, ExitReason.TRAILING_STOP, priority=2
                )

        # 3. Momentum-flip exit.
        if self.config.use_momentum_flip and self._momentum_flipped(side, snapshot):
            return self._build(
                position, current_price, ExitReason.STRATEGY_EXIT, priority=3
            )

        # 4. Time cap (trading days since entry).
        if self._holding_days(position, bar_ts) >= self.config.max_holding_days:
            return self._build(position, current_price, ExitReason.TIME_CUT, priority=4)

        return None

    def _momentum_flipped(self, side: PositionSide, snapshot: dict[str, Any]) -> bool:
        """True when roll-aware TS-momentum sign reverses against the position."""
        from shared.strategy.entry.cta_momentum import _as_dates, _as_floats

        closes = _as_floats(snapshot.get(self.config.close_series_key))
        dates = _as_dates(snapshot.get(self.config.date_series_key))
        if closes is None or dates is None:
            return False
        lb = self.config.momentum_lookback
        if len(closes) < lb + 1 or len(dates) != len(closes):
            return False
        rets = roll_aware_log_returns(closes, dates)
        mom = sum(rets[-lb:])
        if abs(mom) <= self.config.momentum_flip_deadband:
            return False
        mom_dir = PositionSide.LONG if mom > 0 else PositionSide.SHORT
        return mom_dir != side

    def _holding_days(self, position: Position, bar_ts: datetime | None) -> int:
        """Calendar-day span since entry (proxy for trading days held)."""
        ref = to_kst(bar_ts) if bar_ts is not None else to_kst(now_kst())
        entry = to_kst(position.entry_time)
        return max(0, (ref.date() - entry.date()).days)

    def _get_atr(self, snapshot: dict[str, Any], position: Position) -> float:
        """ATR from the live snapshot, falling back to entry-time ATR."""
        for key in ("atr", "atr_daily", "atr_value"):
            val = snapshot.get(key)
            if val is not None:
                try:
                    atr = float(val)
                    if atr > 0:
                        return atr
                except (TypeError, ValueError):
                    pass
        try:
            return max(0.0, float(position.metadata.get("entry_atr", 0.0) or 0.0))
        except (TypeError, ValueError):
            return 0.0

    def _build(
        self,
        position: Position,
        current_price: float,
        reason: ExitReason,
        *,
        priority: int,
    ) -> ExitSignal:
        if position.side == PositionSide.LONG:
            profit_pct = (current_price - position.entry_price) / position.entry_price
        else:
            profit_pct = (position.entry_price - current_price) / position.entry_price
        return ExitSignal(
            code=position.code,
            name=position.name,
            position_id=position.id,
            reason=reason,
            strategy=self.name,
            current_price=current_price,
            exit_price=current_price,
            entry_price=position.entry_price,
            profit_pct=profit_pct,
            confidence=self.config.default_exit_confidence,
            priority=priority,
            quantity=position.quantity,
            high_since_entry=position.highest_price,
        )
