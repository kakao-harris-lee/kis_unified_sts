"""Futures contract / roll-state read-model freshness (Phase A).

Surfaces the ``futures:contract:latest`` snapshot published by
services/futures_contract (roll_state, days_to_expiry, front/night codes) on
the Cockpit health page. Read-only; never touches an order path.
"""

from __future__ import annotations

from typing import Any

from services.dashboard.routes.health_ops import (
    _coerce_redis_text,
    _redis_hgetall,
    _timestamp_summary,
)

_CONTRACT_DEFAULT_KEY = "futures:contract:latest"

# Contract state is published on the premarket/intraday/close cadence; a value
# older than ~14h (close 18:55 → premarket 05:45 gap) reads as stale, well
# inside the 24h key TTL.
_CONTRACT_DEFAULT_STALE_S = 50400


def _contract_settings() -> tuple[str, int]:
    """Return (latest_key, stale_after_seconds) from config/futures_contract.yaml."""
    try:
        from shared.config.loader import ConfigLoader

        raw = ConfigLoader.load("futures_contract.yaml")
        section = raw.get("futures_contract") if isinstance(raw, dict) else None
        section = section if isinstance(section, dict) else {}
        redis_cfg = section.get("redis")
        redis_cfg = redis_cfg if isinstance(redis_cfg, dict) else {}
        key = str(redis_cfg.get("latest_key") or _CONTRACT_DEFAULT_KEY)
        return key, _CONTRACT_DEFAULT_STALE_S
    except Exception:  # noqa: BLE001 - dashboard must not raise on config issues
        return _CONTRACT_DEFAULT_KEY, _CONTRACT_DEFAULT_STALE_S


def _futures_contract_ops(redis: Any) -> dict[str, Any]:
    """Freshness + roll summary for the ``futures:contract:latest`` snapshot.

    ``asof_ts`` is naive KST (publisher convention); ``roll_state=unknown`` or
    ``expired`` maps to a ``warn`` status even when the snapshot is fresh, so a
    missing night master or an unrolled expired contract is visible.
    """
    key, stale_after = _contract_settings()
    summary: dict[str, Any] = {
        "status": "unknown",
        "source": key,
        "product": None,
        "front_symbol": None,
        "next_symbol": None,
        "night_front_symbol": None,
        "days_to_expiry": None,
        "roll_state": None,
        "roll_reason": None,
        "new_entry_front_allowed": None,
        "hedge_front_allowed": None,
        "asof": None,
        "age_s": None,
        "stale_after_s": stale_after,
    }
    payload = _redis_hgetall(redis, key)
    if not payload:
        return summary

    timing = _timestamp_summary(payload)
    age_s = timing["age_s"]
    roll_state = _coerce_redis_text(payload.get("roll_state"))

    if age_s is None:
        status = "unknown"
    elif age_s > stale_after:
        status = "stale"
    elif roll_state in ("unknown", "expired"):
        status = "warn"
    else:
        status = "ok"

    def _int(value: Any) -> int | None:
        # _redis_hgetall JSON-decodes hash values, so a published "8" arrives
        # as int 8; a raw str/bytes still needs coercion.
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return int(value)
        text = _coerce_redis_text(value)
        if not text:
            return None
        try:
            return int(float(text))
        except (TypeError, ValueError):
            return None

    def _bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        text = _coerce_redis_text(value)
        if not text:
            return None
        return text.strip().lower() == "true"

    summary.update(
        {
            "status": status,
            "product": _coerce_redis_text(payload.get("product")) or None,
            "front_symbol": _coerce_redis_text(payload.get("front_symbol")) or None,
            "next_symbol": _coerce_redis_text(payload.get("next_symbol")) or None,
            "night_front_symbol": (
                _coerce_redis_text(payload.get("night_front_symbol")) or None
            ),
            "days_to_expiry": _int(payload.get("days_to_expiry")),
            "roll_state": roll_state,
            "roll_reason": _coerce_redis_text(payload.get("roll_reason")) or None,
            "new_entry_front_allowed": _bool(payload.get("new_entry_front_allowed")),
            "hedge_front_allowed": _bool(payload.get("hedge_front_allowed")),
            "asof": timing["timestamp"],
            "age_s": age_s,
        }
    )
    return summary
