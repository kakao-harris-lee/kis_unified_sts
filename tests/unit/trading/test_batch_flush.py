"""Tests for batch flush functionality in PositionTracker.

Tests the flush-task lifecycle (start, stop, error-handling) after the
legacy ClickHouse buffer path was removed in favour of RuntimeLedger.
"""

import asyncio
from unittest.mock import patch

import pytest

from services.trading.position_tracker import PositionTracker, PositionTrackerConfig


class TestManualFlush:
    """Test manual flush via flush_pending_positions()."""

    @pytest.mark.asyncio
    async def test_manual_flush_empty_batches(self):
        """Manual flush with empty batches should be safe (no-op)."""
        config = PositionTrackerConfig(batch_size=10, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        # Flush without accumulating anything
        swing_count, futures_count = await tracker.flush_pending_positions()

        # Should return 0 for both
        assert swing_count == 0
        assert futures_count == 0


class TestTimerBasedFlush:
    """Test automatic timer-based flush task lifecycle."""

    @pytest.mark.asyncio
    async def test_auto_flush_task_started(self):
        """Auto-flush task should be started on initialization."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=1.0)
        tracker = PositionTracker(config=config)

        # Task should be created
        assert tracker._auto_flush_task is not None
        assert not tracker._auto_flush_task.done()

        # Clean up
        await tracker.stop_auto_flush()

    @pytest.mark.asyncio
    async def test_auto_flush_task_not_started_when_disabled(self):
        """Auto-flush task should NOT start when flush_interval_seconds <= 0."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=0)
        tracker = PositionTracker(config=config)

        # Task should not be created
        assert tracker._auto_flush_task is None

    @pytest.mark.asyncio
    async def test_auto_flush_handles_errors_gracefully(self):
        """Auto-flush task should continue running despite errors."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=0.1)
        tracker = PositionTracker(config=config)

        # Mock flush to raise error on first call, succeed on second
        call_count = 0

        from shared.exceptions import TradingSystemError

        async def mock_flush():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TradingSystemError("Simulated DB error")
            return 0, 0

        with patch.object(
            tracker, "flush_pending_positions", side_effect=mock_flush
        ) as mock:
            # Wait for multiple flush attempts
            # First flush at 0.1s raises error, then 1s retry delay, then second flush at ~1.1s
            await asyncio.sleep(1.5)

            # Should have called flush multiple times despite first error
            assert mock.call_count >= 2

        # Task should still be running
        assert tracker._auto_flush_task is not None
        assert not tracker._auto_flush_task.done()

        # Clean up
        await tracker.stop_auto_flush()


class TestShutdownFlush:
    """Test flush on graceful shutdown via stop_auto_flush()."""

    @pytest.mark.asyncio
    async def test_stop_auto_flush_cancels_task(self):
        """stop_auto_flush should cancel the background task."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=1.0)
        tracker = PositionTracker(config=config)

        # Task should be running
        assert tracker._auto_flush_task is not None
        assert not tracker._auto_flush_task.done()

        # Stop it
        await tracker.stop_auto_flush()

        # Task should be cancelled/done
        assert tracker._auto_flush_task.done()

    @pytest.mark.asyncio
    async def test_stop_auto_flush_safe_when_no_task(self):
        """stop_auto_flush should be safe to call when auto-flush is disabled."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=0)
        tracker = PositionTracker(config=config)

        # No task was created
        assert tracker._auto_flush_task is None

        # Should not raise error
        await tracker.stop_auto_flush()

    @pytest.mark.asyncio
    async def test_stop_auto_flush_safe_to_call_multiple_times(self):
        """stop_auto_flush should be safe to call multiple times."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=1.0)
        tracker = PositionTracker(config=config)

        # Stop it once
        await tracker.stop_auto_flush()

        # Stop it again (should not raise error)
        await tracker.stop_auto_flush()
