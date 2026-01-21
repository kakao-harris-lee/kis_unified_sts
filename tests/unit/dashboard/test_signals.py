"""Test signals endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_signals_list():
    """Test signals list endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/signals")

    assert response.status_code == 200
    data = response.json()
    assert "signals" in data
    assert "total" in data
    assert isinstance(data["signals"], list)


@pytest.mark.asyncio
async def test_signals_list_with_filter():
    """Test signals list with filters."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/signals?strategy=v35_optimized&limit=10")

    assert response.status_code == 200
    data = response.json()
    assert "signals" in data


@pytest.mark.asyncio
async def test_signal_history():
    """Test signal history endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/signals/history?days=7")

    assert response.status_code == 200
    data = response.json()
    assert "history" in data
    assert "total_signals" in data
