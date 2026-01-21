"""Test dashboard FastAPI app."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_app_creation():
    """Test FastAPI app is created."""
    from services.dashboard.app import create_app

    app = create_app()
    assert app is not None
    assert app.title == "KIS Unified Trading Dashboard"


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
