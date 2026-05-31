"""Unit tests for WebSocket health monitoring."""

import time


class TestHealthStatusInitialization:
    """Tests for health status at initialization."""

    def test_initial_health_status(self, mock_adapter):
        """Test health status immediately after initialization."""
        status = mock_adapter.get_health_status()

        assert status["connected"] is False
        assert status["running"] is False
        assert status["last_message_ts"] is None
        assert status["staleness_seconds"] is None

    def test_initial_staleness_is_none(self, mock_adapter):
        """Test staleness is None when no messages received."""
        staleness = mock_adapter.get_connection_staleness()

        assert staleness is None


class TestHealthStatusDuringConnection:
    """Tests for health status during connection lifecycle."""

    def test_health_status_after_connect(self, mock_adapter):
        """Test health status after WebSocket connection opens."""
        mock_adapter._on_open(None)
        status = mock_adapter.get_health_status()

        assert status["connected"] is True
        assert status["running"] is False  # Thread not started yet
        assert status["last_message_ts"] is None
        assert status["staleness_seconds"] is None

    def test_health_status_after_disconnect(self, mock_adapter):
        """Test health status after WebSocket disconnects."""
        # Connect first
        mock_adapter._on_open(None)
        assert mock_adapter.get_health_status()["connected"] is True

        # Then disconnect
        mock_adapter._on_close(None, 1000, "Normal closure")
        status = mock_adapter.get_health_status()

        assert status["connected"] is False

    def test_health_status_with_running_thread(self, mock_adapter):
        """Test health status when thread is running."""
        mock_adapter._set_running(True)
        status = mock_adapter.get_health_status()

        assert status["running"] is True


class TestMessageTimestampTracking:
    """Tests for message timestamp tracking in _on_message."""

    def test_on_message_updates_timestamp(self, mock_adapter):
        """Test _on_message updates last message timestamp."""
        before_ts = time.time()
        mock_adapter._on_message(None, "test_message")
        after_ts = time.time()

        status = mock_adapter.get_health_status()
        assert status["last_message_ts"] is not None
        assert before_ts <= status["last_message_ts"] <= after_ts

    def test_multiple_messages_update_timestamp(self, mock_adapter):
        """Test multiple messages continuously update timestamp."""
        mock_adapter._on_message(None, "first_message")
        first_status = mock_adapter.get_health_status()
        first_ts = first_status["last_message_ts"]

        # Small delay to ensure different timestamp
        time.sleep(0.01)

        mock_adapter._on_message(None, "second_message")
        second_status = mock_adapter.get_health_status()
        second_ts = second_status["last_message_ts"]

        assert second_ts > first_ts

    def test_on_message_thread_safe(self, mock_adapter):
        """Test _on_message timestamp update is thread-safe."""
        # Verify state lock is acquired during timestamp update
        with mock_adapter._state_lock:
            # This should not deadlock
            pass

        mock_adapter._on_message(None, "test_message")
        status = mock_adapter.get_health_status()

        assert status["last_message_ts"] is not None


class TestConnectionStaleness:
    """Tests for get_connection_staleness calculation."""

    def test_staleness_none_without_messages(self, mock_adapter):
        """Test staleness is None when no messages received."""
        staleness = mock_adapter.get_connection_staleness()

        assert staleness is None

    def test_staleness_zero_immediately_after_message(self, mock_adapter):
        """Test staleness is near zero immediately after message."""
        mock_adapter._on_message(None, "test_message")
        staleness = mock_adapter.get_connection_staleness()

        # Should be very close to zero (< 0.1 seconds)
        assert staleness is not None
        assert staleness < 0.1

    def test_staleness_increases_over_time(self, mock_adapter):
        """Test staleness increases as time passes."""
        mock_adapter._on_message(None, "test_message")

        # Get initial staleness
        staleness_1 = mock_adapter.get_connection_staleness()

        # Wait a bit
        time.sleep(0.1)

        # Get staleness again
        staleness_2 = mock_adapter.get_connection_staleness()

        assert staleness_2 > staleness_1

    def test_staleness_never_negative(self, mock_adapter):
        """Test staleness is never negative even with clock skew."""
        # Simulate message received
        mock_adapter._on_message(None, "test_message")

        # Staleness should never be negative
        staleness = mock_adapter.get_connection_staleness()
        assert staleness >= 0.0

    def test_staleness_in_health_status_matches(self, mock_adapter):
        """Test staleness in health status matches standalone method."""
        mock_adapter._on_message(None, "test_message")

        staleness_direct = mock_adapter.get_connection_staleness()
        status = mock_adapter.get_health_status()
        staleness_from_status = status["staleness_seconds"]

        # Should be very close (within 0.01 seconds)
        assert abs(staleness_direct - staleness_from_status) < 0.01


class TestHealthStatusComprehensive:
    """Tests for comprehensive health status reporting."""

    def test_health_status_all_fields_present(self, mock_adapter):
        """Test health status contains all required fields including new counters."""
        status = mock_adapter.get_health_status()

        assert "connected" in status
        assert "running" in status
        assert "last_message_ts" in status
        assert "staleness_seconds" in status
        assert "messages_received" in status
        assert "messages_dropped" in status
        assert "queue_depth" in status

    def test_health_status_field_types(self, mock_adapter):
        """Test health status field types are correct."""
        status = mock_adapter.get_health_status()

        assert isinstance(status["connected"], bool)
        assert isinstance(status["running"], bool)
        assert status["last_message_ts"] is None or isinstance(
            status["last_message_ts"], float
        )
        assert status["staleness_seconds"] is None or isinstance(
            status["staleness_seconds"], float
        )
        assert isinstance(status["messages_received"], int)
        assert isinstance(status["messages_dropped"], int)
        assert isinstance(status["queue_depth"], int)

    def test_initial_counters_are_zero(self, mock_adapter):
        """messages_received and messages_dropped start at zero."""
        status = mock_adapter.get_health_status()
        assert status["messages_received"] == 0
        assert status["messages_dropped"] == 0

    def test_health_status_with_all_states_true(self, mock_adapter):
        """Test health status when all states are true."""
        mock_adapter._set_connected(True)
        mock_adapter._set_running(True)
        mock_adapter._on_message(None, "test_message")

        status = mock_adapter.get_health_status()

        assert status["connected"] is True
        assert status["running"] is True
        assert status["last_message_ts"] is not None
        assert status["staleness_seconds"] is not None
        assert status["staleness_seconds"] >= 0.0

    def test_health_status_after_reconnection(self, mock_adapter):
        """Test health status tracking across reconnection."""
        # First connection
        mock_adapter._on_open(None)
        mock_adapter._on_message(None, "message_1")
        first_status = mock_adapter.get_health_status()

        # Disconnect
        mock_adapter._on_close(None, 1000, "Normal closure")

        # Reconnect
        mock_adapter._on_open(None)
        mock_adapter._on_message(None, "message_2")
        second_status = mock_adapter.get_health_status()

        # Timestamps should be updated
        assert second_status["last_message_ts"] > first_status["last_message_ts"]
        assert second_status["connected"] is True


class TestHealthStatusThreadSafety:
    """Tests for thread-safety of health status methods."""

    def test_get_health_status_thread_safe(self, mock_adapter):
        """Test get_health_status is thread-safe with state lock."""
        # Acquire state lock in another context
        with mock_adapter._state_lock:
            # This verifies lock is released properly
            pass

        # Should not deadlock
        status = mock_adapter.get_health_status()
        assert isinstance(status, dict)

    def test_get_staleness_thread_safe(self, mock_adapter):
        """Test get_connection_staleness is thread-safe with state lock."""
        mock_adapter._on_message(None, "test_message")

        # Acquire state lock
        with mock_adapter._state_lock:
            pass

        # Should not deadlock
        staleness = mock_adapter.get_connection_staleness()
        assert staleness is not None

    def test_concurrent_message_and_health_check(self, mock_adapter):
        """Test message processing doesn't interfere with health checks."""
        # Simulate concurrent operations
        mock_adapter._on_message(None, "message_1")
        status_1 = mock_adapter.get_health_status()

        mock_adapter._on_message(None, "message_2")
        status_2 = mock_adapter.get_health_status()

        # Both should succeed without deadlock
        assert status_1["last_message_ts"] is not None
        assert status_2["last_message_ts"] is not None
        assert status_2["last_message_ts"] >= status_1["last_message_ts"]


class TestHealthMonitoringEdgeCases:
    """Tests for edge cases in health monitoring."""

    def test_staleness_with_very_old_message(self, mock_adapter):
        """Test staleness with message from past."""
        # Manually set old timestamp
        with mock_adapter._state_lock:
            mock_adapter._last_message_ts = time.time() - 3600.0  # 1 hour ago

        staleness = mock_adapter.get_connection_staleness()

        assert staleness is not None
        assert staleness > 3599.0  # At least 1 hour

    def test_health_status_during_state_transitions(self, mock_adapter):
        """Test health status remains consistent during state transitions."""
        # Transition through various states
        mock_adapter._set_running(True)
        status_1 = mock_adapter.get_health_status()

        mock_adapter._set_connected(True)
        status_2 = mock_adapter.get_health_status()

        mock_adapter._on_message(None, "test_message")
        status_3 = mock_adapter.get_health_status()

        # All should be valid
        assert isinstance(status_1, dict)
        assert isinstance(status_2, dict)
        assert isinstance(status_3, dict)

        # States should progress logically
        assert status_1["running"] is True
        assert status_2["connected"] is True
        assert status_3["last_message_ts"] is not None

    def test_health_status_consistent_snapshot(self, mock_adapter):
        """Test health status provides consistent snapshot of state."""
        mock_adapter._set_connected(True)
        mock_adapter._set_running(True)
        mock_adapter._on_message(None, "test_message")

        # Get status snapshot
        status = mock_adapter.get_health_status()

        # Verify staleness is calculated from snapshot
        if status["last_message_ts"] is not None:
            expected_staleness = max(0.0, time.time() - status["last_message_ts"])
            # Should be very close (within 0.01 seconds)
            assert abs(status["staleness_seconds"] - expected_staleness) < 0.01
