"""M5d cutover verify: stream groups + risk freshness + market_context, mode-aware."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest

import scripts.ops.stock_cutover_verify as m

_KST = ZoneInfo("Asia/Seoul")


def _now() -> datetime:
    return datetime(2026, 6, 8, 10, 0, tzinfo=_KST)


async def _setup_healthy(
    redis: Any, *, stream_sfx: str, key_sfx: str, reset_date: str
) -> None:
    # the consumer groups a healthy pipeline has on each (suffixed) stream
    for stream, group in (
        (f"signal.candidate.stock{stream_sfx}", "stock_risk_filter"),
        (f"signal.final.stock{stream_sfx}", "stock_order_router"),
        (f"order.fill.stock{stream_sfx}", "stock_monitor"),
    ):
        await redis.xadd(stream, {"x": "1"})
        await redis.xgroup_create(stream, group, id="0")
    # risk state (NOT suffixed) + meta reset today
    await redis.hset("risk:state:stock", "daily_trade_count", "0")
    await redis.hset("risk:state:stock:meta", "last_reset_date_kst", reset_date)
    # market context (colon-suffixed key)
    await redis.set(
        f"trading:stock:market_context{key_sfx}",
        '{"regime": "NEUTRAL", "generated_at": "2026-06-08T01:00:00+00:00"}',
    )


@pytest.mark.asyncio
async def test_verify_shadow_healthy_returns_0() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(
        redis, stream_sfx=".shadow", key_sfx=":shadow", reset_date="2026-06-08"
    )
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 0


@pytest.mark.asyncio
async def test_verify_live_healthy_returns_0() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(redis, stream_sfx="", key_sfx="", reset_date="2026-06-08")
    rc = await m.run_verify(mode="live", now_kst=_now(), redis_client=redis)
    assert rc == 0


@pytest.mark.asyncio
async def test_verify_missing_core_group_returns_1() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(
        redis, stream_sfx=".shadow", key_sfx=":shadow", reset_date="2026-06-08"
    )
    await redis.xgroup_destroy("signal.final.stock.shadow", "stock_order_router")
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 1


@pytest.mark.asyncio
async def test_verify_stale_risk_reset_returns_1() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(
        redis, stream_sfx=".shadow", key_sfx=":shadow", reset_date="2026-06-05"
    )
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 1


@pytest.mark.asyncio
async def test_verify_shadow_does_not_inspect_live_keys() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(redis, stream_sfx="", key_sfx="", reset_date="2026-06-08")
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 1


@pytest.mark.asyncio
async def test_verify_missing_market_context_is_warn_not_fail() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(
        redis, stream_sfx=".shadow", key_sfx=":shadow", reset_date="2026-06-08"
    )
    await redis.delete("trading:stock:market_context:shadow")
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 0


@pytest.mark.asyncio
async def test_verify_unknown_mode_returns_1() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    rc = await m.run_verify(mode="unknown", now_kst=_now(), redis_client=redis)
    assert rc == 1


@pytest.mark.asyncio
async def test_verify_both_core_groups_missing_returns_1() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(
        redis, stream_sfx=".shadow", key_sfx=":shadow", reset_date="2026-06-08"
    )
    await redis.xgroup_destroy("signal.candidate.stock.shadow", "stock_risk_filter")
    await redis.xgroup_destroy("signal.final.stock.shadow", "stock_order_router")
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 1


@pytest.mark.asyncio
async def test_verify_positions_count_surfaced() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(
        redis, stream_sfx=".shadow", key_sfx=":shadow", reset_date="2026-06-08"
    )
    await redis.hset("trading:stock:positions:shadow", "005930", '{"qty": 10}')
    await redis.hset("trading:stock:positions:shadow", "000660", '{"qty": 5}')
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 0
