"""Schema v2 dashboard endpoint tests: capabilities discovery + validation."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.dashboard.routes.strategy_builder import (
    get_capabilities,
    validate_state,
)
from shared.strategy_builder.schema import (
    BuilderCondition,
    BuilderConditionGroup,
    BuilderIndicator,
    BuilderMetadata,
    BuilderState,
    ConditionOperand,
    ConditionOperator,
    ExitPrimitiveRef,
    OperandType,
)


def _state(**overrides) -> BuilderState:
    base = {
        "metadata": BuilderMetadata(id="v2_route_test", name="V2 Route Test"),
        "asset_class": "stock",
        "indicators": [BuilderIndicator(indicator_id="rsi", alias="rsi")],
        "entry": BuilderConditionGroup(
            conditions=[
                BuilderCondition(
                    left=ConditionOperand(
                        type=OperandType.INDICATOR, indicator_alias="rsi"
                    ),
                    operator=ConditionOperator.LESS_THAN,
                    right=ConditionOperand(type=OperandType.VALUE, value=30.0),
                )
            ]
        ),
        "exit": BuilderConditionGroup(conditions=[]),
    }
    base.update(overrides)
    return BuilderState(**base)


@pytest.mark.asyncio
async def test_capabilities_endpoint_exposes_v2_vocabulary() -> None:
    capabilities = await get_capabilities()
    assert ConditionOperator.PERCENTILE_RANK_ABOVE in capabilities.operators
    assert capabilities.directions == ["long", "short"]
    assert {p.id for p in capabilities.exit_primitives} >= {
        "three_stage",
        "atr_dynamic",
        "chandelier_exit",
        "momentum_decay",
    }
    assert "regime_gate" in capabilities.gate_fields


@pytest.mark.asyncio
async def test_validate_accepts_registered_exit_primitive() -> None:
    response = await validate_state(
        _state(exit_primitive=ExitPrimitiveRef(primitive="atr_dynamic"))
    )
    assert response.valid
    assert response.errors == []


@pytest.mark.asyncio
async def test_validate_rejects_unknown_exit_primitive() -> None:
    response = await validate_state(
        _state(exit_primitive=ExitPrimitiveRef(primitive="not_a_real_exit"))
    )
    assert not response.valid
    assert response.errors
    assert "not_a_real_exit" in response.errors[0]
    assert "Available" in response.errors[0]


@pytest.mark.asyncio
async def test_validate_rejects_asset_restricted_primitive() -> None:
    state = _state(
        asset_class="futures",
        exit_primitive=ExitPrimitiveRef(primitive="three_stage"),
    )
    response = await validate_state(state)
    assert not response.valid
    assert "three_stage" in response.errors[0]


@pytest.mark.asyncio
async def test_validate_short_only_state_has_no_empty_entry_warning() -> None:
    state = _state(
        asset_class="futures",
        entry=BuilderConditionGroup(conditions=[]),
        entry_short=BuilderConditionGroup(
            conditions=[
                BuilderCondition(
                    left=ConditionOperand(
                        type=OperandType.INDICATOR, indicator_alias="rsi"
                    ),
                    operator=ConditionOperator.GREATER_THAN,
                    right=ConditionOperand(type=OperandType.VALUE, value=70.0),
                )
            ]
        ),
    )
    response = await validate_state(state)
    assert response.valid
    assert "Entry conditions are empty." not in response.warnings


def test_register_paper_rejects_unknown_exit_primitive() -> None:
    from services.dashboard.routes.kis_builder import _validate_builder_state

    state = _state(exit_primitive=ExitPrimitiveRef(primitive="not_a_real_exit"))
    with pytest.raises(HTTPException) as excinfo:
        _validate_builder_state(state.model_dump(mode="json"))
    assert excinfo.value.status_code == 400
    assert "not_a_real_exit" in str(excinfo.value.detail)
