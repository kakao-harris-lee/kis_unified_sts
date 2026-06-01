"""BuilderState must accept the frontend's camelCase payload (and still
accept snake_case), while dumping snake_case for the runtime/YAML."""
from __future__ import annotations

from shared.strategy_builder.schema import BuilderState


def _camel_payload() -> dict:
    return {
        "metadata": {
            "id": "t_strat",
            "name": "T",
            "description": "",
            "category": "custom",
            "tags": ["x"],
            "author": "u",
        },
        "assetClass": "stock",
        "indicators": [
            {
                "id": "i1",
                "indicatorId": "rsi",
                "alias": "rsi",
                "displayName": "RSI",
                "params": {},
                "output": "value",
            }
        ],
        "entry": {
            "logic": "AND",
            "conditions": [
                {
                    "id": "c1",
                    "left": {
                        "type": "indicator",
                        "indicatorAlias": "rsi",
                        "indicatorOutput": "value",
                    },
                    "operator": "greater_than",
                    "right": {"type": "value", "value": 30.0},
                }
            ],
        },
        "exit": {"logic": "AND", "conditions": []},
        "risk": {
            "stopLoss": {"enabled": True, "percent": 5.0},
            "takeProfit": {"enabled": False, "percent": 10.0},
            "trailingStop": {"enabled": False, "percent": 3.0},
        },
    }


def test_camelcase_payload_is_accepted() -> None:
    state = BuilderState.model_validate(_camel_payload())
    assert state.asset_class == "stock"
    assert state.indicators[0].indicator_id == "rsi"
    assert state.entry.conditions[0].left.indicator_alias == "rsi"


def test_snakecase_payload_still_accepted() -> None:
    state = BuilderState.model_validate(
        {
            "metadata": {"id": "s", "name": "S"},
            "asset_class": "futures",
            "indicators": [
                {"indicator_id": "rsi", "alias": "rsi", "params": {}, "output": "value"}
            ],
            "entry": {
                "logic": "AND",
                "conditions": [
                    {
                        "left": {"type": "indicator", "indicator_alias": "rsi"},
                        "operator": "greater_than",
                        "right": {"type": "value", "value": 30.0},
                    }
                ],
            },
            "exit": {"logic": "AND", "conditions": []},
            "risk": {"stop_loss": {"enabled": True, "percent": 5.0}},
        }
    )
    assert state.asset_class == "futures"


def test_model_dump_is_snake_case() -> None:
    state = BuilderState.model_validate(_camel_payload())
    dumped = state.model_dump(mode="json")
    assert "asset_class" in dumped
    assert "assetClass" not in dumped
    assert "indicator_id" in dumped["indicators"][0]
