"""futures:daily_reference read-model — publish/read round-trip + TTL source."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import fakeredis
import pytest

from shared.streaming import daily_reference as mod
from shared.streaming.daily_reference import (
    SOURCE_KIS_REST,
    daily_reference_key,
    fetch_futures_prev_close,
    load_daily_reference_ttl_seconds,
    publish_futures_daily_reference,
    read_futures_daily_reference,
)

_KST = ZoneInfo("Asia/Seoul")
_SYMBOL = "A05609"


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


async def test_publish_then_read_round_trips_every_field(redis_client):
    asof = datetime(2026, 9, 10, 8, 45, tzinfo=_KST)
    published = await publish_futures_daily_reference(
        redis_client,
        symbol=_SYMBOL,
        prev_close=411.25,
        source=SOURCE_KIS_REST,
        producer="trader-futures",
        asof=asof,
    )
    assert published is True

    payload = read_futures_daily_reference(redis_client, _SYMBOL)
    assert payload == {
        "prev_close": 411.25,
        "source": SOURCE_KIS_REST,
        "asof_ts": "2026-09-10T08:45:00+09:00",
        "producer": "trader-futures",
    }


async def test_publish_sets_the_configured_ttl(redis_client):
    await publish_futures_daily_reference(
        redis_client,
        symbol=_SYMBOL,
        prev_close=411.25,
        source=SOURCE_KIS_REST,
        producer="trader-futures",
    )
    ttl = redis_client.ttl(daily_reference_key(_SYMBOL))
    assert 0 < ttl <= load_daily_reference_ttl_seconds()


def test_configured_ttl_is_the_repo_default_operational_ttl():
    """The YAML value — not a literal in a call site — bounds the key."""
    assert load_daily_reference_ttl_seconds() == 86_400


async def test_publish_refuses_a_non_positive_prev_close(redis_client):
    """A 0.0 reference is the blind state this model exists to fix."""
    assert (
        await publish_futures_daily_reference(
            redis_client,
            symbol=_SYMBOL,
            prev_close=0.0,
            source=SOURCE_KIS_REST,
            producer="trader-futures",
        )
        is False
    )
    assert read_futures_daily_reference(redis_client, _SYMBOL) is None


async def test_publish_swallows_a_redis_failure(caplog):
    """Best-effort by contract: the trading path that produced the value is
    never perturbed by a Redis outage."""

    class _BrokenRedis:
        def hset(self, *_a, **_kw):
            raise ConnectionError("redis down")

    with caplog.at_level("WARNING"):
        ok = await publish_futures_daily_reference(
            _BrokenRedis(),
            symbol=_SYMBOL,
            prev_close=411.25,
            source=SOURCE_KIS_REST,
            producer="trader-futures",
        )
    assert ok is False
    assert "daily_reference publish failed" in caplog.text


async def test_publish_awaits_an_async_redis_client():
    """The same helper serves a sync singleton and an async client."""
    calls: dict[str, object] = {}

    class _AsyncRedis:
        async def hset(self, key, mapping=None):
            calls["hset"] = (key, mapping)
            return 4

        async def expire(self, key, ttl):
            calls["expire"] = (key, ttl)
            return True

    ok = await publish_futures_daily_reference(
        _AsyncRedis(),
        symbol=_SYMBOL,
        prev_close=411.25,
        source=SOURCE_KIS_REST,
        producer="market-ingest",
        ttl_seconds=60,
    )
    assert ok is True
    assert calls["hset"][0] == daily_reference_key(_SYMBOL)
    assert calls["expire"] == (daily_reference_key(_SYMBOL), 60)


def test_read_returns_none_when_the_key_is_absent(redis_client):
    assert read_futures_daily_reference(redis_client, "A01609") is None


def test_read_decodes_a_byte_valued_hash():
    """A client built without decode_responses must not break the consumer."""

    class _BytesRedis:
        def hgetall(self, _key):
            return {
                b"prev_close": b"411.25",
                b"source": b"kis_rest",
                b"asof_ts": b"2026-09-10T08:45:00+09:00",
                b"producer": b"trader-futures",
            }

    payload = read_futures_daily_reference(_BytesRedis(), _SYMBOL)
    assert payload is not None
    assert payload["prev_close"] == 411.25
    assert payload["producer"] == "trader-futures"


def test_read_rejects_an_unparseable_prev_close():
    class _CorruptRedis:
        def hgetall(self, _key):
            return {"prev_close": "n/a", "asof_ts": "2026-09-10T08:45:00+09:00"}

    assert read_futures_daily_reference(_CorruptRedis(), _SYMBOL) is None


def test_read_never_raises_on_a_redis_failure():
    class _BrokenRedis:
        def hgetall(self, _key):
            raise ConnectionError("redis down")

    assert read_futures_daily_reference(_BrokenRedis(), _SYMBOL) is None


async def test_fetch_prev_close_reads_the_kis_current_price_field():
    class _Client:
        def __init__(self):
            self.calls: list[str] = []

        async def _get_futures_price(self, symbol):
            self.calls.append(symbol)
            return {"price": 412.0, "prev_close": 411.25}

    client = _Client()
    assert await fetch_futures_prev_close(client, _SYMBOL) == 411.25
    assert client.calls == [_SYMBOL]


async def test_fetch_prev_close_is_zero_when_the_field_is_missing():
    class _Client:
        async def _get_futures_price(self, _symbol):
            return {"price": 412.0}

    assert await fetch_futures_prev_close(_Client(), _SYMBOL) == 0.0


async def test_naive_asof_is_interpreted_as_kst(redis_client):
    """KST-native by repo rule: a naive timestamp is never read as UTC."""
    await publish_futures_daily_reference(
        redis_client,
        symbol=_SYMBOL,
        prev_close=411.25,
        source=SOURCE_KIS_REST,
        producer="trader-futures",
        asof=datetime(2026, 9, 10, 8, 45),
    )
    payload = read_futures_daily_reference(redis_client, _SYMBOL)
    assert payload is not None
    assert payload["asof_ts"] == "2026-09-10T08:45:00+09:00"


async def test_asof_defaults_to_now_kst(redis_client):
    await publish_futures_daily_reference(
        redis_client,
        symbol=_SYMBOL,
        prev_close=411.25,
        source=SOURCE_KIS_REST,
        producer="trader-futures",
    )
    payload = read_futures_daily_reference(redis_client, _SYMBOL)
    assert payload is not None
    asof = datetime.fromisoformat(payload["asof_ts"])
    assert asof.utcoffset() == timedelta(hours=9)
    assert abs((datetime.now(_KST) - asof).total_seconds()) < 60


def test_ttl_falls_back_to_the_operational_default_on_a_bad_value(monkeypatch, caplog):
    class _Loader:
        @staticmethod
        def load(_path):
            return {"daily_reference": {"ttl_seconds": 0}}

    monkeypatch.setattr("shared.config.loader.ConfigLoader", _Loader)
    with caplog.at_level("WARNING"):
        assert load_daily_reference_ttl_seconds() == mod._DEFAULT_TTL_SECONDS
    assert "not positive" in caplog.text
