"""On-entry daily-coverage backfill for dynamic-universe stock symbols.

When a symbol enters the screener/fusion universe it must be immediately
trade-ready, which for daily strategies (e.g. ``pattern_pullback``) means having
enough daily history for SMA(200).  KIS only serves ~100 daily bars per call, so
freshly-added symbols start shallow and the daily trend gate silently fails.

This module provides a small, decoupled queue:

* :func:`enqueue_symbols` — cheap, called from any container (read-only data
  mounts are fine) when the universe changes. Adds codes to a Redis set.
* :func:`ensure_daily_coverage` — runs in a container with write access + KIS
  credentials (the scheduler). Drains the queue, skips symbols already deep
  (idempotent), and paginating-backfills the rest. Throttled/batched so an
  LLM universe refresh of many symbols never hammers KIS.

Config-driven (``config/stock_coverage.yaml`` / env); no hardcoded symbol lists.
KST-native via the trading calendar used by the underlying backfill.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_FILE = "stock_coverage.yaml"
_CONFIG_SECTION = "stock_coverage"

# Redis set of codes awaiting a deep daily backfill (DB 1, TTL'd).
PENDING_KEY = "stock:coverage:pending"
# Hash of code -> ISO date last ensured, so we don't re-check on every cycle.
ENSURED_KEY = "stock:coverage:ensured"


@dataclass(frozen=True)
class CoverageConfig:
    """Daily-coverage backfill policy (config/env driven)."""

    enabled: bool = True
    # Minimum daily bars a symbol must have to be considered trade-ready.
    min_daily_bars: int = 200
    # Calendar-day lookback requested from KIS when deepening (pagination walks
    # backward within this window). 400 calendar days ~= 270 trading days.
    backfill_days: int = 400
    # Max symbols deepened per worker cycle (bounds KIS load on bulk universe
    # refreshes; the rest stay queued for the next cycle).
    max_per_cycle: int = 8
    # Seconds to sleep between per-symbol backfills (polite KIS throttle).
    throttle_seconds: float = 1.0
    # TTL for the pending/ensured Redis keys (seconds).
    redis_ttl_seconds: int = 86400

    @classmethod
    def load(cls) -> CoverageConfig:
        raw: dict[str, Any] = {}
        try:
            from shared.config.loader import ConfigLoader

            raw = ConfigLoader.load(_CONFIG_FILE).get(_CONFIG_SECTION, {}) or {}
        except Exception as exc:  # noqa: BLE001 - config is optional; env can drive it
            logger.debug("stock_coverage.yaml load failed (%s); using defaults", exc)

        def _int(env: str, key: str, default: int) -> int:
            val = os.getenv(env)
            if val is not None:
                try:
                    return int(val)
                except ValueError:
                    pass
            try:
                return int(raw.get(key, default))
            except (TypeError, ValueError):
                return default

        def _float(env: str, key: str, default: float) -> float:
            val = os.getenv(env)
            if val is not None:
                try:
                    return float(val)
                except ValueError:
                    pass
            try:
                return float(raw.get(key, default))
            except (TypeError, ValueError):
                return default

        def _flag(env: str, key: str, default: bool) -> bool:
            val = os.getenv(env)
            if val is not None:
                return val.strip().lower() in {"1", "true", "yes", "on"}
            return bool(raw.get(key, default))

        return cls(
            enabled=_flag("STOCK_COVERAGE_ENABLED", "enabled", cls.enabled),
            min_daily_bars=_int(
                "STOCK_COVERAGE_MIN_DAILY_BARS", "min_daily_bars", cls.min_daily_bars
            ),
            backfill_days=_int(
                "STOCK_COVERAGE_BACKFILL_DAYS", "backfill_days", cls.backfill_days
            ),
            max_per_cycle=_int(
                "STOCK_COVERAGE_MAX_PER_CYCLE", "max_per_cycle", cls.max_per_cycle
            ),
            throttle_seconds=_float(
                "STOCK_COVERAGE_THROTTLE_SECONDS",
                "throttle_seconds",
                cls.throttle_seconds,
            ),
            redis_ttl_seconds=_int(
                "STOCK_COVERAGE_REDIS_TTL_SECONDS",
                "redis_ttl_seconds",
                cls.redis_ttl_seconds,
            ),
        )


def _normalize(codes: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    if not isinstance(codes, (list, tuple, set)):
        return out
    for raw in codes:
        code = str(raw).strip()
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def enqueue_symbols(
    codes: Any,
    *,
    redis_client: Any | None = None,
    config: CoverageConfig | None = None,
) -> int:
    """Queue newly-seen universe symbols for a deep daily backfill.

    Best-effort and side-effect-free on failure: callers (e.g. the ingest
    universe-change handler) must never break on a Redis hiccup.  Returns the
    number of codes added to the pending set.
    """
    cfg = config or CoverageConfig.load()
    if not cfg.enabled:
        return 0
    symbols = _normalize(codes)
    if not symbols:
        return 0
    try:
        if redis_client is None:
            from shared.streaming.client import RedisClient

            redis_client = RedisClient.get_client()
        added = int(redis_client.sadd(PENDING_KEY, *symbols))
        redis_client.expire(PENDING_KEY, cfg.redis_ttl_seconds)
        logger.info(
            "coverage: enqueued %d/%d symbols for deep daily backfill",
            added,
            len(symbols),
        )
        return added
    except Exception as exc:  # noqa: BLE001 - never break the caller on Redis errors
        logger.warning("coverage: enqueue failed: %s", exc)
        return 0


def _current_daily_bar_count(store: Any, code: str) -> int:
    """Return the number of daily bars currently stored for ``code``."""
    try:
        df = store.get_daily_bars(code, limit=0)
        return 0 if df is None else int(len(df))
    except Exception as exc:  # noqa: BLE001 - missing symbol dirs return 0, not crash
        logger.debug("coverage: bar count read failed for %s: %s", code, exc)
        return 0


async def ensure_daily_coverage(
    codes: list[str] | None = None,
    *,
    redis_client: Any | None = None,
    store: Any | None = None,
    config: CoverageConfig | None = None,
) -> dict[str, Any]:
    """Deepen daily history for shallow universe symbols (idempotent, throttled).

    Drains :data:`PENDING_KEY` (or uses the explicit ``codes``), skips symbols
    that already have ``>= min_daily_bars`` daily bars, and paginating-backfills
    the rest up to ``max_per_cycle`` symbols.  One symbol's failure never blocks
    the others; failures stay queued for the next cycle.

    Returns a summary dict for logging/metrics.
    """
    import asyncio

    cfg = config or CoverageConfig.load()
    summary: dict[str, Any] = {
        "enabled": cfg.enabled,
        "checked": 0,
        "already_deep": 0,
        "deepened": 0,
        "failed": 0,
        "requeued": 0,
        "rows": 0,
    }
    if not cfg.enabled:
        return summary

    if redis_client is None:
        try:
            from shared.streaming.client import RedisClient

            redis_client = RedisClient.get_client()
        except (
            Exception
        ) as exc:  # noqa: BLE001 - explicit codes path may not need Redis
            logger.debug("coverage: Redis unavailable: %s", exc)
            redis_client = None

    if store is None:
        from shared.storage.config import StorageConfig
        from shared.storage.market_data_store import ParquetMarketDataStore

        store = ParquetMarketDataStore(
            StorageConfig.load_or_default().market_data.parquet.root,
            asset_class="stock",
        )

    # Source the candidate set: explicit codes, else drain the pending Redis set.
    if codes is not None:
        candidates = _normalize(codes)
        drained = False
    else:
        candidates = []
        drained = True
        if redis_client is not None:
            try:
                candidates = _normalize(redis_client.smembers(PENDING_KEY))
            except Exception as exc:  # noqa: BLE001
                logger.warning("coverage: pending read failed: %s", exc)

    if not candidates:
        return summary

    from shared.collector.historical.parquet_backfill import (
        collect_stock_daily_parquet,
    )

    to_deepen: list[str] = []
    done: list[str] = []
    for code in candidates:
        summary["checked"] += 1
        if _current_daily_bar_count(store, code) >= cfg.min_daily_bars:
            summary["already_deep"] += 1
            done.append(code)  # idempotent: clear from queue
            continue
        to_deepen.append(code)

    batch = to_deepen[: max(0, cfg.max_per_cycle)]
    for code in batch:
        try:
            result = await collect_stock_daily_parquet(
                days=cfg.backfill_days,
                codes=[code],
                resume=True,
                verbose=False,
            )
            depth = _current_daily_bar_count(store, code)
            summary["rows"] += int(getattr(result, "rows", 0) or 0)
            if depth >= cfg.min_daily_bars:
                summary["deepened"] += 1
                done.append(code)
                logger.info("coverage: %s deepened to %d daily bars", code, depth)
            else:
                # KIS has no deeper history (recent listing). Mark ensured so we
                # don't retry forever, but log so it's visible.
                summary["failed"] += 1
                done.append(code)
                logger.warning(
                    "coverage: %s only %d daily bars after backfill "
                    "(KIS history exhausted)",
                    code,
                    depth,
                )
        except Exception as exc:  # noqa: BLE001 - one symbol must not abort the batch
            summary["failed"] += 1
            logger.warning("coverage: backfill failed for %s: %s", code, exc)
            # leave in queue for the next cycle (transient KIS/network error)
        if cfg.throttle_seconds > 0:
            await asyncio.sleep(cfg.throttle_seconds)

    # Anything beyond this cycle's batch stays queued for the next run.
    summary["requeued"] = max(0, len(to_deepen) - len(batch))

    if drained and redis_client is not None and done:
        try:
            redis_client.srem(PENDING_KEY, *done)
            now_iso = _today_kst_iso()
            redis_client.hset(ENSURED_KEY, mapping=dict.fromkeys(done, now_iso))
            redis_client.expire(ENSURED_KEY, cfg.redis_ttl_seconds)
        except Exception as exc:  # noqa: BLE001
            logger.warning("coverage: queue cleanup failed: %s", exc)

    logger.info(
        "coverage: cycle done checked=%d already_deep=%d deepened=%d "
        "failed=%d requeued=%d rows=%d",
        summary["checked"],
        summary["already_deep"],
        summary["deepened"],
        summary["failed"],
        summary["requeued"],
        summary["rows"],
    )
    return summary


def _today_kst_iso() -> str:
    """Return today's date in KST as ISO (containers run TZ=Asia/Seoul)."""
    from datetime import datetime

    return datetime.now().date().isoformat()
