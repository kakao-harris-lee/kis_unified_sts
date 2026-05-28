"""Compatibility helpers for the upstream KIS Strategy Builder UI."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from shared.strategy_builder.schema import (
    BuilderCondition,
    BuilderConditionGroup,
    BuilderIndicator,
    BuilderMetadata,
    BuilderState,
    ConditionLogic,
    ConditionOperand,
    ConditionOperator,
    OperandType,
    RiskManagement,
    RiskToggle,
    SymbolSeries,
)

DEFAULT_PRESETS_PATH = Path("config/strategy_builder/kis_presets.yaml")


@lru_cache(maxsize=1)
def load_kis_presets(path: str | Path = DEFAULT_PRESETS_PATH) -> list[dict[str, Any]]:
    """Load upstream-style Strategy Builder presets from YAML config."""
    cfg_path = Path(path)
    if not cfg_path.exists():
        return []
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    root = data.get("strategy_builder_kis", {})
    presets = root.get("presets", [])
    return [item for item in presets if isinstance(item, dict)]


def get_kis_preset(strategy_id: str) -> dict[str, Any] | None:
    """Return a configured upstream-style preset by id."""
    return next((item for item in load_kis_presets() if item.get("id") == strategy_id), None)


def apply_kis_preset_params(
    preset: dict[str, Any],
    params: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply Execute-page preset params to an upstream-style BuilderState.

    The imported UI sends slider values separately from the preset
    ``builder_state``. Keep the binding config-driven where possible by using
    each preset param's default value to locate corresponding indicator params
    and threshold constants inside the state.
    """
    state = deepcopy(preset.get("builder_state", {}))
    if not params:
        return state

    param_defs = [
        item for item in preset.get("params", [])
        if isinstance(item, dict) and item.get("name") in params
    ]
    for param_def in param_defs:
        name = str(param_def["name"])
        default = _as_float(param_def.get("default"))
        value = _as_float(params.get(name))
        if value is None:
            continue
        _apply_param_to_indicators(state, name, default, value)
        _apply_param_to_conditions(state, name, default, value)
    return state


def list_kis_strategy_infos() -> list[dict[str, Any]]:
    """Return strategy list payload expected by the upstream UI."""
    strategies: list[dict[str, Any]] = []
    for preset in load_kis_presets():
        state = deepcopy(preset.get("builder_state", {}))
        strategies.append(
            {
                "id": preset.get("id"),
                "name": preset.get("name"),
                "description": preset.get("description", ""),
                "category": preset.get("category", "custom"),
                "params": deepcopy(preset.get("params", [])),
                "builder_state": state,
            }
        )
    return strategies


def kis_state_to_builder_state(data: dict[str, Any]) -> BuilderState:
    """Convert upstream camelCase BuilderState into STS BuilderState."""
    metadata = data.get("metadata", {})
    return BuilderState(
        metadata=BuilderMetadata(
            id=str(metadata.get("id") or "custom_strategy"),
            name=str(metadata.get("name") or metadata.get("id") or "Custom Strategy"),
            description=str(metadata.get("description") or ""),
            category=str(metadata.get("category") or "custom"),
            tags=list(metadata.get("tags") or ["strategy_builder"]),
            author=str(metadata.get("author") or "KIS"),
        ),
        asset_class=str(data.get("asset_class") or data.get("assetClass") or "stock"),
        indicators=[
            _kis_indicator_to_builder(item)
            for item in data.get("indicators", [])
            if isinstance(item, dict)
        ],
        entry=_kis_group_to_builder(data.get("entry") or {}),
        exit=_kis_group_to_builder(data.get("exit") or {}),
        risk=_kis_risk_to_builder(data.get("risk") or {}),
    )


def builder_state_to_kis_state(state: BuilderState) -> dict[str, Any]:
    """Convert STS BuilderState into upstream camelCase BuilderState."""
    return {
        "metadata": {
            "id": state.metadata.id,
            "name": state.metadata.name,
            "description": state.metadata.description,
            "category": state.metadata.category,
            "tags": list(state.metadata.tags),
            "author": state.metadata.author,
        },
        "indicators": [_builder_indicator_to_kis(indicator) for indicator in state.indicators],
        "entry": _builder_group_to_kis(state.entry),
        "exit": _builder_group_to_kis(state.exit),
        "risk": {
            "stopLoss": state.risk.stop_loss.model_dump(),
            "takeProfit": state.risk.take_profit.model_dump(),
            "trailingStop": state.risk.trailing_stop.model_dump(),
        },
    }


def build_sample_series_for_state(state: BuilderState, symbol: str, name: str | None = None) -> SymbolSeries:
    """Create deterministic paper-only sample data that satisfies entry conditions.

    The upstream UI can generate signals without live market dependencies. This
    keeps the imported UI usable while real backtest/runtime market data wiring
    remains isolated from production trading.
    """
    fields: dict[str, list[float]] = {"close": [100.0, 101.0]}
    indicators: dict[str, list[float]] = {}

    for indicator in state.indicators:
        indicators.setdefault(f"{indicator.alias}.{indicator.output}", [100.0, 100.0])

    for condition in state.entry.conditions:
        _force_condition_pass(condition, fields, indicators)

    entry_refs = {
        ref
        for condition in state.entry.conditions
        for ref in (_series_ref(condition.left), _series_ref(condition.right))
        if ref is not None
    }
    for condition in state.exit.conditions:
        _force_condition_fail(condition, entry_refs, fields, indicators)

    return SymbolSeries(symbol=symbol, name=name, fields=fields, indicators=indicators)


def _kis_indicator_to_builder(data: dict[str, Any]) -> BuilderIndicator:
    return BuilderIndicator(
        id=str(data.get("id") or data.get("alias") or data.get("indicatorId") or "indicator"),
        indicator_id=str(data.get("indicatorId") or data.get("indicator_id") or data.get("id")),
        alias=str(data.get("alias") or data.get("indicatorId") or data.get("id")),
        display_name=data.get("displayName") or data.get("display_name"),
        params=dict(data.get("params") or {}),
        output=str(data.get("output") or "value"),
    )


def _builder_indicator_to_kis(indicator: BuilderIndicator) -> dict[str, Any]:
    result = {
        "id": indicator.id,
        "indicatorId": indicator.indicator_id,
        "alias": indicator.alias,
        "params": dict(indicator.params),
        "output": indicator.output,
    }
    if indicator.display_name:
        result["displayName"] = indicator.display_name
    return result


def _kis_group_to_builder(data: dict[str, Any]) -> BuilderConditionGroup:
    return BuilderConditionGroup(
        logic=ConditionLogic(data.get("logic") or "AND"),
        conditions=[
            _kis_condition_to_builder(item)
            for item in data.get("conditions", [])
            if isinstance(item, dict)
        ],
    )


def _builder_group_to_kis(group: BuilderConditionGroup) -> dict[str, Any]:
    return {
        "logic": group.logic.value,
        "conditions": [_builder_condition_to_kis(condition) for condition in group.conditions],
    }


def _kis_condition_to_builder(data: dict[str, Any]) -> BuilderCondition:
    if data.get("isCandlestick") and data.get("candlestickAlias"):
        signal = str(data.get("candlestickSignal") or "detected")
        operator = (
            ConditionOperator.LESS_THAN
            if signal == "bearish"
            else ConditionOperator.GREATER_THAN
        )
        return BuilderCondition(
            id=str(data.get("id") or "condition"),
            left=ConditionOperand(
                type=OperandType.INDICATOR,
                indicator_alias=str(data["candlestickAlias"]),
                indicator_output="value",
            ),
            operator=operator,
            right=ConditionOperand(type=OperandType.VALUE, value=0),
        )

    return BuilderCondition(
        id=str(data.get("id") or "condition"),
        left=_kis_operand_to_builder(data.get("left") or {}),
        operator=ConditionOperator(data.get("operator") or "greater_than"),
        right=_kis_operand_to_builder(data.get("right") or {}),
    )


def _builder_condition_to_kis(condition: BuilderCondition) -> dict[str, Any]:
    return {
        "id": condition.id,
        "left": _builder_operand_to_kis(condition.left),
        "operator": condition.operator.value,
        "right": _builder_operand_to_kis(condition.right),
    }


def _kis_operand_to_builder(data: dict[str, Any]) -> ConditionOperand:
    operand_type = OperandType(data.get("type") or "value")
    if operand_type == OperandType.INDICATOR:
        return ConditionOperand(
            type=operand_type,
            indicator_alias=data.get("indicatorAlias") or data.get("indicator_alias"),
            indicator_output=str(data.get("indicatorOutput") or data.get("indicator_output") or "value"),
        )
    if operand_type == OperandType.PRICE:
        return ConditionOperand(
            type=operand_type,
            price_field=data.get("priceField") or data.get("price_field") or "close",
        )
    return ConditionOperand(type=operand_type, value=float(data.get("value", 0)))


def _builder_operand_to_kis(operand: ConditionOperand) -> dict[str, Any]:
    if operand.type == OperandType.INDICATOR:
        return {
            "type": "indicator",
            "indicatorAlias": operand.indicator_alias,
            "indicatorOutput": operand.indicator_output,
        }
    if operand.type == OperandType.PRICE:
        return {"type": "price", "priceField": operand.price_field}
    return {"type": "value", "value": operand.value}


def _apply_param_to_indicators(
    state: dict[str, Any],
    name: str,
    default: float | None,
    value: float,
) -> None:
    for indicator in state.get("indicators", []):
        if not isinstance(indicator, dict):
            continue
        indicator_params = indicator.get("params")
        if not isinstance(indicator_params, dict):
            continue
        if name in indicator_params:
            indicator_params[name] = _coerce_param_value(indicator_params[name], value)
            continue
        for key, current in list(indicator_params.items()):
            if default is not None and _numeric_equal(current, default):
                indicator_params[key] = _coerce_param_value(current, value)


def _apply_param_to_conditions(
    state: dict[str, Any],
    name: str,
    default: float | None,
    value: float,
) -> None:
    for group_name in ("entry", "exit"):
        group = state.get(group_name)
        if not isinstance(group, dict):
            continue
        for condition in group.get("conditions", []):
            if not isinstance(condition, dict):
                continue
            for operand_name in ("left", "right"):
                operand = condition.get(operand_name)
                if not isinstance(operand, dict) or operand.get("type") != "value":
                    continue
                current = _as_float(operand.get("value"))
                if current is None:
                    continue
                if default is not None and _numeric_equal(current, default):
                    operand["value"] = _coerce_param_value(operand.get("value"), value)
                elif (
                    default is not None
                    and name in {"buy_threshold", "sell_threshold"}
                    and _numeric_equal(current, 100.0 + default)
                ):
                    operand["value"] = _coerce_param_value(operand.get("value"), 100.0 + value)


def _as_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _numeric_equal(left: object, right: float) -> bool:
    left_value = _as_float(left)
    return left_value is not None and abs(left_value - right) < 1e-9


def _coerce_param_value(_original: object, value: float) -> int | float:
    if float(value).is_integer():
        return int(value)
    return value


def _kis_risk_to_builder(data: dict[str, Any]) -> RiskManagement:
    return RiskManagement(
        stop_loss=_kis_risk_toggle(data.get("stopLoss") or data.get("stop_loss"), True, 5.0),
        take_profit=_kis_risk_toggle(data.get("takeProfit") or data.get("take_profit"), False, 10.0),
        trailing_stop=_kis_risk_toggle(
            data.get("trailingStop") or data.get("trailing_stop"), False, 3.0
        ),
    )


def _kis_risk_toggle(data: object, enabled: bool, percent: float) -> RiskToggle:
    if not isinstance(data, dict):
        return RiskToggle(enabled=enabled, percent=percent)
    return RiskToggle(
        enabled=bool(data.get("enabled", enabled)),
        percent=float(data.get("percent", percent)),
    )


def _force_condition_pass(
    condition: BuilderCondition,
    fields: dict[str, list[float]],
    indicators: dict[str, list[float]],
) -> None:
    left = _series_ref(condition.left)
    right = _series_ref(condition.right)
    values = _passing_values(condition.operator, _constant_value(condition.right))

    if left is not None and right is not None:
        _set_series(left, values[0], fields, indicators)
        _set_series(right, values[1], fields, indicators)
        return
    if left is not None:
        _set_series(left, values[0], fields, indicators)
        return
    if right is not None:
        _set_series(right, values[1], fields, indicators)


def _force_condition_fail(
    condition: BuilderCondition,
    protected_refs: set[tuple[str, str]],
    fields: dict[str, list[float]],
    indicators: dict[str, list[float]],
) -> None:
    left = _series_ref(condition.left)
    right = _series_ref(condition.right)
    if left is not None and left not in protected_refs:
        other = _operand_current_value(condition.right, fields, indicators)
        _set_series(left, _failing_left_values(condition.operator, other), fields, indicators)
        return
    if right is not None and right not in protected_refs:
        other = _operand_current_value(condition.left, fields, indicators)
        _set_series(right, _failing_right_values(condition.operator, other), fields, indicators)


def _passing_values(
    operator: ConditionOperator,
    right_constant: float | None,
) -> tuple[list[float], list[float]]:
    base = right_constant if right_constant is not None else 100.0
    if operator in {ConditionOperator.GREATER_THAN, ConditionOperator.GREATER_EQUAL}:
        return [base - 1.0, base + 1.0], [base, base]
    if operator in {ConditionOperator.LESS_THAN, ConditionOperator.LESS_EQUAL}:
        return [base + 1.0, base - 1.0], [base, base]
    if operator == ConditionOperator.CROSS_BELOW:
        return [base + 1.0, base - 1.0], [base, base]
    if operator == ConditionOperator.EQUALS:
        return [base, base], [base, base]
    return [base - 1.0, base + 1.0], [base, base]


def _failing_left_values(operator: ConditionOperator, other: float | None) -> list[float]:
    base = 100.0 if other is None else other
    if operator in {
        ConditionOperator.GREATER_THAN,
        ConditionOperator.GREATER_EQUAL,
        ConditionOperator.CROSS_ABOVE,
    }:
        return [base - 1.0, base - 1.0]
    if operator in {
        ConditionOperator.LESS_THAN,
        ConditionOperator.LESS_EQUAL,
        ConditionOperator.CROSS_BELOW,
    }:
        return [base + 1.0, base + 1.0]
    return [base + 1.0, base + 1.0]


def _failing_right_values(operator: ConditionOperator, other: float | None) -> list[float]:
    base = 100.0 if other is None else other
    if operator in {
        ConditionOperator.GREATER_THAN,
        ConditionOperator.GREATER_EQUAL,
        ConditionOperator.CROSS_ABOVE,
    }:
        return [base + 1.0, base + 1.0]
    if operator in {
        ConditionOperator.LESS_THAN,
        ConditionOperator.LESS_EQUAL,
        ConditionOperator.CROSS_BELOW,
    }:
        return [base - 1.0, base - 1.0]
    return [base + 1.0, base + 1.0]


def _constant_value(operand: ConditionOperand) -> float | None:
    return float(operand.value) if operand.type == OperandType.VALUE and operand.value is not None else None


def _operand_current_value(
    operand: ConditionOperand,
    fields: dict[str, list[float]],
    indicators: dict[str, list[float]],
) -> float | None:
    if operand.type == OperandType.VALUE and operand.value is not None:
        return float(operand.value)
    ref = _series_ref(operand)
    if ref is None:
        return None
    source = fields if ref[0] == "field" else indicators
    values = source.get(ref[1])
    if not values:
        return None
    return float(values[-1])


def _series_ref(operand: ConditionOperand) -> tuple[str, str] | None:
    if operand.type == OperandType.PRICE:
        return "field", str(operand.price_field or "close")
    if operand.type == OperandType.INDICATOR:
        return "indicator", f"{operand.indicator_alias}.{operand.indicator_output}"
    return None


def _set_series(
    ref: tuple[str, str],
    values: list[float],
    fields: dict[str, list[float]],
    indicators: dict[str, list[float]],
) -> None:
    target = fields if ref[0] == "field" else indicators
    target[ref[1]] = [float(values[0]), float(values[1])]
