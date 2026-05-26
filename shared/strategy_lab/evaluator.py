"""Current-value signal evaluator for Strategy Lab drafts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from shared.strategy_lab.schema import (
    ConditionOperator,
    ConditionSpec,
    LabSignal,
    MarketSnapshot,
    Operand,
    RuleEvaluation,
    RuleGroup,
    SignalSide,
    StrategySpec,
)


@dataclass(frozen=True)
class GroupResult:
    passed: bool
    total: int
    passed_count: int
    evaluations: list[RuleEvaluation]
    missing: list[str]


class StrategyLabEvaluator:
    """Evaluate a visual-builder spec against latest symbol snapshots."""

    def draft_id(self, spec: StrategySpec) -> str:
        payload = spec.model_dump_json(exclude_none=True)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return f"draft_{digest}"

    def generate_signals(
        self,
        spec: StrategySpec,
        snapshots: list[MarketSnapshot],
        *,
        source: str = "preview",
    ) -> list[LabSignal]:
        draft_id = self.draft_id(spec)
        signals: list[LabSignal] = []
        for snapshot in snapshots:
            entry = self.evaluate_group(spec.entry, snapshot)
            exit_ = self.evaluate_group(spec.exit, snapshot)

            if exit_.passed:
                side = SignalSide.SELL
                selected = exit_
                reason = "Exit rules matched"
            elif entry.passed:
                side = SignalSide.BUY
                selected = entry
                reason = "Entry rules matched"
            else:
                side = SignalSide.HOLD
                selected = self._stronger_result(entry, exit_)
                reason = "No actionable rule group matched"

            confidence = self._confidence(selected)
            orderability = self._orderability(side, selected)
            signal = LabSignal(
                draft_id=draft_id,
                strategy_name=spec.name,
                asset_class=spec.asset_class,
                symbol=snapshot.symbol,
                name=snapshot.name,
                side=side,
                confidence=confidence,
                strength=confidence,
                reason=reason,
                reference_price=snapshot.price,
                risk_snapshot=spec.risk.model_dump(exclude_none=True),
                source=source,  # type: ignore[arg-type]
                orderability=orderability,
                matched_rules=selected.evaluations,
                indicator_values=dict(snapshot.indicators),
            )
            signals.append(signal)
        return signals

    def evaluate_group(self, group: RuleGroup, snapshot: MarketSnapshot) -> GroupResult:
        evaluations: list[RuleEvaluation] = []
        total = 0
        passed_count = 0
        missing: list[str] = []

        for condition in group.conditions:
            evaluation = self.evaluate_condition(condition, snapshot)
            evaluations.append(evaluation)
            total += 1
            if evaluation.passed:
                passed_count += 1
            missing.extend(evaluation.missing)

        for child in group.groups:
            child_result = self.evaluate_group(child, snapshot)
            evaluations.extend(child_result.evaluations)
            total += max(child_result.total, 1)
            if child_result.passed:
                passed_count += max(child_result.total, 1)
            missing.extend(child_result.missing)

        if group.operator.value == "all":
            passed = total > 0 and passed_count == total and not missing
        else:
            passed = passed_count > 0 and not missing

        return GroupResult(
            passed=passed,
            total=total,
            passed_count=passed_count,
            evaluations=evaluations,
            missing=sorted(set(missing)),
        )

    def evaluate_condition(
        self,
        condition: ConditionSpec,
        snapshot: MarketSnapshot,
    ) -> RuleEvaluation:
        left_value, left_missing = self._resolve_operand(condition.left, snapshot)
        right_value, right_missing = self._resolve_operand(condition.right, snapshot)
        missing = left_missing + right_missing
        passed = False
        if not missing and left_value is not None and right_value is not None:
            passed = self._compare(left_value, condition.operator, right_value)

        return RuleEvaluation(
            label=condition.label or self._condition_label(condition),
            passed=passed,
            left_value=left_value,
            right_value=right_value,
            operator=condition.operator,
            missing=missing,
        )

    def _resolve_operand(
        self,
        operand: Operand,
        snapshot: MarketSnapshot,
    ) -> tuple[float | None, list[str]]:
        if operand.kind == "literal":
            return operand.value, []
        if operand.kind == "field":
            if operand.name in {"price", "close"}:
                return snapshot.price, []
            return None, [operand.name or "field"]

        name = operand.name or ""
        if name in snapshot.indicators:
            return float(snapshot.indicators[name]), []
        if name in {"price", "close"}:
            return snapshot.price, []
        return None, [name]

    def _compare(
        self,
        left: float,
        operator: ConditionOperator,
        right: float,
    ) -> bool:
        if operator == ConditionOperator.GT:
            return left > right
        if operator == ConditionOperator.GTE:
            return left >= right
        if operator == ConditionOperator.LT:
            return left < right
        if operator == ConditionOperator.LTE:
            return left <= right
        if operator == ConditionOperator.EQ:
            return left == right
        return False

    def _condition_label(self, condition: ConditionSpec) -> str:
        left = self._operand_label(condition.left)
        right = self._operand_label(condition.right)
        return f"{left} {condition.operator.value} {right}"

    def _operand_label(self, operand: Operand) -> str:
        if operand.kind == "literal":
            return str(operand.value)
        return operand.name or operand.kind

    def _confidence(self, result: GroupResult) -> float:
        if result.total <= 0 or result.missing:
            return 0.0
        ratio = result.passed_count / result.total
        return round(max(0.0, min(1.0, ratio)), 4)

    def _orderability(self, side: SignalSide, result: GroupResult) -> str:
        if result.missing:
            return "missing_data"
        if side == SignalSide.HOLD:
            return "not_actionable"
        return "paper_orderable"

    def _stronger_result(self, left: GroupResult, right: GroupResult) -> GroupResult:
        left_score = left.passed_count / left.total if left.total else 0.0
        right_score = right.passed_count / right.total if right.total else 0.0
        return left if left_score >= right_score else right


def snapshot_from_symbol_input(symbol: str, values: dict[str, Any]) -> MarketSnapshot:
    """Normalize a compact API payload into a market snapshot."""
    indicators = values.get("indicators", {})
    if not isinstance(indicators, dict):
        indicators = {}
    data = {
        "symbol": symbol,
        "name": values.get("name"),
        "price": float(values.get("price", values.get("close", 0))),
        "indicators": {k: float(v) for k, v in indicators.items()},
    }
    if values.get("timestamp") is not None:
        data["timestamp"] = values["timestamp"]
    return MarketSnapshot(**data)
