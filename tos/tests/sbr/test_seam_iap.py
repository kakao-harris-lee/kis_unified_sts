"""MANDATED test-only seam cross-check: sbr <-> iap shared closure property (design #17 §0.4d / §7).

The iap ``invalidation_closure`` (``iap/predicates.py:347``) and SBR's §5.3
``recovery_scope_closure`` + §5.6 ``readiness_invalidated_by_change`` are **structurally
isomorphic** pure graph reachability. SBR re-authors the closure **locally** (import of
``tos.iap`` is forbidden — sibling edge 0, §0.4d); the DRY is preserved not by code sharing but
by this **shared closure property contract** that regresses ALL THREE implementations on the
same closure axioms. This file imports the real iap ``invalidation_closure`` as a **test** to
prove the isomorphism holds — and the import-closure test separately proves ``tos.iap`` is
**absent** from the sbr package closure (re-authored, not imported).

Axioms regressed across the three implementations: trigger ∈ closure; transitive completeness
(no dependent escapes); an uncertain / unproven edge is EXPANDED (widening, never narrowing);
∅ graph => {trigger}; deterministic.

A test-only cross-import is **not** a runtime package edge (design #17 §3.4(d)/§7.1).
"""

from __future__ import annotations

from hypothesis import given
from tos.iap import invalidation_closure
from tos.sbr import readiness_invalidated_by_change, recovery_scope_closure

from ._sbr_strategies import graph_and_trigger


def test_three_implementations_agree_on_a_fixed_graph() -> None:
    """(shared-closure contract) iap == sbr scope == sbr invalidation on a fixed graph."""
    graph = {
        "t": frozenset({"a", "b"}),
        "a": frozenset({"c"}),
        "b": frozenset({"c", "d"}),
    }
    expected = frozenset({"t", "a", "b", "c", "d"})
    assert invalidation_closure(graph, "t") == expected
    assert recovery_scope_closure(graph, "t") == expected
    assert readiness_invalidated_by_change(graph, frozenset({"t"})) == expected


def test_three_implementations_agree_on_empty_graph() -> None:
    """(∅ axiom) All three yield the minimal closure {trigger} on an empty graph."""
    assert invalidation_closure({}, "t") == frozenset({"t"})
    assert recovery_scope_closure({}, "t") == frozenset({"t"})
    assert readiness_invalidated_by_change({}, frozenset({"t"})) == frozenset({"t"})


def test_three_implementations_expand_an_uncertain_edge() -> None:
    """(uncertain-widen axiom) All three expand an uncertain edge identically."""
    graph = {"t": frozenset({"a"})}
    uncertain = {"a": frozenset({"x"})}
    assert "x" in invalidation_closure(graph, "t", uncertain=uncertain)
    assert "x" in recovery_scope_closure(graph, "t", unproven=uncertain)
    assert "x" in readiness_invalidated_by_change(
        graph, frozenset({"t"}), unproven=uncertain
    )


@given(graph_and_trigger())
def test_property_all_three_closures_agree(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(shared-closure property) On any graph, iap == sbr scope == sbr single-trigger invalidation."""
    graph, trigger = graph_and_trigger_value
    iap_result = invalidation_closure(graph, trigger)
    sbr_scope = recovery_scope_closure(graph, trigger)
    sbr_invalidation = readiness_invalidated_by_change(graph, frozenset({trigger}))
    assert iap_result == sbr_scope
    assert iap_result == sbr_invalidation


@given(graph_and_trigger())
def test_property_all_three_expand_uncertain_edges_identically(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(shared-closure property) An uncertain edge widens all three closures identically."""
    graph, trigger = graph_and_trigger_value
    uncertain = {trigger: frozenset({"uncertain-node"})}
    iap_result = invalidation_closure(graph, trigger, uncertain=uncertain)
    sbr_scope = recovery_scope_closure(graph, trigger, unproven=uncertain)
    sbr_invalidation = readiness_invalidated_by_change(
        graph, frozenset({trigger}), unproven=uncertain
    )
    assert iap_result == sbr_scope == sbr_invalidation
    assert "uncertain-node" in iap_result
