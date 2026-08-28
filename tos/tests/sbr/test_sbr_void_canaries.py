"""∅-void both-ways canaries across the sbr predicates (design #17 §4.7).

Every empty-input guard is checked in BOTH directions: the forbidden (vacuous-permissive)
direction fires, and the legitimate positive direction is NOT blocked. A vacuous-READY is a
safety violation; a vacuous-NOT_READY is an availability violation — both are defects (#12
both-ways lesson).

Regime tag: predicate / model substrate only; SBR-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.sbr import (
    IsolationFacts,
    ObligationResult,
    RecoveryBarrierPolicy,
    obligation_graph_closed,
    readiness_invalidated_by_change,
    recovery_inventory_complete,
    recovery_scope_closure,
    restore_worst_credible_union,
    restricted_isolation_proven,
    timeout_is_restrictive,
    unknown_stays_conservative,
)

from ._sbr_strategies import (
    clean_inventory_cut,
    clean_isolation_facts,
    clean_obligation_set,
    clean_policy,
    clean_scope,
)


def test_empty_obligation_set_blocks_but_full_set_passes() -> None:
    """(∅ both-ways) Empty obligation set => not closed; a complete acyclic set => closed."""
    assert obligation_graph_closed(frozenset()) is False
    assert obligation_graph_closed(clean_obligation_set()) is True


def test_empty_required_inventory_blocks_but_complete_cut_passes() -> None:
    """(∅ both-ways) Empty required set => incomplete; a complete bounded cut => complete."""
    empty_cut = clean_inventory_cut(required=frozenset())
    assert (
        recovery_inventory_complete(
            empty_cut, RecoveryBarrierPolicy(required_dependency_kinds=frozenset())
        )
        is False
    )
    assert recovery_inventory_complete(clean_inventory_cut(), clean_policy()) is True


def test_empty_graph_scope_is_minimal_but_populated_expands() -> None:
    """(∅ both-ways) Empty graph => {trigger}; a populated graph reaches its dependents."""
    assert recovery_scope_closure({}, "t") == frozenset({"t"})
    assert recovery_scope_closure({"t": frozenset({"a"})}, "t") == frozenset({"t", "a"})


def test_empty_change_invalidates_nothing_but_material_change_reaches_all() -> None:
    """(∅ both-ways) Empty change => ∅ invalidation; a material change reaches every dependent."""
    assert (
        readiness_invalidated_by_change({"t": frozenset({"a"})}, frozenset())
        == frozenset()
    )
    assert readiness_invalidated_by_change(
        {"t": frozenset({"a"})}, frozenset({"t"})
    ) == frozenset({"t", "a"})


def test_unknown_plus_capacity_still_blocks_but_all_satisfied_passes() -> None:
    """(∅ both-ways, §14 line 386) A lingering UNKNOWN blocks even with prior evidence; all-SATISFIED passes."""
    # UNKNOWN present (available "capacity" would tempt an offset) => still non-converged.
    assert (
        unknown_stays_conservative(
            {"f": ObligationResult.UNKNOWN}, {"f": ObligationResult.UNKNOWN}
        )
        is False
    )
    assert (
        unknown_stays_conservative(
            {"f": ObligationResult.SATISFIED}, {"f": ObligationResult.UNKNOWN}
        )
        is True
    )


def test_empty_empty_convergence_is_not_vacuously_true() -> None:
    """(∅ both-ways, §4.1; code-review MAJOR) Zero observed fields is NOT positive proof of
    convergence — ``unknown_stays_conservative({}, {})`` fails closed (sibling discipline:
    obligation_graph_closed/recovery_inventory_complete both refuse ∅). Positive side: a
    single terminal non-UNKNOWN field with empty prior converges.
    """
    assert unknown_stays_conservative({}, {}) is False
    assert unknown_stays_conservative({}, {"f": ObligationResult.SATISFIED}) is False
    assert unknown_stays_conservative({"f": ObligationResult.SATISFIED}, {}) is True


def test_empty_isolation_facts_blocks_but_all_proven_passes() -> None:
    """(∅ both-ways) Default (all-None) facts => not proven; all-eight proven => proven."""
    assert restricted_isolation_proven(clean_scope(), IsolationFacts()) is False
    assert restricted_isolation_proven(clean_scope(), clean_isolation_facts()) is True


def test_empty_branches_block_but_full_union_passes() -> None:
    """(∅ both-ways) Empty branch set => reject; all branches + present union => proper."""
    assert restore_worst_credible_union(frozenset(), None, object()) is False
    assert restore_worst_credible_union(frozenset({"b1", "b2"}), None, object()) is True


def test_none_sizes_block_but_intact_set_passes() -> None:
    """(∅ both-ways) A None obligation-set size => fail-closed; an intact set => holds."""
    assert timeout_is_restrictive(True, False, None, 3) is False
    assert timeout_is_restrictive(True, False, 3, 3) is True
