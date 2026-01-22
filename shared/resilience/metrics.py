"""Prometheus metrics for resilience patterns.

Provides metrics collection for CircuitBreaker and other resilience patterns.

Usage:
    from shared.resilience.metrics import CircuitBreakerMetrics

    # Create metrics (singleton)
    metrics = CircuitBreakerMetrics()

    # Record state changes
    metrics.record_state_change("redis", "open")
    metrics.record_failure("redis")
    metrics.record_success("redis")
"""

import logging
from typing import Optional

try:
    from prometheus_client import Counter, Gauge, Histogram, REGISTRY

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CircuitBreakerMetrics:
    """Prometheus metrics for circuit breakers.

    Metrics:
    - circuit_breaker_state: Current state (0=closed, 1=half_open, 2=open)
    - circuit_breaker_failures_total: Total failure count
    - circuit_breaker_successes_total: Total success count
    - circuit_breaker_state_changes_total: State transition count
    - circuit_breaker_open_duration_seconds: Time spent in open state
    """

    _instance: Optional["CircuitBreakerMetrics"] = None
    _initialized: bool = False

    # State numeric values for gauge
    STATE_VALUES = {"closed": 0, "half_open": 1, "open": 2}

    def __new__(cls, prefix: str = "circuit_breaker"):
        """Singleton pattern to avoid duplicate metric registration."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton for testing purposes."""
        cls._instance = None
        cls._initialized = False

    def __init__(self, prefix: str = "circuit_breaker"):
        if self._initialized:
            return

        self.prefix = prefix

        if PROMETHEUS_AVAILABLE:
            try:
                self.state = Gauge(
                    f"{prefix}_state",
                    "Current circuit breaker state (0=closed, 1=half_open, 2=open)",
                    ["name"],
                )
                self.failures_total = Counter(
                    f"{prefix}_failures_total",
                    "Total number of recorded failures",
                    ["name"],
                )
                self.successes_total = Counter(
                    f"{prefix}_successes_total",
                    "Total number of recorded successes",
                    ["name"],
                )
                self.state_changes_total = Counter(
                    f"{prefix}_state_changes_total",
                    "Total number of state transitions",
                    ["name", "from_state", "to_state"],
                )
                self.open_duration = Histogram(
                    f"{prefix}_open_duration_seconds",
                    "Duration spent in open state before recovery",
                    ["name"],
                    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
                )
                self._initialized = True
                logger.debug("CircuitBreakerMetrics initialized")
            except ValueError:
                # Metrics already registered
                logger.debug("CircuitBreakerMetrics already registered, reusing")
                self._retrieve_existing_metrics(prefix)
                self._initialized = True
        else:
            logger.warning("prometheus_client not available, metrics disabled")
            self.state = None
            self.failures_total = None
            self.successes_total = None
            self.state_changes_total = None
            self.open_duration = None
            self._initialized = True

    def _retrieve_existing_metrics(self, prefix: str) -> None:
        """Retrieve already registered metrics from registry."""
        self.state = REGISTRY._names_to_collectors.get(f"{prefix}_state")
        self.failures_total = REGISTRY._names_to_collectors.get(
            f"{prefix}_failures_total"
        )
        self.successes_total = REGISTRY._names_to_collectors.get(
            f"{prefix}_successes_total"
        )
        self.state_changes_total = REGISTRY._names_to_collectors.get(
            f"{prefix}_state_changes_total"
        )
        self.open_duration = REGISTRY._names_to_collectors.get(
            f"{prefix}_open_duration_seconds"
        )

    def record_failure(self, name: str) -> None:
        """Record a failure for a circuit breaker."""
        if self.failures_total:
            self.failures_total.labels(name=name).inc()

    def record_success(self, name: str) -> None:
        """Record a success for a circuit breaker."""
        if self.successes_total:
            self.successes_total.labels(name=name).inc()

    def record_state_change(
        self, name: str, from_state: str, to_state: str
    ) -> None:
        """Record a state transition.

        Args:
            name: Circuit breaker name
            from_state: Previous state ("closed", "open", "half_open")
            to_state: New state
        """
        if self.state_changes_total:
            self.state_changes_total.labels(
                name=name, from_state=from_state, to_state=to_state
            ).inc()

        if self.state:
            state_value = self.STATE_VALUES.get(to_state, 0)
            self.state.labels(name=name).set(state_value)

    def set_state(self, name: str, state: str) -> None:
        """Set the current state gauge.

        Args:
            name: Circuit breaker name
            state: Current state ("closed", "open", "half_open")
        """
        if self.state:
            state_value = self.STATE_VALUES.get(state, 0)
            self.state.labels(name=name).set(state_value)

    def record_open_duration(self, name: str, duration_seconds: float) -> None:
        """Record duration spent in open state.

        Call this when transitioning from open to half_open or closed.

        Args:
            name: Circuit breaker name
            duration_seconds: Time spent in open state
        """
        if self.open_duration:
            self.open_duration.labels(name=name).observe(duration_seconds)

    @property
    def enabled(self) -> bool:
        """Check if metrics are enabled."""
        return self.state is not None


# Global metrics instance (lazy initialization)
_metrics: Optional[CircuitBreakerMetrics] = None


def get_circuit_breaker_metrics() -> CircuitBreakerMetrics:
    """Get or create the global circuit breaker metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = CircuitBreakerMetrics()
    return _metrics
