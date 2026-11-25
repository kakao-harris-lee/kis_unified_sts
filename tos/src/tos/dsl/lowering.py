"""Typed-algebra -> candidate-AST lowering (design #31 §3.5 D4 / §9-4 seam closure)."""

from __future__ import annotations

from tos.dsl.candidate import CandidateNode, CandidateProgram
from tos.dsl.strategy import AuthoredStrategy
from tos.dsl.vocabulary import (
    KIND_COMPARE,
    KIND_CONST,
    KIND_CONTEXT_REF,
    KIND_NO_ACTION,
    KIND_POLICY,
    KIND_PROPOSE_ACTION,
    KIND_PROPOSE_FLAT,
    KIND_PROPOSE_VECTOR,
    KIND_RULE,
    KIND_TARGET,
    Compare,
    Decision,
    DecisionKind,
    DecisionPolicy,
    Operand,
    Rule,
    TargetSpec,
)

__all__ = ["lower_strategy"]


def _lower_operand(operand: Operand) -> CandidateNode:
    """Lower one authored :class:`Operand` (design §3.5)."""
    if operand.ref is not None:
        return CandidateNode(kind=KIND_CONTEXT_REF, source=operand.ref[0])
    return CandidateNode(kind=KIND_CONST)


def _lower_compare(compare: Compare) -> CandidateNode:
    """Lower one :class:`Compare` to a ``compare`` node over its two lowered operands."""
    return CandidateNode(
        kind=KIND_COMPARE,
        children=(_lower_operand(compare.left), _lower_operand(compare.right)),
    )


def _lower_target(target: TargetSpec) -> CandidateNode:
    """Lower one :class:`TargetSpec` to a bare ``target`` node (structural only)."""
    del target
    return CandidateNode(kind=KIND_TARGET)


def _lower_decision(decision: Decision) -> CandidateNode:
    """Lower one :class:`Decision` to its ``propose_*`` / ``no_action`` node (design §3.5)."""
    if decision.kind is DecisionKind.NO_ACTION:
        return CandidateNode(kind=KIND_NO_ACTION)
    if decision.kind is DecisionKind.ACTION:
        target = decision.target
        if (
            target is None
        ):  # pragma: no cover - Decision._shape_consistent guarantees this
            return CandidateNode(kind=KIND_NO_ACTION)
        return CandidateNode(
            kind=KIND_PROPOSE_ACTION, children=(_lower_target(target),)
        )
    if decision.kind is DecisionKind.FLAT:
        target = decision.target
        if (
            target is None
        ):  # pragma: no cover - Decision._shape_consistent guarantees this
            return CandidateNode(kind=KIND_NO_ACTION)
        return CandidateNode(kind=KIND_PROPOSE_FLAT, children=(_lower_target(target),))
    return CandidateNode(
        kind=KIND_PROPOSE_VECTOR,
        children=tuple(_lower_target(target) for target in decision.vector),
    )


def _lower_rule(rule: Rule) -> CandidateNode:
    """Lower one :class:`Rule` to a ``rule`` node over its guard compares + its decision."""
    children = tuple(_lower_compare(compare) for compare in rule.all_of) + (
        _lower_decision(rule.decision),
    )
    return CandidateNode(kind=KIND_RULE, children=children)


def _lower_policy(policy: DecisionPolicy) -> CandidateNode:
    """Lower a whole :class:`DecisionPolicy` to a ``policy`` node (design #31 §9-4)."""
    children = tuple(_lower_rule(rule) for rule in policy.rules) + (
        _lower_decision(policy.default),
    )
    return CandidateNode(kind=KIND_POLICY, children=children)


def lower_strategy(strategy: AuthoredStrategy) -> CandidateProgram:
    """Lower an Authored Strategy's embedded policy to a candidate program (design #31 §9-4)."""
    if strategy.policy is None:
        return CandidateProgram(nodes=(CandidateNode(kind=KIND_NO_ACTION),))
    return CandidateProgram(nodes=(_lower_policy(strategy.policy),))
