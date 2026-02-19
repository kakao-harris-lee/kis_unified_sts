"""Trades endpoints."""
import asyncio
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/trades", tags=["trades"])


class TradeResponse(BaseModel):
    """Trade response model."""

    id: str
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

    trades: List[TradeResponse]
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


def _get_reader():
    from shared.streaming.trading_state import TradingStateReader
    asset = os.environ.get("TRADING_ASSET_CLASS", "stock")
    return TradingStateReader(asset)


def _load_trades() -> list[dict]:
    """Load all trades from Redis."""
    try:
        reader = _get_reader()
        return reader.get_trades(start=0, count=500)
    except Exception:
        return []


def _to_trade_response(t: dict) -> Optional[TradeResponse]:
    try:
        return TradeResponse(
            id=t.get("id", ""),
            symbol=t.get("symbol", ""),
            side=t.get("side", "long"),
            quantity=int(t.get("quantity", 0)),
            entry_price=float(t.get("entry_price", 0)),
            exit_price=float(t.get("exit_price", 0)),
            pnl=float(t.get("pnl", 0)),
            pnl_pct=float(t.get("pnl_pct", 0)),
            strategy=t.get("strategy", ""),
            entry_time=datetime.fromisoformat(t["entry_time"]) if "entry_time" in t else datetime.now(),
            exit_time=datetime.fromisoformat(t["exit_time"]) if "exit_time" in t else datetime.now(),
        )
    except Exception:
        return None


@router.get("", response_model=TradeListResponse)
async def get_trades(
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=100, description="Number of trades"),
    page: int = Query(1, ge=1, description="Page number"),
):
    """Get list of trades with optional filters."""
    raw = _load_trades()
    trades = [_to_trade_response(t) for t in raw]
    trades = [t for t in trades if t is not None]

    if strategy:
        trades = [t for t in trades if t.strategy == strategy]
    if symbol:
        trades = [t for t in trades if t.symbol == symbol]

    total = len(trades)
    start = (page - 1) * limit
    end = start + limit
    paginated = trades[start:end]

    return TradeListResponse(trades=paginated, total=total, page=page, limit=limit)


@router.get("/statistics", response_model=TradeStatistics)
async def get_trade_statistics():
    """Get overall trade statistics."""
    raw = _load_trades()
    trades = [_to_trade_response(t) for t in raw]
    trades = [t for t in trades if t is not None]

    if not trades:
        return TradeStatistics(
            total_trades=0, winning_trades=0, losing_trades=0,
            win_rate=0.0, total_pnl=0.0, avg_pnl=0.0,
            max_win=0.0, max_loss=0.0, profit_factor=0.0,
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


@router.get("/by-strategy", response_model=List[StrategyPerformance])
async def get_trades_by_strategy():
    """Get trade performance grouped by strategy."""
    raw = _load_trades()
    trades = [_to_trade_response(t) for t in raw]
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


# ---------------------------------------------------------------------------
# ClickHouse DB endpoints
# ---------------------------------------------------------------------------

def _get_ch_database() -> str:
    return os.environ.get("CLICKHOUSE_STOCK_DATABASE", "market")


def _get_ch_client():
    from clickhouse_driver import Client as SyncClient
    host = os.environ.get("CLICKHOUSE_HOST", "localhost")
    port = int(os.environ.get("CLICKHOUSE_PORT", "9000"))
    user = os.environ.get("CLICKHOUSE_USER", "default")
    password = os.environ.get("CLICKHOUSE_PASSWORD", "")
    return SyncClient(host=host, port=port, user=user, password=password)


def _query_ch(sql: str, params: dict = None) -> list:
    client = _get_ch_client()
    try:
        return client.execute(sql, params or {}, with_column_types=True)
    finally:
        client.disconnect()


@router.get("/db/statistics")
async def get_db_statistics():
    """Aggregate statistics from ClickHouse swing_positions table."""
    db = _get_ch_database()
    sql = (
        f"SELECT count() as total_trades, "
        f"countIf(pnl > 0) as winning_trades, "
        f"countIf(pnl <= 0) as losing_trades, "
        f"round(countIf(pnl > 0) / count() * 100, 2) as win_rate, "
        f"sum(pnl) as total_pnl, "
        f"round(avg(pnl), 0) as avg_pnl, "
        f"max(pnl) as max_win, "
        f"min(pnl) as max_loss "
        f"FROM {db}.swing_positions FINAL "
        f"WHERE is_open = 0"
    )
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _query_ch, sql, {})
        rows, columns = result
        col_names = [c[0] for c in columns]
        if rows:
            return dict(zip(col_names, rows[0]))
        return {
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
            "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
            "max_win": 0.0, "max_loss": 0.0,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/db/open")
async def get_db_open_positions():
    """Open positions from ClickHouse swing_positions table."""
    db = _get_ch_database()
    sql = (
        f"SELECT id, code, name, strategy, side, entry_date, entry_price, "
        f"quantity, current_state, high_since_entry, stop_loss_price "
        f"FROM {db}.swing_positions FINAL "
        f"WHERE is_open = 1 "
        f"ORDER BY entry_date DESC"
    )
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _query_ch, sql, {})
        rows, columns = result
        col_names = [c[0] for c in columns]
        return [dict(zip(col_names, row)) for row in rows]
    except Exception as e:
        return {"error": str(e), "positions": []}


@router.get("/db")
async def get_db_trades(
    strategy: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Recent closed trades from ClickHouse swing_positions table."""
    db = _get_ch_database()
    where_clauses = ["is_open = 0"]
    params: dict = {"limit": limit}
    if strategy:
        where_clauses.append("strategy = %(strategy)s")
        params["strategy"] = strategy
    where = " AND ".join(where_clauses)
    sql = (
        f"SELECT id, code, name, strategy, side, entry_date, entry_price, "
        f"exit_date, exit_price, quantity, pnl, exit_reason "
        f"FROM {db}.swing_positions FINAL "
        f"WHERE {where} "
        f"ORDER BY exit_date DESC "
        f"LIMIT %(limit)s"
    )
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _query_ch, sql, params)
        rows, columns = result
        col_names = [c[0] for c in columns]
        return [dict(zip(col_names, row)) for row in rows]
    except Exception as e:
        return {"error": str(e), "trades": []}
