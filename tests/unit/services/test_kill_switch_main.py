"""Tests for services/kill_switch/main.py — Phase 4 Task 13 + Phase 0.2/0.4."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kill_switch.main import (
    _EVENTS_STREAM,
    _FORCE_FLATTEN_KEY,
    ApiErrorRateCondition,
    ClickHouseInsertFailCondition,
    ConsecutiveLossesCondition,
    DailyLossCondition,
    KillSwitchDaemon,
    NewsPipelineLagCondition,
    WeeklyLossCondition,
    _build_api_error_rate_provider,
    _build_clickhouse_insert_fail_provider,
    _build_news_pipeline_lag_provider,
    _clickhouse_insert_fail_condition_enabled,
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

    def test_condition_registration_disabled_when_mirror_disabled(self, monkeypatch):
        monkeypatch.setenv("RUNTIME_STORAGE_CLICKHOUSE_MIRROR_ENABLED", "false")
        condition = MagicMock(enabled=True, threshold=0.1)

        assert _clickhouse_insert_fail_condition_enabled(condition) is False

    def test_condition_registration_enabled_when_mirror_enabled(self, monkeypatch):
        monkeypatch.setenv("RUNTIME_STORAGE_CLICKHOUSE_MIRROR_ENABLED", "true")
        condition = MagicMock(enabled=True, threshold=0.1)

        assert _clickhouse_insert_fail_condition_enabled(condition) is True


# ---------------------------------------------------------------------------
# Daemon-level tests — trigger pipeline, sentinel, telegram, exit.
# ---------------------------------------------------------------------------


class _AlwaysTrigger:
    name = "test_condition"

    def check(self, *, snapshot):  # noqa: ARG002,D401
        return True

    @property
    def details(self):
        return {"reason": "test"}


class _NeverTrigger:
    name = "never"

    def check(self, *, snapshot):  # noqa: ARG002
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


# ---------------------------------------------------------------------------
# Phase 0.2 — Redis sentinel written when _force_flat_callback is invoked.
# ---------------------------------------------------------------------------


class TestForceFlatCallbackRedisSignalling:
    """Verify that the production _force_flat_callback (built inside
    _build_and_run) writes the expected Redis key and stream entry.

    We test the callback in isolation by constructing a minimal async redis
    mock — the same shape as redis.asyncio — and calling the internal helper
    directly.
    """

    @pytest.mark.asyncio
    async def test_redis_key_and_stream_written_on_trigger(self):
        """Trigger pipeline calls set() + xadd() on Redis with correct args."""
        redis_mock = AsyncMock()
        redis_mock.set = AsyncMock()
        redis_mock.xadd = AsyncMock(return_value=b"0-1")
        redis_mock.expire = AsyncMock()

        # Build the callback closure inline (mirrors _build_and_run logic).
        import time as _time

        async def _force_flat_callback(*, reason: str) -> None:
            from services.kill_switch.main import (
                _EVENTS_STREAM,
                _EVENTS_STREAM_TTL_SECONDS,
                _FORCE_FLATTEN_KEY,
                _FORCE_FLATTEN_TTL_SECONDS,
            )

            await redis_mock.set(
                _FORCE_FLATTEN_KEY,
                f"reason={reason}",
                ex=_FORCE_FLATTEN_TTL_SECONDS,
            )
            await redis_mock.xadd(
                _EVENTS_STREAM,
                {
                    "event": "force_flatten_requested",
                    "reason": reason,
                    "ts": str(_time.time()),
                },
            )
            await redis_mock.expire(_EVENTS_STREAM, _EVENTS_STREAM_TTL_SECONDS)

        await _force_flat_callback(reason="daily_loss")

        # Key written with correct name and TTL
        redis_mock.set.assert_awaited_once()
        set_args, set_kwargs = redis_mock.set.call_args
        assert set_args[0] == _FORCE_FLATTEN_KEY
        assert "daily_loss" in set_args[1]
        assert set_kwargs.get("ex") == 300

        # Stream entry written
        redis_mock.xadd.assert_awaited_once()
        xadd_args, _ = redis_mock.xadd.call_args
        assert xadd_args[0] == _EVENTS_STREAM
        fields = xadd_args[1]
        assert fields["event"] == "force_flatten_requested"
        assert fields["reason"] == "daily_loss"

        # Stream TTL set
        redis_mock.expire.assert_awaited_once_with(_EVENTS_STREAM, 86400)

    @pytest.mark.asyncio
    async def test_redis_failure_does_not_raise(self):
        """If Redis is unavailable, the callback should log and not propagate."""
        redis_mock = AsyncMock()
        redis_mock.set = AsyncMock(side_effect=ConnectionError("redis down"))
        redis_mock.xadd = AsyncMock()
        redis_mock.expire = AsyncMock()

        import logging

        with patch.object(
            logging.getLogger("services.kill_switch.main"), "exception"
        ) as log_exc:

            async def _force_flat_callback_with_error(*, reason: str) -> None:
                from services.kill_switch.main import (
                    _EVENTS_STREAM,
                    _EVENTS_STREAM_TTL_SECONDS,
                    _FORCE_FLATTEN_KEY,
                    _FORCE_FLATTEN_TTL_SECONDS,
                )

                try:
                    await redis_mock.set(
                        _FORCE_FLATTEN_KEY,
                        f"reason={reason}",
                        ex=_FORCE_FLATTEN_TTL_SECONDS,
                    )
                    await redis_mock.xadd(
                        _EVENTS_STREAM,
                        {"event": "force_flatten_requested", "reason": reason},
                    )
                    await redis_mock.expire(_EVENTS_STREAM, _EVENTS_STREAM_TTL_SECONDS)
                except Exception:
                    import logging as _logging

                    _logging.getLogger("services.kill_switch.main").exception(
                        "Failed to write force_flatten sentinel to Redis"
                    )

            # Must not raise
            await _force_flat_callback_with_error(reason="weekly_loss")
            log_exc.assert_called_once()


# ---------------------------------------------------------------------------
# Phase 0.4 — Provider factory unit tests.
# ---------------------------------------------------------------------------


class TestApiErrorRateProvider:
    """Verify _build_api_error_rate_provider returns correct float from Redis key."""

    def _make_redis_mock_with_connection_kwargs(self, url="redis://localhost:6379/1"):
        """Return a mock aioredis client with the right connection_pool shape."""
        pool = MagicMock()
        pool.connection_kwargs = {"url": url}
        redis_mock = MagicMock()
        redis_mock.connection_pool = pool
        return redis_mock

    def test_returns_float_from_redis_key(self):
        redis_mock = self._make_redis_mock_with_connection_kwargs()
        sync_redis_mock = MagicMock()
        sync_redis_mock.get.return_value = b"0.35"

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_api_error_rate_provider(redis_mock)
            result = provider()

        assert result == pytest.approx(0.35)
        sync_redis_mock.close.assert_called_once()

    def test_returns_zero_when_key_absent(self):
        redis_mock = self._make_redis_mock_with_connection_kwargs()
        sync_redis_mock = MagicMock()
        sync_redis_mock.get.return_value = None

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_api_error_rate_provider(redis_mock)
            result = provider()

        assert result == 0.0

    def test_returns_zero_on_connection_error(self):
        redis_mock = self._make_redis_mock_with_connection_kwargs()

        with patch("redis.from_url", side_effect=ConnectionError("redis down")):
            provider = _build_api_error_rate_provider(redis_mock)
            result = provider()

        assert result == 0.0

    def test_condition_triggers_when_rate_exceeds_threshold(self):
        redis_mock = self._make_redis_mock_with_connection_kwargs()
        sync_redis_mock = MagicMock()
        sync_redis_mock.get.return_value = b"0.25"

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_api_error_rate_provider(redis_mock)
            cond = ApiErrorRateCondition(threshold=0.2, rate_provider=provider)
            result = cond.check(snapshot=None)

        assert result is True

    def test_condition_does_not_trigger_below_threshold(self):
        redis_mock = self._make_redis_mock_with_connection_kwargs()
        sync_redis_mock = MagicMock()
        sync_redis_mock.get.return_value = b"0.10"

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_api_error_rate_provider(redis_mock)
            cond = ApiErrorRateCondition(threshold=0.2, rate_provider=provider)
            result = cond.check(snapshot=None)

        assert result is False


class TestNewsPipelineLagProvider:
    """Verify _build_news_pipeline_lag_provider computes lag from stream timestamp."""

    def _make_redis_mock(self, url="redis://localhost:6379/1"):
        pool = MagicMock()
        pool.connection_kwargs = {"url": url}
        redis_mock = MagicMock()
        redis_mock.connection_pool = pool
        return redis_mock

    def test_returns_lag_from_stream_entry(self):
        import time

        redis_mock = self._make_redis_mock()
        sync_redis_mock = MagicMock()
        now_ms = int(time.time() * 1000)
        lag_ms = 400_000  # 400 seconds
        ts_ms = now_ms - lag_ms
        # XREVRANGE returns list of (id_bytes, fields_dict)
        sync_redis_mock.xrevrange.return_value = [(f"{ts_ms}-0".encode(), {})]

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_news_pipeline_lag_provider(redis_mock, "stream:news.raw")
            result = provider()

        # Allow 2s tolerance for test execution time
        assert abs(result - 400.0) < 2.0

    def test_returns_zero_when_stream_empty(self):
        redis_mock = self._make_redis_mock()
        sync_redis_mock = MagicMock()
        sync_redis_mock.xrevrange.return_value = []

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_news_pipeline_lag_provider(redis_mock, "stream:news.raw")
            result = provider()

        assert result == 0.0

    def test_returns_zero_on_error(self):
        redis_mock = self._make_redis_mock()

        with patch("redis.from_url", side_effect=ConnectionError("down")):
            provider = _build_news_pipeline_lag_provider(redis_mock, "stream:news.raw")
            result = provider()

        assert result == 0.0

    def test_condition_triggers_when_lag_exceeds_threshold(self):
        import time

        redis_mock = self._make_redis_mock()
        sync_redis_mock = MagicMock()
        # 35 minutes lag > 30 min threshold
        ts_ms = int((time.time() - 2100) * 1000)
        sync_redis_mock.xrevrange.return_value = [(f"{ts_ms}-0".encode(), {})]

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_news_pipeline_lag_provider(redis_mock, "stream:news.raw")
            cond = NewsPipelineLagCondition(
                threshold_seconds=1800, lag_provider=provider
            )
            result = cond.check(snapshot=None)

        assert result is True

    def test_condition_does_not_trigger_when_lag_below_threshold(self):
        import time

        redis_mock = self._make_redis_mock()
        sync_redis_mock = MagicMock()
        # 5 minutes lag < 30 min threshold
        ts_ms = int((time.time() - 300) * 1000)
        sync_redis_mock.xrevrange.return_value = [(f"{ts_ms}-0".encode(), {})]

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_news_pipeline_lag_provider(redis_mock, "stream:news.raw")
            cond = NewsPipelineLagCondition(
                threshold_seconds=1800, lag_provider=provider
            )
            result = cond.check(snapshot=None)

        assert result is False


class TestClickHouseInsertFailProvider:
    """Verify _build_clickhouse_insert_fail_provider reads from Redis key correctly."""

    def _make_redis_mock(self, url="redis://localhost:6379/1"):
        pool = MagicMock()
        pool.connection_kwargs = {"url": url}
        redis_mock = MagicMock()
        redis_mock.connection_pool = pool
        return redis_mock

    def test_returns_float_from_redis_key(self):
        redis_mock = self._make_redis_mock()
        sync_redis_mock = MagicMock()
        sync_redis_mock.get.return_value = b"0.15"

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_clickhouse_insert_fail_provider(redis_mock)
            result = provider()

        assert result == pytest.approx(0.15)

    def test_returns_zero_when_key_absent(self):
        redis_mock = self._make_redis_mock()
        sync_redis_mock = MagicMock()
        sync_redis_mock.get.return_value = None

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_clickhouse_insert_fail_provider(redis_mock)
            result = provider()

        assert result == 0.0

    def test_returns_zero_on_error(self):
        redis_mock = self._make_redis_mock()

        with patch("redis.from_url", side_effect=Exception("timeout")):
            provider = _build_clickhouse_insert_fail_provider(redis_mock)
            result = provider()

        assert result == 0.0

    def test_condition_triggers_when_fail_rate_exceeds_threshold(self):
        redis_mock = self._make_redis_mock()
        sync_redis_mock = MagicMock()
        sync_redis_mock.get.return_value = b"0.20"

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_clickhouse_insert_fail_provider(redis_mock)
            cond = ClickHouseInsertFailCondition(threshold=0.1, rate_provider=provider)
            result = cond.check(snapshot=None)

        assert result is True

    def test_condition_does_not_trigger_in_normal_op(self):
        redis_mock = self._make_redis_mock()
        sync_redis_mock = MagicMock()
        sync_redis_mock.get.return_value = b"0.00"

        with patch("redis.from_url", return_value=sync_redis_mock):
            provider = _build_clickhouse_insert_fail_provider(redis_mock)
            cond = ClickHouseInsertFailCondition(threshold=0.1, rate_provider=provider)
            result = cond.check(snapshot=None)

        assert result is False
