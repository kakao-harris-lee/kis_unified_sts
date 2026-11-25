"""Safety Evidence Envelope (design #4 §2.1, template SoT)."""

from __future__ import annotations

from typing import ClassVar

from tos.canonical import FrozenModel
from tos.evidence._base import AllFalseFlags, EvidenceArtifact
from tos.evidence.elements import CausalLink, DurabilityClass

_ENVELOPE_RECORD_OUTCOME_DEFAULT = "AMBIGUOUS"
_ENVELOPE_CONFIDENTIALITY_DEFAULT = "RESTRICTED"


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
    """Subject identifiers this record is about (template lines 32-65)."""

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
    """Causal edges + authoritative-revision reconciliation (template lines 67-71)."""

    correlation_id: str | None = None
    causal_links: tuple[CausalLink, ...] = ()
    previous_authoritative_revision: int | None = None
    resulting_authoritative_revision: int | None = None


class Payload(FrozenModel):
    """Payload content references (template lines 73-80)."""

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
    """Signature + ledger-placement block (template lines 89-94, design §2.1 note)."""

    source_signature_or_mac: str | None = None
    integrity_key_id: str | None = None
    predecessor_commitment: str | None = None
    segment_id: str | None = None
    evidence_commit_receipt_id: str | None = None


class Lifecycle(FrozenModel):
    """Lifecycle block (template lines 96-100; ``corrected_by_record_id`` omitted)."""

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
    """An immutable, append-only Safety Evidence Envelope (design #4 §2.1)."""

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

    evidence_record_id: str | None = None
    idempotency_id: str | None = None

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

    integrity: Integrity = Integrity()
