"""Shared Redis consumer-group stage framework.

Extracts the consumer-group loop (XGROUP_CREATE → XREADGROUP → per-message
handle → XACK) that news_scorer / risk_filter / order_router each reimplemented,
so every streaming daemon shares one tested loop.

Subclasses implement ``handle_message`` (return ``True`` ⇒ the framework XACKs;
``False`` ⇒ leave the message pending for retry) and may override the optional
hooks ``on_startup`` / ``pre_iteration_gate`` / ``post_poll`` / ``on_shutdown``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from typing import Any, final

logger = logging.getLogger(__name__)


class StreamStage(ABC):
    """Abstract base for a Redis consumer-group daemon stage."""

    def __init__(
        self,
        *,
        redis: Any,
        input_stream: str,
        consumer_group: str,
        worker_id: str,
        xread_block_ms: int,
        batch_size: int,
        xreadgroup_error_sleep_seconds: float = 0.5,
    ) -> None:
        self.redis = redis
        self.input_stream = input_stream
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.xread_block_ms = xread_block_ms
        self.batch_size = batch_size
        self._xreadgroup_error_sleep = xreadgroup_error_sleep_seconds
        self._stop = asyncio.Event()

    # -- subclass contract ------------------------------------------------ #

    @abstractmethod
    async def handle_message(self, msg_id: bytes, fields: dict[bytes, bytes]) -> bool:
        """Process one message.

        Returns:
            ``True``  → the framework XACKs the message after this returns.
            ``False`` → the framework does NOT XACK (stays pending for retry).

        Deliberate skips (poison-pill parse error, gate-blocked) should return
        ``True`` so the message is consumed; transient failures should return
        ``False`` so it is retried. Exceptions raised here propagate out of the
        loop (``on_shutdown`` still runs); subclasses should catch their own
        recoverable errors and map them to a bool.
        """
        ...

    # -- optional hooks (no-op defaults) --------------------------------- #

    async def on_startup(self) -> None:  # noqa: B027 - intentional optional hook
        """Called once before the consume loop. Override for startup guards."""

    async def pre_iteration_gate(self) -> bool:
        """Called at the top of each loop iteration, before XREADGROUP.

        Return ``False`` to abort the loop (e.g. a kill-switch sentinel
        appeared). Default: always proceed.
        """
        return True

    async def post_poll(self, message_count: int) -> None:  # noqa: B027
        """Called after each XREADGROUP returns (``message_count == 0`` when idle).

        Override for per-cycle observability (e.g. backlog gauge update).
        """

    async def on_shutdown(self) -> None:  # noqa: B027 - intentional optional hook
        """Called in the loop's ``finally`` (even on exception).

        Override to flush writers/publishers.
        """

    # -- framework loop (not overridden) --------------------------------- #

    @final
    async def run(self) -> None:
        try:
            await self.on_startup()

            with contextlib.suppress(Exception):
                await self.redis.xgroup_create(
                    self.input_stream, self.consumer_group, id="0", mkstream=True
                )

            while not self._stop.is_set():
                if not await self.pre_iteration_gate():
                    return

                try:
                    messages = await self.redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.worker_id,
                        streams={self.input_stream: ">"},
                        count=self.batch_size,
                        block=self.xread_block_ms,
                    )
                except Exception:
                    logger.exception(
                        "xreadgroup error; sleeping %.1fs",
                        self._xreadgroup_error_sleep,
                    )
                    await asyncio.sleep(self._xreadgroup_error_sleep)
                    continue

                count = sum(len(msgs) for _stream, msgs in messages) if messages else 0
                await self.post_poll(count)

                if not messages:
                    await asyncio.sleep(0)
                    continue

                for _stream, msgs in messages:
                    for msg_id, data in msgs:
                        should_ack = await self.handle_message(msg_id, data)
                        if should_ack:
                            await self.redis.xack(
                                self.input_stream, self.consumer_group, msg_id
                            )
        finally:
            await self.on_shutdown()

    async def stop(self) -> None:
        self._stop.set()
