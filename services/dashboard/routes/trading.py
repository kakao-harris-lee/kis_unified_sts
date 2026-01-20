"""Trading status and control endpoints."""
from datetime import datetime
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/trading", tags=["trading"])


class TradingStatus(BaseModel):
    """Trading system status response."""

    is_running: bool
    market_status: str
    active_strategies: List[str]
    total_positions: int
    total_pnl: float
    last_update: datetime


class PositionResponse(BaseModel):
    """Position response model."""

    code: str
    name: str
    side: str
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float
    pnl_pct: float
    entry_time: datetime
    strategy: str


# In-memory state (replaced by real orchestrator in production)
_trading_state = {
    "is_running": False,
    "positions": [],
}


@router.get("/status", response_model=TradingStatus)
async def get_trading_status():
    """Get current trading system status."""
    return TradingStatus(
        is_running=_trading_state["is_running"],
        market_status="closed",
        active_strategies=[],
        total_positions=len(_trading_state["positions"]),
        total_pnl=0.0,
        last_update=datetime.now(),
    )


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions():
    """Get all open positions."""
    return _trading_state["positions"]


@router.post("/start")
async def start_trading():
    """Start trading system."""
    _trading_state["is_running"] = True
    return {"status": "started"}


@router.post("/stop")
async def stop_trading():
    """Stop trading system."""
    _trading_state["is_running"] = False
    return {"status": "stopped"}
