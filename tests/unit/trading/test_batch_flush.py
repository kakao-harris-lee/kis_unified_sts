"""Tests for batch flush functionality in PositionTracker.

Tests the batching mechanism for closed positions and RL trades,
including accumulation, threshold triggers, manual flush, timer-based
flush, and shutdown flush.
"""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.models.position import Position, PositionSide, PositionState


def _make_position(
    *,
    id="test-pos-001",
    code="005930",
    name="삼성전자",
    side=PositionSide.LONG,
    quantity=10,
    entry_price=70000,
    strategy="bb_reversion",
    fee_rate=0.003,
    exit_price=None,
    exit_time=None,
    exit_reason=None,
):
    """Helper to create a test position."""
    pos = Position(
        id=id,
        code=code,
        name=name,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        entry_time=datetime(2026, 2, 19, 9, 30, 0),
        current_price=exit_price or entry_price,
        highest_price=entry_price,
        lowest_price=entry_price,
        state=PositionState.SURVIVAL,
        strategy=strategy,
        fee_rate=fee_rate,
    )
    if exit_price is not None:
        pos.exit_price = exit_price
        pos.exit_time = exit_time or datetime(2026, 2, 19, 14, 0, 0)
        pos.exit_reason = exit_reason or "TRAILING_STOP"
        pos.current_price = exit_price
    return pos


class TestBatchAccumulation:
    """Test batch accumulation without flush."""

    @pytest.mark.asyncio
    async def test_accumulates_swing_positions_without_flush(self):
        """Positions should accumulate in batch without immediate DB write."""
        config = PositionTrackerConfig(batch_size=10, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Save 3 positions (below threshold of 10)
            for i in range(3):
                pos = _make_position(
                    id=f"pos-{i}",
                    code=f"00593{i}",
                    exit_price=72000,
                )
                result = await tracker.save_closed_to_db(pos)
                assert result is True

        # Should NOT have written to DB yet
        assert mock_client.execute.call_count == 0

        # Should have 3 positions in pending batch
        assert len(tracker._pending_swing_positions) == 3

    @pytest.mark.asyncio
    async def test_accumulates_rl_trades_without_flush(self):
        """RL trades should accumulate in batch without immediate DB write."""
        config = PositionTrackerConfig(batch_size=10, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Save 3 RL trades (below threshold of 10)
            for i in range(3):
                pos = _make_position(
                    id=f"rl-{i}",
                    code="101S6000",
                    strategy="rl_mppo",
                    exit_price=350.0,
                )
                result = await tracker.save_rl_trade_to_db(pos, asset_class="futures")
                assert result is True

        # Should NOT have written to DB yet
        assert mock_client.execute.call_count == 0

        # Should have 3 trades in pending batch
        assert len(tracker._pending_rl_trades) == 3


class TestBatchSizeThresholdTrigger:
    """Test automatic flush when batch size threshold is reached."""

    @pytest.mark.asyncio
    async def test_flushes_swing_positions_at_threshold(self):
        """Should auto-flush when batch reaches configured batch_size."""
        config = PositionTrackerConfig(batch_size=5, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Save 5 positions (exactly at threshold)
            for i in range(5):
                pos = _make_position(
                    id=f"pos-{i}",
                    code=f"00593{i}",
                    exit_price=72000,
                )
                await tracker.save_closed_to_db(pos)

        # Should have flushed automatically
        assert mock_client.execute.call_count == 1

        # Batch should be empty after flush
        assert len(tracker._pending_swing_positions) == 0

    @pytest.mark.asyncio
    async def test_flushes_rl_trades_at_threshold(self):
        """Should auto-flush RL trades when batch reaches configured batch_size."""
        config = PositionTrackerConfig(batch_size=3, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Save 3 RL trades (exactly at threshold)
            for i in range(3):
                pos = _make_position(
                    id=f"rl-{i}",
                    code="101S6000",
                    strategy="rl_mppo",
                    exit_price=350.0,
                )
                await tracker.save_rl_trade_to_db(pos, asset_class="futures")

        # Should have flushed automatically (2 calls: schema + insert)
        assert mock_client.execute.call_count == 2

        # Batch should be empty after flush
        assert len(tracker._pending_rl_trades) == 0

    @pytest.mark.asyncio
    async def test_multiple_threshold_flushes(self):
        """Should flush multiple times as positions accumulate."""
        config = PositionTrackerConfig(batch_size=3, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Save 7 positions (should trigger 2 flushes: 3 + 3, leaving 1)
            for i in range(7):
                pos = _make_position(
                    id=f"pos-{i}",
                    code=f"00593{i}",
                    exit_price=72000,
                )
                await tracker.save_closed_to_db(pos)

        # Should have flushed twice (at position 3 and position 6)
        assert mock_client.execute.call_count == 2

        # Should have 1 remaining position in batch
        assert len(tracker._pending_swing_positions) == 1


class TestManualFlush:
    """Test manual flush via flush_pending_positions()."""

    @pytest.mark.asyncio
    async def test_manual_flush_swing_positions(self):
        """Manual flush should write accumulated positions to DB."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Accumulate 3 positions (below threshold)
            for i in range(3):
                pos = _make_position(id=f"pos-{i}", exit_price=72000)
                await tracker.save_closed_to_db(pos)

            # Should NOT have auto-flushed yet
            assert mock_client.execute.call_count == 0

            # Manual flush
            swing_count, rl_count = await tracker.flush_pending_positions()

        # Should have flushed 3 swing positions
        assert swing_count == 3
        assert rl_count == 0

        # DB should have been called once
        assert mock_client.execute.call_count == 1

        # Batch should be empty
        assert len(tracker._pending_swing_positions) == 0

    @pytest.mark.asyncio
    async def test_manual_flush_rl_trades(self):
        """Manual flush should write accumulated RL trades to DB."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Accumulate 2 RL trades (below threshold)
            for i in range(2):
                pos = _make_position(
                    id=f"rl-{i}",
                    code="101S6000",
                    strategy="rl_mppo",
                    exit_price=350.0,
                )
                await tracker.save_rl_trade_to_db(pos, asset_class="futures")

            # Manual flush
            swing_count, rl_count = await tracker.flush_pending_positions()

        # Should have flushed 2 RL trades
        assert swing_count == 0
        assert rl_count == 2

        # DB should have been called twice (schema + insert)
        assert mock_client.execute.call_count == 2

        # Batch should be empty
        assert len(tracker._pending_rl_trades) == 0

    @pytest.mark.asyncio
    async def test_manual_flush_both_types(self):
        """Manual flush should handle both swing positions and RL trades."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Add swing positions
            for i in range(2):
                pos = _make_position(id=f"pos-{i}", exit_price=72000)
                await tracker.save_closed_to_db(pos)

            # Add RL trades
            for i in range(3):
                pos = _make_position(
                    id=f"rl-{i}",
                    code="101S6000",
                    strategy="rl_mppo",
                    exit_price=350.0,
                )
                await tracker.save_rl_trade_to_db(pos, asset_class="futures")

            # Manual flush
            swing_count, rl_count = await tracker.flush_pending_positions()

        # Should have flushed both types
        assert swing_count == 2
        assert rl_count == 3

        # Both batches should be empty
        assert len(tracker._pending_swing_positions) == 0
        assert len(tracker._pending_rl_trades) == 0

    @pytest.mark.asyncio
    async def test_manual_flush_empty_batches(self):
        """Manual flush with empty batches should be safe (no-op)."""
        config = PositionTrackerConfig(batch_size=10, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Flush without accumulating anything
            swing_count, rl_count = await tracker.flush_pending_positions()

        # Should return 0 for both
        assert swing_count == 0
        assert rl_count == 0

        # Should NOT have called DB
        assert mock_client.execute.call_count == 0


class TestTimerBasedFlush:
    """Test automatic timer-based flush."""

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
    async def test_auto_flush_triggers_periodically(self):
        """Auto-flush should trigger after flush_interval_seconds."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=0.1)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Accumulate 2 positions
            for i in range(2):
                pos = _make_position(id=f"pos-{i}", exit_price=72000)
                await tracker.save_closed_to_db(pos)

            # Wait for auto-flush to trigger (0.1s + buffer)
            await asyncio.sleep(0.25)

        # Should have auto-flushed
        assert mock_client.execute.call_count >= 1

        # Batch should be empty
        assert len(tracker._pending_swing_positions) == 0

        # Clean up
        await tracker.stop_auto_flush()

    @pytest.mark.asyncio
    async def test_auto_flush_handles_errors_gracefully(self):
        """Auto-flush task should continue running despite errors."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=0.1)
        tracker = PositionTracker(config=config)

        # Mock flush to raise error on first call, succeed on second
        call_count = 0

        async def mock_flush():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Simulated DB error")
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
    async def test_stop_auto_flush_performs_final_flush(self):
        """stop_auto_flush should flush remaining positions before shutdown."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=1.0)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Accumulate 3 positions (below threshold, won't auto-flush yet)
            for i in range(3):
                pos = _make_position(id=f"pos-{i}", exit_price=72000)
                await tracker.save_closed_to_db(pos)

            # Should NOT have flushed yet
            assert mock_client.execute.call_count == 0

            # Stop auto-flush (triggers final flush)
            await tracker.stop_auto_flush()

        # Should have flushed the 3 positions
        assert mock_client.execute.call_count == 1

        # Batch should be empty
        assert len(tracker._pending_swing_positions) == 0

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

    @pytest.mark.asyncio
    async def test_stop_auto_flush_flushes_both_types(self):
        """Shutdown flush should handle both swing positions and RL trades."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=1.0)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Add swing positions
            for i in range(2):
                pos = _make_position(id=f"pos-{i}", exit_price=72000)
                await tracker.save_closed_to_db(pos)

            # Add RL trades
            for i in range(3):
                pos = _make_position(
                    id=f"rl-{i}",
                    code="101S6000",
                    strategy="rl_mppo",
                    exit_price=350.0,
                )
                await tracker.save_rl_trade_to_db(pos, asset_class="futures")

            # Stop (triggers final flush)
            await tracker.stop_auto_flush()

        # Should have flushed both types (swing insert + rl schema + rl insert)
        assert mock_client.execute.call_count == 3

        # Both batches should be empty
        assert len(tracker._pending_swing_positions) == 0
        assert len(tracker._pending_rl_trades) == 0


class TestBatchFlushThreadSafety:
    """Test thread safety of batch operations."""

    @pytest.mark.asyncio
    async def test_concurrent_accumulation_thread_safe(self):
        """Concurrent accumulation should be thread-safe with asyncio.Lock."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Simulate concurrent saves
            tasks = []
            for i in range(10):
                pos = _make_position(id=f"pos-{i}", exit_price=72000)
                tasks.append(tracker.save_closed_to_db(pos))

            # Run all concurrently
            results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(results)

        # Should have exactly 10 positions in batch
        assert len(tracker._pending_swing_positions) == 10

        # No data corruption or race conditions
        position_ids = {row[0] for row in tracker._pending_swing_positions}
        assert len(position_ids) == 10  # All unique IDs

    @pytest.mark.asyncio
    async def test_concurrent_flush_thread_safe(self):
        """Concurrent flush calls should be thread-safe."""
        config = PositionTrackerConfig(batch_size=100, flush_interval_seconds=999)
        tracker = PositionTracker(config=config)

        mock_client = MagicMock()
        mock_ch = MagicMock()
        mock_ch.get_sync_client.return_value = mock_client

        with patch.object(tracker, "_get_db_client", return_value=(mock_ch, "testdb")):
            # Add positions
            for i in range(5):
                pos = _make_position(id=f"pos-{i}", exit_price=72000)
                await tracker.save_closed_to_db(pos)

            # Call flush concurrently (should be safe)
            results = await asyncio.gather(
                tracker.flush_pending_positions(),
                tracker.flush_pending_positions(),
            )
            swing1, rl1 = results[0]
            swing2, rl2 = results[1]

        # One should flush 5, the other 0 (batch already empty)
        total_flushed = swing1 + swing2
        assert total_flushed == 5

        # Batch should be empty
        assert len(tracker._pending_swing_positions) == 0
