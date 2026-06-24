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
# Hash of code -> ISO date a symbol was found KIS-history-exhausted (too few bars
# but no transient error). Read to skip re-fetching the *same* exhausted symbol
# again on the *same* KST day, while still re-attempting on a later day so a
# recent listing eventually deepens as it accrues history.
ENSURED_KEY = "stock:coverage:exhausted"
# Worker overlap lock so two scheduler cron ticks never drain/backfill the same
# symbols concurrently (which would double KIS load — the opposite of the intent).
LOCK_KEY = "stock:coverage:lock"
LOCK_TTL_SECONDS = 600  # one market-hours cron interval


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
    # TTL for the pending + exhausted-today Redis keys (seconds).
    redis_ttl_seconds: int = 86400
    # --- on-entry MINUTE prewarm coordination (follow-up (c)) ---
    # Also fetch recent 1m bars into parquet for newly-admitted symbols so the
    # daemon's next warmup_engine (Tier-1 parquet) warms them immediately.
    prewarm_minutes: bool = True
    # KIS-max minute lookback (days) to fetch into parquet.
    prewarm_minute_days: int = 5
    # Skip prewarm if parquet already has >= this many recent 1m bars within the
    # prewarm window (idempotent: don't re-fetch an already-warm symbol).
    min_prewarm_minute_bars: int = 60

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
            prewarm_minutes=_flag(
                "STOCK_COVERAGE_PREWARM_MINUTES",
                "prewarm_minutes",
                cls.prewarm_minutes,
            ),
            prewarm_minute_days=_int(
                "STOCK_COVERAGE_PREWARM_MINUTE_DAYS",
                "prewarm_minute_days",
                cls.prewarm_minute_days,
            ),
            min_prewarm_minute_bars=_int(
                "STOCK_COVERAGE_MIN_PREWARM_MINUTE_BARS",
                "min_prewarm_minute_bars",
                cls.min_prewarm_minute_bars,
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


def _recent_minute_bar_count(store: Any, code: str, lookback_days: int) -> int:
    """Return the count of 1m bars stored for ``code`` within the lookback window."""
    from datetime import datetime, timedelta

    try:
        start = (datetime.now() - timedelta(days=max(lookback_days, 1))).date()
        df = store.get_minute_bars(code, start=start)
        return 0 if df is None else int(len(df))
    except Exception as exc:  # noqa: BLE001 - missing symbol dirs return 0, not crash
        logger.debug("coverage: minute count read failed for %s: %s", code, exc)
        return 0


async def ensure_minute_prewarm(
    code: str,
    *,
    store: Any,
    config: CoverageConfig | None = None,
) -> dict[str, Any]:
    """Fetch recent 1m bars into parquet so a new symbol is minute-warm.

    On-entry minute prewarm coordination (follow-up (c)): a newly-admitted
    intraday symbol needs MINUTE warmth immediately, not only at the next daemon
    warmup.  The coverage worker has no live indicator engine, so prewarm here
    means seeding the parquet store; the daemon's own ``warmup_engine`` (Tier-1
    parquet, no rate limit) then warms the symbol on its next ``_prewarm_cold``
    cycle with correct 5m buckets (the #517 fix).

    Idempotent: skips a symbol that already has ``>= min_prewarm_minute_bars``
    recent 1m bars in parquet.  Returns a small status dict; never raises (one
    symbol must not abort a batch).
    """
    cfg = config or CoverageConfig.load()
    result: dict[str, Any] = {"code": code, "prewarmed": False, "skipped": False}
    if not cfg.prewarm_minutes:
        result["disabled"] = True
        return result

    existing = _recent_minute_bar_count(store, code, cfg.prewarm_minute_days)
    if existing >= cfg.min_prewarm_minute_bars:
        result["skipped"] = True  # already warm
        result["existing_bars"] = existing
        return result

    try:
        from shared.collector.historical.parquet_backfill import (
            backfill_stock_minute_parquet,
        )

        backfill_result = await backfill_stock_minute_parquet(
            days=cfg.prewarm_minute_days,
            codes=[code],
            resume=True,
            verbose=False,
        )
        result["rows"] = int(getattr(backfill_result, "rows", 0) or 0)
        result["prewarmed"] = True
        logger.info(
            "coverage: %s minute-prewarmed (rows=%s, had=%d)",
            code,
            result["rows"],
            existing,
        )
    except Exception as exc:  # noqa: BLE001 - prewarm is best-effort
        result["error"] = str(exc)
        logger.warning("coverage: minute prewarm failed for %s: %s", code, exc)
    return result


def seed_universe_queue(
    *,
    redis_client: Any | None = None,
    config: CoverageConfig | None = None,
    universe_key: str | None = None,
) -> int:
    """Enqueue the whole current live universe for an off-hours coverage top-up.

    Reads ``system:universe:latest`` (DB 1) and enqueues every code so the
    off-hours ``ensure-coverage`` pass covers the entire live universe (not just
    on-entry adds).  Best-effort; returns the number of codes enqueued.
    """
    cfg = config or CoverageConfig.load()
    key: str = (
        universe_key
        or os.getenv("UNIVERSE_LATEST_KEY")
        or "system:universe:latest"
    )
    try:
        if redis_client is None:
            from shared.streaming.client import RedisClient

            redis_client = RedisClient.get_client()
        raw = redis_client.get(key)
    except Exception as exc:  # noqa: BLE001 - never break the caller on Redis errors
        logger.warning("coverage: universe read failed (%s): %s", key, exc)
        return 0
    if not raw:
        logger.info("coverage: universe key %s empty; nothing to seed", key)
        return 0

    codes = _parse_universe_codes(raw)
    if not codes:
        logger.info("coverage: universe %s parsed to 0 codes", key)
        return 0
    return enqueue_symbols(codes, redis_client=redis_client, config=cfg)


def _parse_universe_codes(raw: Any) -> list[str]:
    """Extract stock codes from a ``system:universe:latest`` JSON snapshot.

    Accepts a bare list (``["005930", ...]``) or a list of dicts carrying a
    ``code``/``symbol`` key (the screener snapshot shape).
    """
    import json

    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return []
    items: Any = data
    if isinstance(data, dict):
        items = data.get("symbols") or data.get("universe") or data.get("codes") or []
    if not isinstance(items, (list, tuple)):
        return []
    out: list[str] = []
    for item in items:
        if isinstance(item, dict):
            code = item.get("code") or item.get("symbol")
        else:
            code = item
        if code:
            out.append(str(code).strip())
    return out


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

    if cfg.max_per_cycle <= 0:
        logger.warning(
            "coverage: max_per_cycle=%d <= 0 — no symbols will be deepened "
            "(set STOCK_COVERAGE_ENABLED=false to pause instead)",
            cfg.max_per_cycle,
        )

    # Overlap guard: a slow cycle must not run concurrently with the next cron
    # tick (would double-drain + double-hit KIS). Drain mode only; explicit-codes
    # (manual CLI) intentionally bypasses the lock.
    drained = codes is None
    if drained and redis_client is not None:
        try:
            if not redis_client.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL_SECONDS):
                logger.info("coverage: another cycle holds the lock; skipping")
                summary["skipped_locked"] = True
                return summary
        except Exception as exc:  # noqa: BLE001 - lock is best-effort
            logger.debug("coverage: lock acquire failed (%s); proceeding", exc)

    try:
        return await _run_coverage_cycle(
            cfg=cfg,
            summary=summary,
            redis_client=redis_client,
            store=store,
            explicit_codes=codes,
            drained=drained,
        )
    finally:
        if drained and redis_client is not None:
            try:
                redis_client.delete(LOCK_KEY)
            except Exception as exc:  # noqa: BLE001
                logger.debug("coverage: lock release failed: %s", exc)


async def _run_coverage_cycle(
    *,
    cfg: CoverageConfig,
    summary: dict[str, Any],
    redis_client: Any | None,
    store: Any,
    explicit_codes: list[str] | None,
    drained: bool,
) -> dict[str, Any]:
    import asyncio

    # Source the candidate set: explicit codes, else drain the pending Redis set.
    if explicit_codes is not None:
        candidates = _normalize(explicit_codes)
    else:
        candidates = []
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

    today_iso = _today_kst_iso()
    exhausted_today = _exhausted_today(redis_client) if drained else {}

    to_deepen: list[str] = []
    clear: list[str] = []  # remove from queue (deep enough)
    exhausted_now: list[str] = []  # genuinely exhausted today (keep queued)
    # Symbols that are (or become) daily-deep — candidates for minute prewarm so
    # they are trade-ready (daily depth + minute warmth) the same cycle.
    prewarm_candidates: list[str] = []
    for code in candidates:
        summary["checked"] += 1
        if _current_daily_bar_count(store, code) >= cfg.min_daily_bars:
            summary["already_deep"] += 1
            clear.append(code)  # idempotent: clear from queue
            prewarm_candidates.append(code)
            continue
        # Already found exhausted today → don't re-fetch the same code again this
        # KST day (but it stays queued so a later day re-attempts it as it grows).
        if exhausted_today.get(code) == today_iso:
            summary["skipped_exhausted"] = summary.get("skipped_exhausted", 0) + 1
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
                clear.append(code)
                prewarm_candidates.append(code)
                logger.info("coverage: %s deepened to %d daily bars", code, depth)
            elif int(getattr(result, "page_errors", 0) or 0) > 0:
                # Transient KIS page error mid-pagination → RETRYABLE. Keep queued.
                summary["failed"] += 1
                logger.warning(
                    "coverage: %s under depth (%d) after a transient KIS error; "
                    "kept queued for retry",
                    code,
                    depth,
                )
            else:
                # Genuine exhaustion (recent listing): KIS has no deeper history
                # today. Keep queued but mark exhausted-today so we don't re-fetch
                # it again this KST day; a later day re-attempts as it accrues bars.
                summary["exhausted"] = summary.get("exhausted", 0) + 1
                exhausted_now.append(code)
                logger.warning(
                    "coverage: %s only %d daily bars (KIS history exhausted today)",
                    code,
                    depth,
                )
        except Exception as exc:  # noqa: BLE001 - one symbol must not abort the batch
            summary["failed"] += 1
            logger.warning("coverage: backfill failed for %s: %s", code, exc)
            # leave in queue for the next cycle (transient KIS/network error)
        if cfg.throttle_seconds > 0:
            await asyncio.sleep(cfg.throttle_seconds)

    # On-entry MINUTE prewarm (follow-up (c)): make daily-deep symbols minute-warm
    # the same cycle so an intraday-added symbol is fully trade-ready (daily depth
    # + minute warmth) without waiting for the next daemon warmup. Idempotent
    # (already-warm symbols are skipped), throttled, and bounded by max_per_cycle.
    if cfg.prewarm_minutes and prewarm_candidates:
        summary["prewarmed"] = 0
        summary["prewarm_skipped"] = 0
        prewarm_batch = prewarm_candidates[: max(0, cfg.max_per_cycle)]
        for code in prewarm_batch:
            pre = await ensure_minute_prewarm(code, store=store, config=cfg)
            if pre.get("prewarmed"):
                summary["prewarmed"] += 1
                summary["rows"] += int(pre.get("rows", 0) or 0)
            elif pre.get("skipped"):
                summary["prewarm_skipped"] += 1
            if cfg.throttle_seconds > 0:
                await asyncio.sleep(cfg.throttle_seconds)

    # Anything beyond this cycle's batch stays queued for the next run.
    summary["requeued"] = max(0, len(to_deepen) - len(batch))

    if drained and redis_client is not None:
        try:
            if clear:
                redis_client.srem(PENDING_KEY, *clear)
            if exhausted_now:
                redis_client.hset(
                    ENSURED_KEY, mapping=dict.fromkeys(exhausted_now, today_iso)
                )
                redis_client.expire(ENSURED_KEY, cfg.redis_ttl_seconds)
        except Exception as exc:  # noqa: BLE001
            logger.warning("coverage: queue cleanup failed: %s", exc)

    logger.info(
        "coverage: cycle done checked=%d already_deep=%d deepened=%d "
        "exhausted=%d failed=%d requeued=%d prewarmed=%d rows=%d",
        summary["checked"],
        summary["already_deep"],
        summary["deepened"],
        summary.get("exhausted", 0),
        summary["failed"],
        summary["requeued"],
        summary.get("prewarmed", 0),
        summary["rows"],
    )
    return summary


def _exhausted_today(redis_client: Any | None) -> dict[str, str]:
    """Return the code -> ISO-date map of symbols marked KIS-exhausted."""
    if redis_client is None:
        return {}
    try:
        raw = redis_client.hgetall(ENSURED_KEY) or {}
    except Exception as exc:  # noqa: BLE001
        logger.debug("coverage: exhausted-map read failed: %s", exc)
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        key = k.decode() if isinstance(k, bytes) else str(k)
        val = v.decode() if isinstance(v, bytes) else str(v)
        out[key] = val
    return out


def _today_kst_iso() -> str:
    """Return today's date in KST as ISO (containers run TZ=Asia/Seoul)."""
    from datetime import datetime

    return datetime.now().date().isoformat()
