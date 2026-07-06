"""Futures margin-risk read-model freshness (Phase B).

Surfaces the ``futures:risk:latest`` snapshot published by
services/futures_margin_risk (margin usage, liquidation buffer, stress loss,
risk level) on the Cockpit health / risk page. Read-only; no order path.
"""

from __future__ import annotations

from typing import Any

from services.dashboard.routes.health_ops import (
    _coerce_redis_text,
    _redis_hgetall,
    _timestamp_summary,
)

_MARGIN_DEFAULT_KEY = "futures:risk:latest"

# Account state is published on a short (≤15m TTL) cadence; older than ~20m
# reads as stale.
_MARGIN_DEFAULT_STALE_S = 1200


def _margin_settings() -> tuple[str, int]:
    """Return (latest_key, stale_after_seconds) from config/futures_margin.yaml."""
    try:
        from shared.config.loader import ConfigLoader

        raw = ConfigLoader.load("futures_margin.yaml")
        section = raw.get("futures_margin") if isinstance(raw, dict) else None
        section = section if isinstance(section, dict) else {}
        redis_cfg = section.get("redis")
        redis_cfg = redis_cfg if isinstance(redis_cfg, dict) else {}
        key = str(redis_cfg.get("latest_key") or _MARGIN_DEFAULT_KEY)
        max_age = section.get("account_snapshot_max_age_seconds")
        stale_after = int(max_age) if max_age else _MARGIN_DEFAULT_STALE_S
        # Never report stale below the publish cadence; clamp to a sane floor.
        return key, max(stale_after, _MARGIN_DEFAULT_STALE_S)
    except Exception:  # noqa: BLE001 - dashboard must not raise on config issues
        return _MARGIN_DEFAULT_KEY, _MARGIN_DEFAULT_STALE_S


def _futures_margin_ops(redis: Any) -> dict[str, Any]:
    """Freshness + risk summary for the ``futures:risk:latest`` snapshot.

    ``risk_level`` at ``reduce_only`` and above maps to ``warn`` even when the
    snapshot is fresh, and ``critical`` to ``critical`` — so a live stale
    snapshot (published as critical) or a margin breach is visible without the
    operator parsing raw numbers.
    """
    key, stale_after = _margin_settings()
    summary: dict[str, Any] = {
        "status": "unknown",
        "source": key,
        "risk_level": None,
        "margin_usage_pct": None,
        "maintenance_buffer_krw": None,
        "liquidation_buffer_ticks": None,
        "stress_loss_1atr_krw": None,
        "max_additional_contracts": None,
        "account_equity_krw": None,
        "degraded": None,
        "missing_components": [],
        "asof": None,
        "age_s": None,
        "stale_after_s": stale_after,
    }
    payload = _redis_hgetall(redis, key)
    if not payload:
        return summary

    timing = _timestamp_summary(payload)
    age_s = timing["age_s"]
    risk_level = _coerce_redis_text(payload.get("risk_level"))

    if age_s is not None and age_s > stale_after:
        status = "stale"
    elif risk_level == "critical":
        status = "critical"
    elif risk_level in ("reduce_only", "block_new_entries"):
        status = "warn"
    elif age_s is None:
        status = "unknown"
    else:
        status = "ok"

    def _num(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return float(value)
        text = _coerce_redis_text(value)
        if not text:
            return None
        try:
            return float(text)
        except (TypeError, ValueError):
            return None

    def _int(value: Any) -> int | None:
        num = _num(value)
        return None if num is None else int(num)

    def _bool(value: Any) -> bool | None:
        # _redis_hgetall JSON-decodes hash values, so "false"/"true" arrive as
        # Python bools; a raw str still needs coercion.
        if isinstance(value, bool):
            return value
        text = _coerce_redis_text(value)
        if not text:
            return None
        return text.strip().lower() == "true"

    missing = payload.get("missing_components")
    summary.update(
        {
            "status": status,
            "risk_level": risk_level,
            "margin_usage_pct": _num(payload.get("margin_usage_pct")),
            "maintenance_buffer_krw": _num(payload.get("maintenance_buffer_krw")),
            "liquidation_buffer_ticks": _num(payload.get("liquidation_buffer_ticks")),
            "stress_loss_1atr_krw": _num(payload.get("stress_loss_1atr_krw")),
            "max_additional_contracts": _int(payload.get("max_additional_contracts")),
            "account_equity_krw": _num(payload.get("account_equity_krw")),
            "degraded": _bool(payload.get("degraded")),
            "missing_components": missing if isinstance(missing, list) else [],
            "asof": timing["timestamp"],
            "age_s": age_s,
        }
    )
    return summary
