"""Execution-related exceptions.

All execution module exceptions inherit from ExecutionError,
allowing callers to catch all execution errors with a single handler:

    try:
        await executor.execute_order(order)
    except ExecutionError as e:
        logger.error(f"Execution failed: {e}")
"""


class ExecutionError(Exception):
    """Base exception for all execution-related errors.

    Inherit from this class for any new execution exceptions
    to maintain a consistent exception hierarchy.
    """

    pass


class RateLimitExceeded(ExecutionError):
    """Raised when rate limit timeout expires.

    Attributes:
        key: The rate limit key that was exceeded
        wait_time: Suggested wait time before retry (seconds)
    """

    def __init__(self, key: str, wait_time: float = 0.0):
        self.key = key
        self.wait_time = wait_time
        super().__init__(
            f"Rate limit exceeded for '{key}', retry after {wait_time:.2f}s"
        )


class RedisConnectionError(ExecutionError):
    """Raised when Redis is unavailable.

    This is a wrapper around redis connection errors to provide
    a consistent interface for error handling.
    """

    def __init__(self, message: str = "Redis connection failed"):
        self.message = message
        super().__init__(message)


class OrderExecutionError(ExecutionError):
    """Raised when order execution fails.

    Attributes:
        order_id: The order identifier (if available)
        reason: Human-readable failure reason
    """

    def __init__(self, reason: str, order_id: str | None = None):
        self.order_id = order_id
        self.reason = reason
        msg = f"Order execution failed: {reason}"
        if order_id:
            msg = f"Order {order_id} execution failed: {reason}"
        super().__init__(msg)


class AuthenticationError(ExecutionError):
    """Raised when authentication with KIS API fails."""

    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(message)


class CircuitBreakerOpen(ExecutionError):
    """Raised when circuit breaker is open.

    Attributes:
        component: The component that triggered the circuit breaker
        reset_time: Estimated time until circuit breaker resets (seconds)
    """

    def __init__(self, component: str, reset_time: float = 0.0):
        self.component = component
        self.reset_time = reset_time
        super().__init__(
            f"Circuit breaker open for '{component}', "
            f"retry after {reset_time:.1f}s"
        )
