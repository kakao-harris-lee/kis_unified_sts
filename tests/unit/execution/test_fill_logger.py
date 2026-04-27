"""Tests for shared/execution/fill_logger.py — Phase 4 Task 3."""

from datetime import datetime
from unittest.mock import AsyncMock

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
    ch = AsyncMock()
    fl = FillLogger(redis=redis, ch_client=ch, stream=_STREAM, maxlen=1000)
    await fl.log_fill(**_payload())
    entries = await redis.xrange(_STREAM)
    assert len(entries) == 1
    assert entries[0][1][b"signal_id"] == b"sig-1"
    assert entries[0][1][b"order_id"] == b"ord-1"
    assert entries[0][1][b"order_type"] == b"limit_passive"


@pytest.mark.asyncio
async def test_stream_has_ttl_after_log_fill(redis):
    ch = AsyncMock()
    fl = FillLogger(redis=redis, ch_client=ch, stream=_STREAM, maxlen=1000)
    await fl.log_fill(**_payload())
    ttl = await redis.ttl(_STREAM)
    assert 0 < ttl <= _STREAM_TTL_SECONDS


@pytest.mark.asyncio
async def test_log_fill_batches_ch_writes(redis):
    ch = AsyncMock()
    fl = FillLogger(
        redis=redis, ch_client=ch, stream=_STREAM, maxlen=1000, ch_batch_size=10
    )
    for i in range(9):
        await fl.log_fill(**_payload(order_id=f"ord-{i}"))
    ch.execute.assert_not_awaited()
    await fl.log_fill(**_payload(order_id="ord-9"))
    ch.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_explicit_flush(redis):
    ch = AsyncMock()
    fl = FillLogger(
        redis=redis, ch_client=ch, stream=_STREAM, maxlen=1000, ch_batch_size=100
    )
    await fl.log_fill(**_payload())
    ch.execute.assert_not_awaited()
    await fl.flush()
    ch.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_flush_noop_when_empty(redis):
    ch = AsyncMock()
    fl = FillLogger(redis=redis, ch_client=ch, stream=_STREAM, maxlen=1000)
    await fl.flush()
    ch.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_log_fill_reraises_ch_failure(redis):
    ch = AsyncMock()
    ch.execute.side_effect = RuntimeError("clickhouse down")
    fl = FillLogger(
        redis=redis, ch_client=ch, stream=_STREAM, maxlen=1000, ch_batch_size=1
    )
    with pytest.raises(RuntimeError, match="clickhouse down"):
        await fl.log_fill(**_payload())


@pytest.mark.asyncio
async def test_explicit_flush_reraises_ch_failure(redis):
    ch = AsyncMock()
    fl = FillLogger(
        redis=redis, ch_client=ch, stream=_STREAM, maxlen=1000, ch_batch_size=100
    )
    await fl.log_fill(**_payload())
    ch.execute.side_effect = RuntimeError("clickhouse down")
    with pytest.raises(RuntimeError, match="clickhouse down"):
        await fl.flush()


@pytest.mark.asyncio
async def test_ch_row_uses_naive_datetime(redis):
    ch = AsyncMock()
    fl = FillLogger(
        redis=redis, ch_client=ch, stream=_STREAM, maxlen=1000, ch_batch_size=1
    )
    await fl.log_fill(**_payload())
    rows = ch.execute.call_args[0][1]
    assert len(rows) == 1
    row = rows[0]
    requested_at = row[10]  # column index per V3 schema order
    filled_at = row[11]
    assert isinstance(requested_at, datetime)
    assert requested_at.tzinfo is None
    assert isinstance(filled_at, datetime)
    assert filled_at.tzinfo is None


@pytest.mark.asyncio
async def test_latency_ms_computed_from_timestamps(redis):
    ch = AsyncMock()
    fl = FillLogger(
        redis=redis, ch_client=ch, stream=_STREAM, maxlen=1000, ch_batch_size=1
    )
    await fl.log_fill(**_payload(requested_at_ms=1000, filled_at_ms=1325))
    rows = ch.execute.call_args[0][1]
    latency_ms = rows[0][12]
    assert latency_ms == 325


@pytest.mark.asyncio
async def test_latency_ms_clamped_to_zero_on_clock_skew(redis):
    """If filled_at_ms < requested_at_ms (clock skew), latency must not go negative."""
    ch = AsyncMock()
    fl = FillLogger(
        redis=redis, ch_client=ch, stream=_STREAM, maxlen=1000, ch_batch_size=1
    )
    await fl.log_fill(**_payload(requested_at_ms=1500, filled_at_ms=1000))
    rows = ch.execute.call_args[0][1]
    latency_ms = rows[0][12]
    assert latency_ms == 0


@pytest.mark.asyncio
async def test_stream_fields_are_strings(redis):
    ch = AsyncMock()
    fl = FillLogger(redis=redis, ch_client=ch, stream=_STREAM, maxlen=1000)
    await fl.log_fill(**_payload())
    entries = await redis.xrange(_STREAM)
    fields = entries[0][1]
    assert float(fields[b"requested_price"]) == 331.20
    assert float(fields[b"filled_price"]) == 331.22
    assert float(fields[b"slippage_ticks"]) == 1.0
    assert int(fields[b"quantity"]) == 1
    assert fields[b"venue"] == b"KRX"
    assert fields[b"trade_role"] == b"entry"
