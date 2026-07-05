"""Tests for StreamConsumerFeed (Redis tick stream → price cache + indicator push)."""

from __future__ import annotations

import logging
from datetime import datetime

import pytest

from services.trading.stream_consumer_feed import (
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

    monkeypatch.setattr(
        "services.trading.stream_consumer_feed.asyncio.sleep", fake_sleep
    )
    caplog.set_level(logging.ERROR, logger="services.trading.stream_consumer_feed")

    await feed._read_loop()

    assert redis.calls == 3
    assert sleep_calls == [0.5, 0.5, 0.5]
    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "event=tick_stream_read_error stream=market:ticks sleep_seconds=0.5"
    ]
    assert caplog.records[0].exc_info is not None
