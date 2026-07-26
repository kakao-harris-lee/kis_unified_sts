"""∅-void both-ways canaries across the venue predicates (design #19 §4.7).

Every empty-input guard is checked in BOTH directions: the forbidden (vacuous-permissive)
direction fires, and the legitimate positive direction is NOT blocked. A vacuous-ADMISSIBLE is a
safety violation; a vacuous-INADMISSIBLE is an availability violation — both are defects (#12
both-ways lesson).

Regime tag: predicate / model substrate only; VTG-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.venue import (
    ActionClass,
    OrderAdmissibilityResult,
    VenueGateAuthorityEffect,
    account_constraint_conservative,
    common_mode_reduces_scope,
    decision_binding_exact,
    exact_instrument_route_bound,
    gate_authority_separated,
    material_change_closure,
    no_decision_union,
    order_shape_admissible,
    session_phase_admits,
    tradability_conflict_unknown,
    unknown_continuity_invalidates,
)

from ._venue_strategies import (
    clean_account_facts,
    clean_binding_chain,
    clean_continuity,
    clean_decision,
    clean_instrument_route,
    clean_policy,
    clean_shape,
    clean_shape_constraints,
    clean_snapshot,
)


def test_empty_admitting_set_blocks_but_declared_set_admits() -> None:
    """(∅ both-ways) Empty admitting set => INADMISSIBLE; a declared matching phase => ADMISSIBLE."""
    empty = clean_policy(action=ActionClass.NEW_LONG, admitting_phases=frozenset())
    full = clean_policy(
        action=ActionClass.NEW_LONG, admitting_phases=frozenset({"continuous_trading"})
    )
    snapshot = clean_snapshot()
    assert (
        session_phase_admits(
            "continuous_trading", ActionClass.NEW_LONG, snapshot, empty
        )
        is OrderAdmissibilityResult.INADMISSIBLE
    )
    assert (
        session_phase_admits("continuous_trading", ActionClass.NEW_LONG, snapshot, full)
        is OrderAdmissibilityResult.ADMISSIBLE
    )


def test_empty_allowed_shape_set_blocks_but_full_constraints_pass() -> None:
    """(∅ both-ways) Empty allowed order-type set => UNKNOWN; full constraints => ADMISSIBLE."""
    empty = clean_shape_constraints().model_copy(
        update={"allowed_order_types": frozenset()}
    )
    assert (
        order_shape_admissible(clean_shape(), empty) is OrderAdmissibilityResult.UNKNOWN
    )
    assert (
        order_shape_admissible(clean_shape(), clean_shape_constraints())
        is OrderAdmissibilityResult.ADMISSIBLE
    )


def test_empty_stage_bindings_block_but_full_chain_passes() -> None:
    """(∅ both-ways) Empty stage bindings => not bound; a full chain => bound."""
    empty = clean_binding_chain().model_copy(update={"stage_bindings": ()})
    assert decision_binding_exact(empty) is False
    assert decision_binding_exact(clean_binding_chain()) is True


def test_empty_decision_set_blocks_but_single_passes() -> None:
    """(∅ both-ways) Empty decision set => no union fails; exactly one => passes."""
    assert no_decision_union(frozenset()) is False
    assert no_decision_union(frozenset({"one"})) is True


def test_empty_change_invalidates_nothing_but_material_change_reaches_all() -> None:
    """(∅ both-ways) Empty change => ∅ invalidation; a material change reaches every dependent."""
    assert material_change_closure({"t": frozenset({"a"})}, frozenset()) == frozenset()
    assert material_change_closure(
        {"t": frozenset({"a"})}, frozenset({"t"})
    ) == frozenset({"t", "a"})


def test_empty_graph_closure_is_minimal_but_populated_expands() -> None:
    """(∅ both-ways) Empty graph => {trigger}; a populated graph reaches its dependents."""
    assert material_change_closure({}, frozenset({"t"})) == frozenset({"t"})
    assert material_change_closure(
        {"t": frozenset({"a"})}, frozenset({"t"})
    ) == frozenset({"t", "a"})


def test_empty_observations_unknown_but_resolution_decides() -> None:
    """(∅ both-ways) Empty observations => UNKNOWN; a policy resolution decides."""
    from tos.venue import PolicyResolution, SourceObservation

    assert (
        tradability_conflict_unknown(frozenset(), None)
        is OrderAdmissibilityResult.UNKNOWN
    )
    observations = frozenset(
        {
            SourceObservation(source_id="v", state="OPEN"),
            SourceObservation(source_id="b", state="HALTED"),
        }
    )
    resolution = PolicyResolution(resolved_result=OrderAdmissibilityResult.INADMISSIBLE)
    assert (
        tradability_conflict_unknown(observations, resolution)
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_none_inputs_block_but_clean_inputs_pass() -> None:
    """(∅ both-ways) None facts / route / continuity / effect fail closed; clean ones pass."""
    # account facts
    assert account_constraint_conservative(None, None) is False
    assert account_constraint_conservative(clean_account_facts(), None) is True
    # instrument route
    route = clean_instrument_route()
    assert exact_instrument_route_bound(None, route) is False
    assert exact_instrument_route_bound(clean_decision(route=route), route) is True
    # continuity
    assert unknown_continuity_invalidates(None) is True
    assert unknown_continuity_invalidates(clean_continuity()) is False
    # authority
    assert gate_authority_separated(None, False) is False
    assert gate_authority_separated(VenueGateAuthorityEffect(), False) is True


def test_shared_dependency_reduces_but_genuine_independence_does_not() -> None:
    """(∅ both-ways) A shared dep reduces scope; genuine disjoint corroboration does not."""
    assert common_mode_reduces_scope(frozenset({"feed"}), True) is True
    assert common_mode_reduces_scope(frozenset(), True) is False
