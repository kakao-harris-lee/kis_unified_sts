"""KIS builder route request and response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExecuteStrategyRequest(BaseModel):
    strategy_id: str
    stocks: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    builder_state: dict[str, Any] | None = None


class ExecuteOrderRequest(BaseModel):
    stock_code: str
    stock_name: str | None = None
    action: str
    order_type: str = "limit"
    price: float = 0
    quantity: int = Field(default=1, ge=1)
    signal_reason: str | None = None


class RegisterPaperRequest(BaseModel):
    """Body of POST /register-paper."""

    builder_state: dict[str, Any] = Field(
        ...,
        description="Full BuilderState JSON (matching shared/strategy_builder/schema.py)",
    )
    stop_loss_pct: float = Field(default=5.0, ge=0)
    take_profit_pct: float = Field(default=10.0, ge=0)
    # None → derive from the draft's risk.trailing_stop toggle; an explicit
    # value overrides. (SL/TP stay operator-default driven; trailing is new so
    # there is no prior behavior to preserve, and honoring the builder toggle
    # is what the Risk step's switch implies.)
    trailing_stop_pct: float | None = Field(default=None, ge=0)
    order_amount: int = Field(default=1_000_000, ge=0)
    contracts: int = Field(
        default=1, ge=1, description="Futures contract count (futures only)"
    )
    cooldown_seconds: int = Field(default=0, ge=0)
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RegisteredStrategy(BaseModel):
    """A built strategy listed by GET /registered."""

    id: str
    name: str
    description: str | None = None
    asset_class: str
    enabled: bool
    registered_at: str | None = None
    path: str


class RegisteredListResponse(BaseModel):
    """GET /registered response."""

    strategies: list[RegisteredStrategy]
    total: int


class EnableRequest(BaseModel):
    enabled: bool


class StrategyActivity(BaseModel):
    """Recent signal + closed-trade counts for one built strategy."""

    id: str
    signals: int
    trades: int


class ActivityResponse(BaseModel):
    """GET /registered/activity response."""

    activity: list[StrategyActivity]
