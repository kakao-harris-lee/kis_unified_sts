"""MANDATED test-only seam cross-check: iap <-> orthostate (design #15 §3.4/§3.5 — the max-risk boundary).

The critical boundary (§3.5 core verdict 1): :attr:`ApprovalResult.DENY` (a decision-result,
terminal *for the request*, §11 line 296) is **NOT** orthostate ``IntentState.DENIED`` (an Intent
state that branches from ``APPROVED`` after aggregate-risk/capacity denial). This file imports the
real orthostate ``intent_transition_allowed`` (``predicates.py:432``) + ``IntentState`` +
``CompositeState`` as a **test** to re-confirm, from the actual code:

  1. orthostate **owns** the Intent transition — ``PROPOSED -> DENIED`` is deliberately forbidden
     (DENIED branches from APPROVED); iap never re-authors it.
  2. an iap approval ``DENY`` triggers **no** Intent transition — nothing consumes, so the Intent
     stays ``PROPOSED`` (causal isolation: approval DENY ≠ Intent DENIED).
  3. the iap ``ApprovalConsumptionRecord.intent_identity`` binds the orthostate
     ``CompositeState.intent_identity`` (``orthostate/records.py:93``) by **scalar** — the
     PROPOSED->APPROVED transition itself stays orthostate's.

A test-only cross-import is NOT a runtime package edge (§3.4/§7.1); orthostate is one of the
fifteen siblings iap never imports at runtime (sibling edge 0).
"""

from __future__ import annotations

from tos.iap import (
    ApprovalResult,
    ConsumptionOutcome,
    ConsumptionStatus,
    consumption_transition,
)
from tos.orthostate import CompositeState, IntentState, intent_transition_allowed

from ._iap_strategies import issue_consumption_record

# ---------------------------------------------------------------------------
# (1) orthostate OWNS the Intent transition — PROPOSED -> DENIED is forbidden
# ---------------------------------------------------------------------------


def test_orthostate_forbids_proposed_to_denied() -> None:
    """(§3.5) orthostate deliberately forbids PROPOSED -> DENIED (DENIED branches from APPROVED)."""
    assert intent_transition_allowed(IntentState.PROPOSED, IntentState.DENIED) is False


def test_orthostate_allows_only_proposed_to_approved() -> None:
    """(§3.5) The one PROPOSED transition orthostate allows is PROPOSED -> APPROVED (via consumption)."""
    assert intent_transition_allowed(IntentState.PROPOSED, IntentState.APPROVED) is True
    # DENIED is only reachable from APPROVED (after aggregate-risk/capacity denial, outside iap).
    assert intent_transition_allowed(IntentState.APPROVED, IntentState.DENIED) is True


# ---------------------------------------------------------------------------
# (2) DENY ≠ DENIED — an approval DENY triggers no Intent transition (causal isolation)
# ---------------------------------------------------------------------------


def test_approval_deny_is_not_intent_denied() -> None:
    """(§3.5 core verdict 1) ApprovalResult.DENY and IntentState.DENIED are distinct types/values."""
    assert ApprovalResult.DENY is not IntentState.DENIED
    assert type(ApprovalResult.DENY) is not type(IntentState.DENIED)
    assert ApprovalResult.DENY.value == "DENY"
    assert IntentState.DENIED.value == "DENIED"


def test_approval_deny_causes_no_consumption_so_intent_stays_proposed() -> None:
    """(§3.5) A DENY decision does not consume — nothing drives an Intent transition (stays PROPOSED).

    Causal isolation: iap's consumption state machine only consumes a current APPROVE. A DENY
    yields REJECTED_INELIGIBLE with the status unchanged, so no PROPOSED->APPROVED transition is
    requested — and orthostate anyway forbids PROPOSED->DENIED. The Intent simply remains PROPOSED.
    """
    status, outcome = consumption_transition(
        current_status=ConsumptionStatus.ELIGIBLE,
        decision_result=ApprovalResult.DENY,
        decision_current=True,
        approved_intent_envelope_equivalent=True,
        command_identity="cmd-1",
        command_digest="cmd-digest-1",
    )
    assert outcome is ConsumptionOutcome.REJECTED_INELIGIBLE
    assert status is ConsumptionStatus.ELIGIBLE  # nothing consumed
    # No transition is triggered; the Intent stays PROPOSED (orthostate owns any transition).
    assert intent_transition_allowed(IntentState.PROPOSED, IntentState.DENIED) is False


# ---------------------------------------------------------------------------
# (3) intent_identity scalar seam — iap binds orthostate CompositeState.intent_identity
# ---------------------------------------------------------------------------


def test_consumption_record_binds_orthostate_intent_identity_scalar() -> None:
    """(§12 line 318 / orthostate/records.py:93) The record binds CompositeState.intent_identity by scalar.

    The orthostate ``CompositeState`` owns the ``intent_identity`` field (a ``str | None`` scalar);
    the iap ``ApprovalConsumptionRecord`` binds that identity by the **same scalar** — never an
    orthostate object (sibling edge 0). We assert the field exists on the orthostate side and that
    the iap record round-trips the plain scalar (no full CompositeState instantiation needed — its
    other four dimension states are irrelevant to this seam).
    """
    assert "intent_identity" in CompositeState.model_fields
    intent_identity = "intent-42"
    record = issue_consumption_record(intent_identity=intent_identity)
    assert record.intent_identity == intent_identity
    # The seam carries a plain str scalar — the record holds no orthostate object.
    assert isinstance(record.intent_identity, str)
    assert not isinstance(record.intent_identity, CompositeState)
