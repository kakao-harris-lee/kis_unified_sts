"""Strategy Builder .kis.yaml import/export."""

from __future__ import annotations

from typing import Any

import yaml

from shared.strategy_builder.schema import (
    BuilderCondition,
    BuilderConditionGroup,
    BuilderGates,
    BuilderIndicator,
    BuilderMetadata,
    BuilderState,
    ConditionLogic,
    ConditionOperand,
    ConditionOperator,
    ExitPrimitiveRef,
    OperandType,
    RiskManagement,
    RiskToggle,
)


def builder_state_to_yaml(state: BuilderState) -> str:
    strategy: dict = {
        "id": state.metadata.id,
        "asset_class": state.asset_class,
        "category": state.metadata.category,
        "indicators": [_indicator_to_yaml(indicator) for indicator in state.indicators],
        "entry": _group_to_yaml(state.entry),
        "exit": _group_to_yaml(state.exit),
    }
    # Schema-v2 sections are emitted only when present so pre-v2 states export
    # byte-identical YAML.
    if state.entry_short is not None:
        strategy["entry_short"] = _group_to_yaml(state.entry_short)
    if state.exit_primitive is not None:
        strategy["exit_primitive"] = {
            "primitive": state.exit_primitive.primitive,
            "params": dict(state.exit_primitive.params),
        }
    if state.gates is not None:
        strategy["gates"] = state.gates.model_dump(exclude_none=True)
    data = {
        "version": "1.0",
        "metadata": {
            "id": state.metadata.id,
            "name": state.metadata.name,
            "description": state.metadata.description,
            "category": state.metadata.category,
            "tags": state.metadata.tags,
            "author": state.metadata.author,
        },
        "strategy": strategy,
        "risk": {
            "order_amount": state.risk.order_amount,
            "stop_loss": state.risk.stop_loss.model_dump(),
            "take_profit": state.risk.take_profit.model_dump(),
            "trailing_stop": state.risk.trailing_stop.model_dump(),
        },
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def yaml_to_builder_state(content: str) -> BuilderState:
    data = yaml.safe_load(content) or {}
    metadata = data.get("metadata", {})
    strategy = data.get("strategy", {})
    risk = data.get("risk", {})
    return BuilderState(
        metadata=BuilderMetadata(
            id=str(metadata.get("id") or strategy.get("id") or "custom_strategy"),
            name=str(metadata.get("name") or strategy.get("id") or "Custom Strategy"),
            description=str(metadata.get("description") or ""),
            category=str(
                metadata.get("category") or strategy.get("category") or "custom"
            ),
            tags=list(metadata.get("tags") or []),
            author=str(metadata.get("author") or "STS"),
        ),
        asset_class=strategy.get("asset_class", "stock"),
        indicators=[
            _indicator_from_yaml(item)
            for item in strategy.get("indicators", [])
            if isinstance(item, dict)
        ],
        entry=_group_from_yaml(strategy.get("entry", {})),
        entry_short=(
            _group_from_yaml(strategy["entry_short"])
            if isinstance(strategy.get("entry_short"), dict)
            else None
        ),
        exit=_group_from_yaml(strategy.get("exit", {})),
        exit_primitive=_exit_primitive_from_yaml(strategy.get("exit_primitive")),
        gates=_gates_from_yaml(strategy.get("gates")),
        risk=RiskManagement(
            order_amount=float(risk.get("order_amount", 1_000_000)),
            stop_loss=_risk_toggle(risk.get("stop_loss"), enabled=True, percent=5.0),
            take_profit=_risk_toggle(
                risk.get("take_profit"), enabled=False, percent=10.0
            ),
            trailing_stop=_risk_toggle(
                risk.get("trailing_stop"), enabled=False, percent=3.0
            ),
        ),
    )


def preview_python(state: BuilderState) -> str:
    yaml_text = builder_state_to_yaml(state)
    return "\n".join(
        [
            f"class StrategyBuilder_{_safe_identifier(state.metadata.id)}:",
            f"    name = {state.metadata.name!r}",
            f"    asset_class = {state.asset_class!r}",
            "    source = 'strategy_builder'",
            "",
            "    # Generated preview. Runtime evaluation uses BuilderState AST.",
            "    builder_yaml = '''",
            yaml_text.rstrip(),
            "    '''",
        ]
    )


def _indicator_to_yaml(indicator: BuilderIndicator) -> dict:
    return {
        "id": indicator.indicator_id,
        "alias": indicator.alias,
        "name": indicator.display_name,
        "params": indicator.params,
        "output": indicator.output,
    }


def _indicator_from_yaml(data: dict) -> BuilderIndicator:
    return BuilderIndicator(
        indicator_id=str(data.get("id")),
        alias=str(data.get("alias") or data.get("id")),
        display_name=data.get("name"),
        params=dict(data.get("params") or {}),
        output=str(data.get("output") or "value"),
    )


def _group_to_yaml(group: BuilderConditionGroup) -> dict:
    return {
        "logic": group.logic.value,
        "conditions": [_condition_to_yaml(condition) for condition in group.conditions],
    }


def _group_from_yaml(data: dict) -> BuilderConditionGroup:
    return BuilderConditionGroup(
        logic=ConditionLogic(data.get("logic", "AND")),
        conditions=[
            _condition_from_yaml(item)
            for item in data.get("conditions", [])
            if isinstance(item, dict)
        ],
    )


def _exit_primitive_from_yaml(data: object) -> ExitPrimitiveRef | None:
    if not isinstance(data, dict):
        return None
    return ExitPrimitiveRef(
        primitive=str(data.get("primitive") or ""),
        params=dict(data.get("params") or {}),
    )


def _gates_from_yaml(data: object) -> BuilderGates | None:
    if not isinstance(data, dict):
        return None
    return BuilderGates.model_validate(data)


def _condition_to_yaml(condition: BuilderCondition) -> dict:
    data: dict[str, Any] = {
        "id": condition.id,
        "left": _operand_to_yaml(condition.left),
        "operator": condition.operator.value,
        "right": _operand_to_yaml(condition.right),
    }
    if condition.window is not None:
        data["window"] = condition.window
    return data


def _condition_from_yaml(data: dict) -> BuilderCondition:
    if "left" in data and "right" in data:
        window = data.get("window")
        return BuilderCondition(
            id=str(data.get("id") or "cond_imported"),
            left=_operand_from_yaml(data["left"]),
            operator=_operator_from_value(str(data.get("operator", "greater_than"))),
            right=_operand_from_yaml(data["right"]),
            window=int(window) if window is not None else None,
        )
    indicator = str(data.get("indicator", ""))
    compare_to = data.get("compare_to", 0)
    return BuilderCondition(
        id=str(data.get("id") or "cond_imported"),
        left=ConditionOperand(
            type=OperandType.INDICATOR,
            indicator_alias=indicator,
            indicator_output=str(data.get("output") or "value"),
        ),
        operator=_operator_from_value(str(data.get("operator", "greater_than"))),
        right=_legacy_compare_operand(compare_to, data.get("compare_output")),
    )


def _operand_to_yaml(operand: ConditionOperand) -> dict:
    if operand.type == OperandType.VALUE:
        return {"type": "value", "value": operand.value}
    if operand.type == OperandType.PRICE:
        return {"type": "price", "price_field": operand.price_field}
    return {
        "type": "indicator",
        "indicator_alias": operand.indicator_alias,
        "indicator_output": operand.indicator_output,
    }


def _operand_from_yaml(data: dict) -> ConditionOperand:
    operand_type = OperandType(data.get("type", "value"))
    if operand_type == OperandType.VALUE:
        return ConditionOperand(type=operand_type, value=float(data.get("value", 0)))
    if operand_type == OperandType.PRICE:
        return ConditionOperand(
            type=operand_type, price_field=data.get("price_field", "close")
        )
    return ConditionOperand(
        type=operand_type,
        indicator_alias=str(data.get("indicator_alias")),
        indicator_output=str(data.get("indicator_output") or "value"),
    )


def _legacy_compare_operand(
    value: object, compare_output: object | None
) -> ConditionOperand:
    if isinstance(value, (int, float)):
        return ConditionOperand(type=OperandType.VALUE, value=float(value))
    if isinstance(value, str) and value in {"close", "open", "high", "low", "volume"}:
        return ConditionOperand(type=OperandType.PRICE, price_field=value)
    return ConditionOperand(
        type=OperandType.INDICATOR,
        indicator_alias=str(value),
        indicator_output=str(compare_output or "value"),
    )


def _operator_from_value(value: str) -> ConditionOperator:
    aliases = {
        ">": "greater_than",
        "<": "less_than",
        ">=": "greater_equal",
        "<=": "less_equal",
        "==": "equals",
        "gt": "greater_than",
        "lt": "less_than",
        "gte": "greater_equal",
        "lte": "less_equal",
        "eq": "equals",
        "crosses_above": "cross_above",
        "crosses_below": "cross_below",
    }
    return ConditionOperator(aliases.get(value, value))


def _risk_toggle(data: object, *, enabled: bool, percent: float) -> RiskToggle:
    if not isinstance(data, dict):
        return RiskToggle(enabled=enabled, percent=percent)
    return RiskToggle(
        enabled=bool(data.get("enabled", enabled)),
        percent=float(data.get("percent", percent)),
    )


def _safe_identifier(value: str) -> str:
    chars = [ch if ch.isalnum() or ch == "_" else "_" for ch in value]
    result = "".join(chars).strip("_") or "custom_strategy"
    if result[0].isdigit():
        result = f"strategy_{result}"
    return result
