"""Tests for KISApiErrorRateTracker (shared/kis/error_rate.py).

Covers §10.3-A acceptance criteria:
- Empty window → rate = 0.0
- All successes → rate = 0.0
- All errors → rate = 1.0
- Mixed events → correct fraction
- Window expiry: stale events are excluded
- Redis write: key written at publish_interval_seconds cadence
- Disabled config → no Redis writes
- Concurrent record_* calls are safe
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from shared.kis.error_rate import ErrorRateConfig, KISApiErrorRateTracker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(
    *,
    enabled: bool = True,
    window_seconds: float = 300.0,
    publish_interval_seconds: float = 10.0,
    redis_key: str = "kill_switch:metrics:api_error_rate_5min",
) -> ErrorRateConfig:
    return ErrorRateConfig(
        enabled=enabled,
        window_seconds=window_seconds,
        publish_interval_seconds=publish_interval_seconds,
        redis_key=redis_key,
    )


def _fresh_tracker(**kwargs) -> KISApiErrorRateTracker:
    """Return a new tracker instance (bypasses singleton for test isolation)."""
    return KISApiErrorRateTracker(config=_make_config(**kwargs))


# ---------------------------------------------------------------------------
# Unit tests — rate computation
# ---------------------------------------------------------------------------


class TestCurrentRate:
    """Pure rate-computation tests; no I/O."""

    def test_empty_window_returns_zero(self):
        tracker = _fresh_tracker()
        assert tracker.current_rate() == 0.0

    def test_all_successes_returns_zero(self):
        tracker = _fresh_tracker()
        for _ in range(10):
            tracker.record_success()
        assert tracker.current_rate() == 0.0

    def test_all_errors_returns_one(self):
        tracker = _fresh_tracker()
        for _ in range(5):
            tracker.record_error()
        assert tracker.current_rate() == 1.0

    def test_mixed_returns_correct_fraction(self):
        tracker = _fresh_tracker()
        for _ in range(7):
            tracker.record_success()
        for _ in range(3):
            tracker.record_error()
        rate = tracker.current_rate()
        assert abs(rate - 0.3) < 1e-9

    def test_single_error_fraction(self):
        tracker = _fresh_tracker()
        tracker.record_success()
        tracker.record_success()
        tracker.record_error()
        # 1 error / 3 total ≈ 0.333…
        rate = tracker.current_rate()
        assert abs(rate - (1 / 3)) < 1e-9

    def test_rate_bounded_between_zero_and_one(self):
        tracker = _fresh_tracker()
        for _ in range(100):
            tracker.record_error()
        for _ in range(100):
            tracker.record_success()
        rate = tracker.current_rate()
        assert 0.0 <= rate <= 1.0


# ---------------------------------------------------------------------------
# Window expiry
# ---------------------------------------------------------------------------


class TestWindowExpiry:
    """Events older than window_seconds must not contribute to the rate."""

    def test_expired_events_are_excluded(self):
        # 1-second window so we can expire events quickly
        tracker = _fresh_tracker(window_seconds=0.05)

        # Record errors that will expire
        for _ in range(5):
            tracker.record_error()

        # Wait for the window to close
        time.sleep(0.07)

        # Add a fresh success
        tracker.record_success()

        # Only the fresh success survives → rate = 0.0
        assert tracker.current_rate() == 0.0

    def test_recent_events_within_window_count(self):
        tracker = _fresh_tracker(window_seconds=10.0)

        tracker.record_error()
        tracker.record_success()

        # Both events are fresh
        rate = tracker.current_rate()
        assert abs(rate - 0.5) < 1e-9

    def test_stale_events_pruned_from_deque(self):
        tracker = _fresh_tracker(window_seconds=0.05)

        for _ in range(10):
            tracker.record_error()

        time.sleep(0.07)

        # Trigger pruning via current_rate()
        tracker.current_rate()

        # Deque should be empty after pruning
        assert len(tracker._events) == 0


# ---------------------------------------------------------------------------
# Concurrent safety
# ---------------------------------------------------------------------------


class TestConcurrentSafety:
    """record_* calls from multiple coroutines must not lose events."""

    @pytest.mark.asyncio
    async def test_concurrent_record_does_not_lose_events(self):
        tracker = _fresh_tracker()
        n = 100

        async def record_n_successes():
            for _ in range(n):
                tracker.record_success()
                await asyncio.sleep(0)

        async def record_n_errors():
            for _ in range(n):
                tracker.record_error()
                await asyncio.sleep(0)

        await asyncio.gather(record_n_successes(), record_n_errors())

        total_events = len(tracker._events)
        assert total_events == 2 * n, (
            f"Expected {2 * n} events, got {total_events}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_rate_is_valid_fraction(self):
        tracker = _fresh_tracker()

        async def produce():
            for i in range(50):
                if i % 2 == 0:
                    tracker.record_success()
                else:
                    tracker.record_error()
                await asyncio.sleep(0)

        await asyncio.gather(produce(), produce())

        rate = tracker.current_rate()
        assert 0.0 <= rate <= 1.0


# ---------------------------------------------------------------------------
# Redis publish
# ---------------------------------------------------------------------------


class TestRedisPublish:
    """The background task must write the correct value at the right interval."""

    @pytest.mark.asyncio
    async def test_tracker_writes_to_redis(self):
        tracker = _fresh_tracker(publish_interval_seconds=0.05)

        mock_redis = MagicMock()
        tracker.record_error()
        tracker.record_success()  # expected rate = 0.5

        with patch(
            "shared.streaming.client.RedisClient.get_client",
            return_value=mock_redis,
        ):
            await tracker.start()
            await asyncio.sleep(0.12)  # wait for ≥1 publish tick
            await tracker.stop()

        assert mock_redis.setex.called, "setex should have been called at least once"

        call_args = mock_redis.setex.call_args
        key = call_args[0][0]
        assert key == "kill_switch:metrics:api_error_rate_5min"

        written_rate = float(call_args[0][2])
        assert 0.0 <= written_rate <= 1.0

    @pytest.mark.asyncio
    async def test_disabled_tracker_does_not_write_redis(self):
        tracker = _fresh_tracker(enabled=False, publish_interval_seconds=0.05)

        mock_redis = MagicMock()
        tracker.record_error()

        with patch(
            "shared.streaming.client.RedisClient.get_client",
            return_value=mock_redis,
        ):
            await tracker.start()
            await asyncio.sleep(0.12)
            await tracker.stop()

        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_key_ttl_is_double_window(self):
        window = 60.0
        tracker = _fresh_tracker(
            window_seconds=window,
            publish_interval_seconds=0.05,
        )

        mock_redis = MagicMock()
        tracker.record_success()

        with patch(
            "shared.streaming.client.RedisClient.get_client",
            return_value=mock_redis,
        ):
            await tracker.start()
            await asyncio.sleep(0.12)
            await tracker.stop()

        # TTL should be int(2 * 60.0) = 120
        call_args = mock_redis.setex.call_args
        ttl = call_args[0][1]
        assert ttl == int(window * 2)

    @pytest.mark.asyncio
    async def test_redis_failure_does_not_crash_loop(self):
        tracker = _fresh_tracker(publish_interval_seconds=0.05)

        mock_redis = MagicMock()
        mock_redis.setex.side_effect = ConnectionError("Redis down")
        tracker.record_success()

        with patch(
            "shared.streaming.client.RedisClient.get_client",
            return_value=mock_redis,
        ):
            await tracker.start()
            # Should not raise even though Redis is broken
            await asyncio.sleep(0.15)
            await tracker.stop()

        # Loop survived — setex was attempted
        assert mock_redis.setex.called


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        tracker = _fresh_tracker(publish_interval_seconds=0.05)

        mock_redis = MagicMock()
        with patch(
            "shared.streaming.client.RedisClient.get_client",
            return_value=mock_redis,
        ):
            await tracker.start()
            task_1 = tracker._publish_task
            await tracker.start()  # second call — should be no-op
            task_2 = tracker._publish_task

        assert task_1 is task_2, "start() must not replace a running task"
        await tracker.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        tracker = _fresh_tracker(publish_interval_seconds=0.05)

        mock_redis = MagicMock()
        with patch(
            "shared.streaming.client.RedisClient.get_client",
            return_value=mock_redis,
        ):
            await tracker.start()
            assert tracker._running is True
            await tracker.stop()

        assert tracker._running is False
        assert tracker._publish_task is None


# ---------------------------------------------------------------------------
# ErrorRateConfig — YAML defaults
# ---------------------------------------------------------------------------


class TestErrorRateConfig:
    def test_defaults_used_when_yaml_missing(self):
        with patch("shared.kis.error_rate._load_config", return_value={}):
            cfg = ErrorRateConfig.from_yaml()

        assert cfg.enabled is True
        assert cfg.window_seconds == 300.0
        assert cfg.publish_interval_seconds == 10.0
        assert cfg.redis_key == "kill_switch:metrics:api_error_rate_5min"

    def test_yaml_values_override_defaults(self):
        raw = {
            "enabled": False,
            "window_seconds": 120,
            "publish_interval_seconds": 5,
            "redis_key": "custom:key",
        }
        with patch("shared.kis.error_rate._load_config", return_value=raw):
            cfg = ErrorRateConfig.from_yaml()

        assert cfg.enabled is False
        assert cfg.window_seconds == 120.0
        assert cfg.publish_interval_seconds == 5.0
        assert cfg.redis_key == "custom:key"
