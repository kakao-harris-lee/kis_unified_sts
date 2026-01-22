"""Tests for CircuitBreaker Prometheus metrics."""

import time

import pytest

from shared.resilience import CircuitBreaker, CircuitBreakerMetrics, CircuitState


@pytest.fixture
def metrics():
    """Create fresh metrics instance for each test."""
    CircuitBreakerMetrics.reset_instance()
    m = CircuitBreakerMetrics(prefix="test_circuit_breaker")
    yield m
    CircuitBreakerMetrics.reset_instance()


class TestCircuitBreakerMetrics:
    """Test CircuitBreakerMetrics class."""

    def test_metrics_singleton(self, metrics):
        """Test that metrics is a singleton."""
        m2 = CircuitBreakerMetrics()
        assert m2 is metrics

    def test_metrics_enabled(self, metrics):
        """Test that metrics are enabled when prometheus_client is available."""
        # prometheus_client is in dependencies
        assert metrics.enabled is True

    def test_record_failure(self, metrics):
        """Test recording failures."""
        metrics.record_failure("test-breaker")
        # Should not raise
        metrics.record_failure("test-breaker")

    def test_record_success(self, metrics):
        """Test recording successes."""
        metrics.record_success("test-breaker")
        # Should not raise
        metrics.record_success("test-breaker")

    def test_record_state_change(self, metrics):
        """Test recording state changes."""
        metrics.record_state_change("test-breaker", "closed", "open")
        metrics.record_state_change("test-breaker", "open", "half_open")
        metrics.record_state_change("test-breaker", "half_open", "closed")
        # Should not raise

    def test_set_state(self, metrics):
        """Test setting state gauge."""
        metrics.set_state("test-breaker", "closed")
        metrics.set_state("test-breaker", "open")
        metrics.set_state("test-breaker", "half_open")
        # Should not raise

    def test_record_open_duration(self, metrics):
        """Test recording open duration."""
        metrics.record_open_duration("test-breaker", 10.5)
        # Should not raise


class TestCircuitBreakerWithMetrics:
    """Test CircuitBreaker integration with metrics."""

    def test_breaker_with_metrics(self, metrics):
        """Test circuit breaker with metrics enabled."""
        breaker = CircuitBreaker(
            name="test-with-metrics",
            failure_threshold=2,
            metrics=metrics,
        )

        assert breaker.state == CircuitState.CLOSED

    def test_metrics_recorded_on_failure(self, metrics):
        """Test that metrics are recorded on failure."""
        breaker = CircuitBreaker(
            name="test-failure-metrics",
            failure_threshold=3,
            metrics=metrics,
        )

        breaker.record_failure()
        breaker.record_failure()

        # Should not have opened yet (threshold is 3)
        assert breaker.state == CircuitState.CLOSED

    def test_metrics_recorded_on_success(self, metrics):
        """Test that metrics are recorded on success."""
        breaker = CircuitBreaker(
            name="test-success-metrics",
            failure_threshold=3,
            metrics=metrics,
        )

        breaker.record_success()
        breaker.record_success()

        # Should still be closed
        assert breaker.state == CircuitState.CLOSED

    def test_metrics_recorded_on_state_transition_to_open(self, metrics):
        """Test that metrics are recorded when circuit opens."""
        breaker = CircuitBreaker(
            name="test-open-metrics",
            failure_threshold=2,
            metrics=metrics,
        )

        breaker.record_failure()
        breaker.record_failure()  # Should open

        assert breaker.state == CircuitState.OPEN

    def test_metrics_recorded_on_state_transition_to_half_open(self, metrics):
        """Test that metrics are recorded when circuit goes half-open."""
        breaker = CircuitBreaker(
            name="test-half-open-metrics",
            failure_threshold=1,
            reset_timeout=0.05,
            metrics=metrics,
        )

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        time.sleep(0.1)
        assert breaker.state == CircuitState.HALF_OPEN

    def test_metrics_recorded_on_state_transition_to_closed(self, metrics):
        """Test that metrics are recorded when circuit closes."""
        breaker = CircuitBreaker(
            name="test-close-metrics",
            failure_threshold=1,
            reset_timeout=0.05,
            half_open_max_calls=1,
            metrics=metrics,
        )

        # Open the circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for half-open
        time.sleep(0.1)
        assert breaker.state == CircuitState.HALF_OPEN

        # Close with success
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_breaker_without_metrics_still_works(self):
        """Test that circuit breaker works without metrics."""
        breaker = CircuitBreaker(
            name="test-no-metrics",
            failure_threshold=2,
            # No metrics parameter
        )

        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerMetricsStateValues:
    """Test state numeric values for metrics."""

    def test_state_values_mapping(self):
        """Test that state values are correctly mapped."""
        assert CircuitBreakerMetrics.STATE_VALUES["closed"] == 0
        assert CircuitBreakerMetrics.STATE_VALUES["half_open"] == 1
        assert CircuitBreakerMetrics.STATE_VALUES["open"] == 2
