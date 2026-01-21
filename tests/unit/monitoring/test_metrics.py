"""Test Prometheus metrics."""
import pytest


def test_metrics_registry():
    """Test metrics can be created."""
    from shared.monitoring.metrics import TradingMetrics

    metrics = TradingMetrics()

    # Record some metrics
    metrics.record_trade("005930", "BUY", 1000)
    metrics.record_order_latency(0.05)
    metrics.set_position_count(3)

    # Verify counters exist
    assert metrics.trades_total is not None
    assert metrics.order_latency is not None


def test_metrics_export():
    """Test metrics can be exported."""
    from shared.monitoring.metrics import TradingMetrics

    metrics = TradingMetrics()
    metrics.record_trade("005930", "BUY", 1000)

    # Should be able to get text output
    output = metrics.export()
    assert "trades_total" in output


def test_metrics_singleton_pattern():
    """Test that TradingMetrics follows singleton pattern."""
    from shared.monitoring.metrics import TradingMetrics

    metrics1 = TradingMetrics()
    metrics2 = TradingMetrics()

    # Same instance
    assert metrics1 is metrics2


def test_metrics_reset_instance():
    """Test that reset_instance creates a fresh singleton."""
    from shared.monitoring.metrics import TradingMetrics

    # Get first instance
    metrics1 = TradingMetrics()
    assert metrics1._initialized is True

    # Reset
    TradingMetrics.reset_instance()
    assert TradingMetrics._instance is None
    assert TradingMetrics._initialized is False

    # Get new instance (should be different)
    metrics2 = TradingMetrics()
    # After reset, a new instance can be created
    assert metrics2._initialized is True
