"""venue models + injected inputs + the three core admissibility artifacts (design #19 §2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True,
extra="forbid")`` via :class:`~tos.venue._base.FrozenModel`): ``extra="forbid"`` is the
schema-level realization of "omission is restrictive" (no unknown / silently-dropped field),
and frozen is the record-level realization of the append-only, current-Constraint-Generation-
bound transition log; there is **no** update / delete / mutate method on any model (design #19
§2.0/§4.6). Field names use the ADR §5-§22 terms **verbatim** (spec terms = code terms,
boundary design #1 §2.4).

**Numeric-bound freedom (design #19 §8; ADR §4 non-scope line 103).** venue carries no numeric
tick / lot / band constant: every price band / tick / lot / quantity bound is an **injected**
opaque scalar carried as **policy content** on :class:`VenueShapeConstraints` (null in Phase 1,
fail-closed at the consuming predicate). Nothing numeric is hardcoded — the admissibility logic
is over StrEnums, booleans, set/graph membership, and injected values only.

**Three core artifacts are id-independent (design #19 §2.1/§3.1).**
``VenueConstraintPolicy`` / ``VenueConstraintSnapshot`` / ``OrderAdmissibilityDecision`` are
**issued-identity** records (:class:`~tos.venue._base.IndependentIdArtifact`,
``id != f(digest)``): the id is separately issued, so a same-id / different-bytes forged,
re-issued, contradictory (snapshot / decision substitution §14 / §22), or replayed record is a
detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``. The identity shape is **not**
guessed — the capsule ``VenueConstraintPolicyRef`` = {``policy_id``, ``policy_generation``,
``canonical_digest``}, ``VenueConstraintSnapshotRef`` = {``snapshot_id``,
``constraint_generation``, ``canonical_digest``}, and ``OrderAdmissibilityDecisionRef`` =
{``decision_id``, ``canonical_digest``} (``capsule/capsule.py:130-150``) already fixed it; this
module follows those coordinates (design #19 §2.1). ``ConstraintGeneration`` is **not** a class
here: the monotonic restrictive generation order is REUSED from :mod:`tos.ordering`
(``compare_order``, design #19 §3.2), and the ``constraint_generation`` scalar coordinate is an
``int`` (§0.4e). Every decision carries an all-false
:class:`~tos.venue._base.VenueGateAuthorityEffect` (admissibility != authority, VTG-INV-011).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.venue._base``) only; no
``shared.*``, no sibling ``tos.*`` (design #19 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.venue._base import (
    FrozenModel,
    IndependentIdArtifact,
    VenueGateAuthorityEffect,
)
from tos.venue.vocabulary import (
    ActionClass,
    ConstraintClass,
    OrderAdmissibilityResult,
    TradabilityState,
)

__all__ = [
    # injected inputs / value models
    "InstrumentRouteFields",
    "OrderShapeFields",
    "VenueShapeConstraints",
    "StageBinding",
    "BindingChain",
    "SourceObservation",
    "PolicyResolution",
    "AccountMarginFacts",
    "SourceContinuity",
    "ActionPhaseAdmission",
    "ActionTradability",
    "DependencyEdge",
    "ConstraintDependencyClosure",
    "MaterialConstraintChange",
    # core issued-identity artifacts
    "VenueConstraintPolicy",
    "VenueConstraintSnapshot",
    "OrderAdmissibilityDecision",
    # all-false authority
    "VenueGateAuthorityEffect",
]


# ===========================================================================
# Injected inputs + value models (plain frozen)
# ===========================================================================


class InstrumentRouteFields(FrozenModel):
    """The exact instrument / contract / account / route binding fields (ADR §11 line 281).

    §11 line 281: an admissible decision binds the canonical instrument identity plus **every**
    routing-relevant alias / venue listing / market segment / contract month / product /
    currency / multiplier / expiration / settlement / account / environment / broker / route.
    Consumed by :func:`~tos.venue.predicates.exact_instrument_route_bound`, which requires an
    **exact** match on every field (a ``None`` / mismatch is a substitution and fails closed —
    §11 AC-003 line 613 "Every mismatch must be rejected"). ``routing_relevant_aliases`` is
    compared for **exact set equality** (both-ways: a missing routing field OR a spurious alias
    substitution fails, design #19 §4.7).
    """

    canonical_instrument_id: str | None = None
    venue_listing: str | None = None
    market_segment: str | None = None
    contract_month: str | None = None
    product_type: str | None = None
    currency: str | None = None
    multiplier: str | None = None
    expiration: str | None = None
    settlement_method: str | None = None
    account_mapping: str | None = None
    environment: str | None = None
    broker: str | None = None
    route: str | None = None
    #: The routing-relevant alias set — compared for exact set equality (§11 line 281).
    routing_relevant_aliases: frozenset[str] = frozenset()


class VenueShapeConstraints(FrozenModel):
    """The injected venue order-shape constraints (ADR §12 line 297-311 — all values injected).

    Every price band / tick / lot / quantity value is **injected policy content** (design #19
    §8.0 — nothing numeric is hardcoded); a ``None`` band / tick / lot means the constraint is
    unknown and :func:`~tos.venue.predicates.order_shape_admissible` fails closed (``UNKNOWN``),
    never a permissive default (§8 line 245). The allowed order-type / TIF / side /
    position-effect sets are policy-declared; an **empty** allowed set means "nothing admitted"
    (fail-closed), not "anything admitted". A ``tick_size`` / ``lot_size`` of zero is an
    invalid injected constraint (``UNKNOWN``), not a divisor.
    """

    #: Opaque injected scaled price band (inclusive); ``None`` => unknown => fail-closed.
    price_min: int | None = None
    price_max: int | None = None
    #: Opaque injected price tick (scaled); ``None`` / ``0`` => unknown/invalid => fail-closed.
    tick_size: int | None = None
    #: Opaque injected quantity lot / min / max; ``None`` => unknown => fail-closed.
    lot_size: int | None = None
    min_quantity: int | None = None
    max_quantity: int | None = None
    #: Policy-declared admitted order types / TIFs / sides / position effects (empty => none).
    allowed_order_types: frozenset[str] = frozenset()
    allowed_tifs: frozenset[str] = frozenset()
    allowed_sides: frozenset[str] = frozenset()
    allowed_position_effects: frozenset[str] = frozenset()


class OrderShapeFields(FrozenModel):
    """The exact order shape under evaluation (ADR §12 line 297-311).

    The proposed broker-request shape — price / quantity / order-type / TIF / side /
    position-effect — checked against :class:`VenueShapeConstraints` **without permissive
    rounding** (§12 line 299). ``silently_rounded`` is the positive witness that the shape was
    **not** silently normalized / widened: rounding that changes the shape creates a new
    broker-request shape requiring a new decision (§12 line 309), so anything other than a
    positive ``False`` (i.e. ``True`` or ``None``) fails closed (VTG-AC-004 line 617 "Silent
    normalization or widening must fail"). Price / quantity are opaque injected scaled ints.
    """

    price: int | None = None
    quantity: int | None = None
    order_type: str | None = None
    tif: str | None = None
    side: str | None = None
    position_effect: str | None = None
    #: Positive witness the shape was NOT silently rounded/normalized (§12 line 309); anything
    #: but ``False`` (``True`` / ``None``) => a new shape is required => INADMISSIBLE.
    silently_rounded: bool | None = None


class StageBinding(FrozenModel):
    """One stage's binding of the exact decision identity (ADR §16 line 363-373).

    Each downstream stage (proposal / approval / intent / candidate command / capacity /
    authority / capability / commit-proof / egress) binds the decision by the **same**
    ``decision_id`` and ``canonical_digest``. A missing / mismatched / stale binding is
    rejected (:func:`~tos.venue.predicates.decision_binding_exact`; §16 line 377).
    """

    stage: str | None = None
    bound_decision_id: str | None = None
    bound_decision_digest: str | None = None


class BindingChain(FrozenModel):
    """The exact decision binding chain across downstream stages (ADR §16 line 363-373).

    The decision identity (``decision_id`` + ``canonical_digest``) plus every stage's binding.
    :func:`~tos.venue.predicates.decision_binding_exact` requires the chain to be non-empty and
    every stage to bind the **same** exact identity — a patch / partial-refresh / union / widen
    is unrepresentable (§14 line 343; §16 line 377). An **empty** ``stage_bindings`` is not
    "nothing to bind" — it fails closed (design #19 §4.7).
    """

    decision_id: str | None = None
    decision_digest: str | None = None
    stage_bindings: tuple[StageBinding, ...] = ()


class SourceObservation(FrozenModel):
    """One venue / broker / quote / calendar source observation (ADR §10 line 275).

    A single source's observed tradability-relevant ``state`` token plus its provenance. §10
    line 275: conflicting observations do not auto-resolve — "majority or newest-arrival
    selection is not automatically authoritative"; a source state is an **input, not
    permission**. Consumed by :func:`~tos.venue.predicates.tradability_conflict_unknown`.
    """

    source_id: str | None = None
    #: The observed tradability-relevant state token (e.g. an injected phase / open / halted).
    state: str | None = None
    generation: int | None = None


class PolicyResolution(FrozenModel):
    """A policy-defined conflict resolution (ADR §10 line 275).

    §10 line 275: only a **policy-defined** resolution — never automatic majority / newest —
    may resolve conflicting source observations. ``resolved_result`` is the governed outcome
    the policy declares; a ``None`` means no resolution is available and the conflict stays
    ``UNKNOWN`` (:func:`~tos.venue.predicates.tradability_conflict_unknown`).
    """

    resolution_id: str | None = None
    resolved_result: OrderAdmissibilityResult | None = None


class AccountMarginFacts(FrozenModel):
    """Account / margin / borrow / settlement eligibility facts (ADR §13 line 315-325).

    §13 line 319 verbatim: "Margin, buying power, borrow availability, or account eligibility is
    **not inferred** from a stale balance, a previous successful order, or the absence of a
    broker error." Every ``inferred_from_*`` flag records a **forbidden** optimistic basis: a
    positive ``True`` on any of them makes the facts non-conservative
    (:func:`~tos.venue.predicates.account_constraint_conservative`). ``fresh`` and
    ``corroborated`` are the positive witnesses a headroom claim must carry (broker-agnostic —
    capability-class language only, §13; no concrete broker named). The concrete broker / margin
    query and per-field confidence are +Broker / recon (§3.5); this model carries the
    conservatism witnesses only.
    """

    #: Positive witnesses (both required for a conservative headroom claim).
    fresh: bool | None = None
    corroborated: bool | None = None
    #: Forbidden optimistic bases (§13 line 319) — any positively ``True`` => not conservative.
    inferred_from_stale_balance: bool | None = None
    inferred_from_prior_order: bool | None = None
    inferred_from_absence_of_error: bool | None = None


class SourceContinuity(FrozenModel):
    """Source continuity facts (ADR §9 line 249-263 / §15).

    §9 line 263: restart / reconnect / endpoint-or-credential substitution / sequence reset /
    rollback / failover / missed-page / stale-cache / unverifiable continuity requires a new
    continuity identity or an explicit gap — **unknown continuity invalidates** affected future
    decisions (:func:`~tos.venue.predicates.unknown_continuity_invalidates`). ``verifiable`` is
    the positive witness; any gap flag positively ``True``, or an absent continuity identity,
    fails closed.
    """

    continuity_id: str | None = None
    verifiable: bool | None = None
    restarted: bool | None = None
    reconnected: bool | None = None
    sequence_reset: bool | None = None
    rolled_back: bool | None = None
    failed_over: bool | None = None


class ActionPhaseAdmission(FrozenModel):
    """One action's policy-declared admitting session-phase set (ADR §10 line 273 / §5.5).

    The policy declares, for one exact :class:`~tos.venue.vocabulary.ActionClass`, the set of
    session-phase **tokens** (injected opaque strings, §2.2(3)) in which that action is
    admitted. An **empty** ``admitting_phases`` admits nothing (fail-closed — a vacuous admit is
    not an admit, design #19 §4.7). A phase A decision may not be reused in phase B (§10 line
    273), so the set is per-exact-action; :func:`~tos.venue.state.session_phase_admits` gates on
    membership only.
    """

    action: ActionClass | None = None
    admitting_phases: frozenset[str] = frozenset()


class ActionTradability(FrozenModel):
    """One action's per-action tradability verdict (ADR §11 line 283-291).

    Binds one :class:`~tos.venue.vocabulary.ActionClass` to its
    :class:`~tos.venue.vocabulary.TradabilityState` — the per-action dimension §11 line 291
    requires ("a global ``tradable=true`` field is insufficient").
    """

    action: ActionClass | None = None
    state: TradabilityState | None = None


class DependencyEdge(FrozenModel):
    """One node's dependent-adjacency edge for the material-change closure (ADR §18 line 404-412).

    A ``{node -> dependents}`` adjacency edge; the material-change dependency closure
    (:func:`~tos.venue.predicates.material_change_closure`) computes transitive reachability
    over the edge set. An ``unproven`` edge (isolation not yet proven) is **expanded** exactly
    like a definite edge (under-count is a fail-open, §18 line 412 / §5.8).
    """

    node: str | None = None
    dependents: frozenset[str] = frozenset()


class ConstraintDependencyClosure(FrozenModel):
    """The constraint dependency graph substrate (ADR §18 line 404-412 — reachability closure).

    A thin frozen container the runtime assembles from the policy's declared dependency graph
    (§8 line 240 dependency closure). :func:`~tos.venue.predicates.material_change_closure`
    decides the reachability closure over :meth:`as_graph` / :meth:`as_unproven`. The definite
    edges are proven adjacencies; the unproven edges are isolation-not-yet-proven adjacencies,
    **expanded** (widening) exactly like the definite ones (§18 line 412 — failure to prove
    complete propagation expands containment).
    """

    edges: tuple[DependencyEdge, ...] = ()
    unproven_edges: tuple[DependencyEdge, ...] = ()

    def as_graph(self) -> dict[str, frozenset[str]]:
        """The definite dependency adjacency ``{node: {dependents}}`` (skips null nodes)."""
        return {e.node: e.dependents for e in self.edges if e.node is not None}

    def as_unproven(self) -> dict[str, frozenset[str]]:
        """The unproven (isolation-not-proven) adjacency, expanded like the definite graph."""
        return {e.node: e.dependents for e in self.unproven_edges if e.node is not None}


class MaterialConstraintChange(FrozenModel):
    """One material constraint change trigger (ADR §18 line 404-410 / §5.8 line 139).

    A change (unscheduled closure / halt / suspension, listing / contract / tick / lot / band
    change, account / borrow / margin / settlement change, broker-capability degradation,
    source correction / discontinuity — §18 line 404-410) that fences affected unconsumed
    decisions. §5.8 line 139 verbatim: "Unknown materiality is material" — so :meth:`is_material`
    treats a ``None`` (unknown) materiality as material (fail-closed); only a positive ``False``
    is non-material. The policy — not a proposer or consumer — determines materiality (§14 line
    345); this record carries the classification, it does not re-classify.
    """

    change_id: str | None = None
    constraint_class: ConstraintClass | None = None
    #: §5.8 line 139 — ``None`` (unknown) is treated as material; only positive ``False`` is not.
    material: bool | None = None

    def is_material(self) -> bool:
        """Whether this change is material (unknown materiality is material, §5.8 line 139)."""
        return self.material is not False


# ===========================================================================
# Core issued-identity artifacts (IndependentIdArtifact — id ⊥ digest)
# ===========================================================================


class VenueConstraintPolicy(IndependentIdArtifact):
    """An immutable, separately-governed Venue Constraint Policy (ADR-002-019 §5.1 line 111; §8).

    §5.1 line 111: "immutable, authenticated, separately governed"; §14 line 335 binds "policy
    identity, version, generation, digest, approval state". An
    :class:`~tos.venue._base.IndependentIdArtifact` (``id != f(digest)``): the ``policy_id`` is
    separately issued (capsule ``VenueConstraintPolicyRef`` = {``policy_id``,
    ``policy_generation``, ``canonical_digest``} ``capsule.py:130-135``), so a same-id /
    different-bytes policy forgery / rollback is a detectable ``classify_record_pair``
    ``CRITICAL_CONFLICT`` (§18). **Policy activation is spg-owned** (``BundleMemberKind.
    VENUE_CONSTRAINT_POLICY`` ``spg/vocabulary.py:205`` — the design's "GovernedProfileClass"
    label is a phantom; grep-verified real enum, code-review MINOR-1; ADR-002-014, §3.5) —
    venue is the content author, not the activation authority; it consumes the activation
    verdict as an injected scalar (§8 line 243). Declares the admitting-phase rules consumed
    by ``session_phase_admits``; ``required_constraint_classes`` is **covered digest content
    only** — no Phase-1 predicate consumes it (completeness composition against it is
    runtime/Phase-B scope; code-review MINOR-2 — an empty set therefore grants nothing and
    establishes nothing).
    """

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("policy_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "scope",
            "admitting_phase_rules",
            "required_constraint_classes",
            "shape_constraints",
            "dependency_closure",
        }
    )

    policy_id: str | None = None
    policy_generation: int | None = None
    #: The policy scope identity (environment/broker/account/venue/segment/product/instrument).
    scope: str | None = None
    #: The per-action admitting session-phase rules (§10 line 273; §5.5 SessionPhase tokens).
    admitting_phase_rules: tuple[ActionPhaseAdmission, ...] = ()
    #: The constraint classes an admissible decision MUST positively cover (empty => fail-closed).
    required_constraint_classes: frozenset[ConstraintClass] = frozenset()
    #: The injected order-shape constraints (tick/lot/band — all values injected, §8.0).
    shape_constraints: VenueShapeConstraints = VenueShapeConstraints()
    #: The declared constraint dependency graph (§18 material-change closure substrate).
    dependency_closure: ConstraintDependencyClosure = ConstraintDependencyClosure()

    def admitting_phases_for(self, action: ActionClass) -> frozenset[str] | None:
        """The admitting session-phase set for ``action`` (``None`` if unenumerated).

        Returns the policy-declared admitting phase tokens for the exact action, or ``None``
        when the action is not declared — an unenumerated action fails closed at the consuming
        predicate (§8 line 245 "unsupported enum ... never a permissive default"). An empty
        (but declared) set admits nothing (a vacuous admit is not an admit, §4.7).

        Args:
            action: The exact order action class.

        Returns:
            The admitting phase-token set, or ``None`` if the action is not declared.
        """
        for rule in self.admitting_phase_rules:
            if rule.action is action:
                return rule.admitting_phases
        return None


class VenueConstraintSnapshot(IndependentIdArtifact):
    """An immutable, scope-bounded Venue Constraint Snapshot (ADR-002-019 §5.2 line 115; §9-13).

    §5.2 line 115: "immutable, time- and scope-bounded evaluation ... grants no authority". An
    :class:`~tos.venue._base.IndependentIdArtifact` (``id != f(digest)``): the ``snapshot_id``
    is separately issued (capsule ``VenueConstraintSnapshotRef`` = {``snapshot_id``,
    ``constraint_generation``, ``canonical_digest``} ``capsule.py:138-143``), so a snapshot
    substitution (same id, different bytes) is a detectable ``CRITICAL_CONFLICT`` (VTG-EV-006).
    Carries the current Constraint Generation, the per-action tradability map, the bound policy
    coordinates, and the CII / source-continuity provenance (all injected — capsule / time are
    §3.5). §5.2 "binds Critical Input provenance and uncertainty but **grants no authority**".
    """

    _ID_FIELD: ClassVar[str] = "snapshot_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("constraint_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "constraint_generation",
            "policy_id",
            "policy_generation",
            "policy_digest",
            "observed_session_phase",
            "action_tradability",
            "critical_input_snapshot_digest",
            "source_continuity_id",
            "max_age",
        }
    )

    snapshot_id: str | None = None
    constraint_generation: int | None = None
    #: The bound policy coordinates (injected — venue is content author, spg activates, §3.5).
    policy_id: str | None = None
    policy_generation: int | None = None
    policy_digest: str | None = None
    #: The authoritatively-observed session-phase token (injected opaque str, §2.2(3)).
    observed_session_phase: str | None = None
    #: The per-action tradability map (§11 — a global bool is insufficient).
    action_tradability: tuple[ActionTradability, ...] = ()
    #: CII provenance binding (capsule-owned; venue binds the digest, §3.5).
    critical_input_snapshot_digest: str | None = None
    source_continuity_id: str | None = None
    #: Opaque injected max-age coordinate (clock-free, §8; null in Phase 1).
    max_age: str | None = None

    def tradability_for(self, action: ActionClass) -> TradabilityState | None:
        """The per-action tradability verdict for ``action`` (``None`` if not declared).

        Args:
            action: The exact order action class.

        Returns:
            The action's :class:`~tos.venue.vocabulary.TradabilityState`, or ``None``.
        """
        for entry in self.action_tradability:
            if entry.action is action:
                return entry.state
        return None


class OrderAdmissibilityDecision(IndependentIdArtifact):
    """An immutable Order Admissibility Decision for one exact order shape (ADR §5.4 line 121; §14).

    §5.4 line 121: "immutable canonical result for one exact broker-request shape". An
    :class:`~tos.venue._base.IndependentIdArtifact` (``id != f(digest)``): the ``decision_id`` is
    separately issued (capsule ``OrderAdmissibilityDecisionRef`` = {``decision_id``,
    ``canonical_digest``} ``capsule.py:146-150``), so a decision substitution (same id,
    different bytes) is a detectable ``CRITICAL_CONFLICT`` (VTG-EV-006). Binds — by **digest
    scalar** (sibling edge 0, §3.4) — the exact candidate ``CanonicalBrokerCommand`` id/digest
    (ioc, consumed), the snapshot / policy / capsule digests (consumed), and the brokercap
    profile version/digest **ceiling** (consumed, never promoted — VTG-INV-006). Its ``result``
    is the venue-owned :class:`~tos.venue.vocabulary.OrderAdmissibilityResult`; its
    ``authority_effect`` is all-false (§14 line 341 — a decision is a safety fact, not
    permission, §1 line 21-23). §14 line 342-343: the canonical digest covers all fields that
    can change the decision and cannot be patched / partially refreshed / unioned / widened /
    silently recomputed.
    """

    _ID_FIELD: ClassVar[str] = "decision_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("decision_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "decision_generation",
            "constraint_generation",
            "policy_id",
            "policy_generation",
            "policy_digest",
            "snapshot_id",
            "snapshot_digest",
            "decision_context_capsule_id",
            "decision_context_capsule_digest",
            "candidate_command_id",
            "candidate_command_digest",
            "broker_capability_profile_version",
            "broker_capability_profile_digest",
            "bound_instrument_route",
            "action_class",
            "observed_session_phase",
            "result",
            "failed_predicates",
            "unknown_predicates",
            "authority_effect",
        }
    )

    decision_id: str | None = None
    #: Structural decision generation (id⊥digest completeness coordinate).
    decision_generation: int | None = None
    #: The current Constraint Generation this decision is fenced by (ordering carries, §0.4e).
    constraint_generation: int | None = None
    #: Bound policy coordinates (injected digest scalars; sibling edge 0).
    policy_id: str | None = None
    policy_generation: int | None = None
    policy_digest: str | None = None
    #: Bound snapshot coordinates (injected digest scalars).
    snapshot_id: str | None = None
    snapshot_digest: str | None = None
    #: Bound Decision Context Capsule (capsule-owned; venue binds the digest, §3.5).
    decision_context_capsule_id: str | None = None
    decision_context_capsule_digest: str | None = None
    #: Bound exact candidate CanonicalBrokerCommand (ioc-owned; venue evaluates it, §3.5).
    candidate_command_id: str | None = None
    candidate_command_digest: str | None = None
    #: Brokercap profile CEILING (brokercap-owned; consumed reduce-only, never promoted, §3.5).
    broker_capability_profile_version: str | None = None
    broker_capability_profile_digest: str | None = None
    #: The exact instrument / contract / account / route binding (§11; exact-match consumer).
    bound_instrument_route: InstrumentRouteFields = InstrumentRouteFields()
    #: The exact action class (closed taxonomy, §2.2(2)).
    action_class: ActionClass | None = None
    #: The authoritatively-observed session-phase token (injected opaque str).
    observed_session_phase: str | None = None
    #: The venue-owned admissibility result (§5.4 — truthy-sealed).
    result: OrderAdmissibilityResult | None = None
    #: The predicates that failed / were unknown (§14 line 338; diagnostics).
    failed_predicates: tuple[str, ...] = ()
    unknown_predicates: tuple[str, ...] = ()
    #: §14 line 340-341 — the decision creates no authority (all-false, VTG-INV-011).
    authority_effect: VenueGateAuthorityEffect = VenueGateAuthorityEffect()
