"""Test trades endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_trades_list():
    """Test trades list endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades")

    assert response.status_code == 200
    data = response.json()
    assert "trades" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_trades_statistics():
    """Test trades statistics endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades/statistics")

    assert response.status_code == 200
    data = response.json()
    assert "total_trades" in data
    assert "win_rate" in data
    assert "total_pnl" in data


@pytest.mark.asyncio
async def test_trades_by_strategy():
    """Test trades by strategy endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades/by-strategy")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
