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

        # Setup pipeline mock for get_current_usage
        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zcard = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[0, 5])  # [zremrangebyscore result, zcard result]
        redis.pipeline = MagicMock(return_value=mock_pipe)

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
        # Update pipeline mock to return desired value
        mock_pipe = mock_redis.pipeline.return_value
        mock_pipe.execute.return_value = [0, 15]  # [zremrangebyscore, zcard]

        usage = await limiter.get_current_usage()

        assert usage == 15
        mock_redis.pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics(self, limiter, mock_redis):
        """Test get_metrics returns formatted metrics."""
        # Update pipeline mock for get_current_usage call within get_metrics
        mock_pipe = mock_redis.pipeline.return_value
        mock_pipe.execute.return_value = [0, 10]  # [zremrangebyscore, zcard]

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

        mock_redis.aclose.assert_called_once()
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

        # Setup pipeline mock for get_current_usage
        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zcard = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[0, 5])
        redis.pipeline = MagicMock(return_value=mock_pipe)

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
            mock_pipe = mock_redis.pipeline.return_value
            mock_pipe.execute.return_value = [0, 5]

            # First call - hits Redis
            metrics1 = await limiter.get_metrics()
            assert metrics1["current_usage"] == 5
            assert mock_redis.pipeline.call_count == 1

            # Change the mock return value
            mock_pipe.execute.return_value = [0, 10]

            # Second call - should return cached value
            metrics2 = await limiter.get_metrics()
            assert metrics2["current_usage"] == 5  # Still 5 from cache
            assert mock_redis.pipeline.call_count == 1  # No additional call

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
            mock_pipe = mock_redis.pipeline.return_value
            mock_pipe.execute.return_value = [0, 5]

            # First call
            await limiter.get_metrics()
            mock_pipe.execute.return_value = [0, 10]

            # Second call with cache bypass
            metrics = await limiter.get_metrics(use_cache=False)
            assert metrics["current_usage"] == 10
            assert mock_redis.pipeline.call_count == 2


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


class TestInMemoryRateLimiter:
    """Test in-memory fallback rate limiter."""

    def test_acquire_under_limit(self):
        """Test acquire succeeds when under limit."""
        from shared.execution.rate_limiter import InMemoryRateLimiter

        limiter = InMemoryRateLimiter(max_requests=5, window_size=1.0)

        # Should succeed for all 5 requests
        for _ in range(5):
            assert limiter.acquire() is True

    def test_acquire_at_limit(self):
        """Test acquire fails when at limit."""
        from shared.execution.rate_limiter import InMemoryRateLimiter

        limiter = InMemoryRateLimiter(max_requests=3, window_size=1.0)

        # First 3 succeed
        for _ in range(3):
            assert limiter.acquire() is True

        # 4th fails
        assert limiter.acquire() is False

    def test_acquire_after_window_expires(self):
        """Test acquire succeeds after window expires."""
        from shared.execution.rate_limiter import InMemoryRateLimiter

        limiter = InMemoryRateLimiter(max_requests=2, window_size=0.1)

        # Fill the limit
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        assert limiter.acquire() is False

        # Wait for window to expire
        time.sleep(0.15)

        # Should succeed again
        assert limiter.acquire() is True

    def test_get_usage(self):
        """Test get_usage returns correct count."""
        from shared.execution.rate_limiter import InMemoryRateLimiter

        limiter = InMemoryRateLimiter(max_requests=10, window_size=1.0)

        assert limiter.get_usage() == 0

        limiter.acquire()
        limiter.acquire()
        limiter.acquire()

        assert limiter.get_usage() == 3


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_initial_state_closed(self):
        """Test circuit breaker starts in closed state."""
        from shared.resilience import CircuitBreaker, CircuitState

        cb = CircuitBreaker(name="test", failure_threshold=3, reset_timeout=1.0)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available() is True

    def test_opens_after_threshold_failures(self):
        """Test circuit breaker opens after threshold failures."""
        from shared.resilience import CircuitBreaker, CircuitState

        cb = CircuitBreaker(name="test", failure_threshold=3, reset_timeout=1.0)

        # Record failures
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()  # Threshold reached
        assert cb.state == CircuitState.OPEN
        assert cb.is_available() is False

    def test_success_resets_failure_count(self):
        """Test success resets failure count in closed state."""
        from shared.resilience import CircuitBreaker, CircuitState

        cb = CircuitBreaker(name="test", failure_threshold=3, reset_timeout=1.0)

        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # Reset count

        # Should need 3 more failures to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_transitions_to_half_open(self):
        """Test circuit transitions to half-open after reset timeout."""
        from shared.resilience import CircuitBreaker, CircuitState

        cb = CircuitBreaker(name="test", failure_threshold=2, reset_timeout=0.1)

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for reset timeout
        time.sleep(0.15)

        # Should transition to half-open
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.is_available() is True

    def test_half_open_closes_on_success(self):
        """Test circuit closes after 2 successes in half-open state."""
        from shared.resilience import CircuitBreaker, CircuitState

        cb = CircuitBreaker(name="test", failure_threshold=2, reset_timeout=0.1)

        # Open and wait for half-open
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # First success
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN

        # Second success closes circuit
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_reopens_on_failure(self):
        """Test circuit reopens on failure in half-open state."""
        from shared.resilience import CircuitBreaker, CircuitState

        cb = CircuitBreaker(name="test", failure_threshold=2, reset_timeout=0.1)

        # Open and wait for half-open
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Failure reopens circuit
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_get_reset_time(self):
        """Test get_reset_time returns correct remaining time."""
        from shared.resilience import CircuitBreaker

        cb = CircuitBreaker(name="test", failure_threshold=2, reset_timeout=1.0)

        # Closed state returns 0
        assert cb.get_reset_time() == 0.0

        # Open state returns remaining time
        cb.record_failure()
        cb.record_failure()
        reset_time = cb.get_reset_time()
        assert 0.9 < reset_time <= 1.0


class TestExecutorWarmup:
    """Test executor connection warmup."""

    @pytest.mark.asyncio
    async def test_warmup_paper_mode_skips(self):
        """Test warmup is skipped in PAPER mode."""
        from shared.execution.executor import OrderExecutor
        from shared.execution.config import ExecutionConfig

        config = ExecutionConfig(trading_mode="PAPER")
        executor = OrderExecutor(config)

        result = await executor.warmup()
        assert result is True

        await executor.cleanup()

    @pytest.mark.asyncio
    async def test_warmup_mock_mode_makes_request(self):
        """Test warmup makes HEAD request in MOCK mode."""
        from shared.execution.executor import OrderExecutor
        from shared.execution.config import ExecutionConfig

        config = ExecutionConfig(trading_mode="MOCK")
        executor = OrderExecutor(config)
        await executor.initialize()

        with patch.object(executor.session, "head") as mock_head:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_head.return_value.__aenter__.return_value = mock_response

            result = await executor.warmup()

            assert result is True
            mock_head.assert_called_once()
            # Verify it used the mock URL
            call_args = mock_head.call_args
            assert "openapivts.koreainvestment.com" in call_args[0][0]

        await executor.cleanup()

    @pytest.mark.asyncio
    async def test_warmup_handles_connection_error(self):
        """Test warmup returns False on connection error."""
        from shared.execution.executor import OrderExecutor
        from shared.execution.config import ExecutionConfig

        config = ExecutionConfig(trading_mode="MOCK")
        executor = OrderExecutor(config)
        await executor.initialize()

        with patch.object(executor.session, "head") as mock_head:
            mock_head.side_effect = ConnectionError("Connection refused")

            result = await executor.warmup()

            assert result is False

        await executor.cleanup()
