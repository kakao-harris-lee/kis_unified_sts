"""Rolling-window rate tracker base class.

Provides shared rolling-window failure-rate logic for operational trackers.
Extracted as part of §10.3 DRY follow-up to eliminate the
duplicated deque / publish-loop / Redis-write pattern.

Design
------
* **Rolling deque** — ``collections.deque`` is used for O(1) append/prune.
  Events are ``(monotonic_timestamp, is_failure)`` tuples so no extra
  dataclass allocation is needed on the hot path.
* **Lock primitive** — defaults to ``threading.Lock`` which works safely in
  both pure-asyncio contexts (GIL + single event loop) and mixed
  ``asyncio.to_thread`` executor contexts.  Subclasses can pass
  ``asyncio.Lock`` via ``lock_factory`` if they prefer coroutine-level
  mutual exclusion.
* **Singleton opt-in** — the base class is NOT a singleton.  Subclasses that
  need singleton behaviour (e.g. ``KISApiErrorRateTracker``) keep their own
  ``get_instance`` / ``reset_instance`` classmethods.
* **TTL fallback** — when ``redis_ttl_seconds`` is ``None`` the effective TTL
  is ``2 × window_seconds``, matching the original KIS tracker behaviour.
* **Disabled opt-out** — ``record_success`` / ``record_failure`` are no-ops
  when ``enabled=False``; no Redis I/O is ever performed.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config protocol — subclasses bring their own dataclass
# ---------------------------------------------------------------------------


@runtime_checkable
class RateTrackerConfigProtocol(Protocol):
    """Structural type required by :class:`RollingRateTracker`.

    Both ``ErrorRateConfig`` and ``ChInsertFailTrackerConfig`` satisfy this
    protocol without any code changes.
    """

    enabled: bool
    window_seconds: float
    publish_interval_seconds: float
    redis_key: str
    redis_ttl_seconds: int | None


# ---------------------------------------------------------------------------
# Base tracker
# ---------------------------------------------------------------------------


class RollingRateTracker:
    """Abstract rolling-window rate tracker with periodic Redis publishing.

    Subclasses inherit the full rolling-window / publish-loop / Redis-write
    implementation and only need to:

    1. Call ``super().__init__(config, lock_factory)`` with their config
       object (which must satisfy :class:`RateTrackerConfigProtocol`).
    2. Optionally override ``_redis_client()`` for testing / DI.
    3. Add any domain-specific aliases (``record_error``, ``current_fail_rate``).

    Args:
        config: Config object satisfying :class:`RateTrackerConfigProtocol`.
            Both ``ErrorRateConfig`` and ``ChInsertFailTrackerConfig`` qualify.
        lock_factory: Callable that returns a lock instance.  Defaults to
            ``threading.Lock`` which is safe for both asyncio and
            ``asyncio.to_thread`` callers.  Pass ``asyncio.Lock`` if you want
            coroutine-level mutual exclusion (single event loop only).
        logger_name: Logger name prefix used in all log messages.  Subclasses
            may pass a domain-specific name for clearer log attribution.
    """

    def __init__(
        self,
        config: RateTrackerConfigProtocol,
        lock_factory: Callable[[], Any] | None = None,
        logger_name: str = "RollingRateTracker",
    ) -> None:
        self._config = config
        self._lock = (lock_factory or threading.Lock)()
        self._logger_name = logger_name
        # deque of (monotonic_timestamp: float, is_failure: bool)
        self._events: deque[tuple[float, bool]] = deque()
        self._publish_task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Hot-path recording (synchronous, O(1))
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        """Record one successful event.

        No-op when ``config.enabled`` is ``False``.  Safe to call from any
        thread or asyncio task — the internal lock is always released quickly.
        """
        if not self._config.enabled:
            return
        with self._lock:
            self._events.append((time.monotonic(), False))

    def record_failure(self) -> None:
        """Record one failed event.

        No-op when ``config.enabled`` is ``False``.  Safe to call from any
        thread or asyncio task — the internal lock is always released quickly.
        """
        if not self._config.enabled:
            return
        with self._lock:
            self._events.append((time.monotonic(), True))

    # ------------------------------------------------------------------
    # Rate computation
    # ------------------------------------------------------------------

    def current_rate(self) -> float:
        """Compute the failure rate over the configured rolling window.

        Prunes events older than ``window_seconds`` as a side-effect.
        Always returns ``0.0`` when disabled or the window is empty.

        Returns:
            Failure fraction in ``[0.0, 1.0]``.
        """
        if not self._config.enabled:
            return 0.0
        with self._lock:
            self._prune()
            if not self._events:
                return 0.0
            failures = sum(1 for _, is_fail in self._events if is_fail)
            total = len(self._events)
        return failures / total

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background Redis publish task.

        Idempotent — calling ``start()`` when already running is a no-op.
        """
        if self._running:
            return
        self._running = True
        if self._config.enabled:
            self._publish_task = asyncio.create_task(
                self._publish_loop(), name=f"{self._logger_name}_publisher"
            )
            logger.info(
                "[%s] Started publisher task: window=%ss interval=%ss key=%s",
                self._logger_name,
                self._config.window_seconds,
                self._config.publish_interval_seconds,
                self._config.redis_key,
            )
        else:
            logger.info(
                "[%s] Tracker disabled — no Redis writes will occur",
                self._logger_name,
            )

    async def stop(self) -> None:
        """Cancel the background publish task and do a final Redis write.

        Safe to call when never started or already stopped.
        """
        self._running = False
        if self._publish_task is not None and not self._publish_task.done():
            self._publish_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._publish_task
            self._publish_task = None

        if self._config.enabled:
            await self._write_to_redis()

        logger.info("[%s] Publisher task stopped", self._logger_name)

    # ------------------------------------------------------------------
    # Redis I/O
    # ------------------------------------------------------------------

    def _redis_client(self) -> Any:
        """Return a synchronous Redis client connected to DB 1.

        Subclasses may override for dependency injection (useful in tests).

        Returns:
            A ``redis.Redis`` instance (sync) from the shared streaming client.
        """
        from shared.streaming.client import RedisClient  # local — avoid circular

        return RedisClient.get_client()

    async def _write_to_redis(self) -> None:
        """Write the current failure rate to Redis DB 1.

        Uses ``SETEX`` with the configured (or computed) TTL.  All exceptions
        are caught and logged at WARNING level so the caller is never
        interrupted.
        """
        if not self._config.enabled:
            return
        try:
            rate = self.current_rate()
            ttl = self._effective_ttl()
            r = self._redis_client()
            r.setex(
                self._config.redis_key,
                ttl,
                f"{rate:.6f}",
            )
            logger.debug(
                "[%s] Published rate=%.4f to %s (TTL=%ds)",
                self._logger_name,
                rate,
                self._config.redis_key,
                ttl,
            )
        except Exception as exc:
            logger.warning(
                "[%s] Redis publish failed: %s",
                self._logger_name,
                exc,
                exc_info=False,
            )

    # ------------------------------------------------------------------
    # Background publish loop
    # ------------------------------------------------------------------

    async def _publish_loop(self) -> None:
        """Periodic coroutine that writes the current failure rate to Redis.

        Fires every ``publish_interval_seconds``.  On unexpected exceptions
        the loop logs and retries rather than terminating.
        """
        while self._running:
            try:
                await asyncio.sleep(self._config.publish_interval_seconds)
                if not self._running:
                    break
                await self._write_to_redis()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(
                    "[%s] Publish loop error: %s — retrying",
                    self._logger_name,
                    exc,
                )
                # Don't crash the loop; sleep then retry.
                await asyncio.sleep(self._config.publish_interval_seconds)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _prune(self) -> None:
        """Remove events older than ``window_seconds`` from the left.

        Must be called while ``self._lock`` is held.
        """
        cutoff = time.monotonic() - self._config.window_seconds
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    def _effective_ttl(self) -> int:
        """Compute the Redis TTL in seconds.

        When ``config.redis_ttl_seconds`` is ``None``, falls back to
        ``2 × window_seconds`` (auto-expire when process dies).

        Returns:
            TTL as a positive integer (seconds).
        """
        if self._config.redis_ttl_seconds is not None:
            return int(self._config.redis_ttl_seconds)
        return int(self._config.window_seconds * 2)
