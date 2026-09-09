"""WS feed ↔ tick-stream parity for the futures orderbook snapshot.

The order-router's send-time slippage gate and its paper fill simulator read
``get_orderbook_snapshot`` from whatever feed they were handed. Since the
router can now be fed by the Redis tick stream instead of its own KIS
WebSocket (``FUTURES_ORDER_ROUTER_FEED=stream``), the two feeds must answer
that call identically or the gate silently changes behaviour with the wiring.

This pins the contract end to end on the real classes: one synthetic KIS
orderbook tick + one trade tick go into ``KISFuturesPriceFeed._on_tick``; what
the tick callback receives, merged with ``orderbook_publish_fields`` exactly as
both producers do it, goes out through ``TickStreamPublisher`` into a fake Redis
stream and back through ``StreamConsumerFeed``; and both snapshots are compared
key for key. Hermetic — no KIS connection, no real Redis.
"""

from __future__ import annotations

import asyncio

import fakeredis
import fakeredis.aioredis
import pytest

from services.monitoring.tick_stream_publisher import (
    TickStreamPublisher,
    TickStreamPublisherConfig,
    orderbook_publish_fields,
)
from shared.collector.models import TickData
from shared.kis.auth import KISAuthConfig
from shared.kis.futures_feed import KISFuturesPriceFeed
from shared.streaming.consumer_feed import StreamConsumerFeed

SYMBOL = "A05603"
STREAM = "raw_data"
TICK_TS = 1_700_000_000.0


def _ws_feed() -> tuple[KISFuturesPriceFeed, list[dict]]:
    """A real feed object with no connection — only ``_on_tick`` is exercised.

    The captured list receives exactly what a producer's tick callback receives
    (the TRADE payload; orderbook ticks never reach a callback), so the publish
    below is the real producer path rather than a convenient stand-in.
    """
    feed = KISFuturesPriceFeed(
        config=KISAuthConfig(app_key="k", app_secret="s", is_real=True)
    )
    captured: list[dict] = []
    feed.set_tick_callback(lambda _sym, payload, _ts: captured.append(dict(payload)))
    return feed, captured


def _producer_payload(feed: KISFuturesPriceFeed, captured: list[dict]) -> dict:
    """What both producers publish: the trade tick plus the merged top of book."""
    return {
        **captured[-1],
        **orderbook_publish_fields(feed.get_orderbook_snapshot(SYMBOL)),
    }


def _orderbook_tick(ts: float = TICK_TS) -> TickData:
    return TickData(
        symbol=SYMBOL,
        timestamp=ts,
        bid_price_1=331.18,
        bid_qty_1=12.0,
        ask_price_1=331.22,
        ask_qty_1=9.0,
    )


def _trade_tick(ts: float = TICK_TS) -> TickData:
    return TickData(
        symbol=SYMBOL,
        timestamp=ts,
        bid_price_1=0.0,
        bid_qty_1=0.0,
        ask_price_1=0.0,
        ask_qty_1=0.0,
        current_price=331.20,
        open_price=330.00,
        high_price=331.50,
        low_price=329.80,
        cumulative_volume=4321.0,
    )


def _publisher(client) -> TickStreamPublisher:
    return TickStreamPublisher(
        TickStreamPublisherConfig(
            enabled=True,
            async_publish=False,  # publish inline so the test needs no worker
            futures_stream=STREAM,
            futures_min_interval_seconds=0.0,
        ),
        client=client,
    )


async def _consume(redis, entries_expected: int) -> StreamConsumerFeed:
    feed = StreamConsumerFeed(redis=redis, stream=STREAM, xread_block_ms=20)
    feed._last_id = "0"  # read from the head: entries are already published
    feed.update_symbols([SYMBOL])
    await feed.start()
    try:
        for _ in range(200):
            if len(feed._symbol_tick_ts) and feed._prices.get(SYMBOL):
                if entries_expected <= 1 or feed._prices[SYMBOL].get("close"):
                    break
            await asyncio.sleep(0.01)
    finally:
        await feed.stop()
    return feed


@pytest.mark.asyncio
async def test_stream_snapshot_matches_ws_feed_snapshot():
    """Same ticks in, identical orderbook snapshot out of both feeds."""
    ws, captured = _ws_feed()
    ws._on_tick(_orderbook_tick())
    ws._on_tick(_trade_tick())
    ws_snapshot = ws.get_orderbook_snapshot(SYMBOL)
    published = _producer_payload(ws, captured)

    server = fakeredis.FakeServer()
    _publisher(fakeredis.FakeStrictRedis(server=server, db=1)).publish(
        "futures", SYMBOL, published
    )
    consumer = await _consume(
        fakeredis.aioredis.FakeRedis(server=server, db=1), entries_expected=1
    )
    stream_snapshot = consumer.get_orderbook_snapshot(SYMBOL)

    assert stream_snapshot == ws_snapshot
    assert stream_snapshot["spread"] == pytest.approx(331.22 - 331.18)
    assert stream_snapshot["timestamp"] == TICK_TS
    assert (await consumer.get_current_price(SYMBOL))["close"] == pytest.approx(
        published["close"]
    )


@pytest.mark.asyncio
async def test_stream_snapshot_timestamp_tracks_the_newest_tick():
    """Documented divergence, pinned so it cannot drift silently.

    The WS feed answers from its dedicated orderbook cache, which keeps the
    orderbook tick's own time. The stream carries the producer's *merged*
    snapshot, whose ``timestamp`` the later trade tick overwrites — the same
    semantics as the WS feed's own fallback branch. Prices and quantities stay
    identical; only the clock differs, and it reads newer, so a freshness check
    downstream is looser here than on the WS feed, never stricter.
    """
    ws, captured = _ws_feed()
    ws._on_tick(_orderbook_tick(ts=TICK_TS))
    ws._on_tick(_trade_tick(ts=TICK_TS + 5.0))
    ws_snapshot = ws.get_orderbook_snapshot(SYMBOL)

    server = fakeredis.FakeServer()
    _publisher(fakeredis.FakeStrictRedis(server=server, db=1)).publish(
        "futures", SYMBOL, _producer_payload(ws, captured)
    )
    consumer = await _consume(
        fakeredis.aioredis.FakeRedis(server=server, db=1), entries_expected=1
    )
    stream_snapshot = consumer.get_orderbook_snapshot(SYMBOL)

    assert ws_snapshot["timestamp"] == TICK_TS
    assert stream_snapshot["timestamp"] == TICK_TS + 5.0
    assert {k: v for k, v in stream_snapshot.items() if k != "timestamp"} == {
        k: v for k, v in ws_snapshot.items() if k != "timestamp"
    }


@pytest.mark.asyncio
async def test_trade_only_producer_yields_no_usable_quote():
    """A producer with no quote cached (futures-market-ingest before this
    change, or a book that has not ticked yet) must not manufacture one.

    Literal equality does not hold here and should not: the WS feed's fallback
    branch filters its merged dict down to the orderbook keys and so returns a
    bid/ask-less ``{code, timestamp}`` stub, while the stream feed returns
    ``{}``. What matters is that neither parses into a quote — both block the
    entry gate with ``orderbook_unavailable`` — and ``{}`` is the safer of the
    two, since ``PaperKISFuturesAdapter.get_futures_orderbook`` treats a
    truthy snapshot as usable and subscripts ``bid_price_1``.
    """
    from shared.execution.slippage_control import parse_orderbook_snapshot

    ws, captured = _ws_feed()
    ws._on_tick(_trade_tick())

    server = fakeredis.FakeServer()
    _publisher(fakeredis.FakeStrictRedis(server=server, db=1)).publish(
        "futures", SYMBOL, _producer_payload(ws, captured)
    )
    consumer = await _consume(
        fakeredis.aioredis.FakeRedis(server=server, db=1), entries_expected=1
    )

    ws_snapshot = ws.get_orderbook_snapshot(SYMBOL)
    stream_snapshot = consumer.get_orderbook_snapshot(SYMBOL)
    assert parse_orderbook_snapshot(SYMBOL, ws_snapshot) is None
    assert parse_orderbook_snapshot(SYMBOL, stream_snapshot) is None
    assert stream_snapshot == {}
    assert "bid_price_1" not in ws_snapshot
    assert (await consumer.get_current_price(SYMBOL))["close"] == pytest.approx(331.20)
