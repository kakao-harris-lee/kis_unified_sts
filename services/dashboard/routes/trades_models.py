"""Trades response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TradeResponse(BaseModel):
    """Trade response model."""

    id: str
    asset_class: str
    symbol: str
    name: str = ""
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


class LifecycleStep(BaseModel):
    """One step in a signal/order/fill/trade lifecycle timeline."""

    stage: str
    label: str
    status: str
    id: str | None = None
    timestamp: datetime | None = None
    source: str
    summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class TradeLifecycleResponse(BaseModel):
    """Read-only lifecycle timeline for dashboard inspection."""

    asset_class: str
    as_of: datetime
    filters: dict[str, str] = Field(default_factory=dict)
    lineage: dict[str, str | None] = Field(default_factory=dict)
    steps: list[LifecycleStep]
    warnings: list[str] = Field(default_factory=list)
