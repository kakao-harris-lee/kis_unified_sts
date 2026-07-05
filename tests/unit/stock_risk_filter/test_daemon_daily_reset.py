"""StockRiskFilterDaemon KST day-boundary daily-counter reset (pre_iteration_gate).

The decoupled M4 pipeline stores ``daily_trade_count`` / ``daily_pnl_krw`` in
``risk:state:stock`` (24 h idle TTL). Nothing in the daemon loop reset those
counters at the KST calendar-day boundary, so within a <24 h weekday-to-weekday
span the trade count accumulated and, once it reached
``risk_stock.max_daily_trades``, every later candidate was silently rejected
(``skip_reason="max_daily_trades"``, observed 2026-07-03).

These tests pin the clock (never a hardcoded ``now()``) and drive the reset hook
directly. They reuse the unchanged ``RuntimeRiskState.should_reset_daily`` /
``reset_daily`` API (same one the M5c cron uses).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest

from services.stock_risk_filter.main import StockRiskFilterDaemon
from shared.risk.config import StockRiskConfig
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState

_KST = ZoneInfo("Asia/Seoul")


def _kst(year: int, month: int, day: int, hour: int = 8, minute: int = 59) -> datetime:
    """Aware KST datetime (default 08:59 — just before the 09:00 session open)."""
    return datetime(year, month, day, hour, minute, tzinfo=_KST)


def _decode(value: object) -> str | None:
    if isinstance(value, (bytes, bytearray)):
        return value.decode()
    return None if value is None else str(value)


def _build_daemon(
    redis: fakeredis.aioredis.FakeRedis,
    *,
    clock,
    runtime_state: RuntimeRiskState | None = None,
) -> StockRiskFilterDaemon:
    layer = RiskFilterLayer.from_config(
        config=StockRiskConfig(),
        trading_windows=["09:00-15:30"],
    )
    return StockRiskFilterDaemon(
        redis=redis,
        layer=layer,
        runtime_state=runtime_state
        or RuntimeRiskState(redis=redis, asset_class="stock"),
        candidate_stream="signal.candidate.stock.shadow",
        final_stream="signal.final.stock.shadow",
        consumer_group="stock_risk_filter",
        worker_id="test-worker",
        final_maxlen=1000,
        xread_block_ms=100,
        batch_size=10,
        clock=clock,
    )


@pytest.mark.asyncio
async def test_pre_iteration_gate_resets_daily_on_new_kst_day() -> None:
    """A leftover count from a prior KST day is zeroed on the first cycle of the new day."""
    redis = fakeredis.aioredis.FakeRedis(db=1)
    rs = RuntimeRiskState(redis=redis, asset_class="stock")

    yesterday = _kst(2026, 7, 2)
    await rs.reset_daily(now_kst=yesterday)  # stamp meta = 2026-07-02
    await rs.record_trade(pnl_krw=-1000.0, now_kst=yesterday)  # leftover count = 1
    await rs.record_loss(now_kst=yesterday)  # consecutive_losses -> 1 (must survive)
    assert (await rs.snapshot()).daily_trade_count == 1

    today = _kst(2026, 7, 3)
    daemon = _build_daemon(redis, clock=lambda: today, runtime_state=rs)

    proceed = await daemon.pre_iteration_gate()

    assert proceed is True  # reset never aborts the consume loop
    snap = await rs.snapshot()
    assert snap.daily_trade_count == 0  # reset at the KST day boundary
    assert snap.daily_pnl_krw == 0.0
    assert snap.weekly_pnl_krw == -1000.0  # cumulative window preserved
    assert snap.consecutive_losses == 1  # cumulative loss streak preserved
    meta = await redis.hget("risk:state:stock:meta", "last_reset_date_kst")
    assert _decode(meta) == "2026-07-03"


@pytest.mark.asyncio
async def test_pre_iteration_gate_no_reset_within_same_kst_day() -> None:
    """Within one KST day the running count is never wiped by the gate."""
    redis = fakeredis.aioredis.FakeRedis(db=1)
    rs = RuntimeRiskState(redis=redis, asset_class="stock")

    today = _kst(2026, 7, 3)
    await rs.reset_daily(now_kst=today)  # stamp meta = 2026-07-03
    await rs.record_trade(pnl_krw=500.0, now_kst=today)  # count = 1
    assert (await rs.snapshot()).daily_trade_count == 1

    daemon = _build_daemon(redis, clock=lambda: today, runtime_state=rs)

    proceed = await daemon.pre_iteration_gate()

    assert proceed is True
    assert (await rs.snapshot()).daily_trade_count == 1  # NOT reset


@pytest.mark.asyncio
async def test_repeated_cycles_same_day_do_not_wipe_midsession_trades() -> None:
    """After the morning reset, later cycles the same day leave mid-session trades intact."""
    redis = fakeredis.aioredis.FakeRedis(db=1)
    rs = RuntimeRiskState(redis=redis, asset_class="stock")

    yesterday = _kst(2026, 7, 2)
    await rs.reset_daily(now_kst=yesterday)
    await rs.record_trade(pnl_krw=-1000.0, now_kst=yesterday)  # leftover count = 1

    today = _kst(2026, 7, 3, 9, 0)
    daemon = _build_daemon(redis, clock=lambda: today, runtime_state=rs)

    await daemon.pre_iteration_gate()  # first cycle of the new day → reset
    assert (await rs.snapshot()).daily_trade_count == 0

    await rs.record_trade(pnl_krw=200.0, now_kst=today)  # a trade lands mid-session
    assert (await rs.snapshot()).daily_trade_count == 1

    for _ in range(3):  # later cycles must not re-reset
        assert await daemon.pre_iteration_gate() is True
    assert (await rs.snapshot()).daily_trade_count == 1


@pytest.mark.asyncio
async def test_restart_midsession_does_not_wipe_already_reset_day() -> None:
    """A fresh daemon (in-memory guard empty) trusts the Redis meta guard — no wipe."""
    redis = fakeredis.aioredis.FakeRedis(db=1)
    rs = RuntimeRiskState(redis=redis, asset_class="stock")

    today = _kst(2026, 7, 3, 10, 0)
    await rs.reset_daily(now_kst=today)  # morning reset already happened
    await rs.record_trade(pnl_krw=1000.0, now_kst=today)
    await rs.record_trade(pnl_krw=1000.0, now_kst=today)
    assert (await rs.snapshot()).daily_trade_count == 2

    # Brand-new daemon instance simulates a mid-session restart.
    daemon = _build_daemon(redis, clock=lambda: today, runtime_state=rs)
    await daemon.pre_iteration_gate()

    assert (
        await rs.snapshot()
    ).daily_trade_count == 2  # preserved via Redis meta guard


@pytest.mark.asyncio
async def test_reset_error_is_swallowed_and_retried_next_cycle(monkeypatch) -> None:
    """A transient Redis error on the reset check must not crash the loop; it retries."""
    redis = fakeredis.aioredis.FakeRedis(db=1)
    rs = RuntimeRiskState(redis=redis, asset_class="stock")

    yesterday = _kst(2026, 7, 2)
    await rs.reset_daily(now_kst=yesterday)
    await rs.record_trade(pnl_krw=-1000.0, now_kst=yesterday)  # leftover count = 1

    today = _kst(2026, 7, 3)
    daemon = _build_daemon(redis, clock=lambda: today, runtime_state=rs)

    real_should = rs.should_reset_daily
    calls = {"n": 0}

    async def flaky_should(*, now_kst):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("redis blip")
        return await real_should(now_kst=now_kst)

    monkeypatch.setattr(rs, "should_reset_daily", flaky_should)

    # First cycle: error swallowed, loop proceeds, no reset, guard NOT advanced.
    assert await daemon.pre_iteration_gate() is True
    assert (await rs.snapshot()).daily_trade_count == 1  # still not reset

    # Second cycle: retried and succeeds.
    assert await daemon.pre_iteration_gate() is True
    assert (await rs.snapshot()).daily_trade_count == 0


@pytest.mark.asyncio
async def test_single_daemon_instance_resets_again_after_crossing_midnight() -> None:
    """One long-lived daemon re-arms its in-memory guard across midnight.

    The production-primary scenario: a single ``StockRiskFilterDaemon`` stays
    up and its clock advances past midnight (not a fresh instance per day). The
    in-memory ``_last_reset_date`` guard must re-arm day1 -> day2 so the second
    day's first cycle fires a fresh reset. A mutable clock holder advances the
    pinned time between cycles (no hardcoded ``now()``).
    """
    redis = fakeredis.aioredis.FakeRedis(db=1)
    rs = RuntimeRiskState(redis=redis, asset_class="stock")

    # Prior day (07-01) already stamped; a leftover count carries into day 1.
    await rs.reset_daily(now_kst=_kst(2026, 7, 1))
    await rs.record_trade(
        pnl_krw=-1000.0, now_kst=_kst(2026, 7, 1)
    )  # leftover count = 1

    clock_holder = {"now": _kst(2026, 7, 2, 9, 0)}  # day 1, mid-session
    daemon = _build_daemon(redis, clock=lambda: clock_holder["now"], runtime_state=rs)

    # Day-1 first cycle resets (meta 07-01 -> 07-02).
    await daemon.pre_iteration_gate()
    assert (await rs.snapshot()).daily_trade_count == 0
    meta_day1 = await redis.hget("risk:state:stock:meta", "last_reset_date_kst")
    assert _decode(meta_day1) == "2026-07-02"

    # Day-1 trades accumulate under the SAME instance.
    await rs.record_trade(pnl_krw=100.0, now_kst=clock_holder["now"])
    await rs.record_trade(pnl_krw=100.0, now_kst=clock_holder["now"])
    assert (await rs.snapshot()).daily_trade_count == 2

    # Same instance crosses midnight into day 2 (00:01 KST).
    clock_holder["now"] = _kst(2026, 7, 3, 0, 1)

    await daemon.pre_iteration_gate()  # day-2 first cycle → in-memory guard re-armed

    snap = await rs.snapshot()
    assert snap.daily_trade_count == 0  # second reset fired after the day rollover
    meta_day2 = await redis.hget("risk:state:stock:meta", "last_reset_date_kst")
    assert _decode(meta_day2) == "2026-07-03"
