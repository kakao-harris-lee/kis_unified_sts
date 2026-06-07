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
to KIS ``OrderType.MARKET`` (``ORD_DVSN_CD="01"``).

This adapter is unit-tested against AsyncMock dependencies; the live
integration test belongs in the 2-week paper gate (Task 20) — runtime KIS
behavior is impossible to fully cover in CI.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from shared.execution.models import OrderRequest, OrderSide, OrderType
from shared.execution.passive_maker import Fill

logger = logging.getLogger(__name__)


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
    fill: Fill | None  # None when the order missed (timeout/cancel)
    placed_at_ms: int


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
        order_id = response.order_no or ""

        if not response.success or response.filled_qty == 0:
            # Either the order was rejected outright OR the auto-cancel path
            # ran (timeout). PassiveMaker reads None from await_fill in both
            # cases and reports OrderResult.missed.
            self._fills[order_id] = _StashedFill(fill=None, placed_at_ms=placed_at_ms)
            return order_id

        fill = Fill(
            order_id=order_id,
            price=float(response.filled_price),
            quantity=int(response.filled_qty),
            filled_at_ms=int(time.time() * 1000),
        )
        self._fills[order_id] = _StashedFill(fill=fill, placed_at_ms=placed_at_ms)
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

    async def cancel_order(self, order_id: str) -> bool:
        """No-op when the executor already auto-cancelled on timeout.

        ``OrderExecutor._send_kis_futures_order`` cancels unfilled remainders
        itself when ``futures_auto_cancel_unfilled=true`` in execution.yaml.
        For completeness this method calls ``_cancel_futures_order`` again;
        the KIS API returns a "no such order" error which the executor
        already handles.
        """
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
