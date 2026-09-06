"""WebSocket publisher — Redis pubsub subscription + 1s data-freshness broadcast."""
import asyncio
import json
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis

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


class TestPubsubLoopSelfHeals:
    """Operator review (2026-09-06): with Redis connect_retries=0 (fail-fast,
    shared/streaming/client.py), a single transient ConnectionError from
    pubsub.get_message() must not kill the WS event feed for the process
    lifetime. The per-iteration try/except must retry with a config-driven
    backoff and keep delivering later messages.
    """

    @pytest.mark.asyncio
    async def test_recovers_from_one_connection_error_and_delivers_next_message(
        self, manager, monkeypatch
    ):
        from services.dashboard.websocket_publisher import WebSocketPublisher

        monkeypatch.setenv("DASHBOARD_WS_PUBSUB_RETRY_SECONDS", "0.01")

        publisher = WebSocketPublisher(manager=manager)
        manager.broadcast_topic = AsyncMock()

        good_message = {
            "type": "message",
            "channel": b"trading:events:positions",
            "data": json.dumps({"asset_class": "stock", "x": 1}).encode(),
        }

        calls = {"n": 0}

        def get_message_side_effect(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise redis.ConnectionError("blip")
            if calls["n"] == 2:
                return good_message
            return None

        fake_pubsub = MagicMock()
        fake_pubsub.get_message.side_effect = get_message_side_effect
        fake_redis = MagicMock()
        fake_redis.pubsub.return_value = fake_pubsub

        with patch(
            "shared.streaming.client.RedisClient.get_client", return_value=fake_redis
        ):
            task = asyncio.create_task(publisher._pubsub_loop())
            for _ in range(200):
                await asyncio.sleep(0.01)
                if manager.broadcast_topic.await_count:
                    break
            publisher._stop.set()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        assert calls["n"] >= 2, "loop must retry get_message after ConnectionError"
        manager.broadcast_topic.assert_awaited_once_with(
            "positions", {"asset_class": "stock", "x": 1}, asset_class="stock"
        )

    @pytest.mark.asyncio
    async def test_cancelled_error_exits_loop_and_cleans_up_pubsub(self, manager):
        from services.dashboard.websocket_publisher import WebSocketPublisher

        publisher = WebSocketPublisher(manager=manager)

        def slow_get_message(**kwargs):
            import time as _time

            _time.sleep(0.05)
            return None

        fake_pubsub = MagicMock()
        fake_pubsub.get_message.side_effect = slow_get_message
        fake_redis = MagicMock()
        fake_redis.pubsub.return_value = fake_pubsub

        with patch(
            "shared.streaming.client.RedisClient.get_client", return_value=fake_redis
        ):
            task = asyncio.create_task(publisher._pubsub_loop())
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        fake_pubsub.unsubscribe.assert_called_once()
        fake_pubsub.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_repeated_connection_errors_do_not_kill_loop(
        self, manager, monkeypatch
    ):
        """A sustained outage must keep retrying, not raise out of the task."""
        from services.dashboard.websocket_publisher import WebSocketPublisher

        monkeypatch.setenv("DASHBOARD_WS_PUBSUB_RETRY_SECONDS", "0.01")

        publisher = WebSocketPublisher(manager=manager)

        fake_pubsub = MagicMock()
        fake_pubsub.get_message.side_effect = redis.ConnectionError("down")
        fake_redis = MagicMock()
        fake_redis.pubsub.return_value = fake_pubsub

        with patch(
            "shared.streaming.client.RedisClient.get_client", return_value=fake_redis
        ):
            task = asyncio.create_task(publisher._pubsub_loop())
            await asyncio.sleep(0.1)
            assert not task.done(), "loop must not exit on repeated ConnectionError"
            publisher._stop.set()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        assert fake_pubsub.get_message.call_count > 1


class TestPubsubRetryBackoffConfig:
    def test_default_retry_seconds(self, monkeypatch):
        monkeypatch.delenv("DASHBOARD_WS_PUBSUB_RETRY_SECONDS", raising=False)
        from services.dashboard.websocket_publisher import _pubsub_retry_seconds

        assert _pubsub_retry_seconds() == 0.5

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("DASHBOARD_WS_PUBSUB_RETRY_SECONDS", "1.5")
        from services.dashboard.websocket_publisher import _pubsub_retry_seconds

        assert _pubsub_retry_seconds() == 1.5

    def test_invalid_value_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("DASHBOARD_WS_PUBSUB_RETRY_SECONDS", "soon")
        from services.dashboard.websocket_publisher import _pubsub_retry_seconds

        with pytest.raises(ValueError, match="DASHBOARD_WS_PUBSUB_RETRY_SECONDS"):
            _pubsub_retry_seconds()

    def test_negative_value_raises_value_error(self, monkeypatch):
        """A non-positive backoff would spin asyncio.sleep(-1) as a no-op."""
        monkeypatch.setenv("DASHBOARD_WS_PUBSUB_RETRY_SECONDS", "-1")
        from services.dashboard.websocket_publisher import _pubsub_retry_seconds

        with pytest.raises(ValueError, match="DASHBOARD_WS_PUBSUB_RETRY_SECONDS"):
            _pubsub_retry_seconds()

    def test_zero_value_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("DASHBOARD_WS_PUBSUB_RETRY_SECONDS", "0")
        from services.dashboard.websocket_publisher import _pubsub_retry_seconds

        with pytest.raises(ValueError, match="DASHBOARD_WS_PUBSUB_RETRY_SECONDS"):
            _pubsub_retry_seconds()


class TestPubsubLoopMinorFixes:
    """Delta review minors (2026-09-06): invalid backoff must raise before any
    Redis call (no leaked subscribed pubsub), and a processing-half exception
    must not silently kill the loop's task.
    """

    @pytest.mark.asyncio
    async def test_invalid_retry_seconds_raises_before_any_redis_call(
        self, manager, monkeypatch
    ):
        from services.dashboard.websocket_publisher import WebSocketPublisher

        monkeypatch.setenv("DASHBOARD_WS_PUBSUB_RETRY_SECONDS", "-1")
        publisher = WebSocketPublisher(manager=manager)

        with patch("shared.streaming.client.RedisClient.get_client") as get_client:
            with pytest.raises(ValueError, match="DASHBOARD_WS_PUBSUB_RETRY_SECONDS"):
                await publisher._pubsub_loop()
            get_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_processing_exception_logs_and_loop_continues(
        self, manager, monkeypatch
    ):
        """broadcast_topic raising once must not kill the pubsub task — the
        loop logs a warning and keeps delivering later messages.
        """
        from services.dashboard.websocket_publisher import WebSocketPublisher

        monkeypatch.setenv("DASHBOARD_WS_PUBSUB_RETRY_SECONDS", "0.01")
        publisher = WebSocketPublisher(manager=manager)

        good_message = {
            "type": "message",
            "channel": b"trading:events:positions",
            "data": json.dumps({"asset_class": "stock", "x": 1}).encode(),
        }

        calls = {"n": 0}

        def get_message_side_effect(**kwargs):
            calls["n"] += 1
            if calls["n"] <= 2:
                return good_message
            return None

        fake_pubsub = MagicMock()
        fake_pubsub.get_message.side_effect = get_message_side_effect
        fake_redis = MagicMock()
        fake_redis.pubsub.return_value = fake_pubsub

        manager.broadcast_topic = AsyncMock(side_effect=[RuntimeError("boom"), None])

        with patch(
            "shared.streaming.client.RedisClient.get_client", return_value=fake_redis
        ):
            task = asyncio.create_task(publisher._pubsub_loop())
            for _ in range(200):
                await asyncio.sleep(0.01)
                if manager.broadcast_topic.await_count >= 2:
                    break
            publisher._stop.set()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        # The first broadcast raised, but the loop kept running and delivered
        # the second message instead of dying with an unhandled task exception.
        assert manager.broadcast_topic.await_count == 2
