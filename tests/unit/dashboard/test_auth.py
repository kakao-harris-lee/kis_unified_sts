"""Test authentication middleware."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_api_key_auth_rejects_missing_key():
    """Test API key auth rejects requests without key."""
    from services.dashboard.app import create_app

    app = create_app(require_auth=True, api_key="test-secret-key")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trading/status")

    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_api_key_auth_accepts_valid_key():
    """Test API key auth accepts requests with valid key."""
    from services.dashboard.app import create_app

    app = create_app(require_auth=True, api_key="test-secret-key")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/trading/status",
            headers={"X-API-Key": "test-secret-key"},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_key_auth_rejects_invalid_key():
    """Test API key auth rejects requests with invalid key."""
    from services.dashboard.app import create_app

    app = create_app(require_auth=True, api_key="test-secret-key")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/trading/status",
            headers={"X-API-Key": "wrong-key"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_endpoint_bypasses_auth():
    """Test health endpoint doesn't require auth."""
    from services.dashboard.app import create_app

    app = create_app(require_auth=True, api_key="test-secret-key")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_disabled_by_default():
    """Test auth is disabled when require_auth=False."""
    from services.dashboard.app import create_app

    app = create_app(require_auth=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trading/status")

    assert response.status_code == 200
