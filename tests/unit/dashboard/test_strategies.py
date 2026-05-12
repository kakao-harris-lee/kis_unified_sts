"""Tests for the strategies list endpoint.

Phase 5 of the dashboard redesign removed the strategy CRUD UI; only the
read-only list endpoint remains. Tests for the deleted endpoints
(``GET /{asset}/{name}``, ``POST``, ``POST /validate``, ``GET /schema``)
were removed alongside the route handlers.
"""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_strategy_list():
    """Test strategy list endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/strategies")

    assert response.status_code == 200
    data = response.json()
    assert "strategies" in data
    assert "total" in data
    assert isinstance(data["strategies"], list)
    assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_strategy_list_filter():
    """Test strategy list with asset class filter."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/strategies?asset_class=stock")

    assert response.status_code == 200
    data = response.json()
    assert data["asset_class"] == "stock"
    # All strategies should be stock type
    for strategy in data["strategies"]:
        assert strategy["asset_class"] == "stock"


@pytest.mark.asyncio
async def test_strategy_list_invalid_asset_class():
    """Test strategy list rejects unsupported asset class."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/strategies?asset_class=invalid")

    assert response.status_code == 400
