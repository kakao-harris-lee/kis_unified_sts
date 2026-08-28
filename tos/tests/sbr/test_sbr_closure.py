"""Shared reachability closure — §5.3 scope + §5.6 invalidation both-ways + property (design #17 §5.3/§5.6/MINOR-5).

The single shared kernel :func:`~tos.sbr.predicates._reachability_closure` backs both
``recovery_scope_closure`` (§8 scope expansion) and ``readiness_invalidated_by_change`` (§18
invalidation). The §7 shared-closure property contract regresses BOTH sbr implementations on
the same closure axioms (the iap ``invalidation_closure`` third leg lives in
``test_seam_iap.py`` — a real iap import). Axioms: trigger ∈ closure; an uncertain / unproven
edge is EXPANDED (never narrows); a proven-disconnected node is excluded; a cycle terminates;
∅ graph => {trigger}.

Regime tag: predicate / model substrate only; SBR-EV-004/007/009 NOT_IMPLEMENTED (`/3`
residue); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from hypothesis import given
from tos.sbr import readiness_invalidated_by_change, recovery_scope_closure

from ._sbr_strategies import graph_and_trigger

# ---------------------------------------------------------------------------
# §5.3 recovery_scope_closure (§8 scope expansion)
# ---------------------------------------------------------------------------


def test_scope_trigger_is_in_its_own_closure() -> None:
    """(∅ / §4.7) An empty graph yields the minimal closure {trigger} — not a vacuous empty set."""
    assert recovery_scope_closure({}, "t") == frozenset({"t"})


def test_scope_transitive_reachability_no_escape() -> None:
    """(§8 line 240) The closure includes every transitively-reachable dependency (no escape)."""
    graph = {
        "t": frozenset({"a", "b"}),
        "a": frozenset({"c"}),
        "b": frozenset({"c", "d"}),
    }
    assert recovery_scope_closure(graph, "t") == frozenset({"t", "a", "b", "c", "d"})


def test_scope_unproven_edge_expands() -> None:
    """(§8 line 240) An isolation-not-proven (unproven) edge widens the scope (fail-closed)."""
    closure = recovery_scope_closure(
        {"t": frozenset({"a"})},
        "t",
        unproven={"a": frozenset({"broader-account"})},
    )
    assert "broader-account" in closure


def test_scope_proven_disconnected_node_excluded() -> None:
    """(§8 line 242, availability) A proven-disconnected node is NOT spuriously in scope."""
    graph = {"t": frozenset({"a"}), "island": frozenset({"island-dep"})}
    closure = recovery_scope_closure(graph, "t")
    assert closure == frozenset({"t", "a"})
    assert "island" not in closure


def test_scope_cycle_terminates() -> None:
    """(pure reachability) A dependency cycle terminates and includes the cycle."""
    graph = {"t": frozenset({"a"}), "a": frozenset({"t"})}
    assert recovery_scope_closure(graph, "t") == frozenset({"t", "a"})


# ---------------------------------------------------------------------------
# §5.6 readiness_invalidated_by_change (§18 invalidation)
# ---------------------------------------------------------------------------


def test_invalidation_empty_change_invalidates_nothing() -> None:
    """(§18 canary b, availability) No material change => nothing invalidated (readiness stays valid)."""
    assert (
        readiness_invalidated_by_change({"t": frozenset({"a"})}, frozenset())
        == frozenset()
    )


def test_invalidation_single_trigger_self_included() -> None:
    """(§18) A single material change is always in its own invalidation closure."""
    assert readiness_invalidated_by_change({}, frozenset({"t"})) == frozenset({"t"})


def test_invalidation_reaches_every_affected_readiness_no_escape() -> None:
    """(§18 line 453-461) Every affected readiness is captured (no escape — fail-open guard)."""
    graph = {"cut": frozenset({"r1"}), "r1": frozenset({"r2"})}
    assert readiness_invalidated_by_change(graph, frozenset({"cut"})) == frozenset(
        {"cut", "r1", "r2"}
    )


def test_invalidation_unproven_edge_expands() -> None:
    """(§18 / §0.4d) An uncertain edge widens the invalidation set (an affected readiness cannot escape)."""
    closure = readiness_invalidated_by_change(
        {"cut": frozenset({"r1"})},
        frozenset({"cut"}),
        unproven={"r1": frozenset({"maybe-affected"})},
    )
    assert "maybe-affected" in closure


def test_invalidation_unrelated_readiness_stays_valid() -> None:
    """(§18 canary b) An unrelated readiness is not spuriously invalidated (availability side)."""
    graph = {"cut": frozenset({"r1"}), "other": frozenset({"r-other"})}
    closure = readiness_invalidated_by_change(graph, frozenset({"cut"}))
    assert "other" not in closure
    assert "r-other" not in closure


# ---------------------------------------------------------------------------
# Shared closure property contract — §5.3 == §5.6(single trigger) on the same axioms
# ---------------------------------------------------------------------------


@given(graph_and_trigger())
def test_shared_kernel_scope_and_invalidation_agree(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(shared-closure property) §5.3 scope == §5.6 single-trigger invalidation (one kernel)."""
    graph, trigger = graph_and_trigger_value
    scope = recovery_scope_closure(graph, trigger)
    invalidation = readiness_invalidated_by_change(graph, frozenset({trigger}))
    assert scope == invalidation


@given(graph_and_trigger())
def test_shared_kernel_completeness_no_dependent_escapes(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(property, §4.4) No direct dependent of a closure member escapes (completeness)."""
    graph, trigger = graph_and_trigger_value
    for closure in (
        recovery_scope_closure(graph, trigger),
        readiness_invalidated_by_change(graph, frozenset({trigger})),
    ):
        assert trigger in closure
        for member in closure:
            for dependent in graph.get(member, frozenset()):
                assert dependent in closure, "a reachable dependent escaped (fail-open)"


@given(graph_and_trigger())
def test_shared_kernel_uncertain_only_widens(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(property, §4.4) Adding an uncertain edge can only widen (⊇) — never narrow."""
    graph, trigger = graph_and_trigger_value
    base = recovery_scope_closure(graph, trigger)
    widened = recovery_scope_closure(
        graph, trigger, unproven={trigger: frozenset({"uncertain-x"})}
    )
    assert base <= widened
    assert "uncertain-x" in widened


@given(graph_and_trigger())
def test_shared_kernel_is_deterministic(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(pure function) The closure is deterministic — two computations agree exactly."""
    graph, trigger = graph_and_trigger_value
    assert recovery_scope_closure(graph, trigger) == recovery_scope_closure(
        graph, trigger
    )
