"""Resilience patterns for fault tolerance.

Provides circuit breaker and retry utilities for handling
failures in external service calls.
"""

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from .metrics import CircuitBreakerMetrics, get_circuit_breaker_metrics
from .retry import retry_on_disconnect

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "CircuitBreakerMetrics",
    "get_circuit_breaker_metrics",
    "retry_on_disconnect",
]
