"""Passive-maker order placement for futures.

Phase 4 Task 5 — implements ``place_passive_limit_futures()`` per spec §3.2.

The execution policy is fixed: every entry order is a limit posted at the
current best bid (long) or best ask (short), then we wait up to
``timeout_seconds`` for it to fill. No chasing — if it does not fill, we
cancel and report ``OrderResult.missed``. The caller (order_router daemon,
Task 12) is then free to drop the signal or schedule a force-close path.

Market orders are intentionally not in scope here; they live in
``shared/execution/force_close.py`` (Task 8) under the three whitelisted
conditions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from shared.decision.signal import Signal
from shared.execution.contract_spec import ContractSpec
from shared.execution.fill_logger import FillLogger
from shared.execution.order_result import OrderResult
from shared.execution.tick_math import _compute_slippage_ticks, _round_to_tick


@dataclass(frozen=True, slots=True)
class Fill:
    """Result of a successful order fill returned by ``kis_client.await_fill``.

    Decoupled from the broader :class:`shared.execution.models.OrderResponse`
    so passive_maker / pseudo_oco can share a minimal contract that
    :class:`OrderResult` consumes via duck-typing on ``.price`` / ``.order_id``.
    """

    order_id: str
    price: float
    quantity: int
    filled_at_ms: int


def _now_ms() -> int:
    return int(time.time() * 1000)


class PassiveMaker:
    """Place a passive limit order, wait for fill, log slippage.

    Args:
        kis_client: Async client exposing ``get_futures_orderbook``,
            ``place_futures_order``, ``await_fill``, ``cancel_order``. Tests
            inject :class:`unittest.mock.AsyncMock`; production wiring is in
            Task 17.
        fill_logger: :class:`FillLogger` instance — every fill records to the
            ``stream:order.fill`` audit trail and ``kospi.order_fills``.
    """

    def __init__(
        self,
        *,
        kis_client: Any,
        fill_logger: FillLogger,
        venue: str = "KRX",
    ) -> None:
        self.kis = kis_client
        self.fill_logger = fill_logger
        self.venue = venue

    async def place_passive_limit_futures(
        self,
        *,
        signal: Signal,
        signal_id: str,
        quantity: int,
        spec: ContractSpec,
        timeout_seconds: int = 30,
    ) -> OrderResult:
        orderbook = await self.kis.get_futures_orderbook(signal.symbol)
        raw_price = (
            orderbook.bid[0].price
            if signal.direction == "long"
            else orderbook.ask[0].price
        )
        limit_price = _round_to_tick(raw_price, spec.tick_size_points)

        requested_at_ms = _now_ms()
        order_id = await self.kis.place_futures_order(
            symbol=signal.symbol,
            side=signal.direction,
            quantity=quantity,
            order_type="limit",
            price=limit_price,
        )

        fill = await self.kis.await_fill(order_id, timeout_seconds)
        if fill is None:
            await self.kis.cancel_order(order_id)
            return OrderResult.missed(reason="passive_not_filled", order_id=order_id)

        slippage_ticks = _compute_slippage_ticks(
            requested=limit_price,
            filled=fill.price,
            direction=signal.direction,
            tick_size=spec.tick_size_points,
        )
        await self.fill_logger.log_fill(
            signal_id=signal_id,
            order_id=order_id,
            symbol=signal.symbol,
            side=signal.direction,
            order_type="limit_passive",
            requested_price=limit_price,
            filled_price=fill.price,
            tick_size_points=spec.tick_size_points,
            slippage_ticks=slippage_ticks,
            quantity=quantity,
            requested_at_ms=requested_at_ms,
            filled_at_ms=fill.filled_at_ms,
            venue=self.venue,
            trade_role="entry",
        )
        return OrderResult.filled(fill, slippage_ticks=slippage_ticks)
