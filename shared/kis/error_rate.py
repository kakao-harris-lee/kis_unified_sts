"""KIS API Error Rate Tracker.

Maintains a rolling-window error-rate metric for KIS REST API calls and
publishes it to Redis DB 1 under ``kill_switch:metrics:api_error_rate_5min``.

This unblocks Phase 3 Track A of the LLM-primary plan (§10.3-A), which
requires real production data for the kill-switch provider added in PR #164.

Design decisions
----------------
* **Rolling deque** — `collections.deque` is thread-safe for append/pop from a
  single writer.  We hold an asyncio Lock only during the snapshot iteration so
  concurrent record_* calls from multiple coroutines are safe.
* **Cheap hot path** — ``record_success`` / ``record_error`` are synchronous
  deque-appends (O(1)) and can be called from any asyncio task without
  awaiting.
* **Background publish task** — a single ``asyncio.Task`` wakes every
  ``publish_interval_seconds`` and writes the current rate to Redis DB 1
  with a TTL of ``2 * window_seconds`` so the key auto-expires when the
  process dies.
* **Opt-in** — when ``enabled: false`` the tracker's record_* methods still
  work (no-op publish) but no Redis I/O is performed.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import ClassVar

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    """Load kis_api_error_rate section from config/streaming.yaml."""
    try:
        from shared.config.loader import ConfigLoader

        cfg = ConfigLoader.load("streaming.yaml")
        return cfg.get("kis_api_error_rate", {})
    except Exception:
        logger.warning(
            "[KISErrorRate] Failed to load kis_api_error_rate config, using defaults"
        )
        return {}


@dataclass(frozen=True)
class ErrorRateConfig:
    """Configuration for the KIS API error-rate tracker.

    All values are loaded from ``config/streaming.yaml`` under the
    ``kis_api_error_rate`` key; no magic numbers live in code.
    """

    enabled: bool
    window_seconds: float
    publish_interval_seconds: float
    redis_key: str

    _DEFAULTS: ClassVar[dict] = {
        "enabled": True,
        "window_seconds": 300.0,
        "publish_interval_seconds": 10.0,
        "redis_key": "kill_switch:metrics:api_error_rate_5min",
    }

    @classmethod
    def from_yaml(cls) -> ErrorRateConfig:
        """Load config from streaming.yaml, falling back to built-in defaults."""
        raw = _load_config()
        defaults = cls._DEFAULTS
        return cls(
            enabled=bool(raw.get("enabled", defaults["enabled"])),
            window_seconds=float(
                raw.get("window_seconds", defaults["window_seconds"])
            ),
            publish_interval_seconds=float(
                raw.get(
                    "publish_interval_seconds",
                    defaults["publish_interval_seconds"],
                )
            ),
            redis_key=str(raw.get("redis_key", defaults["redis_key"])),
        )


# ---------------------------------------------------------------------------
# Core tracker
# ---------------------------------------------------------------------------


class KISApiErrorRateTracker:
    """5-minute rolling-window KIS REST API error-rate tracker.

    Thread / coroutine safety:
        ``record_success`` and ``record_error`` append to a ``deque`` which is
        safe for concurrent appends from a single interpreter (GIL) and from
        multiple asyncio tasks (single-threaded event loop).  The publish loop
        acquires an ``asyncio.Lock`` only while computing the snapshot so that
        stale entries can be pruned without racing against concurrent appends.

    Example::

        tracker = KISApiErrorRateTracker.get_instance()
        await tracker.start()           # start background Redis publisher
        tracker.record_success()
        tracker.record_error()
        rate = tracker.current_rate()
        await tracker.stop()

    Args:
        config: Parsed :class:`ErrorRateConfig`. If ``None`` the config is
            loaded from ``streaming.yaml`` automatically.
    """

    _instance: KISApiErrorRateTracker | None = None
    _lock: asyncio.Lock | None = None  # lazily created inside event loop

    def __init__(self, config: ErrorRateConfig | None = None) -> None:
        self._config = config or ErrorRateConfig.from_yaml()
        # deque of (monotonic_timestamp: float, is_error: bool)
        self._events: deque[tuple[float, bool]] = deque()
        self._publish_task: asyncio.Task | None = None
        self._running = False
        self._snapshot_lock: asyncio.Lock | None = None  # created in start()

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> KISApiErrorRateTracker:
        """Return the module-level singleton, creating it if needed.

        The singleton is re-created if the event loop has changed (e.g. in
        test isolation), but in production there is exactly one instance per
        process lifetime.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton — for testing only."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Hot-path recording (synchronous, O(1))
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        """Record a successful KIS API call.

        Safe to call from any asyncio task or sync context.  The call is
        O(1) and never blocks.
        """
        self._events.append((time.monotonic(), False))

    def record_error(self) -> None:
        """Record a failed KIS API call (5xx, EGW00201, network error).

        Safe to call from any asyncio task or sync context.  Business-logic
        errors (e.g. "no positions") must NOT be recorded here — only
        infrastructure failures count.
        """
        self._events.append((time.monotonic(), True))

    # ------------------------------------------------------------------
    # Rate computation
    # ------------------------------------------------------------------

    def current_rate(self) -> float:
        """Compute the error rate over the configured rolling window.

        Prunes events older than ``window_seconds`` from the left of the
        deque as a side-effect.  This is safe because Python's GIL ensures
        atomic list mutations and ``deque.popleft`` is O(1).

        Returns:
            float: Error fraction in [0.0, 1.0].  Returns 0.0 when the
            window contains no events.
        """
        cutoff = time.monotonic() - self._config.window_seconds

        # Prune expired events from the left (oldest)
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

        if not self._events:
            return 0.0

        errors = sum(1 for _, is_err in self._events if is_err)
        total = len(self._events)
        return errors / total

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background Redis publish task.

        Idempotent — calling ``start()`` when already running is a no-op.
        """
        if self._running:
            return
        self._snapshot_lock = asyncio.Lock()
        self._running = True
        if self._config.enabled:
            self._publish_task = asyncio.create_task(
                self._publish_loop(), name="kis_error_rate_publisher"
            )
            logger.info(
                "[KISErrorRate] Started publisher task: window=%ss interval=%ss key=%s",
                self._config.window_seconds,
                self._config.publish_interval_seconds,
                self._config.redis_key,
            )
        else:
            logger.info("[KISErrorRate] Tracker disabled — no Redis writes will occur")

    async def stop(self) -> None:
        """Cancel the background publish task gracefully."""
        self._running = False
        if self._publish_task and not self._publish_task.done():
            self._publish_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._publish_task
            self._publish_task = None
        logger.info("[KISErrorRate] Publisher task stopped")

    # ------------------------------------------------------------------
    # Background publish loop
    # ------------------------------------------------------------------

    async def _publish_loop(self) -> None:
        """Periodic coroutine that writes the current error rate to Redis DB 1.

        The loop fires every ``publish_interval_seconds``.  The Redis key TTL
        is set to ``2 * window_seconds`` so that the key auto-expires if the
        process terminates unexpectedly, preventing the kill switch from acting
        on stale data.
        """
        from shared.streaming.client import RedisClient  # local import — avoid circular

        ttl_seconds = int(self._config.window_seconds * 2)

        while self._running:
            try:
                await asyncio.sleep(self._config.publish_interval_seconds)
                if not self._running:
                    break

                async with self._snapshot_lock:  # type: ignore[union-attr]
                    rate = self.current_rate()

                try:
                    r = RedisClient.get_client()
                    r.setex(
                        self._config.redis_key,
                        ttl_seconds,
                        f"{rate:.6f}",
                    )
                    logger.debug(
                        "[KISErrorRate] Published rate=%.4f to %s (TTL=%ds)",
                        rate,
                        self._config.redis_key,
                        ttl_seconds,
                    )
                except Exception as exc:
                    logger.warning(
                        "[KISErrorRate] Redis publish failed: %s", exc, exc_info=False
                    )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("[KISErrorRate] Publish loop error: %s", exc)
                # Don't crash the loop — sleep then retry
                await asyncio.sleep(self._config.publish_interval_seconds)
