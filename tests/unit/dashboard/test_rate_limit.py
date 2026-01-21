"""Test rate limiting middleware."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_rate_limiter_allows_requests_under_limit():
    """Test rate limiter allows requests under the limit."""
    from services.dashboard.app import create_app

    app = create_app(rate_limit=10, rate_limit_window=60)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Make 5 requests (under limit of 10)
        for _ in range(5):
            response = await client.get("/api/trading/status")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limiter_blocks_requests_over_limit():
    """Test rate limiter blocks requests over the limit."""
    from services.dashboard.app import create_app

    app = create_app(rate_limit=3, rate_limit_window=60)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Make requests until we hit the limit
        for i in range(5):
            response = await client.get("/api/trading/status")
            if i < 3:
                assert response.status_code == 200
            else:
                assert response.status_code == 429
                assert "rate limit" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rate_limiter_includes_headers():
    """Test rate limiter includes rate limit headers."""
    from services.dashboard.app import create_app

    app = create_app(rate_limit=10, rate_limit_window=60)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trading/status")

    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers


@pytest.mark.asyncio
async def test_rate_limiter_disabled_by_default():
    """Test rate limiter is disabled when rate_limit=0."""
    from services.dashboard.app import create_app

    app = create_app(rate_limit=0)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Should be able to make many requests without hitting a limit
        for _ in range(20):
            response = await client.get("/api/trading/status")
            assert response.status_code == 200
