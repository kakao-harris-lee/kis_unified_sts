"""Unified portfolio read-only API (unified investment roadmap Phase 3D/4B).

Exposes the daily equity batch's Redis publication
(``portfolio:equity:latest`` — fixed Phase 3 contract) plus the RuntimeLedger
``portfolio_equity_daily`` history for the ``/risk`` page, and the hedge
advisor's publication (``portfolio:hedge:latest`` — fixed Phase 4 contract,
mini KOSPI200) plus the RuntimeLedger ``hedge_advice`` history for the
``/market`` hedge card. Strictly read-only: no control or execution endpoints
belong here (circuit breaker is shadow-first — 미집행; the hedge advisor is
advisory-only — 자동 주문 없음), and the ledger is opened with a read-only
SQLite connection so this route can never create or migrate schema (the batch
and advisor lanes own their tables).

Endpoints degrade gracefully: when the batch/advisor has not published yet
(key absent) the latest endpoints answer ``{"status": "unavailable"}`` and the
history endpoints return empty series when the DB or table is missing.
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

# Phase 4 publication contract (fixed): hedge advisor hash key + field names.
# 미니 KOSPI200 확정(O4). Env-overridable for operator setups only.
_HEDGE_LATEST_KEY = os.environ.get(
    "PORTFOLIO_HEDGE_LATEST_KEY", "portfolio:hedge:latest"
)
# The advisor runs with the portfolio monitor cron (08:50 / 19:00 KST,
# weekdays), so the widest weekday gap is 19:00 → next-day 08:50 (~13h50m);
# 14h covers it. Weekends need no threshold: the publication TTL (24h)
# expires the key, so the endpoint reports "unavailable" like the equity lane.
_HEDGE_STALE_SECONDS = int(os.environ.get("PORTFOLIO_HEDGE_STALE_SECONDS", "50400"))

# Phase 5 publication contract (fixed): Tier 3 watch hash key + field names.
# ``drawdown``/``trigger_threshold`` are FRACTIONS (−0.16 = −16%, Phase 3
# unit convention). Env-overridable for operator setups only.
_TIER3_WATCH_KEY = os.environ.get("PORTFOLIO_TIER3_WATCH_KEY", "portfolio:tier3:watch")
# The watch publishes on the portfolio monitor cadence (weekday cron), so the
# hedge-lane staleness reasoning applies: 14h covers the widest weekday gap
# and the publication TTL expires the key over weekends (→ "unavailable").
_TIER3_STALE_SECONDS = int(os.environ.get("PORTFOLIO_TIER3_STALE_SECONDS", "50400"))

# RuntimeLedger history table (owned by the batch lane — read-only here).
_HISTORY_TABLE = "portfolio_equity_daily"

# RuntimeLedger hedge advice table (owned by the advisor lane, ledger v4 —
# read-only here). Its exact schema is still landing, so history reads map
# candidate column names defensively (absent columns yield null fields).
_HEDGE_HISTORY_TABLE = "hedge_advice"
# Safety cap: the advice table is append-only and small, but never pull an
# unbounded row count into the API process.
_HEDGE_HISTORY_MAX_ROWS = 1000

# Candidate timestamp columns for a hedge advice row, in priority order.
_HEDGE_TIME_COLUMNS = ("asof_ts", "advised_at", "created_at", "ts", "timestamp")
_HEDGE_NUMERIC_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "recommended_short_contracts",
        ("recommended_short_contracts", "recommended_contracts"),
    ),
    ("net_beta_exposure", ("net_beta_exposure",)),
    ("beta_notional", ("beta_notional",)),
    ("futures_net_notional", ("futures_net_notional",)),
    ("residual_exposure_after", ("residual_exposure_after",)),
    ("futures_price", ("futures_price",)),
    ("score", ("score", "risk_score")),
)
_HEDGE_TEXT_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("product", ("product",)),
    ("band", ("band", "risk_band")),
    ("reason", ("reason",)),
)

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


# ---------------------------------------------------------------------------
# Hedge advisor (Phase 4B — advisory only, 자동 주문 없음)
# ---------------------------------------------------------------------------


def _coerce_int(raw: Any) -> int | None:
    value = _coerce_float(raw)
    if value is None:
        return None
    return int(value)


def _hedge_summary(redis: Any) -> dict[str, Any] | None:
    """Parse the ``portfolio:hedge:latest`` hash (fixed Phase 4 contract).

    All notional/exposure fields are KRW; ``futures_net_notional`` is signed
    (short negative). ``recommended_short_contracts`` is an integer count of
    mini KOSPI200 contracts — a recommendation only, never an order.
    """
    payload = _redis_hgetall(redis, _HEDGE_LATEST_KEY)
    if not payload:
        return None

    asof = _parse_kst_naive(payload.get("asof_ts"))
    age_s = _age_seconds(asof)
    return {
        "product": _coerce_text(payload.get("product")),
        "multiplier": _coerce_float(payload.get("multiplier")),
        "futures_price": _coerce_float(payload.get("futures_price")),
        "stock_long_notional": _coerce_float(payload.get("stock_long_notional")),
        "portfolio_beta": _coerce_float(payload.get("portfolio_beta")),
        "beta_notional": _coerce_float(payload.get("beta_notional")),
        "futures_net_contracts": _coerce_float(payload.get("futures_net_contracts")),
        "futures_net_notional": _coerce_float(payload.get("futures_net_notional")),
        "net_beta_exposure": _coerce_float(payload.get("net_beta_exposure")),
        "recommended_short_contracts": _coerce_int(
            payload.get("recommended_short_contracts")
        ),
        "residual_exposure_after": _coerce_float(
            payload.get("residual_exposure_after")
        ),
        "band": _coerce_text(payload.get("band")),
        "score": _coerce_float(payload.get("score")),
        "advisory_active": _coerce_bool(payload.get("advisory_active")) or False,
        "reason": _coerce_text(payload.get("reason")),
        "degraded": _coerce_bool(payload.get("degraded")) or False,
        "missing_components": _parse_json_list(payload.get("missing_components")),
        "asof": asof.isoformat() if asof else None,
        "age_s": age_s,
        "stale": age_s is not None and age_s > _HEDGE_STALE_SECONDS,
    }


@router.get("/hedge")
async def get_portfolio_hedge() -> dict[str, Any]:
    """Latest hedge advisor snapshot (mini KOSPI200 — 권고 전용).

    ``status`` is ``unavailable`` when the advisor has not published
    ``portfolio:hedge:latest`` yet, ``degraded`` when the advisor flags
    missing components, ``stale`` when publication age exceeds the threshold,
    and ``ok`` otherwise. Read-only and advisory-only — this API exposes no
    order or execution controls, ever.
    """
    hedge = _hedge_summary(_get_redis_client())

    if hedge is None:
        status = "unavailable"
    elif hedge["degraded"]:
        status = "degraded"
    elif hedge["stale"]:
        status = "stale"
    else:
        status = "ok"

    return {
        "status": status,
        "checked_at": datetime.now(UTC).isoformat(),
        "source": _HEDGE_LATEST_KEY,
        # 권고 전용 — 자동 주문 없음 (roadmap §5.4). Fixed marker for the UI.
        "advisory_only": True,
        "hedge": hedge,
    }


def _read_hedge_rows(db_path: Path) -> list[Any]:
    """Read recent hedge advice rows via a read-only SQLite URI connection.

    ``mode=ro`` guarantees this route can never write or create schema — the
    ``hedge_advice`` table is owned by the advisor lane (ledger v4). A missing
    table (advisor not landed yet) degrades to an empty list. Rows come newest
    first (rowid) under a hard cap; windowing happens in Python because the
    landing schema's timestamp column name is not finalized.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            f"SELECT * FROM {_HEDGE_HISTORY_TABLE} "  # noqa: S608 - fixed table
            "ORDER BY rowid DESC LIMIT ?",
            (_HEDGE_HISTORY_MAX_ROWS,),
        )
        return cursor.fetchall()
    except sqlite3.OperationalError:
        # Table absent (advisor not deployed yet) → empty series.
        return []
    finally:
        conn.close()


def _hedge_row_asof(row: Any, available: set[str]) -> datetime | None:
    for column in _HEDGE_TIME_COLUMNS:
        if column in available:
            asof = _parse_kst_naive(row[column])
            if asof is not None:
                return asof
    # Date-only fallback (some ledger tables key on trade_date).
    if "trade_date" in available:
        return _parse_kst_naive(row["trade_date"])
    return None


def _hedge_history_point(row: Any, available: set[str]) -> dict[str, Any] | None:
    asof = _hedge_row_asof(row, available)
    if asof is None:
        # Rows without a parseable timestamp cannot be placed in the window.
        return None
    point: dict[str, Any] = {
        "asof": asof.isoformat(),
        "trade_date": asof.date().isoformat(),
    }
    for field, candidates in _HEDGE_NUMERIC_FIELDS:
        point[field] = _coerce_float(_first_present(row, candidates, available))
    point["recommended_short_contracts"] = _coerce_int(
        point["recommended_short_contracts"]
    )
    for field, candidates in _HEDGE_TEXT_FIELDS:
        point[field] = _coerce_text(_first_present(row, candidates, available))
    advisory = _first_present(row, ("advisory_active", "active"), available)
    point["advisory_active"] = _coerce_bool(advisory)
    return point


@router.get("/hedge/history")
async def get_portfolio_hedge_history(
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    """Recent hedge advice time series for the /market hedge card.

    Reads the RuntimeLedger ``hedge_advice`` table (advisor lane, ledger v4).
    Absent DB, table, or columns degrade to empty/null series. Read-only —
    the connection is opened with ``mode=ro`` so no schema is ever created
    here, and no execution controls exist on this surface.
    """
    now = datetime.now(KST)
    end = now.date()
    start = (now - timedelta(days=days)).date()
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
        rows = _read_hedge_rows(db_path)
    except Exception:  # noqa: BLE001 - history is best-effort
        logger.debug("hedge advice history query failed", exc_info=True)
        return empty

    window_start = now - timedelta(days=days)
    points: list[dict[str, Any]] = []
    for row in rows:
        available = set(row.keys())
        point = _hedge_history_point(row, available)
        if point is None:
            continue
        asof = _parse_kst_naive(point["asof"])
        if asof is None or asof < window_start:
            continue
        points.append(point)
    if not points:
        return empty

    points.sort(key=lambda p: p["asof"])
    return {
        "status": "ok",
        "days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "count": len(points),
        "points": points,
    }


# ---------------------------------------------------------------------------
# Track A core (Phase 5E — Tier 3 watch + core holdings / Kill Criteria)
# ---------------------------------------------------------------------------
# 수동 트랙 — 자동 매매 없음: this surface is display-only and exposes no
# trade, order, or ledger-mutation controls, ever. The Tier 3 watch (Redis)
# and the core holdings config (YAML loader — Phase 5A lane) degrade
# independently: either side may be absent without breaking the endpoint.


def _load_core_holdings():
    """Track A core holdings via the Phase 5A loader; None when unavailable.

    The loader module (``shared/portfolio/core_holdings.py``) is landing in a
    parallel lane and may not exist yet — an import failure degrades to None
    (Phase 2E gate-section pattern), as does any load failure.
    """
    try:
        from shared.portfolio.core_holdings import CoreHoldings
    except Exception:  # noqa: BLE001 - loader lane may not have landed yet
        return None
    try:
        return CoreHoldings.load_or_default()
    except Exception:  # noqa: BLE001 - malformed YAML degrades to null
        return None


def _tier3_summary(redis: Any) -> dict[str, Any] | None:
    """Parse the ``portfolio:tier3:watch`` hash (fixed Phase 5 contract).

    ``drawdown`` and ``trigger_threshold`` pass through as FRACTIONS (≤ 0;
    −0.16 = −16%) — the UI multiplies by 100 for display. ``triggered`` is
    the watch lane's own verdict ("true"/"false"); it is never re-derived
    here from drawdown vs threshold.
    """
    payload = _redis_hgetall(redis, _TIER3_WATCH_KEY)
    if not payload:
        return None

    asof = _parse_kst_naive(payload.get("asof_ts"))
    age_s = _age_seconds(asof)
    return {
        "kospi_close": _coerce_float(payload.get("kospi_close")),
        "kospi_peak": _coerce_float(payload.get("kospi_peak")),
        "drawdown": _coerce_float(payload.get("drawdown")),
        "trigger_threshold": _coerce_float(payload.get("trigger_threshold")),
        "triggered": _coerce_bool(payload.get("triggered")) or False,
        "asof": asof.isoformat() if asof else None,
        "age_s": age_s,
        "stale": age_s is not None and age_s > _TIER3_STALE_SECONDS,
    }


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` off an attribute object or mapping (loader-agnostic)."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _kill_criteria_list(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    return [text for item in raw if (text := _coerce_text(item)) is not None]


def _last_valuation_summary(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    date = _coerce_text(_attr(raw, "date"))
    price = _coerce_float(_attr(raw, "price"))
    if date is None and price is None:
        return None
    return {"date": date, "price": price}


def _sector_label(config: Any, sector: str | None) -> str | None:
    if sector is None:
        return None
    sectors = _attr(config, "sectors") or {}
    spec = sectors.get(sector) if isinstance(sectors, dict) else None
    if spec is None:
        return sector
    return _coerce_text(_attr(spec, "label")) or sector


def _holding_summary(config: Any, holding: Any) -> dict[str, Any]:
    """Serialize one holding; valuation = shares × (last valuation ∥ 평단)."""
    sector = _coerce_text(_attr(holding, "sector"))
    shares = _coerce_float(_attr(holding, "shares"))
    avg_price = _coerce_float(_attr(holding, "avg_price"))
    last_valuation = _last_valuation_summary(_attr(holding, "last_valuation"))
    price = last_valuation["price"] if last_valuation else None
    if price is None:
        price = avg_price
    valuation = shares * price if shares is not None and price is not None else None
    return {
        "symbol": _coerce_text(_attr(holding, "symbol")),
        "name": _coerce_text(_attr(holding, "name")),
        "sector": sector,
        "sector_label": _sector_label(config, sector),
        "thesis": _coerce_text(_attr(holding, "thesis")),
        "kill_criteria": _kill_criteria_list(_attr(holding, "kill_criteria")),
        "shares": shares,
        "avg_price": avg_price,
        "last_valuation": last_valuation,
        "valuation": valuation,
        "weight": None,  # filled once the holdings total is known
    }


def _candidate_summary(config: Any, candidate: Any) -> dict[str, Any]:
    sector = _coerce_text(_attr(candidate, "sector"))
    return {
        "symbol": _coerce_text(_attr(candidate, "symbol")),
        "name": _coerce_text(_attr(candidate, "name")),
        "sector": sector,
        "sector_label": _sector_label(config, sector),
        "thesis": _coerce_text(_attr(candidate, "thesis")),
        "kill_criteria": _kill_criteria_list(_attr(candidate, "kill_criteria")),
    }


def _holdings_summary(config: Any) -> list[dict[str, Any]]:
    """Serialize holdings with weight = valuation share of the holdings total."""
    holdings = [
        _holding_summary(config, holding)
        for holding in (_attr(config, "holdings") or [])
    ]
    total = sum(h["valuation"] for h in holdings if h["valuation"] is not None)
    if total > 0:
        for holding in holdings:
            if holding["valuation"] is not None:
                holding["weight"] = holding["valuation"] / total
    return holdings


def _actual_sector_weights(config: Any) -> dict[str, float]:
    """실비중 from the loader's ``sector_weights()``; {} on any failure."""
    try:
        weights = config.sector_weights()
    except Exception:  # noqa: BLE001 - display-only, degrade to unknown
        return {}
    if not isinstance(weights, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in weights.items():
        coerced = _coerce_float(value)
        if coerced is not None:
            out[str(key)] = coerced
    return out


def _sectors_summary(config: Any) -> dict[str, dict[str, Any]]:
    """Target vs actual weight per configured sector (fractions)."""
    actual = _actual_sector_weights(config)
    sectors = _attr(config, "sectors") or {}
    if not isinstance(sectors, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, spec in sectors.items():
        name = str(key)
        out[name] = {
            "label": _coerce_text(_attr(spec, "label")) or name,
            "target_weight": _coerce_float(_attr(spec, "target_weight")),
            "actual_weight": actual.get(name),
        }
    return out


def _rebalancing_summary(config: Any) -> dict[str, Any] | None:
    rebalancing = _attr(config, "rebalancing")
    if rebalancing is None:
        return None
    return {
        "drift_threshold_pct": _coerce_float(_attr(rebalancing, "drift_threshold_pct")),
        "single_holding_max": _coerce_float(_attr(rebalancing, "single_holding_max")),
    }


@router.get("/core")
async def get_portfolio_core() -> dict[str, Any]:
    """Tier 3 watch + Track A core holdings (Kill Criteria) — display only.

    ``status`` reflects the Tier 3 watch publication (``unavailable`` when the
    watch key is absent, ``stale`` when old, ``ok`` otherwise); the holdings
    side degrades independently (loader unavailable → empty holdings and null
    sectors/rebalancing). 수동 트랙 — 자동 매매 없음: no trade controls exist
    on this surface, and drawdown/weights are fractions (UI converts to %).
    """
    tier3 = _tier3_summary(_get_redis_client())
    config = _load_core_holdings()

    if tier3 is None:
        status = "unavailable"
    elif tier3["stale"]:
        status = "stale"
    else:
        status = "ok"

    return {
        "status": status,
        "checked_at": datetime.now(UTC).isoformat(),
        "source": _TIER3_WATCH_KEY,
        # 수동 트랙 — 자동 매매 없음 (roadmap §5.3). Fixed marker for the UI.
        "manual_track": True,
        "tier3": tier3,
        "holdings": _holdings_summary(config) if config is not None else [],
        "candidates": (
            [
                _candidate_summary(config, candidate)
                for candidate in (_attr(config, "candidates") or [])
            ]
            if config is not None
            else []
        ),
        "sectors": _sectors_summary(config) if config is not None else None,
        "rebalancing": _rebalancing_summary(config) if config is not None else None,
    }
