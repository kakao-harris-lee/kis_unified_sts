"""Trades endpoints."""
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


# In-memory trade storage
_trades_store: List[TradeResponse] = []


@router.get("", response_model=TradeListResponse)
async def get_trades(
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=100, description="Number of trades"),
    page: int = Query(1, ge=1, description="Page number"),
):
    """Get list of trades with optional filters."""
    trades = _trades_store.copy()

    # Apply filters
    if strategy:
        trades = [t for t in trades if t.strategy == strategy]
    if symbol:
        trades = [t for t in trades if t.symbol == symbol]

    # Pagination
    start = (page - 1) * limit
    end = start + limit
    paginated = trades[start:end]

    return TradeListResponse(
        trades=paginated,
        total=len(trades),
        page=page,
        limit=limit,
    )


@router.get("/statistics", response_model=TradeStatistics)
async def get_trade_statistics():
    """Get overall trade statistics."""
    trades = _trades_store

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


@router.get("/by-strategy", response_model=List[StrategyPerformance])
async def get_trades_by_strategy():
    """Get trade performance grouped by strategy."""
    trades = _trades_store

    # Group by strategy
    strategy_trades: dict = {}
    for trade in trades:
        if trade.strategy not in strategy_trades:
            strategy_trades[trade.strategy] = []
        strategy_trades[trade.strategy].append(trade)

    # Calculate per-strategy stats
    results = []
    for strategy, strades in strategy_trades.items():
        winning = len([t for t in strades if t.pnl > 0])
        total_pnl = sum(t.pnl for t in strades)
        results.append(
            StrategyPerformance(
                strategy=strategy,
                trades=len(strades),
                win_rate=winning / len(strades) * 100 if strades else 0,
                total_pnl=total_pnl,
                avg_pnl=total_pnl / len(strades) if strades else 0,
            )
        )

    return results
