"""Tests for StreamConsumerFeed (Redis tick stream → price cache + indicator push)."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

import pytest

from shared.streaming.consumer_feed import (
    StreamConsumerFeed,
    _parse_entry_fields,
)


def _entry(**kw) -> dict[bytes, bytes]:
    return {k.encode(): str(v).encode() for k, v in kw.items()}


class FakeIndicatorEngine:
    def __init__(self):
        self._last_cumulative_volume: dict[str, float] = {}
        self.baseline_calls: list[tuple[str, float]] = []
        self.on_tick_calls: list[tuple[str, dict, object]] = []

    def set_volume_baseline(self, symbol: str, cumulative_volume: float) -> None:
        self.baseline_calls.append((symbol, cumulative_volume))
        self._last_cumulative_volume[symbol] = cumulative_volume

    def on_tick(self, symbol, price_data, timestamp=None):
        self.on_tick_calls.append((symbol, price_data, timestamp))


def test_parse_entry_extracts_price_shape():
    sym, price = _parse_entry_fields(
        _entry(
            schema_version="1",
            symbol="005930",
            price="100.5",
            open="99",
            high="101",
            low="98",
            volume="1234",
            timestamp="1700000000.0",
        )
    )
    assert sym == "005930"
    assert price["code"] == "005930"
    assert price["close"] == 100.5
    assert price["open"] == 99.0 and price["high"] == 101.0 and price["low"] == 98.0
    assert price["volume"] == 1234
    assert price["timestamp"] == 1700000000.0


def test_parse_entry_supports_legacy_price_aliases_during_rollout():
    _, price = _parse_entry_fields(_entry(code="A01", current_price="50.0"))
    assert price["close"] == 50.0 and price["code"] == "A01"


def test_parse_entry_preserves_stream_consumer_legacy_close_priority():
    _, price = _parse_entry_fields(
        _entry(symbol="A01", close="49.0", current_price="50.0", price="51.0")
    )
    assert price["close"] == 49.0


def test_parse_entry_returns_none_on_missing_symbol_or_price():
    assert _parse_entry_fields(_entry(close="1.0")) is None
    assert _parse_entry_fields(_entry(symbol="X")) is None


def test_parse_entry_volume_is_cumulative_bool():
    _, price = _parse_entry_fields(
        _entry(
            schema_version="1",
            symbol="X",
            price="1",
            volume_is_cumulative="true",
        )
    )
    assert price["volume_is_cumulative"] is True


def _feed(**kw):
    return StreamConsumerFeed(redis=object(), stream="market:ticks", **kw)


class _FailingReadRedis:
    def __init__(self) -> None:
        self.calls = 0

    async def xread(self, *_args, **_kwargs):
        self.calls += 1
        raise RuntimeError(f"redis unavailable {self.calls}")


@pytest.mark.asyncio
async def test_apply_entry_updates_cache_and_get_current_price():
    feed = _feed()
    feed._apply_entry(
        _entry(schema_version="1", symbol="005930", price="100.0", volume="10")
    )
    got = await feed.get_current_price("005930")
    assert got["close"] == 100.0 and got["code"] == "005930"
    got["close"] = -1
    assert (await feed.get_current_price("005930"))["close"] == 100.0


@pytest.mark.asyncio
async def test_get_current_price_missing_symbol_returns_empty():
    assert await _feed().get_current_price("nope") == {}


def test_supports_instant_read_is_true():
    assert _feed().supports_instant_read is True


def test_apply_entry_pushes_to_indicator_engine_with_baseline_guard():
    eng = FakeIndicatorEngine()
    feed = _feed(indicator_engine=eng)
    feed._apply_entry(
        _entry(schema_version="1", symbol="005930", price="100.0", volume="500")
    )
    assert eng.baseline_calls == [("005930", 500.0)]
    assert len(eng.on_tick_calls) == 1
    sym, price, ts = eng.on_tick_calls[0]
    assert sym == "005930" and price["close"] == 100.0
    assert isinstance(ts, datetime)
    feed._apply_entry(
        _entry(schema_version="1", symbol="005930", price="101.0", volume="600")
    )
    assert eng.baseline_calls == [("005930", 500.0)]
    assert len(eng.on_tick_calls) == 2


def test_update_symbols_sets_symbol_count():
    feed = _feed()
    feed.update_symbols(["A", "B", "C"])
    assert feed.get_health_status()["symbol_count"] == 3


def test_health_status_has_failover_keys_and_is_stale_before_ticks():
    feed = _feed(stale_threshold_seconds=30.0)
    h = feed.get_health_status()
    for key in (
        "running",
        "connected",
        "staleness_seconds",
        "fresh_symbol_count",
        "symbol_count",
    ):
        assert key in h
    assert h["staleness_seconds"] is None
    assert feed.is_healthy() is False


def test_is_healthy_true_when_running_and_fresh():
    feed = _feed(stale_threshold_seconds=30.0)
    feed._running = True
    feed._apply_entry(_entry(schema_version="1", symbol="X", price="1.0"))
    assert feed.is_healthy() is True
    h = feed.get_health_status()
    assert h["fresh_symbol_count"] == 1
    assert h["staleness_seconds"] is not None and h["staleness_seconds"] < 30.0


def test_set_tick_callback_invoked_instead_of_indicator_push():
    eng = FakeIndicatorEngine()
    feed = _feed(indicator_engine=eng)
    seen: list[tuple] = []
    feed.set_tick_callback(
        lambda symbol, price, ts: seen.append((symbol, price["close"], ts))
    )
    feed._apply_entry(
        _entry(schema_version="1", symbol="005930", price="100.0", volume="500")
    )
    assert len(seen) == 1
    symbol, close, ts = seen[0]
    assert symbol == "005930" and close == 100.0
    assert isinstance(ts, datetime)
    # callback present => indicator engine is NOT pushed
    assert eng.on_tick_calls == []
    assert eng.baseline_calls == []
    # price cache is still updated
    assert feed._prices["005930"]["close"] == 100.0


def test_set_tick_callback_via_constructor():
    seen: list[str] = []
    feed = _feed(tick_callback=lambda s, _p, _ts: seen.append(s))
    feed._apply_entry(_entry(schema_version="1", symbol="000660", price="50.0"))
    assert seen == ["000660"]


def test_no_callback_still_pushes_indicator():
    eng = FakeIndicatorEngine()
    feed = _feed(indicator_engine=eng)
    feed._apply_entry(
        _entry(schema_version="1", symbol="005930", price="100.0", volume="500")
    )
    assert len(eng.on_tick_calls) == 1  # unchanged M1b behavior


def test_tick_callback_exception_is_swallowed():
    feed = _feed()

    def boom(symbol, price, ts):
        raise RuntimeError("callback blew up")

    feed.set_tick_callback(boom)
    # must not propagate out of _apply_entry
    feed._apply_entry(_entry(schema_version="1", symbol="005930", price="100.0"))
    assert feed._prices["005930"]["close"] == 100.0


@pytest.mark.asyncio
async def test_read_loop_consumes_xadded_ticks():
    import asyncio

    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis()
    feed = StreamConsumerFeed(redis=redis, stream="market:ticks", xread_block_ms=20)
    await feed.start()
    try:
        await redis.xadd(
            "market:ticks",
            {
                "schema_version": "1",
                "symbol": "005930",
                "asset": "stock",
                "price": "123.0",
                "timestamp": "1700000000.0",
            },
        )
        for _ in range(50):
            if await feed.get_current_price("005930"):
                break
            await asyncio.sleep(0.02)
        got = await feed.get_current_price("005930")
        assert got["close"] == 123.0
        assert feed.is_healthy() is True
    finally:
        await feed.stop()
    assert feed._running is False


@pytest.mark.asyncio
async def test_read_loop_rate_limits_repeated_xread_errors(monkeypatch, caplog):
    redis = _FailingReadRedis()
    feed = StreamConsumerFeed(redis=redis, stream="market:ticks")
    feed._running = True
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 3:
            feed._running = False

    monkeypatch.setattr("shared.streaming.consumer_feed.asyncio.sleep", fake_sleep)
    caplog.set_level(logging.ERROR, logger="shared.streaming.consumer_feed")

    await feed._read_loop()

    assert redis.calls == 3
    assert sleep_calls == [0.5, 0.5, 0.5]
    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "event=tick_stream_read_error stream=market:ticks sleep_seconds=0.5"
    ]
    assert caplog.records[0].exc_info is not None


# ---------------------------------------------------------------------------
# Orderbook snapshot surface (order-router stream feed)
# ---------------------------------------------------------------------------


def _orderbook_entry(**kw) -> dict[bytes, bytes]:
    base = {
        "schema_version": "1",
        "symbol": "A05603",
        "price": "331.20",
        "timestamp": "1700000000.0",
        "bid_price_1": "331.18",
        "bid_qty_1": "12",
        "ask_price_1": "331.22",
        "ask_qty_1": "9",
        "spread": "0.04",
    }
    base.update({k: str(v) for k, v in kw.items()})
    return _entry(**base)


def test_orderbook_snapshot_returns_ws_feed_key_set():
    feed = _feed()
    feed._apply_entry(_orderbook_entry())

    snap = feed.get_orderbook_snapshot("A05603")

    assert set(snap) == {
        "code",
        "timestamp",
        "bid_price_1",
        "bid_qty_1",
        "ask_price_1",
        "ask_qty_1",
        "spread",
    }
    assert snap["code"] == "A05603"
    assert snap["bid_price_1"] == 331.18
    assert snap["bid_qty_1"] == 12.0
    assert snap["ask_price_1"] == 331.22
    assert snap["ask_qty_1"] == 9.0
    assert snap["spread"] == 0.04
    # Producer tick time, not our arrival time — a downstream freshness check
    # must measure the market event.
    assert snap["timestamp"] == 1700000000.0


def test_orderbook_snapshot_empty_without_a_two_sided_book():
    feed = _feed()
    # Trade-only entry: the pre-existing producer shape, still valid.
    feed._apply_entry(_entry(schema_version="1", symbol="A05603", price="331.20"))
    assert feed.get_orderbook_snapshot("A05603") == {}
    assert feed.get_orderbook_snapshot("nope") == {}

    # One-sided book is not a book.
    feed._apply_entry(_orderbook_entry(ask_price_1="0"))
    assert feed.get_orderbook_snapshot("A05603") == {}


def test_orderbook_snapshot_derives_spread_when_producer_omits_it():
    """`spread` is a pure function of bid/ask in the WS feed; keep the key set
    identical even for a producer that publishes only the four prices."""
    feed = _feed()
    fields = _orderbook_entry()
    del fields[b"spread"]
    feed._apply_entry(fields)

    snap = feed.get_orderbook_snapshot("A05603")
    assert snap["spread"] == pytest.approx(331.22 - 331.18)
    assert snap["bid_qty_1"] == 12.0


def test_orderbook_snapshot_defaults_missing_quantities_to_zero():
    feed = _feed()
    fields = _orderbook_entry()
    del fields[b"bid_qty_1"]
    del fields[b"ask_qty_1"]
    feed._apply_entry(fields)

    snap = feed.get_orderbook_snapshot("A05603")
    assert snap["bid_qty_1"] == 0.0 and snap["ask_qty_1"] == 0.0


def test_update_symbols_records_auxiliary_symbols(caplog):
    """Availability of an auxiliary symbol depends on the producer, which this
    class cannot see — so it records rather than warns, and the caller that
    knows the deployment does the warning."""
    feed = _feed()
    with caplog.at_level(logging.WARNING, logger="shared.streaming.consumer_feed"):
        feed.update_symbols(["A05603"], auxiliary_symbols=["101S6000"])

    assert feed._subscribed == {"A05603"}
    assert feed._auxiliary == {"101S6000"}
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


def test_update_symbols_without_auxiliary_clears_the_set():
    feed = _feed()
    feed.update_symbols(["A05603"], auxiliary_symbols=["101S6000"])
    feed.update_symbols(["A05603"])
    assert feed._auxiliary == set()


def test_health_status_reports_orderbook_age():
    feed = _feed()
    assert feed.get_health_status()["orderbook_age_seconds"] is None

    # A trade-only stream stays orderbook-dark even while ticks flow.
    feed._apply_entry(_entry(schema_version="1", symbol="A05603", price="331.20"))
    status = feed.get_health_status()
    assert status["staleness_seconds"] is not None
    assert status["orderbook_age_seconds"] is None

    feed._apply_entry(_orderbook_entry())
    age = feed.get_health_status()["orderbook_age_seconds"]
    assert age is not None and age >= 0.0


# ---------------------------------------------------------------------------
# Cold-start seeding (order-router restart)
# ---------------------------------------------------------------------------


class _SeedRedis:
    """Minimal async Redis double: XREVRANGE returns a fixed tail, XREAD idles."""

    def __init__(self, entries, *, revrange_raises: bool = False):
        self.entries = entries
        self.revrange_raises = revrange_raises
        self.revrange_calls: list[tuple[str, int]] = []

    async def xrevrange(self, stream, count=None, **_kw):
        self.revrange_calls.append((stream, count))
        if self.revrange_raises:
            raise RuntimeError("stream unavailable")
        return list(self.entries)

    async def xread(self, *_args, **_kwargs):
        await asyncio.sleep(0.01)
        return []


def _seed_entries(*fields):
    """Newest-first, as XREVRANGE returns them."""
    return [(f"{i}-0".encode(), f) for i, f in enumerate(reversed(fields))]


@pytest.mark.asyncio
async def test_seed_latest_primes_the_cache_before_the_first_read():
    """Without this the router is blind until the next tick, so the first
    signal after a restart is blocked on `orderbook_unavailable`."""
    redis = _SeedRedis(_seed_entries(_orderbook_entry()))
    feed = StreamConsumerFeed(
        redis=redis, stream="raw_data", seed_latest=True, seed_count=25
    )
    feed.update_symbols(["A05603"])

    await feed.start()
    try:
        assert redis.revrange_calls == [("raw_data", 25)]
        assert feed.get_orderbook_snapshot("A05603")["bid_price_1"] == 331.18
        assert (await feed.get_current_price("A05603"))["close"] == 331.20
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeding_is_off_by_default():
    redis = _SeedRedis(_seed_entries(_orderbook_entry()))
    feed = StreamConsumerFeed(redis=redis, stream="raw_data")
    feed.update_symbols(["A05603"])

    await feed.start()
    try:
        assert redis.revrange_calls == []
        assert feed.get_orderbook_snapshot("A05603") == {}
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeded_entries_age_from_the_producer_timestamp():
    """A 50-entry replay must not read as 50 ticks that just landed — the
    quote-age gate downstream would then pass a book from an hour ago."""
    old = 1700000000.0
    redis = _SeedRedis(_seed_entries(_orderbook_entry(timestamp=old)))
    feed = StreamConsumerFeed(redis=redis, stream="raw_data", seed_latest=True)
    feed.update_symbols(["A05603"])

    await feed.start()
    try:
        status = feed.get_health_status()
        assert status["last_tick_ts"] == old
        assert status["staleness_seconds"] > 1_000_000  # ages from 2023, not now
        assert status["orderbook_age_seconds"] > 1_000_000
        assert feed.is_healthy() is False
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeding_applies_oldest_first_and_skips_other_symbols():
    redis = _SeedRedis(
        _seed_entries(
            _orderbook_entry(price="331.10", timestamp=1.0),
            _entry(schema_version="1", symbol="A99999", price="1.0"),
            _orderbook_entry(price="331.30", timestamp=2.0),
        )
    )
    feed = StreamConsumerFeed(redis=redis, stream="raw_data", seed_latest=True)
    feed.update_symbols(["A05603"])

    await feed.start()
    try:
        # Newest wins, so the replay order is oldest → newest.
        assert (await feed.get_current_price("A05603"))["close"] == 331.30
        assert await feed.get_current_price("A99999") == {}
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeding_does_not_replay_ticks_into_the_callback():
    """Seeding primes a cache; firing the callback would inject prints the
    process never observed into the volatility baseline."""
    seen: list[str] = []
    redis = _SeedRedis(_seed_entries(_orderbook_entry()))
    feed = StreamConsumerFeed(
        redis=redis,
        stream="raw_data",
        seed_latest=True,
        tick_callback=lambda sym, _p, _ts: seen.append(sym),
    )
    feed.update_symbols(["A05603"])

    await feed.start()
    try:
        assert seen == []
        assert feed.get_orderbook_snapshot("A05603")
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeding_failure_leaves_the_feed_running(caplog):
    redis = _SeedRedis([], revrange_raises=True)
    feed = StreamConsumerFeed(redis=redis, stream="raw_data", seed_latest=True)
    feed.update_symbols(["A05603"])

    with caplog.at_level(logging.WARNING, logger="shared.streaming.consumer_feed"):
        await feed.start()
    try:
        assert feed._running is True
        assert feed.get_orderbook_snapshot("A05603") == {}
        assert any("tick_stream_seed_failed" in r.getMessage() for r in caplog.records)
    finally:
        await feed.stop()


# ---------------------------------------------------------------------------
# quote_ts: the book's own clock, and the last-good-book cache
# ---------------------------------------------------------------------------


def test_snapshot_timestamp_is_the_quote_time_not_the_trade_time():
    """The condition this exists for: a frozen book merged onto fresh trades.
    Reading the entry timestamp would report age≈0 for a dead book forever."""
    feed = _feed()
    feed._apply_entry(_orderbook_entry(timestamp=2000.0, quote_ts=1000.0))

    snap = feed.get_orderbook_snapshot("A05603")
    assert snap["timestamp"] == 1000.0
    # The trade time is still on the price dict, untouched.
    assert feed._prices["A05603"]["timestamp"] == 2000.0
    assert feed.get_health_status()["orderbook_age_seconds"] == pytest.approx(
        time.time() - 1000.0, abs=5
    )


def test_snapshot_falls_back_to_entry_timestamp_for_pre_quote_ts_entries():
    """Back-compat: entries written before quote_ts existed still yield a book,
    at the old (looser) timestamp rather than none at all."""
    feed = _feed()
    feed._apply_entry(_orderbook_entry(timestamp=1500.0))
    assert feed.get_orderbook_snapshot("A05603")["timestamp"] == 1500.0


def test_a_quoteless_entry_does_not_erase_the_last_known_book():
    """Mirrors KISFuturesPriceFeed, which never clears _orderbooks on a trade
    tick. Erasing would block entries on `orderbook_unavailable`, which reads
    as a market condition; keeping it lets the freshness gate reject it as the
    data gap it is."""
    feed = _feed()
    feed._apply_entry(_orderbook_entry(timestamp=1000.0, quote_ts=1000.0))
    feed._apply_entry(_entry(schema_version="1", symbol="A05603", price="331.90"))

    snap = feed.get_orderbook_snapshot("A05603")
    assert snap["bid_price_1"] == 331.18
    assert snap["timestamp"] == 1000.0
    assert feed._prices["A05603"]["close"] == 331.90


def test_an_older_book_arriving_late_is_ignored_entirely():
    """The cache and its clock advance under one condition, so they cannot
    disagree. Two producers overlapping at cutover, or one restarting and
    republishing its cached book, would otherwise install an older book while
    the clock kept the newer time — the gate would read 600s and health 0s."""
    feed = _feed()
    feed._apply_entry(_orderbook_entry(quote_ts=5000.0, price="331.50"))
    feed._apply_entry(_orderbook_entry(quote_ts=1000.0, price="331.10"))

    assert feed._last_orderbook_ts == {"A05603": 5000.0}
    snapshot = feed.get_orderbook_snapshot("A05603")
    assert snapshot["timestamp"] == 5000.0
    # The price is a separate field and does track the latest entry.
    assert feed._prices["A05603"]["close"] == 331.10


def test_a_newer_book_replaces_the_cached_one():
    feed = _feed()
    feed._apply_entry(_orderbook_entry(quote_ts=1000.0))
    feed._apply_entry(_orderbook_entry(quote_ts=5000.0, bid_price_1="331.30"))

    snapshot = feed.get_orderbook_snapshot("A05603")
    assert snapshot["timestamp"] == 5000.0
    assert snapshot["bid_price_1"] == 331.30


def test_orderbook_age_reports_the_stalest_subscribed_symbol():
    """A single number that reported the freshest book could read healthy while
    the symbol actually being traded is stale — the gate judges per symbol, so
    the summary must never be less conservative than the gate."""
    fresh = time.time() - 1.0
    stale = time.time() - 600.0
    feed = _feed()
    feed.update_symbols(["A05603"], auxiliary_symbols=["101S6000"])
    feed._apply_entry(_orderbook_entry(symbol="A05603", quote_ts=fresh))
    feed._apply_entry(_orderbook_entry(symbol="101S6000", quote_ts=stale))

    status = feed.get_health_status()
    assert status["orderbook_age_seconds"] == pytest.approx(600.0, abs=5)
    by_symbol = status["orderbook_age_by_symbol"]
    assert by_symbol["A05603"] == pytest.approx(1.0, abs=5)
    assert by_symbol["101S6000"] == pytest.approx(600.0, abs=5)


def test_orderbook_age_ignores_symbols_we_do_not_follow():
    """The stream carries every symbol its producer publishes; an unrelated
    one going stale is not this consumer's health."""
    feed = _feed()
    feed.update_symbols(["A05603"])
    feed._apply_entry(_orderbook_entry(symbol="A05603", quote_ts=time.time()))
    feed._apply_entry(_orderbook_entry(symbol="A99999", quote_ts=time.time() - 9000))

    status = feed.get_health_status()
    assert status["orderbook_age_seconds"] == pytest.approx(0.0, abs=5)
    assert "A99999" in status["orderbook_age_by_symbol"]


# ---------------------------------------------------------------------------
# Seed age bound (fail-closed independently of the router's gate switch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seeding_skips_entries_older_than_the_bound(caplog):
    """A restart after a halt, or on a day-old stream, must not hand the router
    yesterday's book and rely on a downstream switch to reject it."""
    stale_ts = time.time() - 86_400
    redis = _SeedRedis(
        _seed_entries(_orderbook_entry(timestamp=stale_ts, quote_ts=stale_ts))
    )
    feed = StreamConsumerFeed(
        redis=redis, stream="raw_data", seed_latest=True, seed_max_age_seconds=10.0
    )
    feed.update_symbols(["A05603"])

    with caplog.at_level(logging.INFO, logger="shared.streaming.consumer_feed"):
        await feed.start()
    try:
        assert feed.get_orderbook_snapshot("A05603") == {}
        assert any(
            "entries_skipped_stale=1" in r.getMessage() for r in caplog.records
        ), [r.getMessage() for r in caplog.records]
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeding_applies_entries_inside_the_bound():
    fresh = time.time() - 1.0
    redis = _SeedRedis(_seed_entries(_orderbook_entry(timestamp=fresh, quote_ts=fresh)))
    feed = StreamConsumerFeed(
        redis=redis, stream="raw_data", seed_latest=True, seed_max_age_seconds=10.0
    )
    feed.update_symbols(["A05603"])

    await feed.start()
    try:
        assert feed.get_orderbook_snapshot("A05603")["bid_price_1"] == 331.18
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeding_skips_entries_with_no_readable_time():
    """Unreadable time is treated as infinitely old — fail-closed."""
    redis = _SeedRedis(
        [(b"1-0", {b"schema_version": b"1", b"symbol": b"A05603", b"price": b"331.2"})]
    )
    feed = StreamConsumerFeed(
        redis=redis, stream="raw_data", seed_latest=True, seed_max_age_seconds=10.0
    )
    feed.update_symbols(["A05603"])

    await feed.start()
    try:
        assert await feed.get_current_price("A05603") == {}
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeding_without_a_bound_applies_everything():
    stale_ts = time.time() - 86_400
    redis = _SeedRedis(
        _seed_entries(_orderbook_entry(timestamp=stale_ts, quote_ts=stale_ts))
    )
    feed = StreamConsumerFeed(redis=redis, stream="raw_data", seed_latest=True)
    feed.update_symbols(["A05603"])

    await feed.start()
    try:
        assert feed.get_orderbook_snapshot("A05603")["bid_price_1"] == 331.18
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeding_covers_auxiliary_symbols():
    redis = _SeedRedis(
        _seed_entries(_orderbook_entry(symbol="101S6000"), _orderbook_entry())
    )
    feed = StreamConsumerFeed(redis=redis, stream="raw_data", seed_latest=True)
    feed.update_symbols(["A05603"], auxiliary_symbols=["101S6000"])

    await feed.start()
    try:
        assert feed.get_orderbook_snapshot("101S6000")
        assert feed.get_orderbook_snapshot("A05603")
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeding_keeps_a_fresh_price_when_only_the_book_is_stale(caplog):
    """A frozen book under live trades is exactly the state worth surviving a
    restart: the price is current and useful. Dropping the whole entry for the
    book's sake would leave the router with no price either, and it needs one
    for PseudoOCO stops and for the paper fill simulator."""
    now = time.time()
    redis = _SeedRedis(
        _seed_entries(_orderbook_entry(timestamp=now, quote_ts=now - 86_400))
    )
    feed = StreamConsumerFeed(
        redis=redis, stream="raw_data", seed_latest=True, seed_max_age_seconds=10.0
    )
    feed.update_symbols(["A05603"])

    with caplog.at_level(logging.INFO, logger="shared.streaming.consumer_feed"):
        await feed.start()
    try:
        assert (await feed.get_current_price("A05603"))["close"] == 331.20
        assert feed.get_orderbook_snapshot("A05603") == {}
        seeded = [
            r.getMessage()
            for r in caplog.records
            if "tick_stream_seeded" in r.getMessage()
        ]
        assert seeded and "entries_applied=1" in seeded[0]
        assert "books_skipped_stale=1" in seeded[0]
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeding_drops_the_entry_when_the_trade_itself_is_stale(caplog):
    """Yesterday's tail seeds nothing at all — neither price nor book."""
    old = time.time() - 86_400
    redis = _SeedRedis(_seed_entries(_orderbook_entry(timestamp=old, quote_ts=old)))
    feed = StreamConsumerFeed(
        redis=redis, stream="raw_data", seed_latest=True, seed_max_age_seconds=10.0
    )
    feed.update_symbols(["A05603"])

    with caplog.at_level(logging.INFO, logger="shared.streaming.consumer_feed"):
        await feed.start()
    try:
        assert await feed.get_current_price("A05603") == {}
        assert feed.get_orderbook_snapshot("A05603") == {}
        seeded = [
            r.getMessage()
            for r in caplog.records
            if "tick_stream_seeded" in r.getMessage()
        ]
        assert seeded and "entries_applied=0" in seeded[0]
        assert "entries_skipped_stale=1" in seeded[0]
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_a_live_book_replaces_a_seed_that_carried_none():
    """The gap a stale-book seed leaves closes on the first live two-sided
    entry — the router blocks `orderbook_unavailable` only until then."""
    now = time.time()
    redis = _SeedRedis(
        _seed_entries(_orderbook_entry(timestamp=now, quote_ts=now - 86_400))
    )
    feed = StreamConsumerFeed(
        redis=redis, stream="raw_data", seed_latest=True, seed_max_age_seconds=10.0
    )
    feed.update_symbols(["A05603"])

    await feed.start()
    try:
        assert feed.get_orderbook_snapshot("A05603") == {}
        feed._apply_entry(_orderbook_entry(timestamp=now, quote_ts=now))
        assert feed.get_orderbook_snapshot("A05603")["bid_price_1"] == 331.18
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_a_symbol_filtered_entry_does_not_count_as_a_skipped_book(caplog):
    """An entry the symbol filter dropped had no book to skip; counting it
    would read as this feed's symbol having a stale book."""
    now = time.time()
    redis = _SeedRedis(
        _seed_entries(
            _orderbook_entry(symbol="A99999", timestamp=now, quote_ts=now - 86_400)
        )
    )
    feed = StreamConsumerFeed(
        redis=redis, stream="raw_data", seed_latest=True, seed_max_age_seconds=10.0
    )
    feed.update_symbols(["A05603"])

    with caplog.at_level(logging.INFO, logger="shared.streaming.consumer_feed"):
        await feed.start()
    try:
        seeded = [
            r.getMessage()
            for r in caplog.records
            if "tick_stream_seeded" in r.getMessage()
        ]
        assert seeded and "books_skipped_stale=0" in seeded[0]
        assert "entries_applied=0" in seeded[0]
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_seeding_counts_only_entries_it_actually_applied(caplog):
    """entries_applied must not count entries filtered out by symbol, or the
    log reads as a successful seed of a stream that had nothing for us."""
    redis = _SeedRedis(_seed_entries(_orderbook_entry(symbol="A99999")))
    feed = StreamConsumerFeed(redis=redis, stream="raw_data", seed_latest=True)
    feed.update_symbols(["A05603"])

    with caplog.at_level(logging.INFO, logger="shared.streaming.consumer_feed"):
        await feed.start()
    try:
        seeded = [
            r.getMessage()
            for r in caplog.records
            if "tick_stream_seeded" in r.getMessage()
        ]
        assert seeded and "entries_read=1" in seeded[0]
        assert "entries_applied=0" in seeded[0]
        assert "books_cached=0" in seeded[0]
    finally:
        await feed.stop()


@pytest.mark.asyncio
async def test_an_entry_without_quote_ts_seeds_the_price_not_the_book():
    """Pre-quote_ts entries have no book clock, so under a bound the
    conservative reading applies: price yes, book no."""
    now = time.time()
    redis = _SeedRedis(_seed_entries(_orderbook_entry(timestamp=now)))
    feed = StreamConsumerFeed(
        redis=redis, stream="raw_data", seed_latest=True, seed_max_age_seconds=10.0
    )
    feed.update_symbols(["A05603"])

    await feed.start()
    try:
        assert (await feed.get_current_price("A05603"))["close"] == 331.20
        assert feed.get_orderbook_snapshot("A05603") == {}
    finally:
        await feed.stop()
