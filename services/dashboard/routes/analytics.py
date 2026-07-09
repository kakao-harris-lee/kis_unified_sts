"""Portfolio analytics for dashboard charts (read-only).

- strategy-correlation: pairwise correlation of per-strategy daily PnL series
  (false-diversification check — strategies that crash together).
- exposure-history: per-day gross exposure by symbol from position snapshots
  (concentration-over-time / stacked-area).

No control/execution endpoints. Degrades to empty when the ledger or data is
absent — never 500s on missing history.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from services.dashboard.domain.assets import normalize_asset_class
from services.dashboard.routes.trades_data import _get_runtime_ledger

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


def _day(value: Any) -> str | None:
    """Extract a YYYY-MM-DD day key from an ISO timestamp string."""
    if not value:
        return None
    return str(value)[:10]


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pearson(a: list[float], b: list[float]) -> float | None:
    """Pearson correlation of two equal-length series; None if undefined."""
    n = len(a)
    if n < 2:
        return None
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if var_a <= 0 or var_b <= 0:
        return None
    return round(cov / (var_a**0.5 * var_b**0.5), 4)


@router.get("/strategy-correlation")
async def strategy_correlation(
    asset_class: str = Query(default="all"),
    days: int = Query(default=90, ge=7, le=365),
) -> dict[str, Any]:
    """Pairwise correlation matrix of per-strategy daily PnL over the window."""
    asset = normalize_asset_class(asset_class)
    end = datetime.now(KST).date()
    start = end - timedelta(days=days)
    empty = {
        "status": "empty",
        "strategies": [],
        "matrix": [],
        "days": days,
    }

    ledger = _get_runtime_ledger()
    if ledger is None:
        return empty
    try:
        filters: dict[str, Any] = {
            "start": start.isoformat(),
            "end": end.isoformat() + "T23:59:59",
            "limit": 5000,
        }
        if asset != "all":
            filters["asset_class"] = asset
        trades = ledger.query_trades(filters)
    except Exception:  # noqa: BLE001 - analytics is best-effort
        logger.debug("strategy-correlation query failed", exc_info=True)
        return empty

    # strategy -> {day -> summed pnl}
    by_strategy: dict[str, dict[str, float]] = {}
    all_days: set[str] = set()
    for t in trades:
        strat = str(t.get("strategy") or "unknown")
        day = _day(t.get("exit_time") or t.get("exit_date"))
        pnl = _to_float(t.get("pnl"))
        if day is None or pnl is None:
            continue
        by_strategy.setdefault(strat, {})
        by_strategy[strat][day] = by_strategy[strat].get(day, 0.0) + pnl
        all_days.add(day)

    strategies = sorted(s for s, series in by_strategy.items() if len(series) >= 2)
    if len(strategies) < 2:
        return {**empty, "status": "insufficient_data"}

    days_sorted = sorted(all_days)
    # Align each strategy to the full day axis (missing day → 0 pnl).
    series = {s: [by_strategy[s].get(d, 0.0) for d in days_sorted] for s in strategies}
    matrix = [
        [
            (1.0 if i == j else _pearson(series[si], series[sj]))
            for j, sj in enumerate(strategies)
        ]
        for i, si in enumerate(strategies)
    ]
    return {
        "status": "ok",
        "strategies": strategies,
        "matrix": matrix,
        "days": days,
    }


@router.get("/exposure-history")
async def exposure_history(
    asset_class: str = Query(default="all"),
    days: int = Query(default=60, ge=7, le=365),
) -> dict[str, Any]:
    """Per-day gross exposure by symbol from daily position snapshots."""
    asset = normalize_asset_class(asset_class)
    end = datetime.now(KST).date()
    start = end - timedelta(days=days)
    empty = {"status": "empty", "symbols": [], "points": [], "days": days}

    ledger = _get_runtime_ledger()
    if ledger is None:
        return empty
    try:
        snapshots = ledger.query_position_snapshots_daily(
            None if asset == "all" else asset,
            start=start.isoformat(),
            end=end.isoformat(),
        )
    except Exception:  # noqa: BLE001 - analytics is best-effort
        logger.debug("exposure-history query failed", exc_info=True)
        return empty

    # day -> {symbol -> gross exposure (|qty| * price)}
    by_day: dict[str, dict[str, float]] = {}
    symbols: set[str] = set()
    for snap in snapshots:
        day = _day(snap.get("snapshot_time"))
        symbol = str(snap.get("symbol") or snap.get("code") or "")
        qty = _to_float(snap.get("quantity")) or 0.0
        price = _to_float(snap.get("current_price")) or _to_float(
            snap.get("entry_price")
        )
        if day is None or not symbol or price is None:
            continue
        exposure = abs(qty) * price
        by_day.setdefault(day, {})
        by_day[day][symbol] = by_day[day].get(symbol, 0.0) + exposure
        symbols.add(symbol)

    if not by_day:
        return empty

    symbols_sorted = sorted(symbols)
    points = [
        {
            "trade_date": day,
            **{sym: round(by_day[day].get(sym, 0.0), 2) for sym in symbols_sorted},
        }
        for day in sorted(by_day)
    ]
    return {
        "status": "ok",
        "symbols": symbols_sorted,
        "points": points,
        "days": days,
    }
