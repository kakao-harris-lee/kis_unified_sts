"""Prometheus metrics for trading system."""
import logging

try:
    from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


class TradingMetrics:
    """Trading system metrics for Prometheus.

    Metrics:
    - trades_total: Total number of trades
    - order_latency: Order execution latency
    - position_count: Current position count
    - equity: Current equity value
    - pnl_total: Total P&L
    """

    _instance = None
    _initialized = False

    # Use a distinct default prefix to avoid metric name collisions with
    # services.monitoring.metrics (which also defines "trading_*" series).
    def __new__(cls, prefix: str = "internal_trading"):
        """Singleton pattern to avoid duplicate metric registration."""
        _ = prefix
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton for testing purposes.

        This method should only be used in tests to ensure
        test isolation. It clears the singleton instance so
        a new one can be created.

        Usage in tests:
            @pytest.fixture(autouse=True)
            def reset_metrics():
                yield
                TradingMetrics.reset_instance()
        """
        cls._instance = None
        cls._initialized = False

    def __init__(self, prefix: str = "internal_trading"):
        if self._initialized:
            return

        self.prefix = prefix

        if PROMETHEUS_AVAILABLE:
            try:
                self.trades_total = Counter(
                    f"{prefix}_trades_total",
                    "Total number of trades",
                    ["symbol", "side"],
                )
                self.order_latency = Histogram(
                    f"{prefix}_order_latency_seconds",
                    "Order execution latency",
                    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
                )
                self.position_count = Gauge(
                    f"{prefix}_position_count",
                    "Current number of positions",
                )
                self.equity = Gauge(
                    f"{prefix}_equity",
                    "Current portfolio equity",
                )
                self.pnl_total = Gauge(
                    f"{prefix}_pnl_total",
                    "Total realized P&L",
                )
                self._initialized = True
            except ValueError:
                # Metrics already registered, retrieve from registry
                logger.debug("Metrics already registered, reusing existing")
                self.trades_total = REGISTRY._names_to_collectors.get(f"{prefix}_trades_total")
                self.order_latency = REGISTRY._names_to_collectors.get(f"{prefix}_order_latency_seconds")
                self.position_count = REGISTRY._names_to_collectors.get(f"{prefix}_position_count")
                self.equity = REGISTRY._names_to_collectors.get(f"{prefix}_equity")
                self.pnl_total = REGISTRY._names_to_collectors.get(f"{prefix}_pnl_total")
                self._initialized = True
        else:
            logger.warning("prometheus_client not installed, metrics disabled")
            self.trades_total = None
            self.order_latency = None
            self.position_count = None
            self.equity = None
            self.pnl_total = None
            self._initialized = True

    def record_trade(self, symbol: str, side: str, pnl: float) -> None:
        """Record a completed trade."""
        if self.trades_total:
            self.trades_total.labels(symbol=symbol, side=side).inc()
        if self.pnl_total:
            self.pnl_total.inc(pnl)

    def record_order_latency(self, latency_seconds: float) -> None:
        """Record order execution latency."""
        if self.order_latency:
            self.order_latency.observe(latency_seconds)

    def set_position_count(self, count: int) -> None:
        """Set current position count."""
        if self.position_count:
            self.position_count.set(count)

    def set_equity(self, value: float) -> None:
        """Set current equity value."""
        if self.equity:
            self.equity.set(value)

    def export(self) -> str:
        """Export metrics in Prometheus format."""
        if PROMETHEUS_AVAILABLE:
            return generate_latest(REGISTRY).decode("utf-8")
        return ""
