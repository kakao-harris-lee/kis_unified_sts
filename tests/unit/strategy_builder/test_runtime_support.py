"""Tests for builder_v1 streaming-runtime support detection.

Guards the retirement of cross-based builder strategies (e.g. golden_cross)
from the decoupled streaming runtime: cross_above/cross_below need cross-cycle
history the streaming engine does not provide, so they can never fire and must
be detected up front rather than masquerading as active-but-silent.
"""

from __future__ import annotations

from shared.strategy_builder.runtime_support import (
    STREAMING_UNSUPPORTED_OPERATORS,
    is_streaming_supported,
    streaming_support_reason,
    unsupported_streaming_operators,
)
from shared.strategy_builder.schema import BuilderState, ConditionOperator


def _state(
    entry_op: str = "greater_than", exit_op: str = "greater_than"
) -> BuilderState:
    """Build a parseable two-indicator BuilderState with configurable operators.

    Two SMA indicators so cross conditions are realistic (golden_cross shape).
    """
    return BuilderState.model_validate(
        {
            "metadata": {
                "id": "t",
                "name": "T",
                "description": "",
                "category": "custom",
                "tags": [],
                "author": "test",
            },
            "asset_class": "stock",
            "indicators": [
                {
                    "indicator_id": "sma",
                    "alias": "sma_fast",
                    "params": {"period": 5},
                    "output": "value",
                },
                {
                    "indicator_id": "sma",
                    "alias": "sma_slow",
                    "params": {"period": 20},
                    "output": "value",
                },
            ],
            "entry": {
                "logic": "AND",
                "conditions": [
                    {
                        "left": {
                            "type": "indicator",
                            "indicator_alias": "sma_fast",
                            "indicator_output": "value",
                        },
                        "operator": entry_op,
                        "right": {
                            "type": "indicator",
                            "indicator_alias": "sma_slow",
                            "indicator_output": "value",
                        },
                    }
                ],
            },
            "exit": {
                "logic": "AND",
                "conditions": [
                    {
                        "left": {
                            "type": "indicator",
                            "indicator_alias": "sma_fast",
                            "indicator_output": "value",
                        },
                        "operator": exit_op,
                        "right": {
                            "type": "indicator",
                            "indicator_alias": "sma_slow",
                            "indicator_output": "value",
                        },
                    }
                ],
            },
            "risk": {
                "order_amount": 1_000_000,
                "stop_loss": {"enabled": True, "percent": 5.0},
                "take_profit": {"enabled": False, "percent": 10.0},
                "trailing_stop": {"enabled": False, "percent": 3.0},
            },
        }
    )


def test_cross_operators_are_the_unsupported_set() -> None:
    assert set(STREAMING_UNSUPPORTED_OPERATORS) == {
        ConditionOperator.CROSS_ABOVE,
        ConditionOperator.CROSS_BELOW,
    }


def test_golden_cross_entry_is_unsupported() -> None:
    # golden_cross: entry cross_above, exit cross_below.
    state = _state(entry_op="cross_above", exit_op="cross_below")
    ops = unsupported_streaming_operators(state)
    assert ops == [ConditionOperator.CROSS_ABOVE, ConditionOperator.CROSS_BELOW]
    assert is_streaming_supported(state) is False
    reason = streaming_support_reason(state)
    assert reason is not None
    assert "cross_above" in reason and "cross_below" in reason


def test_cross_above_only_in_entry_is_unsupported() -> None:
    state = _state(entry_op="cross_above", exit_op="greater_than")
    assert unsupported_streaming_operators(state) == [ConditionOperator.CROSS_ABOVE]
    assert is_streaming_supported(state) is False


def test_cross_below_only_in_exit_is_unsupported() -> None:
    state = _state(entry_op="greater_than", exit_op="cross_below")
    assert unsupported_streaming_operators(state) == [ConditionOperator.CROSS_BELOW]
    assert is_streaming_supported(state) is False


def test_non_cross_strategy_is_supported() -> None:
    # Threshold comparisons (rsi > 30 style) work fine on scalar-per-cycle data.
    state = _state(entry_op="greater_than", exit_op="less_than")
    assert unsupported_streaming_operators(state) == []
    assert is_streaming_supported(state) is True
    assert streaming_support_reason(state) is None
