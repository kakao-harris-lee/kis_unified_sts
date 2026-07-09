"""Evaluator for no-code Strategy Builder states."""

from __future__ import annotations

import hashlib
import math

from shared.strategy_builder.schema import (
    PERCENTILE_OPERATORS,
    BuilderCondition,
    BuilderSignal,
    BuilderState,
    ConditionEvaluation,
    ConditionLogic,
    ConditionOperand,
    ConditionOperator,
    OperandType,
    SignalSide,
    SymbolSeries,
)
from shared.strategy_lab.schema import LabSignal
from shared.strategy_lab.schema import SignalSide as LabSignalSide


class StrategyBuilderEvaluator:
    """Evaluate BuilderState rules against symbol series."""

    def draft_id(self, state: BuilderState) -> str:
        digest = self.state_hash(state)[:16]
        return f"draft_{digest}"

    def state_hash(self, state: BuilderState) -> str:
        payload = state.model_dump_json(exclude_none=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def generate_signals(
        self,
        state: BuilderState,
        series: list[SymbolSeries],
    ) -> list[BuilderSignal]:
        draft_id = self.draft_id(state)
        state_hash = self.state_hash(state)
        signals: list[BuilderSignal] = []
        for item in series:
            entry = self.evaluate_group(state.entry.conditions, state.entry.logic, item)
            exit_ = self.evaluate_group(state.exit.conditions, state.exit.logic, item)

            if exit_.passed:
                side = SignalSide.SELL
                selected = exit_
                reason = "Exit conditions matched"
            elif entry.passed:
                side = SignalSide.BUY
                selected = entry
                reason = "Entry conditions matched"
            else:
                side = SignalSide.HOLD
                selected = entry if entry.score >= exit_.score else exit_
                reason = "No actionable condition group matched"

            strength = selected.score
            signal = BuilderSignal(
                draft_id=draft_id,
                builder_state_hash=state_hash,
                strategy_name=state.metadata.name,
                asset_class=state.asset_class,
                symbol=item.symbol,
                name=item.name,
                side=side,
                strength=strength,
                reason=reason,
                reference_price=self._latest(item.fields.get("close")) or self._latest_any(item),
                orderability=self._orderability(side, selected.missing),
                matched_conditions=selected.evaluations,
                indicator_values=self._latest_indicators(item),
            )
            signals.append(signal)
        return signals

    def evaluate_group(
        self,
        conditions: list[BuilderCondition],
        logic: ConditionLogic,
        series: SymbolSeries,
    ) -> _GroupEvaluation:
        evaluations = [self.evaluate_condition(condition, series) for condition in conditions]
        if not evaluations:
            return _GroupEvaluation(False, 0.0, [], ["no_conditions"])

        passed_count = sum(1 for evaluation in evaluations if evaluation.passed)
        missing = sorted({missing for evaluation in evaluations for missing in evaluation.missing})
        if logic == ConditionLogic.AND:
            passed = passed_count == len(evaluations) and not missing
        else:
            passed = passed_count > 0 and not missing
        score = 0.0 if missing else passed_count / len(evaluations)
        return _GroupEvaluation(passed, round(score, 4), evaluations, missing)

    def evaluate_condition(
        self,
        condition: BuilderCondition,
        series: SymbolSeries,
    ) -> ConditionEvaluation:
        left_values, left_missing = self._resolve_operand(condition.left, series)
        right_values, right_missing = self._resolve_operand(condition.right, series)
        missing = left_missing + right_missing

        if condition.operator in PERCENTILE_OPERATORS:
            return self._evaluate_percentile_condition(
                condition, left_values, right_values, missing
            )

        current_left = self._latest(left_values)
        current_right = self._latest(right_values)
        previous_left = self._previous(left_values)
        previous_right = self._previous(right_values)
        passed = False
        if not missing and current_left is not None and current_right is not None:
            passed = self._compare(
                condition.operator,
                current_left,
                current_right,
                previous_left,
                previous_right,
            )

        return ConditionEvaluation(
            condition_id=condition.id,
            label=self._condition_label(condition),
            passed=passed,
            left_value=current_left,
            right_value=current_right,
            previous_left_value=previous_left,
            previous_right_value=previous_right,
            missing=missing,
        )

    def _evaluate_percentile_condition(
        self,
        condition: BuilderCondition,
        left_values: list[float] | None,
        right_values: list[float] | None,
        missing: list[str],
    ) -> ConditionEvaluation:
        """Evaluate a percentile_rank_* condition (schema v2).

        Computes the percentile rank (0-100, inclusive of the value itself) of
        the latest left-operand value within the trailing ``condition.window``
        bars, then compares it against the right-operand threshold. Windows
        with too little (finite) history report a ``missing`` marker so the
        condition group fails safe — mirroring absent-indicator behavior.

        Args:
            condition: Percentile condition (window validated by the schema).
            left_values: Resolved left-operand series (or None when missing).
            right_values: Resolved right-operand values (threshold constant).
            missing: Missing-operand markers accumulated by the caller.

        Returns:
            ConditionEvaluation whose ``left_value`` is the computed rank and
            ``right_value`` the threshold.
        """
        window = int(condition.window or 0)
        threshold = self._latest(right_values)
        rank: float | None = None
        missing = list(missing)

        if not missing:
            label = self._operand_label(condition.left)
            if left_values is None or len(left_values) < window:
                missing.append(f"{label}[window={window}]")
            else:
                window_values = [
                    float(value)
                    for value in left_values[-window:]
                    if math.isfinite(float(value))
                ]
                current = float(left_values[-1])
                if not math.isfinite(current) or len(window_values) < 2:
                    missing.append(f"{label}[window={window}]")
                else:
                    below_or_equal = sum(
                        1 for value in window_values if value <= current
                    )
                    rank = round(100.0 * below_or_equal / len(window_values), 4)

        passed = False
        if not missing and rank is not None and threshold is not None:
            if condition.operator == ConditionOperator.PERCENTILE_RANK_ABOVE:
                passed = rank >= threshold
            else:
                passed = rank <= threshold

        return ConditionEvaluation(
            condition_id=condition.id,
            label=self._condition_label(condition),
            passed=passed,
            left_value=rank,
            right_value=threshold,
            previous_left_value=None,
            previous_right_value=None,
            missing=missing,
        )

    def to_lab_signal(self, signal: BuilderSignal) -> LabSignal:
        return LabSignal(
            signal_id=signal.signal_id,
            draft_id=signal.draft_id,
            strategy_name=signal.strategy_name,
            asset_class=signal.asset_class,
            symbol=signal.symbol,
            name=signal.name,
            side=LabSignalSide(signal.side.value),
            confidence=signal.strength,
            strength=signal.strength,
            reason=signal.reason,
            reference_price=signal.reference_price,
            risk_snapshot={},
            orderability=signal.orderability,
            matched_rules=[],
            indicator_values=signal.indicator_values,
        )

    def _resolve_operand(
        self,
        operand: ConditionOperand,
        series: SymbolSeries,
    ) -> tuple[list[float] | None, list[str]]:
        if operand.type == OperandType.VALUE:
            value = float(operand.value or 0.0)
            return [value, value], []
        if operand.type == OperandType.PRICE:
            key = operand.price_field or "close"
            values = series.fields.get(key)
            return (values, []) if values else (None, [key])
        key = f"{operand.indicator_alias}.{operand.indicator_output}"
        values = series.indicators.get(key)
        if values:
            return values, []
        fallback_values = series.indicators.get(str(operand.indicator_alias))
        if fallback_values:
            return fallback_values, []
        return None, [key]

    def _compare(
        self,
        operator: ConditionOperator,
        left: float,
        right: float,
        previous_left: float | None,
        previous_right: float | None,
    ) -> bool:
        if operator == ConditionOperator.GREATER_THAN:
            return left > right
        if operator == ConditionOperator.LESS_THAN:
            return left < right
        if operator == ConditionOperator.GREATER_EQUAL:
            return left >= right
        if operator == ConditionOperator.LESS_EQUAL:
            return left <= right
        if operator == ConditionOperator.EQUALS:
            return left == right
        if operator == ConditionOperator.CROSS_ABOVE:
            return previous_left is not None and previous_right is not None and previous_left <= previous_right and left > right
        if operator == ConditionOperator.CROSS_BELOW:
            return previous_left is not None and previous_right is not None and previous_left >= previous_right and left < right
        return False

    def _condition_label(self, condition: BuilderCondition) -> str:
        operator_label = condition.operator.value
        if condition.operator in PERCENTILE_OPERATORS:
            operator_label = f"{operator_label}(window={condition.window})"
        return (
            f"{self._operand_label(condition.left)} "
            f"{operator_label} "
            f"{self._operand_label(condition.right)}"
        )

    def _operand_label(self, operand: ConditionOperand) -> str:
        if operand.type == OperandType.VALUE:
            return str(operand.value)
        if operand.type == OperandType.PRICE:
            return str(operand.price_field)
        return f"{operand.indicator_alias}.{operand.indicator_output}"

    def _latest(self, values: list[float] | None) -> float | None:
        if not values:
            return None
        return float(values[-1])

    def _previous(self, values: list[float] | None) -> float | None:
        if not values or len(values) < 2:
            return None
        return float(values[-2])

    def _latest_any(self, series: SymbolSeries) -> float:
        for values in series.fields.values():
            latest = self._latest(values)
            if latest is not None:
                return latest
        raise ValueError(f"No price field values for {series.symbol}")

    def _latest_indicators(self, series: SymbolSeries) -> dict[str, float]:
        return {
            key: float(values[-1])
            for key, values in series.indicators.items()
            if values
        }

    def _orderability(self, side: SignalSide, missing: list[str]) -> str:
        if missing:
            return "missing_data"
        if side == SignalSide.HOLD:
            return "not_actionable"
        return "paper_orderable"


class _GroupEvaluation:
    def __init__(
        self,
        passed: bool,
        score: float,
        evaluations: list[ConditionEvaluation],
        missing: list[str],
    ) -> None:
        self.passed = passed
        self.score = score
        self.evaluations = evaluations
        self.missing = missing
