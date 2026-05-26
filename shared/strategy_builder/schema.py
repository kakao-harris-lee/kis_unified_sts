"""Contracts for the no-code Strategy Builder."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IndicatorCategory(StrEnum):
    MOVING_AVERAGE = "moving_average"
    OSCILLATOR = "oscillator"
    TREND = "trend"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    MISC = "misc"
    CANDLESTICK = "candlestick"


class ParamType(StrEnum):
    NUMBER = "number"
    STRING = "string"


class ConditionOperator(StrEnum):
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    EQUALS = "equals"
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"


class ConditionLogic(StrEnum):
    AND = "AND"
    OR = "OR"


class OperandType(StrEnum):
    INDICATOR = "indicator"
    VALUE = "value"
    PRICE = "price"


class SignalSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class IndicatorParam(BaseModel):
    name: str
    type: ParamType = ParamType.NUMBER
    default: int | float | str
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    description: str | None = None


class IndicatorOutput(BaseModel):
    id: str
    name: str
    description: str | None = None


class IndicatorDefinition(BaseModel):
    id: str
    name: str
    name_ko: str
    category: IndicatorCategory
    description: str
    params: list[IndicatorParam] = Field(default_factory=list)
    outputs: list[IndicatorOutput] = Field(default_factory=list)
    default_output: str = "value"
    implemented: bool = True
    backtest_supported: bool = True
    runtime_supported: bool = True

    model_config = ConfigDict(extra="forbid")


class BuilderMetadata(BaseModel):
    id: str = Field(default_factory=lambda: f"builder_{uuid4().hex[:12]}")
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    category: str = "custom"
    tags: list[str] = Field(default_factory=lambda: ["strategy_builder"])
    author: str = "STS"

    @field_validator("id", "name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class BuilderIndicator(BaseModel):
    id: str = Field(default_factory=lambda: f"ind_{uuid4().hex[:12]}")
    indicator_id: str
    alias: str
    display_name: str | None = None
    params: dict[str, int | float | str] = Field(default_factory=dict)
    output: str = "value"

    model_config = ConfigDict(extra="forbid")

    @field_validator("alias")
    @classmethod
    def alias_must_be_identifier_like(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("alias must not be blank")
        safe = normalized.replace("_", "")
        if not safe.isalnum() or normalized[0].isdigit():
            raise ValueError("alias must be alphanumeric/underscore and not start with a digit")
        return normalized


class ConditionOperand(BaseModel):
    type: OperandType
    indicator_alias: str | None = None
    indicator_output: str = "value"
    value: float | None = None
    price_field: Literal["close", "open", "high", "low", "volume"] | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_operand(self) -> ConditionOperand:
        if self.type == OperandType.INDICATOR and not self.indicator_alias:
            raise ValueError("indicator operand requires indicator_alias")
        if self.type == OperandType.VALUE and self.value is None:
            raise ValueError("value operand requires value")
        if self.type == OperandType.PRICE and not self.price_field:
            raise ValueError("price operand requires price_field")
        return self


class BuilderCondition(BaseModel):
    id: str = Field(default_factory=lambda: f"cond_{uuid4().hex[:12]}")
    left: ConditionOperand
    operator: ConditionOperator
    right: ConditionOperand

    model_config = ConfigDict(extra="forbid")


class BuilderConditionGroup(BaseModel):
    logic: ConditionLogic = ConditionLogic.AND
    conditions: list[BuilderCondition] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class RiskToggle(BaseModel):
    enabled: bool = False
    percent: float = Field(default=0.0, ge=0)


class RiskManagement(BaseModel):
    order_amount: float = Field(default=1_000_000, ge=0)
    stop_loss: RiskToggle = Field(default_factory=lambda: RiskToggle(enabled=True, percent=5.0))
    take_profit: RiskToggle = Field(default_factory=lambda: RiskToggle(enabled=False, percent=10.0))
    trailing_stop: RiskToggle = Field(default_factory=lambda: RiskToggle(enabled=False, percent=3.0))


class BuilderState(BaseModel):
    metadata: BuilderMetadata
    asset_class: Literal["stock", "futures"] = "stock"
    indicators: list[BuilderIndicator] = Field(default_factory=list)
    entry: BuilderConditionGroup = Field(default_factory=BuilderConditionGroup)
    exit: BuilderConditionGroup = Field(default_factory=BuilderConditionGroup)
    risk: RiskManagement = Field(default_factory=RiskManagement)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_condition_aliases(self) -> BuilderState:
        aliases = {indicator.alias for indicator in self.indicators}
        for group_name, group in (("entry", self.entry), ("exit", self.exit)):
            for condition in group.conditions:
                for operand in (condition.left, condition.right):
                    if (
                        operand.type == OperandType.INDICATOR
                        and operand.indicator_alias not in aliases
                    ):
                        raise ValueError(
                            f"{group_name} condition references unknown indicator alias "
                            f"{operand.indicator_alias}"
                        )
        return self


class SymbolSeries(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    name: str | None = None
    timestamps: list[datetime] = Field(default_factory=list)
    fields: dict[str, list[float]] = Field(default_factory=dict)
    indicators: dict[str, list[float]] = Field(default_factory=dict)

    @field_validator("timestamps")
    @classmethod
    def ensure_tz_aware(cls, values: list[datetime]) -> list[datetime]:
        result: list[datetime] = []
        for value in values:
            result.append(value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC))
        return result


class ConditionEvaluation(BaseModel):
    condition_id: str
    label: str
    passed: bool
    left_value: float | None = None
    right_value: float | None = None
    previous_left_value: float | None = None
    previous_right_value: float | None = None
    missing: list[str] = Field(default_factory=list)


class BuilderSignal(BaseModel):
    signal_id: str = Field(default_factory=lambda: f"sig_{uuid4().hex}")
    draft_id: str
    builder_state_hash: str
    strategy_name: str
    asset_class: str
    symbol: str
    name: str | None = None
    side: SignalSide
    strength: float = Field(ge=0, le=1)
    reason: str
    reference_price: float = Field(gt=0)
    orderability: str
    matched_conditions: list[ConditionEvaluation] = Field(default_factory=list)
    indicator_values: dict[str, float] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    lab_signal_id: str | None = None


class BuilderCapabilities(BaseModel):
    indicators: list[IndicatorDefinition]
    operators: list[ConditionOperator]
    price_fields: list[str]
    risk_fields: dict[str, Any]
    default_order_amount: float
    ttl_seconds: int
