"""venue admissibility decision predicates (design #19 §5/§6) — pure, fail-closed."""

from __future__ import annotations

from collections.abc import Mapping

from tos.venue.records import (
    AccountMarginFacts,
    BindingChain,
    InstrumentRouteFields,
    OrderAdmissibilityDecision,
    OrderShapeFields,
    PolicyResolution,
    SourceContinuity,
    SourceObservation,
    VenueGateAuthorityEffect,
    VenueShapeConstraints,
)
from tos.venue.vocabulary import (
    ActionClass,
    OrderAdmissibilityResult,
    TradabilityState,
)

__all__ = [
    "exact_instrument_route_bound",
    "order_shape_admissible",
    "decision_binding_exact",
    "no_decision_union",
    "material_change_closure",
    "tradability_conflict_unknown",
    "account_constraint_conservative",
    "egress_currentness_active",
    "stale_decision_rejected_at_egress",
    "exit_not_assumed_admissible",
    "protective_label_no_bypass",
    "common_mode_reduces_scope",
    "unknown_continuity_invalidates",
    "gate_authority_separated",
    "reopen_revives_nothing",
]

_ROUTE_SCALAR_FIELDS: tuple[str, ...] = (
    "canonical_instrument_id",
    "venue_listing",
    "market_segment",
    "contract_month",
    "product_type",
    "currency",
    "multiplier",
    "expiration",
    "settlement_method",
    "account_mapping",
    "environment",
    "broker",
    "route",
)

_EXIT_ACTION_CLASSES: frozenset[ActionClass] = frozenset(
    {
        ActionClass.DECREASE,
        ActionClass.CLOSE,
        ActionClass.REVERSAL,
        ActionClass.CANCEL,
        ActionClass.AMEND,
        ActionClass.REPLACE,
        ActionClass.REDUCE_ONLY,
        ActionClass.PROTECTIVE,
        ActionClass.EMERGENCY,
    }
)


def _reachability_closure(
    graph: Mapping[str, frozenset[str]],
    trigger: str,
    *,
    unproven: Mapping[str, frozenset[str]] | None = None,
) -> frozenset[str]:
    """The transitive-reachability closure from ``trigger`` (design #19 §5.4 / §0.4d)."""
    unproven_adj: Mapping[str, frozenset[str]] = unproven or {}
    closure: set[str] = set()
    stack: list[str] = [trigger]
    while stack:
        node = stack.pop()
        if node in closure:
            continue
        closure.add(node)
        for dependent in graph.get(node, frozenset()):
            if dependent not in closure:
                stack.append(dependent)
        for dependent in unproven_adj.get(node, frozenset()):
            if dependent not in closure:
                stack.append(dependent)
    return frozenset(closure)


def exact_instrument_route_bound(
    decision: OrderAdmissibilityDecision | None,
    candidate_fields: InstrumentRouteFields | None,
) -> bool:
    """Whether the decision binds the candidate's exact instrument / route (§11; VTG-INV-004)."""
    if decision is None or candidate_fields is None:
        return False
    bound = decision.bound_instrument_route
    for name in _ROUTE_SCALAR_FIELDS:
        bound_value = getattr(bound, name)
        candidate_value = getattr(candidate_fields, name)
        if bound_value is None or candidate_value is None:
            return False
        if bound_value != candidate_value:
            return False
    return bound.routing_relevant_aliases == candidate_fields.routing_relevant_aliases


def _resolved_tick(price: int, constraints: VenueShapeConstraints) -> int | None:
    """The on-grid tick for ``price`` (kernel round #4 K-1; §8.0 — every bound is injected)."""
    if constraints.price_band_ticks:
        for row in constraints.price_band_ticks:
            if row.band_min <= price <= row.band_max:
                return row.tick
        return None
    return constraints.tick_size


def order_shape_admissible(
    shape: OrderShapeFields | None,
    constraints: VenueShapeConstraints | None,
) -> OrderAdmissibilityResult:
    """Whether the exact order shape is venue-admissible (§12; VTG-INV-004)."""
    if shape is None or constraints is None:
        return OrderAdmissibilityResult.UNKNOWN
    if shape.silently_rounded is not False:
        return OrderAdmissibilityResult.INADMISSIBLE
    if (
        shape.price is None
        or constraints.price_min is None
        or constraints.price_max is None
        or shape.quantity is None
        or constraints.lot_size is None
        or constraints.min_quantity is None
        or constraints.max_quantity is None
    ):
        return OrderAdmissibilityResult.UNKNOWN
    tick = _resolved_tick(shape.price, constraints)
    if tick is None or tick == 0 or constraints.lot_size == 0:
        return OrderAdmissibilityResult.UNKNOWN
    if (
        not constraints.allowed_order_types
        or not constraints.allowed_tifs
        or not constraints.allowed_sides
        or not constraints.allowed_position_effects
    ):
        return OrderAdmissibilityResult.UNKNOWN
    if shape.price < constraints.price_min or shape.price > constraints.price_max:
        return OrderAdmissibilityResult.INADMISSIBLE
    if constraints.price_band_ticks:
        if shape.price % tick != 0:
            return OrderAdmissibilityResult.INADMISSIBLE
    elif (shape.price - constraints.price_min) % tick != 0:
        return OrderAdmissibilityResult.INADMISSIBLE
    if (
        shape.quantity < constraints.min_quantity
        or shape.quantity > constraints.max_quantity
    ):
        return OrderAdmissibilityResult.INADMISSIBLE
    if shape.quantity % constraints.lot_size != 0:
        return OrderAdmissibilityResult.INADMISSIBLE
    if shape.order_type not in constraints.allowed_order_types:
        return OrderAdmissibilityResult.INADMISSIBLE
    if shape.tif not in constraints.allowed_tifs:
        return OrderAdmissibilityResult.INADMISSIBLE
    if shape.side not in constraints.allowed_sides:
        return OrderAdmissibilityResult.INADMISSIBLE
    if shape.position_effect not in constraints.allowed_position_effects:
        return OrderAdmissibilityResult.INADMISSIBLE
    return OrderAdmissibilityResult.ADMISSIBLE


def decision_binding_exact(chain: BindingChain | None) -> bool:
    """Whether the decision binds every downstream stage with the exact identity (§16; VTG-INV-004)."""
    if chain is None:
        return False
    if chain.decision_id is None or chain.decision_digest is None:
        return False
    if not chain.stage_bindings:
        return False
    for binding in chain.stage_bindings:
        if binding.bound_decision_id != chain.decision_id:
            return False
        if binding.bound_decision_digest != chain.decision_digest:
            return False
    return True


def no_decision_union(decision_digests: frozenset[str]) -> bool:
    """Whether the shape maps to exactly one decision (no union / widen) (§14; VTG-INV-004)."""
    return len(decision_digests) == 1


def material_change_closure(
    dep_graph: Mapping[str, frozenset[str]],
    change_triggers: frozenset[str],
    *,
    unproven: Mapping[str, frozenset[str]] | None = None,
) -> frozenset[str]:
    """The dependencies invalidated by a material constraint change (§18 line 404-412; VTG-INV-008)."""
    invalidated: set[str] = set()
    for trigger in change_triggers:
        invalidated |= _reachability_closure(dep_graph, trigger, unproven=unproven)
    return frozenset(invalidated)


def tradability_conflict_unknown(
    observations: frozenset[SourceObservation],
    resolution: PolicyResolution | None,
) -> OrderAdmissibilityResult:
    """Whether conflicting tradability observations resolve — only via policy (§10; VTG-INV-005)."""
    if not observations:
        return OrderAdmissibilityResult.UNKNOWN
    states = {obs.state for obs in observations}
    if len(states) > 1:
        if resolution is not None and resolution.resolved_result is not None:
            return resolution.resolved_result
        return OrderAdmissibilityResult.UNKNOWN
    if resolution is not None and resolution.resolved_result is not None:
        return resolution.resolved_result
    return OrderAdmissibilityResult.UNKNOWN


def account_constraint_conservative(
    facts: AccountMarginFacts | None,
    prior: AccountMarginFacts | None,
) -> bool:
    """Whether account / margin / borrow headroom is conservatively established (§13; VTG-INV-005)."""
    del prior
    if facts is None:
        return False
    if facts.inferred_from_stale_balance is True:
        return False
    if facts.inferred_from_prior_order is True:
        return False
    if facts.inferred_from_absence_of_error is True:
        return False
    if facts.fresh is not True:
        return False
    return facts.corroborated is True


def egress_currentness_active(
    current_actively_established: bool | None,
    request_generation: int | None,
    current_generation: int | None,
) -> bool:
    """Whether final-egress currentness is actively established (§17; VTG-INV-010)."""
    if current_actively_established is not True:
        return False
    if request_generation is None or current_generation is None:
        return False
    return request_generation == current_generation


def stale_decision_rejected_at_egress(
    current_actively_established: bool | None,
    request_generation: int | None,
    current_generation: int | None,
) -> bool:
    """Whether a new-risk egress request must be rejected on currentness grounds (§17; VTG-INV-010)."""
    return not egress_currentness_active(
        current_actively_established, request_generation, current_generation
    )


def exit_not_assumed_admissible(
    action: ActionClass,
    tradability: TradabilityState,
) -> bool:
    """Whether an exit-class action's admissibility is positively proven, not assumed (§11/§19; VTG-INV-003)."""
    if action not in _EXIT_ACTION_CLASSES:
        return False
    return tradability is TradabilityState.TRADABLE


def protective_label_no_bypass(
    label_is_protective: bool | None,
    exact_admissibility: OrderAdmissibilityResult,
    separate_protective_authority: bool | None,
    intermediate_effects_capacity_covered: bool | None,
) -> bool:
    """Whether a protective action may proceed — never on a label alone (§19; VTG-INV-007)."""
    if label_is_protective is not True:
        return False
    if exact_admissibility not in (
        OrderAdmissibilityResult.ADMISSIBLE,
        OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY,
    ):
        return False
    if separate_protective_authority is not True:
        return False
    return intermediate_effects_capacity_covered is True


def common_mode_reduces_scope(
    shared_dependencies: frozenset[str],
    independent_corroboration: bool | None,
) -> bool:
    """Whether a common-mode dependency reduces the corroboration scope (§15; VTG-INV-005/006)."""
    if shared_dependencies:
        return True
    return independent_corroboration is not True


def unknown_continuity_invalidates(continuity: SourceContinuity | None) -> bool:
    """Whether an unknown / unverifiable source continuity invalidates future decisions (§9; VTG-INV-005)."""
    if continuity is None:
        return True
    if continuity.continuity_id is None:
        return True
    if continuity.verifiable is not True:
        return True
    return (
        continuity.restarted is True
        or continuity.reconnected is True
        or continuity.sequence_reset is True
        or continuity.rolled_back is True
        or continuity.failed_over is True
    )


def gate_authority_separated(
    effect: VenueGateAuthorityEffect | None,
    holds_live_credential: bool | None,
) -> bool:
    """Whether the venue gate grants no authority and holds no live credential (§7; VTG-INV-011)."""
    if effect is None:
        return False
    if holds_live_credential is not False:
        return False
    return not (
        effect.approves
        or effect.mutates_capacity
        or effect.issues_authority
        or effect.classifies_protection
        or effect.transmits
        or effect.clears_halt
        or effect.rearms
    )


def reopen_revives_nothing(
    *,
    venue_reopened: bool | None = None,
    halt_released: bool | None = None,
    reconnected: bool | None = None,
    restarted: bool | None = None,
    failed_over: bool | None = None,
    clock_recovered: bool | None = None,
    constraint_service_recovered: bool | None = None,
    prior_decision: object | None = None,
) -> bool:
    """Whether a venue reopen / recovery revives a prior decision — never (§22; VTG-INV-013)."""
    del venue_reopened, halt_released, reconnected, restarted
    del failed_over, clock_recovered, constraint_service_recovered, prior_decision
    return True
