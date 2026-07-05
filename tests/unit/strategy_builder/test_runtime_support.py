"""Tests for builder_v1 runtime-support detection.

Since the declarative Indicator Context feeds the evaluator the full indicator
series, cross_above/cross_below now work in every runtime that runs builder_v1.
The unsupported-operator set is therefore empty and every state reports as
supported; these tests pin that (and that the extensible scan still works).
"""

from __future__ import annotations

from shared.strategy_builder.runtime_support import (
    STREAMING_UNSUPPORTED_OPERATORS,
    is_streaming_supported,
    streaming_support_reason,
    unsupported_streaming_operators,
)
from shared.strategy_builder.schema import BuilderState


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


def test_unsupported_operator_set_is_empty() -> None:
    assert set(STREAMING_UNSUPPORTED_OPERATORS) == set()


def test_golden_cross_is_now_supported() -> None:
    # golden_cross (entry cross_above, exit cross_below) fires via the
    # full-series Indicator Context — no longer flagged as unsupported.
    state = _state(entry_op="cross_above", exit_op="cross_below")
    assert unsupported_streaming_operators(state) == []
    assert is_streaming_supported(state) is True
    assert streaming_support_reason(state) is None


def test_threshold_strategy_is_supported() -> None:
    state = _state(entry_op="greater_than", exit_op="less_than")
    assert unsupported_streaming_operators(state) == []
    assert is_streaming_supported(state) is True
    assert streaming_support_reason(state) is None
