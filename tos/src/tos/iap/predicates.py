"""iap request / decision / binding / closure / confinement predicates (design #15 §5/§6)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tos.iap.records import (
    ApprovalAuthorityEffect,
    ProposalApprovalRequest,
    TradingApprovalPolicy,
)
from tos.iap.vocabulary import ApprovalResult, MaterialityVerdict

__all__ = [
    "request_is_complete",
    "approval_decision",
    "exact_binding_holds",
    "invalidation_closure",
    "materiality_is_material",
    "unknown_confines",
    "independent_validation_declared",
    "no_widening_no_union",
    "approval_grants_no_authority",
    "active_egress_currentness",
    "conflicting_evaluators_unknown",
]


_UNKNOWN_TOKEN = "UNKNOWN"
_LATEST_TOKEN = "latest"


def _is_wildcard(value: str) -> bool:
    """Whether a scope token is a wildcard / "latest" (§9 line 253; dsl ``proposal.py:59`` isomorph)."""
    return "*" in value or value.strip().lower() == _LATEST_TOKEN


def _scope_state(value: str | None) -> str:
    """Classify one required scalar scope field (§9 line 253 / §4.1)."""
    if value is None or not value.strip():
        return "deny"
    if _is_wildcard(value):
        return "deny"
    if value.strip().upper() == _UNKNOWN_TOKEN:
        return "unknown"
    return "ok"


def request_is_complete(
    request: ProposalApprovalRequest | None,
    policy: TradingApprovalPolicy | None,
) -> ApprovalResult:
    """Whether the request is one complete, immutable, exact request (§9 / IAP-INV-001 / IAP-AC-001)."""
    if request is None:
        return ApprovalResult.DENY
    if policy is None:
        return ApprovalResult.UNKNOWN

    required_scalars: tuple[str | None, ...] = (
        request.proposer_identity,
        request.environment,
        request.account,
        request.instrument,
        request.action_class,
        request.operating_mode,
        request.direction,
        request.position_effect,
        request.quantity_basis,
        request.proposal_id,
        request.proposal_digest,
        request.decision_context_capsule_id,
        request.decision_context_capsule_digest,
        request.critical_input_snapshot_digest,
        request.construction_envelope_id,
        request.construction_envelope_digest,
        request.canonical_broker_command_id,
        request.canonical_broker_command_digest,
        request.venue_snapshot_digest,
        request.venue_admissibility_decision_digest,
        request.broker_capability_profile_digest,
        request.trading_approval_policy_id,
        request.trading_approval_policy_digest,
    )
    saw_unknown = False
    for value in required_scalars:
        state = _scope_state(value)
        if state == "deny":
            return ApprovalResult.DENY
        if state == "unknown":
            saw_unknown = True

    if request.request_generation is None:
        return ApprovalResult.DENY
    if request.trading_approval_policy_generation is None:
        return ApprovalResult.DENY
    if request.required_scope_complete is not True:
        return ApprovalResult.DENY
    if request.single_use is not True or request.exact_intent_only is not True:
        return ApprovalResult.DENY
    if not request.required_independent_facts:
        return ApprovalResult.DENY
    if not request.common_mode_declarations:
        return ApprovalResult.DENY

    if saw_unknown:
        return ApprovalResult.UNKNOWN
    return ApprovalResult.APPROVE


def approval_decision(
    request: ProposalApprovalRequest | None,
    policy: TradingApprovalPolicy | None,
    generation: int | None,
    *,
    independent_validation_passed: bool | None,
    all_bindings_current: bool | None,
    policy_supports_request: bool | None,
    generation_current: bool | None,
    conflicting_evaluations: bool | None = None,
    unverifiable_input: bool | None = None,
) -> ApprovalResult:
    """The deterministic, restrictive Independent Approval decision (§11 / IAP-INV-003 / IAP-AC-003)."""
    completeness = request_is_complete(request, policy)
    if completeness is ApprovalResult.DENY:
        return ApprovalResult.DENY

    if (
        independent_validation_passed is False
        or all_bindings_current is False
        or policy_supports_request is False
        or generation_current is False
    ):
        return ApprovalResult.DENY

    if (
        completeness is ApprovalResult.UNKNOWN
        or generation is None
        or conflicting_evaluations is True
        or unverifiable_input is True
        or independent_validation_passed is None
        or all_bindings_current is None
        or policy_supports_request is None
        or generation_current is None
    ):
        return ApprovalResult.UNKNOWN

    return ApprovalResult.APPROVE


def exact_binding_holds(
    bound_chain: Mapping[str, str | None],
    actual_chain: Mapping[str, str | None],
) -> ApprovalResult:
    """Whether the exact binding chain holds through the pipeline (§13 / IAP-INV-004 / IAP-AC-004)."""
    if set(bound_chain) != set(actual_chain):
        return ApprovalResult.DENY
    if not bound_chain:
        return ApprovalResult.DENY
    saw_unknown = False
    for name, bound_digest in bound_chain.items():
        actual_digest = actual_chain[name]
        if bound_digest is None or actual_digest is None:
            saw_unknown = True
            continue
        if bound_digest != actual_digest:
            return ApprovalResult.DENY
    if saw_unknown:
        return ApprovalResult.UNKNOWN
    return ApprovalResult.APPROVE


def invalidation_closure(
    graph: Mapping[str, frozenset[str]],
    trigger: str,
    *,
    uncertain: Mapping[str, frozenset[str]] | None = None,
) -> frozenset[str]:
    """The complete invalidation dependency closure from a material trigger (§14 / IAP-INV-008 / IAP-AC-007)."""
    uncertain_adj: Mapping[str, frozenset[str]] = uncertain or {}
    closure: set[str] = set()
    stack: list[str] = [trigger]
    while stack:
        node = stack.pop()
        if node in closure:
            continue
        closure.add(node)
        for dependent in graph.get(node, frozenset()):
            if dependent not in closure:
                stack.append(dependent)
        for dependent in uncertain_adj.get(node, frozenset()):
            if dependent not in closure:
                stack.append(dependent)
    return frozenset(closure)


def materiality_is_material(verdict: MaterialityVerdict) -> bool:
    """Whether an approval-change verdict is material — unknown materiality is material (§5.7 line 126)."""
    return verdict is not MaterialityVerdict.IMMATERIAL


def unknown_confines(
    *,
    any_unknown_state: bool | None,
    capacity_available: bool | None = None,
    protective_or_priority_label: bool | None = None,
    human_preference: bool | None = None,
) -> bool:
    """Whether an UNKNOWN state confines (blocks) ordinary new risk (§16 / IAP-INV-010 / IAP-AC-009)."""
    del capacity_available, protective_or_priority_label, human_preference
    return any_unknown_state is not False


def independent_validation_declared(
    *,
    proposer_only_value: bool | None,
    shared_failure_path: bool | None,
    common_mode_declared: bool | None,
) -> bool:
    """Whether independent validation is structurally declared (§10 / IAP-INV-002 / IAP-AC-002)."""
    return (
        proposer_only_value is False
        and shared_failure_path is False
        and common_mode_declared is True
    )


def no_widening_no_union(
    *,
    single_exact_decision: bool | None,
    no_union_of_narrower: bool | None,
) -> bool:
    """Whether no widening / union of scope is attempted (§7/§13 / IAP-INV-007 / IAP-AC-006)."""
    return single_exact_decision is True and no_union_of_narrower is True


def approval_grants_no_authority(effect: ApprovalAuthorityEffect) -> bool:
    """Whether the approval authority effect grants nothing (§7 / IAP-INV-005 line 150)."""
    return not (
        effect.mutates_capacity
        or effect.creates_headroom
        or effect.issues_authority
        or effect.classifies_protection
        or effect.transmits
        or effect.clears_halt
        or effect.rearms
    )


def active_egress_currentness(
    *,
    active_bounded_proof: bool | None,
    inferred_from_absence: bool | None,
    single_authoritative_consumption: bool | None,
) -> bool:
    """Whether final-egress currentness is actively proven (§15 / IAP-INV-009 / IAP-AC-008)."""
    return (
        active_bounded_proof is True
        and inferred_from_absence is False
        and single_authoritative_consumption is True
    )


def conflicting_evaluators_unknown(
    results: Sequence[ApprovalResult],
) -> ApprovalResult:
    """The retained result of concurrent approval evaluators (§17 line 403 / IAP-INV-012 / IAP-AC-010)."""
    if not results:
        return ApprovalResult.UNKNOWN
    distinct = set(results)
    if len(distinct) > 1:
        return ApprovalResult.UNKNOWN
    return next(iter(distinct))


def decision_unexpired(
    *, max_decision_age_ms: int | None, decision_age_bound_ms: int | None
) -> bool:
    """Whether an approval decision is unexpired (ADR-002-023 §12 item 2 / §18)."""
    if max_decision_age_ms is None or decision_age_bound_ms is None:
        return False
    if decision_age_bound_ms < 0:
        return False
    return decision_age_bound_ms <= max_decision_age_ms
