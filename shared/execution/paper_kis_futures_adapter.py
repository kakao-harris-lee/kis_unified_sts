"""Paper (simulated) KIS futures adapter for the order_router (F-3).

A drop-in for the duck-typed ``kis_client`` interface PassiveMaker uses
(``get_futures_orderbook`` / ``place_futures_order`` / ``await_fill`` /
``cancel_order``). Reads the REAL orderbook from the live futures feed but
simulates passive-limit fills locally — NO real KIS order is ever placed.
Enables paper validation of the decoupled futures execution path with real
market data (KIS 모의투자 does not serve a futures realtime feed).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from shared.execution.passive_maker import Fill

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _PaperOrder:
    symbol: str
    side: str
    limit: float
    quantity: int


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _passive_filled(
    side: str,
    limit: float,
    last_trade: float | None,
    best_bid: float | None,
    best_ask: float | None,
) -> bool:
    """True if a passive limit at ``limit`` would fill given the market state.

    long (resting at best bid): fills when the market trades down to the bid
    (a trade prints <= limit) or the ask crosses to <= limit. short (resting at
    best ask): fills when a trade prints >= limit or the bid crosses >= limit.
    """
    if side == "long":
        return (last_trade is not None and last_trade <= limit) or (
            best_ask is not None and best_ask <= limit
        )
    return (last_trade is not None and last_trade >= limit) or (
        best_bid is not None and best_bid >= limit
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


class PaperKISFuturesAdapter:
    """Simulated futures kis_client: real orderbook in, simulated fills, no orders."""

    def __init__(self, *, futures_price_feed: Any, poll_interval: float = 0.2) -> None:
        self.feed = futures_price_feed
        self._poll_interval = poll_interval
        self._pending: dict[str, _PaperOrder] = {}

    async def get_futures_orderbook(self, symbol: str) -> Any:
        snap = self.feed.get_orderbook_snapshot(symbol)
        if not snap:
            raise RuntimeError(f"no orderbook snapshot for {symbol}")
        return SimpleNamespace(
            bid=[SimpleNamespace(price=float(snap["bid_price_1"]))],
            ask=[SimpleNamespace(price=float(snap["ask_price_1"]))],
        )

    async def place_futures_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,  # noqa: ARG002 — part of duck-typed kis_client interface
        price: float | None,
    ) -> str:
        order_id = f"PAPER-{uuid4().hex[:12]}"
        self._pending[order_id] = _PaperOrder(
            symbol=symbol,
            side=side,
            limit=float(price or 0.0),
            quantity=int(quantity),
        )
        return order_id

    async def await_fill(self, order_id: str, timeout_seconds: int) -> Fill | None:
        order = self._pending.get(order_id)
        if order is None:
            logger.warning("paper await_fill: no pending order %s", order_id)
            return None
        deadline = time.monotonic() + float(timeout_seconds)
        while time.monotonic() < deadline:
            price = await self.feed.get_current_price(order.symbol)
            snap = self.feed.get_orderbook_snapshot(order.symbol) or {}
            last_trade = _to_float((price or {}).get("close"))
            best_bid = _to_float(snap.get("bid_price_1"))
            best_ask = _to_float(snap.get("ask_price_1"))
            if _passive_filled(order.side, order.limit, last_trade, best_bid, best_ask):
                return Fill(
                    order_id=order_id,
                    price=order.limit,
                    quantity=order.quantity,
                    filled_at_ms=_now_ms(),
                )
            await asyncio.sleep(self._poll_interval)
        logger.info("paper await_fill: %s timed out (passive miss)", order_id)
        return None

    async def cancel_order(self, order_id: str) -> bool:
        self._pending.pop(order_id, None)
        return True
