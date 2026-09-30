"""futures:daily_reference read-model — publish/read, shared prefetch, config."""

from __future__ import annotations

import logging
from datetime import datetime, time

import fakeredis
import pytest

from shared.decision.context import (
    load_futures_close_from_config,
    load_futures_open_from_config,
)
from shared.strategy.market_time import KST
from shared.streaming import daily_reference as mod
from shared.streaming.daily_reference import (
    SOURCE_KIS_REST,
    DailyReferenceConfig,
    DailyReferenceSchedule,
    daily_reference_key,
    fetch_futures_prev_close,
    load_daily_reference_config,
    load_daily_reference_schedule,
    prefetch_and_publish_futures_daily_references,
    publish_futures_daily_reference,
    read_futures_daily_reference,
)

_SYMBOL = "A05609"
_OTHER = "A01609"
# 2026-09-15 is a KRX trading day (Tuesday); 2026-09-12 is a Saturday.
_NOW = datetime(2026, 9, 15, 9, 0, tzinfo=KST)
_NON_FINITE = [float("nan"), float("inf"), float("-inf")]


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


def _publish(redis, **overrides):
    kwargs = {
        "symbol": _SYMBOL,
        "prev_close": 411.25,
        "source": SOURCE_KIS_REST,
        "producer": "trader-futures",
        "asof": _NOW,
    }
    kwargs.update(overrides)
    return publish_futures_daily_reference(redis, **kwargs)


class _KISClient:
    """Stands in for KISClient — only the futures current-price call is used."""

    def __init__(self, values: dict[str, object]):
        self._values = values
        self.calls: list[str] = []

    async def _get_futures_price(self, symbol):
        self.calls.append(symbol)
        value = self._values[symbol]
        if isinstance(value, Exception):
            raise value
        return {"price": 412.0, "prev_close": value}


class _Loader:
    """ConfigLoader stand-in returning a fixed document."""

    def __init__(self, document):
        self._document = document

    def load(self, _path):
        if isinstance(self._document, Exception):
            raise self._document
        return self._document


# ---------------------------------------------------------------------------
# publish / read
# ---------------------------------------------------------------------------


def test_publish_then_read_round_trips_every_field(redis_client):
    assert _publish(redis_client) is True

    payload = read_futures_daily_reference(redis_client, _SYMBOL)
    assert payload == {
        "prev_close": 411.25,
        "source": SOURCE_KIS_REST,
        "asof_ts": "2026-09-15T09:00:00+09:00",
        "producer": "trader-futures",
    }


def test_publish_sets_the_configured_ttl_and_replaces_the_whole_hash(redis_client):
    """DEL inside the pipeline: no field or TTL-less state from an earlier writer
    survives a publish."""
    key = daily_reference_key(_SYMBOL)
    redis_client.hset(key, mapping={"prev_close": "1.0", "legacy_field": "x"})
    assert redis_client.ttl(key) == -1

    assert _publish(redis_client) is True

    assert 0 < redis_client.ttl(key) <= load_daily_reference_config().ttl_seconds
    assert "legacy_field" not in redis_client.hgetall(key)


def test_publish_never_leaves_a_key_without_ttl_when_the_transaction_fails(
    redis_client, caplog
):
    """R2 regression: HSET then a failing EXPIRE left a TTL -1 key. The
    commands now commit together or not at all."""

    class _FailingExecRedis:
        """Direct HSET/EXPIRE would succeed; only the transaction fails."""

        def __init__(self, inner):
            self._inner = inner

        # Direct DEL/HSET pass through, so a non-transactional implementation
        # reaches the failing EXPIRE and leaves a TTL -1 key (the R2 defect)
        # instead of dying early on a missing method.
        def delete(self, *args, **kwargs):
            return self._inner.delete(*args, **kwargs)

        def hset(self, *args, **kwargs):
            return self._inner.hset(*args, **kwargs)

        def expire(self, *_args, **_kwargs):
            raise ConnectionError("connection dropped before EXPIRE")

        def pipeline(self, transaction=True):
            pipe = self._inner.pipeline(transaction=transaction)

            def _execute(*_args, **_kwargs):
                raise ConnectionError("connection dropped during EXEC")

            pipe.execute = _execute
            return pipe

    with caplog.at_level("WARNING"):
        ok = _publish(_FailingExecRedis(redis_client))

    assert ok is False
    assert redis_client.exists(daily_reference_key(_SYMBOL)) == 0
    assert "daily_reference publish failed" in caplog.text


def test_publish_swallows_a_redis_failure(caplog):
    """Best-effort by contract: the trading path that produced the value is
    never perturbed by a Redis outage."""

    class _BrokenRedis:
        def pipeline(self, *_a, **_kw):
            raise ConnectionError("redis down")

    with caplog.at_level("WARNING"):
        ok = _publish(_BrokenRedis())
    assert ok is False
    assert "daily_reference publish failed" in caplog.text


@pytest.mark.parametrize("bad", [0.0, -1.0, *_NON_FINITE])
def test_publish_refuses_a_non_finite_or_non_positive_prev_close(redis_client, bad):
    """A 0.0 reference is the blind state this model exists to fix; nan/inf
    slipped past the old ``<= 0`` guard and were stored as "nan"."""
    assert _publish(redis_client, prev_close=bad) is False
    assert redis_client.exists(daily_reference_key(_SYMBOL)) == 0


def test_read_returns_none_when_the_key_is_absent(redis_client):
    assert read_futures_daily_reference(redis_client, _OTHER) is None


@pytest.mark.parametrize("stored", ["nan", "inf", "-inf", "0", "n/a"])
def test_read_rejects_an_unusable_stored_prev_close(redis_client, stored):
    redis_client.hset(
        daily_reference_key(_SYMBOL),
        mapping={"prev_close": stored, "asof_ts": "2026-09-15T09:00:00+09:00"},
    )
    assert read_futures_daily_reference(redis_client, _SYMBOL) is None


def test_read_decodes_a_byte_valued_hash():
    """A client built without decode_responses must not break the consumer."""

    class _BytesRedis:
        def hgetall(self, _key):
            return {
                b"prev_close": b"411.25",
                b"source": b"kis_rest",
                b"asof_ts": b"2026-09-15T09:00:00+09:00",
                b"producer": b"trader-futures",
            }

    payload = read_futures_daily_reference(_BytesRedis(), _SYMBOL)
    assert payload is not None
    assert payload["prev_close"] == 411.25
    assert payload["producer"] == "trader-futures"


def test_read_never_raises_on_a_redis_failure():
    class _BrokenRedis:
        def hgetall(self, _key):
            raise ConnectionError("redis down")

    assert read_futures_daily_reference(_BrokenRedis(), _SYMBOL) is None


def test_naive_asof_is_interpreted_as_kst(redis_client):
    """KST-native by repo rule: a naive timestamp is never read as UTC."""
    _publish(redis_client, asof=datetime(2026, 9, 15, 8, 45))
    payload = read_futures_daily_reference(redis_client, _SYMBOL)
    assert payload is not None
    assert payload["asof_ts"] == "2026-09-15T08:45:00+09:00"


def test_asof_defaults_to_now_kst(redis_client, monkeypatch):
    monkeypatch.setattr(mod, "now_kst", lambda: _NOW)
    _publish(redis_client, asof=None)
    payload = read_futures_daily_reference(redis_client, _SYMBOL)
    assert payload is not None
    assert payload["asof_ts"] == "2026-09-15T09:00:00+09:00"


async def test_fetch_prev_close_reads_the_kis_current_price_field():
    client = _KISClient({_SYMBOL: 411.25})
    assert await fetch_futures_prev_close(client, _SYMBOL) == 411.25
    assert client.calls == [_SYMBOL]


async def test_fetch_prev_close_is_zero_when_the_field_is_missing():
    class _Client:
        async def _get_futures_price(self, _symbol):
            return {"price": 412.0}

    assert await fetch_futures_prev_close(_Client(), _SYMBOL) == 0.0


# ---------------------------------------------------------------------------
# prefetch_and_publish_futures_daily_references (R3: one path, both producers)
# ---------------------------------------------------------------------------


async def test_prefetch_publishes_every_usable_symbol(redis_client):
    kis = _KISClient({_SYMBOL: 411.25, _OTHER: 820.5})

    result = await prefetch_and_publish_futures_daily_references(
        kis, [_SYMBOL, _OTHER], producer="market-ingest", redis=redis_client, asof=_NOW
    )

    assert result.prev_closes == {_SYMBOL: 411.25, _OTHER: 820.5}
    assert result.published_all([_SYMBOL, _OTHER])
    assert kis.calls == [_SYMBOL, _OTHER]
    payload = read_futures_daily_reference(redis_client, _OTHER)
    assert payload is not None
    assert payload["producer"] == "market-ingest"
    assert payload["source"] == SOURCE_KIS_REST
    assert payload["asof_ts"] == "2026-09-15T09:00:00+09:00"


@pytest.mark.parametrize(
    ("value", "log_fragment"),
    [
        (ConnectionError("KIS unreachable"), "prev_close prefetch failed for A05609"),
        (0, "prev_close prefetch returned 0.0 for A05609"),
        (float("nan"), "prev_close prefetch returned nan for A05609"),
        (float("inf"), "prev_close prefetch returned inf for A05609"),
    ],
)
async def test_prefetch_warns_and_skips_only_the_unusable_symbol(
    redis_client, caplog, value, log_fragment
):
    kis = _KISClient({_SYMBOL: value, _OTHER: 820.5})

    with caplog.at_level("WARNING"):
        result = await prefetch_and_publish_futures_daily_references(
            kis, [_SYMBOL, _OTHER], producer="market-ingest", redis=redis_client
        )

    assert log_fragment in caplog.text
    assert result.prev_closes == {_OTHER: 820.5}
    assert result.published == frozenset({_OTHER})
    assert not result.published_all([_SYMBOL, _OTHER])
    assert read_futures_daily_reference(redis_client, _SYMBOL) is None


async def test_prefetch_keeps_values_when_redis_is_unavailable(monkeypatch, caplog):
    """The orchestrator's in-process cache must not depend on Redis."""
    calls = {"n": 0}

    def _boom():
        calls["n"] += 1
        raise ConnectionError("redis down")

    monkeypatch.setattr(
        "shared.streaming.client.RedisClient.get_client", staticmethod(_boom)
    )
    kis = _KISClient({_SYMBOL: 411.25, _OTHER: 820.5})

    with caplog.at_level("WARNING"):
        result = await prefetch_and_publish_futures_daily_references(
            kis, [_SYMBOL, _OTHER], producer="trader-futures"
        )

    assert result.prev_closes == {_SYMBOL: 411.25, _OTHER: 820.5}
    assert result.published == frozenset()
    assert calls["n"] == 1, "Redis is resolved once per call, not per symbol"
    assert "daily_reference publish failed" in caplog.text


async def test_prefetch_publishes_with_the_configured_ttl(redis_client, monkeypatch):
    """N2: the helper path must use the YAML TTL, not a literal."""
    monkeypatch.setattr(
        mod,
        "load_daily_reference_config",
        lambda: DailyReferenceConfig(ttl_seconds=12_345),
    )

    await prefetch_and_publish_futures_daily_references(
        _KISClient({_SYMBOL: 411.25}),
        [_SYMBOL],
        producer="market-ingest",
        redis=redis_client,
    )

    assert 12_340 <= redis_client.ttl(daily_reference_key(_SYMBOL)) <= 12_345


async def test_prefetch_logs_failures_at_the_requested_level(monkeypatch, caplog):
    """A retrying caller can quiet the per-symbol lines — KIS, value, and Redis
    failures alike — without losing them at DEBUG."""

    def _boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr(
        "shared.streaming.client.RedisClient.get_client", staticmethod(_boom)
    )
    kis = _KISClient({_SYMBOL: ConnectionError("KIS"), _OTHER: 0, "A05612": 411.25})

    with caplog.at_level(logging.DEBUG, logger="shared.streaming.daily_reference"):
        await prefetch_and_publish_futures_daily_references(
            kis,
            [_SYMBOL, _OTHER, "A05612"],
            producer="market-ingest",
            failure_log_level=logging.DEBUG,
        )

    failures = [
        r
        for r in caplog.records
        if "fail" in r.getMessage() or "returned" in r.getMessage()
    ]
    assert len(failures) == 3, [r.getMessage() for r in caplog.records]
    assert {r.levelno for r in failures} == {logging.DEBUG}


async def test_prefetch_with_nothing_usable_never_touches_redis(monkeypatch):
    def _unexpected():
        raise AssertionError("Redis resolved with nothing to publish")

    monkeypatch.setattr(
        "shared.streaming.client.RedisClient.get_client", staticmethod(_unexpected)
    )
    result = await prefetch_and_publish_futures_daily_references(
        _KISClient({_SYMBOL: 0}), [_SYMBOL], producer="trader-futures"
    )
    assert result.prev_closes == {}
    assert result.published == frozenset()


# ---------------------------------------------------------------------------
# config (R6: no silent fallback) and schedule
# ---------------------------------------------------------------------------


def test_configured_values_come_from_the_yaml():
    """The YAML value — not a literal in a call site — bounds the key."""
    cfg = load_daily_reference_config()
    assert cfg.ttl_seconds == 86_400
    assert cfg.poll_seconds == 60.0
    assert cfg.open_offset_minutes == 0


@pytest.mark.parametrize(
    ("document", "log_fragment"),
    [
        ({"futures_contract": {}}, "has no daily_reference section"),
        ({"daily_reference": {"poll_seconds": 60}}, "ttl_seconds is missing"),
        (OSError("unreadable"), "futures_contract.yaml unreadable"),
    ],
)
def test_a_missing_ttl_setting_warns_instead_of_defaulting_silently(
    monkeypatch, caplog, document, log_fragment
):
    monkeypatch.setattr("shared.config.loader.ConfigLoader", _Loader(document))
    with caplog.at_level("WARNING"):
        cfg = load_daily_reference_config()
    assert cfg.ttl_seconds == mod._DEFAULT_TTL_SECONDS
    assert log_fragment in caplog.text


@pytest.mark.parametrize(
    ("name", "bad"),
    [
        ("ttl_seconds", 0),
        ("ttl_seconds", "forever"),
        ("poll_seconds", 5),
        ("open_offset_minutes", -1),
    ],
)
def test_an_invalid_setting_warns_and_uses_the_fallback(monkeypatch, caplog, name, bad):
    document = {
        "daily_reference": {
            "ttl_seconds": 86_400,
            "poll_seconds": 60,
            "open_offset_minutes": 0,
            name: bad,
        }
    }
    monkeypatch.setattr("shared.config.loader.ConfigLoader", _Loader(document))
    with caplog.at_level("WARNING"):
        cfg = load_daily_reference_config()
    assert getattr(cfg, name) == getattr(DailyReferenceConfig(), name)
    assert f"daily_reference.{name}={bad!r} is invalid" in caplog.text


def test_schedule_window_is_open_minus_offset_until_the_futures_close():
    hour, minute = load_futures_open_from_config()
    schedule = load_daily_reference_schedule(
        DailyReferenceConfig(
            ttl_seconds=86_400, poll_seconds=90, open_offset_minutes=10
        )
    )
    open_minutes = hour * 60 + minute
    assert schedule.poll_seconds == 90
    assert schedule.publish_from == time(
        (open_minutes - 10) // 60, (open_minutes - 10) % 60
    )
    assert schedule.publish_until == time(*load_futures_close_from_config())


def test_schedule_is_due_only_on_a_trading_day_inside_the_window():
    schedule = DailyReferenceSchedule(
        poll_seconds=60, publish_from=time(8, 45), publish_until=time(15, 45)
    )

    assert not schedule.is_due(datetime(2026, 9, 15, 8, 44, 59, tzinfo=KST))
    assert schedule.is_due(datetime(2026, 9, 15, 8, 45, tzinfo=KST))
    assert schedule.is_due(datetime(2026, 9, 15, 15, 44, 59, tzinfo=KST))
    assert not schedule.is_due(datetime(2026, 9, 15, 15, 45, tzinfo=KST)), "close"
    assert not schedule.is_due(datetime(2026, 9, 15, 20, 0, tzinfo=KST))
    assert not schedule.window_closed(datetime(2026, 9, 15, 15, 44, 59, tzinfo=KST))
    assert schedule.window_closed(datetime(2026, 9, 15, 15, 45, tzinfo=KST))
    assert not schedule.is_due(datetime(2026, 9, 12, 10, 0, tzinfo=KST)), "Saturday"
    # KST-native: 23:50 UTC on the 14th is 08:50 KST on the 15th.
    assert schedule.is_due(datetime.fromisoformat("2026-09-14T23:50:00+00:00"))
