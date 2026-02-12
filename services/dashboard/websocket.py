"""WebSocket manager for real-time updates."""
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manage WebSocket connections for real-time updates.

    Includes connection limits to prevent resource exhaustion.
    """

    # Connection limits
    MAX_CONNECTIONS_PER_CLIENT = 5
    MAX_TOTAL_CONNECTIONS = 100

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._subscriptions: Dict[str, List[WebSocket]] = {}
        self._client_connections: Dict[str, int] = defaultdict(int)
        self._websocket_clients: Dict[WebSocket, str] = {}

    async def connect(
        self, websocket: WebSocket, client_id: Optional[str] = None
    ) -> bool:
        """Accept and track a new WebSocket connection.

        Returns:
            True if connection was accepted, False if rejected due to limits.
        """
        client_id = client_id or self._get_client_id(websocket)

        # Check per-client limit
        if self._client_connections[client_id] >= self.MAX_CONNECTIONS_PER_CLIENT:
            logger.warning(f"Client {client_id} exceeded connection limit")
            await websocket.close(code=4002, reason="Too many connections")
            return False

        # Check total limit
        total_connections = len(self.active_connections)
        if total_connections >= self.MAX_TOTAL_CONNECTIONS:
            logger.warning(f"Server at max capacity: {total_connections}")
            await websocket.close(code=4003, reason="Server at capacity")
            return False

        await websocket.accept()
        self.active_connections.append(websocket)
        self._client_connections[client_id] += 1
        self._websocket_clients[websocket] = client_id
        logger.info(
            f"WebSocket connected. Client: {client_id}, "
            f"Total connections: {len(self.active_connections)}"
        )
        return True

    def _get_client_id(self, websocket: WebSocket) -> str:
        """Get client identifier from WebSocket."""
        if websocket.client:
            return websocket.client.host
        return "unknown"

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        # Update client connection count
        client_id = self._websocket_clients.pop(websocket, None)
        if client_id and self._client_connections[client_id] > 0:
            self._client_connections[client_id] -= 1
            if self._client_connections[client_id] == 0:
                del self._client_connections[client_id]

        # Remove from all subscriptions
        for channel in self._subscriptions.values():
            if websocket in channel:
                channel.remove(websocket)

        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, channel: str):
        """Subscribe a connection to a channel."""
        if channel not in self._subscriptions:
            self._subscriptions[channel] = []
        if websocket not in self._subscriptions[channel]:
            self._subscriptions[channel].append(websocket)

    def unsubscribe(self, websocket: WebSocket, channel: str):
        """Unsubscribe a connection from a channel."""
        if channel in self._subscriptions and websocket in self._subscriptions[channel]:
            self._subscriptions[channel].remove(websocket)

    def get_subscriptions(self, websocket: WebSocket) -> List[str]:
        """Get list of channels a WebSocket is subscribed to."""
        return [
            channel
            for channel, subs in self._subscriptions.items()
            if websocket in subs
        ]

    async def send_personal(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send a message to a specific connection."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connections."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """Broadcast a message to all connections subscribed to a channel."""
        if channel not in self._subscriptions:
            return

        disconnected = []
        for connection in self._subscriptions[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn)

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self.active_connections)

    def get_client_count(self) -> int:
        """Get number of unique clients."""
        return len(self._client_connections)


# Global WebSocket manager instance
ws_manager = WebSocketManager()


async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections."""
    connected = await ws_manager.connect(websocket)
    if not connected:
        return

    try:
        while True:
            data = await websocket.receive_json()

            # Handle subscription messages
            if data.get("type") == "subscribe":
                channel = data.get("channel")
                if channel:
                    ws_manager.subscribe(websocket, channel)
                    await ws_manager.send_personal(
                        websocket,
                        {
                            "type": "subscribed",
                            "channel": channel,
                            "timestamp": datetime.now().isoformat(),
                        },
                    )

            elif data.get("type") == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    ws_manager.unsubscribe(websocket, channel)
                    await ws_manager.send_personal(
                        websocket,
                        {
                            "type": "unsubscribed",
                            "channel": channel,
                            "timestamp": datetime.now().isoformat(),
                        },
                    )

            elif data.get("type") == "ping":
                await ws_manager.send_personal(
                    websocket,
                    {"type": "pong", "timestamp": datetime.now().isoformat()},
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)
