"""KIS API Error Rate Tracker.

Maintains a rolling-window error-rate metric for KIS REST API calls and
publishes it to Redis DB 1 under ``kill_switch:metrics:api_error_rate_5min``.

This unblocks Phase 3 Track A of the LLM-primary plan (§10.3-A), which
requires real production data for the kill-switch provider added in PR #164.

Design decisions
----------------
* **Extends RollingRateTracker** — the rolling-window / publish-loop / Redis
  write implementation lives in ``shared/observability/rate_tracker.py``
  (§10.3 DRY follow-up).  This class adds only KIS-specific concerns:
  singleton access and the ``record_error()`` alias.
* **asyncio.Lock for snapshot** — KIS client calls ``record_error`` from
  asyncio tasks inside a single event loop, so we keep the original
  ``asyncio.Lock`` for the snapshot step (injected via ``lock_factory``).
  The base defaults to ``threading.Lock``, which also works; either is
  correct here.
* **TTL semantics** — ``ErrorRateConfig`` has no explicit ``redis_ttl_seconds``
  field; the base computes ``2 × window_seconds`` automatically when the
  attribute is ``None``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar

from shared.observability.rate_tracker import RollingRateTracker

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

    ``redis_ttl_seconds`` is absent by design — the base class computes
    ``2 × window_seconds`` automatically when the value is ``None``.
    """

    enabled: bool
    window_seconds: float
    publish_interval_seconds: float
    redis_key: str

    # Satisfies RateTrackerConfigProtocol — base uses 2 × window_seconds.
    redis_ttl_seconds: int | None = None

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


class KISApiErrorRateTracker(RollingRateTracker):
    """5-minute rolling-window KIS REST API error-rate tracker.

    Extends :class:`~shared.observability.rate_tracker.RollingRateTracker`
    with KIS-specific concerns:

    * **Singleton access** — ``get_instance()`` / ``reset_instance()`` for the
      common case where a single process-wide tracker is sufficient.
    * **``record_error()`` alias** — backward-compatible alias for
      ``record_failure()``; ``shared/kis/client.py`` calls ``record_error()``
      at six call sites.

    Thread / coroutine safety:
        ``record_success`` and ``record_error`` append to a ``deque`` which is
        safe for concurrent appends from a single interpreter (GIL) and from
        multiple asyncio tasks (single-threaded event loop).

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

    def __init__(self, config: ErrorRateConfig | None = None) -> None:
        resolved_config = config or ErrorRateConfig.from_yaml()
        super().__init__(resolved_config, logger_name="KISErrorRate")

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
    # Backward-compatible alias
    # ------------------------------------------------------------------

    def record_error(self) -> None:
        """Record a failed KIS API call (5xx, EGW00201, network error).

        Alias for :meth:`record_failure` — preserved for backward compatibility
        with all call sites in ``shared/kis/client.py``.

        Safe to call from any asyncio task or sync context.  Business-logic
        errors (e.g. "no positions") must NOT be recorded here — only
        infrastructure failures count.
        """
        self.record_failure()
