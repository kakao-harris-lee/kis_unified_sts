"""Test Redis rate limiter."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time


class TestRedisRateLimiter:
    """Unit tests for RedisRateLimiter with mocked Redis."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.script_load = AsyncMock(return_value="mock_sha")
        redis.evalsha = AsyncMock(return_value=1)  # 1 = allowed
        redis.eval = AsyncMock(return_value=1)
        redis.zcard = AsyncMock(return_value=5)
        redis.zremrangebyscore = AsyncMock()
        redis.delete = AsyncMock()
        redis.close = AsyncMock()
        return redis

    @pytest.fixture
    def limiter(self, mock_redis):
        """Create rate limiter with mocked Redis."""
        with patch("redis.asyncio.Redis") as MockRedis:
            MockRedis.from_url = MagicMock(return_value=mock_redis)

            from shared.execution.rate_limiter import RedisRateLimiter
            limiter = RedisRateLimiter(
                redis_url="redis://localhost:6379",
                key_prefix="test",
                requests_per_second=20.0,
                window_size=1.0,
            )
            # Inject mock directly
            limiter._redis = mock_redis
            limiter._script_sha = "mock_sha"
            return limiter

    @pytest.mark.asyncio
    async def test_acquire_allowed(self, limiter, mock_redis):
        """Test acquire returns True when under limit."""
        mock_redis.evalsha.return_value = 1  # Allowed

        result = await limiter.acquire(timeout=1.0)

        assert result is True
        mock_redis.evalsha.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_blocked_then_allowed(self, limiter, mock_redis):
        """Test acquire waits and retries when rate limited."""
        # First call blocked, second allowed
        mock_redis.evalsha.side_effect = [0, 1]

        result = await limiter.acquire(timeout=1.0)

        assert result is True
        assert mock_redis.evalsha.call_count == 2

    @pytest.mark.asyncio
    async def test_acquire_timeout_raises(self, limiter, mock_redis):
        """Test acquire raises RateLimitExceeded on timeout."""
        from shared.execution.exceptions import RateLimitExceeded

        mock_redis.evalsha.return_value = 0  # Always blocked

        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.acquire(timeout=0.2)

        assert "test" in exc_info.value.key

    @pytest.mark.asyncio
    async def test_acquire_redis_connection_error_fails_open(self, limiter, mock_redis):
        """Test Redis connection errors allow requests (fail-open)."""
        mock_redis.evalsha.side_effect = ConnectionError("Connection lost")

        # Should return True (fail-open), not raise
        result = await limiter.acquire(timeout=1.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_get_current_usage(self, limiter, mock_redis):
        """Test get_current_usage returns count from Redis."""
        mock_redis.zcard.return_value = 15

        usage = await limiter.get_current_usage()

        assert usage == 15
        mock_redis.zremrangebyscore.assert_called_once()
        mock_redis.zcard.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics(self, limiter, mock_redis):
        """Test get_metrics returns formatted metrics."""
        mock_redis.zcard.return_value = 10

        metrics = await limiter.get_metrics()

        assert metrics["rate_limit_key"] == "kis:ratelimit:test"
        assert metrics["current_usage"] == 10
        assert metrics["max_requests"] == 20
        assert metrics["window_size"] == 1.0
        assert metrics["utilization_pct"] == 50.0

    @pytest.mark.asyncio
    async def test_reset(self, limiter, mock_redis):
        """Test reset clears the rate limit counter."""
        await limiter.reset()

        mock_redis.delete.assert_called_once_with("kis:ratelimit:test")

    @pytest.mark.asyncio
    async def test_close(self, limiter, mock_redis):
        """Test close cleans up Redis connection."""
        await limiter.close()

        mock_redis.close.assert_called_once()
        assert limiter._redis is None
        assert limiter._script_sha is None

    def test_key_format(self, limiter):
        """Test Redis key format."""
        assert limiter.key == "kis:ratelimit:test"

    def test_max_requests_calculation(self, limiter):
        """Test max_requests is calculated from requests_per_second."""
        # 20 req/sec * 1.0 sec window = 20 max requests
        assert limiter.max_requests == 20

    @pytest.mark.asyncio
    async def test_acquire_uses_eval_fallback_when_no_script_sha(self, mock_redis):
        """Test acquire falls back to eval() when script_sha is None."""
        with patch("redis.asyncio.Redis") as MockRedis:
            MockRedis.from_url = MagicMock(return_value=mock_redis)

            from shared.execution.rate_limiter import RedisRateLimiter
            limiter = RedisRateLimiter(
                redis_url="redis://localhost:6379",
                key_prefix="test-fallback",
                requests_per_second=20.0,
                window_size=1.0,
            )
            # Inject mock with NO script_sha (simulates script_load failure)
            limiter._redis = mock_redis
            limiter._script_sha = None  # Force fallback path

            mock_redis.eval.return_value = 1  # Allowed

            result = await limiter.acquire(timeout=1.0)

            assert result is True
            # Should use eval(), not evalsha()
            mock_redis.eval.assert_called_once()
            mock_redis.evalsha.assert_not_called()

    @pytest.mark.asyncio
    async def test_acquire_connection_error_fails_open(self, limiter, mock_redis):
        """Test ConnectionError specifically triggers fail-open."""
        mock_redis.evalsha.side_effect = ConnectionError("Connection refused")

        result = await limiter.acquire(timeout=1.0)

        assert result is True  # Should fail open

    @pytest.mark.asyncio
    async def test_acquire_unexpected_error_propagates(self, limiter, mock_redis):
        """Test unexpected errors are re-raised, not swallowed."""
        mock_redis.evalsha.side_effect = ValueError("Unexpected programming error")

        with pytest.raises(ValueError) as exc_info:
            await limiter.acquire(timeout=1.0)

        assert "Unexpected programming error" in str(exc_info.value)


class TestRedisUrlSanitization:
    """Test Redis URL sanitization for logging."""

    def test_sanitize_url_with_password(self):
        """Test password is removed from Redis URL."""
        from shared.execution.rate_limiter import _sanitize_redis_url

        url = "redis://user:secretpassword@localhost:6379/0"
        sanitized = _sanitize_redis_url(url)

        assert "secretpassword" not in sanitized
        assert "****" in sanitized
        assert "localhost:6379" in sanitized

    def test_sanitize_url_without_password(self):
        """Test URL without password is unchanged."""
        from shared.execution.rate_limiter import _sanitize_redis_url

        url = "redis://localhost:6379/0"
        sanitized = _sanitize_redis_url(url)

        assert sanitized == url


class TestMetricsCaching:
    """Test metrics caching functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.script_load = AsyncMock(return_value="mock_sha")
        redis.zcard = AsyncMock(return_value=5)
        redis.zremrangebyscore = AsyncMock()
        redis.close = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_metrics_cache_returns_cached_value(self, mock_redis):
        """Test that get_metrics returns cached value within TTL."""
        with patch("redis.asyncio.Redis") as MockRedis:
            MockRedis.from_url = MagicMock(return_value=mock_redis)

            from shared.execution.rate_limiter import RedisRateLimiter
            limiter = RedisRateLimiter(
                redis_url="redis://localhost:6379",
                key_prefix="test-cache",
                metrics_cache_ttl=10.0,  # Long TTL for test
            )
            limiter._redis = mock_redis
            mock_redis.zcard.return_value = 5

            # First call - hits Redis
            metrics1 = await limiter.get_metrics()
            assert metrics1["current_usage"] == 5
            assert mock_redis.zcard.call_count == 1

            # Change the mock return value
            mock_redis.zcard.return_value = 10

            # Second call - should return cached value
            metrics2 = await limiter.get_metrics()
            assert metrics2["current_usage"] == 5  # Still 5 from cache
            assert mock_redis.zcard.call_count == 1  # No additional call

    @pytest.mark.asyncio
    async def test_metrics_cache_bypass(self, mock_redis):
        """Test that use_cache=False bypasses cache."""
        with patch("redis.asyncio.Redis") as MockRedis:
            MockRedis.from_url = MagicMock(return_value=mock_redis)

            from shared.execution.rate_limiter import RedisRateLimiter
            limiter = RedisRateLimiter(
                redis_url="redis://localhost:6379",
                key_prefix="test-cache",
                metrics_cache_ttl=10.0,
            )
            limiter._redis = mock_redis
            mock_redis.zcard.return_value = 5

            # First call
            await limiter.get_metrics()
            mock_redis.zcard.return_value = 10

            # Second call with cache bypass
            metrics = await limiter.get_metrics(use_cache=False)
            assert metrics["current_usage"] == 10
            assert mock_redis.zcard.call_count == 2


class TestRedisFailureScenarios:
    """Test various Redis failure scenarios."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.script_load = AsyncMock(return_value="mock_sha")
        redis.evalsha = AsyncMock(return_value=1)
        redis.close = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_os_error_fails_open(self, mock_redis):
        """Test OSError triggers fail-open."""
        with patch("redis.asyncio.Redis") as MockRedis:
            MockRedis.from_url = MagicMock(return_value=mock_redis)

            from shared.execution.rate_limiter import RedisRateLimiter
            limiter = RedisRateLimiter(
                redis_url="redis://localhost:6379",
                key_prefix="test",
            )
            limiter._redis = mock_redis
            limiter._script_sha = "mock_sha"
            mock_redis.evalsha.side_effect = OSError("Network unreachable")

            result = await limiter.acquire(timeout=1.0)
            assert result is True  # Fail-open

    @pytest.mark.asyncio
    async def test_timeout_error_fails_open(self, mock_redis):
        """Test TimeoutError triggers fail-open."""
        with patch("redis.asyncio.Redis") as MockRedis:
            MockRedis.from_url = MagicMock(return_value=mock_redis)

            from shared.execution.rate_limiter import RedisRateLimiter
            limiter = RedisRateLimiter(
                redis_url="redis://localhost:6379",
                key_prefix="test",
            )
            limiter._redis = mock_redis
            limiter._script_sha = "mock_sha"

            # Create an exception with the right __name__
            class TimeoutError(Exception):
                pass

            mock_redis.evalsha.side_effect = TimeoutError("Connection timed out")

            result = await limiter.acquire(timeout=1.0)
            assert result is True  # Fail-open


class TestOrderExecutorWithRateLimiter:
    """Test OrderExecutor integration with rate limiter."""

    @pytest.mark.asyncio
    async def test_executor_acquires_before_order(self):
        """Test executor calls rate limiter before sending order."""
        from shared.execution.executor import OrderExecutor
        from shared.execution.config import ExecutionConfig
        from shared.execution.models import OrderRequest, OrderSide, OrderType

        with patch("shared.execution.rate_limiter.RedisRateLimiter") as MockLimiter:
            mock_limiter = AsyncMock()
            mock_limiter.acquire = AsyncMock(return_value=True)
            mock_limiter.close = AsyncMock()
            MockLimiter.return_value = mock_limiter

            config = ExecutionConfig(
                trading_mode="PAPER",
                redis_url="redis://localhost:6379",
                rate_limit_key="test",
            )
            executor = OrderExecutor(config)

            order = OrderRequest(
                code="005930",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=10,
            )

            response = await executor.execute_order(order)

            mock_limiter.acquire.assert_called_once()
            assert response.success is True

            await executor.cleanup()

    @pytest.mark.asyncio
    async def test_executor_rate_limit_error_returns_failure(self):
        """Test executor returns failure when rate limited."""
        from shared.execution.executor import OrderExecutor
        from shared.execution.config import ExecutionConfig
        from shared.execution.models import OrderRequest, OrderSide, OrderType
        from shared.execution.exceptions import RateLimitExceeded

        with patch("shared.execution.rate_limiter.RedisRateLimiter") as MockLimiter:
            mock_limiter = AsyncMock()
            mock_limiter.acquire = AsyncMock(
                side_effect=RateLimitExceeded(key="test", wait_time=1.0)
            )
            mock_limiter.close = AsyncMock()
            MockLimiter.return_value = mock_limiter

            config = ExecutionConfig(
                trading_mode="PAPER",
                redis_url="redis://localhost:6379",
                rate_limit_key="test",
            )
            executor = OrderExecutor(config)

            order = OrderRequest(
                code="005930",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=10,
            )

            response = await executor.execute_order(order)

            assert response.success is False
            assert "Rate limit exceeded" in response.message

            await executor.cleanup()

    @pytest.mark.asyncio
    async def test_executor_works_without_redis_configured(self):
        """Test executor works normally when redis_url is empty."""
        from shared.execution.executor import OrderExecutor
        from shared.execution.config import ExecutionConfig
        from shared.execution.models import OrderRequest, OrderSide, OrderType

        config = ExecutionConfig(
            trading_mode="PAPER",
            redis_url="",  # No Redis configured
        )
        executor = OrderExecutor(config)

        assert executor._rate_limiter is None

        order = OrderRequest(
            code="005930",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )

        response = await executor.execute_order(order)

        assert response.success is True
        await executor.cleanup()
