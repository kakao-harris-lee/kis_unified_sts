"""Track A composed exit: ATR trailing + crash guard + catastrophic backstop + EOD.

Replaces ``setup_target_exit`` for futures Setup A/C.
Precedence: crash guard → catastrophic backstop → trail stop → EOD.
Long/short symmetric; all thresholds config-driven.

Crash guard (I1 follow-up)
--------------------------
Two complementary paths detect a crash:

1. **Single-tick fast path** (original): a single adverse tick ≥ ``crash_atr_mult × ATR``.
   Catches a sudden vertical spike within one scan interval (~0.5s).
2. **Rolling-window path** (I1 fix): the maximum adverse move within the last
   ``crash_window_seconds`` (default 60) is compared against the same threshold.
   Catches gradual 1-minute sell-offs that no single tick trips.

Either path fires the ``FORCE_CLOSE`` signal.  The price history is kept in
``position.metadata["crash_price_history"]`` (list of ``[iso_ts, price]`` pairs),
pruned to the rolling window each tick.
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from shared.config.mixins import ConfigMixin
from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol
from shared.strategy.market_data import get_price_from_snapshot, get_symbol_snapshot
from shared.strategy.market_time import effective_close_time, is_trading_day_kst, now_kst, to_kst

logger = logging.getLogger(__name__)

_CRASH_HISTORY_KEY = "crash_price_history"


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


def max_adverse_move_in_window(
    side: PositionSide,
    current_price: float,
    history: list[tuple[datetime, float]],
    window_seconds: float,
    current_ts: datetime,
) -> float:
    """Return the maximum adverse move within the rolling window.

    For LONG: the largest drop (oldest_price_in_window - current_price).
    For SHORT: the largest rise (current_price - oldest_price_in_window).

    Only prices whose timestamp falls within ``[current_ts - window_seconds, current_ts]``
    are considered.  ``current_price`` itself is always included as the latest point.

    Args:
        side: Position direction (LONG or SHORT).
        current_price: Latest price (most recent data point).
        history: List of ``(timestamp, price)`` pairs in any order.
        window_seconds: Rolling window width in seconds.
        current_ts: Timestamp of ``current_price`` (tz-aware KST preferred).

    Returns:
        Maximum adverse move in price units (≥ 0 when adverse, ≤ 0 when favorable).
    """
    from datetime import timedelta

    cutoff = current_ts - timedelta(seconds=window_seconds)
    in_window = [price for ts, price in history if ts >= cutoff]
    if not in_window:
        return 0.0

    if side == PositionSide.LONG:
        # Worst price in window is the highest (best) entry price; we moved adversely DOWN.
        peak = max(in_window)
        return peak - current_price
    else:
        # Worst price in window is the lowest (best) entry price; we moved adversely UP.
        trough = min(in_window)
        return current_price - trough


def catastrophic_stop_hit(side: PositionSide, entry_price: float, current_price: float, atr: float, catastrophic_atr_mult: float) -> bool:
    """True when loss from entry >= catastrophic_atr_mult*atr."""
    threshold = catastrophic_atr_mult * atr
    if side == PositionSide.LONG:
        return (entry_price - current_price) >= threshold
    return (current_price - entry_price) >= threshold


@dataclass
class TrackAExitConfig(ConfigMixin):
    trail_atr_mult: float = 1.5
    trail_activate_atr_mult: float = 2.0
    crash_atr_mult: float = 3.5
    crash_cooldown_minutes: int = 30
    crash_window_seconds: float = 60.0  # I1: rolling window for windowed crash detection
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
        assert self.crash_window_seconds > 0
        assert self.catastrophic_atr_mult > 0
        assert 0.0 < self.default_exit_confidence <= 1.0


class TrackAExit(ExitSignalGenerator[TrackAExitConfig]):
    """ATR trailing stop + crash guard + catastrophic backstop + EOD exit.

    Replaces ``setup_target_exit`` for futures Setup A/C.
    Precedence (highest priority first):
        1. crash guard  → FORCE_CLOSE
        2. catastrophic → STOP_LOSS
        3. trail stop   → TRAILING_STOP
        4. EOD          → EOD_CLOSE
    ATR is read from the live snapshot; falls back to ``position.metadata["entry_atr"]``.
    When ATR == 0 all ATR-based exits are skipped (only EOD can fire).
    ``prev_price`` is read from then written to ``position.metadata["prev_price"]`` each tick.
    """

    CONFIG_CLASS = TrackAExitConfig

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "track_a_exit"

    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        signal = self._check_position(context.position, context.market_data or {})
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

    def _update_crash_history(
        self, position: Position, current_price: float, now: Any
    ) -> list[tuple[datetime, float]]:
        """Append current_price to ``crash_price_history`` and prune to the rolling window.

        History is stored in ``position.metadata[_CRASH_HISTORY_KEY]`` as a list of
        ``[iso_timestamp, price]`` pairs (JSON-serialisable).  Returns the pruned
        history as a list of ``(datetime, float)`` tuples for immediate use.
        """
        from datetime import timedelta

        now_dt: datetime = to_kst(now)
        cutoff = now_dt - timedelta(seconds=self.config.crash_window_seconds)

        raw: list[list] = position.metadata.get(_CRASH_HISTORY_KEY, [])
        # Parse existing entries.
        parsed: list[tuple[datetime, float]] = []
        for entry in raw:
            try:
                ts_str, price = entry[0], float(entry[1])
                ts = datetime.fromisoformat(ts_str)
                if ts >= cutoff:
                    parsed.append((ts, price))
            except (IndexError, TypeError, ValueError):
                continue

        # Append current tick.
        parsed.append((now_dt, current_price))

        # Persist pruned list back to metadata.
        position.metadata[_CRASH_HISTORY_KEY] = [
            [ts.isoformat(), price] for ts, price in parsed
        ]
        return parsed

    def _check_position(self, position: Position, snapshot: dict[str, Any]) -> ExitSignal | None:
        current_price = get_price_from_snapshot(snapshot)
        if current_price is None:
            current_price = position.current_price if position.current_price > 0 else None
        if current_price is None or position.entry_price <= 0:
            return None

        now = now_kst()
        atr = self._get_atr(snapshot, position)
        prev_price = float(position.metadata.get("prev_price", current_price))
        profit_pct = self._calc_profit_pct(position, current_price)
        profit_amount = self._calc_profit_amount(position, current_price)
        holding_minutes = int((to_kst(now) - to_kst(position.entry_time)).total_seconds() / 60)
        favorable_extreme = (
            position.highest_price if position.side == PositionSide.LONG else position.lowest_price
        )

        # Update prev_price and rolling crash history each tick before any early return.
        position.metadata["prev_price"] = current_price
        crash_history = self._update_crash_history(position, current_price, now)

        # p1: crash guard — single-tick OR windowed adverse move >= crash_atr_mult * ATR
        if atr > 0:
            single_tick_crash = crash_triggered(
                position.side, current_price, prev_price, atr, self.config.crash_atr_mult
            )
            windowed_crash = (
                max_adverse_move_in_window(
                    side=position.side,
                    current_price=current_price,
                    history=crash_history,
                    window_seconds=self.config.crash_window_seconds,
                    current_ts=to_kst(now),
                )
                >= self.config.crash_atr_mult * atr
            )
            if single_tick_crash or windowed_crash:
                crash_path = "single_tick" if single_tick_crash else "windowed"
                return self._create_exit_signal(
                    position=position, current_price=current_price,
                    profit_pct=profit_pct, profit_amount=profit_amount,
                    reason=ExitReason.FORCE_CLOSE, priority=1,
                    holding_minutes=holding_minutes,
                    metadata={
                        "exit_type": "crash_guard",
                        "crash_path": crash_path,
                        "prev_price": prev_price,
                        "atr": atr,
                        "crash_cooldown_minutes": self.config.crash_cooldown_minutes,
                    },
                )

        # p2: catastrophic backstop — total loss from entry >= catastrophic_atr_mult * ATR
        if atr > 0 and catastrophic_stop_hit(
            position.side, position.entry_price, current_price, atr, self.config.catastrophic_atr_mult
        ):
            return self._create_exit_signal(
                position=position, current_price=current_price,
                profit_pct=profit_pct, profit_amount=profit_amount,
                reason=ExitReason.STOP_LOSS, priority=2,
                holding_minutes=holding_minutes,
                metadata={"exit_type": "catastrophic_stop", "atr": atr},
            )

        # p3: trailing stop — only after trail activation threshold is reached
        if atr > 0 and trail_activated(
            position.side, position.entry_price, favorable_extreme, atr, self.config.trail_activate_atr_mult
        ):
            trail = trail_stop_price(
                position.side, favorable_extreme, atr, self.config.trail_atr_mult
            )
            crossed = (
                current_price <= trail
                if position.side == PositionSide.LONG
                else current_price >= trail
            )
            if crossed:
                return self._create_exit_signal(
                    position=position, current_price=current_price,
                    profit_pct=profit_pct, profit_amount=profit_amount,
                    reason=ExitReason.TRAILING_STOP, priority=3,
                    holding_minutes=holding_minutes,
                    metadata={
                        "exit_type": "trail_stop",
                        "trail_price": trail,
                        "favorable_extreme": favorable_extreme,
                        "atr": atr,
                    },
                )

        # p4: EOD close
        if self._should_eod_close(now):
            return self._create_exit_signal(
                position=position, current_price=current_price,
                profit_pct=profit_pct, profit_amount=profit_amount,
                reason=ExitReason.EOD_CLOSE, priority=4,
                holding_minutes=holding_minutes,
                metadata={"exit_type": "eod_close"},
            )

        return None

    def _get_atr(self, snapshot: dict[str, Any], position: Position) -> float:
        """Snapshot ATR first; fall back to ``position.metadata["entry_atr"]``."""
        for key in ("atr", "atr_14", "atr14"):
            val = snapshot.get(key)
            if val is not None:
                try:
                    f = float(val)
                    if f > 0:
                        return f
                except (TypeError, ValueError):
                    pass
        entry_atr = position.metadata.get("entry_atr")
        if entry_atr is not None:
            try:
                f = float(entry_atr)
                if f > 0:
                    return f
            except (TypeError, ValueError):
                pass
        return 0.0

    def _should_eod_close(self, now: Any) -> bool:
        if not self.config.eod_close_enabled:
            return False
        now_local = to_kst(now)
        if not is_trading_day_kst(now_local):
            return False
        return now_local.time() >= effective_close_time(self.config.eod_close_time)

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
            "[%s] Exit: %s reason=%s price=%.2f pnl=%+.2f%%",
            self.name, position.code, reason.value, current_price, profit_pct * 100,
        )
        high_since_entry = (
            position.highest_price if position.side == PositionSide.LONG else position.lowest_price
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
            high_since_entry=high_since_entry,
            holding_minutes=holding_minutes,
            quantity=position.quantity,
            metadata=metadata,
        )
