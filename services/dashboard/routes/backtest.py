"""Backtest endpoints."""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    """Backtest run request."""

    strategy: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = 10_000_000
    params: Optional[dict] = None


class BacktestRunResponse(BaseModel):
    """Backtest run response."""

    run_id: str
    status: str
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    created_at: datetime


class BacktestResult(BaseModel):
    """Backtest result."""

    run_id: str
    status: str
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    win_rate: float
    created_at: datetime
    completed_at: Optional[datetime]


class BacktestListResponse(BaseModel):
    """Backtest list response."""

    runs: List[BacktestResult]
    total: int
    page: int
    limit: int


# In-memory backtest storage
_backtest_store: dict[str, BacktestResult] = {}


@router.get("", response_model=BacktestListResponse)
async def get_backtests(
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    limit: int = Query(20, ge=1, le=100, description="Number of runs"),
    page: int = Query(1, ge=1, description="Page number"),
):
    """Get list of backtest runs."""
    runs = list(_backtest_store.values())

    # Apply filters
    if strategy:
        runs = [r for r in runs if r.strategy == strategy]

    # Sort by created_at desc
    runs.sort(key=lambda r: r.created_at, reverse=True)

    # Pagination
    start = (page - 1) * limit
    end = start + limit
    paginated = runs[start:end]

    return BacktestListResponse(
        runs=paginated,
        total=len(runs),
        page=page,
        limit=limit,
    )


@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest(request: BacktestRequest):
    """Start a new backtest run."""
    run_id = str(uuid.uuid4())[:8]
    now = datetime.now()

    # Create initial result (simulated - real impl would run async)
    result = BacktestResult(
        run_id=run_id,
        status="completed",  # Simulated instant completion
        strategy=request.strategy,
        symbol=request.symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        final_capital=request.initial_capital * 1.15,  # Simulated 15% return
        total_return=15.0,
        sharpe_ratio=1.5,
        max_drawdown=-8.5,
        total_trades=42,
        win_rate=58.5,
        created_at=now,
        completed_at=now,
    )

    _backtest_store[run_id] = result

    return BacktestRunResponse(
        run_id=run_id,
        status="completed",
        strategy=request.strategy,
        symbol=request.symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        created_at=now,
    )


@router.get("/{run_id}", response_model=BacktestResult)
async def get_backtest_result(run_id: str):
    """Get backtest result by ID."""
    if run_id not in _backtest_store:
        raise HTTPException(status_code=404, detail=f"Backtest run {run_id} not found")

    return _backtest_store[run_id]


@router.delete("/{run_id}")
async def delete_backtest(run_id: str):
    """Delete a backtest run."""
    if run_id not in _backtest_store:
        raise HTTPException(status_code=404, detail=f"Backtest run {run_id} not found")

    del _backtest_store[run_id]
    return {"status": "deleted", "run_id": run_id}
