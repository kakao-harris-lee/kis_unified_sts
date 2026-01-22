"""Distributed rate limiter using Redis.

Provides cross-process rate limiting for KIS API calls using
Redis sorted sets with sliding window algorithm.

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
from typing import TYPE_CHECKING

from .exceptions import RateLimitExceeded


def _sanitize_redis_url(url: str) -> str:
    """Remove password from Redis URL for safe logging."""
    # Pattern: redis://[:password@]host:port/db
    return re.sub(r"(redis://[^:]*:)[^@]+(@)", r"\1****\2", url)

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

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


class RedisRateLimiter:
    """Distributed rate limiter using Redis sliding window.

    Uses Redis sorted sets for precise sliding window rate limiting.
    More accurate than token bucket for bursty traffic patterns.

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

        Args:
            timeout: Maximum time to wait for capacity (seconds)

        Returns:
            True if allowed to proceed

        Raises:
            RateLimitExceeded: If timeout expires while rate limited
        """
        start_time = time.monotonic()
        retry_delay = self._initial_retry_delay

        while True:
            try:
                allowed = await self._try_acquire()
                if allowed:
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
                # Network/connection errors - fail open to avoid blocking trading
                logger.warning(
                    f"Redis connection error in rate limiter, bypassing: {e}"
                )
                return True
            except Exception as e:
                # Check for redis-specific errors (imported dynamically)
                error_type = type(e).__name__
                if error_type in ("ConnectionError", "TimeoutError", "RedisError"):
                    logger.warning(
                        f"Redis error in rate limiter, bypassing: {e}"
                    )
                    return True
                # Re-raise unexpected errors (programming bugs, etc.)
                logger.error(f"Unexpected error in rate limiter: {e}")
                raise

    async def _try_acquire(self) -> bool:
        """Attempt to acquire rate limit slot.

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

        Returns:
            Number of requests in current sliding window
        """
        try:
            redis = await self._get_redis()
            now = time.time()

            # Remove old entries and count
            await redis.zremrangebyscore(
                self.key, 0, now - self.window_size
            )
            count = await redis.zcard(self.key)
            return count
        except Exception as e:
            logger.warning(f"Failed to get usage: {e}")
            return 0

    async def get_metrics(self, use_cache: bool = True) -> dict:
        """Get rate limiter metrics for monitoring.

        Args:
            use_cache: Whether to use cached metrics if available

        Returns:
            Dict with current usage, limits, and utilization
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

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._script_sha = None
            logger.debug("Redis connection closed")
