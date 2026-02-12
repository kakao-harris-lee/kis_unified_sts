"""Test trading status endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_trading_status():
    """Test trading status endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trading/status")

    assert response.status_code == 200
    data = response.json()
    assert "is_running" in data
    assert "market_status" in data


@pytest.mark.asyncio
async def test_positions_list():
    """Test positions list endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trading/positions")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_start_trading():
    """Test start trading endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/trading/start")

    assert response.status_code == 200
    assert response.json()["status"] == "use CLI: sts trade start"


@pytest.mark.asyncio
async def test_stop_trading():
    """Test stop trading endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/trading/stop")

    assert response.status_code == 200
    assert response.json()["status"] == "use CLI: sts trade stop"
