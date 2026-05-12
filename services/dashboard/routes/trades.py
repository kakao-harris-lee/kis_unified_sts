"""Trades endpoints."""

import asyncio
import os
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.dashboard.routes.trading import _normalize_asset_class
from shared.exceptions import InfrastructureError


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


def _get_reader():
    from shared.streaming.trading_state import TradingStateReader

    asset = os.environ.get("TRADING_ASSET_CLASS", "stock")
    return TradingStateReader(asset)


def _load_trades() -> list[dict]:
    """Load all trades from Redis."""
    try:
        reader = _get_reader()
        return reader.get_trades(start=0, count=500)
    except InfrastructureError:
        # Redis unavailable - return empty list
        return []


def _to_trade_response(t: dict) -> TradeResponse | None:
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
    _normalize_asset_class(asset_class)
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


def _query_ch(sql: str, params: dict | None = None) -> tuple[list, list]:
    """Execute a ClickHouse query and return (rows, column_types)."""
    from clickhouse_driver import Client as SyncClient

    from shared.db.config import ClickHouseConfig

    cfg = ClickHouseConfig.from_env()
    client = SyncClient(
        host=cfg.host, port=cfg.port, user=cfg.user, password=cfg.password
    )
    try:
        return client.execute(sql, params or {}, with_column_types=True)
    finally:
        client.disconnect()


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


@router.get("/rl/statistics")
async def get_db_rl_statistics(
    asset_class: str = Query("futures"),
    strategy: str | None = Query(None),
):
    """Aggregate statistics from ClickHouse rl_trades table."""
    from shared.db.config import ClickHouseConfig

    asset_class = _normalize_asset_class(asset_class)

    db = ClickHouseConfig.from_env().database
    where_clauses = []
    params: dict = {}
    if asset_class != "all":
        where_clauses.append("asset_class = %(asset_class)s")
        params["asset_class"] = asset_class
    if strategy:
        where_clauses.append("strategy = %(strategy)s")
        params["strategy"] = strategy

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql = (
        f"SELECT count() as total_trades, "
        f"countIf(pnl > 0) as winning_trades, "
        f"countIf(pnl <= 0) as losing_trades, "
        f"if(count() > 0, round(countIf(pnl > 0) / count() * 100, 2), 0) as win_rate, "
        f"ifNull(sum(pnl), 0) as total_pnl, "
        f"if(count() > 0, round(avg(pnl), 2), 0) as avg_pnl, "
        f"ifNull(max(pnl), 0) as max_win, "
        f"ifNull(min(pnl), 0) as max_loss "
        f"FROM {db}.rl_trades "
        f"{where_sql}"
    )
    try:
        loop = asyncio.get_running_loop()
        rows, columns = await loop.run_in_executor(None, _query_ch, sql, params)
        col_names = [c[0] for c in columns]
        if rows and rows[0][0] > 0:
            return dict(zip(col_names, rows[0]))
        return _empty_db_stats()
    except InfrastructureError as e:
        raise HTTPException(status_code=503, detail=f"ClickHouse unavailable: {e}")
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Database error: {type(e).__name__}"
        )


@router.get("/fills")
async def get_recent_fills(
    asset_class: str = Query(default="futures"),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict:
    """Recent order fills from ClickHouse ``kospi.order_fills``.

    The ``order_fills`` table itself does not carry an ``asset_class`` column
    (it was introduced in Phase 4 for futures). Until a multi-asset variant
    lands, all rows are treated as ``futures``; the ``asset_class`` filter
    short-circuits the query for non-futures requests unless ``all``.

    ``trade_role`` is normalized to ``entry`` / ``exit`` for UI consumption —
    ``stop_loss``/``take_profit``/``force_close`` all collapse to ``exit``.

    Returns ``{"fills": []}`` if ClickHouse is unavailable so the cockpit
    panel degrades gracefully.
    """
    asset = _normalize_asset_class(asset_class)
    if asset == "stock":
        # order_fills currently only holds futures fills.
        return {"fills": []}

    sql = (
        "SELECT signal_id, symbol, side, filled_price, quantity, "
        "filled_at, trade_role "
        "FROM kospi.order_fills "
        "ORDER BY filled_at DESC "
        "LIMIT %(limit)s"
    )
    try:
        loop = asyncio.get_running_loop()
        rows, columns = await loop.run_in_executor(
            None, _query_ch, sql, {"limit": limit}
        )
        col_names = [c[0] for c in columns]
        fills = []
        for row in rows:
            rec = dict(zip(col_names, row))
            role = rec.get("trade_role", "")
            rec["trade_role"] = "entry" if role == "entry" else "exit"
            rec["asset_class"] = "futures"
            if isinstance(rec.get("filled_at"), datetime):
                rec["filled_at"] = rec["filled_at"].isoformat()
            fills.append(rec)
        return {"fills": fills}
    except Exception:
        # ClickHouse unavailable or query error — return empty for graceful UI degrade.
        return {"fills": []}


@router.get("/rl")
async def get_db_rl_trades(
    asset_class: str = Query("futures"),
    strategy: str | None = Query(None),
    code: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Recent RL closed trades from ClickHouse rl_trades table."""
    from shared.db.config import ClickHouseConfig

    asset_class = _normalize_asset_class(asset_class)

    db = ClickHouseConfig.from_env().database
    where_clauses = []
    params: dict = {"limit": limit}
    if asset_class != "all":
        where_clauses.append("asset_class = %(asset_class)s")
        params["asset_class"] = asset_class
    if strategy:
        where_clauses.append("strategy = %(strategy)s")
        params["strategy"] = strategy
    if code:
        where_clauses.append("code = %(code)s")
        params["code"] = code

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql = (
        f"SELECT id, asset_class, code, name, strategy, side, entry_date, entry_price, "
        f"exit_date, exit_price, quantity, pnl, pnl_pct, hold_seconds, exit_reason "
        f"FROM {db}.rl_trades "
        f"{where_sql} "
        f"ORDER BY exit_date DESC "
        f"LIMIT %(limit)s"
    )
    try:
        loop = asyncio.get_running_loop()
        rows, columns = await loop.run_in_executor(None, _query_ch, sql, params)
        col_names = [c[0] for c in columns]
        return [dict(zip(col_names, row)) for row in rows]
    except InfrastructureError as e:
        raise HTTPException(status_code=503, detail=f"ClickHouse unavailable: {e}")
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Database error: {type(e).__name__}"
        )
