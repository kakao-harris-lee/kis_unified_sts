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
    """Drain everything already on the stream, then stop.

    Waits for the reader to reach the stream's last id rather than a fixed
    sleep — a wall-clock drain is time-fragile (#592).
    """
    tail = await redis.xrevrange(STREAM, count=1)
    assert len(tail) == 1, "nothing published"
    last_id = tail[0][0].decode() if isinstance(tail[0][0], bytes) else str(tail[0][0])

    feed = StreamConsumerFeed(redis=redis, stream=STREAM, xread_block_ms=20)
    feed._last_id = "0"  # read from the head: entries are already published
    feed.update_symbols([SYMBOL])
    await feed.start()
    try:
        for _ in range(200):
            if feed._last_id == last_id:
                break
            await asyncio.sleep(0.01)
    finally:
        await feed.stop()
    assert feed._last_id == last_id, (
        f"reader stopped at {feed._last_id}, expected {last_id} "
        f"({entries_expected} entries published)"
    )
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
async def test_frozen_book_under_fresh_trades_keeps_the_quote_time():
    """The condition the whole `quote_ts` field exists for.

    Trades keep printing while H0IFASP0 goes quiet — a real state the WS feed
    models (`_log_orderbook_staleness`) and never expires the cached book for.
    The producer then merges a frozen bid/ask onto a fresh trade timestamp
    every ~0.2s. If the stream carried only the entry timestamp, a freshness
    check would read age≈0 forever and pass a dead book into the entry gate.
    Both feeds must report the ORDERBOOK tick's own time here.
    """
    ws, captured = _ws_feed()
    ws._on_tick(_orderbook_tick(ts=TICK_TS))
    ws._on_tick(_trade_tick(ts=TICK_TS + 5.0))
    ws_snapshot = ws.get_orderbook_snapshot(SYMBOL)

    server = fakeredis.FakeServer()
    published = _producer_payload(ws, captured)
    assert published["timestamp"] == TICK_TS + 5.0  # the trade print
    assert published["quote_ts"] == TICK_TS  # the frozen book
    _publisher(fakeredis.FakeStrictRedis(server=server, db=1)).publish(
        "futures", SYMBOL, published
    )
    consumer = await _consume(
        fakeredis.aioredis.FakeRedis(server=server, db=1), entries_expected=1
    )
    stream_snapshot = consumer.get_orderbook_snapshot(SYMBOL)

    assert stream_snapshot == ws_snapshot
    assert stream_snapshot["timestamp"] == TICK_TS
    # The trade time is still available on the price dict, unchanged.
    assert (await consumer.get_current_price(SYMBOL))["timestamp"] == TICK_TS + 5.0


@pytest.mark.asyncio
async def test_a_quoteless_entry_does_not_erase_a_known_book():
    """Mirrors the WS feed, which never clears `_orderbooks` on a trade tick.

    A producer cold start or a cutover handoff publishes trade-only entries for
    a while. Dropping the book there would block every entry on
    `orderbook_unavailable`, which reads as a market condition; keeping it with
    its true `quote_ts` lets the freshness gate reject it as what it is.
    """
    ws, captured = _ws_feed()
    ws._on_tick(_orderbook_tick(ts=TICK_TS))
    ws._on_tick(_trade_tick(ts=TICK_TS))

    server = fakeredis.FakeServer()
    publisher = _publisher(fakeredis.FakeStrictRedis(server=server, db=1))
    publisher.publish("futures", SYMBOL, _producer_payload(ws, captured))
    # A later trade-only publish: same symbol, no book at all.
    publisher.publish(
        "futures",
        SYMBOL,
        {"code": SYMBOL, "close": 331.40, "timestamp": TICK_TS + 60.0},
    )

    consumer = await _consume(
        fakeredis.aioredis.FakeRedis(server=server, db=1), entries_expected=2
    )

    assert (await consumer.get_current_price(SYMBOL))["close"] == pytest.approx(331.40)
    snapshot = consumer.get_orderbook_snapshot(SYMBOL)
    assert snapshot["bid_price_1"] == 331.18
    assert snapshot["timestamp"] == TICK_TS  # still the old book's own time


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
