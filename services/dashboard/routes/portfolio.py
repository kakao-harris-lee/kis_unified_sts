"""Unified portfolio equity read-only API (unified investment roadmap Phase 3D).

Exposes the daily equity batch's Redis publication
(``portfolio:equity:latest`` — fixed Phase 3 contract) plus the RuntimeLedger
``portfolio_equity_daily`` history for the ``/risk`` page. Strictly read-only:
no control or execution endpoints belong here (circuit breaker is shadow-first
— 미집행), and the ledger is opened with a read-only SQLite connection so this
route can never create or migrate schema (the batch lane owns the table).

Endpoints degrade gracefully: when the batch has not published yet (key
absent) the latest endpoint answers ``{"status": "unavailable"}`` and the
history endpoint returns empty series when the DB or table is missing.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from services.dashboard.routes.market_risk import (
    KST,
    _age_seconds,
    _coerce_bool,
    _coerce_float,
    _coerce_text,
    _parse_json_list,
    _parse_kst_naive,
    _redis_hgetall,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Phase 3 publication contract (fixed): hash key + field names. The key is
# env-overridable for operator setups; the default is the agreed contract.
_EQUITY_LATEST_KEY = os.environ.get(
    "PORTFOLIO_EQUITY_LATEST_KEY", "portfolio:equity:latest"
)
# The equity batch publishes once per trading day, so the widest legitimate
# gap is Friday EOD → Monday EOD (~72h). Add slack to avoid flagging every
# weekend; override for operator setups with a different cadence.
_EQUITY_STALE_SECONDS = int(
    os.environ.get("PORTFOLIO_EQUITY_STALE_SECONDS", str(78 * 3600))
)

# RuntimeLedger history table (owned by the batch lane — read-only here).
_HISTORY_TABLE = "portfolio_equity_daily"

# History columns read off the ledger rows. Values are (output_field,
# candidate columns in priority order) — absent columns yield null series so
# the dashboard tolerates modest naming variance while the batch lane lands.
_HISTORY_NUMERIC_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("total_equity", ("total_equity", "total")),
    ("track_a_equity", ("track_a_equity",)),
    ("track_b_equity", ("track_b_equity",)),
    ("track_c_equity", ("track_c_equity",)),
    ("month_start_equity", ("month_start_equity", "month_start")),
    ("month_peak_equity", ("month_peak_equity", "month_peak")),
    ("monthly_mdd_pct", ("monthly_mdd_pct", "mdd_pct")),
)
_HISTORY_TEXT_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("stage", ("stage",)),
    ("mode", ("mode",)),
)


# ---------------------------------------------------------------------------
# Infra accessors (monkeypatched in tests)
# ---------------------------------------------------------------------------


def _get_redis_client():
    """Redis DB 1 client via the shared singleton; None on infra failure."""
    try:
        from shared.streaming.client import RedisClient

        return RedisClient.get_client()
    except Exception:  # noqa: BLE001 - dashboard must stay resilient
        return None


def _ledger_db_path() -> Path | None:
    """RuntimeLedger SQLite path from storage config; None when unavailable."""
    try:
        from shared.storage.config import StorageConfig

        config = StorageConfig.load_or_default()
        if config.runtime_storage.backend != "sqlite":
            return None
        db_path = Path(config.runtime_storage.sqlite.path)
        if not db_path.exists() or db_path.is_dir():
            return None
        return db_path
    except Exception:  # noqa: BLE001 - history degrades to empty series
        return None


def _load_portfolio_config():
    """Portfolio config (Phase 3) — read-only display source for thresholds.

    ``load_or_default`` already degrades to code defaults when the YAML file
    is absent; a malformed YAML additionally degrades to the same defaults
    here. None only when even the defaults cannot be built.
    """
    try:
        from shared.portfolio.config import PortfolioConfig
    except Exception:  # noqa: BLE001 - dashboard must stay resilient
        return None
    try:
        return PortfolioConfig.load_or_default()
    except Exception:  # noqa: BLE001 - malformed YAML → shipped defaults
        try:
            return PortfolioConfig()
        except Exception:  # noqa: BLE001
            return None


# ---------------------------------------------------------------------------
# Latest snapshot assembly
# ---------------------------------------------------------------------------


def _equity_summary(redis: Any) -> dict[str, Any] | None:
    """Parse the ``portfolio:equity:latest`` hash (fixed Phase 3 contract).

    ``track_a_equity`` publishes ``""`` while the manual core ledger is not
    recorded yet — that coerces to null so the UI can render 결측 explicitly.
    """
    payload = _redis_hgetall(redis, _EQUITY_LATEST_KEY)
    if not payload:
        return None

    asof = _parse_kst_naive(payload.get("asof_ts"))
    age_s = _age_seconds(asof)
    return {
        "total_equity": _coerce_float(payload.get("total_equity")),
        "track_a_equity": _coerce_float(payload.get("track_a_equity")),
        "track_b_equity": _coerce_float(payload.get("track_b_equity")),
        "track_c_equity": _coerce_float(payload.get("track_c_equity")),
        "month_start_equity": _coerce_float(payload.get("month_start_equity")),
        "month_peak_equity": _coerce_float(payload.get("month_peak_equity")),
        "monthly_mdd_pct": _coerce_float(payload.get("monthly_mdd_pct")),
        "stage": _coerce_text(payload.get("stage")),
        "mode": _coerce_text(payload.get("mode")),
        "degraded": _coerce_bool(payload.get("degraded")) or False,
        "missing_components": _parse_json_list(payload.get("missing_components")),
        "asof": asof.isoformat() if asof else None,
        "age_s": age_s,
        "stale": age_s is not None and age_s > _EQUITY_STALE_SECONDS,
    }


def _stages_summary() -> dict[str, Any] | None:
    """MDD stage thresholds + breaker mode from ``config/portfolio.yaml``.

    Display-only: the dashboard never mutates the breaker mode. None when the
    portfolio module is unavailable so the UI falls back to static labels.
    """
    config = _load_portfolio_config()
    if config is None:
        return None
    stages = config.circuit_breaker.monthly_mdd_stages
    return {
        "mode": config.circuit_breaker.mode,
        "reduce": {
            "threshold": stages.reduce.threshold,
            "new_entry_size_factor": stages.reduce.new_entry_size_factor,
        },
        "halt_new": {"threshold": stages.halt_new.threshold},
        "full_stop": {"threshold": stages.full_stop.threshold},
    }


@router.get("/equity")
async def get_portfolio_equity() -> dict[str, Any]:
    """Latest unified equity snapshot + MDD stage thresholds.

    ``status`` is ``unavailable`` when the batch has not published
    ``portfolio:equity:latest`` yet, ``degraded`` when the batch flags missing
    components, ``stale`` when publication age exceeds the threshold, and
    ``ok`` otherwise. Read-only — this API never mutates runtime state.
    """
    equity = _equity_summary(_get_redis_client())

    if equity is None:
        status = "unavailable"
    elif equity["degraded"]:
        status = "degraded"
    elif equity["stale"]:
        status = "stale"
    else:
        status = "ok"

    return {
        "status": status,
        "checked_at": datetime.now(UTC).isoformat(),
        "source": _EQUITY_LATEST_KEY,
        "equity": equity,
        "stages": _stages_summary(),
    }


# ---------------------------------------------------------------------------
# History (RuntimeLedger daily rows — read-only connection)
# ---------------------------------------------------------------------------


def _read_history_rows(db_path: Path, start_iso: str, end_iso: str) -> list[Any]:
    """Read daily rows via a read-only SQLite URI connection.

    ``mode=ro`` guarantees this route can never write or create schema — the
    ``portfolio_equity_daily`` table is owned by the equity batch lane. A
    missing table (batch not landed yet) degrades to an empty list.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            f"SELECT * FROM {_HISTORY_TABLE} "  # noqa: S608 - fixed table name
            "WHERE trade_date >= ? AND trade_date <= ? ORDER BY trade_date ASC",
            (start_iso, end_iso),
        )
        return cursor.fetchall()
    except sqlite3.OperationalError:
        # Table absent (batch not deployed yet) → empty series.
        return []
    finally:
        conn.close()


def _first_present(row: Any, columns: tuple[str, ...], available: set[str]) -> Any:
    for column in columns:
        if column in available:
            value = row[column]
            if value is not None:
                return value
    return None


def _history_point(row: Any, available: set[str]) -> dict[str, Any]:
    point: dict[str, Any] = {
        "trade_date": (
            _coerce_text(row["trade_date"]) if "trade_date" in available else None
        ),
    }
    for field, candidates in _HISTORY_NUMERIC_FIELDS:
        point[field] = _coerce_float(_first_present(row, candidates, available))
    for field, candidates in _HISTORY_TEXT_FIELDS:
        point[field] = _coerce_text(_first_present(row, candidates, available))
    return point


@router.get("/equity/history")
async def get_portfolio_equity_history(
    days: int = Query(default=90, ge=1, le=730),
) -> dict[str, Any]:
    """Daily unified-equity time series for the /risk charts.

    Reads the RuntimeLedger ``portfolio_equity_daily`` table (one row per
    trading day; the last row wins on duplicate dates). Absent DB, table, or
    columns degrade to empty/null series. Read-only — the connection is
    opened with ``mode=ro`` so no schema is ever created here.
    """
    end = datetime.now(KST).date()
    start = end - timedelta(days=days)
    empty: dict[str, Any] = {
        "status": "empty",
        "days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "count": 0,
        "points": [],
    }

    db_path = _ledger_db_path()
    if db_path is None:
        return empty
    try:
        rows = _read_history_rows(db_path, start.isoformat(), end.isoformat())
    except Exception:  # noqa: BLE001 - history is best-effort
        logger.debug("portfolio equity history query failed", exc_info=True)
        return empty
    if not rows:
        return empty

    # Keep one point per trade_date (last row wins) to stay one-per-day even
    # if the batch ever double-writes a date.
    by_date: dict[str, dict[str, Any]] = {}
    for row in rows:
        available = set(row.keys())
        point = _history_point(row, available)
        key = point["trade_date"] or ""
        by_date[key] = point
    points = [by_date[key] for key in sorted(by_date)]

    return {
        "status": "ok",
        "days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "count": len(points),
        "points": points,
    }
