"""Shared Redis consumer-group stage framework.

Extracts the consumer-group loop (XGROUP_CREATE → pending reclaim / XREADGROUP
→ per-message handle → XACK) that news_scorer / risk_filter / order_router each
reimplemented, so every streaming daemon shares one tested loop.

``StreamStage`` handles one input stream. ``MultiStreamStage`` applies the same
contract to several input streams while preserving stream-specific retry and
ACK behavior. Subclasses implement ``handle_message`` (return ``True`` ⇒ the
framework XACKs; ``False`` ⇒ leave the message pending for retry) and may
override the optional hooks ``on_startup`` / ``pre_iteration_gate`` /
``post_poll`` / ``on_shutdown``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, final

from shared.streaming.audit import (
    RateLimitedLog,
    decode_stream_id,
    extract_audit_fields,
    format_audit_kv,
)

logger = logging.getLogger(__name__)


def _duration_ms(started_at: float) -> int:
    return max(0, int((time.perf_counter() - started_at) * 1000))


def _log_processed_message(
    *,
    stream: str | bytes,
    consumer_group: str,
    worker_id: str,
    msg_id: bytes,
    fields: dict[bytes, bytes],
    ack: bool,
    claimed: bool,
    duration_ms: int,
) -> None:
    logger.info(
        format_audit_kv(
            event="stream_message_processed",
            stream=decode_stream_id(stream),
            consumer_group=consumer_group,
            worker_id=worker_id,
            msg_id=decode_stream_id(msg_id),
            ack=ack,
            claimed=claimed,
            duration_ms=duration_ms,
            **extract_audit_fields(fields),
        )
    )


def _log_failed_message(
    *,
    stream: str | bytes,
    consumer_group: str,
    worker_id: str,
    msg_id: bytes,
    fields: dict[bytes, bytes],
    claimed: bool,
    duration_ms: int,
) -> None:
    logger.error(
        format_audit_kv(
            event="stream_message_failed",
            stream=decode_stream_id(stream),
            consumer_group=consumer_group,
            worker_id=worker_id,
            msg_id=decode_stream_id(msg_id),
            claimed=claimed,
            duration_ms=duration_ms,
            **extract_audit_fields(fields),
        )
    )


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
        pending_retry_idle_ms: int = 60_000,
    ) -> None:
        self.redis = redis
        self.input_stream = input_stream
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.xread_block_ms = xread_block_ms
        self.batch_size = batch_size
        self._xreadgroup_error_sleep = xreadgroup_error_sleep_seconds
        self.pending_retry_idle_ms = pending_retry_idle_ms
        self._pending_claim_start_id: str | bytes = "0-0"
        self._pending_claim_disabled = pending_retry_idle_ms < 0
        self._xautoclaim_error_log = RateLimitedLog()
        self._xreadgroup_error_log = RateLimitedLog()
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

    async def _claim_pending_messages(self) -> list[tuple[bytes, dict[bytes, bytes]]]:
        """Claim idle pending messages for retry.

        ``handle_message(False)`` intentionally leaves a record in the consumer
        group's pending-entry list. ``XAUTOCLAIM`` makes that contract real
        across worker restarts and avoids a hot loop by waiting until the entry
        has been idle for ``pending_retry_idle_ms``.
        """
        if self._pending_claim_disabled:
            return []
        try:
            result = await self.redis.xautoclaim(
                self.input_stream,
                self.consumer_group,
                self.worker_id,
                self.pending_retry_idle_ms,
                self._pending_claim_start_id,
                count=self.batch_size,
            )
        except AttributeError:
            logger.warning("redis client lacks XAUTOCLAIM; pending retry disabled")
            self._pending_claim_disabled = True
            return []
        except Exception as exc:
            message = str(exc).lower()
            if "unknown command" in message or "syntax" in message:
                logger.warning(
                    "redis XAUTOCLAIM unavailable; pending retry disabled",
                    exc_info=True,
                )
                self._pending_claim_disabled = True
                return []
            self._xautoclaim_error_log.exception(
                logger,
                "xautoclaim error; sleeping %.1fs",
                self._xreadgroup_error_sleep,
            )
            await asyncio.sleep(self._xreadgroup_error_sleep)
            return []

        if not isinstance(result, (list, tuple)) or len(result) < 2:
            return []
        next_id = result[0]
        messages = result[1] or []
        self._pending_claim_start_id = next_id or "0-0"
        if self._pending_claim_start_id in {b"0-0", "0-0"}:
            self._pending_claim_start_id = "0-0"
        return list(messages)

    async def _process_messages(
        self,
        messages: list[tuple[bytes, dict[bytes, bytes]]],
        *,
        claimed: bool = False,
    ) -> None:
        for msg_id, data in messages:
            started_at = time.perf_counter()
            try:
                should_ack = await self.handle_message(msg_id, data)
            except Exception:
                _log_failed_message(
                    stream=self.input_stream,
                    consumer_group=self.consumer_group,
                    worker_id=self.worker_id,
                    msg_id=msg_id,
                    fields=data,
                    claimed=claimed,
                    duration_ms=_duration_ms(started_at),
                )
                raise
            _log_processed_message(
                stream=self.input_stream,
                consumer_group=self.consumer_group,
                worker_id=self.worker_id,
                msg_id=msg_id,
                fields=data,
                ack=should_ack,
                claimed=claimed,
                duration_ms=_duration_ms(started_at),
            )
            if should_ack:
                await self.redis.xack(self.input_stream, self.consumer_group, msg_id)

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

                claimed = await self._claim_pending_messages()
                if claimed:
                    await self.post_poll(len(claimed))
                    await self._process_messages(claimed, claimed=True)
                    continue

                try:
                    messages = await self.redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.worker_id,
                        streams={self.input_stream: ">"},
                        count=self.batch_size,
                        block=self.xread_block_ms,
                    )
                except Exception:
                    self._xreadgroup_error_log.exception(
                        logger,
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
                    await self._process_messages(list(msgs), claimed=False)
        finally:
            await self.on_shutdown()

    async def stop(self) -> None:
        self._stop.set()


class MultiStreamStage(ABC):
    """Abstract base for a Redis consumer-group daemon stage with many inputs."""

    def __init__(
        self,
        *,
        redis: Any,
        input_streams: list[str],
        consumer_group: str,
        worker_id: str,
        xread_block_ms: int,
        batch_size: int,
        xreadgroup_error_sleep_seconds: float = 0.5,
        pending_retry_idle_ms: int = 60_000,
    ) -> None:
        if not input_streams:
            raise ValueError("input_streams must not be empty")
        self.redis = redis
        self.input_streams = list(input_streams)
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.xread_block_ms = xread_block_ms
        self.batch_size = batch_size
        self._xreadgroup_error_sleep = xreadgroup_error_sleep_seconds
        self.pending_retry_idle_ms = pending_retry_idle_ms
        self._pending_claim_start_ids: dict[str, str | bytes] = dict.fromkeys(
            self.input_streams, "0-0"
        )
        self._pending_claim_disabled = pending_retry_idle_ms < 0
        self._xautoclaim_error_log = RateLimitedLog()
        self._xreadgroup_error_log = RateLimitedLog()
        self._stop = asyncio.Event()

    # -- subclass contract ------------------------------------------------ #

    @abstractmethod
    async def handle_message(
        self,
        stream: str | bytes,
        msg_id: bytes,
        fields: dict[bytes, bytes],
    ) -> bool:
        """Process one message from its source stream.

        Returns:
            ``True``  → the framework XACKs the message on ``stream``.
            ``False`` → the framework does NOT XACK (stays pending for retry).
        """
        ...

    # -- optional hooks (no-op defaults) --------------------------------- #

    async def on_startup(self) -> None:  # noqa: B027 - intentional optional hook
        """Called once before the consume loop. Override for startup guards."""

    async def pre_iteration_gate(self) -> bool:
        """Called at the top of each loop iteration, before XREADGROUP."""
        return True

    async def post_poll(self, message_count: int) -> None:  # noqa: B027
        """Called after each poll/reclaim returns a message count."""

    async def on_shutdown(self) -> None:  # noqa: B027 - intentional optional hook
        """Called in the loop's ``finally`` (even on exception)."""

    # -- framework loop (not overridden) --------------------------------- #

    async def _claim_pending_messages(
        self, stream: str
    ) -> list[tuple[bytes, dict[bytes, bytes]]]:
        """Claim idle pending messages for one source stream."""
        if self._pending_claim_disabled:
            return []
        try:
            result = await self.redis.xautoclaim(
                stream,
                self.consumer_group,
                self.worker_id,
                self.pending_retry_idle_ms,
                self._pending_claim_start_ids[stream],
                count=self.batch_size,
            )
        except AttributeError:
            logger.warning("redis client lacks XAUTOCLAIM; pending retry disabled")
            self._pending_claim_disabled = True
            return []
        except Exception as exc:
            message = str(exc).lower()
            if "unknown command" in message or "syntax" in message:
                logger.warning(
                    "redis XAUTOCLAIM unavailable; pending retry disabled",
                    exc_info=True,
                )
                self._pending_claim_disabled = True
                return []
            self._xautoclaim_error_log.exception(
                logger,
                "xautoclaim error; sleeping %.1fs",
                self._xreadgroup_error_sleep,
            )
            await asyncio.sleep(self._xreadgroup_error_sleep)
            return []

        if not isinstance(result, (list, tuple)) or len(result) < 2:
            return []
        next_id = result[0]
        messages = result[1] or []
        self._pending_claim_start_ids[stream] = next_id or "0-0"
        if self._pending_claim_start_ids[stream] in {b"0-0", "0-0"}:
            self._pending_claim_start_ids[stream] = "0-0"
        return list(messages)

    async def _claim_pending_by_stream(
        self,
    ) -> list[tuple[str, list[tuple[bytes, dict[bytes, bytes]]]]]:
        claimed_by_stream = []
        for stream in self.input_streams:
            claimed = await self._claim_pending_messages(stream)
            if claimed:
                claimed_by_stream.append((stream, claimed))
        return claimed_by_stream

    async def _process_messages(
        self,
        stream: str | bytes,
        messages: list[tuple[bytes, dict[bytes, bytes]]],
        *,
        claimed: bool = False,
    ) -> None:
        for msg_id, data in messages:
            started_at = time.perf_counter()
            try:
                should_ack = await self.handle_message(stream, msg_id, data)
            except Exception:
                _log_failed_message(
                    stream=stream,
                    consumer_group=self.consumer_group,
                    worker_id=self.worker_id,
                    msg_id=msg_id,
                    fields=data,
                    claimed=claimed,
                    duration_ms=_duration_ms(started_at),
                )
                raise
            _log_processed_message(
                stream=stream,
                consumer_group=self.consumer_group,
                worker_id=self.worker_id,
                msg_id=msg_id,
                fields=data,
                ack=should_ack,
                claimed=claimed,
                duration_ms=_duration_ms(started_at),
            )
            if should_ack:
                await self.redis.xack(stream, self.consumer_group, msg_id)

    @final
    async def run(self) -> None:
        try:
            await self.on_startup()

            for stream in self.input_streams:
                with contextlib.suppress(Exception):
                    await self.redis.xgroup_create(
                        stream, self.consumer_group, id="0", mkstream=True
                    )

            while not self._stop.is_set():
                if not await self.pre_iteration_gate():
                    return

                claimed_by_stream = await self._claim_pending_by_stream()
                if claimed_by_stream:
                    count = sum(
                        len(messages) for _stream, messages in claimed_by_stream
                    )
                    await self.post_poll(count)
                    for stream, messages in claimed_by_stream:
                        await self._process_messages(stream, messages, claimed=True)
                    continue

                try:
                    messages = await self.redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.worker_id,
                        streams=dict.fromkeys(self.input_streams, ">"),
                        count=self.batch_size,
                        block=self.xread_block_ms,
                    )
                except Exception:
                    self._xreadgroup_error_log.exception(
                        logger,
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

                for stream, msgs in messages:
                    await self._process_messages(stream, list(msgs), claimed=False)
        finally:
            await self.on_shutdown()

    async def stop(self) -> None:
        self._stop.set()
