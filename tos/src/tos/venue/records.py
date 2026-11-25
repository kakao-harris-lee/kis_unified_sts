"""venue models + injected inputs + the three core admissibility artifacts (design #19 §2)."""

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
    "InstrumentRouteFields",
    "OrderShapeFields",
    "PriceBandTick",
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
    "VenueConstraintPolicy",
    "VenueConstraintSnapshot",
    "OrderAdmissibilityDecision",
    "VenueGateAuthorityEffect",
]


class InstrumentRouteFields(FrozenModel):
    """The exact instrument / contract / account / route binding fields (ADR §11 line 281)."""

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
    routing_relevant_aliases: frozenset[str] = frozenset()


class PriceBandTick(FrozenModel):
    """One declared price-band's tick size (kernel round #4 K-1; inclusive bounds)."""

    band_min: int
    band_max: int
    tick: int


class VenueShapeConstraints(FrozenModel):
    """The injected venue order-shape constraints (ADR §12 line 297-311 — all values injected)."""

    price_min: int | None = None
    price_max: int | None = None
    tick_size: int | None = None
    price_band_ticks: tuple[PriceBandTick, ...] | None = None
    lot_size: int | None = None
    min_quantity: int | None = None
    max_quantity: int | None = None
    allowed_order_types: frozenset[str] = frozenset()
    allowed_tifs: frozenset[str] = frozenset()
    allowed_sides: frozenset[str] = frozenset()
    allowed_position_effects: frozenset[str] = frozenset()


class OrderShapeFields(FrozenModel):
    """The exact order shape under evaluation (ADR §12 line 297-311)."""

    price: int | None = None
    quantity: int | None = None
    order_type: str | None = None
    tif: str | None = None
    side: str | None = None
    position_effect: str | None = None
    silently_rounded: bool | None = None


class StageBinding(FrozenModel):
    """One stage's binding of the exact decision identity (ADR §16 line 363-373)."""

    stage: str | None = None
    bound_decision_id: str | None = None
    bound_decision_digest: str | None = None


class BindingChain(FrozenModel):
    """The exact decision binding chain across downstream stages (ADR §16 line 363-373)."""

    decision_id: str | None = None
    decision_digest: str | None = None
    stage_bindings: tuple[StageBinding, ...] = ()


class SourceObservation(FrozenModel):
    """One venue / broker / quote / calendar source observation (ADR §10 line 275)."""

    source_id: str | None = None
    state: str | None = None
    generation: int | None = None


class PolicyResolution(FrozenModel):
    """A policy-defined conflict resolution (ADR §10 line 275)."""

    resolution_id: str | None = None
    resolved_result: OrderAdmissibilityResult | None = None


class AccountMarginFacts(FrozenModel):
    """Account / margin / borrow / settlement eligibility facts (ADR §13 line 315-325)."""

    fresh: bool | None = None
    corroborated: bool | None = None
    inferred_from_stale_balance: bool | None = None
    inferred_from_prior_order: bool | None = None
    inferred_from_absence_of_error: bool | None = None


class SourceContinuity(FrozenModel):
    """Source continuity facts (ADR §9 line 249-263 / §15)."""

    continuity_id: str | None = None
    verifiable: bool | None = None
    restarted: bool | None = None
    reconnected: bool | None = None
    sequence_reset: bool | None = None
    rolled_back: bool | None = None
    failed_over: bool | None = None


class ActionPhaseAdmission(FrozenModel):
    """One action's policy-declared admitting session-phase set (ADR §10 line 273 / §5.5)."""

    action: ActionClass | None = None
    admitting_phases: frozenset[str] = frozenset()


class ActionTradability(FrozenModel):
    """One action's per-action tradability verdict (ADR §11 line 283-291)."""

    action: ActionClass | None = None
    state: TradabilityState | None = None


class DependencyEdge(FrozenModel):
    """One node's dependent-adjacency edge for the material-change closure (ADR §18 line 404-412)."""

    node: str | None = None
    dependents: frozenset[str] = frozenset()


class ConstraintDependencyClosure(FrozenModel):
    """The constraint dependency graph substrate (ADR §18 line 404-412 — reachability closure)."""

    edges: tuple[DependencyEdge, ...] = ()
    unproven_edges: tuple[DependencyEdge, ...] = ()

    def as_graph(self) -> dict[str, frozenset[str]]:
        """The definite dependency adjacency ``{node: {dependents}}`` (skips null nodes)."""
        return {e.node: e.dependents for e in self.edges if e.node is not None}

    def as_unproven(self) -> dict[str, frozenset[str]]:
        """The unproven (isolation-not-proven) adjacency, expanded like the definite graph."""
        return {e.node: e.dependents for e in self.unproven_edges if e.node is not None}


class MaterialConstraintChange(FrozenModel):
    """One material constraint change trigger (ADR §18 line 404-410 / §5.8 line 139)."""

    change_id: str | None = None
    constraint_class: ConstraintClass | None = None
    material: bool | None = None

    def is_material(self) -> bool:
        """Whether this change is material (unknown materiality is material, §5.8 line 139)."""
        return self.material is not False


class VenueConstraintPolicy(IndependentIdArtifact):
    """An immutable, separately-governed Venue Constraint Policy (ADR-002-019 §5.1 line 111; §8)."""

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
    scope: str | None = None
    admitting_phase_rules: tuple[ActionPhaseAdmission, ...] = ()
    required_constraint_classes: frozenset[ConstraintClass] = frozenset()
    shape_constraints: VenueShapeConstraints = VenueShapeConstraints()
    dependency_closure: ConstraintDependencyClosure = ConstraintDependencyClosure()

    def admitting_phases_for(self, action: ActionClass) -> frozenset[str] | None:
        """The admitting session-phase set for ``action`` (``None`` if unenumerated)."""
        for rule in self.admitting_phase_rules:
            if rule.action is action:
                return rule.admitting_phases
        return None


class VenueConstraintSnapshot(IndependentIdArtifact):
    """An immutable, scope-bounded Venue Constraint Snapshot (ADR-002-019 §5.2 line 115; §9-13)."""

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
    policy_id: str | None = None
    policy_generation: int | None = None
    policy_digest: str | None = None
    observed_session_phase: str | None = None
    action_tradability: tuple[ActionTradability, ...] = ()
    critical_input_snapshot_digest: str | None = None
    source_continuity_id: str | None = None
    max_age: str | None = None

    def tradability_for(self, action: ActionClass) -> TradabilityState | None:
        """The per-action tradability verdict for ``action`` (``None`` if not declared)."""
        for entry in self.action_tradability:
            if entry.action is action:
                return entry.state
        return None


class OrderAdmissibilityDecision(IndependentIdArtifact):
    """An immutable Order Admissibility Decision for one exact order shape (ADR §5.4 line 121; §14)."""

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
    decision_generation: int | None = None
    constraint_generation: int | None = None
    policy_id: str | None = None
    policy_generation: int | None = None
    policy_digest: str | None = None
    snapshot_id: str | None = None
    snapshot_digest: str | None = None
    decision_context_capsule_id: str | None = None
    decision_context_capsule_digest: str | None = None
    candidate_command_id: str | None = None
    candidate_command_digest: str | None = None
    broker_capability_profile_version: str | None = None
    broker_capability_profile_digest: str | None = None
    bound_instrument_route: InstrumentRouteFields = InstrumentRouteFields()
    action_class: ActionClass | None = None
    observed_session_phase: str | None = None
    result: OrderAdmissibilityResult | None = None
    failed_predicates: tuple[str, ...] = ()
    unknown_predicates: tuple[str, ...] = ()
    authority_effect: VenueGateAuthorityEffect = VenueGateAuthorityEffect()
