"""Authored element schemas for the evidence templates (design #4 §2.5)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel


class EdgeType(StrEnum):
    """Causal-link edge types (design §2.5 A, ADR §5.5 line 112)."""

    INTENT = "INTENT"
    APPROVAL = "APPROVAL"
    AUTHORITY = "AUTHORITY"
    CAPACITY_COMMIT = "CAPACITY_COMMIT"
    CAPABILITY_CLAIM = "CAPABILITY_CLAIM"
    PROFILE_ACTIVATION = "PROFILE_ACTIVATION"
    TRANSMISSION_ATTEMPT = "TRANSMISSION_ATTEMPT"
    BROKER_EVENT = "BROKER_EVENT"
    CORRECTION = "CORRECTION"
    HALT = "HALT"
    RECOVERY = "RECOVERY"


class DurabilityClass(StrEnum):
    """Durability classes (design §2.5 B, ADR §10.1 line 273-278)."""

    PRE_EFFECT_DURABLE = "PRE_EFFECT_DURABLE"
    POST_EFFECT_BOUNDED = "POST_EFFECT_BOUNDED"
    EMERGENCY_DURABLE = "EMERGENCY_DURABLE"
    DERIVED_REBUILDABLE = "DERIVED_REBUILDABLE"
    DENY_IF_UNSPECIFIED = "DENY_IF_UNSPECIFIED"


class RetentionHorizon(StrEnum):
    """Retention horizons (design §2.5 B, ADR §17 line 434-439)."""

    BROKER_CORRECTION_LATE_FILL = "BROKER_CORRECTION_LATE_FILL"
    IDEMPOTENCY_REPLAY = "IDEMPOTENCY_REPLAY"
    ECONOMIC_EFFECT = "ECONOMIC_EFFECT"
    SAFETY_REVIEW = "SAFETY_REVIEW"
    INCIDENT_LEGAL_HOLD = "INCIDENT_LEGAL_HOLD"
    VERIFICATION_ACCEPTANCE = "VERIFICATION_ACCEPTANCE"


class ToleranceKind(StrEnum):
    """Replay comparison tolerance kinds (design §2.5 D, ADR §15 line 407)."""

    EXACT = "EXACT"
    ABSOLUTE = "ABSOLUTE"
    RELATIVE = "RELATIVE"


class PreservedProperty(StrEnum):
    """Properties a redaction profile must preserve (design §2.5 B, ADR §16 line 422)."""

    ORDERING = "ORDERING"
    QUANTITIES = "QUANTITIES"
    ECONOMIC_EFFECT = "ECONOMIC_EFFECT"
    IDENTITIES = "IDENTITIES"
    SCOPE = "SCOPE"
    OUTCOME = "OUTCOME"


class RemainingUncertainty(StrEnum):
    """Residual uncertainty after repair/recovery (design §2.5 C, ADR §14 line 372)."""

    UNKNOWN = "UNKNOWN"
    BOUNDED = "BOUNDED"
    RESOLVED = "RESOLVED"


class CausalLink(FrozenModel):
    """A typed causal edge to a predecessor record (design §2.5 A)."""

    edge_type: EdgeType
    target_id: str
    target_digest: str

    @model_validator(mode="after")
    def _require_immutable_target(self) -> CausalLink:
        """Reject a link whose target id or digest is absent/placeholder (§12 325)."""
        for name in ("target_id", "target_digest"):
            value = getattr(self, name)
            if not value or value == "TBD":
                raise ArtifactIntegrityError(
                    f"CausalLink.{name} must be a concrete immutable reference "
                    "(no mutable/'latest' alias, no timestamp-only link) — §2.5 A"
                )
        return self


class RecordClassDurabilityRule(FrozenModel):
    """Per-record-class durability rule (design §2.5 B, EIP line 21)."""

    record_class: str
    durability_class: DurabilityClass = DurabilityClass.DENY_IF_UNSPECIFIED
    required_replication: int | None = None
    acknowledgement_rule: str | None = None


class RequiredCausalParentRule(FrozenModel):
    """Required-causal-parent rule for a record class (design §2.5 B, EIP line 40)."""

    record_class: str
    required_parent_edge_types: tuple[EdgeType, ...] = ()


class SourceSequenceRule(FrozenModel):
    """Per-source-class sequence rule (design §2.5 B, EIP line 41, ADR §11)."""

    source_class: str
    requires_monotonic_local_sequence: bool = True
    continuity_reset_creates_new_identity: bool = True
    gap_or_dup_across_continuity_reconcilable_not_hideable: bool = True


class RetentionRecordClassRule(FrozenModel):
    """Per-record-class retention rule (design §2.5 B, EIP line 47, ADR §17)."""

    record_class: str
    horizons: tuple[RetentionHorizon, ...] = ()
    min_retention_ms: int | None = None


class RedactionProfile(FrozenModel):
    """A redaction view profile (design §2.5 B, ADR §16, ERI-INV-010)."""

    profile_id: str
    removed_fields: tuple[str, ...] = ()
    tokenized_fields: tuple[str, ...] = ()
    preserves_canonical_digest: bool = True
    preserves_field_presence: bool = True
    preserves: tuple[PreservedProperty, ...] = ()


class ObservedBranch(FrozenModel):
    """A preserved branch after fork/conflicting-restore (design §2.5 C, ADR §13 341)."""

    branch_id: str | None = None
    segment_id: str | None = None
    head_commitment: str | None = None
    store_continuity_id: str | None = None
    store_generation: int | None = None
    record_ids_in_branch: tuple[str, ...] = ()


class RecoverySource(FrozenModel):
    """A repair recovery source with custody (design §2.5 C, ADR §14 372, §19 474)."""

    source_ref: str | None = None
    custodian: str | None = None
    acquisition_method: str | None = None
    acquisition_time_snapshot_id: str | None = None
    transfer_history: tuple[str, ...] = ()
    remaining_uncertainty: RemainingUncertainty = RemainingUncertainty.UNKNOWN


class NormalizedViewVersion(FrozenModel):
    """A normalized view over raw records (design §2.5 D, ADR §5.9 line 126-128)."""

    view_id: str | None = None
    transform_identity: str | None = None
    transform_version: str | None = None
    raw_record_digests: tuple[str, ...] = ()


class SourceContinuityVector(FrozenModel):
    """A per-source continuity coordinate for replay (design §2.5 D, ADR §11)."""

    source_continuity_id: str | None = None
    workload_identity: str | None = None
    first_local_sequence: int | None = None
    last_local_sequence: int | None = None
    committed_prefix_position: int | None = None


class NondeterministicBoundary(FrozenModel):
    """A documented nondeterministic boundary (design §2.5 D, ERI-INV-009 line 170)."""

    boundary_id: str | None = None
    description: str | None = None
    bounded: bool = False
    seed_ref: str | None = None


class Tolerance(FrozenModel):
    """A replay comparison tolerance (design §2.5 D, ADR §15 line 407)."""

    field_ref: str | None = None
    tolerance_kind: ToleranceKind = ToleranceKind.EXACT
    tolerance_value: str | None = None
