"""Background task: Redis pubsub → WS broadcast + periodic data-freshness/kill-switch ticks."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from typing import Any

from services.dashboard.websocket import WebSocketManager

logger = logging.getLogger(__name__)

_PERIODIC_INTERVAL_S = 1.0
_TRADING_EVENT_CHANNELS = (
    "trading:events:positions",
    "trading:events:signals",
    "trading:events:fills",
)


class WebSocketPublisher:
    """Bridges Redis pubsub trading events and periodic state snapshots to WS subscribers."""

    def __init__(self, manager: WebSocketManager):
        self.manager = manager
        self._task: asyncio.Task | None = None
        self._pubsub_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_kill_switch: dict[str, Any] | None = None

    async def start(self) -> None:
        """Spawn background loops."""
        self._stop.clear()
        self._task = asyncio.create_task(self._periodic_loop())
        self._pubsub_task = asyncio.create_task(self._pubsub_loop())

    async def stop(self) -> None:
        """Signal stop and cancel background tasks."""
        self._stop.set()
        for t in (self._task, self._pubsub_task):
            if t is not None and not t.done():
                t.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await t

    async def _fetch_kill_switch_state(self) -> dict[str, Any]:
        from services.dashboard.routes.health import get_kill_switch

        return await get_kill_switch()

    async def _fetch_data_freshness_state(self) -> dict[str, Any]:
        from services.dashboard.routes.health import get_data_freshness

        return await get_data_freshness(asset_class="all")

    async def _tick_kill_switch(self) -> None:
        try:
            state = await self._fetch_kill_switch_state()
        except Exception as e:  # noqa: BLE001
            logger.debug("kill_switch fetch failed: %s", e)
            return
        # Compare only dynamic fields (exclude checked_at)
        comparable = {k: v for k, v in state.items() if k != "checked_at"}
        last_comparable = (
            {k: v for k, v in self._last_kill_switch.items() if k != "checked_at"}
            if self._last_kill_switch
            else None
        )
        if comparable != last_comparable:
            await self.manager.broadcast_topic("kill-switch", state)
            self._last_kill_switch = state

    async def _tick_data_freshness(self) -> None:
        try:
            state = await self._fetch_data_freshness_state()
        except Exception as e:  # noqa: BLE001
            logger.debug("data_freshness fetch failed: %s", e)
            return
        await self.manager.broadcast_topic("data-freshness", state)

    async def _periodic_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self.manager.get_connection_count() > 0:
                    await self._tick_kill_switch()
                    await self._tick_data_freshness()
            except Exception as e:  # noqa: BLE001
                logger.warning("Publisher periodic loop error: %s", e)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=_PERIODIC_INTERVAL_S)
            except TimeoutError:
                continue

    async def _pubsub_loop(self) -> None:
        """Subscribe to Redis pubsub trading events and forward to WS subscribers."""
        try:
            from shared.streaming.client import RedisClient

            redis = RedisClient.get_client()
            pubsub = redis.pubsub()
        except Exception as e:  # noqa: BLE001
            logger.warning("WebSocket publisher pubsub init failed: %s", e)
            return

        try:
            for channel in _TRADING_EVENT_CHANNELS:
                pubsub.subscribe(channel)

            while not self._stop.is_set():
                # redis-py's pubsub read is blocking. Run it off the event loop
                # so dashboard HTTP requests are not delayed by socket_timeout.
                message = await asyncio.to_thread(
                    pubsub.get_message,
                    ignore_subscribe_messages=True,
                    timeout=0.5,
                )
                if message is None:
                    await asyncio.sleep(0)
                    continue
                if message.get("type") != "message":
                    continue
                channel = message.get("channel")
                if isinstance(channel, bytes):
                    channel = channel.decode()
                topic = channel.rsplit(":", 1)[-1]  # positions / signals / fills
                try:
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    payload = json.loads(data)
                except (TypeError, ValueError):
                    continue
                asset_class = (
                    payload.get("asset_class", "all")
                    if isinstance(payload, dict)
                    else "all"
                )
                await self.manager.broadcast_topic(
                    topic, payload, asset_class=asset_class
                )
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("Publisher pubsub loop error: %s", e)
        finally:
            try:
                pubsub.unsubscribe()
                pubsub.close()
            except Exception:  # noqa: BLE001
                pass
