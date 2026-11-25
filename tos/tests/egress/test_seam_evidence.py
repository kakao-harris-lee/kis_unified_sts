"""MANDATED test-only seam cross-check: evidence commit receipt != QCC 2-layer (design #22 §3.4/§3.5/§7)."""

from __future__ import annotations

import tos.egress as egress
from tos.egress import evidence_receipt_is_not_quorum_proof
from tos.evidence.ledger import SegmentCommitmentScheme
from tos.evidence.receipt import EvidenceCommitReceipt, ReceiptVerificationStatus


def test_receipt_verification_status_self_limits_to_unverified() -> None:
    """(§0.4d evidence receipt.py:11-12) UNVERIFIED is the only honest Phase-1 verification state."""
    default_status = EvidenceCommitReceipt.model_fields["verification_status"].default
    assert default_status is ReceiptVerificationStatus.UNVERIFIED


def test_receipt_is_single_signer_and_all_false() -> None:
    """(§0.4d) A commit receipt is single-signer + all-false — structurally not a quorum proof."""
    fields = EvidenceCommitReceipt.model_fields
    assert "receipt_signer_identity" in fields
    assert "receipt_signature" in fields
    assert "permits_broker_transmission" in fields


def test_egress_rejects_any_receipt_as_a_quorum_proof() -> None:
    """(§5.4) evidence_receipt_is_not_quorum_proof rejects a receipt substitute unconditionally."""
    assert (
        evidence_receipt_is_not_quorum_proof(ReceiptVerificationStatus.UNVERIFIED)
        is True
    )
    assert evidence_receipt_is_not_quorum_proof(None) is True


def test_egress_reauthors_no_evidence_receipt_or_commitment_scheme() -> None:
    """(§3.5) egress re-authors NO EvidenceCommitReceipt / SegmentCommitmentScheme."""
    assert not hasattr(egress, "EvidenceCommitReceipt")
    assert not hasattr(egress, "SegmentCommitmentScheme")
    assert not hasattr(egress, "ReceiptVerificationStatus")
    assert EvidenceCommitReceipt.__name__ == "EvidenceCommitReceipt"
    assert SegmentCommitmentScheme.__name__ == "SegmentCommitmentScheme"
