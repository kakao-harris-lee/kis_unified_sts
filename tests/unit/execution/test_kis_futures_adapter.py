"""Tests for shared/execution/kis_futures_adapter.py — Phase 4 Task 17."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.execution.kis_futures_adapter import KISFuturesAdapter
from shared.execution.passive_maker import Fill


@pytest.fixture
def feed():
    f = MagicMock()
    f.get_orderbook_snapshot.return_value = {
        "code": "A05603",
        "bid_price_1": 331.20,
        "bid_qty_1": 100.0,
        "ask_price_1": 331.22,
        "ask_qty_1": 80.0,
    }
    return f


@pytest.fixture
def executor():
    e = AsyncMock()
    e.config = SimpleNamespace(trading_mode="MOCK")
    e._send_kis_futures_order = AsyncMock(
        return_value=SimpleNamespace(
            success=True,
            order_no="ORD-1",
            filled_qty=1,
            filled_price=331.20,
            message="filled",
        )
    )
    e._cancel_futures_order = AsyncMock(return_value=SimpleNamespace(success=True))
    return e


@pytest.fixture
def adapter(executor, feed):
    return KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)


@pytest.mark.asyncio
async def test_orderbook_returns_bid_ask_namespace(adapter):
    ob = await adapter.get_futures_orderbook("A05603")
    assert ob.bid[0].price == 331.20
    assert ob.ask[0].price == 331.22


@pytest.mark.asyncio
async def test_orderbook_raises_on_empty_snapshot(adapter, feed):
    feed.get_orderbook_snapshot.return_value = {}
    with pytest.raises(RuntimeError, match="no orderbook"):
        await adapter.get_futures_orderbook("A05603")


@pytest.mark.asyncio
async def test_place_long_limit_stashes_fill(adapter, executor):
    order_id = await adapter.place_futures_order(
        symbol="A05603",
        side="long",
        quantity=1,
        order_type="limit",
        price=331.20,
    )
    assert order_id == "ORD-1"
    executor._send_kis_futures_order.assert_awaited_once()
    request = executor._send_kis_futures_order.call_args.args[0]
    assert request.code == "A05603"
    assert request.side == "BUY"
    assert request.order_type == "00"  # LIMIT
    assert request.price == 331.20

    fill = await adapter.await_fill("ORD-1", timeout_seconds=30)
    assert isinstance(fill, Fill)
    assert fill.price == 331.20
    assert fill.quantity == 1
    assert fill.order_id == "ORD-1"


@pytest.mark.asyncio
async def test_place_short_market_uses_sell_market(adapter, executor):
    await adapter.place_futures_order(
        symbol="A05603",
        side="short",
        quantity=1,
        order_type="market",
        price=None,
    )
    request = executor._send_kis_futures_order.call_args.args[0]
    assert request.side == "SELL"
    assert request.order_type == "01"  # MARKET


@pytest.mark.asyncio
async def test_unfilled_response_stashes_none(executor, feed):
    executor._send_kis_futures_order.return_value = SimpleNamespace(
        success=False,
        order_no="ORD-MISS",
        filled_qty=0,
        filled_price=0.0,
        message="passive_not_filled",
    )
    a = KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)
    await a.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=331.20
    )
    fill = await a.await_fill("ORD-MISS", timeout_seconds=30)
    assert fill is None


@pytest.mark.asyncio
async def test_partial_fill_qty_zero_treated_as_miss(executor, feed):
    executor._send_kis_futures_order.return_value = SimpleNamespace(
        success=True, order_no="ORD-2", filled_qty=0, filled_price=0.0, message="ok"
    )
    a = KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)
    await a.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=331.20
    )
    assert await a.await_fill("ORD-2", timeout_seconds=30) is None


@pytest.mark.asyncio
async def test_cancel_order_calls_executor(adapter, executor):
    result = await adapter.cancel_order("ORD-1")
    assert result is True
    executor._cancel_futures_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_order_returns_false_on_exception(adapter, executor):
    executor._cancel_futures_order.side_effect = RuntimeError("KIS down")
    assert await adapter.cancel_order("ORD-1") is False


@pytest.mark.asyncio
async def test_await_fill_unknown_id_returns_none(adapter):
    fill = await adapter.await_fill("never-placed", timeout_seconds=30)
    assert fill is None


@pytest.mark.asyncio
async def test_unknown_side_raises(adapter):
    with pytest.raises(ValueError, match="unknown side"):
        await adapter.place_futures_order(
            symbol="A05603",
            side="sideways",
            quantity=1,
            order_type="limit",
            price=331.20,
        )
