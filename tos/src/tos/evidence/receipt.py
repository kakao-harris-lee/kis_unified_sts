"""Evidence Commit Receipt (design #4 §2.2, template SoT).

Models ``EVIDENCE-COMMIT-RECEIPT-template.yaml`` (33 lines, all scalar). A
digest-bound artifact (design §3.2) with an **independent** ``receipt_id``
(id != f(digest), design #4 §3.1).

**Phase-1 honesty (design §2.2 / gap 5):** the receipt is pure data and proves
**no durability**. Its durable-verification status can never leave ``UNVERIFIED``
in Phase 1 — proving "durably accepted" needs an out-of-scope durable store +
anchor service (L2+). Only the *binding* and *substitution-rejection* predicates
are EV-L1 (see :mod:`tos.evidence.predicates`); those are pure functions, not a
durability proof.

**Interpretations (design deviations, reported):**

* The inherited ``canonical_digest`` is the receipt's own self-digest over its
  covered issuance fields; ``canonical_record_digest`` is a **covered binding
  reference** to the target record's digest (design §3.2 "대상 레코드에 bind").
* The template's top-level ``status: UNVERIFIED`` is a *durable-verification*
  status, distinct from the ``ArtifactStatus`` (DRAFT/ISSUED) lifecycle the
  digest-binding base uses. To avoid overloading the inherited ``status`` it is
  modelled as ``verification_status`` (a :class:`ReceiptVerificationStatus`),
  fixed to ``UNVERIFIED`` in Phase 1.

Pure module: ``pydantic`` + stdlib only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError
from tos.evidence._base import EvidenceArtifact
from tos.evidence.elements import DurabilityClass

_RECEIPT_AUTHORITY_FLAGS = (
    "creates_authority",
    "creates_capacity",
    "permits_broker_transmission",
    "may_rearm",
)


class ReceiptVerificationStatus(StrEnum):
    """Durable-verification status of a receipt (template ``status``, design §2.2).

    ``UNVERIFIED`` is the only state a pure Phase-1 model can honestly hold —
    ``VERIFIED`` (durable acceptance) requires an out-of-scope durable store +
    anchor service and is therefore unconstructable here (gap 5).
    """

    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"


class EvidenceCommitReceipt(EvidenceArtifact):
    """A digest-bound Evidence Commit Receipt (design #4 §2.2).

    Binds to exactly one target record digest (``canonical_record_digest``), one
    EIP generation, and one ``store_continuity_id``, and carries
    ``valid_for_request_digest`` / ``valid_for_scope_digest`` /
    ``valid_for_egress_generation`` (design §10.2). Substitution rejection is a
    pure predicate; durable acceptance is not proven (status stays UNVERIFIED).
    """

    _ID_FIELD: ClassVar[str] = "receipt_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "evidence_record_id",
        "canonical_record_digest",
        "record_class",
        "evidence_integrity_policy_id",
        "evidence_integrity_policy_digest",
        "store_continuity_id",
        "durable_segment_id",
        "integrity_anchor_predecessor",
        "acknowledgement_rule",
        "committed_at_time_snapshot_id",
        "committed_at_monotonic_continuity_id",
        "receipt_signer_identity",
        "receipt_signature",
        "valid_for_request_digest",
        "valid_for_scope_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "evidence_record_id",
            "canonical_record_digest",
            "record_class",
            "durability_class",
            "evidence_integrity_policy_id",
            "evidence_integrity_policy_generation",
            "evidence_integrity_policy_digest",
            "store_continuity_id",
            "store_generation",
            "durable_segment_id",
            "durable_position",
            "integrity_anchor_predecessor",
            "acknowledgement_rule",
            "committed_at_time_snapshot_id",
            "committed_at_monotonic_continuity_id",
            "committed_at_local_monotonic_value",
            "receipt_signer_identity",
            "receipt_key_generation",
            "receipt_signature",
            "valid_for_request_digest",
            "valid_for_scope_digest",
            "valid_for_egress_generation",
            "creates_authority",
            "creates_capacity",
            "permits_broker_transmission",
            "may_rearm",
        }
    )

    # ---- Layer-0 identity (independent) + verification status (excluded) ------
    receipt_id: str | None = None
    verification_status: ReceiptVerificationStatus = (
        ReceiptVerificationStatus.UNVERIFIED
    )

    # ---- Covered issuance / binding fields ----
    evidence_record_id: str | None = None
    canonical_record_digest: str | None = None
    record_class: str | None = None
    durability_class: DurabilityClass = DurabilityClass.DENY_IF_UNSPECIFIED
    evidence_integrity_policy_id: str | None = None
    evidence_integrity_policy_generation: int | None = None
    evidence_integrity_policy_digest: str | None = None
    store_continuity_id: str | None = None
    store_generation: int | None = None
    durable_segment_id: str | None = None
    durable_position: int | None = None
    integrity_anchor_predecessor: str | None = None
    acknowledgement_rule: str | None = None
    committed_at_time_snapshot_id: str | None = None
    committed_at_monotonic_continuity_id: str | None = None
    committed_at_local_monotonic_value: int | None = None
    receipt_signer_identity: str | None = None
    receipt_key_generation: int | None = None
    receipt_signature: str | None = None
    valid_for_request_digest: str | None = None
    valid_for_scope_digest: str | None = None
    valid_for_egress_generation: int | None = None

    # ---- Authority effect flags — all false (template lines 25-28, §4.6) ----
    creates_authority: bool = False
    creates_capacity: bool = False
    permits_broker_transmission: bool = False
    may_rearm: bool = False

    @model_validator(mode="after")
    def _receipt_invariants(self) -> EvidenceCommitReceipt:
        """Enforce all-false authority + UNVERIFIED-only durability (§2.2/§4.6)."""
        for name in _RECEIPT_AUTHORITY_FLAGS:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"EvidenceCommitReceipt.{name} must be false "
                    "(a valid receipt proves durability, not authorization — §4.6)"
                )
        if self.verification_status is not ReceiptVerificationStatus.UNVERIFIED:
            raise ArtifactIntegrityError(
                "verification_status cannot leave UNVERIFIED in Phase 1 — durable "
                "acceptance needs an out-of-scope durable store + anchor (gap 5)"
            )
        return self
