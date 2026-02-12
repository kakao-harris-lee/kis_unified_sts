"""Test WebSocket manager."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def websocket_manager():
    """Create a fresh WebSocket manager for testing."""
    from services.dashboard.websocket import WebSocketManager
    return WebSocketManager()


def create_mock_websocket(client_host: str = "127.0.0.1") -> MagicMock:
    """Create a mock WebSocket."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_json = AsyncMock()
    ws.client = MagicMock()
    ws.client.host = client_host
    return ws


@pytest.mark.asyncio
async def test_websocket_connect(websocket_manager):
    """Test WebSocket connection."""
    ws = create_mock_websocket()

    result = await websocket_manager.connect(ws, "client1")

    assert result is True
    ws.accept.assert_called_once()
    assert ws in websocket_manager.active_connections
    assert websocket_manager.get_connection_count() == 1


@pytest.mark.asyncio
async def test_websocket_disconnect(websocket_manager):
    """Test WebSocket disconnection."""
    ws = create_mock_websocket()

    await websocket_manager.connect(ws, "client1")
    websocket_manager.disconnect(ws)

    assert ws not in websocket_manager.active_connections
    assert websocket_manager.get_connection_count() == 0


@pytest.mark.asyncio
async def test_websocket_subscribe_channel(websocket_manager):
    """Test channel subscription."""
    ws = create_mock_websocket()

    await websocket_manager.connect(ws, "client1")
    websocket_manager.subscribe(ws, "positions")
    websocket_manager.subscribe(ws, "signals")

    subscriptions = websocket_manager.get_subscriptions(ws)
    assert "positions" in subscriptions
    assert "signals" in subscriptions


@pytest.mark.asyncio
async def test_websocket_unsubscribe_channel(websocket_manager):
    """Test channel unsubscription."""
    ws = create_mock_websocket()

    await websocket_manager.connect(ws, "client1")
    websocket_manager.subscribe(ws, "positions")
    websocket_manager.unsubscribe(ws, "positions")

    subscriptions = websocket_manager.get_subscriptions(ws)
    assert "positions" not in subscriptions


@pytest.mark.asyncio
async def test_websocket_broadcast_to_channel(websocket_manager):
    """Test broadcast to channel."""
    ws1 = create_mock_websocket("127.0.0.1")
    ws2 = create_mock_websocket("127.0.0.2")
    ws3 = create_mock_websocket("127.0.0.3")

    await websocket_manager.connect(ws1, "client1")
    await websocket_manager.connect(ws2, "client2")
    await websocket_manager.connect(ws3, "client3")

    websocket_manager.subscribe(ws1, "signals")
    websocket_manager.subscribe(ws2, "signals")
    # ws3 not subscribed to signals

    message = {"type": "signal", "data": {}}
    await websocket_manager.broadcast_to_channel("signals", message)

    ws1.send_json.assert_called_once_with(message)
    ws2.send_json.assert_called_once_with(message)
    ws3.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_websocket_broadcast_all(websocket_manager):
    """Test broadcast to all connections."""
    ws1 = create_mock_websocket("127.0.0.1")
    ws2 = create_mock_websocket("127.0.0.2")

    await websocket_manager.connect(ws1, "client1")
    await websocket_manager.connect(ws2, "client2")

    message = {"type": "system", "data": "broadcast"}
    await websocket_manager.broadcast(message)

    ws1.send_json.assert_called_once_with(message)
    ws2.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_websocket_per_client_limit(websocket_manager):
    """Test per-client connection limit."""
    from services.dashboard.websocket import WebSocketManager

    # Create more connections than allowed for a single client
    websockets = []
    for i in range(WebSocketManager.MAX_CONNECTIONS_PER_CLIENT + 1):
        ws = create_mock_websocket()
        websockets.append(ws)

    # First MAX_CONNECTIONS_PER_CLIENT should succeed
    for i in range(WebSocketManager.MAX_CONNECTIONS_PER_CLIENT):
        result = await websocket_manager.connect(websockets[i], "client1")
        assert result is True

    # Next one should fail
    result = await websocket_manager.connect(
        websockets[WebSocketManager.MAX_CONNECTIONS_PER_CLIENT], "client1"
    )
    assert result is False
    websockets[WebSocketManager.MAX_CONNECTIONS_PER_CLIENT].close.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_total_connection_limit(websocket_manager):
    """Test total connection limit."""
    from services.dashboard.websocket import WebSocketManager

    # Set a lower limit for testing
    original_limit = WebSocketManager.MAX_TOTAL_CONNECTIONS
    WebSocketManager.MAX_TOTAL_CONNECTIONS = 3

    try:
        ws1 = create_mock_websocket("127.0.0.1")
        ws2 = create_mock_websocket("127.0.0.2")
        ws3 = create_mock_websocket("127.0.0.3")
        ws4 = create_mock_websocket("127.0.0.4")

        assert await websocket_manager.connect(ws1, "client1") is True
        assert await websocket_manager.connect(ws2, "client2") is True
        assert await websocket_manager.connect(ws3, "client3") is True

        # Fourth connection should fail due to total limit
        result = await websocket_manager.connect(ws4, "client4")
        assert result is False
        ws4.close.assert_called_once()

    finally:
        WebSocketManager.MAX_TOTAL_CONNECTIONS = original_limit


@pytest.mark.asyncio
async def test_websocket_disconnect_frees_slot(websocket_manager):
    """Test that disconnecting frees up connection slot."""
    from services.dashboard.websocket import WebSocketManager

    # Set a low limit for testing
    original_limit = WebSocketManager.MAX_CONNECTIONS_PER_CLIENT
    WebSocketManager.MAX_CONNECTIONS_PER_CLIENT = 2

    try:
        ws1 = create_mock_websocket()
        ws2 = create_mock_websocket()
        ws3 = create_mock_websocket()

        await websocket_manager.connect(ws1, "client1")
        await websocket_manager.connect(ws2, "client1")

        # Third should fail
        result = await websocket_manager.connect(ws3, "client1")
        assert result is False

        # Disconnect one
        websocket_manager.disconnect(ws1)

        # Now third should succeed
        ws3_new = create_mock_websocket()
        result = await websocket_manager.connect(ws3_new, "client1")
        assert result is True

    finally:
        WebSocketManager.MAX_CONNECTIONS_PER_CLIENT = original_limit


@pytest.mark.asyncio
async def test_websocket_send_personal(websocket_manager):
    """Test sending message to specific connection."""
    ws = create_mock_websocket()
    await websocket_manager.connect(ws, "client1")

    message = {"type": "personal", "data": "test"}
    await websocket_manager.send_personal(ws, message)

    ws.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_websocket_handles_send_error(websocket_manager):
    """Test that send errors disconnect the client."""
    ws = create_mock_websocket()
    ws.send_json = AsyncMock(side_effect=Exception("Connection closed"))

    await websocket_manager.connect(ws, "client1")
    assert websocket_manager.get_connection_count() == 1

    await websocket_manager.send_personal(ws, {"type": "test"})

    # Client should be disconnected after error
    assert websocket_manager.get_connection_count() == 0
