"""Test signals endpoints."""

from unittest.mock import MagicMock, patch

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
async def test_signals_respect_asset_class_and_emit_strength():
    """Cockpit compact list needs asset tags and a strength field."""
    from services.dashboard.app import create_app
    from services.dashboard.routes import signals as signals_route

    readers = {
        "futures": MagicMock(
            get_signals=MagicMock(
                return_value=[
                    {
                        "id": "fut-1",
                        "symbol": "A05000",
                        "side": "BUY",
                        "signal_type": "entry",
                        "strategy": "setup_a",
                        "price": 390.0,
                        "confidence": 0.72,
                        "timestamp": "2026-05-21T09:01:00+00:00",
                        "executed": False,
                    }
                ]
            )
        ),
        "stock": MagicMock(
            get_signals=MagicMock(
                return_value=[
                    {
                        "id": "stk-1",
                        "symbol": "086790",
                        "side": "SELL",
                        "signal_type": "exit",
                        "strategy": "pattern_pullback",
                        "price": 119200.0,
                        "confidence": 0.61,
                        "timestamp": "2026-05-21T09:02:00+00:00",
                        "executed": True,
                    }
                ]
            )
        ),
    }

    with patch.object(
        signals_route, "_get_reader", side_effect=lambda asset: readers[asset]
    ):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/signals?asset_class=all&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert [s["asset_class"] for s in body["signals"]] == ["stock", "futures"]
    assert body["signals"][0]["strength"] == pytest.approx(0.61)
    assert body["signals"][1]["confidence"] == pytest.approx(0.72)


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
