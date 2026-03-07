"""Trading status and control endpoints."""
import os
from datetime import datetime
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from shared.exceptions import InfrastructureError

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


def _get_reader():
    """Get TradingStateReader for the configured asset class."""
    from shared.streaming.trading_state import TradingStateReader
    asset = os.environ.get("TRADING_ASSET_CLASS", "stock")
    return TradingStateReader(asset)


@router.get("/status", response_model=TradingStatus)
async def get_trading_status():
    """Get current trading system status."""
    try:
        reader = _get_reader()
        status = reader.get_status()
    except InfrastructureError:
        # Redis unavailable - return default status
        status = {}

    if not status:
        return TradingStatus(
            is_running=False,
            market_status="closed",
            active_strategies=[],
            total_positions=0,
            total_pnl=0.0,
            last_update=datetime.now(),
        )

    state = status.get("state", "stopped").lower()
    config = status.get("config", {})
    stats = status.get("stats", {})
    positions = status.get("positions", {})

    # config/stats/positions may be JSON strings from Redis HASH
    if isinstance(config, str):
        try:
            config = __import__("json").loads(config)
        except (ValueError, TypeError):
            # Invalid JSON - use empty dict
            config = {}
    if isinstance(stats, str):
        try:
            stats = __import__("json").loads(stats)
        except (ValueError, TypeError):
            # Invalid JSON - use empty dict
            stats = {}
    if isinstance(positions, str):
        try:
            positions = __import__("json").loads(positions)
        except (ValueError, TypeError):
            # Invalid JSON - use empty dict
            positions = {}

    strategies = [config.get("strategy", "")] if config.get("strategy") else []
    # Collect strategy names from strategies dict if available
    strats_info = status.get("strategies", {})
    if isinstance(strats_info, str):
        try:
            strats_info = __import__("json").loads(strats_info)
        except (ValueError, TypeError):
            # Invalid JSON - use empty dict
            strats_info = {}
    if isinstance(strats_info, dict) and strats_info.get("strategies"):
        strategies = strats_info["strategies"]

    start_time = stats.get("start_time")

    return TradingStatus(
        is_running=state in ("running", "waiting"),
        market_status=status.get("regime") or "unknown",
        active_strategies=strategies,
        total_positions=positions.get("open_positions", 0) if isinstance(positions, dict) else 0,
        total_pnl=float(stats.get("total_pnl", 0)),
        last_update=datetime.fromisoformat(start_time) if start_time else datetime.now(),
    )


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions():
    """Get all open positions."""
    try:
        reader = _get_reader()
        positions = reader.get_positions()
    except InfrastructureError:
        # Redis unavailable - return empty list
        positions = []

    result = []
    for p in positions:
        try:
            result.append(PositionResponse(
                code=p.get("code", ""),
                name=p.get("name", ""),
                side=p.get("side", "long"),
                quantity=int(p.get("quantity", 0)),
                entry_price=float(p.get("entry_price", 0)),
                current_price=float(p.get("current_price", 0)),
                unrealized_pnl=float(p.get("unrealized_pnl", 0)),
                pnl_pct=float(p.get("pnl_pct", 0)),
                entry_time=datetime.fromisoformat(p["entry_time"]) if "entry_time" in p else datetime.now(),
                strategy=p.get("strategy", ""),
            ))
        except (ValueError, TypeError, KeyError):
            # Invalid position data - skip this record
            continue
    return result


@router.post("/start")
async def start_trading():
    """Start trading system (placeholder — orchestrator runs as CLI)."""
    return {"status": "use CLI: sts trade start"}


@router.post("/stop")
async def stop_trading():
    """Stop trading system (placeholder — orchestrator runs as CLI)."""
    return {"status": "use CLI: sts trade stop"}
