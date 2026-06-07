"""F-6: LiveExitExecutor — real market flatten, guard-blocked."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from shared.execution.live_exit_executor import LiveExitExecutor
from shared.execution.passive_maker import Fill


@pytest.mark.asyncio
async def test_flatten_places_market_order_when_not_suspended():
    kis = AsyncMock()
    kis.place_futures_order.return_value = "EXIT-1"
    kis.await_fill.return_value = Fill(
        order_id="EXIT-1", price=329.5, quantity=1, filled_at_ms=2000
    )
    guard = AsyncMock()
    guard.is_live_suspended.return_value = False
    ex = LiveExitExecutor(kis_client=kis, live_mode_guard=guard, redis=AsyncMock())
    fill = await ex.flatten(
        symbol="A05603", side="short", quantity=1, requested_price=330.0, now_ms=2000
    )
    assert fill is not None and fill.price == 329.5
    assert kis.place_futures_order.await_args.kwargs["order_type"] == "market"
    assert kis.place_futures_order.await_args.kwargs["side"] == "short"
    assert kis.place_futures_order.await_args.kwargs["price"] is None


@pytest.mark.asyncio
async def test_flatten_blocked_when_suspended_places_no_order():
    kis = AsyncMock()
    guard = AsyncMock()
    guard.is_live_suspended.return_value = True
    ex = LiveExitExecutor(kis_client=kis, live_mode_guard=guard, redis=AsyncMock())
    fill = await ex.flatten(
        symbol="A05603", side="short", quantity=1, requested_price=330.0, now_ms=2000
    )
    assert fill is None
    kis.place_futures_order.assert_not_awaited()  # guard-blocked → no real order


@pytest.mark.asyncio
async def test_flatten_returns_none_when_unfilled():
    kis = AsyncMock()
    kis.place_futures_order.return_value = "EXIT-1"
    kis.await_fill.return_value = None  # not filled within timeout
    guard = AsyncMock()
    guard.is_live_suspended.return_value = False
    ex = LiveExitExecutor(kis_client=kis, live_mode_guard=guard, redis=AsyncMock())
    fill = await ex.flatten(
        symbol="A05603", side="short", quantity=1, requested_price=330.0, now_ms=2000
    )
    assert fill is None
