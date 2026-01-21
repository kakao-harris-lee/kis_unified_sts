"""Signals endpoints."""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/signals", tags=["signals"])


class SignalResponse(BaseModel):
    """Signal response model."""

    id: str
    symbol: str
    side: str
    signal_type: str
    strategy: str
    price: float
    confidence: float
    timestamp: datetime
    executed: bool


class SignalListResponse(BaseModel):
    """Signal list response."""

    signals: List[SignalResponse]
    total: int
    page: int
    limit: int


class SignalHistoryResponse(BaseModel):
    """Signal history response."""

    history: List[dict]
    total_signals: int
    days: int


# In-memory signal storage (replaced by real storage in production)
_signals_store: List[SignalResponse] = []


@router.get("", response_model=SignalListResponse)
async def get_signals(
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    side: Optional[str] = Query(None, description="Filter by side (BUY/SELL)"),
    limit: int = Query(50, ge=1, le=100, description="Number of signals"),
    page: int = Query(1, ge=1, description="Page number"),
):
    """Get list of signals with optional filters."""
    signals = _signals_store.copy()

    # Apply filters
    if strategy:
        signals = [s for s in signals if s.strategy == strategy]
    if side:
        signals = [s for s in signals if s.side == side]

    # Pagination
    start = (page - 1) * limit
    end = start + limit
    paginated = signals[start:end]

    return SignalListResponse(
        signals=paginated,
        total=len(signals),
        page=page,
        limit=limit,
    )


@router.get("/history", response_model=SignalHistoryResponse)
async def get_signal_history(
    days: int = Query(7, ge=1, le=30, description="Number of days"),
):
    """Get signal history statistics."""
    cutoff = datetime.now() - timedelta(days=days)
    recent_signals = [s for s in _signals_store if s.timestamp >= cutoff]

    # Group by date
    history = {}
    for signal in recent_signals:
        date_key = signal.timestamp.strftime("%Y-%m-%d")
        if date_key not in history:
            history[date_key] = {"date": date_key, "count": 0, "buy": 0, "sell": 0}
        history[date_key]["count"] += 1
        if signal.side == "BUY":
            history[date_key]["buy"] += 1
        else:
            history[date_key]["sell"] += 1

    return SignalHistoryResponse(
        history=list(history.values()),
        total_signals=len(recent_signals),
        days=days,
    )
