"""Pydantic contracts for Strategy Lab."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LogicalOperator(StrEnum):
    ALL = "all"
    ANY = "any"


class ConditionOperator(StrEnum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"


class SignalSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalStatus(StrEnum):
    GENERATED = "generated"
    DISPLAYED = "displayed"
    ORDER_TICKET_CREATED = "order_ticket_created"
    PAPER_ORDER_SUBMITTED = "paper_order_submitted"
    PAPER_FILLED = "paper_filled"
    PAPER_REJECTED = "paper_rejected"
    EXPIRED = "expired"
    DISMISSED = "dismissed"


class OrderStatus(StrEnum):
    READY = "ready"
    REJECTED = "rejected"
    FILLED = "filled"


class Operand(BaseModel):
    """A rule operand.

    ``kind="indicator"`` resolves against the latest indicator values.
    ``kind="literal"`` uses the numeric value directly.
    """

    kind: Literal["indicator", "field", "literal"] = "indicator"
    name: str | None = None
    value: float | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_operand(self) -> Operand:
        if self.kind == "literal" and self.value is None:
            raise ValueError("literal operand requires value")
        if self.kind in {"indicator", "field"} and not self.name:
            raise ValueError(f"{self.kind} operand requires name")
        return self


class ConditionSpec(BaseModel):
    """Single rule condition."""

    left: Operand
    operator: ConditionOperator
    right: Operand
    label: str | None = None

    model_config = ConfigDict(extra="forbid")


class RuleGroup(BaseModel):
    """Nested condition group."""

    operator: LogicalOperator = LogicalOperator.ALL
    conditions: list[ConditionSpec] = Field(default_factory=list)
    groups: list[RuleGroup] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def require_rules(self) -> RuleGroup:
        if not self.conditions and not self.groups:
            raise ValueError("rule group requires at least one condition or group")
        return self


class RiskSpec(BaseModel):
    """Paper risk preview settings for a generated strategy."""

    order_amount: float | None = Field(default=None, ge=0)
    quantity: int | None = Field(default=None, ge=1)
    max_position_amount: float | None = Field(default=None, ge=0)
    stop_loss_pct: float | None = Field(default=None, ge=0)
    take_profit_pct: float | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")


class StrategySpec(BaseModel):
    """Normalized visual-builder strategy specification."""

    name: str = Field(min_length=1, max_length=120)
    asset_class: Literal["stock", "futures"] = "stock"
    description: str | None = None
    entry: RuleGroup
    exit: RuleGroup
    risk: RiskSpec = Field(default_factory=RiskSpec)
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized


class MarketSnapshot(BaseModel):
    """Latest symbol values used by preview signal generation."""

    symbol: str = Field(min_length=1, max_length=40)
    name: str | None = None
    price: float = Field(gt=0)
    indicators: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(extra="forbid")

    @field_validator("timestamp")
    @classmethod
    def ensure_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class RuleEvaluation(BaseModel):
    label: str
    passed: bool
    left_value: float | None = None
    right_value: float | None = None
    operator: ConditionOperator | None = None
    missing: list[str] = Field(default_factory=list)


class LabSignal(BaseModel):
    """Generated Strategy Lab signal shown in the dashboard."""

    signal_id: str = Field(default_factory=lambda: f"sig_{uuid4().hex}")
    draft_id: str
    strategy_name: str
    asset_class: str
    symbol: str
    name: str | None = None
    side: SignalSide
    confidence: float = Field(ge=0, le=1)
    strength: float = Field(ge=0, le=1)
    reason: str
    reference_price: float = Field(gt=0)
    risk_snapshot: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: Literal["preview", "backtest", "paper_run"] = "preview"
    orderability: str = "paper_orderable"
    matched_rules: list[RuleEvaluation] = Field(default_factory=list)
    indicator_values: dict[str, float] = Field(default_factory=dict)
    status: SignalStatus = SignalStatus.GENERATED
    paper_order_id: str | None = None
    fill_id: str | None = None
    position_id: str | None = None

    @field_validator("generated_at")
    @classmethod
    def ensure_generated_at_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class OrderTicket(BaseModel):
    """Paper-only order ticket created from a generated signal."""

    ticket_id: str = Field(default_factory=lambda: f"ticket_{uuid4().hex}")
    signal_id: str
    draft_id: str
    strategy_name: str
    asset_class: str
    symbol: str
    side: SignalSide
    quantity: int = Field(ge=1)
    order_amount: float = Field(gt=0)
    estimated_price: float = Field(gt=0)
    position_impact: str
    status: OrderStatus = OrderStatus.READY
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaperOrder(BaseModel):
    """Immediate-fill paper order emitted by Strategy Lab."""

    order_id: str = Field(default_factory=lambda: f"order_{uuid4().hex}")
    ticket_id: str
    signal_id: str
    draft_id: str
    asset_class: str
    symbol: str
    side: SignalSide
    quantity: int
    price: float
    status: OrderStatus
    fill_id: str | None = None
    position_id: str | None = None
    realized_pnl: float = 0.0
    reason: str | None = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaperPosition(BaseModel):
    """Strategy Lab paper position snapshot."""

    position_id: str = Field(default_factory=lambda: f"pos_{uuid4().hex}")
    draft_id: str
    asset_class: str
    symbol: str
    quantity: int
    avg_price: float
    realized_pnl: float = 0.0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
