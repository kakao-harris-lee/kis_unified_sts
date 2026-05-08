"""ClickHouse Insert Failure Rate Tracker

Maintains a rolling-window failure-rate counter for ClickHouse batch inserts
and publishes the rate to Redis so the kill-switch service can use it as a
circuit-breaker signal.

Data flow
---------
1. ``PositionTracker._flush_batch()`` calls ``record_success()`` or
   ``record_failure()`` after each INSERT attempt.
2. A background ``_publish_loop`` task wakes every
   ``publish_interval_seconds`` and writes the current rate (0.0–1.0) to
   Redis key ``kill_switch:metrics:clickhouse_insert_fail_rate`` (DB 1).
3. The kill-switch service reads that key via
   ``_build_clickhouse_insert_fail_provider()`` (PR #164 stub provider) and
   trips the circuit if the rate exceeds its configured threshold.

Partial-insert policy
---------------------
``clickhouse_driver.Client.execute`` is all-or-nothing for MergeTree
tables; a raised exception means the entire batch was rejected.  We
therefore model each batch flush as a single event rather than tracking
individual rows.

TODO(follow-up): Once ``shared/observability/rate_tracker.py`` is extracted
(planned in the §10.3-A parallel PR for KIS API error rate), this class
should be refactored to extend that shared base class to eliminate the
duplicated rolling-window logic.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChInsertFailTrackerConfig:
    """Configuration for :class:`ClickHouseInsertFailTracker`.

    All tuneable parameters come from YAML (``config/streaming.yaml``,
    section ``clickhouse_insert_fail_rate``) so that **no magic numbers**
    live in source code.

    Args:
        enabled: When ``False`` the tracker records nothing and writes
            nothing to Redis.  Useful for backtesting environments where
            the kill-switch Redis key must remain absent.
        window_seconds: Length of the rolling observation window in seconds.
            Defaults to 300 (5 minutes).
        publish_interval_seconds: How often (in seconds) the background task
            publishes the current rate to Redis.  Defaults to 10 seconds.
        redis_key: Redis key to write.  Must match the key read by
            ``_build_clickhouse_insert_fail_provider`` in
            ``services/kill_switch/main.py``.
        redis_ttl_seconds: TTL applied to the Redis key on every write.
            Defaults to 2 × ``window_seconds`` so the key disappears if the
            process dies and no new data arrives.
    """

    enabled: bool = True
    window_seconds: int = 300
    publish_interval_seconds: int = 10
    redis_key: str = "kill_switch:metrics:clickhouse_insert_fail_rate"
    redis_ttl_seconds: int = 600  # 2 × default window_seconds

    def __post_init__(self) -> None:
        if self.window_seconds < 1:
            raise ValueError(
                f"window_seconds must be >= 1, got {self.window_seconds}"
            )
        if self.publish_interval_seconds < 1:
            raise ValueError(
                f"publish_interval_seconds must be >= 1, got {self.publish_interval_seconds}"
            )
        if not self.redis_key:
            raise ValueError("redis_key must not be empty")
        if self.redis_ttl_seconds < self.window_seconds:
            raise ValueError(
                "redis_ttl_seconds must be >= window_seconds to avoid premature key expiry"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChInsertFailTrackerConfig:
        """Build config from a dict (e.g. loaded from YAML).

        Args:
            data: Raw mapping, typically the ``clickhouse_insert_fail_rate``
                section from ``config/streaming.yaml``.

        Returns:
            Validated :class:`ChInsertFailTrackerConfig` instance.
        """
        return cls(
            enabled=bool(data.get("enabled", True)),
            window_seconds=int(data.get("window_seconds", 300)),
            publish_interval_seconds=int(data.get("publish_interval_seconds", 10)),
            redis_key=str(
                data.get(
                    "redis_key",
                    "kill_switch:metrics:clickhouse_insert_fail_rate",
                )
            ),
            redis_ttl_seconds=int(data.get("redis_ttl_seconds", 600)),
        )


@dataclass
class _Event:
    """A single insert-attempt event stored in the rolling window."""

    timestamp: datetime
    success: bool = field(compare=False)


class ClickHouseInsertFailTracker:
    """Rolling-window ClickHouse insert failure rate tracker.

    Thread-safe: ``record_success`` / ``record_failure`` are protected by a
    ``threading.Lock`` so they can be called from both sync executor threads
    (``asyncio.to_thread``) and the async task that publishes to Redis.

    Usage::

        tracker = ClickHouseInsertFailTracker(config, redis_client)
        await tracker.start()         # starts background publish loop
        ...
        tracker.record_success()      # after successful INSERT
        tracker.record_failure()      # after failed INSERT
        ...
        await tracker.stop()          # cancels loop, cleans up

    The tracker is intentionally a thin observability side-car — it never
    raises, never blocks the caller, and its failures are logged at DEBUG
    level only.
    """

    def __init__(
        self,
        config: ChInsertFailTrackerConfig,
        redis_client: Any,
    ) -> None:
        """
        Args:
            config: Tracker configuration.
            redis_client: An ``aioredis`` / ``redis.asyncio`` client
                (``await client.set(...)`` style).  Must be connected to
                Redis DB 1.
        """
        self._config = config
        self._redis = redis_client
        self._lock = threading.Lock()
        # deque has no bound so we manage eviction manually in _evict_old
        self._window: deque[_Event] = deque()
        self._publish_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Public recording API (sync, thread-safe)
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        """Record one successful ClickHouse batch INSERT.

        No-op when ``config.enabled`` is ``False``.
        """
        if not self._config.enabled:
            return
        with self._lock:
            self._window.append(_Event(timestamp=datetime.now(), success=True))

    def record_failure(self) -> None:
        """Record one failed ClickHouse batch INSERT.

        No-op when ``config.enabled`` is ``False``.
        """
        if not self._config.enabled:
            return
        with self._lock:
            self._window.append(_Event(timestamp=datetime.now(), success=False))

    # ------------------------------------------------------------------
    # Rate computation
    # ------------------------------------------------------------------

    def current_fail_rate(self) -> float:
        """Compute the failure rate over the configured rolling window.

        Returns:
            Float in [0.0, 1.0].  Returns ``0.0`` when the window is empty
            or the tracker is disabled.
        """
        if not self._config.enabled:
            return 0.0
        with self._lock:
            self._evict_old()
            events = list(self._window)

        if not events:
            return 0.0

        failures = sum(1 for e in events if not e.success)
        return failures / len(events)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background Redis publish loop.

        Safe to call multiple times (idempotent when already running).
        """
        if not self._config.enabled:
            logger.debug("ChInsertFailTracker disabled — not starting publish loop")
            return
        if self._publish_task is not None and not self._publish_task.done():
            return  # already running
        self._publish_task = asyncio.get_event_loop().create_task(
            self._publish_loop(),
            name="ch_insert_fail_publish",
        )
        logger.info(
            "ChInsertFailTracker publish loop started "
            f"(interval={self._config.publish_interval_seconds}s, "
            f"window={self._config.window_seconds}s, "
            f"key={self._config.redis_key})"
        )

    async def stop(self) -> None:
        """Cancel the publish loop and do a final Redis write.

        Safe to call when never started or already stopped.
        """
        import contextlib

        if self._publish_task is not None and not self._publish_task.done():
            self._publish_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._publish_task
            self._publish_task = None

        if self._config.enabled:
            await self._write_to_redis()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evict_old(self) -> None:
        """Remove events older than ``window_seconds`` from the left of the deque.

        Must be called while ``self._lock`` is held.
        """
        cutoff = datetime.now().timestamp() - self._config.window_seconds
        while self._window and self._window[0].timestamp.timestamp() < cutoff:
            self._window.popleft()

    async def _write_to_redis(self) -> None:
        """Write current fail rate to Redis (async).

        Failures are swallowed and logged at DEBUG so the caller is never
        interrupted.
        """
        if not self._config.enabled:
            return
        try:
            rate = self.current_fail_rate()
            await self._redis.set(
                self._config.redis_key,
                f"{rate:.6f}",
                ex=self._config.redis_ttl_seconds,
            )
            logger.debug(
                "ChInsertFailTracker: published rate=%.4f to %s",
                rate,
                self._config.redis_key,
            )
        except Exception:
            logger.debug(
                "ChInsertFailTracker: failed to write to Redis — skipping",
                exc_info=True,
            )

    async def _publish_loop(self) -> None:
        """Background coroutine that periodically publishes the fail rate."""
        while True:
            try:
                await asyncio.sleep(self._config.publish_interval_seconds)
                await self._write_to_redis()
            except asyncio.CancelledError:
                logger.debug("ChInsertFailTracker publish loop cancelled")
                raise
            except Exception:
                logger.debug(
                    "ChInsertFailTracker publish loop error — continuing",
                    exc_info=True,
                )
