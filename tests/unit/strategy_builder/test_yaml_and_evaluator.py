"""Strategy Builder schema, YAML, and evaluator tests."""

from shared.strategy_builder.evaluator import StrategyBuilderEvaluator
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
    SignalSide,
    SymbolSeries,
)
from shared.strategy_builder.yaml_io import builder_state_to_yaml, yaml_to_builder_state


def _golden_cross_state() -> BuilderState:
    return BuilderState(
        metadata=BuilderMetadata(id="golden_cross_test", name="Golden Cross Test"),
        indicators=[
            BuilderIndicator(
                indicator_id="sma", alias="sma_fast", params={"period": 5}
            ),
            BuilderIndicator(
                indicator_id="sma", alias="sma_slow", params={"period": 20}
            ),
        ],
        entry=BuilderConditionGroup(
            logic=ConditionLogic.AND,
            conditions=[
                BuilderCondition(
                    left=ConditionOperand(
                        type=OperandType.INDICATOR,
                        indicator_alias="sma_fast",
                    ),
                    operator=ConditionOperator.CROSS_ABOVE,
                    right=ConditionOperand(
                        type=OperandType.INDICATOR,
                        indicator_alias="sma_slow",
                    ),
                )
            ],
        ),
        exit=BuilderConditionGroup(
            logic=ConditionLogic.AND,
            conditions=[
                BuilderCondition(
                    left=ConditionOperand(
                        type=OperandType.INDICATOR,
                        indicator_alias="sma_fast",
                    ),
                    operator=ConditionOperator.CROSS_BELOW,
                    right=ConditionOperand(
                        type=OperandType.INDICATOR,
                        indicator_alias="sma_slow",
                    ),
                )
            ],
        ),
    )


def test_builder_yaml_roundtrip_preserves_indicator_cross_condition():
    state = _golden_cross_state()
    yaml_text = builder_state_to_yaml(state)
    restored = yaml_to_builder_state(yaml_text)

    assert restored.metadata.id == "golden_cross_test"
    assert [indicator.alias for indicator in restored.indicators] == [
        "sma_fast",
        "sma_slow",
    ]
    assert restored.entry.conditions[0].operator == ConditionOperator.CROSS_ABOVE
    assert restored.exit.conditions[0].operator == ConditionOperator.CROSS_BELOW


def test_evaluator_handles_cross_above_buy_signal():
    state = _golden_cross_state()
    series = SymbolSeries(
        symbol="005930",
        fields={"close": [69000, 71000]},
        indicators={
            "sma_fast.value": [99.0, 101.0],
            "sma_slow.value": [100.0, 100.0],
        },
    )

    signal = StrategyBuilderEvaluator().generate_signals(state, [series])[0]

    assert signal.side == SignalSide.BUY
    assert signal.orderability == "paper_orderable"
    assert signal.matched_conditions[0].passed is True


def test_evaluator_reports_missing_indicator_data():
    state = _golden_cross_state()
    series = SymbolSeries(symbol="005930", fields={"close": [69000, 71000]})

    signal = StrategyBuilderEvaluator().generate_signals(state, [series])[0]

    assert signal.side == SignalSide.HOLD
    assert signal.orderability == "missing_data"
    assert "sma_fast.value" in signal.matched_conditions[0].missing


def test_evaluator_crosses_static_threshold():
    state = BuilderState(
        metadata=BuilderMetadata(id="rsi_cross", name="RSI Cross"),
        indicators=[
            BuilderIndicator(indicator_id="rsi", alias="rsi", params={"period": 14}),
        ],
        entry=BuilderConditionGroup(
            conditions=[
                BuilderCondition(
                    left=ConditionOperand(
                        type=OperandType.INDICATOR,
                        indicator_alias="rsi",
                    ),
                    operator=ConditionOperator.CROSS_ABOVE,
                    right=ConditionOperand(type=OperandType.VALUE, value=30),
                )
            ]
        ),
        exit=BuilderConditionGroup(conditions=[]),
    )

    signal = StrategyBuilderEvaluator().generate_signals(
        state,
        [
            SymbolSeries(
                symbol="005930",
                fields={"close": [70000, 70100]},
                indicators={"rsi.value": [29.5, 31.0]},
            )
        ],
    )[0]

    assert signal.side == SignalSide.BUY
