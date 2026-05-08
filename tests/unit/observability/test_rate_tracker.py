"""Tests for shared/observability/rate_tracker.py — RollingRateTracker base class.

Covers §10.3 DRY follow-up acceptance criteria:
- Empty window → 0.0
- All success → 0.0
- All failure → 1.0
- Mixed events → correct ratio
- Window expiry / pruning
- start/stop lifecycle (cancellable, no leaked tasks)
- Redis write format ``f"{rate:.6f}"`` parseable via ``float(value)``
- Publish loop resilience (Redis raises → log, retry)
- disabled config → no Redis writes
- TTL = window × 2 fallback when ``redis_ttl_seconds`` is ``None``
- Explicit TTL when set
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from shared.observability.rate_tracker import RollingRateTracker

# ---------------------------------------------------------------------------
# Minimal config satisfying RateTrackerConfigProtocol
# ---------------------------------------------------------------------------


@dataclass
class _TestConfig:
    """Minimal config for testing RollingRateTracker directly."""

    enabled: bool = True
    window_seconds: float = 300.0
    publish_interval_seconds: float = 10.0
    redis_key: str = "test:metrics:rate"
    redis_ttl_seconds: int | None = None  # → 2 × window_seconds


def _make_tracker(
    **kwargs: Any,
) -> RollingRateTracker:
    """Build a RollingRateTracker with an optional config override."""
    config = _TestConfig(**kwargs)
    return RollingRateTracker(config, logger_name="TestTracker")


# ---------------------------------------------------------------------------
# Rate computation
# ---------------------------------------------------------------------------


class TestCurrentRate:
    """Pure rate-computation tests — no I/O."""

    def test_empty_window_returns_zero(self) -> None:
        tracker = _make_tracker()
        assert tracker.current_rate() == 0.0

    def test_all_successes_returns_zero(self) -> None:
        tracker = _make_tracker()
        for _ in range(10):
            tracker.record_success()
        assert tracker.current_rate() == 0.0

    def test_all_failures_returns_one(self) -> None:
        tracker = _make_tracker()
        for _ in range(5):
            tracker.record_failure()
        assert tracker.current_rate() == 1.0

    def test_mixed_returns_correct_fraction(self) -> None:
        """3 failures out of 10 total → 0.3."""
        tracker = _make_tracker()
        for _ in range(7):
            tracker.record_success()
        for _ in range(3):
            tracker.record_failure()
        assert abs(tracker.current_rate() - 0.3) < 1e-9

    def test_single_failure_fraction(self) -> None:
        tracker = _make_tracker()
        tracker.record_success()
        tracker.record_success()
        tracker.record_failure()
        assert abs(tracker.current_rate() - 1 / 3) < 1e-9

    def test_rate_bounded_zero_to_one(self) -> None:
        tracker = _make_tracker()
        for _ in range(50):
            tracker.record_failure()
        for _ in range(50):
            tracker.record_success()
        rate = tracker.current_rate()
        assert 0.0 <= rate <= 1.0

    def test_disabled_always_returns_zero(self) -> None:
        tracker = _make_tracker(enabled=False)
        tracker.record_failure()
        tracker.record_success()
        assert tracker.current_rate() == 0.0


# ---------------------------------------------------------------------------
# Window expiry / pruning
# ---------------------------------------------------------------------------


class TestWindowExpiry:
    """Events older than window_seconds must not contribute to the rate."""

    def test_expired_events_excluded(self) -> None:
        tracker = _make_tracker(window_seconds=0.05)
        for _ in range(5):
            tracker.record_failure()
        time.sleep(0.07)
        tracker.record_success()
        # Only the fresh success survives → 0 failures / 1 total = 0.0
        assert tracker.current_rate() == 0.0

    def test_recent_events_included(self) -> None:
        tracker = _make_tracker(window_seconds=10.0)
        tracker.record_failure()
        tracker.record_success()
        assert abs(tracker.current_rate() - 0.5) < 1e-9

    def test_stale_events_pruned_from_deque(self) -> None:
        tracker = _make_tracker(window_seconds=0.05)
        for _ in range(8):
            tracker.record_failure()
        time.sleep(0.07)
        tracker.current_rate()  # trigger prune
        assert len(tracker._events) == 0

    def test_disabled_record_noop_no_events(self) -> None:
        tracker = _make_tracker(enabled=False)
        tracker.record_success()
        tracker.record_failure()
        assert len(tracker._events) == 0


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    """start() / stop() must manage the background task correctly."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self) -> None:
        tracker = _make_tracker(publish_interval_seconds=0.1)
        mock_redis = MagicMock()
        with patch("shared.streaming.client.RedisClient.get_client", return_value=mock_redis):
            await tracker.start()
            try:
                assert tracker._publish_task is not None
                assert not tracker._publish_task.done()
            finally:
                await tracker.stop()

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        tracker = _make_tracker(publish_interval_seconds=0.1)
        mock_redis = MagicMock()
        with patch("shared.streaming.client.RedisClient.get_client", return_value=mock_redis):
            await tracker.start()
            task_1 = tracker._publish_task
            await tracker.start()  # second call — no-op
            task_2 = tracker._publish_task
            assert task_1 is task_2
        await tracker.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self) -> None:
        tracker = _make_tracker(publish_interval_seconds=0.1)
        mock_redis = MagicMock()
        with patch("shared.streaming.client.RedisClient.get_client", return_value=mock_redis):
            await tracker.start()
            assert tracker._running is True
            await tracker.stop()
        assert tracker._running is False
        assert tracker._publish_task is None

    @pytest.mark.asyncio
    async def test_stop_safe_when_never_started(self) -> None:
        tracker = _make_tracker()
        mock_redis = MagicMock()
        with patch("shared.streaming.client.RedisClient.get_client", return_value=mock_redis):
            await tracker.stop()  # must not raise

    @pytest.mark.asyncio
    async def test_disabled_start_no_task(self) -> None:
        tracker = _make_tracker(enabled=False)
        await tracker.start()
        assert tracker._publish_task is None
        await tracker.stop()


# ---------------------------------------------------------------------------
# Redis write format and TTL
# ---------------------------------------------------------------------------


class TestRedisWrite:
    """Verify Redis key, value format, and TTL."""

    @pytest.mark.asyncio
    async def test_write_value_parseable_as_float(self) -> None:
        """The format ``f'{rate:.6f}'`` must round-trip via ``float(value)``."""
        tracker = _make_tracker()
        tracker.record_failure()
        tracker.record_success()  # rate = 0.5

        mock_redis = MagicMock()
        with patch("shared.streaming.client.RedisClient.get_client", return_value=mock_redis):
            await tracker._write_to_redis()

        mock_redis.setex.assert_called_once()
        key, ttl, value = mock_redis.setex.call_args[0]
        parsed = float(value)
        assert abs(parsed - 0.5) < 1e-5, f"Expected ~0.5, got {parsed}"
        assert key == "test:metrics:rate"

    @pytest.mark.asyncio
    async def test_ttl_fallback_is_double_window(self) -> None:
        """When ``redis_ttl_seconds`` is ``None``, TTL = 2 × window_seconds."""
        tracker = _make_tracker(window_seconds=90.0, redis_ttl_seconds=None)
        tracker.record_success()

        mock_redis = MagicMock()
        with patch("shared.streaming.client.RedisClient.get_client", return_value=mock_redis):
            await tracker._write_to_redis()

        _, ttl, _ = mock_redis.setex.call_args[0]
        assert ttl == int(90.0 * 2)  # 180

    @pytest.mark.asyncio
    async def test_explicit_ttl_used(self) -> None:
        """When ``redis_ttl_seconds`` is set, use it exactly."""
        tracker = _make_tracker(window_seconds=60.0, redis_ttl_seconds=500)
        tracker.record_success()

        mock_redis = MagicMock()
        with patch("shared.streaming.client.RedisClient.get_client", return_value=mock_redis):
            await tracker._write_to_redis()

        _, ttl, _ = mock_redis.setex.call_args[0]
        assert ttl == 500

    @pytest.mark.asyncio
    async def test_disabled_no_redis_write(self) -> None:
        tracker = _make_tracker(enabled=False)
        tracker.record_failure()

        mock_redis = MagicMock()
        with patch("shared.streaming.client.RedisClient.get_client", return_value=mock_redis):
            await tracker._write_to_redis()

        mock_redis.setex.assert_not_called()


# ---------------------------------------------------------------------------
# Publish loop — periodic writes and resilience
# ---------------------------------------------------------------------------


class TestPublishLoop:
    """The background loop must write periodically and survive Redis errors."""

    @pytest.mark.asyncio
    async def test_loop_writes_to_redis(self) -> None:
        tracker = _make_tracker(publish_interval_seconds=0.05)
        tracker.record_failure()
        tracker.record_success()

        mock_redis = MagicMock()
        with patch("shared.streaming.client.RedisClient.get_client", return_value=mock_redis):
            await tracker.start()
            await asyncio.sleep(0.15)  # allow ≥2 ticks
            await tracker.stop()

        assert mock_redis.setex.called, "setex should have been called at least once"

    @pytest.mark.asyncio
    async def test_redis_failure_does_not_crash_loop(self) -> None:
        """A Redis error must be logged and the loop must keep running."""
        tracker = _make_tracker(publish_interval_seconds=0.05)
        tracker.record_success()

        mock_redis = MagicMock()
        mock_redis.setex.side_effect = ConnectionError("Redis unavailable")
        with patch("shared.streaming.client.RedisClient.get_client", return_value=mock_redis):
            await tracker.start()
            await asyncio.sleep(0.20)  # survive multiple failing ticks
            await tracker.stop()

        assert mock_redis.setex.called, "setex was attempted despite errors"

    @pytest.mark.asyncio
    async def test_disabled_loop_never_started(self) -> None:
        tracker = _make_tracker(enabled=False, publish_interval_seconds=0.05)

        mock_redis = MagicMock()
        with patch("shared.streaming.client.RedisClient.get_client", return_value=mock_redis):
            await tracker.start()
            await asyncio.sleep(0.12)
            await tracker.stop()

        mock_redis.setex.assert_not_called()
