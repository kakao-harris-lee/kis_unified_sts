"""F-3: PaperKISFuturesAdapter — real orderbook, simulated passive fills, no real orders."""

from __future__ import annotations

import pytest

from shared.execution.paper_kis_futures_adapter import (
    PaperKISFuturesAdapter,
    _passive_filled,
)
from shared.execution.passive_maker import Fill


class _FakeFeed:
    def __init__(self, snapshot: dict, price: dict) -> None:
        self._snap = snapshot
        self._price = price

    async def get_current_price(self, symbol: str) -> dict:  # noqa: ARG002
        return dict(self._price)

    def get_orderbook_snapshot(self, symbol: str) -> dict:  # noqa: ARG002
        return dict(self._snap)


def test_passive_filled_long() -> None:
    assert _passive_filled("long", 100.0, 99.0, 100.0, 100.5) is True
    assert _passive_filled("long", 100.0, 101.0, 100.0, 100.0) is True
    assert _passive_filled("long", 100.0, 101.0, 100.0, 100.5) is False


def test_passive_filled_short() -> None:
    assert _passive_filled("short", 100.0, 101.0, 99.5, 100.0) is True
    assert _passive_filled("short", 100.0, 99.0, 100.0, 100.0) is True
    assert _passive_filled("short", 100.0, 99.0, 99.5, 100.0) is False


def test_passive_filled_none_inputs() -> None:
    assert _passive_filled("long", 100.0, None, None, None) is False


@pytest.mark.asyncio
async def test_get_futures_orderbook_delegates_to_feed() -> None:
    feed = _FakeFeed({"bid_price_1": 331.20, "ask_price_1": 331.22}, {"close": 331.21})
    adapter = PaperKISFuturesAdapter(futures_price_feed=feed)
    book = await adapter.get_futures_orderbook("A05603")
    assert book.bid[0].price == 331.20
    assert book.ask[0].price == 331.22


@pytest.mark.asyncio
async def test_get_futures_orderbook_empty_raises() -> None:
    adapter = PaperKISFuturesAdapter(futures_price_feed=_FakeFeed({}, {}))
    with pytest.raises(RuntimeError):
        await adapter.get_futures_orderbook("A05603")


@pytest.mark.asyncio
async def test_place_order_synthetic_id_no_real_call() -> None:
    adapter = PaperKISFuturesAdapter(
        futures_price_feed=_FakeFeed({"bid_price_1": 100.0, "ask_price_1": 100.5}, {})
    )
    oid = await adapter.place_futures_order(
        symbol="A05603", side="long", quantity=2, order_type="limit", price=100.0
    )
    assert oid.startswith("PAPER-")
    assert adapter._pending[oid].limit == 100.0
    assert adapter._pending[oid].quantity == 2


@pytest.mark.asyncio
async def test_await_fill_fills_at_limit_when_market_reaches() -> None:
    feed = _FakeFeed({"bid_price_1": 100.0, "ask_price_1": 100.5}, {"close": 99.0})
    adapter = PaperKISFuturesAdapter(futures_price_feed=feed, poll_interval=0.01)
    oid = await adapter.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=100.0
    )
    fill = await adapter.await_fill(oid, timeout_seconds=1)
    assert isinstance(fill, Fill)
    assert fill.price == 100.0
    assert fill.quantity == 1


@pytest.mark.asyncio
async def test_await_fill_misses_on_timeout() -> None:
    feed = _FakeFeed({"bid_price_1": 100.0, "ask_price_1": 100.5}, {"close": 101.0})
    adapter = PaperKISFuturesAdapter(futures_price_feed=feed, poll_interval=0.01)
    oid = await adapter.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=100.0
    )
    fill = await adapter.await_fill(oid, timeout_seconds=0.05)
    assert fill is None


@pytest.mark.asyncio
async def test_cancel_order_is_noop_true() -> None:
    adapter = PaperKISFuturesAdapter(
        futures_price_feed=_FakeFeed({"bid_price_1": 100.0, "ask_price_1": 100.5}, {})
    )
    oid = await adapter.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=100.0
    )
    assert await adapter.cancel_order(oid) is True
    assert oid not in adapter._pending
