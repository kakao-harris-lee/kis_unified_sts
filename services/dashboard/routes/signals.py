"""Signals endpoints."""

import os
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel

from services.dashboard.routes.trading import _normalize_asset_class, _target_assets
from shared.exceptions import InfrastructureError

router = APIRouter(prefix="/api/signals", tags=["signals"])


class SignalResponse(BaseModel):
    """Signal response model."""

    id: str
    asset_class: str
    symbol: str
    side: str
    signal_type: str
    strategy: str
    price: float
    confidence: float
    strength: float
    timestamp: datetime
    executed: bool
    setup_type: str | None = None


class SignalListResponse(BaseModel):
    """Signal list response."""

    signals: list[SignalResponse]
    total: int
    page: int
    limit: int


class SignalHistoryResponse(BaseModel):
    """Signal history response."""

    history: list[dict]
    total_signals: int
    days: int


def _get_reader(asset_class: str | None = None):
    from shared.streaming.trading_state import TradingStateReader

    asset = asset_class or os.environ.get("TRADING_ASSET_CLASS", "stock")
    return TradingStateReader(asset)


def _load_signals(asset_class: str) -> list[dict]:
    try:
        reader = _get_reader(asset_class)
        return reader.get_signals(start=0, count=200)
    except InfrastructureError:
        # Redis unavailable - return empty list
        return []


def _to_signal_response(s: dict, asset_class: str) -> SignalResponse | None:
    try:
        # Always emit tz-aware UTC timestamps so callers (e.g.
        # /history's cutoff comparison) can mix freely without
        # "can't compare offset-naive and offset-aware" crashes.
        if "timestamp" in s:
            ts = datetime.fromisoformat(s["timestamp"])
            ts = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)
        else:
            ts = datetime.now(UTC)
        confidence = float(s.get("confidence", s.get("strength", 0)) or 0)
        return SignalResponse(
            id=s.get("id", ""),
            asset_class=asset_class,
            symbol=s.get("symbol", ""),
            side=s.get("side", ""),
            signal_type=s.get("signal_type", ""),
            strategy=s.get("strategy", ""),
            price=float(s.get("price", 0)),
            confidence=confidence,
            strength=confidence,
            timestamp=ts,
            executed=bool(s.get("executed", False)),
            setup_type=s.get("setup_type") or s.get("stage") or None,
        )
    except (ValueError, TypeError, KeyError):
        # Invalid signal data - skip this record
        return None


@router.get("", response_model=SignalListResponse)
async def get_signals(
    strategy: str | None = Query(None, description="Filter by strategy"),
    side: str | None = Query(None, description="Filter by side (BUY/SELL)"),
    limit: int = Query(50, ge=1, le=100, description="Number of signals"),
    page: int = Query(1, ge=1, description="Page number"),
    asset_class: str = Query(default="futures"),
):
    """Get list of signals with optional filters."""
    asset = _normalize_asset_class(asset_class)
    raw_by_asset = [
        (target, signal)
        for target in _target_assets(asset)
        for signal in _load_signals(target)
    ]
    signals = [_to_signal_response(s, target) for target, s in raw_by_asset]
    signals = [s for s in signals if s is not None]
    signals.sort(key=lambda s: s.timestamp, reverse=True)

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
    asset_class: str = Query(default="futures"),
):
    """Get signal history statistics."""
    asset = _normalize_asset_class(asset_class)
    raw_by_asset = [
        (target, signal)
        for target in _target_assets(asset)
        for signal in _load_signals(target)
    ]
    signals = [_to_signal_response(s, target) for target, s in raw_by_asset]
    signals = [s for s in signals if s is not None]

    # _to_signal_response always emits tz-aware UTC; cutoff must match.
    cutoff = datetime.now(UTC) - timedelta(days=days)
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
