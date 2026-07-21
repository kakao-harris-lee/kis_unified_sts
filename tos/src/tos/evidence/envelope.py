"""Safety Evidence Envelope (design #4 §2.1, template SoT).

Models ``SAFETY-EVIDENCE-ENVELOPE-template.yaml`` (111 lines). Field layers
(design §2.1, used by the §3.3 digest coverage):

* **Layer-0 (identity/meta, self-excluded)**: ``evidence_record_id``,
  ``idempotency_id``, ``status``, ``canonicalization_version``, ``canonical_digest``.
  Identity is NOT derived from the digest (design #4 §3.1/§2.1) so that a §12
  same-id/different-bytes conflict stays representable and detectable.
* **Layer-1 (covered)**: ``record_class``, ``record_outcome``, ``schema_id``/
  ``schema_version``, the EIP reference triple, ``source``, ``scope``,
  ``subjects``, ``causality``, ``payload``, ``time_evidence``, ``lifecycle``, and
  ``authority_effect``.
* **Layer-2 / ledger-placement (self-excluded)**: the whole ``integrity`` block
  (``predecessor_commitment``/``segment_id`` are decided by ledger placement, and
  ``evidence_commit_receipt_id`` is issued *after* the record — design §2.1 note),
  and the derived correction back-reference (see below).

**Interpretations (design deviations, reported):**

1. The inherited ``canonical_digest`` (Layer-0) is the envelope's own canonical
   *record* digest over Layer-1 — the role design §3.2/§4.2 calls the record's
   ``canonical_payload_digest``. The template's ``payload.canonical_payload_digest``
   / ``payload.raw_payload_digest`` stay as covered references to the external
   payload artifact. Because the payload digests are covered, the record digest
   changes iff any covered field changes, so keying the §12 conflict predicate on
   ``(evidence_record_id, canonical_digest)`` is at least as sensitive as keying
   on the payload digest (design §4.2 intent preserved).
2. ``lifecycle.corrected_by_record_id`` is **not stored**: design §2.0 states the
   correction back-reference is derived by a forward ledger scan and that writing
   it onto the original would violate append-only. It is therefore omitted from
   the stored model and computed by
   :func:`tos.evidence.predicates.corrected_by`; the authoritative correction
   link is the correcting record's ``supersedes_record_id`` + a ``CORRECTION``
   causal link.

Pure module: ``pydantic`` + stdlib only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.canonical import FrozenModel
from tos.evidence._base import AllFalseFlags, EvidenceArtifact
from tos.evidence.elements import CausalLink, DurabilityClass

_ENVELOPE_RECORD_OUTCOME_DEFAULT = "AMBIGUOUS"  # template line 5 (conservative)
_ENVELOPE_CONFIDENTIALITY_DEFAULT = "RESTRICTED"  # template line 79


class EnvelopeSource(FrozenModel):
    """Producer identity / continuity (template lines 12-21)."""

    principal_id: str | None = None
    effective_principal_id: str | None = None
    workload_identity: str | None = None
    environment_id: str | None = None
    deployment_id: str | None = None
    process_continuity_id: str | None = None
    key_generation: int | None = None
    local_sequence: int | None = None
    authoritative_log_position: int | None = None


class EnvelopeScope(FrozenModel):
    """Evidence scope (template lines 23-30)."""

    safety_cell_id: str | None = None
    capacity_domain_id: str | None = None
    account_id: str | None = None
    broker_id: str | None = None
    venue_id: str | None = None
    instrument_id: str | None = None
    strategy_id: str | None = None


class EnvelopeSubjects(FrozenModel):
    """Subject identifiers this record is about (template lines 32-65).

    All optional (``null`` in the template). ``decision_context_capsule_id`` /
    ``context_generation`` carry the design #2 capsule as a **scalar reference**
    only — the capsule model class is never imported (design #4 §0.3/§3.1).
    """

    intent_id: str | None = None
    transmission_attempt_id: str | None = None
    broker_order_id: str | None = None
    fill_id: str | None = None
    position_id: str | None = None
    capacity_allocation_id: str | None = None
    command_id: str | None = None
    approval_set_id: str | None = None
    live_authorization_id: str | None = None
    profile_generation: int | None = None
    halt_generation: int | None = None
    recovery_generation: int | None = None
    recovery_session_id: str | None = None
    recovery_inventory_cut_id: str | None = None
    recovery_obligation_id: str | None = None
    recovery_evidence_package_id: str | None = None
    recovery_readiness_decision_id: str | None = None
    critical_input_observation_id: str | None = None
    critical_input_snapshot_id: str | None = None
    decision_context_capsule_id: str | None = None
    context_generation: int | None = None
    venue_constraint_snapshot_id: str | None = None
    order_admissibility_decision_id: str | None = None
    constraint_generation: int | None = None
    canonical_broker_command_id: str | None = None
    economic_effect_envelope_id: str | None = None
    order_conformance_proof_id: str | None = None
    construction_generation: int | None = None
    aggregate_risk_state_snapshot_id: str | None = None
    adverse_scenario_set_id: str | None = None
    aggregate_risk_decision_id: str | None = None
    aggregate_risk_generation: int | None = None
    non_trade_event_id: str | None = None


class Causality(FrozenModel):
    """Causal edges + authoritative-revision reconciliation (template lines 67-71).

    ``causal_links`` carries typed :class:`CausalLink` edges (design §2.5 A);
    time is never a causal edge.
    """

    correlation_id: str | None = None
    causal_links: tuple[CausalLink, ...] = ()
    previous_authoritative_revision: int | None = None
    resulting_authoritative_revision: int | None = None


class Payload(FrozenModel):
    """Payload content references (template lines 73-80).

    ``raw_payload_digest`` (raw) and ``canonical_payload_digest`` (canonical) are
    references to the external payload artifact — never the raw credential/key/
    token itself (design §4.7 ERI-INV-013 structural realization).
    """

    content_type: str | None = None
    raw_payload_digest: str | None = None
    canonical_payload_digest: str | None = None
    byte_length: int | None = None
    encrypted_location: str | None = None
    confidentiality_class: str = _ENVELOPE_CONFIDENTIALITY_DEFAULT
    redaction_profile_id: str | None = None


class TimeEvidence(FrozenModel):
    """Trustworthy-time evidence (template lines 82-87). Time is not a causal edge."""

    trustworthy_time_snapshot_id: str | None = None
    source_wall_time: int | None = None
    local_monotonic_value: int | None = None
    monotonic_continuity_id: str | None = None
    uncertainty_ms: int | None = None


class Integrity(FrozenModel):
    """Signature + ledger-placement block (template lines 89-94, design §2.1 note).

    Excluded from the record digest preimage: ``predecessor_commitment`` /
    ``segment_id`` are decided by ledger placement (§2.4 segment commitment), and
    ``evidence_commit_receipt_id`` is a Layer-2 reference issued after the record.
    The MAC's cryptographic verification is EV-L2+ (key custody); the model only
    carries the field's presence/structure (design §3.4 honest-scope).
    """

    source_signature_or_mac: str | None = None
    integrity_key_id: str | None = None
    predecessor_commitment: str | None = None
    segment_id: str | None = None
    evidence_commit_receipt_id: str | None = None


class Lifecycle(FrozenModel):
    """Lifecycle block (template lines 96-100; ``corrected_by_record_id`` omitted).

    ``corrected_by_record_id`` is a derived forward-scan back-reference and is not
    stored (design §2.0); ``supersedes_record_id`` is the authoritative forward
    supersession link (covered).
    """

    durability_class: DurabilityClass = DurabilityClass.DENY_IF_UNSPECIFIED
    retention_class: str | None = None
    legal_hold_ids: tuple[str, ...] = ()
    supersedes_record_id: str | None = None


class EnvelopeAuthorityEffect(AllFalseFlags):
    """Envelope authority effect — all false (template lines 103-108, design §4.6)."""

    creates_authority: bool = False
    may_mutate_live_state: bool = False
    may_transmit_to_broker: bool = False
    may_release_capacity: bool = False
    may_rearm: bool = False


class SafetyEvidenceEnvelope(EvidenceArtifact):
    """An immutable, append-only Safety Evidence Envelope (design #4 §2.1).

    Digest-verified (``canonical_digest == H_ver(canonicalize(Layer-1))``) with an
    **independent** ``evidence_record_id`` (globally unique, stable across
    retry/replication/export/replay) and ``idempotency_id``. Use :meth:`issue`.
    """

    _ID_FIELD: ClassVar[str] = "evidence_record_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "record_class",
        "schema_id",
        "schema_version",
        "evidence_integrity_policy_id",
        "evidence_integrity_policy_digest",
        "source.principal_id",
        "source.workload_identity",
        "source.environment_id",
        "scope.safety_cell_id",
        "scope.capacity_domain_id",
        "scope.account_id",
        "scope.broker_id",
        "causality.correlation_id",
        "payload.content_type",
        "payload.raw_payload_digest",
        "payload.canonical_payload_digest",
        "time_evidence.trustworthy_time_snapshot_id",
        "lifecycle.retention_class",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "record_class",
            "record_outcome",
            "schema_id",
            "schema_version",
            "evidence_integrity_policy_id",
            "evidence_integrity_policy_generation",
            "evidence_integrity_policy_digest",
            "source",
            "scope",
            "subjects",
            "causality",
            "payload",
            "time_evidence",
            "lifecycle",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §2.1) --------
    # canonical_digest / status / canonicalization_version inherited.
    evidence_record_id: str | None = None
    idempotency_id: str | None = None

    # ---- Layer-1 covered content ----
    record_class: str | None = None
    record_outcome: str = _ENVELOPE_RECORD_OUTCOME_DEFAULT
    schema_id: str | None = None
    schema_version: str | None = None
    evidence_integrity_policy_id: str | None = None
    evidence_integrity_policy_generation: int | None = None
    evidence_integrity_policy_digest: str | None = None
    source: EnvelopeSource = EnvelopeSource()
    scope: EnvelopeScope = EnvelopeScope()
    subjects: EnvelopeSubjects = EnvelopeSubjects()
    causality: Causality = Causality()
    payload: Payload = Payload()
    time_evidence: TimeEvidence = TimeEvidence()
    lifecycle: Lifecycle = Lifecycle()
    authority_effect: EnvelopeAuthorityEffect = EnvelopeAuthorityEffect()

    # ---- Layer-2 / ledger-placement (excluded from the digest) ----
    integrity: Integrity = Integrity()
