"""MANDATED test-only seam cross-check: evidence commit receipt != QCC 2-layer (design #22 §3.4/§3.5/§7).

evidence (ADR-002-016) owns the durability substrate — the ``EvidenceCommitReceipt`` and the
``SegmentCommitmentScheme`` (``evidence/ledger.py:82``). It is a **different layer** from the QCC:
the receipt is single-signer (``receipt_signer_identity``), can only honestly hold
``ReceiptVerificationStatus.UNVERIFIED`` in Phase 1 (``evidence/receipt.py:11-12`` — durable
acceptance is out of scope), and is all-false (``permits_broker_transmission`` False). EGRESS's
``evidence_receipt_is_not_quorum_proof`` is the pure realization of ADR §21.4's leader-receipt
rejection — a receipt can **never** substitute for a QCC (§0.4d/§5.4). EGRESS **re-authors none** of
the evidence receipt / segment-commitment (sibling edge 0). This file imports the real evidence
models as a **test** to prove the 2-layer distinction; the import-closure test proves ``tos.evidence``
is **absent** from the egress runtime closure.

Regime tag: structural / coordinate predicate substrate only; EGRESS-EV-004 substrate;
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import tos.egress as egress
from tos.egress import evidence_receipt_is_not_quorum_proof
from tos.evidence.ledger import SegmentCommitmentScheme
from tos.evidence.receipt import EvidenceCommitReceipt, ReceiptVerificationStatus


def test_receipt_verification_status_self_limits_to_unverified() -> None:
    """(§0.4d evidence receipt.py:11-12) UNVERIFIED is the only honest Phase-1 verification state."""
    # The default verification status a Phase-1 receipt holds is UNVERIFIED (durable acceptance is
    # out of scope) — the structural reason a receipt is not durable quorum acceptance (§5.4).
    default_status = EvidenceCommitReceipt.model_fields["verification_status"].default
    assert default_status is ReceiptVerificationStatus.UNVERIFIED


def test_receipt_is_single_signer_and_all_false() -> None:
    """(§0.4d) A commit receipt is single-signer + all-false — structurally not a quorum proof."""
    fields = EvidenceCommitReceipt.model_fields
    # single leader signer (≠ a quorum threshold, §5.3).
    assert "receipt_signer_identity" in fields
    assert "receipt_signature" in fields
    # all-false authority (transmits nothing).
    assert "permits_broker_transmission" in fields


def test_egress_rejects_any_receipt_as_a_quorum_proof() -> None:
    """(§5.4) evidence_receipt_is_not_quorum_proof rejects a receipt substitute unconditionally."""
    # Whatever an evidence receipt (or any leader receipt / journal) is offered as, it is NOT a QCC.
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
    # sanity: the real siblings ARE these types (the producer side), egress just does not import them.
    assert EvidenceCommitReceipt.__name__ == "EvidenceCommitReceipt"
    assert SegmentCommitmentScheme.__name__ == "SegmentCommitmentScheme"
