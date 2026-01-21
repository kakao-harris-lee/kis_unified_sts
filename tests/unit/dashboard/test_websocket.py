"""Test WebSocket endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_websocket_manager_creation():
    """Test WebSocket manager can be created."""
    from services.dashboard.websocket import WebSocketManager

    manager = WebSocketManager()
    assert manager is not None
    assert manager.active_connections == []


@pytest.mark.asyncio
async def test_websocket_endpoint_exists():
    """Test WebSocket endpoint is registered."""
    from services.dashboard.app import create_app

    app = create_app()

    # Check that /ws route exists
    routes = [route.path for route in app.routes]
    assert "/ws" in routes or any("/ws" in str(r) for r in routes)
