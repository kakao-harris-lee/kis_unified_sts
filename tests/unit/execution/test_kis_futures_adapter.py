"""Tests for shared/execution/kis_futures_adapter.py — Phase 4 Task 17."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.execution.kis_futures_adapter import KISFuturesAdapter
from shared.execution.models import OrderResponse
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
        return_value=OrderResponse(
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
    executor._send_kis_futures_order.return_value = OrderResponse(
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
    executor._send_kis_futures_order.return_value = OrderResponse(
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


# ---------------------------------------------------------------------------
# wave-3b D-8 — fill stash key collision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejected_orders_do_not_share_one_stash_slot(executor, feed):
    """Two rejected orders carry no ODNO; keying on "" made them collide.

    The second rejection used to overwrite the first, so ``await_fill`` for the
    first order answered with the second order's stash.
    """
    executor._send_kis_futures_order.return_value = OrderResponse(
        success=False,
        order_no=None,
        filled_qty=0,
        filled_price=0.0,
        message="rejected",
    )
    a = KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)

    first = await a.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=331.20
    )
    second = await a.place_futures_order(
        symbol="A05603", side="short", quantity=2, order_type="limit", price=331.40
    )

    assert first != second
    assert len(a._fills) == 2


@pytest.mark.asyncio
async def test_filled_orders_still_key_on_the_broker_order_number(executor, feed):
    """Negative control: a real ODNO is used verbatim, not synthesized."""
    a = KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)

    order_id = await a.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=331.20
    )

    assert order_id == "ORD-1"
    fill = await a.await_fill(order_id, timeout_seconds=30)
    assert isinstance(fill, Fill)


@pytest.mark.asyncio
async def test_synthesized_id_is_never_sent_to_the_broker(executor, feed):
    """A local id must not reach ORGN_ODNO on the cancel wire."""
    executor._send_kis_futures_order.return_value = OrderResponse(
        success=False,
        order_no=None,
        filled_qty=0,
        filled_price=0.0,
        message="rejected",
    )
    a = KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)

    order_id = await a.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=331.20
    )

    assert await a.cancel_order(order_id) is True
    executor._cancel_futures_order.assert_not_awaited()


# ---------------------------------------------------------------------------
# Review attempt-1 #1 / #2 — the D-2 failure mode must not survive the adapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_fill_on_rejected_cancel_reaches_await_fill(executor, feed):
    """A partial fill is a LIVE position and must not be dropped as a miss.

    The executor reports success=False for a partial (the order did not
    complete). Guarding the stash on `success` therefore threw away a real
    position — the D-2 failure verbatim, partial instead of full: PassiveMaker
    reports `missed` and PseudoOCO never arms a protective exit.
    """
    executor._send_kis_futures_order.return_value = OrderResponse(
        success=False,
        order_no="ORD-PARTIAL",
        filled_qty=1,
        filled_price=331.20,
        message="Futures fill timeout and cancel failed: 취소할 수량이 없습니다",
    )
    a = KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)

    order_id = await a.place_futures_order(
        symbol="A05603", side="long", quantity=3, order_type="limit", price=331.20
    )

    fill = await a.await_fill(order_id, timeout_seconds=30)
    assert isinstance(fill, Fill)
    assert fill.quantity == 1
    assert fill.price == 331.20
    assert a.fill_state_unknown(order_id) is False


@pytest.mark.asyncio
async def test_zero_quantity_success_is_still_a_miss(executor, feed):
    """Negative control: the guard is on quantity, and zero is still a miss."""
    executor._send_kis_futures_order.return_value = OrderResponse(
        success=True, order_no="ORD-ZERO", filled_qty=0, filled_price=0.0, message="ok"
    )
    a = KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)

    order_id = await a.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=331.20
    )

    assert await a.await_fill(order_id, timeout_seconds=30) is None


@pytest.mark.asyncio
async def test_unknown_fill_state_is_escalated_and_distinguishable(
    executor, feed, caplog
):
    """`fill_state_unknown` must be consumed, not just produced."""
    executor._send_kis_futures_order.return_value = OrderResponse(
        success=False,
        order_no="ORD-UNKNOWN",
        filled_qty=0,
        filled_price=0.0,
        message="Futures fill timeout and cancel failed: 초당 거래건수 초과",
        fill_state_unknown=True,
    )
    a = KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)

    with caplog.at_level(logging.ERROR, logger="shared.execution.kis_futures_adapter"):
        order_id = await a.place_futures_order(
            symbol="A05603", side="long", quantity=1, order_type="limit", price=331.20
        )

    assert await a.await_fill(order_id, timeout_seconds=30) is None
    # ...but it is NOT an ordinary miss.
    assert a.fill_state_unknown(order_id) is True
    assert any("fill state UNKNOWN" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_ordinary_miss_is_not_flagged_unknown(executor, feed):
    """Negative control: a plain unfilled order stays an ordinary miss."""
    executor._send_kis_futures_order.return_value = OrderResponse(
        success=False,
        order_no="ORD-MISS",
        filled_qty=0,
        filled_price=0.0,
        message="Futures unfilled order cancelled",
    )
    a = KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)

    order_id = await a.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=331.20
    )

    assert await a.await_fill(order_id, timeout_seconds=30) is None
    assert a.fill_state_unknown(order_id) is False


@pytest.mark.asyncio
async def test_unknown_id_does_not_manufacture_alarm(adapter):
    assert adapter.fill_state_unknown("never-placed") is False


@pytest.mark.asyncio
async def test_positive_quantity_without_a_price_is_not_fabricated_into_a_fill(
    executor, feed, caplog
):
    """A qty>0 with price 0 is not a measurement; do not seed a bracket with it."""
    executor._send_kis_futures_order.return_value = OrderResponse(
        success=False,
        order_no="ORD-NOPRICE",
        filled_qty=2,
        filled_price=0.0,
        message="partial with no price",
    )
    a = KISFuturesAdapter(order_executor=executor, futures_price_feed=feed)

    with caplog.at_level(logging.ERROR, logger="shared.execution.kis_futures_adapter"):
        order_id = await a.place_futures_order(
            symbol="A05603", side="long", quantity=3, order_type="limit", price=331.20
        )

    assert await a.await_fill(order_id, timeout_seconds=30) is None
    assert a.fill_state_unknown(order_id) is True
    assert any("non-positive price" in r.getMessage() for r in caplog.records)
