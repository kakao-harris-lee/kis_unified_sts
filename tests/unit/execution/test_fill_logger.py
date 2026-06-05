"""Tests for shared/execution/fill_logger.py — Phase 4 Task 3."""

from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest

from shared.execution.fill_logger import FillLogger

_STREAM = "stream:order.fill"
_STREAM_TTL_SECONDS = 86400


def _payload(**overrides):
    base = {
        "signal_id": "sig-1",
        "order_id": "ord-1",
        "symbol": "A05603",
        "side": "long",
        "order_type": "limit_passive",
        "requested_price": 331.20,
        "filled_price": 331.22,
        "tick_size_points": 0.02,
        "slippage_ticks": 1.0,
        "quantity": 1,
        "requested_at_ms": 1_700_000_000_000,
        "filled_at_ms": 1_700_000_000_125,  # 125ms latency
        "venue": "KRX",
        "trade_role": "entry",
        "broker_error_code": "",
    }
    base.update(overrides)
    return base


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis()


@pytest.mark.asyncio
async def test_log_fill_writes_to_stream(redis):
    fl = FillLogger(redis=redis, archive_client=None, stream=_STREAM, maxlen=1000)
    await fl.log_fill(**_payload())
    entries = await redis.xrange(_STREAM)
    assert len(entries) == 1
    assert entries[0][1][b"signal_id"] == b"sig-1"
    assert entries[0][1][b"order_id"] == b"ord-1"
    assert entries[0][1][b"order_type"] == b"limit_passive"


@pytest.mark.asyncio
async def test_stream_has_ttl_after_log_fill(redis):
    fl = FillLogger(redis=redis, archive_client=None, stream=_STREAM, maxlen=1000)
    await fl.log_fill(**_payload())
    ttl = await redis.ttl(_STREAM)
    assert 0 < ttl <= _STREAM_TTL_SECONDS


@pytest.mark.asyncio
async def test_log_fill_ignores_archive_client(redis):
    archive_client = AsyncMock()
    fl = FillLogger(
        redis=redis,
        archive_client=archive_client,
        stream=_STREAM,
        maxlen=1000,
        batch_size=10,
    )
    for i in range(10):
        await fl.log_fill(**_payload(order_id=f"ord-{i}"))
    archive_client.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_log_fill_works_without_archive_client(redis):
    fl = FillLogger(redis=redis, archive_client=None, stream=_STREAM, maxlen=1000)
    await fl.log_fill(**_payload(order_id="ord-no-ch"))
    await fl.flush()

    entries = await redis.xrange(_STREAM)
    assert len(entries) == 1
    assert entries[0][1][b"order_id"] == b"ord-no-ch"


@pytest.mark.asyncio
async def test_log_fill_records_runtime_ledger_when_mirror_disabled(redis):
    ledger = MagicMock()
    fl = FillLogger(
        redis=redis,
        archive_client=None,
        runtime_ledger=ledger,
        stream=_STREAM,
        maxlen=1000,
        asset_class="futures",
    )

    await fl.log_fill(**_payload(order_id="ord-ledger"))

    ledger.record_fill.assert_called_once()
    payload = ledger.record_fill.call_args.args[0]
    assert payload["id"] == "fill:ord-ledger:entry:1700000000125"
    assert payload["idempotency_key"] == payload["id"]
    assert payload["asset_class"] == "futures"
    assert payload["symbol"] == "A05603"
    assert payload["price"] == 331.22
    assert payload["latency_ms"] == 125


@pytest.mark.asyncio
async def test_log_fill_reraises_runtime_ledger_failure(redis):
    ledger = MagicMock()
    ledger.record_fill.side_effect = RuntimeError("ledger down")
    fl = FillLogger(
        redis=redis,
        archive_client=None,
        runtime_ledger=ledger,
        stream=_STREAM,
        maxlen=1000,
    )

    with pytest.raises(RuntimeError, match="ledger down"):
        await fl.log_fill(**_payload(order_id="ord-ledger-fail"))


@pytest.mark.asyncio
async def test_explicit_flush(redis):
    fl = FillLogger(
        redis=redis, archive_client=None, stream=_STREAM, maxlen=1000, batch_size=100
    )
    await fl.log_fill(**_payload())
    await fl.flush()
    entries = await redis.xrange(_STREAM)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_flush_noop_when_empty(redis):
    archive_client = AsyncMock()
    fl = FillLogger(
        redis=redis, archive_client=archive_client, stream=_STREAM, maxlen=1000
    )
    await fl.flush()
    archive_client.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_latency_ms_computed_from_timestamps(redis):
    fl = FillLogger(
        redis=redis, archive_client=None, stream=_STREAM, maxlen=1000, batch_size=1
    )
    await fl.log_fill(**_payload(requested_at_ms=1000, filled_at_ms=1325))
    entries = await redis.xrange(_STREAM)
    assert entries[0][1][b"latency_ms"] == b"325"


@pytest.mark.asyncio
async def test_latency_ms_clamped_to_zero_on_clock_skew(redis):
    """If filled_at_ms < requested_at_ms (clock skew), latency must not go negative."""
    fl = FillLogger(
        redis=redis, archive_client=None, stream=_STREAM, maxlen=1000, batch_size=1
    )
    await fl.log_fill(**_payload(requested_at_ms=1500, filled_at_ms=1000))
    entries = await redis.xrange(_STREAM)
    assert entries[0][1][b"latency_ms"] == b"0"


@pytest.mark.asyncio
async def test_stream_fields_are_strings(redis):
    fl = FillLogger(redis=redis, archive_client=None, stream=_STREAM, maxlen=1000)
    await fl.log_fill(**_payload())
    entries = await redis.xrange(_STREAM)
    fields = entries[0][1]
    assert float(fields[b"requested_price"]) == 331.20
    assert float(fields[b"filled_price"]) == 331.22
    assert float(fields[b"slippage_ticks"]) == 1.0
    assert int(fields[b"quantity"]) == 1
    assert fields[b"venue"] == b"KRX"
    assert fields[b"trade_role"] == b"entry"
