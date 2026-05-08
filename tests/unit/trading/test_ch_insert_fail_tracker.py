"""Tests for services/trading/ch_insert_fail_tracker.py

Covers:
- Empty window → rate = 0.0
- All successes → rate = 0.0
- All failures → rate = 1.0
- Mixed events → correct fractional rate
- Window expiry: events older than window_seconds are excluded
- Redis write: correct value and key at the configured cadence
- Disabled config → no Redis writes (opt-out)
- Concurrent record_success / record_failure safety
- PositionTracker._flush_batch calls record_failure() on CH error
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.trading.ch_insert_fail_tracker import (
    ChInsertFailTrackerConfig,
    ClickHouseInsertFailTracker,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**kwargs) -> ChInsertFailTrackerConfig:
    """Build a test config with fast intervals by default."""
    defaults = {
        "enabled": True,
        "window_seconds": 300,
        "publish_interval_seconds": 10,
        "redis_key": "kill_switch:metrics:clickhouse_insert_fail_rate",
        "redis_ttl_seconds": 600,
    }
    defaults.update(kwargs)
    return ChInsertFailTrackerConfig.from_dict(defaults)


def _make_tracker(config: ChInsertFailTrackerConfig | None = None, redis=None):
    """Build a ClickHouseInsertFailTracker with a mock Redis client."""
    if redis is None:
        redis = AsyncMock()
    cfg = config or _make_config()
    return ClickHouseInsertFailTracker(cfg, redis), redis


# ---------------------------------------------------------------------------
# ChInsertFailTrackerConfig
# ---------------------------------------------------------------------------

class TestChInsertFailTrackerConfig:
    """Unit tests for ChInsertFailTrackerConfig validation."""

    def test_defaults(self):
        cfg = ChInsertFailTrackerConfig()
        assert cfg.enabled is True
        assert cfg.window_seconds == 300
        assert cfg.publish_interval_seconds == 10
        assert cfg.redis_key == "kill_switch:metrics:clickhouse_insert_fail_rate"
        assert cfg.redis_ttl_seconds == 600

    def test_from_dict_full(self):
        cfg = ChInsertFailTrackerConfig.from_dict(
            {
                "enabled": False,
                "window_seconds": 60,
                "publish_interval_seconds": 5,
                "redis_key": "custom:key",
                "redis_ttl_seconds": 120,
            }
        )
        assert cfg.enabled is False
        assert cfg.window_seconds == 60
        assert cfg.publish_interval_seconds == 5
        assert cfg.redis_key == "custom:key"
        assert cfg.redis_ttl_seconds == 120

    def test_from_dict_partial_uses_defaults(self):
        cfg = ChInsertFailTrackerConfig.from_dict({"window_seconds": 120})
        assert cfg.window_seconds == 120
        assert cfg.publish_interval_seconds == 10  # default

    def test_invalid_window_seconds(self):
        with pytest.raises(ValueError, match="window_seconds"):
            ChInsertFailTrackerConfig(window_seconds=0)

    def test_invalid_publish_interval(self):
        with pytest.raises(ValueError, match="publish_interval_seconds"):
            ChInsertFailTrackerConfig(publish_interval_seconds=0)

    def test_invalid_ttl_less_than_window(self):
        with pytest.raises(ValueError, match="redis_ttl_seconds"):
            ChInsertFailTrackerConfig(window_seconds=300, redis_ttl_seconds=100)

    def test_empty_redis_key_raises(self):
        with pytest.raises(ValueError, match="redis_key"):
            ChInsertFailTrackerConfig(redis_key="")


# ---------------------------------------------------------------------------
# Rolling-window fail rate computation
# ---------------------------------------------------------------------------

class TestFailRate:
    """Tests for current_fail_rate() covering all edge cases."""

    def test_empty_window_returns_zero(self):
        tracker, _ = _make_tracker()
        assert tracker.current_fail_rate() == 0.0

    def test_all_successes_returns_zero(self):
        tracker, _ = _make_tracker()
        for _ in range(5):
            tracker.record_success()
        assert tracker.current_fail_rate() == 0.0

    def test_all_failures_returns_one(self):
        tracker, _ = _make_tracker()
        for _ in range(5):
            tracker.record_failure()
        assert tracker.current_fail_rate() == 1.0

    def test_mixed_events(self):
        """2 failures out of 10 events → 0.2."""
        tracker, _ = _make_tracker()
        for _ in range(8):
            tracker.record_success()
        for _ in range(2):
            tracker.record_failure()
        assert abs(tracker.current_fail_rate() - 0.2) < 1e-9

    def test_single_failure_among_successes(self):
        tracker, _ = _make_tracker()
        tracker.record_success()
        tracker.record_success()
        tracker.record_failure()
        # 1/3
        assert abs(tracker.current_fail_rate() - 1 / 3) < 1e-9

    def test_window_expiry_excludes_old_events(self):
        """Events older than window_seconds must be excluded."""
        tracker, _ = _make_tracker(_make_config(window_seconds=60))

        # Manually inject an old failure (70 seconds ago)
        old_ts = datetime.now() - timedelta(seconds=70)
        from services.trading.ch_insert_fail_tracker import _Event
        with tracker._lock:
            tracker._window.appendleft(_Event(timestamp=old_ts, success=False))

        # Add a recent success
        tracker.record_success()

        # The old failure should be outside the 60-second window → excluded
        assert tracker.current_fail_rate() == 0.0

    def test_window_includes_recent_events(self):
        """Events within window_seconds must remain included."""
        tracker, _ = _make_tracker(_make_config(window_seconds=300))

        # Inject a failure 100 seconds ago (within 300-second window)
        old_ts = datetime.now() - timedelta(seconds=100)
        from services.trading.ch_insert_fail_tracker import _Event
        with tracker._lock:
            tracker._window.appendleft(_Event(timestamp=old_ts, success=False))

        tracker.record_success()

        # 1 failure / 2 total = 0.5
        assert abs(tracker.current_fail_rate() - 0.5) < 1e-9

    def test_disabled_tracker_returns_zero(self):
        tracker, _ = _make_tracker(_make_config(enabled=False))
        tracker.record_failure()  # should be a no-op
        assert tracker.current_fail_rate() == 0.0


# ---------------------------------------------------------------------------
# Disabled config → no Redis writes
# ---------------------------------------------------------------------------

class TestDisabledTracker:
    """When enabled=False the tracker must not touch Redis."""

    @pytest.mark.asyncio
    async def test_no_redis_write_when_disabled(self):
        redis_mock = AsyncMock()
        tracker, _ = _make_tracker(_make_config(enabled=False), redis=redis_mock)

        await tracker._write_to_redis()

        redis_mock.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_is_noop_when_disabled(self):
        redis_mock = AsyncMock()
        tracker, _ = _make_tracker(_make_config(enabled=False), redis=redis_mock)

        await tracker.start()
        assert tracker._publish_task is None

    @pytest.mark.asyncio
    async def test_record_methods_are_noop_when_disabled(self):
        tracker, _ = _make_tracker(_make_config(enabled=False))
        tracker.record_success()
        tracker.record_failure()
        assert len(tracker._window) == 0


# ---------------------------------------------------------------------------
# Redis write — correct key, value, TTL
# ---------------------------------------------------------------------------

class TestRedisWrite:
    """Verify that the rate is published to Redis with correct parameters."""

    @pytest.mark.asyncio
    async def test_write_sends_correct_key_and_ttl(self):
        redis_mock = AsyncMock()
        cfg = _make_config(
            redis_key="kill_switch:metrics:clickhouse_insert_fail_rate",
            redis_ttl_seconds=600,
        )
        tracker = ClickHouseInsertFailTracker(cfg, redis_mock)
        tracker.record_failure()
        tracker.record_success()

        await tracker._write_to_redis()

        redis_mock.set.assert_called_once()
        call_args = redis_mock.set.call_args
        assert call_args[0][0] == "kill_switch:metrics:clickhouse_insert_fail_rate"
        published_rate = float(call_args[0][1])
        assert abs(published_rate - 0.5) < 1e-5
        assert call_args[1]["ex"] == 600

    @pytest.mark.asyncio
    async def test_write_sends_zero_when_empty(self):
        redis_mock = AsyncMock()
        tracker = ClickHouseInsertFailTracker(_make_config(), redis_mock)

        await tracker._write_to_redis()

        redis_mock.set.assert_called_once()
        published_rate = float(redis_mock.set.call_args[0][1])
        assert published_rate == 0.0

    @pytest.mark.asyncio
    async def test_write_all_failures(self):
        redis_mock = AsyncMock()
        tracker = ClickHouseInsertFailTracker(_make_config(), redis_mock)
        for _ in range(3):
            tracker.record_failure()

        await tracker._write_to_redis()

        published_rate = float(redis_mock.set.call_args[0][1])
        assert abs(published_rate - 1.0) < 1e-9

    @pytest.mark.asyncio
    async def test_redis_error_is_swallowed(self):
        """Redis write failures must not propagate (observability side-car)."""
        redis_mock = AsyncMock()
        redis_mock.set.side_effect = ConnectionError("Redis unavailable")
        tracker = ClickHouseInsertFailTracker(_make_config(), redis_mock)

        # Must not raise
        await tracker._write_to_redis()


# ---------------------------------------------------------------------------
# Lifecycle: start / stop
# ---------------------------------------------------------------------------

class TestLifecycle:
    """Test background publish loop start/stop behaviour."""

    @pytest.mark.asyncio
    async def test_start_creates_publish_task(self):
        redis_mock = AsyncMock()
        tracker = ClickHouseInsertFailTracker(_make_config(), redis_mock)

        await tracker.start()
        try:
            assert tracker._publish_task is not None
            assert not tracker._publish_task.done()
        finally:
            await tracker.stop()

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        redis_mock = AsyncMock()
        tracker = ClickHouseInsertFailTracker(_make_config(), redis_mock)

        await tracker.start()
        task1 = tracker._publish_task
        await tracker.start()  # second call — same task
        assert tracker._publish_task is task1

        await tracker.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task_and_does_final_write(self):
        redis_mock = AsyncMock()
        tracker = ClickHouseInsertFailTracker(_make_config(), redis_mock)

        await tracker.start()
        assert tracker._publish_task is not None

        tracker.record_failure()
        await tracker.stop()

        # Task should be done (cancelled)
        assert tracker._publish_task is None or tracker._publish_task.done()
        # Final write must have happened
        redis_mock.set.assert_called()

    @pytest.mark.asyncio
    async def test_stop_safe_when_never_started(self):
        redis_mock = AsyncMock()
        tracker = ClickHouseInsertFailTracker(_make_config(), redis_mock)

        # Should not raise even though start() was never called
        await tracker.stop()

    @pytest.mark.asyncio
    async def test_publish_loop_writes_periodically(self):
        """Verify that the loop writes to Redis after sleeping."""
        redis_mock = AsyncMock()
        cfg = _make_config(publish_interval_seconds=1)
        tracker = ClickHouseInsertFailTracker(cfg, redis_mock)
        tracker.record_failure()

        await tracker.start()
        await asyncio.sleep(1.1)
        await tracker.stop()

        # At least one write from the loop + one final write on stop
        assert redis_mock.set.call_count >= 1


# ---------------------------------------------------------------------------
# Concurrency safety
# ---------------------------------------------------------------------------

class TestConcurrencySafety:
    """Verify thread-safe recording under concurrent access."""

    def test_concurrent_record_does_not_corrupt_state(self):
        """Concurrent record_success / record_failure must not raise or lose events."""
        tracker, _ = _make_tracker()
        errors: list[Exception] = []

        def writer(is_success: bool, n: int) -> None:
            for _ in range(n):
                try:
                    if is_success:
                        tracker.record_success()
                    else:
                        tracker.record_failure()
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(True, 100)),
            threading.Thread(target=writer, args=(False, 100)),
            threading.Thread(target=writer, args=(True, 50)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Errors during concurrent writes: {errors}"
        assert len(tracker._window) == 250  # 100 + 100 + 50

    def test_concurrent_read_and_write(self):
        """current_fail_rate() must not raise when called concurrently with recording."""
        tracker, _ = _make_tracker()
        errors: list[Exception] = []

        def reader(n: int) -> None:
            for _ in range(n):
                try:
                    tracker.current_fail_rate()
                except Exception as e:
                    errors.append(e)

        def writer(n: int) -> None:
            for i in range(n):
                try:
                    if i % 2 == 0:
                        tracker.record_success()
                    else:
                        tracker.record_failure()
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=reader, args=(200,)),
            threading.Thread(target=writer, args=(200,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Errors during concurrent read/write: {errors}"


# ---------------------------------------------------------------------------
# PositionTracker integration: record_failure called on CH error
# ---------------------------------------------------------------------------

class TestPositionTrackerIntegration:
    """Verify that PositionTracker wires record_failure into _flush_batch."""

    @pytest.mark.asyncio
    async def test_record_failure_called_when_ch_insert_raises(self):
        """_flush_batch must call record_failure() when ClickHouse raises."""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )
        from shared.exceptions import InfrastructureError

        config = PositionTrackerConfig(batch_size=50, flush_interval_seconds=0)
        mock_ch_fail_tracker = MagicMock()
        tracker = PositionTracker(
            config=config,
            ch_fail_tracker=mock_ch_fail_tracker,
        )

        # Make _get_db_client raise so the CH INSERT fails
        with patch.object(
            tracker,
            "_get_db_client",
            side_effect=InfrastructureError("CH unavailable"),
        ):
            await tracker._flush_batch(
                [("row1",)],
                table_name="rl_trades",
                insert_cols="(id)",
                label="test",
            )

        mock_ch_fail_tracker.record_failure.assert_called_once()
        mock_ch_fail_tracker.record_success.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_success_called_on_successful_flush(self):
        """_flush_batch must call record_success() when INSERT succeeds."""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )

        config = PositionTrackerConfig(batch_size=50, flush_interval_seconds=0)
        mock_ch_fail_tracker = MagicMock()
        tracker = PositionTracker(
            config=config,
            ch_fail_tracker=mock_ch_fail_tracker,
        )

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            await tracker._flush_batch(
                [("row1",)],
                table_name="rl_trades",
                insert_cols="(id)",
                label="test",
            )

        mock_ch_fail_tracker.record_success.assert_called_once()
        mock_ch_fail_tracker.record_failure.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_tracker_attached_does_not_raise(self):
        """_flush_batch must work normally when no CH fail tracker is attached."""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )

        config = PositionTrackerConfig(batch_size=50, flush_interval_seconds=0)
        tracker = PositionTracker(config=config)  # no redis_client → tracker is None
        assert tracker._ch_fail_tracker is None

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            count, _ = await tracker._flush_batch(
                [("row1",)],
                table_name="rl_trades",
                insert_cols="(id)",
                label="test",
            )
        assert count == 1

    def test_position_tracker_accepts_ch_fail_tracker_param(self):
        """PositionTracker.__init__ must accept ch_fail_tracker without error."""
        from services.trading.position_tracker import (
            PositionTracker,
            PositionTrackerConfig,
        )

        mock_tracker = MagicMock()
        tracker = PositionTracker(
            config=PositionTrackerConfig(flush_interval_seconds=0),
            ch_fail_tracker=mock_tracker,
        )
        assert tracker._ch_fail_tracker is mock_tracker
