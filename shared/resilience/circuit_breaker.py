"""Unified circuit breaker implementation.

Provides fault tolerance for external service calls by tracking
failures and temporarily blocking requests when a service is unhealthy.

States:
    CLOSED: Normal operation, requests pass through
    OPEN: Service failing, requests blocked for reset_timeout
    HALF_OPEN: Testing if service recovered

Usage:
    breaker = CircuitBreaker(
        name="redis",
        failure_threshold=5,
        reset_timeout=30.0,
    )

    if breaker.is_available():
        try:
            result = await call_service()
            breaker.record_success()
        except Exception:
            breaker.record_failure()
    else:
        # Use fallback or raise error
        ...
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Generator, Optional

if TYPE_CHECKING:
    from shared.resilience.metrics import CircuitBreakerMetrics

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker.

    Attributes:
        failure_threshold: Consecutive failures before opening circuit
        reset_timeout: Seconds to wait before attempting recovery
        half_open_max_calls: Successful calls required in half-open to close
    """

    failure_threshold: int = 5
    reset_timeout: float = 30.0
    half_open_max_calls: int = 2

    # Aliases for compatibility with existing code
    @property
    def recovery_timeout_seconds(self) -> float:
        """Alias for reset_timeout (auth.py compatibility)."""
        return self.reset_timeout


class CircuitBreaker:
    """Circuit breaker for external service failures.

    Thread-safe implementation that can be used in both sync and async contexts.
    Tracks consecutive failures and temporarily blocks requests to prevent
    cascading failures.

    Attributes:
        name: Identifier for logging and status reporting
        config: Circuit breaker configuration
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        half_open_max_calls: int = 2,
        *,
        config: CircuitBreakerConfig | None = None,
        thread_safe: bool = True,
        metrics: Optional["CircuitBreakerMetrics"] = None,
    ):
        """Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker
            failure_threshold: Consecutive failures before opening
            reset_timeout: Seconds to wait before attempting recovery
            half_open_max_calls: Successes required in half-open to close
            config: Optional config object (overrides individual params)
            thread_safe: Whether to use locking for thread safety
            metrics: Optional Prometheus metrics collector
        """
        self.name = name

        # Use config if provided, otherwise use individual params
        if config is not None:
            self._failure_threshold = config.failure_threshold
            self._reset_timeout = config.reset_timeout
            self._half_open_max_calls = config.half_open_max_calls
        else:
            self._failure_threshold = failure_threshold
            self._reset_timeout = reset_timeout
            self._half_open_max_calls = half_open_max_calls

        # Internal state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: float = 0.0
        self._open_start_time: float = 0.0  # For tracking open duration

        # Thread safety
        self._thread_safe = thread_safe
        self._lock = threading.Lock() if thread_safe else None

        # Prometheus metrics (optional)
        self._metrics = metrics
        if self._metrics:
            self._metrics.set_state(self.name, self._state.value)

    @contextmanager
    def _locked(self) -> Generator[None, None, None]:
        """Context manager for thread-safe lock acquisition.

        Yields immediately if thread safety is disabled.
        """
        if self._lock:
            with self._lock:
                yield
        else:
            yield

    @property
    def state(self) -> CircuitState:
        """Get current circuit breaker state.

        Automatically transitions from OPEN to HALF_OPEN after reset_timeout.
        """
        with self._locked():
            self._check_state_transition()
            return self._state

    def _check_state_transition(self) -> None:
        """Check and perform automatic state transitions (no lock)."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self._reset_timeout:
                old_state = self._state
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN")

                # Record metrics
                if self._metrics:
                    self._metrics.record_state_change(
                        self.name, old_state.value, self._state.value
                    )
                    # Record open duration
                    if self._open_start_time > 0:
                        duration = time.time() - self._open_start_time
                        self._metrics.record_open_duration(self.name, duration)

    def is_available(self) -> bool:
        """Check if requests should be allowed through.

        Returns:
            True if circuit is CLOSED or HALF_OPEN (with capacity)
        """
        with self._locked():
            self._check_state_transition()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.HALF_OPEN:
                # Allow calls up to half_open_max_calls limit
                return self._half_open_calls < self._half_open_max_calls

            return False  # OPEN

    def can_execute(self) -> bool:
        """Alias for is_available() (auth.py compatibility)."""
        return self.is_available()

    @property
    def is_open(self) -> bool:
        """Check if circuit is blocking requests.

        Returns:
            True if requests should be blocked (OPEN state or HALF_OPEN at capacity)

        Note:
            This is the inverse of is_available() for compatibility with
            code that uses `if breaker.is_open: skip_execution`
        """
        return not self.is_available()

    def record_success(self) -> None:
        """Record a successful operation."""
        with self._locked():
            self._success_count += 1

            # Record metrics
            if self._metrics:
                self._metrics.record_success(self.name)

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self._half_open_max_calls:
                    self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed operation."""
        with self._locked():
            self._failure_count += 1
            self._last_failure_time = time.time()
            self._success_count = 0

            # Record metrics
            if self._metrics:
                self._metrics.record_failure(self.name)

            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery - reopen
                self._transition_to_open()
            elif self._failure_count >= self._failure_threshold:
                self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition to OPEN state (no lock)."""
        old_state = self._state
        self._state = CircuitState.OPEN
        self._open_start_time = time.time()
        logger.warning(
            f"Circuit breaker '{self.name}' OPENED (failures: {self._failure_count})"
        )

        # Record metrics
        if self._metrics:
            self._metrics.record_state_change(
                self.name, old_state.value, self._state.value
            )

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state (no lock)."""
        old_state = self._state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        logger.info(f"Circuit breaker '{self.name}' CLOSED")

        # Record metrics
        if self._metrics:
            self._metrics.record_state_change(
                self.name, old_state.value, self._state.value
            )
            # Record open duration if we were open
            if old_state == CircuitState.OPEN and self._open_start_time > 0:
                duration = time.time() - self._open_start_time
                self._metrics.record_open_duration(self.name, duration)

    def get_reset_time(self) -> float:
        """Get time remaining until circuit breaker resets.

        Returns:
            Seconds until transition to HALF_OPEN, or 0.0 if not OPEN
        """
        with self._locked():
            if self._state != CircuitState.OPEN:
                return 0.0
            elapsed = time.time() - self._last_failure_time
            return max(0.0, self._reset_timeout - elapsed)

    def reset(self) -> None:
        """Force reset to CLOSED state."""
        with self._locked():
            self._transition_to_closed()

    def get_status(self) -> dict[str, Any]:
        """Get current status for monitoring.

        Returns:
            Dict with state, failure_count, last_failure, and config info
        """
        with self._locked():
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "half_open_calls": self._half_open_calls,
                "last_failure": (
                    datetime.fromtimestamp(self._last_failure_time).isoformat()
                    if self._last_failure_time > 0
                    else None
                ),
                "config": {
                    "failure_threshold": self._failure_threshold,
                    "reset_timeout": self._reset_timeout,
                    "half_open_max_calls": self._half_open_max_calls,
                },
            }

    # Configuration property accessors for compatibility
    @property
    def failure_threshold(self) -> int:
        """Get failure threshold."""
        return self._failure_threshold

    @property
    def reset_timeout(self) -> float:
        """Get reset timeout."""
        return self._reset_timeout

    @property
    def half_open_max_calls(self) -> int:
        """Get half-open max calls."""
        return self._half_open_max_calls
