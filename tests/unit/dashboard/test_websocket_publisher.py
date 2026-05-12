"""WebSocket publisher — Redis pubsub subscription + 1s data-freshness broadcast."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from services.dashboard.websocket import WebSocketManager


@pytest.fixture
def manager():
    return WebSocketManager()


@pytest.mark.asyncio
async def test_publisher_class_exists(manager):
    """Module imports cleanly."""
    from services.dashboard.websocket_publisher import WebSocketPublisher
    publisher = WebSocketPublisher(manager=manager)
    assert publisher is not None


@pytest.mark.asyncio
async def test_publishes_kill_switch_diff(manager):
    """Publisher broadcasts kill-switch state only when it changes."""
    from services.dashboard.websocket_publisher import WebSocketPublisher
    publisher = WebSocketPublisher(manager=manager)
    manager.broadcast_topic = AsyncMock()

    state_a = {"enabled": False, "active_conditions": []}
    state_b = {"enabled": True, "active_conditions": [{"name": "daily_mdd_exceeded"}]}

    with patch.object(publisher, "_fetch_kill_switch_state", new=AsyncMock(return_value=state_a)):
        await publisher._tick_kill_switch()
        await publisher._tick_kill_switch()  # unchanged → no second broadcast

    assert manager.broadcast_topic.call_count == 1

    with patch.object(publisher, "_fetch_kill_switch_state", new=AsyncMock(return_value=state_b)):
        await publisher._tick_kill_switch()

    assert manager.broadcast_topic.call_count == 2


@pytest.mark.asyncio
async def test_data_freshness_broadcasts_every_tick(manager):
    """Data freshness broadcasts on every tick (low-frequency periodic)."""
    from services.dashboard.websocket_publisher import WebSocketPublisher
    publisher = WebSocketPublisher(manager=manager)
    manager.broadcast_topic = AsyncMock()

    state = {"sources": [{"asset_class": "futures", "fresh_ratio": 1.0}]}
    with patch.object(publisher, "_fetch_data_freshness_state", new=AsyncMock(return_value=state)):
        await publisher._tick_data_freshness()
        await publisher._tick_data_freshness()

    assert manager.broadcast_topic.call_count == 2


@pytest.mark.asyncio
async def test_start_stop_lifecycle(manager):
    """Start spawns tasks, stop cancels them."""
    from services.dashboard.websocket_publisher import WebSocketPublisher
    publisher = WebSocketPublisher(manager=manager)

    # Make the periodic loop sleep briefly and the pubsub loop a noop
    with patch.object(publisher, "_periodic_loop", new=AsyncMock()) as p, \
         patch.object(publisher, "_pubsub_loop", new=AsyncMock()) as q:
        await publisher.start()
        await asyncio.sleep(0)  # let tasks scheduler tick
        await publisher.stop()

    assert p.await_count >= 1
    assert q.await_count >= 1
