"""are value models + injected inputs + the four digest-bound artifacts (design #13 §2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True, extra="forbid")``
via :class:`~tos.are._base.FrozenModel`): ``extra="forbid"`` is the schema-level realization
of §14 line 362 "reject unsupported or silently dropped dimensions" / §9 line 262 "cannot
declare a missing scope immaterial", and frozen is the record-level realization of
append-only immutability (§5.2 generation; §22 evidence) — there is **no** update / delete /
mutate method on any model (design #13 §2.0). enum values / field names use the ADR §5-§21
terms **verbatim** (spec terms = code terms, boundary design #1 §2.4; the
erratum-defect-class seal, design #13 §2.2).

Numeric magnitudes (current usage / effect / limit / headroom / increment) use the
already-core :data:`~tos.canonical.CanonicalDecimal` (design #13 §0.4c / §3.1) so ``1.0`` and
``1.00`` share one artifact digest and a NaN / infinity is **unconstructable** — never a bare
``Decimal`` / ``float`` (§14 line 358). Every magnitude / limit / floor / bound is otherwise
an **injected** value carried on the models, never hardcoded (design #13 §8): a missing value
fails closed at the consuming predicate.

The final ``AdverseIncrement[s,d]`` uses the rcl :class:`~tos.rcl.CapacityVector` type
(``vector.py:74``, ADR-002-002 §6 — the type owner) via the single ``are -> rcl`` sibling
edge (design #13 §0.4c / MAJOR-1): the increment is the exact type rcl commits
(``CommitReservation.proposed_adverse_increment``), so dominance is sealed at the **type
level** and no reduction reducer is needed. The intermediate per-(scope, dimension, scenario)
representation :class:`ProjectedCell` is are-local (it carries a scenario axis rcl
``CapacityVector`` does not). are REUSES the type only — capacity commit / serialize / benefit
arithmetic stays rcl-owned (§3.5; are mutates nothing, §4.5).

The four digest-bound citizens (``AggregateRiskPolicy`` / ``AggregateRiskStateSnapshot`` /
``AdverseScenarioSet`` / ``AggregateRiskDecision``) are each an
:class:`~tos.are._base.IndependentIdArtifact` with an independent, governance / evaluation
-assigned id (``id != f(digest)``, design #13 §3.1) so a same-id / different-bytes forged /
re-issued / contradictory decision is a detectable ``classify_record_pair``
``CRITICAL_CONFLICT``. Each generation is an immutable record; a legitimate revalidation /
supersession is a **new** generation (a fresh id), never an in-place mutation (design #13
§2.3). The ``AggregateRiskDecision`` is **forward-only** (§16 line 413): it carries **no**
future Capacity Commitment / reservation coordinate — rcl charges ``bound_reservation_*``
post-commit (non-cyclic, design #13 §5.6).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.are._base``) + the rcl
``CapacityVector`` type only; no ``shared.*``, no other sibling ``tos.*`` (design #13 §0.3).
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from tos.are._base import (
    AllFalseAggregateAuthority,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.are.vocabulary import (
    AdverseScenarioKind,
    BenefitKind,
    RiskDecisionResult,
    RiskDimensionKind,
    RiskScopeKind,
)
from tos.canonical import CanonicalDecimal
from tos.rcl import CapacityVector

__all__ = [
    "AggregateRiskAuthorityEffect",
    "RiskDimensionDescriptor",
    "ProjectedCell",
    "BenefitProof",
    "CancellationRiskInputs",
    "ValuationInputs",
    "AdverseIncrementResult",
    "AggregateRiskPolicy",
    "AggregateRiskStateSnapshot",
    "AdverseScenarioSet",
    "AggregateRiskDecision",
]


# ===========================================================================
# All-false authority effect (ARE-INV-009 / §7)
# ===========================================================================


class AggregateRiskAuthorityEffect(AllFalseAggregateAuthority):
    """Authority effect of a GRANT / decision / snapshot — every flag false (ARE-INV-009).

    ADR-002-021 §1 line 17 verbatim: "A ``GRANT`` is not capacity, Live Authorization, a
    Transmission Capability, or broker permission." The pure-model realization of ``capacity
    != authority`` (ARE-INV-009 line 185; rcl ``RclAuthorityEffect`` ``authority.py:19-36``
    isomorph): a non-authoritative artifact ``creates_capacity`` no capacity,
    ``permits_transmission`` nothing, ``issues_live_authorization`` nothing,
    ``grants_broker_permission`` nothing, and ``may_rearm`` nothing. Any ``True`` value makes
    the artifact unconstructable (the full "no capacity-mutation / broker path anywhere" proof
    is +Security EV-L2/L3, ARE-EV-011).
    """

    creates_capacity: bool = False
    permits_transmission: bool = False
    issues_live_authorization: bool = False
    grants_broker_permission: bool = False
    may_rearm: bool = False


# ===========================================================================
# Value models (plain frozen)
# ===========================================================================


class RiskDimensionDescriptor(FrozenModel):
    """One governed dimension's explicit vector semantics (ADR-002-021 §10 line 270-281).

    ARE-INV-004 line 166: each governed dimension SHALL have exact unit / sign / scope / limit
    source / valuation / aggregation / uncertainty / scenario semantics — a scalar notional /
    model score / VaR point / broker margin / local pass flag can never substitute for the
    vector (§1 line 21). The cross-dimension conversion coefficient is a Critical Input and
    "cannot silently default" (§10 line 281): a ``None`` ``conversion_coefficient`` fails the
    :func:`~tos.are.predicates.dimension_vector_integrity` check closed. Every field is
    injected (Phase-0 supplies the concrete per-product semantics, §28 q2); a ``None`` is
    UNKNOWN and never silently treated as present.
    """

    dimension: RiskDimensionKind | None = None
    scope: RiskScopeKind | None = None
    unit: str | None = None
    sign_convention: str | None = None
    limit_source: str | None = None
    valuation_rule: str | None = None
    aggregation_rule: str | None = None
    uncertainty_treatment: str | None = None
    correlation_treatment: str | None = None
    scenario_semantics: str | None = None
    freshness_requirement: str | None = None
    conversion_coefficient: CanonicalDecimal | None = None


class ProjectedCell(FrozenModel):
    """One per-(scope, dimension, scenario) projection record (ADR-002-021 §12 line 311-328).

    §12 line 311-321 verbatim ``ProjectedUsage[s,d,q] = ConservativeCurrentUsage +
    MaximumCredibleCommandEffect + RequiredConcurrentAndOverlapEffect``; ``AdverseIncrement[s,d]
    = max_q(ProjectedUsage - ConservativeCurrentUsageAlreadyCommitted)``. The component
    magnitudes are **injected** :data:`~tos.canonical.CanonicalDecimal` (are combines them
    arithmetically — a sum / difference / max — but is **not** a numeric engine: the valuation /
    scenario / correlation models are Phase-0, §4 non-scope). Any ``None`` component makes the
    derived quantity ``None`` (UNKNOWN propagates — fail-closed, §4.1/§4.3), never assume-zero.
    The §6.2 intermediate-state witnesses (``no_action_risk`` / ``worst_intermediate_risk`` /
    ``credible_space_bounded`` / ``no_credible_intermediate_increases_exceedance`` /
    ``already_exceeded_regime``) are injected per scenario for the protective-magnitude
    producers (design #13 §5.3); an unbounded credible space (``credible_space_bounded`` not
    ``True``) is UNKNOWN, never silently excluded (§19 line 470).
    """

    scope: RiskScopeKind | None = None
    dimension: RiskDimensionKind | None = None
    scenario: AdverseScenarioKind | None = None
    conservative_current_usage: CanonicalDecimal | None = None
    max_credible_command_effect: CanonicalDecimal | None = None
    required_concurrent_overlap_effect: CanonicalDecimal | None = None
    conservative_current_usage_already_committed: CanonicalDecimal | None = None
    effective_limit: CanonicalDecimal | None = None
    # §6.1/§6.2 conservative-risk magnitudes for the protective seam (injected per cell;
    # distinct from the usage components above — a protective action reduces risk, so
    # ``final_conservative_risk`` may be below ``current_conservative_risk``, §6.1 line 263).
    current_conservative_risk: CanonicalDecimal | None = None
    final_conservative_risk: CanonicalDecimal | None = None
    no_action_risk: CanonicalDecimal | None = None
    worst_intermediate_risk: CanonicalDecimal | None = None
    credible_space_bounded: bool | None = None
    no_credible_intermediate_increases_exceedance: bool | None = None
    already_exceeded_regime: bool | None = None

    def projected_usage(self) -> Decimal | None:
        """Return ``ConservativeCurrentUsage + MaxCredibleCommandEffect + OverlapEffect`` (§12).

        Pure ``Decimal`` addition (no float, no numeric engine). A ``None`` on **any**
        component yields ``None`` (UNKNOWN propagates conservatively — fail-closed, §4.1);
        it is never treated as zero.
        """
        parts = (
            self.conservative_current_usage,
            self.max_credible_command_effect,
            self.required_concurrent_overlap_effect,
        )
        total = Decimal(0)
        for part in parts:
            if part is None:
                return None
            total = total + part
        return total

    def requested_increment(self) -> Decimal | None:
        """Return ``ProjectedUsage - ConservativeCurrentUsageAlreadyCommitted`` (§12 line 321).

        §12 line 328: an intended reduction "cannot make the requested increment negative
        merely because the final target is smaller" — the projected usage already carries the
        worst credible temporary / overlap / reversal effect, so the difference stays positive
        where credible; are performs no ``max(0, ...)`` clamp that would erase it. ``None`` on
        either operand => ``None`` (fail-closed).
        """
        projected = self.projected_usage()
        committed = self.conservative_current_usage_already_committed
        if projected is None or committed is None:
            return None
        return projected - committed

    def headroom(self) -> Decimal | None:
        """Return ``EffectiveLimit - ConservativeCurrentUsageAlreadyCommitted`` (§5.6).

        ``None`` limit or ``None`` committed usage => ``None`` (fail-closed — a missing limit
        never admits an increment, §5.6/§14).
        """
        limit = self.effective_limit
        committed = self.conservative_current_usage_already_committed
        if limit is None or committed is None:
            return None
        return limit - committed


class BenefitProof(FrozenModel):
    """A netting / hedge / diversification / correlation benefit proof (ADR-002-021 §13).

    §13 line 336-342: a benefit reduces adverse capacity **only when positively proven** on
    all seven premises. Each premise is a ``bool`` defaulting ``False`` (absence is not proof),
    so a bare :class:`BenefitProof` proves nothing (design #13 §4.2 ∅-seal —
    :func:`~tos.are.predicates.benefit_admissible` returns ``False``). §13 line 344: a broker
    margin number, historical correlation, shared model output, recent co-movement, strategy
    label, or human assertion is not sufficient proof — those are **not** modeled as premise
    flags, so they can never be counted as proof.
    """

    kind: BenefitKind | None = None
    # §13 line 336-342 — the seven premises (each must be positively True).
    exact_identity_and_eligibility: bool = False
    current_enforceable_state_and_fqp: bool = False
    simultaneous_availability: bool = False
    approved_basis_correlation_liquidity_stress: bool = False
    margin_recognition: bool = False
    no_undeclared_common_mode: bool = False
    complete_adverse_leg_failure_scenario: bool = False
    proof_reference: str | None = None


class CancellationRiskInputs(FrozenModel):
    """Injected magnitudes for the protective cancellation-arbiter flags (design #13 §3.4).

    The conservative aggregate-risk magnitudes are (ADR §19 / §11.1-11.3) an injected
    projection input; the two produced flags
    (:func:`~tos.are.predicates.continued_existence_worsens_aggregate` /
    :func:`~tos.are.predicates.cancellation_worsens_aggregate`) compare them against the
    ``baseline_no_action_risk``. Any ``None`` makes the produced flag ``None`` (fail-closed —
    protective treats ``None`` as most-restrictive, ``predicates.py:529/531``).
    """

    continued_existence_risk: CanonicalDecimal | None = None
    post_cancellation_risk: CanonicalDecimal | None = None
    baseline_no_action_risk: CanonicalDecimal | None = None


class ValuationInputs(FrozenModel):
    """Injected valuation classification inputs (ADR-002-021 §14 line 350-354).

    §14 line 352: observation / executable / stress / liquidation / settlement / conversion
    prices — and stale / unknown — must be distinguished; "A zero, negative, future, crossed,
    stale, or missing value is not automatically conservative." Each is an injected ``bool |
    None`` load-bearing flag; the broker margin / buying-power figures are Critical Input
    ceilings, not proof the local model may omit exposure (§14 line 354). Any ``None`` / not-
    ``True`` fails :func:`~tos.are.predicates.valuation_conservative` closed.
    """

    price_classes_distinguished: bool | None = None
    stale_or_unknown_flagged: bool | None = None
    no_zero_negative_future_crossed_as_conservative: bool | None = None
    broker_figure_treated_as_ceiling_only: bool | None = None
    local_or_broker_more_restrictive_dominates: bool | None = None


class AdverseIncrementResult(FrozenModel):
    """The result of :func:`~tos.are.predicates.adverse_increment` (design #13 §5.3).

    Carries the ``RiskDecisionResult`` verdict (``UNKNOWN`` whenever a projection cell is
    absent / non-finite or the adverse-scenario coverage floor is unmet — never a smaller
    vector, §1 line 29) and the final ``AdverseIncrement[s,d]`` as the rcl
    :class:`~tos.rcl.CapacityVector` type (type-level dominance, design #13 §0.4c). The
    protective-magnitude producers (§3.4) read the seam values off this result; a ``None``
    magnitude propagates to the protective classifier as ``RISK_INCREASING_DENIED``
    (``protective/predicates.py:289-290``).
    """

    result: RiskDecisionResult = RiskDecisionResult.UNKNOWN
    increment: CapacityVector = CapacityVector()
    final_conservative_risk: CanonicalDecimal | None = None
    current_conservative_risk: CanonicalDecimal | None = None
    no_action_risk: CanonicalDecimal | None = None
    worst_intermediate_risk: CanonicalDecimal | None = None
    credible_space_bounded: bool | None = None
    no_credible_intermediate_increases_exceedance: bool | None = None
    already_exceeded_regime: bool | None = None


# ===========================================================================
# Digest-bound append-only artifacts
# ===========================================================================


class AggregateRiskPolicy(IndependentIdArtifact):
    """An append-only, generation-immutable Aggregate Risk Policy (ADR-002-021 §5.1 / §8).

    The governed dimensions / scopes and the canonical policy identity a decision binds (§8
    line 229 "canonical digest, signer, approval"; §22 line 508). A digest-bound
    :class:`~tos.are._base.IndependentIdArtifact` with an independent ``policy_id`` (``id !=
    f(digest)``, design #13 §3.1) so a same-id / different-bytes forged / re-issued generation
    is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``; a legitimate revalidation
    is a **new** generation (a fresh ``policy_id`` + ``policy_generation``), never an in-place
    mutation (design #13 §2.3). The policy is a member of the spg Safety Configuration Bundle
    (§5.1); are does not govern it, it references it by scalar (design #13 §8.2).

    ``_REQUIRED_COVERED`` lists **structural identity / generation / version** only (design
    #13 §2.3); the concrete per-product dimension set / numeric limits are Phase-0-injected and
    excluded so a policy is ISSUED-reachable under Phase-1 null bounds — a missing limit fails
    closed at the consuming predicate. Non-transmitting, non-enforcing (design #13 §4.5).
    """

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_generation",
        "policy_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "policy_version",
            "governed_dimensions",
            "governed_scopes",
            "signer_identity",
            "approval_identity",
            "evidence_package_ref",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    policy_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.1 / §8) ------------------------------
    policy_generation: int | None = None
    policy_version: str | None = None
    governed_dimensions: tuple[RiskDimensionKind, ...] = ()
    governed_scopes: tuple[RiskScopeKind, ...] = ()
    signer_identity: str | None = None
    approval_identity: str | None = None
    evidence_package_ref: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    policy_order: int | None = None


class AggregateRiskStateSnapshot(IndependentIdArtifact):
    """An append-only Aggregate Risk State Snapshot (ADR-002-021 §5.3 / §9).

    The consistency-cut aggregate state a projection reads (§15 line 375 "snapshot identity /
    cut / generations / digest"; §9 line 258). §5.3 line 124: the snapshot **grants no
    permission** — it is a non-authoritative representation, so it carries an all-false
    :class:`AggregateRiskAuthorityEffect` (ARE-INV-009). A digest-bound
    :class:`~tos.are._base.IndependentIdArtifact`; consistency-cut identity is orthogonal to
    the digest (design #13 §3.1). The snapshot is **assembled** by a runtime (§9 consistency-cut
    protocol is EV-L2/L3, §28 q3); are models it and reads injected fields, it does **not**
    assemble it.

    ``_REQUIRED_COVERED`` lists structural identity / cut only (design #13 §2.3); the numeric
    conservative-usage magnitudes are excluded so a snapshot is ISSUED-reachable under Phase-1
    null bounds — a missing magnitude fails closed at the consuming predicate.
    """

    _ID_FIELD: ClassVar[str] = "snapshot_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "snapshot_generation",
        "consistency_cut_identity",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "snapshot_generation",
            "consistency_cut_identity",
            "covered_scopes",
            "conservative_current_usage",
            "lineage_ref",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    snapshot_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.3 / §9) ------------------------------
    snapshot_generation: int | None = None
    consistency_cut_identity: str | None = None
    covered_scopes: tuple[RiskScopeKind, ...] = ()
    conservative_current_usage: CapacityVector = CapacityVector()
    lineage_ref: str | None = None
    # §5.3 line 124 — the snapshot grants no permission (all-false, ARE-INV-009).
    authority_effect: AggregateRiskAuthorityEffect = AggregateRiskAuthorityEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    snapshot_order: int | None = None

    def covers(self, scope: RiskScopeKind) -> bool:
        """Whether ``scope`` is among the snapshot's covered scopes (pure lookup)."""
        return scope in self.covered_scopes


class AdverseScenarioSet(IndependentIdArtifact):
    """An append-only, policy-bound Adverse Scenario Set (ADR-002-021 §5.4 / §11).

    The immutable set of credible adverse scenarios a projection dominates (§15 line 376
    "scenario set identity / generation / digest"). §5.4 line 128 / §11 line 301: the set is a
    **min-coverage floor**, never a whitelist — "Absence from the set is not proof that a
    credible adverse path can be ignored", so an empty / under-covering set fails closed
    (design #13 §4.7). A digest-bound :class:`~tos.are._base.IndependentIdArtifact`; a
    legitimate scenario add / prune is a **new** generation (§28 q5), never an in-place
    mutation (design #13 §2.3).

    ``_REQUIRED_COVERED`` lists structural identity / generation only; the concrete scenario
    values are Phase-0-injected and excluded (a missing value fails closed downstream).
    """

    _ID_FIELD: ClassVar[str] = "scenario_set_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("scenario_set_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "scenario_set_generation",
            "policy_binding_id",
            "covered_scenario_kinds",
            "evidence_package_ref",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    scenario_set_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.4 / §11) -----------------------------
    scenario_set_generation: int | None = None
    policy_binding_id: str | None = None
    covered_scenario_kinds: tuple[AdverseScenarioKind, ...] = ()
    evidence_package_ref: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    scenario_set_order: int | None = None

    def covered_kinds(self) -> frozenset[AdverseScenarioKind]:
        """The set of adverse-scenario kinds this set covers (pure)."""
        return frozenset(self.covered_scenario_kinds)


class AggregateRiskDecision(IndependentIdArtifact):
    """An append-only, forward-only Aggregate Risk Decision (ADR-002-021 §5.5 / §15 / §16).

    The GRANT / DENY / UNKNOWN result binding one exact snapshot / scenario-set / effect (§15
    line 373 "canonical digest"). **decision_id is orthogonal to the canonical_decision_digest**
    (rcl ``GrantDecisionRef`` ``authority.py:53/55`` carries them as **separate** fields — the
    consumer already presumes ``id != f(digest)``, design #13 §3.1) so a same-id / different-
    bytes contradictory / re-issued decision is a detectable ``classify_record_pair``
    ``CRITICAL_CONFLICT`` (two decisions can never be unioned / reused / patched, ARE-INV-002
    line 158). **Forward-only** (§16 line 413): it carries **no** future Capacity Commitment /
    reservation coordinate — rcl ``grant_authorizes_exact_request`` charges
    ``bound_reservation_*`` post-commit (the non-cyclic code realization, design #13 §5.6). The
    ``authority_effect`` is all-false (a GRANT is not capacity, ARE-INV-009).

    The ``adverse_increment`` is the rcl :class:`~tos.rcl.CapacityVector` type (type-level
    dominance, design #13 §0.4c). ``_REQUIRED_COVERED`` requires the generation + a concrete
    result; the numeric increment / limit are excluded so a DENY / UNKNOWN decision is
    ISSUED-reachable under Phase-1 null bounds. Non-transmitting, non-enforcing (design #13
    §4.5).
    """

    _ID_FIELD: ClassVar[str] = "decision_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "decision_generation",
        "result",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "decision_generation",
            "result",
            "policy_digest",
            "snapshot_digest",
            "scenario_set_digest",
            "effect_digest",
            "applicable_risk_scopes",
            "grant_identity",
            "adverse_increment",
            "effective_limit",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    decision_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.5 / §15 / §16) -----------------------
    decision_generation: int | None = None
    result: RiskDecisionResult | None = None
    policy_digest: str | None = None
    snapshot_digest: str | None = None
    scenario_set_digest: str | None = None
    effect_digest: str | None = None
    applicable_risk_scopes: tuple[str, ...] = ()
    grant_identity: str | None = None
    adverse_increment: CapacityVector = CapacityVector()
    effective_limit: CapacityVector = CapacityVector()
    authority_effect: AggregateRiskAuthorityEffect = AggregateRiskAuthorityEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    decision_order: int | None = None
