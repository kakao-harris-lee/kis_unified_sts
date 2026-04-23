"""Tests for DailyBudget — Redis INCRBYFLOAT with daily cap."""

import fakeredis.aioredis
import pytest

from shared.scoring.budget import BudgetExceeded, DailyBudget


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis()


@pytest.mark.asyncio
async def test_add_below_limit_does_not_raise(redis):
    b = DailyBudget(redis, daily_usd_limit=5.0, key_prefix="test:scorer:cost")
    await b.charge(0.001, date="20260422")  # tiny per-call cost
    assert await b.used_today(date="20260422") == pytest.approx(0.001)


@pytest.mark.asyncio
async def test_add_exceeding_limit_raises(redis):
    b = DailyBudget(redis, daily_usd_limit=0.002, key_prefix="test:scorer:cost")
    await b.charge(0.001, date="20260422")
    with pytest.raises(BudgetExceeded):
        await b.charge(0.002, date="20260422")  # pushes over 0.002


@pytest.mark.asyncio
async def test_per_day_isolation(redis):
    b = DailyBudget(redis, daily_usd_limit=0.005, key_prefix="test:scorer:cost")
    await b.charge(0.004, date="20260422")
    # New day: budget resets.
    await b.charge(0.004, date="20260423")
    assert await b.used_today(date="20260422") == pytest.approx(0.004)
    assert await b.used_today(date="20260423") == pytest.approx(0.004)


@pytest.mark.asyncio
async def test_ttl_set_on_key(redis):
    b = DailyBudget(redis, daily_usd_limit=1.0, key_prefix="test:scorer:cost")
    await b.charge(0.001, date="20260422")
    ttl = await redis.ttl("test:scorer:cost:20260422")
    assert 0 < ttl <= 86400 * 2  # up to 48h retention
