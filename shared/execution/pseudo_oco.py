"""Client-side pseudo-OCO bracket for paper futures.

Phase 4 Task 7 — KIS server-side OCO is restricted, so we simulate brackets
in-process: register a stop + target after entry fills, watch incoming
ticks, and on either trigger close the position via :class:`FillLogger`
and mark the other side cancelled.

The ``register_bracket → on_tick → check_expiry`` interface is synchronous
in flow (each method awaits only the FillLogger I/O). The asyncio task
orchestration that wires this to a live price feed lives in the
``order_router`` daemon (Task 12); driving ``on_tick`` directly from tests
keeps this module easy to verify deterministically.

Spec §4.2 — "loss wins on ties": when a single bar straddles both stop and
target, the stop has priority. Implemented by checking the stop trigger
first inside :meth:`on_tick`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from shared.decision.signal import Signal
from shared.execution.fill_logger import FillLogger
from shared.execution.passive_maker import Fill

if TYPE_CHECKING:
    from shared.risk.runtime_state import RuntimeRiskState

logger = logging.getLogger(__name__)


class OCOState(str, Enum):
    ACTIVE = "active"
    STOP_HIT = "stop_hit"
    TARGET_HIT = "target_hit"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class OCOHandle:
    handle_id: str
    signal_id: str
    symbol: str
    direction: str  # entry direction: "long" | "short"
    quantity: int
    stop_price: float
    target_price: float
    valid_until_ms: int | None
    tick_size_points: float = 0.0  # for slippage logging; harness can ignore
    state: OCOState = OCOState.ACTIVE
    entry_filled_at_ms: int = field(default=0)
    entry_price: float = 0.0


def _opposite(direction: str) -> str:
    return "short" if direction == "long" else "long"


def _is_stop_hit(handle: OCOHandle, price: float) -> bool:
    if handle.direction == "long":
        return price <= handle.stop_price
    return price >= handle.stop_price


def _is_target_hit(handle: OCOHandle, price: float) -> bool:
    if handle.direction == "long":
        return price >= handle.target_price
    return price <= handle.target_price


class PseudoOCO:
    """Track stop+target brackets for paper futures, log fills on trigger."""

    def __init__(
        self,
        *,
        fill_logger: FillLogger,
        venue: str = "KRX",
        runtime_state: RuntimeRiskState | None = None,
        multiplier_krw_per_point: float = 0.0,
        close_executor: Any = None,
    ) -> None:
        self.fill_logger = fill_logger
        self.venue = venue
        self._runtime_state = runtime_state
        self._multiplier = multiplier_krw_per_point
        self._close_executor = close_executor
        self._handles: dict[str, OCOHandle] = {}
        self._next_id: int = 1

    async def register_bracket(
        self,
        *,
        signal: Signal,
        signal_id: str,
        fill: Fill,
        tick_size_points: float = 0.0,
    ) -> OCOHandle:
        valid_until_ms = (
            int(signal.valid_until.timestamp() * 1000)
            if signal.valid_until is not None
            else None
        )
        handle = OCOHandle(
            handle_id=f"OCO-{self._next_id}",
            signal_id=signal_id,
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=fill.quantity,
            entry_price=fill.price,
            stop_price=signal.stop_loss,
            target_price=signal.take_profit,
            valid_until_ms=valid_until_ms,
            tick_size_points=tick_size_points,
            entry_filled_at_ms=fill.filled_at_ms,
        )
        self._next_id += 1
        self._handles[handle.handle_id] = handle
        return handle

    def cancel(self, handle_id: str) -> bool:
        h = self._handles.pop(handle_id, None)
        if h is None:
            return False
        h.state = OCOState.CANCELLED
        return True

    async def on_tick(
        self, *, symbol: str, price: float, now_ms: int
    ) -> list[OCOHandle]:
        fired: list[OCOHandle] = []
        for handle_id in list(self._handles.keys()):
            handle = self._handles[handle_id]
            if handle.symbol != symbol or handle.state is not OCOState.ACTIVE:
                continue
            # Loss-wins: stop checked before target.
            if _is_stop_hit(handle, price):
                closed = await self._close(
                    handle,
                    fill_price=handle.stop_price,
                    now_ms=now_ms,
                    trade_role="stop_loss",
                    order_type="stop",
                    new_state=OCOState.STOP_HIT,
                )
            elif _is_target_hit(handle, price):
                closed = await self._close(
                    handle,
                    fill_price=handle.target_price,
                    now_ms=now_ms,
                    trade_role="take_profit",
                    order_type="limit_passive",
                    new_state=OCOState.TARGET_HIT,
                )
            else:
                continue
            if closed:
                fired.append(handle)
                del self._handles[handle_id]
        return fired

    async def check_expiry(
        self, *, now_ms: int, market_price: float | None = None
    ) -> list[OCOHandle]:
        """Force-close any handles whose ``valid_until_ms`` has elapsed.

        Args:
            now_ms: Current epoch ms.
            market_price: Real-time market quote at expiry. The order_router
                daemon (Task 12) supplies this from its live feed; tests can
                pass it explicitly. If ``None``, the bracket's target_price
                is used as a fallback — only valid for harness scenarios that
                don't care about the audit price.
        """
        expired: list[OCOHandle] = []
        for handle_id in list(self._handles.keys()):
            handle = self._handles[handle_id]
            if handle.state is not OCOState.ACTIVE:
                continue
            if handle.valid_until_ms is not None and now_ms >= handle.valid_until_ms:
                fill_price = (
                    market_price if market_price is not None else handle.target_price
                )
                if await self._close(
                    handle,
                    fill_price=fill_price,
                    now_ms=now_ms,
                    trade_role="force_close",
                    order_type="market",
                    new_state=OCOState.EXPIRED,
                ):
                    expired.append(handle)
                    del self._handles[handle_id]
        return expired

    async def _close(
        self,
        handle: OCOHandle,
        *,
        fill_price: float,
        now_ms: int,
        trade_role: str,
        order_type: str,
        new_state: OCOState,
    ) -> bool:
        """Close a handle. Returns True if closed, False if blocked (retry).

        Paper (no close_executor): synthesize a fill at ``fill_price``.
        Live (close_executor set): place a real order; None return = guard-
        blocked/unfilled → leave the handle ACTIVE for the next poll.
        """
        if self._close_executor is not None:
            real_fill = await self._close_executor.flatten(
                symbol=handle.symbol,
                side=_opposite(handle.direction),
                quantity=handle.quantity,
                requested_price=fill_price,
                now_ms=now_ms,
            )
            if real_fill is None:
                logger.warning(
                    "live exit not placed handle=%s role=%s; will retry",
                    handle.handle_id,
                    trade_role,
                )
                return False
            actual_price = float(real_fill.price)
        else:
            actual_price = fill_price
        # State transition before the log I/O: a re-raised log_fill failure must
        # not leave the handle ACTIVE for a duplicate fire (see PR #134 note).
        handle.state = new_state
        try:
            await self.fill_logger.log_fill(
                signal_id=handle.signal_id,
                order_id=f"{handle.handle_id}-{trade_role}",
                symbol=handle.symbol,
                side=_opposite(handle.direction),
                order_type=order_type,
                requested_price=fill_price,
                filled_price=actual_price,
                tick_size_points=handle.tick_size_points,
                slippage_ticks=0.0,
                quantity=handle.quantity,
                requested_at_ms=now_ms,
                filled_at_ms=now_ms,
                venue=self.venue,
                trade_role=trade_role,
            )
            await self._record_pnl(handle, exit_price=actual_price)
        except Exception:
            if self._close_executor is not None:
                # The real exit order already FILLED — the position is flat.
                # Losing the fill log / PnL must NOT cause a second real flatten
                # on the next poll, so treat the handle as closed (return True →
                # caller deletes it) and scream for manual reconciliation.
                logger.critical(
                    "RECONCILIATION GAP: real exit %s filled @%.4f (role=%s) but "
                    "fill-log/PnL failed; position IS flat — reconcile manually",
                    handle.handle_id,
                    actual_price,
                    trade_role,
                )
                return True
            # Paper (no real order placed): preserve the redelivery invariant.
            raise
        return True

    async def _record_pnl(self, handle: OCOHandle, *, exit_price: float) -> None:
        if self._runtime_state is None or self._multiplier <= 0.0:
            return
        sign = 1.0 if handle.direction == "long" else -1.0
        pnl = (
            (exit_price - handle.entry_price)
            * sign
            * handle.quantity
            * self._multiplier
        )
        await self._runtime_state.record_trade(pnl_krw=pnl)
        if pnl < 0:
            await self._runtime_state.record_loss()
        else:
            await self._runtime_state.record_win()

    @property
    def active_handles(self) -> list[OCOHandle]:
        return [h for h in self._handles.values() if h.state is OCOState.ACTIVE]
