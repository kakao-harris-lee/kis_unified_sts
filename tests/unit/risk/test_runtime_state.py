"""Tests for shared/risk/runtime_state.py — Phase 4 Task 9."""

from datetime import datetime
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest

from shared.risk.runtime_state import RuntimeRiskState

KST = ZoneInfo("Asia/Seoul")


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.fixture
def state(redis):
    return RuntimeRiskState(redis=redis, asset_class="futures")


@pytest.mark.asyncio
async def test_record_trade_accumulates_daily_pnl(state):
    await state.record_trade(pnl_krw=10_000.0)
    snap = await state.snapshot()
    assert snap.daily_pnl_krw == 10_000.0
    assert snap.weekly_pnl_krw == 10_000.0
    assert snap.daily_trade_count == 1


@pytest.mark.asyncio
async def test_record_trade_handles_negative(state):
    await state.record_trade(pnl_krw=-5_000.0)
    await state.record_trade(pnl_krw=-3_000.0)
    snap = await state.snapshot()
    assert snap.daily_pnl_krw == -8_000.0
    assert snap.weekly_pnl_krw == -8_000.0
    assert snap.daily_trade_count == 2


@pytest.mark.asyncio
async def test_record_loss_increments_streak(state):
    await state.record_loss()
    await state.record_loss()
    snap = await state.snapshot()
    assert snap.consecutive_losses == 2


@pytest.mark.asyncio
async def test_record_win_resets_streak(state):
    await state.record_loss()
    await state.record_loss()
    await state.record_win()
    snap = await state.snapshot()
    assert snap.consecutive_losses == 0


@pytest.mark.asyncio
async def test_reset_daily_zeros_daily_pnl_and_count(state):
    await state.record_trade(pnl_krw=50_000.0)
    await state.record_trade(pnl_krw=-20_000.0)

    await state.reset_daily(now_kst=datetime(2026, 4, 28, 9, 0, tzinfo=KST))

    snap = await state.snapshot()
    assert snap.daily_pnl_krw == 0.0
    assert snap.daily_trade_count == 0
    # weekly NOT reset
    assert snap.weekly_pnl_krw == 30_000.0


@pytest.mark.asyncio
async def test_reset_daily_does_not_touch_consecutive_losses(state):
    await state.record_loss()
    await state.record_loss()
    await state.reset_daily(now_kst=datetime(2026, 4, 28, 9, 0, tzinfo=KST))
    snap = await state.snapshot()
    assert snap.consecutive_losses == 2


@pytest.mark.asyncio
async def test_should_reset_daily_true_on_first_call(state):
    assert (
        await state.should_reset_daily(now_kst=datetime(2026, 4, 27, 9, 0, tzinfo=KST))
        is True
    )


@pytest.mark.asyncio
async def test_should_reset_daily_false_same_day(state):
    await state.reset_daily(now_kst=datetime(2026, 4, 27, 9, 0, tzinfo=KST))
    assert (
        await state.should_reset_daily(
            now_kst=datetime(2026, 4, 27, 14, 30, tzinfo=KST)
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_reset_daily_true_next_day(state):
    await state.reset_daily(now_kst=datetime(2026, 4, 27, 9, 0, tzinfo=KST))
    assert (
        await state.should_reset_daily(now_kst=datetime(2026, 4, 28, 9, 0, tzinfo=KST))
        is True
    )


@pytest.mark.asyncio
async def test_round_trip_through_redis(redis):
    s1 = RuntimeRiskState(redis=redis, asset_class="futures")
    await s1.record_trade(pnl_krw=12_345.0)
    await s1.record_loss()

    # Fresh instance — same Redis backing
    s2 = RuntimeRiskState(redis=redis, asset_class="futures")
    snap = await s2.snapshot()
    assert snap.daily_pnl_krw == 12_345.0
    assert snap.consecutive_losses == 1


@pytest.mark.asyncio
async def test_separate_asset_classes_isolated(redis):
    futures = RuntimeRiskState(redis=redis, asset_class="futures")
    stock = RuntimeRiskState(redis=redis, asset_class="stock")

    await futures.record_trade(pnl_krw=100.0)
    await stock.record_trade(pnl_krw=200.0)

    assert (await futures.snapshot()).daily_pnl_krw == 100.0
    assert (await stock.snapshot()).daily_pnl_krw == 200.0


@pytest.mark.asyncio
async def test_meta_key_has_ttl(state, redis):
    await state.reset_daily(now_kst=datetime(2026, 4, 27, 9, 0, tzinfo=KST))
    ttl = await redis.ttl("risk:state:futures:meta")
    assert 0 < ttl <= 86400 * 7
