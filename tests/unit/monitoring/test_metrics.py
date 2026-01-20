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
