"""Shared valid-artifact builders + strategies for the iap property tests (design #15 §7)."""

from __future__ import annotations

from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.iap import (
    ApprovalConsumptionRecord,
    ApprovalResult,
    ConsumptionStatus,
    IndependentApprovalDecision,
    OrderingEvent,
    ProposalApprovalRequest,
    TradingApprovalPolicy,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

REQUIRED_FIELD_TEXT = st.text(min_size=1, max_size=8).filter(
    lambda s: s.strip() != "" and s != "TBD" and "*" not in s and s.upper() != "UNKNOWN"
)
TRIBOOL = st.sampled_from([True, False, None])
APPROVAL_RESULTS = st.sampled_from(list(ApprovalResult))
CONSUMPTION_STATUSES = st.sampled_from(list(ConsumptionStatus))

_COMPLETE_SCOPE: dict[str, str] = {
    "proposer_identity": "strat-1",
    "environment": "PAPER",
    "account": "ACCT-1",
    "instrument": "INSTR-1",
    "action_class": "ENTRY",
    "operating_mode": "PAPER",
    "direction": "LONG",
    "position_effect": "OPEN",
    "quantity_basis": "SHARES:100",
    "proposal_id": "prop-1",
    "proposal_digest": "prop-digest-1",
    "decision_context_capsule_id": "cap-1",
    "decision_context_capsule_digest": "cap-digest-1",
    "critical_input_snapshot_digest": "snap-digest-1",
    "construction_envelope_id": "env-1",
    "construction_envelope_digest": "env-digest-1",
    "canonical_broker_command_id": "cmd-1",
    "canonical_broker_command_digest": "cmd-digest-1",
    "venue_snapshot_digest": "venue-snap-1",
    "venue_admissibility_decision_digest": "venue-adm-1",
    "broker_capability_profile_digest": "bcp-digest-1",
    "trading_approval_policy_id": "pol-1",
    "trading_approval_policy_digest": "pol-digest-1",
}


def issue_policy(**overrides: Any) -> TradingApprovalPolicy:
    """Issue a valid spg-governed :class:`TradingApprovalPolicy` (all required covered concrete)."""
    base: dict[str, Any] = {
        "policy_id": "pol-1",
        "policy_generation": 1,
        "policy_version": "v1",
    }
    base.update(overrides)
    return TradingApprovalPolicy.issue(scheme=SCHEME, **base)


def complete_request(**overrides: Any) -> ProposalApprovalRequest:
    """Issue a fully **complete** :class:`ProposalApprovalRequest` (earns APPROVE, §9)."""
    base: dict[str, Any] = {
        "request_id": "req-1",
        "request_generation": 1,
        "required_scope_complete": True,
        "trading_approval_policy_generation": 1,
        "required_independent_facts": ("independent-source-a",),
        "common_mode_declarations": ("common-mode-decl-a",),
        "max_request_age_ms": 1000,
        "single_use": True,
        "exact_intent_only": True,
        "invalidation_set": ("inv-node-1",),
        **_COMPLETE_SCOPE,
    }
    base.update(overrides)
    return ProposalApprovalRequest.issue(scheme=SCHEME, **base)


def minimal_request(**overrides: Any) -> ProposalApprovalRequest:
    """Issue a minimal request (defaults only — structurally incomplete, denies)."""
    base: dict[str, Any] = {"request_id": "req-0", "request_generation": 1}
    base.update(overrides)
    return ProposalApprovalRequest.issue(scheme=SCHEME, **base)


def issue_decision(**overrides: Any) -> IndependentApprovalDecision:
    """Issue a valid :class:`IndependentApprovalDecision` (concrete generation)."""
    base: dict[str, Any] = {
        "decision_id": "dec-1",
        "decision_generation": 1,
        "request_id": "req-1",
        "request_digest": "req-digest-1",
        "result": ApprovalResult.APPROVE,
    }
    base.update(overrides)
    return IndependentApprovalDecision.issue(scheme=SCHEME, **base)


def issue_consumption_record(**overrides: Any) -> ApprovalConsumptionRecord:
    """Issue a valid :class:`ApprovalConsumptionRecord` (concrete generation)."""
    base: dict[str, Any] = {
        "consumption_record_id": "cons-1",
        "consumption_generation": 1,
        "decision_id": "dec-1",
        "decision_digest": "dec-digest-1",
        "intent_identity": "intent-1",
        "result": ApprovalResult.APPROVE,
        "consumption_status": ConsumptionStatus.CONSUMED,
    }
    base.update(overrides)
    return ApprovalConsumptionRecord.issue(scheme=SCHEME, **base)


def ordering_event(sequence: int, *, continuity: str = "cont-1") -> OrderingEvent:
    """A single-continuity :class:`~tos.ordering.OrderingEvent` (a Trading Approval Generation)."""
    return OrderingEvent(
        event_id=f"gen-{sequence}",
        source_continuity_id=continuity,
        source_native_sequence=sequence,
    )


APPROVE_FACTS: dict[str, Any] = {
    "independent_validation_passed": True,
    "all_bindings_current": True,
    "policy_supports_request": True,
    "generation_current": True,
    "conflicting_evaluations": False,
    "unverifiable_input": False,
}
