"""Data-freshness writer — publish WebSocket tick-freshness stats to Redis.

The dashboard health endpoint
(``services/dashboard/routes/health.py::get_data_freshness``) reads the STRING
key ``trading:{asset}:data_freshness`` and parses ``symbol_count``,
``fresh_count`` and ``last_tick_s`` out of the JSON payload. Nothing in
``shared/`` or ``services/`` writes that key, so the dashboard reports the
"no data" sentinel (``last_tick_s == -1``) forever and can never warn on a
stalled feed.

This module is that missing writer. ``DataFreshnessTracker`` records per-symbol
tick arrival times (from the ingest hot path) and periodically SETs a snapshot
whose schema exactly matches the health.py parser.

Design notes:
    - Additive / best-effort: ``write_snapshot`` never raises, so a Redis
      failure cannot disrupt the ingest loop.
    - Thread-safe: ``record_tick`` runs on the feed's frame-processing thread
      while ``write_snapshot`` runs on the ingest asyncio loop.
    - KST-native: ``checked_at`` uses naive ``datetime.now()`` (container
      TZ=Asia/Seoul). ``last_tick_s`` is a wall-clock *duration* so it is
      timezone-independent.
    - TTL required (CLAUDE.md): the key expires after ``ttl_seconds`` (24h
      default) so a dead ingest process stops masquerading as fresh.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_KEY = "trading:{asset}:data_freshness"

# health.py only knows these two asset classes; guard against writing a key it
# will never read.
_SUPPORTED_ASSETS = ("stock", "futures")

# CLAUDE.md default operational TTL is 24h.
DEFAULT_FRESHNESS_TTL_SECONDS = 86_400
# A symbol counts as "fresh" if it ticked within this many seconds.
DEFAULT_FRESHNESS_WINDOW_SECONDS = 60.0


def _get_redis() -> Any:
    """Return the shared Redis client singleton (DB 1, decode_responses=True)."""
    from shared.streaming.client import RedisClient

    return RedisClient.get_client()


class DataFreshnessTracker:
    """Track per-symbol last-tick times and snapshot them to Redis.

    Args:
        asset: ``"stock"`` or ``"futures"`` (matches ``_DATA_FRESHNESS_KEYS``).
        window_seconds: freshness window; falls back to the
            ``DATA_FRESHNESS_WINDOW_SECONDS`` env var then the module default.
        ttl_seconds: key TTL; falls back to the ``DATA_FRESHNESS_TTL_SECONDS``
            env var then the module default (24h).
    """

    def __init__(
        self,
        asset: str,
        *,
        window_seconds: float | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        self._asset = asset
        self._window_s = (
            window_seconds
            if window_seconds is not None
            else float(
                os.getenv(
                    "DATA_FRESHNESS_WINDOW_SECONDS", DEFAULT_FRESHNESS_WINDOW_SECONDS
                )
            )
        )
        self._ttl_s = (
            ttl_seconds
            if ttl_seconds is not None
            else int(
                os.getenv("DATA_FRESHNESS_TTL_SECONDS", DEFAULT_FRESHNESS_TTL_SECONDS)
            )
        )
        self._last_tick: dict[str, float] = {}
        self._lock = threading.Lock()

    def record_tick(self, symbol: str, *, now: float | None = None) -> None:
        """Record that ``symbol`` produced a tick (call on every tick received)."""
        ts = time.time() if now is None else now
        with self._lock:
            self._last_tick[symbol] = ts

    def build_snapshot(
        self, symbols: list[str], *, now: float | None = None
    ) -> dict[str, Any]:
        """Compute a freshness snapshot for the current subscribed universe.

        Args:
            symbols: the currently subscribed symbol universe (defines
                ``symbol_count``).
            now: reference time (defaults to ``time.time()``); injectable for
                deterministic tests.

        Returns:
            A dict with the exact fields ``get_data_freshness`` parses
            (``symbol_count``, ``fresh_count``, ``last_tick_s``) plus
            informational ``asset_class`` / ``checked_at``.
        """
        ref = time.time() if now is None else now
        with self._lock:
            # Prune symbols that rotated out of the subscribed universe. The
            # stock feed churns through many codes a day (screener / intraday
            # dynamic mode), so without this _last_tick would grow unbounded.
            # Output only ever iterates `symbols`, so pruning never changes the
            # snapshot — it strictly bounds memory.
            self._last_tick = {
                s: self._last_tick[s] for s in symbols if s in self._last_tick
            }
            last_tick = dict(self._last_tick)

        symbol_count = len(symbols)
        fresh_count = 0
        newest: float | None = None
        for sym in symbols:
            ts = last_tick.get(sym)
            if ts is None:
                continue
            if ref - ts <= self._window_s:
                fresh_count += 1
            if newest is None or ts > newest:
                newest = ts

        last_tick_s = int(ref - newest) if newest is not None else -1
        return {
            "asset_class": self._asset,
            "symbol_count": symbol_count,
            "fresh_count": fresh_count,
            "last_tick_s": last_tick_s,
            # Naive == KST (container TZ=Asia/Seoul). Informational only; the
            # health endpoint stamps its own checked_at.
            "checked_at": datetime.now().isoformat(),
        }

    def write_snapshot(
        self,
        symbols: list[str],
        *,
        now: float | None = None,
        redis_client: Any | None = None,
    ) -> dict[str, Any] | None:
        """Build and SET the freshness snapshot (best-effort).

        Args:
            symbols: currently subscribed symbol universe.
            now: reference time (injectable for tests).
            redis_client: override client (injectable for tests); defaults to
                the shared singleton.

        Returns:
            The written snapshot on success, or ``None`` if the asset is
            unsupported or the Redis write failed.
        """
        if self._asset not in _SUPPORTED_ASSETS:
            return None
        snapshot = self.build_snapshot(symbols, now=now)
        try:
            client = redis_client if redis_client is not None else _get_redis()
            client.set(
                _KEY.format(asset=self._asset),
                json.dumps(snapshot),
                ex=self._ttl_s,
            )
        except Exception:  # noqa: BLE001 - never break ingest on Redis failure
            logger.debug(
                "Failed to write data_freshness for asset=%s",
                self._asset,
                exc_info=True,
            )
            return None
        return snapshot
