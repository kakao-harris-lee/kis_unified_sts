"""Integration tests for rate limiter with real Redis.

These tests require a running Redis instance.
Run with: pytest tests/integration/test_rate_limiter_redis.py -v

To skip these tests when Redis is unavailable:
    pytest -m "not integration"
"""
import asyncio
import pytest
import os


# Skip all tests in this module if Redis is not available
pytestmark = [pytest.mark.integration]


def redis_available():
    """Check if Redis is available."""
    try:
        import redis
        r = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            socket_timeout=1,
        )
        r.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def redis_url():
    """Get Redis URL from environment or use default."""
    return os.getenv("REDIS_URL", "redis://localhost:6379")


@pytest.fixture
async def limiter(redis_url):
    """Create a real rate limiter and clean up after test."""
    from shared.execution.rate_limiter import RedisRateLimiter

    limiter = RedisRateLimiter(
        redis_url=redis_url,
        key_prefix="test-integration",
        requests_per_second=10.0,  # Lower limit for testing
        window_size=1.0,
    )
    # Clear any existing data
    await limiter.reset()
    yield limiter
    # Clean up
    await limiter.reset()
    await limiter.close()


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_rate_limiter_allows_under_limit(limiter):
    """Test rate limiter allows requests under the limit."""
    # Make 5 requests (under limit of 10)
    results = []
    for _ in range(5):
        result = await limiter.acquire(timeout=1.0)
        results.append(result)

    assert all(results)
    assert len(results) == 5


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit(limiter):
    """Test rate limiter blocks when over limit."""
    from shared.execution.exceptions import RateLimitExceeded

    # Make 10 requests quickly (at limit)
    for _ in range(10):
        await limiter.acquire(timeout=1.0)

    # 11th request should be blocked
    with pytest.raises(RateLimitExceeded):
        await limiter.acquire(timeout=0.2)  # Short timeout


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_sliding_window_expires(limiter):
    """Test that old requests expire from the sliding window."""
    # Make requests up to the limit
    for _ in range(10):
        await limiter.acquire(timeout=1.0)

    # Wait for window to expire
    await asyncio.sleep(1.1)

    # Should be allowed now
    result = await limiter.acquire(timeout=1.0)
    assert result is True


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_metrics_accuracy(limiter):
    """Test metrics reflect actual usage."""
    # Start fresh
    await limiter.reset()

    # Make 7 requests
    for _ in range(7):
        await limiter.acquire(timeout=1.0)

    metrics = await limiter.get_metrics()

    assert metrics["current_usage"] == 7
    assert metrics["max_requests"] == 10
    assert metrics["utilization_pct"] == 70.0


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_separate_keys_isolated(redis_url):
    """Test that different keys are isolated from each other."""
    from shared.execution.rate_limiter import RedisRateLimiter

    # Create two limiters with different keys
    limiter_stock = RedisRateLimiter(
        redis_url=redis_url,
        key_prefix="test-stock",
        requests_per_second=5.0,
        window_size=1.0,
    )
    limiter_futures = RedisRateLimiter(
        redis_url=redis_url,
        key_prefix="test-futures",
        requests_per_second=5.0,
        window_size=1.0,
    )

    try:
        # Reset both
        await limiter_stock.reset()
        await limiter_futures.reset()

        # Exhaust stock limit
        for _ in range(5):
            await limiter_stock.acquire(timeout=1.0)

        # Stock should be blocked
        from shared.execution.exceptions import RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            await limiter_stock.acquire(timeout=0.1)

        # Futures should still be available
        result = await limiter_futures.acquire(timeout=1.0)
        assert result is True

        # Verify metrics show different states
        stock_metrics = await limiter_stock.get_metrics()
        futures_metrics = await limiter_futures.get_metrics()

        assert stock_metrics["current_usage"] == 5
        assert futures_metrics["current_usage"] == 1

    finally:
        await limiter_stock.reset()
        await limiter_futures.reset()
        await limiter_stock.close()
        await limiter_futures.close()


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_concurrent_requests(limiter):
    """Test rate limiter handles concurrent requests correctly."""
    # Launch 20 concurrent requests (limit is 10)
    async def make_request():
        try:
            return await limiter.acquire(timeout=0.5)
        except Exception:
            return False

    tasks = [make_request() for _ in range(20)]
    results = await asyncio.gather(*tasks)

    # Should allow exactly 10 (the limit)
    allowed = sum(1 for r in results if r is True)
    assert allowed == 10


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_two_processes_share_rate_limit(redis_url):
    """Simulate stock + futures processes hitting their separate limits.

    This test verifies that:
    1. Each key has its own independent limit
    2. Exhausting one doesn't affect the other
    3. Both can operate at full capacity independently
    """
    from shared.execution.rate_limiter import RedisRateLimiter

    async def simulate_orchestrator(key_prefix: str, num_requests: int):
        """Simulate an orchestrator making requests."""
        limiter = RedisRateLimiter(
            redis_url=redis_url,
            key_prefix=f"test-{key_prefix}",
            requests_per_second=10.0,
            window_size=1.0,
        )
        await limiter.reset()

        successful = 0
        for _ in range(num_requests):
            try:
                if await limiter.acquire(timeout=0.1):
                    successful += 1
            except Exception:
                pass

        await limiter.close()
        return successful

    # Run both "orchestrators" concurrently
    # Each tries to make 15 requests (over their 10 limit)
    results = await asyncio.gather(
        simulate_orchestrator("stock-sim", 15),
        simulate_orchestrator("futures-sim", 15),
    )

    stock_successful, futures_successful = results

    # Each should get exactly their limit (10)
    assert stock_successful == 10
    assert futures_successful == 10
