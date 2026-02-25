from __future__ import annotations

import time

from services.monitoring.tick_stream_publisher import (
    TickStreamPublisher,
    TickStreamPublisherConfig,
)


class _FakeRedis:
    def __init__(self) -> None:
        self.xadd_calls: list[dict] = []
        self.expire_calls: list[tuple[str, int]] = []

    def xadd(self, stream: str, fields: dict[str, str], maxlen: int, approximate: bool):
        self.xadd_calls.append(
            {
                "stream": stream,
                "fields": fields,
                "maxlen": maxlen,
                "approximate": approximate,
            }
        )
        return "1-0"

    def expire(self, stream: str, ttl: int):
        self.expire_calls.append((stream, ttl))
        return True


class _SlowFakeRedis(_FakeRedis):
    def __init__(self, delay_seconds: float) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds

    def xadd(self, stream: str, fields: dict[str, str], maxlen: int, approximate: bool):
        time.sleep(self.delay_seconds)
        return super().xadd(stream, fields, maxlen, approximate)


def _wait_until(predicate, timeout_seconds: float = 1.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_publish_stock_tick_to_market_stream():
    client = _FakeRedis()
    cfg = TickStreamPublisherConfig(
        enabled=True,
        async_publish=False,
        stock_stream="market:ticks",
        futures_stream="raw_data",
        stream_maxlen=10000,
        stock_min_interval_seconds=0.0,
        futures_min_interval_seconds=0.0,
        stream_ttl_seconds=86400,
        ttl_refresh_interval_seconds=60.0,
    )
    publisher = TickStreamPublisher(cfg, client=client)

    publisher.publish(
        "stock",
        "005930",
        {
            "close": 71500.0,
            "volume": 123456,
            "timestamp": 1771982309.0,
        },
    )

    assert len(client.xadd_calls) == 1
    call = client.xadd_calls[0]
    assert call["stream"] == "market:ticks"
    assert call["fields"]["asset"] == "stock"
    assert call["fields"]["symbol"] == "005930"
    assert call["fields"]["current_price"] == "71500.0"
    assert call["fields"]["volume"] == "123456.0"
    assert client.expire_calls == [("market:ticks", 86400)]


def test_publish_respects_per_symbol_interval(monkeypatch):
    client = _FakeRedis()
    cfg = TickStreamPublisherConfig(
        enabled=True,
        async_publish=False,
        stock_stream="market:ticks",
        futures_stream="raw_data",
        stream_maxlen=10000,
        stock_min_interval_seconds=1.0,
        futures_min_interval_seconds=0.0,
        stream_ttl_seconds=86400,
        ttl_refresh_interval_seconds=60.0,
    )
    publisher = TickStreamPublisher(cfg, client=client)

    ticks = iter([1000.0, 1000.2])
    monkeypatch.setattr(
        "services.monitoring.tick_stream_publisher.time.time", lambda: next(ticks)
    )

    payload = {"close": 71500.0, "timestamp": 1000.0}
    publisher.publish("stock", "005930", payload)
    publisher.publish("stock", "005930", payload)

    assert len(client.xadd_calls) == 1


def test_publish_skips_invalid_price():
    client = _FakeRedis()
    cfg = TickStreamPublisherConfig(
        enabled=True,
        async_publish=False,
        stock_stream="market:ticks",
        futures_stream="raw_data",
        stream_maxlen=10000,
        stock_min_interval_seconds=0.0,
        futures_min_interval_seconds=0.0,
        stream_ttl_seconds=86400,
        ttl_refresh_interval_seconds=60.0,
    )
    publisher = TickStreamPublisher(cfg, client=client)

    publisher.publish("stock", "005930", {"close": 0})
    publisher.publish("stock", "005930", {"close": ""})

    assert client.xadd_calls == []
    assert client.expire_calls == []


def test_ttl_refresh_is_rate_limited(monkeypatch):
    client = _FakeRedis()
    cfg = TickStreamPublisherConfig(
        enabled=True,
        async_publish=False,
        stock_stream="market:ticks",
        futures_stream="raw_data",
        stream_maxlen=10000,
        stock_min_interval_seconds=0.0,
        futures_min_interval_seconds=0.0,
        stream_ttl_seconds=86400,
        ttl_refresh_interval_seconds=60.0,
    )
    publisher = TickStreamPublisher(cfg, client=client)

    ticks = iter([1000.0, 1001.0, 1062.0])
    monkeypatch.setattr(
        "services.monitoring.tick_stream_publisher.time.time", lambda: next(ticks)
    )

    payload = {"close": 360.0, "timestamp": 1000.0}
    publisher.publish("futures", "A01603", payload)
    publisher.publish("futures", "A01603", payload)
    publisher.publish("futures", "A01603", payload)

    assert len(client.xadd_calls) == 3
    assert client.expire_calls == [("raw_data", 86400), ("raw_data", 86400)]


def test_async_publish_flushes_without_blocking():
    client = _FakeRedis()
    cfg = TickStreamPublisherConfig(
        enabled=True,
        async_publish=True,
        stock_stream="market:ticks",
        futures_stream="raw_data",
        stream_maxlen=10000,
        stock_min_interval_seconds=0.0,
        futures_min_interval_seconds=0.0,
        stream_ttl_seconds=86400,
        ttl_refresh_interval_seconds=60.0,
        queue_maxsize=100,
        flush_batch_size=20,
        worker_wait_seconds=0.01,
    )
    publisher = TickStreamPublisher(cfg, client=client)

    start = time.perf_counter()
    for idx in range(5):
        symbol = f"{idx:06d}"
        publisher.publish(
            "stock",
            symbol,
            {"close": 70000 + idx, "timestamp": 1771982309.0},
        )
    elapsed = time.perf_counter() - start

    try:
        assert elapsed < 0.05
        assert _wait_until(lambda: len(client.xadd_calls) >= 5, timeout_seconds=1.0)
        stats = publisher.get_stats()
        assert stats["enqueued_total"] >= 5
        assert stats["published_total"] >= 5
        assert stats["worker_alive"] is True
    finally:
        publisher.close()


def test_async_queue_overflow_is_dropped():
    client = _SlowFakeRedis(delay_seconds=0.05)
    cfg = TickStreamPublisherConfig(
        enabled=True,
        async_publish=True,
        stock_stream="market:ticks",
        futures_stream="raw_data",
        stream_maxlen=10000,
        stock_min_interval_seconds=0.0,
        futures_min_interval_seconds=0.0,
        stream_ttl_seconds=86400,
        ttl_refresh_interval_seconds=60.0,
        queue_maxsize=3,
        flush_batch_size=1,
        worker_wait_seconds=0.01,
    )
    publisher = TickStreamPublisher(cfg, client=client)

    for idx in range(20):
        symbol = f"{idx:06d}"
        publisher.publish(
            "stock",
            symbol,
            {"close": 70000 + idx, "timestamp": 1771982309.0},
        )

    publisher.close(timeout=3.0)

    stats = publisher.get_stats()
    assert stats["dropped_overflow_total"] > 0
    assert stats["dropped_total"] >= stats["dropped_overflow_total"]
