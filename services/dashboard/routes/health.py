"""Health and observability endpoints for the Cockpit page."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from services.dashboard.routes.trading import _normalize_asset_class
from shared.execution.contract_spec import ContractSpecRegistry
from shared.storage.config import StorageConfig
from shared.storage.runtime_ledger import SQLiteRuntimeLedger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])

# ---------------------------------------------------------------------------
# Process health
# ---------------------------------------------------------------------------

_PID_FILES: dict[str, Path] = {
    "futures": Path("/home/deploy/project/kis_unified_sts/pids/futures_trading.pid"),
    "stock": Path("/home/deploy/project/kis_unified_sts/pids/stock_trading.pid"),
}


def _read_pid_file(path: Path) -> int | None:
    """Read a PID file. Returns the PID as int, or None on any failure."""
    try:
        if not path.exists():
            return None
        pid = int(path.read_text().strip())
        return pid if pid > 0 else None
    except (OSError, ValueError):
        return None


def _is_alive(pid: int) -> bool:
    """Check whether the given PID is alive via ``kill(pid, 0)``."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def _proc_uptime_seconds(pid: int) -> int:
    """Return process uptime in seconds via ``/proc/<pid>`` ctime. 0 on failure."""
    try:
        ctime = Path(f"/proc/{pid}").stat().st_ctime
        return int(time.time() - ctime)
    except (OSError, IndexError, ValueError):
        return 0


@router.get("/process")
async def get_process_health() -> dict[str, Any]:
    """Return per-asset-class process status (alive flag, pid, uptime)."""
    processes: list[dict[str, Any]] = []
    for asset_class, pid_path in _PID_FILES.items():
        pid = _read_pid_file(pid_path)
        if pid is None:
            processes.append(
                {
                    "asset_class": asset_class,
                    "pid": 0,
                    "uptime_s": 0,
                    "last_activity_s": -1,
                    "alive": False,
                }
            )
            continue
        alive = _is_alive(pid)
        processes.append(
            {
                "asset_class": asset_class,
                "pid": pid,
                "uptime_s": _proc_uptime_seconds(pid) if alive else 0,
                "last_activity_s": 0,
                "alive": alive,
            }
        )
    return {"processes": processes, "checked_at": datetime.now(UTC).isoformat()}


# ---------------------------------------------------------------------------
# Shared Redis accessor
# ---------------------------------------------------------------------------


def _get_redis_client():
    """Return a Redis client on DB 1. Returns None on connection failure.

    Uses the shared ``RedisClient`` singleton (``shared/streaming/client.py``)
    which honors ``REDIS_HOST/PORT/PASSWORD/DB`` env vars and defaults to DB 1.
    """
    try:
        from shared.streaming.client import RedisClient

        return RedisClient.get_client()
    except Exception:  # noqa: BLE001 - dashboard must not raise on infra failure
        return None


# ---------------------------------------------------------------------------
# Data freshness
# ---------------------------------------------------------------------------

_DATA_FRESHNESS_KEYS: dict[str, str] = {
    "futures": "trading:futures:data_freshness",
    "stock": "trading:stock:data_freshness",
}


@router.get("/data-freshness")
async def get_data_freshness(
    asset_class: str = Query(default="all"),
) -> dict[str, Any]:
    """Return WebSocket tick-freshness stats per data source."""
    asset = _normalize_asset_class(asset_class)
    redis = _get_redis_client()
    sources: list[dict[str, Any]] = []

    targets = (
        [(asset, _DATA_FRESHNESS_KEYS[asset])]
        if asset in _DATA_FRESHNESS_KEYS
        else list(_DATA_FRESHNESS_KEYS.items())
    )

    for ac, key in targets:
        raw = None
        if redis is not None:
            try:
                raw = redis.get(key)
            except Exception:  # noqa: BLE001
                raw = None
        if raw is None:
            sources.append(
                {
                    "source": "websocket",
                    "asset_class": ac,
                    "symbol_count": 0,
                    "fresh_count": 0,
                    "fresh_ratio": 0.0,
                    "last_tick_s": -1,
                }
            )
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        symbol_count = int(payload.get("symbol_count", 0))
        fresh_count = int(payload.get("fresh_count", 0))
        ratio = (fresh_count / symbol_count) if symbol_count > 0 else 0.0
        # Clamp to [0.0, 1.0] in case of stale/inconsistent counters.
        ratio = max(0.0, min(1.0, ratio))
        sources.append(
            {
                "source": "websocket",
                "asset_class": ac,
                "symbol_count": symbol_count,
                "fresh_count": fresh_count,
                "fresh_ratio": round(ratio, 4),
                "last_tick_s": int(payload.get("last_tick_s", -1)),
            }
        )

    return {"sources": sources, "checked_at": datetime.now(UTC).isoformat()}


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

_KILL_SWITCH_CONDITIONS = (
    "daily_mdd_exceeded",
    "weekly_mdd_exceeded",
    "consecutive_losses",
    "kis_error_rate_high",
    "news_pipeline_lag",
)


def _bytes_or_str_to_bool(value: Any) -> bool:
    """Coerce a Redis return value (str / bytes / None) into a bool."""
    if value is None:
        return False
    if isinstance(value, bytes):
        value = value.decode(errors="ignore")
    return str(value).strip().lower() in ("true", "1")


@router.get("/kill-switch")
async def get_kill_switch() -> dict[str, Any]:
    """Return kill-switch enabled flag and any currently active conditions."""
    redis = _get_redis_client()
    if redis is None:
        return {
            "enabled": False,
            "active_conditions": [],
            "last_triggered_at": None,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    try:
        enabled = _bytes_or_str_to_bool(redis.get("kill_switch:enabled"))
    except Exception:  # noqa: BLE001
        enabled = False

    active: list[dict[str, Any]] = []
    for name in _KILL_SWITCH_CONDITIONS:
        try:
            flag = redis.get(f"kill_switch:condition:{name}")
        except Exception:  # noqa: BLE001
            flag = None
        if _bytes_or_str_to_bool(flag):
            try:
                value_raw = redis.get(f"kill_switch:condition:{name}:value")
            except Exception:  # noqa: BLE001
                value_raw = None
            try:
                value = float(value_raw) if value_raw is not None else None
            except (TypeError, ValueError):
                value = None
            active.append({"name": name, "value": value})

    try:
        last_trip = redis.get("kill_switch:last_triggered_at")
    except Exception:  # noqa: BLE001
        last_trip = None
    if isinstance(last_trip, bytes):
        last_trip = last_trip.decode(errors="ignore")

    return {
        "enabled": enabled,
        "active_conditions": active,
        "last_triggered_at": last_trip,
        "checked_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Aggregated summary (1s cache)
# ---------------------------------------------------------------------------

_summary_cache: dict[str, Any] = {"data": None, "expires_at": 0.0, "asset": None}
_summary_lock = Lock()
_KST = ZoneInfo("Asia/Seoul")
_DEFAULT_FUTURES_MULTIPLIER_KRW = 50_000
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


def _futures_multiplier_krw_per_point() -> int:
    try:
        registry = ContractSpecRegistry.from_yaml("config/execution.yaml")
        spec = registry.specs.get("kospi200_mini")
        if spec is not None:
            return int(spec.multiplier_krw_per_point)
    except Exception:  # noqa: BLE001
        pass
    return _DEFAULT_FUTURES_MULTIPLIER_KRW


def _is_today_kst(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bytes):
        value = value.decode(errors="ignore")
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_KST)
    return dt.astimezone(_KST).date() == datetime.now(_KST).date()


def _today_pnl_from_runtime_ledger(asset: str) -> tuple[int, bool]:
    """Return (today_pnl_krw, ledger_available)."""
    try:
        config = StorageConfig.load_or_default()
        if config.runtime_storage.backend != "sqlite":
            return 0, False
        db_path = Path(config.runtime_storage.sqlite.path)
        if not db_path.exists() or db_path.is_dir():
            return 0, False

        multiplier = _futures_multiplier_krw_per_point()
        total = 0.0
        ledger = SQLiteRuntimeLedger(config.runtime_storage.sqlite)
        try:
            targets = ("futures", "stock") if asset == "all" else (asset,)
            for target in targets:
                for row in ledger.query_trades(
                    {"asset_class": target, "limit": 10_000}
                ):
                    payload = (
                        row.get("payload")
                        if isinstance(row.get("payload"), dict)
                        else {}
                    )
                    exit_time = row.get("exit_time") or payload.get("exit_time")
                    if not _is_today_kst(exit_time):
                        continue
                    pnl = float(row.get("pnl") or payload.get("pnl") or 0.0)
                    row_asset = row.get("asset_class") or payload.get("asset_class")
                    if row_asset == "futures":
                        pnl *= multiplier
                    total += pnl
        finally:
            ledger.close()
        return int(total), True
    except Exception:  # noqa: BLE001
        return 0, False


def _today_pnl_krw(asset: str) -> int:
    """Today's realized PnL in KRW for the selected asset view."""
    pnl, ledger_available = _today_pnl_from_runtime_ledger(asset)
    if ledger_available:
        return pnl
    return 0


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


def _build_ops_summary(
    *,
    asset: str,
    redis: Any,
    processes: list[dict[str, Any]],
    data_sources: list[dict[str, Any]],
    kill_switch: dict[str, Any],
    today_pnl: int,
    forecasting: dict[str, Any],
    checked_at: str,
) -> dict[str, Any]:
    scheduler = _scheduler_ops(redis)
    forecasting_summary = _forecasting_ops(forecasting)
    kill_summary = _kill_switch_ops(kill_switch)

    asset_rows: dict[str, dict[str, Any]] = {}
    for target in _ops_targets(asset):
        status = _read_status_hash(redis, target)
        data_freshness = _data_freshness_ops(data_sources, target)
        asset_rows[target] = {
            "asset_class": target,
            "process": _process_ops(processes, target),
            "data_freshness": data_freshness,
            "kill_switch": kill_summary,
            "today_pnl": _today_pnl_krw(target),
            "scheduler": scheduler,
            "producers": _producers_ops(redis, target, data_freshness),
            "forecasting": forecasting_summary,
            "pipeline": _pipeline_ops(target, status),
            "mode": _mode_ops(target, status),
        }

    if asset == "all":
        process_summary: dict[str, Any] = {
            "status": _status_from_known_items(
                [row["process"] for row in asset_rows.values()]
            ),
            "assets": {key: row["process"] for key, row in asset_rows.items()},
        }
        data_summary: dict[str, Any] = {
            "status": _status_from_known_items(
                [row["data_freshness"] for row in asset_rows.values()]
            ),
            "assets": {key: row["data_freshness"] for key, row in asset_rows.items()},
        }
        pipeline_summary = _aggregate_pipeline(asset_rows)
        producers_summary = _aggregate_producers(asset_rows)
        mode_summary = _aggregate_mode(asset_rows)
    else:
        row = asset_rows[asset]
        process_summary = row["process"]
        data_summary = row["data_freshness"]
        pipeline_summary = row["pipeline"]
        producers_summary = row["producers"]
        mode_summary = row["mode"]

    return {
        "asset_class": asset,
        "checked_at": checked_at,
        "process": process_summary,
        "data_freshness": data_summary,
        "kill_switch": kill_summary,
        "today_pnl": today_pnl,
        "scheduler": scheduler,
        "producers": producers_summary,
        "forecasting": forecasting_summary,
        "pipeline": pipeline_summary,
        "mode": mode_summary,
        "assets": asset_rows,
    }


@router.get("/summary")
async def get_health_summary(
    asset_class: str = Query(default="all"),
) -> dict[str, Any]:
    """Aggregated health snapshot (1s cache, keyed by asset_class)."""
    asset = _normalize_asset_class(asset_class)
    now = time.time()

    with _summary_lock:
        cached = _summary_cache.get("data")
        if (
            cached
            and _summary_cache.get("expires_at", 0.0) > now
            and _summary_cache.get("asset") == asset
        ):
            return cached

    process = await get_process_health()
    data = await get_data_freshness(asset_class=asset_class)
    kill = await get_kill_switch()
    pnl = _today_pnl_krw(asset)
    forecasting = await get_forecasting_health()
    redis = _get_redis_client()
    ops_summary = _build_ops_summary(
        asset=asset,
        redis=redis,
        processes=process["processes"],
        data_sources=data["sources"],
        kill_switch=kill,
        today_pnl=pnl,
        forecasting=forecasting,
        checked_at=process["checked_at"],
    )

    payload = {
        "processes": process["processes"],
        "data_sources": data["sources"],
        "kill_switch": kill,
        "today_pnl": pnl,
        "asset_class": asset,
        "checked_at": process["checked_at"],
        "ops_summary": ops_summary,
        "scheduler": ops_summary["scheduler"],
        "producers": ops_summary["producers"],
        "forecasting": ops_summary["forecasting"],
        "pipeline": ops_summary["pipeline"],
        "mode": ops_summary["mode"],
    }

    with _summary_lock:
        _summary_cache["data"] = payload
        _summary_cache["expires_at"] = now + 1.0
        _summary_cache["asset"] = asset

    return payload


# ---------------------------------------------------------------------------
# Forecasting service health
# ---------------------------------------------------------------------------


@router.get("/forecasting")
async def get_forecasting_health() -> dict[str, Any]:
    """Forecasting service health (model + publish freshness)."""
    redis = _get_redis_client()
    forecast_raw = None
    model_raw = None
    if redis is not None:
        try:
            forecast_raw = redis.get("forecast:vol:current")
        except Exception:  # noqa: BLE001
            forecast_raw = None
        try:
            model_raw = redis.get("forecast:vol:model")
        except Exception:  # noqa: BLE001
            model_raw = None

    forecast_text = _coerce_redis_text(forecast_raw)
    model_text = _coerce_redis_text(model_raw)

    forecast_fresh = forecast_text is not None
    forecast_age_s = -1
    if forecast_text is not None:
        try:
            d = json.loads(forecast_text)
            asof = datetime.fromisoformat(d["asof"])
            forecast_age_s = int((datetime.now(UTC) - asof).total_seconds())
        except Exception:  # noqa: BLE001
            forecast_age_s = -1

    model_loaded = model_text is not None
    model_r2_oos = None
    model_last_refit = None
    if model_text is not None:
        try:
            d = json.loads(model_text)
            coeffs = d.get("coefficients", {}) if isinstance(d, dict) else {}
            model_r2_oos = coeffs.get("r2_oos")
            model_last_refit = coeffs.get("fit_date")
        except Exception:  # noqa: BLE001
            pass

    return {
        "service_alive": forecast_age_s >= 0 and forecast_age_s < 300,
        "forecast_fresh": forecast_fresh,
        "forecast_age_s": forecast_age_s,
        "model_loaded": model_loaded,
        "model_last_refit": model_last_refit,
        "model_r2_oos": model_r2_oos,
        "checked_at": datetime.now(UTC).isoformat(),
    }
