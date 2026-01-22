"""Distributed rate limiter using Redis.

Provides cross-process rate limiting for KIS API calls using
Redis sorted sets with sliding window algorithm.

Features:
- Redis-based distributed rate limiting
- In-memory fallback when Redis is unavailable
- Circuit breaker for Redis failures
- Metrics caching for reduced Redis load

Usage:
    limiter = RedisRateLimiter(
        redis_url="redis://localhost:6379",
        key_prefix="stock",
        requests_per_second=20.0,
    )

    # Acquire permission before API call
    if await limiter.acquire():
        response = await api.call()
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import deque
from typing import TYPE_CHECKING

from .exceptions import CircuitBreakerOpen, RateLimitExceeded

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def _sanitize_redis_url(url: str) -> str:
    """Remove password from Redis URL for safe logging."""
    # Pattern: redis://[:password@]host:port/db
    return re.sub(r"(rediss?://[^:]*:)[^@]+(@)", r"\1****\2", url)


# Expiry multiplier for Redis keys: keys expire after this multiple of window_size.
# Using 2x ensures keys aren't prematurely expired during normal operation while
# still preventing memory leaks from abandoned rate limit keys.
EXPIRE_WINDOW_MULTIPLIER = 2

# Lua script for atomic rate limit check-and-increment
# Uses sorted set with timestamps as scores for sliding window
RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local request_id = ARGV[4]
local expire_multiplier = tonumber(ARGV[5])

-- Remove entries older than the window
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current requests in window
local count = redis.call('ZCARD', key)

if count < max_requests then
    -- Add this request with current timestamp as score
    redis.call('ZADD', key, now, request_id)
    -- Set expiry to prevent memory leaks (multiplier * window for safety)
    redis.call('EXPIRE', key, math.ceil(window * expire_multiplier))
    return 1  -- Allowed
else
    return 0  -- Rate limited
end
"""


class InMemoryRateLimiter:
    """Simple in-memory sliding window rate limiter.

    Used as fallback when Redis is unavailable. Provides local-only
    rate limiting (not distributed across processes).
    """

    def __init__(self, max_requests: int, window_size: float):
        """Initialize in-memory rate limiter.

        Args:
            max_requests: Maximum requests allowed per window
            window_size: Window size in seconds
        """
        self.max_requests = max_requests
        self.window_size = window_size
        self._timestamps: deque[float] = deque()

    def acquire(self) -> bool:
        """Try to acquire a rate limit slot.

        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()
        cutoff = now - self.window_size

        # Remove expired timestamps
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

        # Check if under limit
        if len(self._timestamps) < self.max_requests:
            self._timestamps.append(now)
            return True

        return False

    def get_usage(self) -> int:
        """Get current number of requests in window."""
        now = time.time()
        cutoff = now - self.window_size

        # Remove expired timestamps
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

        return len(self._timestamps)


class CircuitBreaker:
    """Circuit breaker for external service failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests blocked for reset_timeout
    - HALF_OPEN: Testing if service recovered
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 30.0):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Consecutive failures before opening
            reset_timeout: Seconds to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._success_count = 0

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        if self._state == self.OPEN:
            # Check if we should transition to half-open
            if time.time() - self._last_failure_time >= self.reset_timeout:
                self._state = self.HALF_OPEN
        return self._state

    def is_available(self) -> bool:
        """Check if requests should be allowed through."""
        return self.state != self.OPEN

    def record_success(self) -> None:
        """Record a successful operation."""
        if self._state == self.HALF_OPEN:
            self._success_count += 1
            # Require 2 successes to close circuit
            if self._success_count >= 2:
                self._state = self.CLOSED
                self._failure_count = 0
                self._success_count = 0
                logger.info("Circuit breaker closed - service recovered")
        elif self._state == self.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        self._success_count = 0

        if self._state == self.HALF_OPEN:
            # Failed during recovery attempt - reopen
            self._state = self.OPEN
            logger.warning("Circuit breaker reopened - recovery failed")
        elif self._failure_count >= self.failure_threshold:
            self._state = self.OPEN
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures"
            )

    def get_reset_time(self) -> float:
        """Get time remaining until circuit breaker resets."""
        if self._state != self.OPEN:
            return 0.0
        elapsed = time.time() - self._last_failure_time
        return max(0.0, self.reset_timeout - elapsed)


class RedisRateLimiter:
    """Distributed rate limiter using Redis sliding window.

    Uses Redis sorted sets for precise sliding window rate limiting.
    More accurate than token bucket for bursty traffic patterns.

    Features:
    - Distributed rate limiting via Redis
    - In-memory fallback when Redis unavailable
    - Circuit breaker to prevent cascading failures
    - Configurable retry behavior with exponential backoff
    - Metrics caching to reduce Redis load

    Attributes:
        key: Redis key for this rate limiter
        max_requests: Maximum requests allowed per window
        window_size: Window size in seconds
    """

    def __init__(
        self,
        redis_url: str,
        key_prefix: str,
        requests_per_second: float = 20.0,
        window_size: float = 1.0,
        initial_retry_delay: float = 0.05,
        max_retry_delay: float = 0.2,
        backoff_multiplier: float = 1.5,
        metrics_cache_ttl: float = 1.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 30.0,
    ):
        """Initialize rate limiter.

        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for Redis key (e.g., "stock", "futures")
            requests_per_second: Maximum requests per second
            window_size: Sliding window size in seconds
            initial_retry_delay: Initial delay when retrying (seconds)
            max_retry_delay: Maximum retry delay cap (seconds)
            backoff_multiplier: Multiplier for exponential backoff
            metrics_cache_ttl: TTL for cached metrics (seconds)
            circuit_breaker_threshold: Failures before opening circuit
            circuit_breaker_timeout: Time before attempting recovery
        """
        self._redis_url = redis_url
        self._redis: Redis | None = None
        self._script_sha: str | None = None

        self.key = f"kis:ratelimit:{key_prefix}"
        self.max_requests = int(requests_per_second * window_size)
        self.window_size = window_size
        self._request_counter = 0

        # Retry configuration
        self._initial_retry_delay = initial_retry_delay
        self._max_retry_delay = max_retry_delay
        self._backoff_multiplier = backoff_multiplier

        # Metrics cache
        self._metrics_cache_ttl = metrics_cache_ttl
        self._metrics_cache: dict | None = None
        self._metrics_cache_time: float = 0.0

        # Circuit breaker for Redis failures
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            reset_timeout=circuit_breaker_timeout,
        )

        # In-memory fallback limiter
        self._fallback_limiter = InMemoryRateLimiter(
            max_requests=self.max_requests,
            window_size=self.window_size,
        )

        logger.info(
            f"RedisRateLimiter initialized: key={self.key}, "
            f"max={self.max_requests}/{self.window_size}s"
        )

    async def _get_redis(self) -> Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                from redis.asyncio import Redis

                self._redis = Redis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_timeout=5.0,  # Prevent hangs
                    socket_connect_timeout=5.0,
                )
                # Register Lua script for better performance
                self._script_sha = await self._redis.script_load(RATE_LIMIT_SCRIPT)
                logger.debug(f"Redis connected: {_sanitize_redis_url(self._redis_url)}")
            except ImportError:
                raise ImportError(
                    "redis package required for rate limiting. "
                    "Install with: pip install redis"
                )
        return self._redis

    async def acquire(self, timeout: float = 5.0) -> bool:
        """Acquire permission to make an API call.

        Blocks up to timeout seconds waiting for rate limit capacity.
        Uses Redis when available, falls back to in-memory limiter.

        Args:
            timeout: Maximum time to wait for capacity (seconds)

        Returns:
            True if allowed to proceed

        Raises:
            RateLimitExceeded: If timeout expires while rate limited
            CircuitBreakerOpen: If circuit breaker is open and fallback fails
        """
        start_time = time.monotonic()
        retry_delay = self._initial_retry_delay

        # Check circuit breaker
        if not self._circuit_breaker.is_available():
            # Use fallback limiter when circuit is open
            logger.debug("Circuit breaker open, using in-memory fallback")
            return await self._acquire_with_fallback(timeout)

        while True:
            try:
                allowed = await self._try_acquire()
                if allowed:
                    self._circuit_breaker.record_success()
                    return True

                # Check timeout
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    raise RateLimitExceeded(
                        key=self.key,
                        wait_time=self.window_size,
                    )

                # Exponential backoff, capped at max_retry_delay
                await asyncio.sleep(min(retry_delay, self._max_retry_delay))
                retry_delay *= self._backoff_multiplier

            except RateLimitExceeded:
                raise
            except (OSError, ConnectionError) as e:
                self._circuit_breaker.record_failure()
                logger.warning(
                    f"Redis connection error, using fallback: {e}"
                )
                return await self._acquire_with_fallback(timeout - (time.monotonic() - start_time))
            except Exception as e:
                error_type = type(e).__name__
                if error_type in ("ConnectionError", "TimeoutError", "RedisError"):
                    self._circuit_breaker.record_failure()
                    logger.warning(
                        f"Redis error, using fallback: {e}"
                    )
                    return await self._acquire_with_fallback(timeout - (time.monotonic() - start_time))
                # Re-raise unexpected errors
                logger.error(f"Unexpected error in rate limiter: {e}")
                raise

    async def _acquire_with_fallback(self, remaining_timeout: float) -> bool:
        """Acquire using in-memory fallback limiter.

        Args:
            remaining_timeout: Time remaining to acquire

        Returns:
            True if allowed

        Raises:
            RateLimitExceeded: If timeout expires
        """
        start_time = time.monotonic()
        retry_delay = self._initial_retry_delay

        while True:
            if self._fallback_limiter.acquire():
                return True

            elapsed = time.monotonic() - start_time
            if elapsed >= remaining_timeout:
                raise RateLimitExceeded(
                    key=f"{self.key}:fallback",
                    wait_time=self.window_size,
                )

            await asyncio.sleep(min(retry_delay, self._max_retry_delay))
            retry_delay *= self._backoff_multiplier

    async def _try_acquire(self) -> bool:
        """Attempt to acquire rate limit slot from Redis.

        Returns:
            True if slot acquired, False if rate limited
        """
        redis = await self._get_redis()

        now = time.time()
        self._request_counter += 1
        request_id = f"{now}-{self._request_counter}"

        # Execute Lua script atomically
        if self._script_sha:
            result = await redis.evalsha(
                self._script_sha,
                1,  # number of keys
                self.key,
                str(now),
                str(self.window_size),
                str(self.max_requests),
                request_id,
                str(EXPIRE_WINDOW_MULTIPLIER),
            )
        else:
            result = await redis.eval(
                RATE_LIMIT_SCRIPT,
                1,
                self.key,
                str(now),
                str(self.window_size),
                str(self.max_requests),
                request_id,
                str(EXPIRE_WINDOW_MULTIPLIER),
            )

        return result == 1

    async def get_current_usage(self) -> int:
        """Get current number of requests in window.

        Uses Redis pipelining for efficiency.

        Returns:
            Number of requests in current sliding window
        """
        try:
            redis = await self._get_redis()
            now = time.time()

            # Use pipeline for atomic operation with single round-trip
            pipe = redis.pipeline()
            pipe.zremrangebyscore(self.key, 0, now - self.window_size)
            pipe.zcard(self.key)
            results = await pipe.execute()

            return results[1]  # zcard result
        except Exception as e:
            logger.warning(f"Failed to get usage from Redis: {e}")
            # Return fallback usage
            return self._fallback_limiter.get_usage()

    async def get_metrics(self, use_cache: bool = True) -> dict:
        """Get rate limiter metrics for monitoring.

        Args:
            use_cache: Whether to use cached metrics if available

        Returns:
            Dict with current usage, limits, utilization, and circuit state
        """
        now = time.time()

        # Return cached metrics if still valid
        if (
            use_cache
            and self._metrics_cache is not None
            and (now - self._metrics_cache_time) < self._metrics_cache_ttl
        ):
            return self._metrics_cache

        current = await self.get_current_usage()
        utilization = (current / self.max_requests * 100) if self.max_requests > 0 else 0

        metrics = {
            "rate_limit_key": self.key,
            "current_usage": current,
            "max_requests": self.max_requests,
            "window_size": self.window_size,
            "utilization_pct": round(utilization, 1),
            "circuit_breaker_state": self._circuit_breaker.state,
            "using_fallback": self._circuit_breaker.state != CircuitBreaker.CLOSED,
        }

        # Update cache
        self._metrics_cache = metrics
        self._metrics_cache_time = now

        return metrics

    async def reset(self) -> None:
        """Reset rate limit counter (for testing)."""
        try:
            redis = await self._get_redis()
            await redis.delete(self.key)
            logger.debug(f"Rate limit reset: {self.key}")
        except Exception as e:
            logger.warning(f"Failed to reset rate limit: {e}")

        # Also reset fallback
        self._fallback_limiter._timestamps.clear()

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._script_sha = None
            logger.debug("Redis connection closed")
