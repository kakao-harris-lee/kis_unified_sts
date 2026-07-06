"""Health and observability endpoints for the Cockpit page."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from services.dashboard.domain.assets import normalize_asset_class
from services.dashboard.routes.health_futures_contract import _futures_contract_ops
from services.dashboard.routes.health_futures_margin import _futures_margin_ops
from services.dashboard.routes.health_market_structure import _market_structure_ops
from services.dashboard.routes.health_ops import (
    _aggregate_mode,
    _aggregate_pipeline,
    _aggregate_producers,
    _coerce_redis_text,
    _data_freshness_ops,
    _forecasting_ops,
    _kill_switch_ops,
    _mode_ops,
    _ops_targets,
    _pipeline_ops,
    _process_ops,
    _producers_ops,
    _read_status_hash,
    _scheduler_ops,
    _status_from_known_items,
)
from services.dashboard.routes.health_process import (
    _PID_FILES,
    _is_alive,
    _proc_uptime_seconds,
    _read_pid_file,
)
from shared.execution.contract_spec import ContractSpecRegistry
from shared.storage.config import StorageConfig
from shared.storage.runtime_ledger import SQLiteRuntimeLedger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])

_DATA_FRESHNESS_KEYS: dict[str, str] = {
    "futures": "trading:futures:data_freshness",
    "stock": "trading:stock:data_freshness",
}

_KILL_SWITCH_CONDITIONS = (
    "daily_mdd_exceeded",
    "weekly_mdd_exceeded",
    "consecutive_losses",
    "kis_error_rate_high",
    "news_pipeline_lag",
)

_summary_cache: dict[str, Any] = {"data": None, "expires_at": 0.0, "asset": None}

_summary_lock = Lock()

_KST = ZoneInfo("Asia/Seoul")

_DEFAULT_FUTURES_MULTIPLIER_KRW = 50_000


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


@router.get("/data-freshness")
async def get_data_freshness(
    asset_class: str = Query(default="all"),
) -> dict[str, Any]:
    """Return WebSocket tick-freshness stats per data source."""
    asset = normalize_asset_class(asset_class)
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


@router.get("/market-structure")
async def get_market_structure_health() -> dict[str, Any]:
    """Market-structure daily snapshot freshness (premarket/close publisher)."""
    summary = _market_structure_ops(_get_redis_client())
    summary["checked_at"] = datetime.now(UTC).isoformat()
    return summary


@router.get("/futures-contract")
async def get_futures_contract_health() -> dict[str, Any]:
    """Futures contract / roll-state read-model (Phase A, shadow read-only)."""
    summary = _futures_contract_ops(_get_redis_client())
    summary["checked_at"] = datetime.now(UTC).isoformat()
    return summary


@router.get("/futures-margin")
async def get_futures_margin_health() -> dict[str, Any]:
    """Futures margin-risk read-model (Phase B, shadow read-only)."""
    summary = _futures_margin_ops(_get_redis_client())
    summary["checked_at"] = datetime.now(UTC).isoformat()
    return summary


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
    market_structure = _market_structure_ops(redis)
    futures_contract = _futures_contract_ops(redis)
    futures_margin = _futures_margin_ops(redis)

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
        "market_structure": market_structure,
        "futures_contract": futures_contract,
        "futures_margin": futures_margin,
        "pipeline": pipeline_summary,
        "mode": mode_summary,
        "assets": asset_rows,
    }


@router.get("/summary")
async def get_health_summary(
    asset_class: str = Query(default="all"),
) -> dict[str, Any]:
    """Aggregated health snapshot (1s cache, keyed by asset_class)."""
    asset = normalize_asset_class(asset_class)
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
        "market_structure": ops_summary["market_structure"],
        "futures_contract": ops_summary["futures_contract"],
        "futures_margin": ops_summary["futures_margin"],
        "pipeline": ops_summary["pipeline"],
        "mode": ops_summary["mode"],
    }

    with _summary_lock:
        _summary_cache["data"] = payload
        _summary_cache["expires_at"] = now + 1.0
        _summary_cache["asset"] = asset

    return payload


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
