"""Phase 3C C1 — kill_switch monthly_loss condition + month-long latch.

Hermetic: fakeredis + injected clock into RuntimeRiskState; condition unit
tests use MagicMock snapshots like the sibling daily/weekly tests.
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest

from services.kill_switch.config import KillSwitchConfig
from services.kill_switch.main import KillSwitchDaemon, MonthlyLossCondition
from shared.risk.runtime_state import RuntimeRiskState

KST = ZoneInfo("Asia/Seoul")
EQUITY = 100_000_000

T0 = datetime(2026, 7, 10, 14, 0, tzinfo=KST)
NEXT_MONTH = datetime(2026, 8, 1, 0, 0, tzinfo=KST)


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _snapshot(**overrides):
    base = {
        "daily_pnl_krw": 0.0,
        "weekly_pnl_krw": 0.0,
        "monthly_pnl_krw": 0.0,
        "consecutive_losses": 0,
        "daily_trade_count": 0,
        "atr_90th_percentile": 0.0,
    }
    base.update(overrides)
    return MagicMock(**base)


# ---------------------------------------------------------------------------
# Condition unit tests
# ---------------------------------------------------------------------------


class TestMonthlyLossCondition:
    def test_trigger_at_limit(self):
        c = MonthlyLossCondition(limit_pct=0.15, equity_krw=EQUITY)
        assert c.check(snapshot=_snapshot(monthly_pnl_krw=-15_000_000)) is True

    def test_trigger_beyond_limit(self):
        c = MonthlyLossCondition(limit_pct=0.15, equity_krw=EQUITY)
        assert c.check(snapshot=_snapshot(monthly_pnl_krw=-20_000_000)) is True

    def test_no_trigger_below_limit(self):
        c = MonthlyLossCondition(limit_pct=0.15, equity_krw=EQUITY)
        assert c.check(snapshot=_snapshot(monthly_pnl_krw=-14_999_999)) is False

    def test_no_trigger_on_profit(self):
        c = MonthlyLossCondition(limit_pct=0.15, equity_krw=EQUITY)
        assert c.check(snapshot=_snapshot(monthly_pnl_krw=30_000_000)) is False

    def test_no_trigger_on_zero_equity(self):
        c = MonthlyLossCondition(limit_pct=0.15, equity_krw=0)
        assert c.check(snapshot=_snapshot(monthly_pnl_krw=-50_000_000)) is False

    def test_condition_name(self):
        c = MonthlyLossCondition(limit_pct=0.15, equity_krw=EQUITY)
        assert c.name == "monthly_loss"


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


class TestMonthlyLossConfig:
    def test_default_yaml_arms_monthly_loss_at_15pct(self):
        cfg = KillSwitchConfig.from_yaml()
        assert cfg.conditions.monthly_loss.enabled is True
        assert cfg.conditions.monthly_loss.limit_pct == 0.15

    def test_yaml_without_monthly_loss_leaves_condition_unarmed(self, tmp_path):
        custom = tmp_path / "kill_switch.yaml"
        custom.write_text(textwrap.dedent("""
                kill_switch:
                  enabled: true
                  conditions:
                    daily_loss:
                      enabled: true
                      limit_pct: 0.03
                """).strip())
        cfg = KillSwitchConfig.from_yaml(str(custom))
        # limit_pct None → _build_and_run does not instantiate the condition.
        assert cfg.conditions.monthly_loss.limit_pct is None


# ---------------------------------------------------------------------------
# Latch semantics — the condition input holds until the KST month boundary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monthly_latch_holds_until_month_end_then_releases():
    redis = fakeredis.aioredis.FakeRedis(db=1)
    clock = MutableClock(T0)
    state = RuntimeRiskState(
        redis=redis,
        asset_class="futures",
        clock=clock,
        consecutive_loss_soft_threshold=4,
        soft_reduce_persist_days=14,
    )
    cond = MonthlyLossCondition(limit_pct=0.15, equity_krw=EQUITY)

    await state.record_trade(pnl_krw=-15_000_000.0)
    assert cond.check(snapshot=await state.snapshot()) is True

    # Days later, no trades, and the 24 h main HASH has expired — the
    # monthly accumulation must still trip the condition (month-long latch).
    clock.now = T0 + timedelta(days=8)
    await redis.delete("risk:state:futures")
    assert cond.check(snapshot=await state.snapshot()) is True

    # KST month boundary: the monthly window resets and the latch releases.
    clock.now = NEXT_MONTH
    assert cond.check(snapshot=await state.snapshot()) is False


@pytest.mark.asyncio
async def test_daemon_trips_on_monthly_loss_and_writes_sentinel(tmp_path):
    redis = fakeredis.aioredis.FakeRedis(db=1)
    clock = MutableClock(T0)
    state = RuntimeRiskState(
        redis=redis,
        asset_class="futures",
        clock=clock,
        consecutive_loss_soft_threshold=4,
        soft_reduce_persist_days=14,
    )
    await state.record_trade(pnl_krw=-16_000_000.0)

    sentinel = tmp_path / "tripped"
    daemon = KillSwitchDaemon(
        runtime_state=state,
        conditions=[MonthlyLossCondition(limit_pct=0.15, equity_krw=EQUITY)],
        force_close_callback=AsyncMock(),
        telegram_client=AsyncMock(),
        check_interval_seconds=0.001,
        sentinel_path=str(sentinel),
    )

    await daemon.run()

    assert daemon.tripped is True
    assert daemon.triggered_reason == "monthly_loss"
    assert sentinel.exists()
    assert "monthly_loss" in sentinel.read_text()
