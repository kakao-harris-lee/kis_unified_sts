"""MANDATED test-only seam cross-check: iap <-> orthostate (design #15 §3.4/§3.5 — the max-risk boundary)."""

from __future__ import annotations

from tos.iap import (
    ApprovalResult,
    ConsumptionOutcome,
    ConsumptionStatus,
    consumption_transition,
)
from tos.orthostate import CompositeState, IntentState, intent_transition_allowed

from ._iap_strategies import issue_consumption_record


def test_orthostate_forbids_proposed_to_denied() -> None:
    """(§3.5) orthostate deliberately forbids PROPOSED -> DENIED (DENIED branches from APPROVED)."""
    assert intent_transition_allowed(IntentState.PROPOSED, IntentState.DENIED) is False


def test_orthostate_allows_only_proposed_to_approved() -> None:
    """(§3.5) The one PROPOSED transition orthostate allows is PROPOSED -> APPROVED (via consumption)."""
    assert intent_transition_allowed(IntentState.PROPOSED, IntentState.APPROVED) is True
    assert intent_transition_allowed(IntentState.APPROVED, IntentState.DENIED) is True


def test_approval_deny_is_not_intent_denied() -> None:
    """(§3.5 core verdict 1) ApprovalResult.DENY and IntentState.DENIED are distinct types/values."""
    assert ApprovalResult.DENY is not IntentState.DENIED
    assert type(ApprovalResult.DENY) is not type(IntentState.DENIED)
    assert ApprovalResult.DENY.value == "DENY"
    assert IntentState.DENIED.value == "DENIED"


def test_approval_deny_causes_no_consumption_so_intent_stays_proposed() -> None:
    """(§3.5) A DENY decision does not consume — nothing drives an Intent transition (stays PROPOSED)."""
    status, outcome = consumption_transition(
        current_status=ConsumptionStatus.ELIGIBLE,
        decision_result=ApprovalResult.DENY,
        decision_current=True,
        approved_intent_envelope_equivalent=True,
        command_identity="cmd-1",
        command_digest="cmd-digest-1",
    )
    assert outcome is ConsumptionOutcome.REJECTED_INELIGIBLE
    assert status is ConsumptionStatus.ELIGIBLE
    assert intent_transition_allowed(IntentState.PROPOSED, IntentState.DENIED) is False


def test_consumption_record_binds_orthostate_intent_identity_scalar() -> None:
    """(§12 line 318 / orthostate/records.py:93) The record binds CompositeState.intent_identity by scalar."""
    assert "intent_identity" in CompositeState.model_fields
    intent_identity = "intent-42"
    record = issue_consumption_record(intent_identity=intent_identity)
    assert record.intent_identity == intent_identity
    assert isinstance(record.intent_identity, str)
    assert not isinstance(record.intent_identity, CompositeState)
