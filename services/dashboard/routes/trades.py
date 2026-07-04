"""Trades endpoints.

This module is the FastAPI route facade. Implementation details live in focused
route-adjacent modules so existing imports from ``services.dashboard.routes.trades``
remain stable while the heavy ledger and lifecycle helpers stay isolated.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Query

from services.dashboard.domain.assets import normalize_asset_class, target_assets
from services.dashboard.routes import trades_lifecycle as _lifecycle_helpers
from services.dashboard.routes.trades_data import (
    _empty_db_stats,
    _get_reader,
    _get_runtime_ledger,
    _ledger_trade_to_closed_dict,
    _load_runtime_ledger_fills,
    _load_runtime_ledger_trades,
    _load_trades,
    _parse_optional_tz_aware,
    _parse_tz_aware,
    _statistics_from_trade_dicts,
    _to_trade_response,
)
from services.dashboard.routes.trades_lifecycle import (
    _build_lifecycle_response,
    _empty_lifecycle_rows,
    _load_lifecycle_redis_rows,
)
from services.dashboard.routes.trades_models import (
    LifecycleStep,
    StrategyPerformance,
    TradeLifecycleResponse,
    TradeListResponse,
    TradeResponse,
    TradeStatistics,
)

router = APIRouter(prefix="/api/trades", tags=["trades"])

__all__ = [
    "LifecycleStep",
    "StrategyPerformance",
    "TradeLifecycleResponse",
    "TradeListResponse",
    "TradeResponse",
    "TradeStatistics",
    "_build_lifecycle_response",
    "_empty_db_stats",
    "_empty_lifecycle_rows",
    "_get_reader",
    "_get_runtime_ledger",
    "_ledger_trade_to_closed_dict",
    "_load_lifecycle_ledger_rows",
    "_load_lifecycle_redis_rows",
    "_load_runtime_ledger_fills",
    "_load_runtime_ledger_trades",
    "_load_trades",
    "_parse_optional_tz_aware",
    "_parse_tz_aware",
    "_statistics_from_trade_dicts",
    "get_db_closed_statistics",
    "get_db_closed_trades",
    "get_recent_fills",
    "get_trade_lifecycle",
    "get_trade_statistics",
    "get_trades",
    "get_trades_by_strategy",
    "router",
]


def _load_lifecycle_ledger_rows(
    asset_class: str,
    *,
    symbol: str | None = None,
    signal_id: str | None = None,
    order_id: str | None = None,
    fill_id: str | None = None,
    trade_id: str | None = None,
    position_id: str | None = None,
    allow_symbol_lookup: bool = True,
    limit: int = 500,
    ledger: Any | None = None,
) -> tuple[dict[str, list[dict]], bool]:
    """Compatibility wrapper that keeps facade-level monkeypatches effective."""
    owns_ledger = ledger is None
    active_ledger = ledger or _get_runtime_ledger()
    if active_ledger is None:
        return _empty_lifecycle_rows(), False
    try:
        return _lifecycle_helpers._load_lifecycle_ledger_rows(
            asset_class,
            symbol=symbol,
            signal_id=signal_id,
            order_id=order_id,
            fill_id=fill_id,
            trade_id=trade_id,
            position_id=position_id,
            allow_symbol_lookup=allow_symbol_lookup,
            limit=limit,
            ledger=active_ledger,
        )
    finally:
        if owns_ledger:
            active_ledger.close()


@router.get("", response_model=TradeListResponse)
async def get_trades(
    strategy: str | None = Query(None, description="Filter by strategy"),
    symbol: str | None = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=100, description="Number of trades"),
    page: int = Query(1, ge=1, description="Page number"),
    asset_class: str = Query(default="futures"),
):
    """Get list of trades with optional filters."""
    asset = normalize_asset_class(asset_class)
    ledger_rows, ledger_available = _load_runtime_ledger_trades(
        asset,
        strategy=strategy,
        symbol=symbol,
        limit=max(limit * page, limit),
    )
    using_ledger = ledger_available
    if using_ledger:
        raw_by_asset = [
            (str(trade.get("asset_class") or asset), trade) for trade in ledger_rows
        ]
    else:
        raw_by_asset = [
            (target, trade)
            for target in target_assets(asset)
            for trade in _load_trades(target)
        ]
    trades = [_to_trade_response(t, target) for target, t in raw_by_asset]
    trades = [t for t in trades if t is not None]
    trades.sort(key=lambda t: t.exit_time, reverse=True)

    if strategy and not using_ledger:
        trades = [t for t in trades if t.strategy == strategy]
    if symbol and not using_ledger:
        trades = [t for t in trades if t.symbol == symbol]

    total = len(trades)
    start = (page - 1) * limit
    end = start + limit
    paginated = trades[start:end]

    return TradeListResponse(trades=paginated, total=total, page=page, limit=limit)


@router.get("/statistics", response_model=TradeStatistics)
async def get_trade_statistics():
    """Get overall trade statistics."""
    asset = normalize_asset_class(os.environ.get("TRADING_ASSET_CLASS", "stock"))
    ledger_rows, ledger_available = _load_runtime_ledger_trades(asset)
    raw = ledger_rows if ledger_available else _load_trades(asset)
    trades = [
        _to_trade_response(
            t, t.get("asset_class", asset) if isinstance(t, dict) else asset
        )
        for t in raw
    ]
    trades = [t for t in trades if t is not None]

    if not trades:
        return TradeStatistics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            avg_pnl=0.0,
            max_win=0.0,
            max_loss=0.0,
            profit_factor=0.0,
        )

    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl < 0]
    total_pnl = sum(t.pnl for t in trades)
    gross_profit = sum(t.pnl for t in winning) if winning else 0
    gross_loss = abs(sum(t.pnl for t in losing)) if losing else 0

    return TradeStatistics(
        total_trades=len(trades),
        winning_trades=len(winning),
        losing_trades=len(losing),
        win_rate=len(winning) / len(trades) * 100 if trades else 0,
        total_pnl=total_pnl,
        avg_pnl=total_pnl / len(trades) if trades else 0,
        max_win=max((t.pnl for t in trades), default=0),
        max_loss=min((t.pnl for t in trades), default=0),
        profit_factor=gross_profit / gross_loss if gross_loss > 0 else 0,
    )


@router.get("/by-strategy", response_model=list[StrategyPerformance])
async def get_trades_by_strategy(
    asset_class: str | None = Query(default=None, description="stock, futures, or all"),
):
    """Get trade performance grouped by strategy."""
    asset = normalize_asset_class(
        asset_class or os.environ.get("TRADING_ASSET_CLASS", "stock")
    )
    ledger_rows, ledger_available = _load_runtime_ledger_trades(asset)
    if ledger_available:
        raw = ledger_rows
    else:
        raw = []
        for target in target_assets(asset):
            raw.extend(_load_trades(target))
    trades = [
        _to_trade_response(
            t, t.get("asset_class", asset) if isinstance(t, dict) else asset
        )
        for t in raw
    ]
    trades = [t for t in trades if t is not None]

    strategy_trades: dict[str, list[TradeResponse]] = {}
    for trade in trades:
        if trade.strategy not in strategy_trades:
            strategy_trades[trade.strategy] = []
        strategy_trades[trade.strategy].append(trade)

    results = []
    for strat, strades in strategy_trades.items():
        winning = len([t for t in strades if t.pnl > 0])
        total_pnl = sum(t.pnl for t in strades)
        results.append(
            StrategyPerformance(
                strategy=strat,
                trades=len(strades),
                win_rate=winning / len(strades) * 100 if strades else 0,
                total_pnl=total_pnl,
                avg_pnl=total_pnl / len(strades) if strades else 0,
            )
        )

    return results


@router.get("/lifecycle", response_model=TradeLifecycleResponse)
async def get_trade_lifecycle(
    signal_id: str | None = Query(None, description="Filter by signal id"),
    order_id: str | None = Query(None, description="Filter by order id"),
    fill_id: str | None = Query(None, description="Filter by fill id"),
    trade_id: str | None = Query(None, description="Filter by closed trade id"),
    symbol: str | None = Query(None, description="Filter by symbol/code"),
    asset_class: str = Query(default="futures"),
) -> TradeLifecycleResponse:
    """Return a read-only signal/order/fill/trade lifecycle timeline."""
    asset = normalize_asset_class(asset_class)
    ledger_rows, ledger_available = _load_lifecycle_ledger_rows(
        asset,
        symbol=symbol,
        signal_id=signal_id,
        order_id=order_id,
        fill_id=fill_id,
        trade_id=trade_id,
    )
    redis_rows = _load_lifecycle_redis_rows(asset, symbol=symbol)
    return _build_lifecycle_response(
        asset_class=asset,
        signal_id=signal_id,
        order_id=order_id,
        fill_id=fill_id,
        trade_id=trade_id,
        symbol=symbol,
        ledger_rows=ledger_rows,
        redis_rows=redis_rows,
        ledger_available=ledger_available,
    )


@router.get("/closed/statistics")
async def get_db_closed_statistics(
    asset_class: str = Query("futures"),
    strategy: str | None = Query(None),
):
    """Aggregate statistics from RuntimeLedger."""
    asset_class = normalize_asset_class(asset_class)
    ledger_rows, ledger_available = _load_runtime_ledger_trades(
        asset_class,
        strategy=strategy,
        limit=10_000,
    )
    if ledger_available:
        return _statistics_from_trade_dicts(ledger_rows)
    return _empty_db_stats()


@router.get("/fills")
async def get_recent_fills(
    asset_class: str = Query(default="futures"),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict:
    """Recent order fills from RuntimeLedger."""
    asset = normalize_asset_class(asset_class)
    ledger_fills, ledger_available = _load_runtime_ledger_fills(asset, limit=limit)
    if ledger_available:
        return {"fills": ledger_fills}
    return {"fills": []}


@router.get("/closed")
async def get_db_closed_trades(
    asset_class: str = Query("futures"),
    strategy: str | None = Query(None),
    code: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Recent closed trades from RuntimeLedger."""
    asset_class = normalize_asset_class(asset_class)
    ledger_rows, ledger_available = _load_runtime_ledger_trades(
        asset_class,
        strategy=strategy,
        symbol=code,
        limit=limit,
    )
    if ledger_available:
        return [_ledger_trade_to_closed_dict(row) for row in ledger_rows]
    return []
