"""Pytest fixtures for monitoring tests."""
import pytest

from shared.monitoring.metrics import TradingMetrics


@pytest.fixture(autouse=True)
def reset_metrics_singleton():
    """Reset metrics singleton between tests for isolation.

    This fixture runs automatically for every test in the monitoring
    test directory to ensure metrics state doesn't leak between tests.
    """
    # Run the test
    yield
    # Cleanup: reset singleton after test
    TradingMetrics.reset_instance()
