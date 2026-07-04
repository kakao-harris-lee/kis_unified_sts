"""Market-structure snapshot freshness helpers."""

from __future__ import annotations

from typing import Any

from services.dashboard.routes.health_ops import (
    _coerce_redis_text,
    _redis_hgetall,
    _timestamp_summary,
)

_MARKET_STRUCTURE_DEFAULT_KEY = "market:structure:latest"

_MARKET_STRUCTURE_DEFAULT_STALE_S = 50400


def _market_structure_settings() -> tuple[str, int]:
    """Return (latest_key, stale_after_seconds) from config/market_structure.yaml."""
    try:
        from shared.config.loader import ConfigLoader

        raw = ConfigLoader.load("market_structure.yaml")
        collector = raw.get("collector") if isinstance(raw, dict) else None
        collector = collector if isinstance(collector, dict) else {}
        redis_cfg = collector.get("redis")
        redis_cfg = redis_cfg if isinstance(redis_cfg, dict) else {}
        health_cfg = collector.get("health")
        health_cfg = health_cfg if isinstance(health_cfg, dict) else {}
        key = str(redis_cfg.get("latest_key") or _MARKET_STRUCTURE_DEFAULT_KEY)
        stale_after = int(
            health_cfg.get("stale_after_seconds") or _MARKET_STRUCTURE_DEFAULT_STALE_S
        )
        return key, stale_after
    except Exception:  # noqa: BLE001 - dashboard must not raise on config issues
        return _MARKET_STRUCTURE_DEFAULT_KEY, _MARKET_STRUCTURE_DEFAULT_STALE_S


def _market_structure_ops(redis: Any) -> dict[str, Any]:
    """Freshness summary for the ``market:structure:latest`` snapshot hash.

    ``asof`` is written by the collector in naive KST; ``_timestamp_summary``
    assumes KST for naive timestamps, so ``age_s`` is publication age. Status
    is ``ok`` while the age is within the configured stale threshold (14h by
    default: > close 18:40 → premarket 08:00 gap, < the 24h key TTL).
    """
    key, stale_after = _market_structure_settings()
    summary: dict[str, Any] = {
        "status": "unknown",
        "source": key,
        "snapshot": None,
        "trade_date": None,
        "asof": None,
        "age_s": None,
        "stale_after_s": stale_after,
        "coverage_ratio": None,
        "missing_components": [],
    }
    payload = _redis_hgetall(redis, key)
    if not payload:
        return summary

    timing = _timestamp_summary(payload)
    age_s = timing["age_s"]
    if age_s is None:
        status = "unknown"
    else:
        status = "ok" if age_s <= stale_after else "stale"

    coverage: float | None = None
    raw_coverage = payload.get("coverage_ratio")
    if raw_coverage not in (None, ""):
        try:
            coverage = float(raw_coverage)
        except (TypeError, ValueError):
            coverage = None

    missing = payload.get("missing_components")
    summary.update(
        {
            "status": status,
            "snapshot": _coerce_redis_text(payload.get("snapshot")) or None,
            "trade_date": _coerce_redis_text(payload.get("trade_date")) or None,
            "asof": timing["timestamp"],
            "age_s": age_s,
            "coverage_ratio": coverage,
            "missing_components": missing if isinstance(missing, list) else [],
        }
    )
    return summary
