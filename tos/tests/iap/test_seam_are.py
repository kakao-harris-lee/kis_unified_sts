"""MANDATED test-only seam cross-check: iap <-> are / liveauth (design #15 §3.4; §13 line 346).

Downstream siblings reference the iap decision / consumption identity by **scalar** — iap imports
nothing (sibling edge 0). This file imports the real siblings as a **test** to lock the simple
signature match:

* are ``AggregateRiskPolicy.approval_identity`` (``are/records.py:348``) is a ``str | None`` scalar
  that accepts an iap decision identity (v1.1 MAJOR-1: the seam is on ``AggregateRiskPolicy``, not
  ``AggregateRiskDecision`` — the latter carries no ``approval_identity`` field);
* liveauth ``LiveAuthorization.approval_record_identity`` (``liveauth/records.py:112``) is a
  ``str | None`` scalar that accepts an iap consumption-record identity ("approval != authorization"
  ``liveauth/records.py:188`` — liveauth is downstream of iap).

A test-only cross-import is NOT a runtime package edge (§3.4/§7.1); are / liveauth are two of the
fifteen siblings iap never imports at runtime (sibling edge 0).
"""

from __future__ import annotations

from tos.are import AggregateRiskPolicy
from tos.liveauth import LiveAuthorization

from ._iap_strategies import issue_consumption_record, issue_decision


def test_are_policy_accepts_iap_decision_identity_scalar() -> None:
    """(are/records.py:348) AggregateRiskPolicy.approval_identity accepts the iap decision id scalar.

    Coordinate honesty (code-review MINOR): ``AggregateRiskPolicy.approval_identity`` is a
    POLICY-GOVERNANCE approval field (who approved the policy artifact) — a separate axis
    from the runtime iap approval-decision dataflow. This test therefore claims only
    scalar-acceptance. The "are decision -> iap approval reference" wiring does NOT exist
    yet (``AggregateRiskDecision`` carries no approval_identity field — regression-pinned
    below) and is -023 downstream FUTURE wiring, same posture as the ioc
    ``OrderConformanceProof`` future-wiring note in test_seam_ioc.
    """
    decision = issue_decision(decision_id="iap-dec-1")
    assert decision.decision_id is not None
    # A DRAFT construction is enough to prove the field accepts the scalar (no digest needed).
    policy = AggregateRiskPolicy(approval_identity=decision.decision_id)
    assert policy.approval_identity == decision.decision_id
    assert isinstance(policy.approval_identity, str)
    assert not isinstance(policy.approval_identity, type(decision))


def test_liveauth_accepts_iap_consumption_record_identity_scalar() -> None:
    """(liveauth/records.py:112) LiveAuthorization.approval_record_identity accepts the iap consumption id scalar."""
    record = issue_consumption_record(consumption_record_id="iap-cons-1")
    assert record.consumption_record_id is not None
    auth = LiveAuthorization(approval_record_identity=record.consumption_record_id)
    assert auth.approval_record_identity == record.consumption_record_id
    assert isinstance(auth.approval_record_identity, str)
    assert not isinstance(auth.approval_record_identity, type(record))


def test_are_decision_carries_no_approval_identity_field() -> None:
    """(v1.1 MAJOR-1) The seam is on AggregateRiskPolicy — AggregateRiskDecision has no approval_identity."""
    from tos.are import AggregateRiskDecision

    assert "approval_identity" not in AggregateRiskDecision.model_fields
    assert "approval_identity" in AggregateRiskPolicy.model_fields
