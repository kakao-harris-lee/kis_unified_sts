"""Execution-related exceptions."""


class RateLimitExceeded(Exception):
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


class RedisConnectionError(Exception):
    """Raised when Redis is unavailable.

    This is a wrapper around redis connection errors to provide
    a consistent interface for error handling.
    """

    def __init__(self, message: str = "Redis connection failed"):
        self.message = message
        super().__init__(message)
