"""KIS futures adapter for PassiveMaker — Phase 4 Task 17.

Bridges the duck-typed interface that
:class:`shared.execution.passive_maker.PassiveMaker` expects (``get_futures_orderbook``,
``place_futures_order``, ``await_fill``, ``cancel_order``) onto the production
:class:`OrderExecutor` (REST orders) + :class:`FuturesPriceFeed` (WebSocket
orderbook snapshots).

The existing ``OrderExecutor._send_kis_futures_order`` performs place + await
+ auto-cancel as a single call, returning a :class:`OrderResponse`. PassiveMaker
splits these into separate calls. The adapter stashes the awaited result by
``order_id`` so ``await_fill`` returns the same fill in O(1).

Force-close flows that need true market orders go through the same
``place_futures_order`` path with ``order_type="market"`` — the adapter maps
to :class:`OrderType.MARKET`, whose internal value is ``"01"`` in the *stock*
code system; ``OrderExecutor`` then translates that to futures
``ORD_DVSN_CD="02"`` (시장가). Do not read the internal ``"01"`` as a futures
wire code — futures ``ORD_DVSN_CD="01"`` means 지정가 (limit), the exact
inversion that ``executor._map_futures_order_type`` exists to keep separated.

This adapter is unit-tested against AsyncMock dependencies; the live
integration test belongs in the 2-week paper gate (Task 20) — runtime KIS
behavior is impossible to fully cover in CI.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from shared.execution.models import OrderRequest, OrderSide, OrderType
from shared.execution.passive_maker import Fill

logger = logging.getLogger(__name__)

#: Prefix for locally-synthesized ids used when the broker accepted no order
#: number. Purely internal to this adapter — never sent on the wire.
_UNIDENTIFIED_ORDER_PREFIX = "NO-ODNO-"


def _side_to_kis(side: str) -> OrderSide:
    """Map PassiveMaker side ('long'/'short') to KIS OrderSide.

    'long' = BUY (entry) or BUY-to-cover (close-short). 'short' = SELL.
    Closing direction semantics already handled at the caller (PassiveMaker
    passes signal.direction; ForceCloseExecutor passes _opposite()).
    """
    if side == "long":
        return OrderSide.BUY
    if side == "short":
        return OrderSide.SELL
    raise ValueError(f"unknown side: {side!r}")


def _order_type_to_kis(order_type: str) -> OrderType:
    if order_type in ("limit", "limit_passive"):
        return OrderType.LIMIT
    if order_type == "market":
        return OrderType.MARKET
    raise ValueError(f"unknown order_type: {order_type!r}")


@dataclass
class _StashedFill:
    fill: Fill | None  # None when nothing executed (timeout/cancel/reject)
    placed_at_ms: int
    #: True when the executed quantity could not be established. A stash with
    #: ``fill=None`` AND this set is NOT a flat book — it is an unresolved
    #: position. Read it through :meth:`KISFuturesAdapter.fill_state_unknown`.
    fill_state_unknown: bool = False


class KISFuturesAdapter:
    """Translate PassiveMaker's duck-typed surface to the live KIS executor."""

    def __init__(
        self,
        *,
        order_executor: Any,  # OrderExecutor — duck-typed for testability
        futures_price_feed: Any,  # FuturesPriceFeed (WS-driven snapshots)
    ) -> None:
        self.executor = order_executor
        self.feed = futures_price_feed
        self._fills: dict[str, _StashedFill] = {}

    async def get_futures_orderbook(self, symbol: str) -> Any:
        """Return an object with ``.bid[0].price`` / ``.ask[0].price``.

        Reads the latest WebSocket snapshot from
        :class:`FuturesPriceFeed.get_orderbook_snapshot`. Returns
        :exc:`RuntimeError` when the snapshot is empty so callers can decide
        whether to retry or skip the signal — passive maker treats it as
        "passive_not_filled" naturally because the place_futures_order will
        also fail downstream.
        """
        snap = self.feed.get_orderbook_snapshot(symbol)
        if not snap:
            raise RuntimeError(f"no orderbook snapshot for {symbol}")
        bid = float(snap["bid_price_1"])
        ask = float(snap["ask_price_1"])
        return SimpleNamespace(
            bid=[SimpleNamespace(price=bid)],
            ask=[SimpleNamespace(price=ask)],
        )

    async def place_futures_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        price: float | None,
    ) -> str:
        """Place via OrderExecutor, stash the awaited fill, return order_id.

        ``OrderExecutor._send_kis_futures_order`` performs place + await +
        auto-cancel in one call. We stash the result so ``await_fill`` is a
        cheap dict lookup.
        """
        request = OrderRequest(
            code=symbol,
            side=_side_to_kis(side),
            order_type=_order_type_to_kis(order_type),
            quantity=quantity,
            price=price,
        )
        placed_at_ms = int(time.time() * 1000)
        # _send_kis_futures_order returns an OrderResponse — defer to its
        # return shape rather than assuming the executor's internals.
        response = await self.executor._send_kis_futures_order(
            request, is_mock=self.executor.config.trading_mode != "REAL"
        )
        # A rejected order carries no broker order number. Keying the stash on
        # "" made every such order share one slot, so a second rejection
        # overwrote the first and `await_fill` answered the wrong caller.
        # Synthesize a unique local id instead — it is never sent to the broker,
        # it only has to be unique within this adapter.
        order_id = response.order_no or (
            f"{_UNIDENTIFIED_ORDER_PREFIX}{uuid.uuid4().hex}"
        )

        unknown = response.fill_state_unknown is True
        if unknown:
            # The executor could not establish what executed. This is NOT an
            # ordinary miss: a position may be open at the broker right now.
            # Reporting it as `missed` is exactly the D-2 failure — the caller
            # would treat the book as flat and never arm a protective exit.
            logger.error(
                "fill state UNKNOWN for %s %s x%s (order_id=%s, broker=%s): the "
                "broker may hold a position with no protective exit. Reconcile "
                "against the broker before trading this symbol again.",
                side,
                symbol,
                quantity,
                order_id,
                response.message,
            )

        filled_qty = int(response.filled_qty)
        filled_price = float(response.filled_price)
        if filled_qty > 0 and filled_price <= 0.0:
            # A positive quantity with no price is not a measurement; building
            # a Fill from it would seed slippage and the protective bracket
            # with a fabricated 0. Escalate instead of inventing a price.
            logger.error(
                "fill reported qty=%s with non-positive price=%s (order_id=%s) "
                "— treating fill state as unknown rather than fabricating a "
                "price for the protective bracket",
                filled_qty,
                filled_price,
                order_id,
            )
            unknown = True
            filled_qty = 0

        if filled_qty <= 0:
            # No executed quantity: rejected outright, or the auto-cancel path
            # ran and nothing filled. PassiveMaker reads None from await_fill.
            # NOTE the guard is on QUANTITY, not on `success`: the executor
            # reports success=False for a PARTIAL fill (the order did not
            # complete), and a partial fill is still a live position that must
            # reach PseudoOCO.
            self._fills[order_id] = _StashedFill(
                fill=None, placed_at_ms=placed_at_ms, fill_state_unknown=unknown
            )
            return order_id

        fill = Fill(
            order_id=order_id,
            price=filled_price,
            quantity=filled_qty,
            filled_at_ms=int(time.time() * 1000),
        )
        self._fills[order_id] = _StashedFill(
            fill=fill, placed_at_ms=placed_at_ms, fill_state_unknown=unknown
        )
        return order_id

    async def await_fill(
        self,
        order_id: str,
        timeout_seconds: float,  # noqa: ARG002 — honored by executor internally
    ) -> Fill | None:
        """Return the stashed fill (or None if missed). ``timeout_seconds``
        is honored by ``_send_kis_futures_order`` itself; this method is
        synchronous in practice.
        """
        stash = self._fills.get(order_id)
        if stash is None:
            logger.warning("await_fill: no stash for order_id=%s", order_id)
            return None
        return stash.fill

    def fill_state_unknown(self, order_id: str) -> bool:
        """True when this order's executed quantity could not be established.

        ``await_fill`` returning ``None`` is ambiguous on its own: it means
        either "nothing executed" or "we could not find out". Callers that
        would otherwise treat ``None`` as a flat book MUST consult this before
        doing so — an unresolved order may be an open position with no
        protective exit.

        Unknown ids answer ``False``: absence of a stash is not evidence of an
        unresolved fill, and this must not manufacture alarm for an order this
        adapter never placed.
        """
        stash = self._fills.get(order_id)
        if stash is None:
            return False
        return stash.fill_state_unknown

    async def cancel_order(self, order_id: str) -> bool:
        """No-op when the executor already auto-cancelled on timeout.

        ``OrderExecutor._send_kis_futures_order`` cancels unfilled remainders
        itself when ``futures_auto_cancel_unfilled=true`` in execution.yaml.
        For completeness this method calls ``_cancel_futures_order`` again;
        the KIS API returns a "no such order" error which the executor
        already handles.
        """
        if order_id.startswith(_UNIDENTIFIED_ORDER_PREFIX):
            # Locally-synthesized id: the broker never accepted this order, so
            # there is nothing to cancel and the id must not reach the wire.
            logger.debug("cancel_order: no broker order number for %s", order_id)
            return True
        try:
            await self.executor._cancel_futures_order(
                order_no=order_id,
                cancel_quantity=0,  # 0 = cancel all remaining
                is_mock=self.executor.config.trading_mode != "REAL",
                is_night=False,
            )
            return True
        except Exception:
            logger.exception("cancel_order failed order_id=%s", order_id)
            return False
