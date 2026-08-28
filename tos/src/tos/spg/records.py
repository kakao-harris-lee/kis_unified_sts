"""spg value models + the dual digest-bound governance artifacts (design #12 §2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True,
extra="forbid")`` via :class:`~tos.spg._base.FrozenModel`): ``extra="forbid"`` is the
schema-level realization of §7 line 226 "Unknown fields that can affect authority SHALL be
rejected" / §11 step 12 "no bypass through omitted, unknown, deprecated, duplicated, or
extension fields", and frozen is the record-level realization of append-only (§21 auditable
/ §5.4 no-reuse) — there is **no** update / delete / mutate method on any model (design #12
§2.0). enum values / field names use the ADR §5-§12 terms **verbatim** (spec terms = code
terms, boundary design #1 §2.4; the erratum-defect-class seal, design #12 §2.2).

Numeric limits / §11 boundary values use the promoted core
:data:`~tos.canonical.CanonicalDecimal` (design #12 §0.4c / §3.1) so ``1.0`` and ``1.00``
share one artifact digest — never a bare ``Decimal``. Every validity interval / review
deadline / staging age / approval age is otherwise an **injected** scalar carried on the
predicate-input models, never hardcoded (design #12 §8): a missing value fails closed at the
consuming predicate.

The five digest-bound citizens (``HardSafetyEnvelope`` / ``RuntimeSafetyProfile`` /
``SafetyConfigurationBundle`` / ``ActivationRecord`` / ``ConsumerCompatibilityManifest``)
are each an :class:`~tos.spg._base.IndependentIdArtifact` with an independent,
governance-assigned id (``id != f(digest)``, design #12 §3.1) so a same-id / different-bytes
forged / re-issued generation is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``.
Each generation is an immutable record; a legitimate revalidation / supersession is a **new**
generation (a fresh id, linked by ``superseded_version_link``), never an in-place mutation
(design #12 §2.3).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.spg._base``) + ``tos.spg``
only; no ``shared.*``, no other sibling ``tos.*`` (design #12 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.canonical import CanonicalDecimal
from tos.spg._base import FrozenModel, IndependentIdArtifact
from tos.spg.vocabulary import BundleMemberKind, ChangeDirection, ValidationReason

# ===========================================================================
# Value models (plain frozen) — artifact-covered content
# ===========================================================================


class EnvelopeVersion(FrozenModel):
    """The §7 version block of a Hard Safety Envelope generation (ADR-002-014 §7 line 214-224).

    Dates are **injected scalars** (opaque strings), never read from a clock — spg accesses
    no clock (design #12 §3.5). ``version`` is the immutable version identifier;
    ``superseded_version_link`` links a supersession chain whose order is carried by
    ``tos.ordering`` (design #12 §3.2). This block is covered (digest preimage), so a changed
    version / effective date / approver changes the envelope digest. Distinct type from
    :class:`ProfileVersion` and from ``brokercap.ProfileVersion`` (coordinate non-collapse,
    design #12 §4.4).
    """

    version: str | None = None
    effective_date: str | None = None
    evidence_package_version: str | None = None
    approver_identity: str | None = None
    expiration_or_revalidation_date: str | None = None
    superseded_version_link: str | None = None
    change_classification: str | None = None


class ProfileVersion(FrozenModel):
    """The §7 version block of a Runtime Safety Profile generation (ADR-002-014 §7 line 214-224).

    Structurally the §7 version block (as :class:`EnvelopeVersion`) but a **distinct type**
    on the safety-config-governance profile axis: ``spg.ProfileVersion is not
    brokercap.ProfileVersion`` (broker-capability axis) and is unrelated to the time
    ``safety_profile_version`` snapshot coordinate — coordinate non-collapse rests on
    distinct types + non-import (design #12 §4.4). Dates are injected scalars (no clock).
    """

    version: str | None = None
    effective_date: str | None = None
    evidence_package_version: str | None = None
    approver_identity: str | None = None
    expiration_or_revalidation_date: str | None = None
    superseded_version_link: str | None = None
    change_classification: str | None = None


class GovernedDimensionLimit(FrozenModel):
    """One governed dimension's limit + §7/§11 unit metadata (ADR-002-014 §9/§10/§11 step 3).

    Reused on both artifacts: a :class:`HardSafetyEnvelope` dimension carries ``envelope_max``
    (the maximum authority limit, §9 line 257-267) with ``profile_value`` ``None``; a
    :class:`RuntimeSafetyProfile` dimension carries ``profile_value`` (the exact operating
    value, §10) with ``envelope_max`` ``None``. ``envelope_max`` / ``profile_value`` are
    :data:`~tos.canonical.CanonicalDecimal` (scale-normalized so ``1.0`` == ``1.00`` at the
    digest; a bare ``Decimal`` is forbidden — §11 step 3 precision/rounding). The
    ``unit`` / ``multiplier`` / ``sign`` / ``precision`` / ``rounding`` / ``boundary``
    metadata stay distinct string fields (never folded into the magnitude — canonical §3.4
    safety-significant-distinction preservation); ``profile_within_envelope`` compares a
    profile dimension against the **same-``dimension``** envelope dimension and rejects a
    unit mismatch (design #12 §5.1/§5.2).

    A ``None`` magnitude is UNKNOWN and fails closed at the consuming predicate (missing max
    or value => not-within, §5.1); it is never silently treated as unbounded.
    """

    dimension: str | None = None
    envelope_max: CanonicalDecimal | None = None
    profile_value: CanonicalDecimal | None = None
    unit: str | None = None
    multiplier: str | None = None
    sign: str | None = None
    precision: str | None = None
    rounding: str | None = None
    boundary: str | None = None


class BundleMemberRef(FrozenModel):
    """A resolved reference to one Safety-Configuration-Bundle member (design #12 §2.2(4)/§5.3).

    Carries a member's ``kind`` + id / generation / digest scalars plus its
    resolution status (``resolved`` / ``immutable``). A member is bundle-complete only when
    it is present, ``resolved is True``, ``immutable is True``, and its ``member_id`` is
    concrete (design #12 §6.4); any ``None`` fails closed (an unresolved / floating /
    mutable member cannot create new-risk authority — SPG-INV-002 line 157). The 29 modeled
    kinds ride as :class:`~tos.spg.vocabulary.BundleMemberKind`; the 7 deferred
    sub-generation refs are Phase-0-injected refs whose ``kind`` may be ``None`` (an
    opaque Phase-0 ref) yet still must be resolved + immutable.
    """

    kind: BundleMemberKind | None = None
    member_id: str | None = None
    generation: int | None = None
    digest: str | None = None
    resolved: bool | None = None
    immutable: bool | None = None


class SemanticValidationResult(FrozenModel):
    """The rich semantic-validation verdict (ADR-002-014 §11 line 315; design #12 §5.2).

    §11 line 315 verbatim: "Validation must produce a deterministic result **and reason
    set** for one exact bundle digest." A thin ``bool`` cannot express the §20 per-failure
    response, so the verdict is rich: ``valid`` plus the ``rejected_dimensions`` and the
    ``reason_set`` of :class:`~tos.spg.vocabulary.ValidationReason` (design #12 §5.2 —
    the #11 thin-signature MINOR lesson). A **valid** result carries an **empty** reason set;
    an **invalid** result carries a **non-empty** reason set (at least one reason) — this is
    a construction invariant, so a vacuous "invalid with no reason" is unrepresentable
    (design #12 §4.2 ∅-seal).
    """

    valid: bool
    rejected_dimensions: frozenset[str] = frozenset()
    reason_set: frozenset[ValidationReason] = frozenset()
    bundle_digest: str | None = None

    @model_validator(mode="after")
    def _enforce_valid_reason_coupling(self) -> SemanticValidationResult:
        """Enforce the valid<->empty-reason-set invariant (design #12 §4.2 ∅-seal)."""
        if self.valid and self.reason_set:
            raise ValueError(
                "a VALID SemanticValidationResult must carry an empty reason_set "
                f"(got {sorted(self.reason_set)}) — design #12 §4.2"
            )
        if not self.valid and not self.reason_set:
            raise ValueError(
                "an INVALID SemanticValidationResult must carry >= 1 reason "
                "(a vacuous invalid is unrepresentable) — design #12 §4.2"
            )
        return self


# ===========================================================================
# Injected predicate-input models (plain frozen)
# ===========================================================================


class SemanticValidationInputs(FrozenModel):
    """Injected fold-step results for semantic validation (ADR-002-014 §11; design #12 §5.2).

    The §11 steps that are **sibling-owned** (folded here as ``bool | None``, fail-closed)
    plus the one cross-field observation and the injected direction verdict:

    * ``signature_and_revocation_ok`` — step 1 (signing / revocation; ADR-002-015 runtime).
    * ``canonical_reproducible`` — step 2 (``canonical_digest == H_ver(canonicalize(covered))``
      re-computable; a ``False`` => ``CANONICAL_DIGEST_IRREPRODUCIBLE``).
    * ``cross_field_consistent`` — step 5 (the cross-field constraint SET is a Phase-0
      INSTANCE value, so the observation is injected; a ``None`` / ``False`` =>
      ``CROSS_FIELD_CONSTRAINT_VIOLATION``, fail-closed).
    * ``aggregate_effect_within`` — step 7 (aggregate risk effect; ARE / ADR-002-021).
    * ``software_deployment_ok`` — step 8 (software / deployment; ADR-002-029).
    * ``bundle_member_digests_match`` — step 9 (member digest resolution; a ``False`` =>
      ``FLOATING_REFERENCE``).
    * ``time_validity_ok`` — step 10 (trustworthy-time validity; ADR-002-008 injected flag).
    * ``change_direction`` — step 11 direction verdict; ``PERMISSIVE`` / ``AUTHORITY_INCREASING``
      / ``None`` => ``UNORDERABLE_DIRECTION`` + non-live (§11 line 317). Only ``RESTRICTIVE``
      passes the direction gate.

    Every ``bool | None`` fails closed (``None`` UNKNOWN or ``False`` invalidates). The
    all-optional default makes a bare instance fail every fold step (design #12 §4.1).
    """

    signature_and_revocation_ok: bool | None = None
    canonical_reproducible: bool | None = None
    cross_field_consistent: bool | None = None
    aggregate_effect_within: bool | None = None
    software_deployment_ok: bool | None = None
    bundle_member_digests_match: bool | None = None
    time_validity_ok: bool | None = None
    change_direction: ChangeDirection | None = None


class ActivationInputs(FrozenModel):
    """Injected inputs for atomic mixed-generation activation (ADR-002-014 §13; design #12 §5.3).

    The four load-bearing seam bools spg produces for liveauth ``atomic_activation_ok``
    (``version_fully_active`` / ``mixed_versions_present`` / ``units_compatible`` /
    ``envelope_bounded``) plus the two staging / attestation gates that route a
    not-yet-committed activation to ``DEFERRED``. Every ``bool | None`` fails closed: only a
    positive ``True`` (and, for ``mixed_versions_present``, a positive ``False``) admits
    ``COMMITTABLE`` (§13 line 385 "Partial distribution, mixed versions, missing values,
    incompatible units, or unverifiable activation state SHALL fail closed").
    """

    version_fully_active: bool | None = None
    mixed_versions_present: bool | None = None
    units_compatible: bool | None = None
    envelope_bounded: bool | None = None
    staging_complete: bool | None = None
    attestation_complete: bool | None = None


class ChangeDirectionInputs(FrozenModel):
    """Injected observations for the change-direction verdict (ADR-002-014 §5.9/§14; §5.5).

    A restrictive-only classification requires **positive proof** on every axis; anything
    unproven / widening / semantics-altering folds to ``AUTHORITY_INCREASING`` (design #12
    §5.5). Fields:

    * ``previously_denied_now_permitted`` — a previously denied / more-constrained scope is
      now permitted (``True`` => ``AUTHORITY_INCREASING``; §5.9 line 143).
    * ``all_dimensions_ordered_conservative`` — every dimension can be conservatively ordered
      (``None`` / ``False`` => unorderable/unproven => ``AUTHORITY_INCREASING``; §11 line 317).
    * ``semantics_changed`` — a nominal reduction that changes unit / aggregation /
      scope-exclusion / fallback / protective-ownership / broker-capability / state-confidence
      / calculation semantics (``True`` / ``None`` => cannot be presumed restrictive =>
      ``AUTHORITY_INCREASING``; §14 line 405 verbatim).
    * ``any_dimension_widened`` — at least one dimension enlarges (``True`` => ``PERMISSIVE``;
      §5.9 line 143).
    * ``all_narrowing_or_equal`` — every credible dimension only denies / narrows (the sole
      positive path to ``RESTRICTIVE``; §14 line 393).
    """

    previously_denied_now_permitted: bool | None = None
    all_dimensions_ordered_conservative: bool | None = None
    semantics_changed: bool | None = None
    any_dimension_widened: bool | None = None
    all_narrowing_or_equal: bool | None = None


class RestrictiveOverrideInputs(FrozenModel):
    """Injected preservation flags for a restrictive override (ADR-002-014 §14 line 395-403; §5.5).

    A restrictive override is admissible only when the change direction is ``RESTRICTIVE``
    **and** every preservation flag is positively ``True`` (design #12 §5.5): no auto-revert
    (§14 line 402), and capacity / orders / exposure / UNKNOWN / protective coverage are all
    preserved (§14 line 401). Any ``None`` / ``False`` fails closed. The economic-continuity
    magnitudes themselves are rcl-owned (§19); spg carries only the direction verdict + these
    preservation booleans.
    """

    no_auto_revert: bool | None = None
    capacity_preserved: bool | None = None
    orders_preserved: bool | None = None
    exposure_preserved: bool | None = None
    unknown_preserved: bool | None = None
    protective_preserved: bool | None = None


class RollbackInputs(FrozenModel):
    """Injected preconditions for a rollback = new proposal (ADR-002-014 §17 line 452-458; §6.1).

    §17 line 452 verbatim: "Rollback is a new proposal, never a state reversal." Reusing an
    older artifact is admissible only as a **new generation** with **current** schema /
    software / broker / time validation, **current** approval, break-before-make, and a
    **fresh** re-arm (design #12 §6.1). Every ``bool | None`` fails closed. The
    restore-generation fence enforcement is rcl-owned (``restore_generation``); +Security
    historical-signature replay is not-Phase-1 (design #12 §1).
    """

    new_generation_issued: bool | None = None
    current_schema_valid: bool | None = None
    current_approval: bool | None = None
    break_before_make: bool | None = None
    fresh_rearm: bool | None = None


class CompatibilityQuery(FrozenModel):
    """The consumer-compatibility requirements a manifest must cover (ADR-002-014 §16; §6.3).

    The exact schemas / fields / units / calculations / constraints / failure-semantics the
    bundle requires a consumer to declare (§16 line 434-436). A
    :class:`ConsumerCompatibilityManifest` matches only when each required set is a subset of
    the consumer's declared set (design #12 §6.3); a cache miss / inability to establish
    currentness is denial (§16 line 442). All default-empty tuples.
    """

    required_schemas: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    required_units: tuple[str, ...] = ()
    required_calculations: tuple[str, ...] = ()
    required_constraints: tuple[str, ...] = ()
    required_failure_semantics: tuple[str, ...] = ()


# ===========================================================================
# Digest-bound append-only governance artifacts
# ===========================================================================


class HardSafetyEnvelope(IndependentIdArtifact):
    """An append-only, generation-immutable Hard Safety Envelope (ADR-002-014 §7/§9).

    The maximum authority ceiling (§9 line 257-267): the mandatory governed dimensions +
    their maxima, the permitted scope, and the prohibited fallbacks, under a §7 version
    block. A digest-bound :class:`~tos.spg._base.IndependentIdArtifact` with an independent
    ``envelope_id`` (``id != f(digest)``, design #12 §3.1) so a same-id / different-bytes
    forged or re-issued generation is a detectable ``classify_record_pair``
    ``CRITICAL_CONFLICT``; a legitimate revalidation / supersession is a **new** generation
    (a fresh ``envelope_id`` + ``envelope_generation``, linked by
    ``EnvelopeVersion.superseded_version_link``), never an in-place mutation (design #12
    §2.3; §5.4 line 123 "cannot be reused after rejection, revocation, rollback, restore, or
    supersession").

    ``_REQUIRED_COVERED`` lists **structural identity / version / generation** only (design
    #12 §2.3); the numeric maxima inside ``governed_dimensions`` are excluded so an envelope
    is ISSUED-reachable under Phase-1 null bounds (the recon / liveauth / brokercap
    ``records.py`` discipline) — a missing maximum fails closed at the consuming predicate.
    ``envelope_order`` is self-excluded from the digest preimage (it carries the append-only
    ``tos.ordering`` generation order, set at ledger placement). This record has **no** egress
    / capacity-mutation / authorization-issue / activation-commit method — it is a
    non-transmitting, non-enforcing representation (design #12 §4.5).
    """

    _ID_FIELD: ClassVar[str] = "envelope_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "envelope_generation",
        "envelope_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "envelope_generation",
            "envelope_version",
            "governed_dimensions",
            "permitted_scope",
            "prohibited_fallbacks",
            "residual_risk_ceiling",
            "evidence_package_ref",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    envelope_id: str | None = None

    # ---- Layer-1 covered content (ADR §7 / §9) --------------------------------
    envelope_generation: int | None = None
    envelope_version: EnvelopeVersion | None = None
    governed_dimensions: tuple[GovernedDimensionLimit, ...] = ()
    permitted_scope: tuple[str, ...] = ()
    prohibited_fallbacks: tuple[str, ...] = ()
    residual_risk_ceiling: CanonicalDecimal | None = None
    evidence_package_ref: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    envelope_order: int | None = None

    def max_for(self, dimension: str) -> CanonicalDecimal | None:
        """Return the envelope maximum for ``dimension``, or ``None`` if **undeclared**.

        An undeclared dimension has no maximum (``None``) — the caller maps a ``None`` to
        most-restrictive (a profile referencing an undeclared dimension is over-envelope;
        design #12 §4.1 / §5.1). Pure lookup over the frozen tuple; mutates nothing.
        """
        for gdl in self.governed_dimensions:
            if gdl.dimension == dimension and gdl.dimension is not None:
                return gdl.envelope_max
        return None

    def boundary_for(self, dimension: str) -> str | None:
        """Return the declared ``boundary`` inclusion token for ``dimension``, else ``None``.

        The §11 step 3 (line 304) "boundary inclusion" metadata of the envelope-side
        (constraint-owning) dimension, which decides whether the envelope maximum is
        itself inside the permitted set (``tos.spg.predicates._exceeds_envelope_maximum``;
        EV-L2 pilot design §5 H-2). First-match lookup with exactly the :meth:`max_for`
        semantics, so a maximum and its boundary are always read from the **same**
        declaration. Pure lookup over the frozen tuple; mutates nothing.
        """
        for gdl in self.governed_dimensions:
            if gdl.dimension == dimension and gdl.dimension is not None:
                return gdl.boundary
        return None

    def declares(self, dimension: str) -> bool:
        """Whether ``dimension`` is a declared governed dimension of this envelope."""
        return any(
            gdl.dimension == dimension and gdl.dimension is not None
            for gdl in self.governed_dimensions
        )


class RuntimeSafetyProfile(IndependentIdArtifact):
    """An append-only, generation-immutable Runtime Safety Profile (ADR-002-014 §7/§10).

    One exact live scope operating **at or below** a single Hard Safety Envelope generation
    (§10 line 281 "one exact envelope id and generation"): the explicit governed-dimension
    operating values, the explicit scope, permitted behaviors, and fallback rules (all <=
    the envelope), under a §7 version block. A digest-bound
    :class:`~tos.spg._base.IndependentIdArtifact` with an independent ``profile_id``
    (``id != f(digest)``, design #12 §3.1); each generation is immutable and a legitimate
    revalidation is a **new** generation (design #12 §2.3). ``target_envelope_id`` /
    ``target_envelope_generation`` pin the one exact envelope this profile operates under
    (checked by ``profile_within_envelope``, design #12 §5.1). Non-transmitting,
    non-enforcing (design #12 §4.5).
    """

    _ID_FIELD: ClassVar[str] = "profile_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "profile_generation",
        "profile_version",
        "target_envelope_id",
        "target_envelope_generation",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "profile_generation",
            "profile_version",
            "target_envelope_id",
            "target_envelope_generation",
            "governed_dimensions",
            "scope",
            "permitted_behaviors",
            "fallback_rules",
            "evidence_package_ref",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    profile_id: str | None = None

    # ---- Layer-1 covered content (ADR §7 / §10) -------------------------------
    profile_generation: int | None = None
    profile_version: ProfileVersion | None = None
    target_envelope_id: str | None = None
    target_envelope_generation: int | None = None
    governed_dimensions: tuple[GovernedDimensionLimit, ...] = ()
    scope: tuple[str, ...] = ()
    permitted_behaviors: tuple[str, ...] = ()
    fallback_rules: tuple[str, ...] = ()
    evidence_package_ref: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    profile_order: int | None = None

    def value_for(self, dimension: str) -> CanonicalDecimal | None:
        """Return the profile operating value for ``dimension``, or ``None`` if absent.

        A ``None`` (absent or unbounded) fails closed at the consuming predicate (missing
        value is over-envelope, design #12 §5.1). Pure lookup; mutates nothing.
        """
        for gdl in self.governed_dimensions:
            if gdl.dimension == dimension and gdl.dimension is not None:
                return gdl.profile_value
        return None


class SafetyConfigurationBundle(IndependentIdArtifact):
    """A closed Safety Configuration Bundle (ADR-002-014 §5.3; design #12 §2.2(4)).

    Holds the one exact Envelope + Profile it governs (nested, so
    :func:`~tos.spg.predicates.semantic_validation` is self-contained for the L1 steps) plus
    the ``tuple[BundleMemberRef]`` of the 29 modeled members + 7 Phase-0-injected refs.
    ``bundle_complete`` (design #12 §6.4) requires every required member present / resolved /
    immutable; SPG-INV-002 line 157 "No new-risk authority is created from a partial,
    unresolved, mutable, or open-ended Safety Configuration Bundle". A digest-bound
    :class:`~tos.spg._base.IndependentIdArtifact`; the bundle digest binds the exact
    envelope + profile + member set. Non-transmitting, non-enforcing (design #12 §4.5).
    """

    _ID_FIELD: ClassVar[str] = "bundle_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("bundle_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "bundle_generation",
            "envelope",
            "profile",
            "members",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    bundle_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.3) -----------------------------------
    bundle_generation: int | None = None
    envelope: HardSafetyEnvelope | None = None
    profile: RuntimeSafetyProfile | None = None
    members: tuple[BundleMemberRef, ...] = ()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    bundle_order: int | None = None

    def member_for(self, kind: BundleMemberKind) -> BundleMemberRef | None:
        """Return the member ref for ``kind``, or ``None`` if **absent** (fail-closed)."""
        for ref in self.members:
            if ref.kind is kind:
                return ref
        return None


class ActivationRecord(IndependentIdArtifact):
    """A safety-configuration ActivationRecord (ADR-002-014 §5.7 line 133-135; §13/§15).

    Records a single activation: the ``profile_generation``, the complete artifact digests,
    the scope, the approval ids, the compatibility-attestation refs, the ``predecessor_generation``
    it serializes against (§15), and the restrictive-generation effects. §5.7 line 135
    verbatim: it "grants no Live Authorization by itself" — this record has **no** method
    that activates / authorizes / mutates capacity (design #12 §4.5). A digest-bound
    :class:`~tos.spg._base.IndependentIdArtifact`; the record is the SPG-EV-012 decision-replay
    substrate (design #12 §5.7).
    """

    _ID_FIELD: ClassVar[str] = "activation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("profile_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "profile_generation",
            "envelope_digest",
            "profile_digest",
            "bundle_digest",
            "scope",
            "approval_ids",
            "compatibility_attestation_refs",
            "predecessor_generation",
            "restrictive_generation_effects",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    activation_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.7 / §13 / §15) -----------------------
    profile_generation: int | None = None
    envelope_digest: str | None = None
    profile_digest: str | None = None
    bundle_digest: str | None = None
    scope: tuple[str, ...] = ()
    approval_ids: tuple[str, ...] = ()
    compatibility_attestation_refs: tuple[str, ...] = ()
    predecessor_generation: int | None = None
    restrictive_generation_effects: tuple[str, ...] = ()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    activation_order: int | None = None


class ConsumerCompatibilityManifest(IndependentIdArtifact):
    """A Consumer Compatibility Manifest (ADR-002-014 §5.6 line 129-131; §16).

    A consumer's declaration of the exact schemas / fields / units / calculations /
    constraints / failure-semantics it can handle (§16 line 434-436), under a manifest
    version. ``compatibility_manifest_matches`` (design #12 §6.3) admits only when the
    bundle's requirements are all covered; an empty manifest is a vacuous non-match (denial,
    design #12 §6.3). A digest-bound :class:`~tos.spg._base.IndependentIdArtifact`;
    non-transmitting, non-enforcing (design #12 §4.5).
    """

    _ID_FIELD: ClassVar[str] = "manifest_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("consumer_identity",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "consumer_identity",
            "manifest_version",
            "declared_schemas",
            "declared_fields",
            "declared_units",
            "declared_calculations",
            "declared_constraints",
            "declared_failure_semantics",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    manifest_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.6 / §16) -----------------------------
    consumer_identity: str | None = None
    manifest_version: str | None = None
    declared_schemas: tuple[str, ...] = ()
    declared_fields: tuple[str, ...] = ()
    declared_units: tuple[str, ...] = ()
    declared_calculations: tuple[str, ...] = ()
    declared_constraints: tuple[str, ...] = ()
    declared_failure_semantics: tuple[str, ...] = ()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    manifest_order: int | None = None
