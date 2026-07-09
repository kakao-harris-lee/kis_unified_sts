"""Contracts for the no-code Strategy Builder."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

# Builder input models accept BOTH the frontend's camelCase payload (via the
# generated alias) and snake_case (populate_by_name) used by tests / the
# materialized YAML. model_dump(by_alias=False, the default) keeps snake_case
# so the runtime + YAML are unaffected.
_BUILDER_MODEL_CONFIG = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    extra="forbid",
)


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
    # Percentile-rank operators (schema v2): compare the percentile rank of the
    # latest left-operand value within a trailing window (``BuilderCondition.window``
    # bars) against the right-operand threshold (0-100). Enables conditions like
    # "ATR in the top 10% of the trailing 120 bars" (Setup D-class volatility gates).
    PERCENTILE_RANK_ABOVE = "percentile_rank_above"
    PERCENTILE_RANK_BELOW = "percentile_rank_below"


PERCENTILE_OPERATORS: frozenset[ConditionOperator] = frozenset(
    {
        ConditionOperator.PERCENTILE_RANK_ABOVE,
        ConditionOperator.PERCENTILE_RANK_BELOW,
    }
)


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

    model_config = _BUILDER_MODEL_CONFIG

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

    model_config = _BUILDER_MODEL_CONFIG

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

    model_config = _BUILDER_MODEL_CONFIG

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
    # Trailing window (bars) for the percentile_rank_* operators; ignored (and
    # must stay None) for scalar/cross operators so pre-v2 states hash unchanged.
    window: int | None = Field(default=None, ge=2)

    model_config = _BUILDER_MODEL_CONFIG

    @model_validator(mode="after")
    def validate_percentile_shape(self) -> BuilderCondition:
        if self.operator in PERCENTILE_OPERATORS:
            if self.window is None:
                raise ValueError(
                    f"operator {self.operator.value} requires 'window' "
                    "(trailing bars, integer >= 2)"
                )
            if self.left.type == OperandType.VALUE:
                raise ValueError(
                    f"operator {self.operator.value} needs a series on the left "
                    "(indicator or price operand, not a constant value)"
                )
            if self.right.type != OperandType.VALUE or not (
                0.0 <= float(self.right.value or 0.0) <= 100.0
            ):
                raise ValueError(
                    f"operator {self.operator.value} requires a value operand "
                    "between 0 and 100 on the right (percentile threshold)"
                )
        return self


class BuilderConditionGroup(BaseModel):
    logic: ConditionLogic = ConditionLogic.AND
    conditions: list[BuilderCondition] = Field(default_factory=list)

    model_config = _BUILDER_MODEL_CONFIG


class ExitPrimitiveRef(BaseModel):
    """Reference to a registered exit component (``ExitRegistry`` name).

    Lets a builder strategy compose a stateful exit primitive (e.g.
    ``three_stage``, ``atr_dynamic``, ``chandelier_exit``, ``momentum_decay``)
    with the declarative stop/target/trailing risk block. Name resolution
    against the registry happens at strategy-build/validation time (the schema
    layer stays import-cycle free); unknown names are rejected there with the
    list of available primitives.
    """

    primitive: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = _BUILDER_MODEL_CONFIG

    @field_validator("primitive")
    @classmethod
    def primitive_not_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("exit primitive name must not be blank")
        return normalized


class BuilderRegimeGate(BaseModel):
    """Schema hook for the existing framework regime gate.

    Field names and defaults mirror ``regime_gate_cfg_from_yaml``
    (``shared/strategy/gates/regime_gate.py``); the factory dumps this model
    into that loader so the builder reuses the framework gate unchanged.
    """

    enabled: bool = False
    regime_percentile_max: float = Field(default=60.0, ge=0.0, le=100.0)
    impact_score_max: int = Field(default=70, ge=0, le=100)
    event_window_minutes: int = Field(default=15, ge=0)
    require_overnight_us_direction: bool = False
    permissive_on_missing: bool = True

    model_config = _BUILDER_MODEL_CONFIG


class BuilderGates(BaseModel):
    """Optional entry gates for a builder strategy (schema v2).

    ``regime_gate`` reuses the framework RegimeGate attachment; ``cooldown_seconds``
    is consumed by the builder entry bridge (the effective cooldown is the max of
    this and the deploy-time ``cooldown_seconds`` param, i.e. most conservative).
    No LLM-veto field yet: the platform has no framework-level veto hook to
    attach to (it lives inside the Setup adapters), so adding one here would
    require new LLM plumbing — deferred.
    """

    regime_gate: BuilderRegimeGate | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0)

    model_config = _BUILDER_MODEL_CONFIG


class RiskToggle(BaseModel):
    enabled: bool = False
    percent: float = Field(default=0.0, ge=0)

    model_config = _BUILDER_MODEL_CONFIG


class RiskManagement(BaseModel):
    order_amount: float = Field(default=1_000_000, ge=0)
    stop_loss: RiskToggle = Field(default_factory=lambda: RiskToggle(enabled=True, percent=5.0))
    take_profit: RiskToggle = Field(default_factory=lambda: RiskToggle(enabled=False, percent=10.0))
    trailing_stop: RiskToggle = Field(default_factory=lambda: RiskToggle(enabled=False, percent=3.0))

    model_config = _BUILDER_MODEL_CONFIG


class BuilderState(BaseModel):
    metadata: BuilderMetadata
    asset_class: Literal["stock", "futures"] = "stock"
    indicators: list[BuilderIndicator] = Field(default_factory=list)
    entry: BuilderConditionGroup = Field(default_factory=BuilderConditionGroup)
    # Schema v2: optional short-entry condition group. ``entry`` stays the long
    # group; when ``entry_short`` matches (and ``entry`` did not), the runtime
    # bridge emits ``signal_direction="short"``. Futures-only — the stock paper
    # pipeline cannot execute short entries.
    entry_short: BuilderConditionGroup | None = None
    exit: BuilderConditionGroup = Field(default_factory=BuilderConditionGroup)
    risk: RiskManagement = Field(default_factory=RiskManagement)
    # Schema v2: optional named exit primitive composed with the risk block.
    exit_primitive: ExitPrimitiveRef | None = None
    # Schema v2: optional entry gates (regime gate / cooldown).
    gates: BuilderGates | None = None

    model_config = _BUILDER_MODEL_CONFIG

    def condition_groups(self) -> list[tuple[str, BuilderConditionGroup]]:
        """Return the named condition groups present on this state."""
        groups: list[tuple[str, BuilderConditionGroup]] = [("entry", self.entry)]
        if self.entry_short is not None:
            groups.append(("entry_short", self.entry_short))
        groups.append(("exit", self.exit))
        return groups

    @model_validator(mode="after")
    def validate_condition_aliases(self) -> BuilderState:
        aliases = {indicator.alias for indicator in self.indicators}
        for group_name, group in self.condition_groups():
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

    @model_validator(mode="after")
    def validate_short_entries_futures_only(self) -> BuilderState:
        if (
            self.entry_short is not None
            and self.entry_short.conditions
            and self.asset_class != "futures"
        ):
            raise ValueError(
                "entry_short (short entries) is only supported for "
                f"asset_class='futures'; got asset_class={self.asset_class!r}. "
                "The stock paper pipeline is long-only."
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


class ExitPrimitiveDefinition(BaseModel):
    """Catalog metadata for an exit primitive exposed to the builder UI.

    ``id`` must be an ``ExitRegistry`` component name (the registry is the
    validation SoT); ``asset_classes`` restricts which asset classes may
    reference it (e.g. ``three_stage`` is stock-only per operational rule).
    """

    id: str
    name: str | None = None
    name_ko: str | None = None
    description: str | None = None
    asset_classes: list[Literal["stock", "futures"]] = Field(
        default_factory=lambda: ["stock", "futures"]
    )

    model_config = ConfigDict(extra="forbid")


class BuilderCapabilities(BaseModel):
    indicators: list[IndicatorDefinition]
    operators: list[ConditionOperator]
    price_fields: list[str]
    risk_fields: dict[str, Any]
    default_order_amount: float
    ttl_seconds: int
    # Schema v2 vocabulary (additive; defaults keep older payload consumers working).
    directions: list[str] = Field(default_factory=lambda: ["long"])
    exit_primitives: list[ExitPrimitiveDefinition] = Field(default_factory=list)
    gate_fields: dict[str, Any] = Field(default_factory=dict)
