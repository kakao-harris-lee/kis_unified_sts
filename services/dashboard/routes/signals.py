"""Signals endpoints."""
import os
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


def _get_reader():
    from shared.streaming.trading_state import TradingStateReader
    asset = os.environ.get("TRADING_ASSET_CLASS", "stock")
    return TradingStateReader(asset)


def _load_signals() -> list[dict]:
    try:
        reader = _get_reader()
        return reader.get_signals(start=0, count=200)
    except Exception:
        return []


def _to_signal_response(s: dict) -> Optional[SignalResponse]:
    try:
        return SignalResponse(
            id=s.get("id", ""),
            symbol=s.get("symbol", ""),
            side=s.get("side", ""),
            signal_type=s.get("signal_type", ""),
            strategy=s.get("strategy", ""),
            price=float(s.get("price", 0)),
            confidence=float(s.get("confidence", 0)),
            timestamp=datetime.fromisoformat(s["timestamp"]) if "timestamp" in s else datetime.now(),
            executed=bool(s.get("executed", False)),
        )
    except Exception:
        return None


@router.get("", response_model=SignalListResponse)
async def get_signals(
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    side: Optional[str] = Query(None, description="Filter by side (BUY/SELL)"),
    limit: int = Query(50, ge=1, le=100, description="Number of signals"),
    page: int = Query(1, ge=1, description="Page number"),
):
    """Get list of signals with optional filters."""
    raw = _load_signals()
    signals = [_to_signal_response(s) for s in raw]
    signals = [s for s in signals if s is not None]

    if strategy:
        signals = [s for s in signals if s.strategy == strategy]
    if side:
        signals = [s for s in signals if s.side == side]

    total = len(signals)
    start = (page - 1) * limit
    end = start + limit
    paginated = signals[start:end]

    return SignalListResponse(signals=paginated, total=total, page=page, limit=limit)


@router.get("/history", response_model=SignalHistoryResponse)
async def get_signal_history(
    days: int = Query(7, ge=1, le=30, description="Number of days"),
):
    """Get signal history statistics."""
    raw = _load_signals()
    signals = [_to_signal_response(s) for s in raw]
    signals = [s for s in signals if s is not None]

    cutoff = datetime.now() - timedelta(days=days)
    recent = [s for s in signals if s.timestamp >= cutoff]

    history: dict[str, dict] = {}
    for signal in recent:
        date_key = signal.timestamp.strftime("%Y-%m-%d")
        if date_key not in history:
            history[date_key] = {"date": date_key, "count": 0, "buy": 0, "sell": 0}
        history[date_key]["count"] += 1
        if signal.side == "BUY" or signal.side == "entry":
            history[date_key]["buy"] += 1
        else:
            history[date_key]["sell"] += 1

    return SignalHistoryResponse(
        history=list(history.values()),
        total_signals=len(recent),
        days=days,
    )
