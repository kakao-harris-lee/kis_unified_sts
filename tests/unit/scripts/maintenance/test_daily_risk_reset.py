"""M5c daily risk reset: zero daily counters, preserve cumulative, idempotent, isolate."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest

import scripts.maintenance.daily_risk_reset as m
from shared.risk.runtime_state import RuntimeRiskState

_KST = ZoneInfo("Asia/Seoul")


def _kst_open(year: int, month: int, day: int) -> datetime:
    """08:59 KST on the given date (1 min before the 09:00 session open)."""
    return datetime(year, month, day, 8, 59, tzinfo=_KST)


def _decode(value: object) -> str | None:
    if isinstance(value, (bytes, bytearray)):
        return value.decode()
    return None if value is None else str(value)


@pytest.mark.asyncio
async def test_reset_zeros_daily_preserves_cumulative() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    rs = RuntimeRiskState(redis=redis, asset_class="stock")
    await rs.record_trade(pnl_krw=-5000.0)
    await rs.record_trade(pnl_krw=3000.0)
    await rs.record_loss()  # consecutive_losses -> 1

    now = _kst_open(2026, 6, 8)
    did_reset = await m.reset_asset(redis, "stock", now_kst=now)

    assert did_reset is True
    snap = await rs.snapshot()
    assert snap.daily_trade_count == 0  # reset
    assert snap.daily_pnl_krw == 0.0  # reset
    assert snap.consecutive_losses == 1  # PRESERVED
    assert snap.weekly_pnl_krw == -2000.0  # PRESERVED
    meta = await redis.hget("risk:state:stock:meta", "last_reset_date_kst")
    assert _decode(meta) == "2026-06-08"


@pytest.mark.asyncio
async def test_reset_idempotent_does_not_wipe_midsession() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    rs = RuntimeRiskState(redis=redis, asset_class="stock")
    now = _kst_open(2026, 6, 8)

    assert await m.reset_asset(redis, "stock", now_kst=now) is True
    # a trade lands after the morning reset
    await rs.record_trade(pnl_krw=1000.0)
    # a second run on the SAME KST day must SKIP — never wipe the day's counters
    did_reset = await m.reset_asset(redis, "stock", now_kst=now)

    assert did_reset is False
    snap = await rs.snapshot()
    assert snap.daily_trade_count == 1  # NOT wiped
    assert snap.daily_pnl_krw == 1000.0  # NOT wiped


@pytest.mark.asyncio
async def test_run_reset_resets_both_assets() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    now = _kst_open(2026, 6, 8)

    rc = await m.run_reset(now_kst=now, redis_client=redis)

    assert rc == 0
    for asset in ("stock", "futures"):
        meta = await redis.hget(f"risk:state:{asset}:meta", "last_reset_date_kst")
        assert _decode(meta) == "2026-06-08"


@pytest.mark.asyncio
async def test_run_reset_rc0_when_all_already_reset() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    now = _kst_open(2026, 6, 8)
    assert await m.run_reset(now_kst=now, redis_client=redis) == 0  # first run resets
    # second run same day: every asset skips -> still rc=0, nothing wiped
    assert await m.run_reset(now_kst=now, redis_client=redis) == 0


@pytest.mark.asyncio
async def test_run_reset_isolates_per_asset_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    now = _kst_open(2026, 6, 8)
    attempted: list[str] = []

    async def fake_reset_asset(r: object, asset: str, *, now_kst: datetime) -> bool:
        attempted.append(asset)
        if asset == "futures":
            raise RuntimeError("redis down for futures")
        return True

    monkeypatch.setattr(m, "reset_asset", fake_reset_asset)

    rc = await m.run_reset(now_kst=now, redis_client=redis)

    assert rc == 1  # any asset failure -> exit 1 (cron-mail)
    assert attempted == ["stock", "futures"]  # both attempted (isolation)
