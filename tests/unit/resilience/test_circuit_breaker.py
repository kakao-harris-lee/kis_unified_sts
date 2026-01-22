"""Tests for CircuitBreaker."""

import threading
import time
from unittest.mock import patch

import pytest

from shared.resilience import CircuitBreaker, CircuitBreakerConfig, CircuitState


class TestCircuitBreakerBasic:
    """Test basic CircuitBreaker functionality."""

    def test_initial_state_is_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker(name="test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_available() is True
        assert breaker.is_open is False

    def test_config_params(self):
        """Test configuration via individual parameters."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=3,
            reset_timeout=10.0,
            half_open_max_calls=1,
        )
        assert breaker.failure_threshold == 3
        assert breaker.reset_timeout == 10.0
        assert breaker.half_open_max_calls == 1

    def test_config_object(self):
        """Test configuration via CircuitBreakerConfig object."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            reset_timeout=60.0,
            half_open_max_calls=5,
        )
        breaker = CircuitBreaker(name="test", config=config)
        assert breaker.failure_threshold == 10
        assert breaker.reset_timeout == 60.0
        assert breaker.half_open_max_calls == 5

    def test_config_object_overrides_params(self):
        """Test that config object overrides individual params."""
        config = CircuitBreakerConfig(failure_threshold=10)
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=3,  # Should be overridden
            config=config,
        )
        assert breaker.failure_threshold == 10


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig dataclass."""

    def test_defaults(self):
        """Test default config values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.reset_timeout == 30.0
        assert config.half_open_max_calls == 2

    def test_recovery_timeout_alias(self):
        """Test recovery_timeout_seconds alias for compatibility."""
        config = CircuitBreakerConfig(reset_timeout=45.0)
        assert config.recovery_timeout_seconds == 45.0


class TestCircuitBreakerStateTransitions:
    """Test state transition logic."""

    def test_closed_to_open_on_failure_threshold(self):
        """Test transition from CLOSED to OPEN when failures reach threshold."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        # Record failures up to threshold
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        breaker.record_failure()  # 3rd failure - should open

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_available() is False
        assert breaker.is_open is True

    def test_success_resets_failure_count_in_closed(self):
        """Test that success resets failure count in CLOSED state."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        breaker.record_success()  # Should reset failure count

        # Now we need 3 more failures to open
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED  # Still closed

    def test_open_to_half_open_after_timeout(self):
        """Test transition from OPEN to HALF_OPEN after reset timeout."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            reset_timeout=0.1,  # 100ms for fast tests
        )

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for reset timeout
        time.sleep(0.15)

        # State should now be HALF_OPEN
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.is_available() is True

    def test_half_open_to_closed_on_success(self):
        """Test transition from HALF_OPEN to CLOSED on successful calls."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            reset_timeout=0.05,
            half_open_max_calls=2,
        )

        # Open the circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for reset
        time.sleep(0.1)
        assert breaker.state == CircuitState.HALF_OPEN

        # Record successes
        breaker.record_success()
        assert breaker.state == CircuitState.HALF_OPEN
        breaker.record_success()  # 2nd success - should close

        assert breaker.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self):
        """Test transition from HALF_OPEN back to OPEN on failure."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            reset_timeout=0.05,
        )

        # Open the circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for reset
        time.sleep(0.1)
        assert breaker.state == CircuitState.HALF_OPEN

        # Failure should reopen
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN


class TestHalfOpenCapacity:
    """Test HALF_OPEN call limiting."""

    def test_half_open_limits_concurrent_calls(self):
        """Test that HALF_OPEN state limits concurrent test calls."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            reset_timeout=0.05,
            half_open_max_calls=2,
        )

        # Open the circuit
        breaker.record_failure()
        time.sleep(0.1)  # Wait for HALF_OPEN

        assert breaker.state == CircuitState.HALF_OPEN

        # First two calls should be allowed
        assert breaker.is_available() is True
        breaker.record_success()  # Increments half_open_calls to 1

        assert breaker.is_available() is True
        breaker.record_success()  # Increments to 2, closes circuit

        # Circuit should now be CLOSED
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerReset:
    """Test reset functionality."""

    def test_reset_from_open(self):
        """Test force reset from OPEN state."""
        breaker = CircuitBreaker(name="test", failure_threshold=1)

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_available() is True

    def test_reset_clears_failure_count(self):
        """Test that reset clears failure count."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        breaker.record_failure()
        breaker.record_failure()

        breaker.reset()

        # Now we need 3 failures to open again
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED


class TestGetResetTime:
    """Test get_reset_time functionality."""

    def test_reset_time_when_closed(self):
        """Test get_reset_time returns 0 when CLOSED."""
        breaker = CircuitBreaker(name="test")
        assert breaker.get_reset_time() == 0.0

    def test_reset_time_when_open(self):
        """Test get_reset_time returns remaining time when OPEN."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            reset_timeout=10.0,
        )

        breaker.record_failure()

        reset_time = breaker.get_reset_time()
        assert 9.0 < reset_time <= 10.0  # Allow some tolerance

    def test_reset_time_decreases(self):
        """Test that reset time decreases over time."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            reset_timeout=1.0,
        )

        breaker.record_failure()
        initial_time = breaker.get_reset_time()

        time.sleep(0.2)
        later_time = breaker.get_reset_time()

        assert later_time < initial_time


class TestGetStatus:
    """Test status reporting."""

    def test_status_includes_all_fields(self):
        """Test that get_status returns all required fields."""
        breaker = CircuitBreaker(
            name="test-breaker",
            failure_threshold=5,
            reset_timeout=30.0,
            half_open_max_calls=2,
        )

        status = breaker.get_status()

        assert status["name"] == "test-breaker"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["success_count"] == 0
        assert status["half_open_calls"] == 0
        assert status["last_failure"] is None
        assert status["config"]["failure_threshold"] == 5
        assert status["config"]["reset_timeout"] == 30.0
        assert status["config"]["half_open_max_calls"] == 2

    def test_status_updates_after_failures(self):
        """Test that status reflects failures."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)

        breaker.record_failure()
        breaker.record_failure()

        status = breaker.get_status()
        assert status["failure_count"] == 2
        assert status["last_failure"] is not None

    def test_status_updates_after_success(self):
        """Test that status reflects successes."""
        breaker = CircuitBreaker(name="test")

        breaker.record_success()
        breaker.record_success()
        breaker.record_success()

        status = breaker.get_status()
        assert status["success_count"] == 3


class TestCompatibilityAliases:
    """Test compatibility methods and properties."""

    def test_can_execute_alias(self):
        """Test can_execute() is alias for is_available()."""
        breaker = CircuitBreaker(name="test")

        assert breaker.can_execute() == breaker.is_available()

        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()  # Opens circuit

        assert breaker.can_execute() == breaker.is_available()
        assert breaker.can_execute() is False

    def test_is_open_is_inverse_of_is_available(self):
        """Test is_open is inverse of is_available."""
        breaker = CircuitBreaker(name="test", failure_threshold=1)

        assert breaker.is_open is False
        assert breaker.is_available() is True

        breaker.record_failure()

        assert breaker.is_open is True
        assert breaker.is_available() is False


class TestThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_failures(self):
        """Test concurrent failure recording is thread-safe."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=100,
            thread_safe=True,
        )

        def record_failures():
            for _ in range(10):
                breaker.record_failure()

        threads = [threading.Thread(target=record_failures) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 100 failures recorded
        status = breaker.get_status()
        assert status["failure_count"] == 100

    def test_concurrent_successes(self):
        """Test concurrent success recording is thread-safe."""
        breaker = CircuitBreaker(name="test", thread_safe=True)

        def record_successes():
            for _ in range(10):
                breaker.record_success()

        threads = [threading.Thread(target=record_successes) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        status = breaker.get_status()
        assert status["success_count"] == 100

    def test_no_thread_safety(self):
        """Test that thread_safe=False disables locking."""
        breaker = CircuitBreaker(name="test", thread_safe=False)

        assert breaker._lock is None

        # Should still work in single-threaded context
        breaker.record_failure()
        breaker.record_success()
        _ = breaker.state
        _ = breaker.is_available()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_failure_threshold(self):
        """Test with very small failure threshold."""
        breaker = CircuitBreaker(name="test", failure_threshold=1)

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_very_short_reset_timeout(self):
        """Test with very short reset timeout."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            reset_timeout=0.01,
        )

        breaker.record_failure()
        time.sleep(0.02)

        assert breaker.state == CircuitState.HALF_OPEN

    def test_single_half_open_call(self):
        """Test with half_open_max_calls=1."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            reset_timeout=0.01,
            half_open_max_calls=1,
        )

        breaker.record_failure()
        time.sleep(0.02)

        assert breaker.state == CircuitState.HALF_OPEN
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_multiple_resets(self):
        """Test multiple reset calls are safe."""
        breaker = CircuitBreaker(name="test")

        breaker.reset()
        breaker.reset()
        breaker.reset()

        assert breaker.state == CircuitState.CLOSED

    def test_success_in_open_state_no_effect(self):
        """Test that success while OPEN doesn't change state."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            reset_timeout=100,  # Long timeout
        )

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        breaker.record_success()  # Should have no effect
        assert breaker.state == CircuitState.OPEN


class TestLogging:
    """Test logging behavior."""

    def test_logs_state_transitions(self, caplog):
        """Test that state transitions are logged."""
        import logging

        with caplog.at_level(logging.INFO):
            breaker = CircuitBreaker(
                name="test-logger",
                failure_threshold=1,
                reset_timeout=0.01,
            )

            breaker.record_failure()  # Should log OPEN
            time.sleep(0.02)
            _ = breaker.state  # Should log HALF_OPEN

        assert "OPENED" in caplog.text
        assert "test-logger" in caplog.text
        assert "HALF_OPEN" in caplog.text
