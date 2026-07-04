"""Operational health summary helper functions."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")

_OPS_ASSETS = ("stock", "futures")

_STATUS_KEYS: dict[str, str] = {
    "stock": "trading:stock:status",
    "futures": "trading:futures:status",
}

_SCHEDULER_STATUS_KEYS = ("scheduler:status", "ops:scheduler:status")

_PRODUCER_LATEST_KEYS: dict[str, tuple[dict[str, str | None], ...]] = {
    "stock": (
        {"name": "market_ingest", "key": None},
        {"name": "screener", "key": "system:universe:latest"},
        {"name": "fusion_ranker", "key": "system:trade_targets:latest"},
    ),
    "futures": ({"name": "market_ingest", "key": None},),
}


def _coerce_redis_text(value: Any) -> str | None:
    """Decode bytes or pass through str. Returns None for other types."""
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            return None
    if isinstance(value, str):
        return value
    return None


def _ops_targets(asset: str) -> tuple[str, ...]:
    return _OPS_ASSETS if asset == "all" else (asset,)


def _maybe_json(value: Any) -> Any:
    text = _coerce_redis_text(value)
    if text is None:
        return value
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def _safe_mapping(value: Any) -> dict[str, Any]:
    value = _maybe_json(value)
    return value if isinstance(value, dict) else {}


def _decode_hash(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    decoded: dict[str, Any] = {}
    for key, value in raw.items():
        key_text = _coerce_redis_text(key) if isinstance(key, bytes) else str(key)
        if not key_text:
            continue
        decoded[key_text] = _maybe_json(value)
    return decoded


def _redis_get(redis: Any, key: str) -> Any:
    if redis is None:
        return None
    try:
        return redis.get(key)
    except Exception:  # noqa: BLE001
        return None


def _redis_hgetall(redis: Any, key: str) -> dict[str, Any]:
    if redis is None:
        return {}
    try:
        return _decode_hash(redis.hgetall(key) or {})
    except Exception:  # noqa: BLE001
        return {}


def _read_json_key(redis: Any, key: str) -> dict[str, Any]:
    return _safe_mapping(_redis_get(redis, key))


def _parse_ops_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), UTC)
        except (OSError, ValueError):
            return None

    text = _coerce_redis_text(value) or str(value)
    text = text.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_KST)
    return parsed.astimezone(UTC)


def _timestamp_summary(payload: dict[str, Any]) -> dict[str, Any]:
    for field in (
        "updated_at",
        "generated_at",
        "last_success_at",
        "last_run_at",
        "asof",
        "timestamp",
    ):
        parsed = _parse_ops_timestamp(payload.get(field))
        if parsed is not None:
            return {
                "timestamp": parsed.isoformat(),
                "age_s": max(0, int((datetime.now(UTC) - parsed).total_seconds())),
                "field": field,
            }
    return {"timestamp": None, "age_s": None, "field": None}


def _status_from_known_items(items: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "unknown") for item in items}
    if not statuses or statuses == {"unknown"}:
        return "unknown"
    if statuses == {"ok"}:
        return "ok"
    if "ok" in statuses:
        return "degraded"
    return sorted(statuses)[0]


def _process_ops(processes: list[dict[str, Any]], asset: str) -> dict[str, Any]:
    process = next((p for p in processes if p.get("asset_class") == asset), None)
    if not process:
        return {
            "status": "unknown",
            "alive": None,
            "pid": None,
            "uptime_s": None,
            "last_activity_s": None,
        }
    alive = bool(process.get("alive"))
    return {
        "status": "ok" if alive else "unknown",
        "alive": alive,
        "pid": process.get("pid") or None,
        "uptime_s": process.get("uptime_s"),
        "last_activity_s": process.get("last_activity_s"),
    }


def _data_freshness_ops(sources: list[dict[str, Any]], asset: str) -> dict[str, Any]:
    matches = [src for src in sources if src.get("asset_class") == asset]
    if not matches:
        return {
            "status": "unknown",
            "sources": [],
            "fresh_ratio": None,
            "last_tick_s": None,
        }

    ratios = [
        float(src.get("fresh_ratio"))
        for src in matches
        if isinstance(src.get("fresh_ratio"), (int, float))
    ]
    last_ticks = [
        int(src.get("last_tick_s"))
        for src in matches
        if isinstance(src.get("last_tick_s"), int) and int(src.get("last_tick_s")) >= 0
    ]
    status = "ok" if ratios and max(ratios) > 0 and last_ticks else "unknown"
    return {
        "status": status,
        "sources": matches,
        "fresh_ratio": round(max(ratios), 4) if ratios else None,
        "last_tick_s": min(last_ticks) if last_ticks else None,
    }


def _kill_switch_ops(kill_switch: dict[str, Any]) -> dict[str, Any]:
    active = kill_switch.get("active_conditions") or []
    enabled = bool(kill_switch.get("enabled"))
    return {
        "status": "tripped" if enabled or active else "ok",
        "enabled": enabled,
        "active_conditions": active if isinstance(active, list) else [],
        "last_triggered_at": kill_switch.get("last_triggered_at"),
    }


def _read_status_hash(redis: Any, asset: str) -> dict[str, Any]:
    key = _STATUS_KEYS.get(asset)
    if not key:
        return {}
    status = _redis_hgetall(redis, key)
    if status:
        return status
    return _read_json_key(redis, key)


def _mode_ops(asset: str, status: dict[str, Any]) -> dict[str, Any]:
    config = _safe_mapping(status.get("config"))
    direct_mode = status.get("mode") or status.get("run_mode")
    if isinstance(direct_mode, str) and direct_mode.strip():
        return {
            "value": direct_mode.strip().lower(),
            "source": f"{_STATUS_KEYS[asset]}.mode",
        }

    execution_mode = config.get("execution_mode") or config.get("mode")
    if isinstance(execution_mode, str) and execution_mode.strip():
        return {
            "value": execution_mode.strip().lower(),
            "source": f"{_STATUS_KEYS[asset]}.config.execution_mode",
        }

    if isinstance(config.get("paper_trading"), bool):
        return {
            "value": "paper" if config["paper_trading"] else "live",
            "source": f"{_STATUS_KEYS[asset]}.config.paper_trading",
        }

    env_key = "STOCK_PIPELINE_MODE" if asset == "stock" else "FUTURES_PIPELINE_MODE"
    env_mode = os.getenv(env_key, "").strip()
    if env_mode:
        return {"value": env_mode.lower(), "source": f"env:{env_key}"}

    return {"value": "unknown", "source": None}


def _pipeline_ops(asset: str, status: dict[str, Any]) -> dict[str, Any]:
    if not status:
        return {
            "status": "unknown",
            "state": "unknown",
            "source": _STATUS_KEYS.get(asset),
            "updated_at": None,
            "age_s": None,
            "publisher_pid": None,
            "details": None,
        }

    timing = _timestamp_summary(status)
    state = str(status.get("state") or "unknown").lower()
    pipeline = _safe_mapping(status.get("pipeline"))
    positions = _safe_mapping(status.get("positions"))
    strategies = _safe_mapping(status.get("strategies"))
    is_running = state in {"running", "waiting"} or pipeline.get("is_running") is True
    pipeline_status = (
        "ok" if is_running else ("unknown" if state == "unknown" else state)
    )

    return {
        "status": pipeline_status,
        "state": state,
        "source": status.get("source") or _STATUS_KEYS.get(asset),
        "updated_at": timing["timestamp"],
        "age_s": timing["age_s"],
        "publisher_pid": status.get("publisher_pid"),
        "open_positions": positions.get("open_positions"),
        "strategies": strategies.get("strategies"),
        "details": pipeline or None,
    }


def _producer_from_data_freshness(
    asset: str,
    data_freshness: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": "market_ingest",
        "status": data_freshness.get("status", "unknown"),
        "source": "data_freshness",
        "last_seen_age_s": data_freshness.get("last_tick_s"),
        "fresh_ratio": data_freshness.get("fresh_ratio"),
        "symbol_count": sum(
            int(src.get("symbol_count", 0) or 0)
            for src in data_freshness.get("sources", [])
            if src.get("asset_class") == asset
        ),
    }


def _producer_from_latest_key(redis: Any, name: str, key: str) -> dict[str, Any]:
    payload = _read_json_key(redis, key)
    if not payload:
        return {
            "name": name,
            "status": "unknown",
            "source": key,
            "updated_at": None,
            "age_s": None,
            "item_count": None,
        }

    timing = _timestamp_summary(payload)
    codes = payload.get("codes")
    item_count = len(codes) if isinstance(codes, list) else None
    return {
        "name": name,
        "status": "ok",
        "source": key,
        "updated_at": timing["timestamp"],
        "age_s": timing["age_s"],
        "item_count": item_count,
    }


def _producers_ops(
    redis: Any,
    asset: str,
    data_freshness: dict[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for spec in _PRODUCER_LATEST_KEYS.get(asset, ()):
        name = str(spec["name"])
        key = spec.get("key")
        if key is None:
            items.append(_producer_from_data_freshness(asset, data_freshness))
        else:
            items.append(_producer_from_latest_key(redis, name, str(key)))
    return {"status": _status_from_known_items(items), "items": items}


def _scheduler_ops(redis: Any) -> dict[str, Any]:
    for key in _SCHEDULER_STATUS_KEYS:
        payload = _redis_hgetall(redis, key) or _read_json_key(redis, key)
        if not payload:
            continue
        timing = _timestamp_summary(payload)
        jobs = payload.get("jobs")
        return {
            "status": str(payload.get("status") or "ok").lower(),
            "source": key,
            "updated_at": timing["timestamp"],
            "age_s": timing["age_s"],
            "last_run_at": payload.get("last_run_at"),
            "last_success_at": payload.get("last_success_at"),
            "jobs": jobs if isinstance(jobs, list) else [],
        }

    return {
        "status": "unknown",
        "source": None,
        "updated_at": None,
        "age_s": None,
        "last_run_at": None,
        "last_success_at": None,
        "jobs": [],
    }


def _forecasting_ops(forecasting: dict[str, Any]) -> dict[str, Any]:
    forecast_age = forecasting.get("forecast_age_s")
    forecast_fresh = bool(forecasting.get("forecast_fresh"))
    service_alive = bool(forecasting.get("service_alive"))
    if service_alive and forecast_fresh:
        status = "ok"
    elif forecast_age in (None, -1) and not forecast_fresh:
        status = "unknown"
    else:
        status = "stale"
    return {
        "status": status,
        "service_alive": service_alive,
        "forecast_fresh": forecast_fresh,
        "forecast_age_s": forecast_age if forecast_age != -1 else None,
        "model_loaded": bool(forecasting.get("model_loaded")),
        "model_last_refit": forecasting.get("model_last_refit"),
        "model_r2_oos": forecasting.get("model_r2_oos"),
    }


def _aggregate_mode(asset_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    modes = {
        asset: row["mode"]["value"]
        for asset, row in asset_rows.items()
        if row.get("mode")
    }
    known = {mode for mode in modes.values() if mode != "unknown"}
    if not known:
        value = "unknown"
    elif len(known) == 1 and all(mode in known for mode in modes.values()):
        value = next(iter(known))
    else:
        value = "mixed"
    return {"value": value, "assets": modes}


def _aggregate_pipeline(asset_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    assets = {asset: row["pipeline"] for asset, row in asset_rows.items()}
    return {"status": _status_from_known_items(list(assets.values())), "assets": assets}


def _aggregate_producers(asset_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    assets = {asset: row["producers"] for asset, row in asset_rows.items()}
    return {"status": _status_from_known_items(list(assets.values())), "assets": assets}
