from __future__ import annotations

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


def test_publish_stock_tick_to_market_stream():
    client = _FakeRedis()
    cfg = TickStreamPublisherConfig(
        enabled=True,
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
    assert call["fields"]["symbol"] == "005930"
    assert call["fields"]["current_price"] == "71500.0"
    assert call["fields"]["volume"] == "123456.0"
    assert client.expire_calls == [("market:ticks", 86400)]


def test_publish_respects_per_symbol_interval(monkeypatch):
    client = _FakeRedis()
    cfg = TickStreamPublisherConfig(
        enabled=True,
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
