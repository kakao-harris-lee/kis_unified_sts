"""Evaluator tests for the percentile_rank_* operators (schema v2)."""

from __future__ import annotations

from shared.strategy_builder.evaluator import StrategyBuilderEvaluator
from shared.strategy_builder.schema import (
    BuilderCondition,
    ConditionOperand,
    ConditionOperator,
    OperandType,
    SymbolSeries,
)


def _condition(
    operator: ConditionOperator,
    threshold: float,
    window: int,
) -> BuilderCondition:
    return BuilderCondition(
        id="cond_pct",
        left=ConditionOperand(type=OperandType.INDICATOR, indicator_alias="atr"),
        operator=operator,
        right=ConditionOperand(type=OperandType.VALUE, value=threshold),
        window=window,
    )


def _series(values: list[float]) -> SymbolSeries:
    return SymbolSeries(
        symbol="101S6000",
        fields={"close": [100.0] * len(values)},
        indicators={"atr.value": values},
    )


def test_percentile_rank_above_passes_when_latest_is_extreme() -> None:
    evaluator = StrategyBuilderEvaluator()
    # Latest value 10 is the max of the 5-bar window -> rank 100.
    values = [1.0, 2.0, 3.0, 4.0, 10.0]
    result = evaluator.evaluate_condition(
        _condition(ConditionOperator.PERCENTILE_RANK_ABOVE, 90.0, 5),
        _series(values),
    )
    assert result.passed
    assert result.left_value == 100.0
    assert result.right_value == 90.0
    assert result.missing == []


def test_percentile_rank_above_fails_for_mid_range_value() -> None:
    evaluator = StrategyBuilderEvaluator()
    # Latest 3 ranks 3/5 = 60 within the window -> below the 90 threshold.
    values = [1.0, 2.0, 5.0, 4.0, 3.0]
    result = evaluator.evaluate_condition(
        _condition(ConditionOperator.PERCENTILE_RANK_ABOVE, 90.0, 5),
        _series(values),
    )
    assert not result.passed
    assert result.left_value == 60.0


def test_percentile_rank_below_symmetry() -> None:
    evaluator = StrategyBuilderEvaluator()
    # Latest 1 is the min of the window -> rank 20 (1 of 5 <= it).
    values = [5.0, 4.0, 3.0, 2.0, 1.0]
    result = evaluator.evaluate_condition(
        _condition(ConditionOperator.PERCENTILE_RANK_BELOW, 20.0, 5),
        _series(values),
    )
    assert result.passed
    assert result.left_value == 20.0


def test_percentile_uses_trailing_window_only() -> None:
    evaluator = StrategyBuilderEvaluator()
    # Huge early value sits outside the trailing 3-bar window and must not
    # deflate the rank: window [2, 3, 4] -> latest 4 ranks 100.
    values = [1000.0, 1.0, 2.0, 3.0, 4.0]
    result = evaluator.evaluate_condition(
        _condition(ConditionOperator.PERCENTILE_RANK_ABOVE, 99.0, 3),
        _series(values),
    )
    assert result.passed
    assert result.left_value == 100.0


def test_percentile_insufficient_history_reports_missing() -> None:
    evaluator = StrategyBuilderEvaluator()
    result = evaluator.evaluate_condition(
        _condition(ConditionOperator.PERCENTILE_RANK_ABOVE, 90.0, 10),
        _series([1.0, 2.0, 3.0]),
    )
    assert not result.passed
    assert result.missing == ["atr.value[window=10]"]


def test_percentile_nan_warmup_values_are_filtered() -> None:
    evaluator = StrategyBuilderEvaluator()
    # NaN warmup bars inside the window are dropped; rank runs over the
    # remaining finite values ([2, 3, 9] -> latest 9 ranks 100).
    values = [float("nan"), float("nan"), 2.0, 3.0, 9.0]
    result = evaluator.evaluate_condition(
        _condition(ConditionOperator.PERCENTILE_RANK_ABOVE, 90.0, 5),
        _series(values),
    )
    assert result.passed
    assert result.left_value == 100.0


def test_percentile_nan_latest_value_is_missing() -> None:
    evaluator = StrategyBuilderEvaluator()
    values = [1.0, 2.0, 3.0, 4.0, float("nan")]
    result = evaluator.evaluate_condition(
        _condition(ConditionOperator.PERCENTILE_RANK_ABOVE, 90.0, 5),
        _series(values),
    )
    assert not result.passed
    assert result.missing == ["atr.value[window=5]"]


def test_percentile_missing_indicator_fails_safe() -> None:
    evaluator = StrategyBuilderEvaluator()
    series = SymbolSeries(symbol="101S6000", fields={}, indicators={})
    result = evaluator.evaluate_condition(
        _condition(ConditionOperator.PERCENTILE_RANK_ABOVE, 90.0, 5),
        series,
    )
    assert not result.passed
    assert "atr.value" in result.missing


def test_percentile_label_includes_window() -> None:
    evaluator = StrategyBuilderEvaluator()
    result = evaluator.evaluate_condition(
        _condition(ConditionOperator.PERCENTILE_RANK_ABOVE, 90.0, 120),
        _series([1.0] * 120),
    )
    assert result.label == "atr.value percentile_rank_above(window=120) 90.0"
