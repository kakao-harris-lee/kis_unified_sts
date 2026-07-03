"""Phase 3C — calendar-window risk state (C1 monthly / C2 soft-reduce / C5 weekly).

Hermetic: fakeredis + injected clock; soft-reduce parameters are passed as
constructor overrides so no config file is read.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest

from shared.risk.runtime_state import RuntimeRiskState
from shared.risk.state import RiskState, RiskStateSnapshot

KST = ZoneInfo("Asia/Seoul")

# Friday 2026-07-03 14:00 KST — week anchor 2026-06-29 (Mon), month 2026-07.
T0 = datetime(2026, 7, 3, 14, 0, tzinfo=KST)
NEXT_MONDAY = datetime(2026, 7, 6, 0, 0, tzinfo=KST)
NEXT_MONTH = datetime(2026, 8, 1, 0, 0, tzinfo=KST)

BASE_KEY = "risk:state:futures"
PERIOD_KEY = "risk:state:futures:period"


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.fixture
def clock():
    return MutableClock(T0)


def make_state(redis, clock, **kwargs) -> RuntimeRiskState:
    kwargs.setdefault("consecutive_loss_soft_threshold", 4)
    kwargs.setdefault("soft_reduce_persist_days", 14)
    return RuntimeRiskState(redis=redis, asset_class="futures", clock=clock, **kwargs)


# ---------------------------------------------------------------------------
# C1 — monthly accumulation + KST month-boundary reset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_trade_accumulates_monthly_pnl(redis, clock):
    state = make_state(redis, clock)
    await state.record_trade(pnl_krw=-5_000_000.0)
    await state.record_trade(pnl_krw=-3_000_000.0)
    snap = await state.snapshot()
    assert snap.monthly_pnl_krw == -8_000_000.0
    assert snap.weekly_pnl_krw == -8_000_000.0
    assert snap.daily_pnl_krw == -8_000_000.0


@pytest.mark.asyncio
async def test_monthly_resets_at_kst_month_boundary(redis, clock):
    # Friday 2026-07-31 belongs to the week anchored Monday 2026-07-27, which
    # spans the month boundary — weekly must survive while monthly resets.
    clock.now = datetime(2026, 7, 31, 10, 0, tzinfo=KST)
    state = make_state(redis, clock)
    await state.record_trade(pnl_krw=-1_000_000.0)

    clock.now = NEXT_MONTH  # Saturday 2026-08-01 00:00 KST, same ISO week
    snap = await state.snapshot()
    assert snap.monthly_pnl_krw == 0.0
    assert snap.weekly_pnl_krw == -1_000_000.0


@pytest.mark.asyncio
async def test_monthly_persists_within_month_across_weeks(redis, clock):
    state = make_state(redis, clock)
    await state.record_trade(pnl_krw=-2_000_000.0)

    clock.now = NEXT_MONDAY + timedelta(days=1)  # new week, same month
    snap = await state.snapshot()
    assert snap.weekly_pnl_krw == 0.0
    assert snap.monthly_pnl_krw == -2_000_000.0


@pytest.mark.asyncio
async def test_period_ttl_covers_remainder_of_month_not_24h(redis, clock):
    state = make_state(redis, clock)
    await state.record_trade(pnl_krw=-100_000.0)
    ttl = await redis.ttl(PERIOD_KEY)
    expected = int((NEXT_MONTH - T0).total_seconds()) + 86400 * 7
    assert abs(ttl - expected) < 10
    assert ttl > 86400  # never the 24 h operational TTL


@pytest.mark.asyncio
async def test_monthly_survives_base_hash_expiry(redis, clock):
    """The monthly latch input must not die with the 24 h main-HASH TTL."""
    state = make_state(redis, clock)
    await state.record_trade(pnl_krw=-15_000_000.0)
    await redis.delete(BASE_KEY)  # simulate 24 h idle expiry

    snap = await state.snapshot()
    assert snap.monthly_pnl_krw == -15_000_000.0
    assert snap.daily_pnl_krw == 0.0


# ---------------------------------------------------------------------------
# C5 — weekly window: explicit KST Monday 00:00 boundary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weekly_resets_at_kst_monday_boundary(redis, clock):
    state = make_state(redis, clock)
    await state.record_trade(pnl_krw=-500_000.0)

    clock.now = NEXT_MONDAY
    snap = await state.snapshot()
    assert snap.weekly_pnl_krw == 0.0

    await state.record_trade(pnl_krw=300_000.0)
    snap = await state.snapshot()
    assert snap.weekly_pnl_krw == 300_000.0


@pytest.mark.asyncio
async def test_weekly_not_reset_before_monday(redis, clock):
    state = make_state(redis, clock)
    await state.record_trade(pnl_krw=-500_000.0)

    clock.now = datetime(2026, 7, 5, 23, 59, tzinfo=KST)  # Sunday night
    snap = await state.snapshot()
    assert snap.weekly_pnl_krw == -500_000.0


@pytest.mark.asyncio
async def test_weekly_survives_idle_beyond_24h(redis, clock):
    """C5: no-trade weekdays must not wipe the weekly accumulation."""
    state = make_state(redis, clock)
    await state.record_trade(pnl_krw=-7_000_000.0)
    await redis.delete(BASE_KEY)  # simulate 24 h idle TTL expiry

    clock.now = T0 + timedelta(days=2)  # Sunday, same week
    snap = await state.snapshot()
    assert snap.weekly_pnl_krw == -7_000_000.0


@pytest.mark.asyncio
async def test_migration_fallback_uses_base_weekly_when_period_absent(redis, clock):
    # Pre-period-hash deployment state: only the main HASH exists.
    legacy = RiskState(redis, "futures")
    snap = RiskStateSnapshot(weekly_pnl_krw=-4_000_000.0)
    await legacy.save(snap)

    state = make_state(redis, clock)
    loaded = await state.snapshot()
    assert loaded.weekly_pnl_krw == -4_000_000.0
    assert loaded.monthly_pnl_krw == -4_000_000.0


@pytest.mark.asyncio
async def test_first_trade_seeds_period_from_base_weekly(redis, clock):
    legacy = RiskState(redis, "futures")
    await legacy.save(RiskStateSnapshot(weekly_pnl_krw=-4_000_000.0))

    state = make_state(redis, clock)
    await state.record_trade(pnl_krw=-1_000_000.0)
    snap = await state.snapshot()
    assert snap.weekly_pnl_krw == -5_000_000.0
    assert snap.monthly_pnl_krw == -5_000_000.0


# ---------------------------------------------------------------------------
# C2 — consecutive-loss soft-reduce persistence window
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fourth_loss_opens_14day_reduce_window(redis, clock):
    state = make_state(redis, clock)
    for _ in range(4):
        await state.record_loss()
    snap = await state.snapshot()
    assert snap.size_reduce_until_kst == (T0 + timedelta(days=14)).isoformat()


@pytest.mark.asyncio
async def test_below_soft_threshold_opens_no_window(redis, clock):
    state = make_state(redis, clock)
    for _ in range(3):
        await state.record_loss()
    snap = await state.snapshot()
    assert snap.size_reduce_until_kst == ""


@pytest.mark.asyncio
async def test_window_survives_wins(redis, clock):
    state = make_state(redis, clock)
    for _ in range(4):
        await state.record_loss()
    await state.record_win()
    snap = await state.snapshot()
    assert snap.consecutive_losses == 0
    assert snap.size_reduce_until_kst == (T0 + timedelta(days=14)).isoformat()


@pytest.mark.asyncio
async def test_further_loss_extends_window(redis, clock):
    state = make_state(redis, clock)
    for _ in range(4):
        await state.record_loss()
    clock.now = T0 + timedelta(days=2)
    await state.record_loss()  # 5th loss re-anchors the window
    snap = await state.snapshot()
    assert snap.size_reduce_until_kst == (T0 + timedelta(days=16)).isoformat()


@pytest.mark.asyncio
async def test_window_survives_restart_and_base_expiry(redis, clock):
    state = make_state(redis, clock)
    for _ in range(4):
        await state.record_loss()

    await redis.delete(BASE_KEY)  # streak counter gone (24 h TTL)
    reborn = make_state(redis, clock)  # fresh instance = process restart
    snap = await reborn.snapshot()
    assert snap.consecutive_losses == 0
    assert snap.size_reduce_until_kst == (T0 + timedelta(days=14)).isoformat()


@pytest.mark.asyncio
async def test_persist_days_zero_disables_window(redis, clock):
    state = make_state(redis, clock, soft_reduce_persist_days=0)
    for _ in range(4):
        await state.record_loss()
    snap = await state.snapshot()
    assert snap.size_reduce_until_kst == ""


@pytest.mark.asyncio
async def test_period_ttl_covers_reduce_window_past_month_end(redis, clock):
    clock.now = datetime(2026, 7, 25, 14, 0, tzinfo=KST)
    state = make_state(redis, clock)
    for _ in range(4):
        await state.record_loss()
    until = clock.now + timedelta(days=14)  # 2026-08-08 > month end
    ttl = await redis.ttl(PERIOD_KEY)
    expected = int((until - clock.now).total_seconds()) + 86400 * 7
    assert abs(ttl - expected) < 10


@pytest.mark.asyncio
async def test_window_preserves_pnl_accumulations(redis, clock):
    state = make_state(redis, clock)
    await state.record_trade(pnl_krw=-1_000_000.0)
    for _ in range(4):
        await state.record_loss()
    snap = await state.snapshot()
    assert snap.weekly_pnl_krw == -1_000_000.0
    assert snap.monthly_pnl_krw == -1_000_000.0


# ---------------------------------------------------------------------------
# Key isolation + daily-reset regression
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_period_key_respects_suffix(redis, clock):
    shadow = RuntimeRiskState(
        redis=redis,
        asset_class="futures",
        key_suffix="shadow",
        clock=clock,
        consecutive_loss_soft_threshold=4,
        soft_reduce_persist_days=14,
    )
    assert shadow._period_key == "risk:state:futures:shadow:period"
    await shadow.record_trade(pnl_krw=-100.0)
    assert await redis.exists("risk:state:futures:shadow:period") == 1
    assert await redis.exists(PERIOD_KEY) == 0


@pytest.mark.asyncio
async def test_reset_daily_does_not_touch_period_windows(redis, clock):
    state = make_state(redis, clock)
    await state.record_trade(pnl_krw=-1_000_000.0)
    await state.reset_daily(now_kst=T0)
    snap = await state.snapshot()
    assert snap.daily_pnl_krw == 0.0
    assert snap.weekly_pnl_krw == -1_000_000.0
    assert snap.monthly_pnl_krw == -1_000_000.0
