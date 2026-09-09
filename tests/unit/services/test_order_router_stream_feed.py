"""order_router price-feed selection: tick stream (default) vs own KIS WS.

KIS serves one futures WebSocket per account, so the router's legacy self-fed
feed cannot coexist with ``trader-futures`` — whichever connects second is
dropped (measured 2026-09-07/08). ``FUTURES_ORDER_ROUTER_FEED=stream`` (the
default) has it consume the futures ticks another process already publishes
instead, and ``ws`` keeps the old path as an explicit opt-in.

These tests cover the selection itself and then run the two consumers that
actually need a quote — the send-time slippage gate and the paper fill
simulator — against a real :class:`StreamConsumerFeed` fed through the real
publisher. Hermetic: fakeredis, no KIS.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import fakeredis
import fakeredis.aioredis
import pytest

from services.monitoring.tick_stream_publisher import (
    TickStreamPublisher,
    TickStreamPublisherConfig,
)
from services.order_router.main import (
    OrderRouterDaemon,
    _build_price_feed,
    _resolve_feed_mode,
)
from shared.decision.signal import Signal
from shared.execution.contract_spec import ContractSpec
from shared.streaming.consumer_feed import StreamConsumerFeed

SYMBOL = "A05603"
STREAM = "raw_data"
FINAL_STREAM = "signal.final.futures.shadow"
GROUP = "order_router"
ROUTER_LOGGER = "services.order_router.main"


class _ExplodingFeed:
    """Stand-in for KISFuturesPriceFeed that fails if it is ever constructed."""

    def __init__(self, *args, **kwargs):  # noqa: ARG002
        raise AssertionError("stream mode must not construct a KIS WebSocket feed")


class _RecordingFeed:
    def __init__(self, *, config):
        self.config = config
        self.symbol_calls: list[tuple[list[str], list[str] | None]] = []

    def update_symbols(self, symbols, auxiliary_symbols=None):
        self.symbol_calls.append((list(symbols), auxiliary_symbols))


def _forbid_ws(monkeypatch) -> None:
    monkeypatch.setattr(
        "shared.kis.futures_feed.KISFuturesPriceFeed", _ExplodingFeed, raising=True
    )


# ---------------------------------------------------------------------------
# Mode resolution
# ---------------------------------------------------------------------------


def test_feed_mode_defaults_to_stream(monkeypatch):
    monkeypatch.delenv("FUTURES_ORDER_ROUTER_FEED", raising=False)
    assert _resolve_feed_mode() == "stream"


@pytest.mark.parametrize("raw", ["ws", "WS", " ws "])
def test_feed_mode_accepts_ws_opt_in(monkeypatch, raw):
    monkeypatch.setenv("FUTURES_ORDER_ROUTER_FEED", raw)
    assert _resolve_feed_mode() == "ws"


def test_blank_feed_mode_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("FUTURES_ORDER_ROUTER_FEED", "   ")
    assert _resolve_feed_mode() == "stream"


def test_unknown_feed_mode_fails_closed(monkeypatch):
    """A typo must stop the container, not silently pick a mode: guessing `ws`
    would cost trader-futures its market data."""
    monkeypatch.setenv("FUTURES_ORDER_ROUTER_FEED", "redis")
    with pytest.raises(ValueError, match="FUTURES_ORDER_ROUTER_FEED"):
        _resolve_feed_mode()


# ---------------------------------------------------------------------------
# Feed construction
# ---------------------------------------------------------------------------


def test_stream_mode_opens_no_kis_websocket(monkeypatch, caplog):
    _forbid_ws(monkeypatch)
    monkeypatch.delenv("FUTURES_TICK_STREAM", raising=False)

    with caplog.at_level(logging.INFO, logger=ROUTER_LOGGER):
        feed = _build_price_feed(feed_mode="stream", redis=object(), symbol=SYMBOL)

    assert isinstance(feed, StreamConsumerFeed)
    assert feed.stream == STREAM
    assert feed._subscribed == {SYMBOL}
    messages = [r.getMessage() for r in caplog.records]
    assert any("feed=stream" in m and "no KIS WS opened" in m for m in messages)


def test_stream_mode_honours_the_tick_stream_env(monkeypatch):
    _forbid_ws(monkeypatch)
    monkeypatch.setenv("FUTURES_TICK_STREAM", "raw_data_alt")

    feed = _build_price_feed(feed_mode="stream", redis=object(), symbol=SYMBOL)

    assert feed.stream == "raw_data_alt"


def test_ws_mode_still_builds_the_kis_feed(monkeypatch, caplog):
    monkeypatch.setattr(
        "shared.kis.futures_feed.KISFuturesPriceFeed", _RecordingFeed, raising=True
    )
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", "key")
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", "secret")

    with caplog.at_level(logging.INFO, logger=ROUTER_LOGGER):
        feed = _build_price_feed(
            feed_mode="ws",
            redis=object(),
            symbol=SYMBOL,
            auxiliary_symbols=["101S6000"],
        )

    assert isinstance(feed, _RecordingFeed)
    assert feed.symbol_calls == [([SYMBOL], ["101S6000"])]
    assert feed.config.app_key == "key" and feed.config.is_real is True
    assert any("feed=ws" in r.getMessage() for r in caplog.records)


def test_stream_mode_warns_that_cross_asset_will_block_every_entry(monkeypatch, caplog):
    """Operator decision ②: cross-asset stays out of scope for stream mode, so
    say plainly what happens rather than letting entries vanish silently."""
    _forbid_ws(monkeypatch)

    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        _build_price_feed(
            feed_mode="stream",
            redis=object(),
            symbol=SYMBOL,
            auxiliary_symbols=["101S6000"],
            cross_asset_enabled=True,
        )

    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("cross_asset_unavailable" in m for m in warnings), warnings


def test_stream_mode_is_quiet_when_cross_asset_is_off(monkeypatch, caplog):
    _forbid_ws(monkeypatch)

    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        _build_price_feed(feed_mode="stream", redis=object(), symbol=SYMBOL)

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# ---------------------------------------------------------------------------
# The gate and the paper adapter, running on a stream-fed feed
# ---------------------------------------------------------------------------


def _spec() -> ContractSpec:
    return ContractSpec(
        name="kospi200_mini",
        multiplier_krw_per_point=50_000,
        tick_size_points=0.02,
        tick_value_krw=1_000,
        commission_rate=0.0,
        symbol_prefix="A05",
    )


def _signal(entry_price: float = 331.20) -> Signal:
    now = datetime.now(UTC)
    return Signal(
        setup_type="A_gap_reversion",
        direction="long",
        symbol=SYMBOL,
        entry_price=entry_price,
        stop_loss=entry_price - 0.70,
        take_profit=entry_price + 1.30,
        confidence=0.85,
        valid_until=now.replace(year=now.year + 1),
        # Paper caps signal age at 3.5s (config/execution.yaml paper_override).
        generated_at=now,
    )


def _paper_controller():
    from shared.config.loader import ConfigLoader
    from shared.execution.slippage_control import (
        FuturesSlippageController,
        load_futures_slippage_config,
    )

    cfg = load_futures_slippage_config(
        ConfigLoader.load("execution.yaml"), paper_trading=True
    )
    # Pin the paper thresholds this test reasons about; a config change that
    # moves them should surface here rather than as a mystery pass/block.
    assert cfg.max_spread_ticks == 6 and cfg.tick_size == 0.02
    assert cfg.min_depth_multiplier == 1.0 and cfg.cross_asset_enabled is False
    return FuturesSlippageController(cfg)


async def _stream_feed_with_quote(
    *,
    bid: float,
    ask: float,
    last: float | None = None,
    bid_qty: float = 10.0,
    ask_qty: float = 10.0,
    quote_ts: float | None = None,
):
    """Publish one orchestrator-shaped merged snapshot and consume it.

    Goes through the real ``TickStreamPublisher`` (sync path) and the real
    ``StreamConsumerFeed`` reader, so the quote the gate sees has survived the
    actual encode/decode contract. Returns ``(router_redis, feed)``; the feed
    holds a *separate* client on the same fake server so that stopping its
    blocking read cannot leave the router's connection mid-reply.
    """
    server = fakeredis.FakeServer()
    publisher = TickStreamPublisher(
        TickStreamPublisherConfig(
            enabled=True,
            async_publish=False,
            futures_stream=STREAM,
            futures_min_interval_seconds=0.0,
        ),
        client=fakeredis.FakeStrictRedis(server=server, db=1),
    )
    publisher.publish(
        "futures",
        SYMBOL,
        {
            "code": SYMBOL,
            "close": bid if last is None else last,
            "timestamp": (
                datetime.now(UTC).timestamp() if quote_ts is None else quote_ts
            ),
            "bid_price_1": bid,
            "bid_qty_1": bid_qty,
            "ask_price_1": ask,
            "ask_qty_1": ask_qty,
            "spread": ask - bid,
        },
    )

    feed = StreamConsumerFeed(
        redis=fakeredis.aioredis.FakeRedis(server=server, db=1),
        stream=STREAM,
        xread_block_ms=20,
    )
    feed._last_id = "0"
    feed.update_symbols([SYMBOL])
    await feed.start()
    for _ in range(200):
        if feed.get_orderbook_snapshot(SYMBOL):
            break
        await asyncio.sleep(0.01)
    await feed.stop()
    assert feed.get_orderbook_snapshot(SYMBOL), "stream feed never cached a quote"
    return fakeredis.aioredis.FakeRedis(server=server, db=1), feed


def _kis_client() -> AsyncMock:
    from shared.execution.passive_maker import Fill

    client = AsyncMock()
    client.get_futures_orderbook.return_value = SimpleNamespace(
        bid=[SimpleNamespace(price=331.20)],
        ask=[SimpleNamespace(price=331.22)],
    )
    client.place_futures_order.return_value = "ORD-1"
    client.await_fill.return_value = Fill(
        order_id="ORD-1", price=331.20, quantity=1, filled_at_ms=2000
    )
    return client


async def _route_one(redis, feed, controller, signal: Signal):
    from shared.execution.passive_maker import PassiveMaker
    from shared.execution.pseudo_oco import PseudoOCO

    fill_logger = AsyncMock()
    kis = _kis_client()
    daemon = OrderRouterDaemon(
        redis=redis,
        passive_maker=PassiveMaker(kis_client=kis, fill_logger=fill_logger),
        pseudo_oco=PseudoOCO(fill_logger=fill_logger),
        contract_spec=_spec(),
        final_stream=FINAL_STREAM,
        consumer_group=GROUP,
        worker_id="test-worker",
        xread_block_ms=10,
        batch_size=10,
        passive_timeout_seconds=5,
        futures_price_feed=feed,
        slippage_controller=controller,
    )
    fields = signal.to_stream_dict()
    fields["signal_id"] = "sig-1"
    fields["size_multiplier"] = "1.0"
    fields["filtered_at_ms"] = "1000"
    await redis.xadd(FINAL_STREAM, fields)

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())
    return daemon, kis


@pytest.mark.asyncio
async def test_stream_fed_gate_blocks_a_wide_spread(caplog):
    # 0.24 points = 12 ticks, over the paper cap of 6.
    redis, feed = await _stream_feed_with_quote(bid=331.18, ask=331.42)

    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        daemon, kis = await _route_one(redis, feed, _paper_controller(), _signal())

    assert daemon.slippage_blocked_count == 1
    assert any("reason=wide_spread" in r.getMessage() for r in caplog.records), [
        r.getMessage() for r in caplog.records
    ]
    kis.place_futures_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_fed_gate_passes_a_tight_book():
    # 1 tick spread, depth 10 >= 1 contract * 1.0, zero price deviation.
    redis, feed = await _stream_feed_with_quote(bid=331.20, ask=331.22)

    daemon, kis = await _route_one(redis, feed, _paper_controller(), _signal(331.20))

    assert daemon.slippage_blocked_count == 0
    kis.place_futures_order.assert_awaited_once()
    assert kis.place_futures_order.call_args.kwargs["order_type"] == "limit"


@pytest.mark.asyncio
async def test_paper_adapter_fills_from_a_stream_feed():
    """PaperKISFuturesAdapter duck-types the feed; the stream one must satisfy
    both halves of what it reads (top of book + last trade)."""
    from shared.execution.paper_kis_futures_adapter import PaperKISFuturesAdapter

    _redis, feed = await _stream_feed_with_quote(bid=331.20, ask=331.22)
    adapter = PaperKISFuturesAdapter(futures_price_feed=feed, poll_interval=0.01)

    book = await adapter.get_futures_orderbook(SYMBOL)
    assert book.bid[0].price == 331.20 and book.ask[0].price == 331.22

    order_id = await adapter.place_futures_order(
        symbol=SYMBOL, side="long", quantity=1, order_type="limit", price=331.21
    )
    fill = await adapter.await_fill(order_id, timeout_seconds=1.0)

    # The published last trade (331.20) is at or below the resting long limit,
    # so the simulator fills at the limit.
    assert fill is not None
    assert fill.price == 331.21 and fill.quantity == 1


# ---------------------------------------------------------------------------
# Quote-freshness gate (router-only; applies in both feed modes)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_quote_is_blocked_before_the_controller_sees_it(caplog):
    """`evaluate_entry` filters on the SIGNAL's age and never reads the quote's
    timestamp, so without this gate a feed that stopped ticking keeps serving
    its last, still-parseable book. Both producers publish on trade ticks, so a
    quiet book is exactly when it happens."""
    controller = _paper_controller()
    assert controller.config.order_router_max_quote_age_seconds == 10.0
    stale = datetime.now(UTC).timestamp() - 120.0
    redis, feed = await _stream_feed_with_quote(bid=331.20, ask=331.22, quote_ts=stale)

    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        daemon, kis = await _route_one(redis, feed, controller, _signal(331.20))

    assert daemon.slippage_blocked_count == 1
    assert any("reason=quote_stale" in r.getMessage() for r in caplog.records), [
        r.getMessage() for r in caplog.records
    ]
    kis.place_futures_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_quote_without_a_readable_timestamp_is_blocked(caplog):
    """Fail-closed: `parse_orderbook_snapshot` substitutes `now` for a missing
    timestamp, so an ageless quote would otherwise read as brand new."""
    redis, feed = await _stream_feed_with_quote(bid=331.20, ask=331.22)
    feed._prices["A05603"].pop("timestamp")

    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        daemon, kis = await _route_one(
            redis, feed, _paper_controller(), _signal(331.20)
        )

    assert daemon.slippage_blocked_count == 1
    assert any(
        "reason=quote_stale:unknown_timestamp" in r.getMessage() for r in caplog.records
    )
    kis.place_futures_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_quote_age_zero_disables_the_freshness_gate():
    """The knob is a rollback switch, like order_router_gate."""
    controller = _paper_controller()
    controller.config.order_router_max_quote_age_seconds = 0.0
    stale = datetime.now(UTC).timestamp() - 3600.0
    redis, feed = await _stream_feed_with_quote(bid=331.20, ask=331.22, quote_ts=stale)

    daemon, kis = await _route_one(redis, feed, controller, _signal(331.20))

    assert daemon.slippage_blocked_count == 0
    kis.place_futures_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_book_still_reports_orderbook_unavailable(caplog):
    """The freshness gate must not steal the controller's own reason for the
    case where there is no book at all."""
    redis, feed = await _stream_feed_with_quote(bid=331.20, ask=331.22)
    feed._prices.clear()
    assert feed.get_orderbook_snapshot(SYMBOL) == {}

    with caplog.at_level(logging.WARNING, logger=ROUTER_LOGGER):
        daemon, kis = await _route_one(
            redis, feed, _paper_controller(), _signal(331.20)
        )

    assert daemon.slippage_blocked_count == 1
    assert any(
        "reason=orderbook_unavailable" in r.getMessage() for r in caplog.records
    ), [r.getMessage() for r in caplog.records]
    kis.place_futures_order.assert_not_awaited()
