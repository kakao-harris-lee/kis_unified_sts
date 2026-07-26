"""MANDATED test-only seam cross-check: hag human attestation <-> iap automated decision (design #20 §3.5/§7).

iap (ADR-002-023) owns the **automated per-proposal** decision axis: ``ProposalApprovalRequest``
(``records.py:158``) / ``IndependentApprovalDecision`` (``records.py:277``) / ``ApprovalResult``.
hag owns the **human principal attestation** axis: ``HumanApprovalRequest`` /
``HumanApprovalAttestation`` / ``AttestationDecision``. ADR §4 line 98 verbatim: "an automated
``APPROVE`` cannot satisfy a human quorum." The two are **distinct types on distinct axes** —
mutually non-substitutable; the "Human" prefix makes the split irreversible (§0.4e). The MAJOR-1
correction: the capsule ``approval_request_id`` (``capsule.py:161``) is an **iap** Bindings-chain
field, **not** an HAG seam — this test locks that regression. This file imports the real iap symbols
as a **test**; the import-closure test proves ``tos.iap`` is **absent** from the hag runtime closure.

Regime tag: predicate / model substrate only; HAG-EV-002/004 substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.hag import AttestationDecision, HumanApprovalAttestation, HumanApprovalRequest
from tos.iap import (
    ApprovalResult,
    IndependentApprovalDecision,
    ProposalApprovalRequest,
)


def test_human_and_automated_approval_are_distinct_types() -> None:
    """(§3.5 (c); ADR §4 line 98) The human attestation type and the iap automated types are distinct."""
    assert HumanApprovalAttestation is not IndependentApprovalDecision
    assert HumanApprovalRequest is not ProposalApprovalRequest
    # The human attestation has a principal coordinate (collapse-centric); the iap decision has none.
    assert "principal_id" in HumanApprovalAttestation.model_fields
    assert "principal_id" not in IndependentApprovalDecision.model_fields


def test_automated_approve_and_human_approve_are_different_vocabularies() -> None:
    """(§3.5 (c)) The iap ApprovalResult and the hag AttestationDecision are distinct enums."""
    assert AttestationDecision is not ApprovalResult
    # Both spell an APPROVE, but on different axes — an automated APPROVE cannot satisfy a human quorum.
    assert AttestationDecision.APPROVE.value == "APPROVE"
    assert ApprovalResult.APPROVE.value == "APPROVE"
    assert AttestationDecision.APPROVE is not ApprovalResult.APPROVE


def test_capsule_approval_request_id_is_the_iap_axis_not_an_hag_seam() -> None:
    """(MAJOR-1) The capsule approval_request_id belongs to the iap Bindings chain — not consumed by hag."""
    # The iap ProposalApprovalRequest owns the approval-request identity axis.
    assert "request_id" in ProposalApprovalRequest.model_fields
    # hag's request binds the capsule DIGEST (request -> capsule direction), NOT the capsule's
    # own approval_request_id (which is the iap Bindings-chain field, §0.4a/§0.4e).
    hag_request_fields = set(HumanApprovalRequest.model_fields)
    assert "decision_context_capsule_digest" in hag_request_fields
    assert "decision_context_capsule_id" in hag_request_fields
    assert "approval_request_id" not in hag_request_fields  # never consumed (iap axis)


def test_hag_does_not_reauthor_iap_decision() -> None:
    """(§0.4e/§3.5) hag re-authors none of the iap automated-decision axis."""
    import tos.hag as hag

    assert not hasattr(hag, "IndependentApprovalDecision")
    assert not hasattr(hag, "ProposalApprovalRequest")
    assert not hasattr(hag, "ApprovalResult")
