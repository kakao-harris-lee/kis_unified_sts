"""material_change_closure — §18 invalidation reachability both-ways + property (design #19 §5.4/§0.4d).

The shared reachability kernel backs the §18 material-change closure. Axioms: trigger ∈ closure;
an uncertain / unproven edge is EXPANDED (never narrows); a proven-disconnected node is excluded;
a cycle terminates; ∅ change_triggers => ∅ (availability side); ∅ graph + trigger => {trigger}.
The iap ``invalidation_closure`` / sbr ``_reachability_closure`` third/fourth legs live in
``test_seam_iap.py`` / ``test_seam_sbr.py`` (real sibling imports as tests).

Regime tag: predicate / model substrate only; VTG-EV-006/008 NOT_IMPLEMENTED (`/3` residue);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from hypothesis import given
from tos.venue import material_change_closure

from ._venue_strategies import graph_and_trigger


def test_single_trigger_is_in_its_own_closure() -> None:
    """(§18 / §4.7) A single material change is always in its own invalidation closure."""
    assert material_change_closure({}, frozenset({"t"})) == frozenset({"t"})


def test_empty_change_invalidates_nothing_availability_side() -> None:
    """(§18 canary b) No material change => nothing invalidated (a valid decision stays valid)."""
    assert material_change_closure({"t": frozenset({"a"})}, frozenset()) == frozenset()


def test_transitive_reachability_no_escape() -> None:
    """(§18 line 412) Every transitively-affected decision is captured (no escape — fail-open guard)."""
    graph = {
        "cut": frozenset({"d1"}),
        "d1": frozenset({"d2"}),
        "d2": frozenset({"egress"}),
    }
    assert material_change_closure(graph, frozenset({"cut"})) == frozenset(
        {"cut", "d1", "d2", "egress"}
    )


def test_unproven_edge_expands() -> None:
    """(§18 line 412 / §5.8) An uncertain edge widens the closure (an affected decision cannot escape)."""
    closure = material_change_closure(
        {"cut": frozenset({"d1"})},
        frozenset({"cut"}),
        unproven={"d1": frozenset({"maybe-affected"})},
    )
    assert "maybe-affected" in closure


def test_proven_disconnected_node_excluded() -> None:
    """(§18 availability) A proven-disconnected decision is NOT spuriously invalidated."""
    graph = {"cut": frozenset({"d1"}), "island": frozenset({"island-dep"})}
    closure = material_change_closure(graph, frozenset({"cut"}))
    assert closure == frozenset({"cut", "d1"})
    assert "island" not in closure


def test_multiple_triggers_union() -> None:
    """(§18) The closure is the union over every material change trigger."""
    graph = {"c1": frozenset({"a"}), "c2": frozenset({"b"})}
    assert material_change_closure(graph, frozenset({"c1", "c2"})) == frozenset(
        {"c1", "c2", "a", "b"}
    )


def test_cycle_terminates() -> None:
    """(pure reachability) A dependency cycle terminates and includes the cycle."""
    graph = {"t": frozenset({"a"}), "a": frozenset({"t"})}
    assert material_change_closure(graph, frozenset({"t"})) == frozenset({"t", "a"})


@given(graph_and_trigger())
def test_property_completeness_no_dependent_escapes(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(property, §18) No direct dependent of a closure member escapes (completeness)."""
    graph, trigger = graph_and_trigger_value
    closure = material_change_closure(graph, frozenset({trigger}))
    assert trigger in closure
    for member in closure:
        for dependent in graph.get(member, frozenset()):
            assert dependent in closure, "a reachable dependent escaped (fail-open)"


@given(graph_and_trigger())
def test_property_uncertain_only_widens(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(property, §5.8) Adding an uncertain edge can only widen (⊇) — never narrow."""
    graph, trigger = graph_and_trigger_value
    base = material_change_closure(graph, frozenset({trigger}))
    widened = material_change_closure(
        graph, frozenset({trigger}), unproven={trigger: frozenset({"uncertain-x"})}
    )
    assert base <= widened
    assert "uncertain-x" in widened


@given(graph_and_trigger())
def test_property_is_deterministic(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(pure function) The closure is deterministic — two computations agree exactly."""
    graph, trigger = graph_and_trigger_value
    assert material_change_closure(
        graph, frozenset({trigger})
    ) == material_change_closure(graph, frozenset({trigger}))
