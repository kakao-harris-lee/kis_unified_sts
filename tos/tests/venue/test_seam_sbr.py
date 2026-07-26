"""MANDATED test-only seam cross-check: venue <-> sbr shared closure property (design #19 §0.4d / §7).

The sbr ``recovery_scope_closure`` + ``readiness_invalidated_by_change`` (``sbr/predicates.py``)
and venue's ``material_change_closure`` are **structurally isomorphic** pure graph reachability.
venue re-authors the closure **locally** (import of ``tos.sbr`` is forbidden — sibling edge 0,
§0.4d); the DRY is preserved not by code sharing but by this **shared closure property contract**
that regresses all implementations on the same closure axioms. This file imports the real sbr
closures as a **test** to prove the isomorphism — and the import-closure test separately proves
``tos.sbr`` is **absent** from the venue package closure (re-authored, not imported).

Axioms regressed: trigger ∈ closure; transitive completeness (no dependent escapes); an
uncertain / unproven edge is EXPANDED (widening, never narrowing); ∅ graph => {trigger};
deterministic.

A test-only cross-import is **not** a runtime package edge (§3.4(d)/§7.1).

Regime tag: predicate / model substrate only; VTG-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from hypothesis import given
from tos.sbr import readiness_invalidated_by_change, recovery_scope_closure
from tos.venue import material_change_closure

from ._venue_strategies import graph_and_trigger


def test_three_implementations_agree_on_a_fixed_graph() -> None:
    """(shared-closure contract) venue == sbr scope == sbr invalidation on a fixed graph."""
    graph = {
        "t": frozenset({"a", "b"}),
        "a": frozenset({"c"}),
        "b": frozenset({"c", "d"}),
    }
    expected = frozenset({"t", "a", "b", "c", "d"})
    assert material_change_closure(graph, frozenset({"t"})) == expected
    assert recovery_scope_closure(graph, "t") == expected
    assert readiness_invalidated_by_change(graph, frozenset({"t"})) == expected


def test_three_implementations_agree_on_empty_graph() -> None:
    """(∅ axiom) All yield the minimal closure {trigger} on an empty graph."""
    assert material_change_closure({}, frozenset({"t"})) == frozenset({"t"})
    assert recovery_scope_closure({}, "t") == frozenset({"t"})
    assert readiness_invalidated_by_change({}, frozenset({"t"})) == frozenset({"t"})


def test_three_implementations_expand_an_uncertain_edge() -> None:
    """(uncertain-widen axiom) All expand an uncertain edge identically."""
    graph = {"t": frozenset({"a"})}
    uncertain = {"a": frozenset({"x"})}
    assert "x" in material_change_closure(graph, frozenset({"t"}), unproven=uncertain)
    assert "x" in recovery_scope_closure(graph, "t", unproven=uncertain)
    assert "x" in readiness_invalidated_by_change(
        graph, frozenset({"t"}), unproven=uncertain
    )


@given(graph_and_trigger())
def test_property_all_three_closures_agree(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(shared-closure property) On any graph, venue == sbr scope == sbr single-trigger invalidation."""
    graph, trigger = graph_and_trigger_value
    venue_result = material_change_closure(graph, frozenset({trigger}))
    sbr_scope = recovery_scope_closure(graph, trigger)
    sbr_invalidation = readiness_invalidated_by_change(graph, frozenset({trigger}))
    assert venue_result == sbr_scope
    assert venue_result == sbr_invalidation


@given(graph_and_trigger())
def test_property_all_three_expand_uncertain_identically(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(shared-closure property) An uncertain edge widens all three closures identically."""
    graph, trigger = graph_and_trigger_value
    uncertain = {trigger: frozenset({"uncertain-node"})}
    venue_result = material_change_closure(
        graph, frozenset({trigger}), unproven=uncertain
    )
    sbr_scope = recovery_scope_closure(graph, trigger, unproven=uncertain)
    sbr_invalidation = readiness_invalidated_by_change(
        graph, frozenset({trigger}), unproven=uncertain
    )
    assert venue_result == sbr_scope == sbr_invalidation
    assert "uncertain-node" in venue_result
