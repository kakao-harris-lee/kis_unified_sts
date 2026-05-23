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

from fastapi import APIRouter, Query

from services.dashboard.routes.trading import _normalize_asset_class

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])

# ---------------------------------------------------------------------------
# Process health
# ---------------------------------------------------------------------------

_PID_FILES: dict[str, Path] = {
    "futures": Path("/home/deploy/project/kis_unified_sts/pids/rl_paper.pid"),
    "stock": Path("/home/deploy/project/kis_unified_sts/pids/stock_paper.pid"),
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
    "clickhouse_insert_fail_rate_high",
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


def _today_pnl_krw(asset: str) -> int:
    """Today's realized PnL in KRW for the selected asset view.

    Futures ``rl_trades.pnl`` is stored in index points and converted by the
    configured contract multiplier. Stock ``stock_trades.pnl`` is already KRW.
    Returns 0 on failure so the Cockpit stays available if ClickHouse is down.
    """
    try:
        from clickhouse_driver import Client as SyncClient

        from shared.db.config import ClickHouseConfig

        cfg = ClickHouseConfig.from_env()
        client = SyncClient(
            host=cfg.host, port=cfg.port, user=cfg.user, password=cfg.password
        )
        try:
            queries: list[tuple[str, dict]] = []
            if asset in ("futures", "all"):
                queries.append(
                    (
                        "SELECT sum(pnl * 50000) FROM kospi.rl_trades "
                        "WHERE asset_class = 'futures' "
                        "AND toDate(exit_date, 'Asia/Seoul') = toDate(now(), 'Asia/Seoul')",
                        {},
                    )
                )
            if asset in ("stock", "all"):
                queries.append(
                    (
                        "SELECT sum(pnl) FROM market.stock_trades "
                        "WHERE toDate(exit_date, 'Asia/Seoul') = toDate(now(), 'Asia/Seoul')",
                        {},
                    )
                )

            total = 0
            for query, params in queries:
                result = client.execute(query, params)
                total += int(result[0][0] or 0) if result else 0
            return total
        finally:
            client.disconnect()
    except Exception:  # noqa: BLE001
        return 0


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

    payload = {
        "processes": process["processes"],
        "data_sources": data["sources"],
        "kill_switch": kill,
        "today_pnl": pnl,
        "asset_class": asset,
        "checked_at": process["checked_at"],
    }

    with _summary_lock:
        _summary_cache["data"] = payload
        _summary_cache["expires_at"] = now + 1.0
        _summary_cache["asset"] = asset

    return payload


# ---------------------------------------------------------------------------
# Forecasting service health
# ---------------------------------------------------------------------------


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
