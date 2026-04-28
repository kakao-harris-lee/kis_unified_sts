"""Tests for services/kill_switch/main.py — Phase 4 Task 13."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.kill_switch.main import (
    ApiErrorRateCondition,
    ClickHouseInsertFailCondition,
    ConsecutiveLossesCondition,
    DailyLossCondition,
    KillSwitchDaemon,
    NewsPipelineLagCondition,
    WeeklyLossCondition,
)

# ---------------------------------------------------------------------------
# Condition tests — each guards a single rule.
# ---------------------------------------------------------------------------


def _snapshot(**overrides):
    base = {
        "daily_pnl_krw": 0.0,
        "weekly_pnl_krw": 0.0,
        "consecutive_losses": 0,
        "daily_trade_count": 0,
        "atr_90th_percentile": 0.0,
    }
    base.update(overrides)
    return MagicMock(**base)


class TestDailyLoss:
    def test_no_trigger_when_within_limit(self):
        c = DailyLossCondition(limit_pct=0.03, equity_krw=100_000_000)
        snap = _snapshot(daily_pnl_krw=-2_000_000)  # -2% on 100M equity
        assert c.check(snapshot=snap) is False

    def test_trigger_when_loss_exceeds_limit(self):
        c = DailyLossCondition(limit_pct=0.03, equity_krw=100_000_000)
        snap = _snapshot(daily_pnl_krw=-3_500_000)  # -3.5%
        assert c.check(snapshot=snap) is True

    def test_no_trigger_on_profit(self):
        c = DailyLossCondition(limit_pct=0.03, equity_krw=100_000_000)
        snap = _snapshot(daily_pnl_krw=5_000_000)
        assert c.check(snapshot=snap) is False


class TestWeeklyLoss:
    def test_trigger_at_limit(self):
        c = WeeklyLossCondition(limit_pct=0.07, equity_krw=100_000_000)
        snap = _snapshot(weekly_pnl_krw=-7_000_000)
        assert c.check(snapshot=snap) is True

    def test_no_trigger_below_limit(self):
        c = WeeklyLossCondition(limit_pct=0.07, equity_krw=100_000_000)
        snap = _snapshot(weekly_pnl_krw=-5_000_000)
        assert c.check(snapshot=snap) is False


class TestConsecutiveLosses:
    def test_trigger_at_threshold(self):
        c = ConsecutiveLossesCondition(threshold=6)
        snap = _snapshot(consecutive_losses=6)
        assert c.check(snapshot=snap) is True

    def test_no_trigger_below_threshold(self):
        c = ConsecutiveLossesCondition(threshold=6)
        snap = _snapshot(consecutive_losses=5)
        assert c.check(snapshot=snap) is False


class TestApiErrorRate:
    def test_trigger_when_rate_exceeds(self):
        c = ApiErrorRateCondition(threshold=0.2, rate_provider=lambda: 0.3)
        assert c.check(snapshot=None) is True

    def test_no_trigger_when_below(self):
        c = ApiErrorRateCondition(threshold=0.2, rate_provider=lambda: 0.15)
        assert c.check(snapshot=None) is False


class TestNewsPipelineLag:
    def test_trigger_when_lag_exceeds(self):
        c = NewsPipelineLagCondition(threshold_seconds=300, lag_provider=lambda: 400)
        assert c.check(snapshot=None) is True

    def test_no_trigger_when_fresh(self):
        c = NewsPipelineLagCondition(threshold_seconds=300, lag_provider=lambda: 60)
        assert c.check(snapshot=None) is False


class TestClickHouseInsertFail:
    def test_trigger_when_fail_rate_exceeds(self):
        c = ClickHouseInsertFailCondition(threshold=0.1, rate_provider=lambda: 0.2)
        assert c.check(snapshot=None) is True

    def test_no_trigger_in_normal_op(self):
        c = ClickHouseInsertFailCondition(threshold=0.1, rate_provider=lambda: 0.0)
        assert c.check(snapshot=None) is False


# ---------------------------------------------------------------------------
# Daemon-level tests — trigger pipeline, sentinel, telegram, exit.
# ---------------------------------------------------------------------------


class _AlwaysTrigger:
    name = "test_condition"

    def check(self, *, snapshot):  # noqa: D401
        return True

    @property
    def details(self):
        return {"reason": "test"}


class _NeverTrigger:
    name = "never"

    def check(self, *, snapshot):
        return False

    @property
    def details(self):
        return {}


@pytest.fixture
def runtime_state():
    s = AsyncMock()
    s.snapshot = AsyncMock(return_value=MagicMock())
    return s


@pytest.fixture
def telegram():
    return AsyncMock()


@pytest.fixture
def force_close_callback():
    return AsyncMock()


@pytest.mark.asyncio
async def test_no_trigger_keeps_running(runtime_state, telegram, force_close_callback):
    daemon = KillSwitchDaemon(
        runtime_state=runtime_state,
        conditions=[_NeverTrigger()],
        force_close_callback=force_close_callback,
        telegram_client=telegram,
        check_interval_seconds=0.001,
        sentinel_path=None,
    )

    import asyncio

    async def _stop_after():
        await asyncio.sleep(0.01)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    assert daemon.tripped is False
    force_close_callback.assert_not_awaited()
    telegram.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_trigger_fires_force_close_and_telegram(
    runtime_state, telegram, force_close_callback
):
    daemon = KillSwitchDaemon(
        runtime_state=runtime_state,
        conditions=[_AlwaysTrigger()],
        force_close_callback=force_close_callback,
        telegram_client=telegram,
        check_interval_seconds=0.001,
        sentinel_path=None,
    )

    await daemon.run()  # Returns once trigger fires; no separate stop needed

    assert daemon.tripped is True
    assert daemon.triggered_reason == "test_condition"
    force_close_callback.assert_awaited_once_with(reason="test_condition")
    telegram.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_sentinel_written_on_trigger(
    tmp_path, runtime_state, telegram, force_close_callback
):
    sentinel = tmp_path / "tripped"
    daemon = KillSwitchDaemon(
        runtime_state=runtime_state,
        conditions=[_AlwaysTrigger()],
        force_close_callback=force_close_callback,
        telegram_client=telegram,
        check_interval_seconds=0.001,
        sentinel_path=str(sentinel),
    )

    await daemon.run()

    assert sentinel.exists()
    content = sentinel.read_text()
    assert "test_condition" in content


@pytest.mark.asyncio
async def test_already_tripped_short_circuits_on_startup(
    tmp_path, runtime_state, telegram, force_close_callback
):
    sentinel = tmp_path / "tripped"
    sentinel.write_text("previous trip")

    daemon = KillSwitchDaemon(
        runtime_state=runtime_state,
        conditions=[_NeverTrigger()],  # would not fire on its own
        force_close_callback=force_close_callback,
        telegram_client=telegram,
        check_interval_seconds=0.001,
        sentinel_path=str(sentinel),
    )

    await daemon.run()

    # Daemon refused to start because sentinel pre-existed
    assert daemon.tripped is True
    assert daemon.triggered_reason == "sentinel_present"
    # No second force-flat on a recovered tripped state
    force_close_callback.assert_not_awaited()
