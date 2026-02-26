"""Tests for futures WebSocket feed cache behavior."""

import pytest

from shared.collector.models import TickData
from shared.kis.auth import KISAuthConfig
from shared.kis.futures_feed import KISFuturesPriceFeed


def _make_feed() -> KISFuturesPriceFeed:
    return KISFuturesPriceFeed(config=KISAuthConfig(app_key="k", app_secret="s", is_real=True))


def test_update_symbols_with_auxiliary_symbol():
    feed = _make_feed()
    feed.update_symbols(["A05603"], auxiliary_symbols=["101S6000"])
    assert feed.symbol_count == 2
    assert "A05603" in feed._symbols
    assert "101S6000" in feed._symbols


@pytest.mark.asyncio
async def test_orderbook_and_trade_ticks_are_merged():
    feed = _make_feed()

    orderbook_tick = TickData(
        symbol="A05603",
        timestamp=1700000000.0,
        bid_price_1=330.48,
        bid_qty_1=12.0,
        ask_price_1=330.50,
        ask_qty_1=15.0,
    )
    feed._on_tick(orderbook_tick)

    trade_tick = TickData(
        symbol="A05603",
        timestamp=1700000001.0,
        bid_price_1=0.0,
        bid_qty_1=0.0,
        ask_price_1=0.0,
        ask_qty_1=0.0,
        current_price=330.49,
        open_price=330.20,
        high_price=330.70,
        low_price=330.10,
        cumulative_volume=1234.0,
    )
    feed._on_tick(trade_tick)

    payload = await feed.get_current_price("A05603")
    assert payload["close"] == 330.49
    assert payload["bid_price_1"] == 330.48
    assert payload["ask_price_1"] == 330.50
    assert payload["spread"] == pytest.approx(0.02)


def test_get_orderbook_snapshot_returns_cached_top_of_book():
    feed = _make_feed()
    tick = TickData(
        symbol="A05603",
        timestamp=1700000000.0,
        bid_price_1=330.40,
        bid_qty_1=20.0,
        ask_price_1=330.42,
        ask_qty_1=18.0,
    )
    feed._on_tick(tick)

    ob = feed.get_orderbook_snapshot("A05603")
    assert ob["bid_price_1"] == 330.40
    assert ob["ask_price_1"] == 330.42
    assert ob["bid_qty_1"] == 20.0
    assert ob["ask_qty_1"] == 18.0
