"""Trades endpoints."""

import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel

from services.dashboard.routes.trading import _normalize_asset_class, _target_assets
from shared.exceptions import InfrastructureError
from shared.storage.config import StorageConfig
from shared.storage.runtime_ledger import RuntimeLedgerError, SQLiteRuntimeLedger


def _parse_tz_aware(value: str | None) -> datetime:
    """Parse an ISO timestamp into tz-aware UTC, or fall back to now(UTC).

    Same convention as services/dashboard/routes/signals.py — the dashboard
    emits tz-aware UTC throughout so downstream comparisons (statistics,
    history, etc.) never hit "can't compare offset-naive and offset-aware".
    """
    if value is None:
        return datetime.now(UTC)
    try:
        ts = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.now(UTC)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


router = APIRouter(prefix="/api/trades", tags=["trades"])


class TradeResponse(BaseModel):
    """Trade response model."""

    id: str
    asset_class: str
    symbol: str
    side: str
    quantity: int
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    strategy: str
    entry_time: datetime
    exit_time: datetime


class TradeListResponse(BaseModel):
    """Trade list response."""

    trades: list[TradeResponse]
    total: int
    page: int
    limit: int


class TradeStatistics(BaseModel):
    """Trade statistics."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    max_win: float
    max_loss: float
    profit_factor: float


class StrategyPerformance(BaseModel):
    """Per-strategy performance."""

    strategy: str
    trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float


def _get_reader(asset_class: str | None = None):
    from shared.streaming.trading_state import TradingStateReader

    asset = asset_class or os.environ.get("TRADING_ASSET_CLASS", "stock")
    return TradingStateReader(asset)


def _load_trades(asset_class: str) -> list[dict]:
    """Load all trades from Redis."""
    try:
        reader = _get_reader(asset_class)
        return reader.get_trades(start=0, count=500)
    except InfrastructureError:
        # Redis unavailable - return empty list
        return []


def _get_runtime_ledger() -> SQLiteRuntimeLedger | None:
    """Return dashboard runtime ledger reader when an existing SQLite DB is configured."""
    try:
        config = StorageConfig.load_or_default()
        if config.dashboard.trade_stats_source != "runtime_ledger":
            return None
        if config.runtime_storage.backend != "sqlite":
            return None
        path = Path(config.runtime_storage.sqlite.path)
        if not path.exists() or path.is_dir():
            return None
        return SQLiteRuntimeLedger(config.runtime_storage.sqlite)
    except Exception:
        return None


def _ledger_row_to_trade_dict(row: dict) -> dict:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    asset_class = row.get("asset_class") or payload.get("asset_class") or "unknown"
    symbol = row.get("symbol") or payload.get("code") or payload.get("symbol") or ""
    return {
        "id": row.get("id") or payload.get("id") or payload.get("trade_id") or "",
        "asset_class": asset_class,
        "symbol": symbol,
        "code": symbol,
        "name": row.get("name") or payload.get("name") or "",
        "side": row.get("side") or payload.get("side") or "long",
        "quantity": row.get("quantity") or payload.get("quantity") or 0,
        "entry_price": row.get("entry_price") or payload.get("entry_price") or 0.0,
        "exit_price": row.get("exit_price") or payload.get("exit_price") or 0.0,
        "pnl": row.get("pnl") or payload.get("pnl") or 0.0,
        "pnl_pct": row.get("pnl_pct") or payload.get("pnl_pct") or 0.0,
        "strategy": row.get("strategy") or payload.get("strategy") or "",
        "entry_time": row.get("entry_time") or payload.get("entry_time"),
        "exit_time": row.get("exit_time") or payload.get("exit_time"),
        "hold_seconds": row.get("hold_seconds") or payload.get("hold_seconds") or 0,
        "exit_reason": row.get("exit_reason") or payload.get("exit_reason") or "",
    }


def _load_runtime_ledger_trades(
    asset_class: str,
    *,
    strategy: str | None = None,
    symbol: str | None = None,
    limit: int = 500,
) -> tuple[list[dict], bool]:
    """Load trades from RuntimeLedger.

    Returns (rows, available). ``available`` is true only when an existing
    RuntimeLedger DB was opened, so callers can distinguish "empty ledger" from
    "ledger not configured yet".
    """
    ledger = _get_runtime_ledger()
    if ledger is None:
        return [], False

    try:
        rows: list[dict] = []
        for target in _target_assets(asset_class):
            filters: dict = {"asset_class": target, "limit": limit}
            if strategy:
                filters["strategy"] = strategy
            if symbol:
                filters["symbol"] = symbol
            rows.extend(ledger.query_trades(filters))
        trades = [_ledger_row_to_trade_dict(row) for row in rows]
        trades.sort(key=lambda t: _parse_tz_aware(t.get("exit_time")), reverse=True)
        return trades[:limit], True
    except RuntimeLedgerError:
        return [], False
    finally:
        ledger.close()


def _to_trade_response(t: dict, asset_class: str) -> TradeResponse | None:
    try:
        return TradeResponse(
            id=t.get("id", ""),
            asset_class=t.get("asset_class", asset_class),
            symbol=t.get("symbol") or t.get("code", ""),
            side=t.get("side", "long"),
            quantity=int(t.get("quantity", 0)),
            entry_price=float(t.get("entry_price", 0)),
            exit_price=float(t.get("exit_price", 0)),
            pnl=float(t.get("pnl", 0)),
            pnl_pct=float(t.get("pnl_pct", 0)),
            strategy=t.get("strategy", ""),
            entry_time=_parse_tz_aware(t.get("entry_time")),
            exit_time=_parse_tz_aware(t.get("exit_time")),
        )
    except (ValueError, TypeError, KeyError):
        # Invalid trade data - skip this record
        return None


@router.get("", response_model=TradeListResponse)
async def get_trades(
    strategy: str | None = Query(None, description="Filter by strategy"),
    symbol: str | None = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=100, description="Number of trades"),
    page: int = Query(1, ge=1, description="Page number"),
    asset_class: str = Query(default="futures"),
):
    """Get list of trades with optional filters."""
    asset = _normalize_asset_class(asset_class)
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
            for target in _target_assets(asset)
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
    asset = _normalize_asset_class(os.environ.get("TRADING_ASSET_CLASS", "stock"))
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
async def get_trades_by_strategy():
    """Get trade performance grouped by strategy."""
    asset = _normalize_asset_class(os.environ.get("TRADING_ASSET_CLASS", "stock"))
    ledger_rows, ledger_available = _load_runtime_ledger_trades(asset)
    raw = ledger_rows if ledger_available else _load_trades(asset)
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


def _empty_db_stats() -> dict[str, float]:
    return {
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "win_rate": 0.0,
        "total_pnl": 0.0,
        "avg_pnl": 0.0,
        "max_win": 0.0,
        "max_loss": 0.0,
    }


def _statistics_from_trade_dicts(trades: list[dict]) -> dict[str, float]:
    if not trades:
        return _empty_db_stats()

    pnls = [float(t.get("pnl", 0) or 0) for t in trades]
    winning = [pnl for pnl in pnls if pnl > 0]
    losing = [pnl for pnl in pnls if pnl <= 0]
    total_pnl = sum(pnls)
    return {
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": round(len(winning) / len(trades) * 100, 2),
        "total_pnl": total_pnl,
        "avg_pnl": round(total_pnl / len(trades), 2),
        "max_win": max(pnls, default=0.0),
        "max_loss": min(pnls, default=0.0),
    }


def _ledger_trade_to_closed_dict(trade: dict) -> dict:
    return {
        "id": trade.get("id", ""),
        "asset_class": trade.get("asset_class", "unknown"),
        "code": trade.get("code") or trade.get("symbol", ""),
        "name": trade.get("name", ""),
        "strategy": trade.get("strategy", ""),
        "side": trade.get("side", "long"),
        "entry_date": trade.get("entry_time"),
        "entry_price": trade.get("entry_price", 0.0),
        "exit_date": trade.get("exit_time"),
        "exit_price": trade.get("exit_price", 0.0),
        "quantity": trade.get("quantity", 0),
        "pnl": trade.get("pnl", 0.0),
        "pnl_pct": trade.get("pnl_pct", 0.0),
        "hold_seconds": trade.get("hold_seconds", 0),
        "exit_reason": trade.get("exit_reason", ""),
    }


def _ledger_fill_to_dict(fill: dict) -> dict:
    payload = fill.get("payload") if isinstance(fill.get("payload"), dict) else {}
    role = payload.get("trade_role", "")
    filled_at = fill.get("filled_at") or payload.get("filled_at")
    if isinstance(filled_at, datetime):
        filled_at = filled_at.isoformat()
    return {
        "signal_id": payload.get("signal_id", ""),
        "symbol": fill.get("symbol")
        or payload.get("symbol")
        or payload.get("code", ""),
        "side": fill.get("side") or payload.get("side", ""),
        "filled_price": fill.get("price") or payload.get("filled_price", 0.0),
        "quantity": fill.get("quantity") or payload.get("quantity", 0),
        "filled_at": filled_at,
        "trade_role": "entry" if role == "entry" else "exit",
        "asset_class": fill.get("asset_class")
        or payload.get("asset_class")
        or "unknown",
        "order_id": fill.get("order_id") or payload.get("order_id", ""),
    }


def _load_runtime_ledger_fills(
    asset_class: str,
    *,
    limit: int = 100,
) -> tuple[list[dict], bool]:
    ledger = _get_runtime_ledger()
    if ledger is None:
        return [], False
    try:
        rows: list[dict] = []
        for target in _target_assets(asset_class):
            rows.extend(ledger.query_fills({"asset_class": target, "limit": limit}))
        fills = [_ledger_fill_to_dict(row) for row in rows]
        fills.sort(key=lambda f: _parse_tz_aware(f.get("filled_at")), reverse=True)
        return fills[:limit], True
    except RuntimeLedgerError:
        return [], False
    finally:
        ledger.close()


@router.get("/closed/statistics")
async def get_db_closed_statistics(
    asset_class: str = Query("futures"),
    strategy: str | None = Query(None),
):
    """Aggregate statistics from RuntimeLedger."""
    asset_class = _normalize_asset_class(asset_class)
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
    asset = _normalize_asset_class(asset_class)
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
    asset_class = _normalize_asset_class(asset_class)
    ledger_rows, ledger_available = _load_runtime_ledger_trades(
        asset_class,
        strategy=strategy,
        symbol=code,
        limit=limit,
    )
    if ledger_available:
        return [_ledger_trade_to_closed_dict(row) for row in ledger_rows]
    return []
