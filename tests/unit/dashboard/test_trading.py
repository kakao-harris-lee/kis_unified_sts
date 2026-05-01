"""Test trading status endpoints."""

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient


def test_parse_tz_aware_round_trip_through_naive():
    """Same contract as trades.py: tz-aware UTC out, regardless of input."""
    from services.dashboard.routes.trading import _parse_tz_aware

    naive = _parse_tz_aware("2026-05-01T09:00:00")
    assert naive.tzinfo is not None and naive.utcoffset() == timedelta(0)

    aware = _parse_tz_aware("2026-05-01T18:00:00+09:00")
    assert aware.tzinfo is not None and aware.hour == 9

    fallback = _parse_tz_aware(None)
    assert fallback.tzinfo is not None and fallback.utcoffset() == timedelta(0)


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
