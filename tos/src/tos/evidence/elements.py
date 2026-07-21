"""Authored element schemas for the evidence templates (design #4 §2.5).

The canonical templates leave several arrays element-less (``causal_links: []``,
EIP rule lists, gap ``observed_branches``/``recovery_sources``, replay vectors).
This module authors those element schemas from the ADR-002-016 prose the design
cites (gap 1). Each element is a frozen model; enum-typed fields fail closed on
unregistered values (an unknown ``edge_type`` is unconstructable — design §2.5 A
MINOR-1).

Pure module: ``pydantic`` + stdlib only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel

# ===========================================================================
# Enums (closed sets except EdgeType, which is *provisional*, design §2.5 A)
# ===========================================================================


class EdgeType(StrEnum):
    """Causal-link edge types (design §2.5 A, ADR §5.5 line 112).

    **Provisional 11-type set (MINOR-1)**: ADR §5.5 line 112 is exemplary ("such
    as"), so this set is not closed for all time — Phase-0 (§9.2 item 5) may
    extend it under policy approval. But an *unregistered* edge type is
    fail-closed here: because ``CausalLink.edge_type`` is typed to this enum,
    constructing a link with an unknown edge type raises (unconstructable).
    """

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
    """Durability classes (design §2.5 B, ADR §10.1 line 273-278).

    ``DENY_IF_UNSPECIFIED`` is the fail-closed default: a record class with no
    rule denies new risk (EIP line 20).
    """

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
    """Residual uncertainty after repair/recovery (design §2.5 C, ADR §14 line 372).

    Fail-closed default ``UNKNOWN``: repair never restores former evidence
    strength, so uncertainty is preserved, not erased.
    """

    UNKNOWN = "UNKNOWN"
    BOUNDED = "BOUNDED"
    RESOLVED = "RESOLVED"


# ===========================================================================
# (A) ENVELOPE causal_links[] — Causal Link (design §2.5 A, ADR §5.5)
# ===========================================================================


class CausalLink(FrozenModel):
    """A typed causal edge to a predecessor record (design §2.5 A).

    Both ``target_id`` (immutable identity) and ``target_digest`` (immutable
    digest) are required and concrete: a mutable URL / filename / dashboard row /
    "latest" alias cannot be expressed (ADR §12 line 325). There is **no**
    timestamp field — a timestamp-only link is forbidden (ADR §5.5 line 112); time
    lives only in ``time_evidence`` and is never a causal edge. ``edge_type`` is
    typed to :class:`EdgeType`, so an unknown edge type is fail-closed.
    """

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


# ===========================================================================
# (B) EIP element schemas (design §2.5 B, ADR §5.3)
# ===========================================================================


class RecordClassDurabilityRule(FrozenModel):
    """Per-record-class durability rule (design §2.5 B, EIP line 21)."""

    record_class: str
    durability_class: DurabilityClass = DurabilityClass.DENY_IF_UNSPECIFIED
    required_replication: int | None = None  # injected bound (§8), null => UNKNOWN
    acknowledgement_rule: str | None = None


class RequiredCausalParentRule(FrozenModel):
    """Required-causal-parent rule for a record class (design §2.5 B, EIP line 40).

    A record class missing a required parent edge is an incomplete chain -> gap
    (ADR §12 line 326). The concrete matrix values are Phase-0 (§9.2 item 5); this
    is the schema only.
    """

    record_class: str
    required_parent_edge_types: tuple[EdgeType, ...] = ()


class SourceSequenceRule(FrozenModel):
    """Per-source-class sequence rule (design §2.5 B, EIP line 41, ADR §11)."""

    source_class: str
    requires_monotonic_local_sequence: bool = True
    continuity_reset_creates_new_identity: bool = True
    gap_or_dup_across_continuity_reconcilable_not_hideable: bool = True


class RetentionRecordClassRule(FrozenModel):
    """Per-record-class retention rule (design §2.5 B, EIP line 47, ADR §17).

    ``effective_horizon`` is the *longest* applicable horizon (ADR §17 line 432),
    computed by :func:`tos.evidence.predicates.effective_retention_horizon` — not
    stored. ``min_retention_ms`` is an injected bound (§8), null => UNKNOWN.
    """

    record_class: str
    horizons: tuple[RetentionHorizon, ...] = ()
    min_retention_ms: int | None = None


class RedactionProfile(FrozenModel):
    """A redaction view profile (design §2.5 B, ADR §16, ERI-INV-010).

    A profile preserves the canonical digest and field presence (a reviewer can
    detect that redaction occurred) and lists the safety properties it preserves.
    A profile that removes ordering / quantity / authority / effect / independence
    fields is INVALID — enforced by
    :func:`tos.evidence.predicates.redaction_profile_valid`.
    """

    profile_id: str
    removed_fields: tuple[str, ...] = ()
    tokenized_fields: tuple[str, ...] = ()
    preserves_canonical_digest: bool = True
    preserves_field_presence: bool = True
    preserves: tuple[PreservedProperty, ...] = ()


# ===========================================================================
# (C) GAP observed_branches[] / recovery_sources[] (design §2.5 C)
# ===========================================================================


class ObservedBranch(FrozenModel):
    """A preserved branch after fork/conflicting-restore (design §2.5 C, ADR §13 341).

    On a fork every branch is preserved; last-write-wins merge is forbidden
    (ADR §18 line 456, §22 line 523).
    """

    branch_id: str | None = None
    segment_id: str | None = None
    head_commitment: str | None = None
    store_continuity_id: str | None = None
    store_generation: int | None = None
    record_ids_in_branch: tuple[str, ...] = ()


class RecoverySource(FrozenModel):
    """A repair recovery source with custody (design §2.5 C, ADR §14 372, §19 474).

    Repair appends source / method / uncertainty / custody; it does not rewrite an
    interval or restore former evidence strength (ADR §14 line 372).
    """

    source_ref: str | None = None
    custodian: str | None = None
    acquisition_method: str | None = None
    acquisition_time_snapshot_id: str | None = None
    transfer_history: tuple[str, ...] = ()
    remaining_uncertainty: RemainingUncertainty = RemainingUncertainty.UNKNOWN


# ===========================================================================
# (D) REPLAY element schemas (design §2.5 D, ADR §15)
# ===========================================================================


class NormalizedViewVersion(FrozenModel):
    """A normalized view over raw records (design §2.5 D, ADR §5.9 line 126-128).

    References raw digests + a transform identity; it never overwrites raw
    (ERI-INV-005).
    """

    view_id: str | None = None
    transform_identity: str | None = None
    transform_version: str | None = None
    raw_record_digests: tuple[str, ...] = ()


class SourceContinuityVector(FrozenModel):
    """A per-source continuity coordinate for replay (design §2.5 D, ADR §11).

    Cross-continuity monotonic values must not be subtracted (§11 line 313); a
    reset creates a new identity (§11 line 315).
    """

    source_continuity_id: str | None = None
    workload_identity: str | None = None
    first_local_sequence: int | None = None
    last_local_sequence: int | None = None
    committed_prefix_position: int | None = None


class NondeterministicBoundary(FrozenModel):
    """A documented nondeterministic boundary (design §2.5 D, ERI-INV-009 line 170).

    ``bounded=False`` (unbounded) forces the replay result into
    {INCONCLUSIVE, DIVERGED} — never MATCH (design §6.1).
    """

    boundary_id: str | None = None
    description: str | None = None
    bounded: bool = False
    seed_ref: str | None = None


class Tolerance(FrozenModel):
    """A replay comparison tolerance (design §2.5 D, ADR §15 line 407).

    Safety-relevant fields require ``EXACT``; a tolerance can never turn a
    safety-relevant DIVERGED into a MATCH (design §6). ``tolerance_value`` is an
    injected bound (§8), null => UNKNOWN.
    """

    field_ref: str | None = None
    tolerance_kind: ToleranceKind = ToleranceKind.EXACT
    tolerance_value: str | None = None
