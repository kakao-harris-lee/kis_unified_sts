"""StockRiskFilterDaemon.handle_message: pass -> final XADD; reject -> no XADD; poison-pill drop."""

from __future__ import annotations

from datetime import UTC, datetime

import fakeredis.aioredis
import pytest

from services.stock_risk_filter.main import StockRiskFilterDaemon
from shared.risk.config import StockRiskConfig
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState


def _encode(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _candidate(
    code: str = "005930", generated_at_ms: str | None = None
) -> dict[str, str]:
    if generated_at_ms is None:
        # 09:30 KST = 00:30 UTC — inside the 09:00-15:30 stock window.
        generated_at_ms = str(
            int(datetime(2026, 6, 5, 0, 30, tzinfo=UTC).timestamp() * 1000)
        )
    return {
        "signal_id": "sig-1",
        "code": code,
        "name": "n",
        "strategy": "vr_composite",
        "direction": "long",
        "price": "71000.0",
        "quantity": "10",
        "confidence": "0.62",
        "generated_at_ms": generated_at_ms,
        "metadata_json": "{}",
    }


def _build_daemon(redis: fakeredis.aioredis.FakeRedis) -> StockRiskFilterDaemon:
    layer = RiskFilterLayer.from_config(
        config=StockRiskConfig(),
        trading_windows=["09:00-15:30"],
    )
    return StockRiskFilterDaemon(
        redis=redis,
        layer=layer,
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        candidate_stream="signal.candidate.stock.shadow",
        final_stream="signal.final.stock.shadow",
        consumer_group="stock_risk_filter",
        worker_id="test-worker",
        final_maxlen=1000,
        xread_block_ms=100,
        batch_size=10,
    )


@pytest.mark.asyncio
async def test_passing_candidate_emits_final_with_size_multiplier() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", _encode(_candidate()))
    assert ack is True
    entries = await redis.xrange("signal.final.stock.shadow")
    assert len(entries) == 1
    _id, fields = entries[0]
    assert fields[b"code"] == b"005930"
    assert b"size_multiplier" in fields
    assert b"filtered_at_ms" in fields


@pytest.mark.asyncio
async def test_outside_session_rejected_no_final() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    # 20:00 KST = 11:00 UTC — outside 09:00-15:30.
    off = str(int(datetime(2026, 6, 5, 11, 0, tzinfo=UTC).timestamp() * 1000))
    ack = await daemon.handle_message(b"1-0", _encode(_candidate(generated_at_ms=off)))
    assert ack is True  # rejected is audit-only consume
    entries = await redis.xrange("signal.final.stock.shadow")
    assert entries == []


@pytest.mark.asyncio
async def test_unparseable_is_poison_pill_drop() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", {b"price": b"not-a-float", b"code": b"x"})
    assert ack is True  # consumed, not retried
    assert await redis.xrange("signal.final.stock.shadow") == []


@pytest.mark.asyncio
async def test_filter_eval_raises_leaves_pending() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)

    class _Boom:
        def evaluate(self, *a: object, **k: object) -> object:  # noqa: ARG002
            raise RuntimeError("boom")

    daemon.layer = _Boom()  # type: ignore[assignment]
    ack = await daemon.handle_message(b"1-0", _encode(_candidate()))
    assert ack is False  # NO XACK -> message stays pending for retry
    assert await redis.xrange("signal.final.stock.shadow") == []


@pytest.mark.asyncio
async def test_final_stream_has_ttl() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", _encode(_candidate()))
    assert ack is True
    ttl = await redis.ttl("signal.final.stock.shadow")
    assert 0 < ttl <= 86400
