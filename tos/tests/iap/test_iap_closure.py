"""invalidation_closure — invalidation dependency closure (design #15 §5.4; IAP-EV-007 substrate, core L1 slice).

The closure property (§7 / §4.4): a material trigger reaches EVERY dependent (no escape — a
partial closure is a fail-open); an uncertain edge is EXPANDED (treated reachable — under-count is
prohibited, the #14 MAJOR-1 safety direction); a proven-disconnected node is excluded (the
availability side). ∅ both-ways: an empty graph yields the minimal closure {trigger}. materiality
UNKNOWN => MATERIAL is the entry condition (§5.7 line 126). Pure function — deterministic.

Regime tag: predicate / model substrate only; IAP-EV-007 NOT_IMPLEMENTED (`/3` residue);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.iap import MaterialityVerdict, invalidation_closure, materiality_is_material


def test_transitive_reachability() -> None:
    """(§14 line 361) The closure includes every transitively-reachable dependent (no escape)."""
    graph = {
        "t": frozenset({"a", "b"}),
        "a": frozenset({"c"}),
        "b": frozenset({"c", "d"}),
    }
    assert invalidation_closure(graph, "t") == frozenset({"t", "a", "b", "c", "d"})


def test_trigger_is_in_its_own_closure() -> None:
    """(∅ / §4.7) An empty graph yields the minimal closure {trigger} — not a vacuous empty set."""
    assert invalidation_closure({}, "t") == frozenset({"t"})


def test_uncertain_edge_is_expanded() -> None:
    """(§4.4, #14 MAJOR-1) An uncertain edge is followed (reachable) — under-count is a fail-open."""
    closure = invalidation_closure(
        {"t": frozenset({"a"})},
        "t",
        uncertain={"a": frozenset({"maybe-dependent"})},
    )
    assert "maybe-dependent" in closure


def test_disconnected_node_is_excluded() -> None:
    """(availability side) A proven-disconnected node is NOT spuriously invalidated."""
    graph = {"t": frozenset({"a"}), "island": frozenset({"island-dep"})}
    closure = invalidation_closure(graph, "t")
    assert closure == frozenset({"t", "a"})
    assert "island" not in closure


def test_cycle_terminates() -> None:
    """(pure reachability) A dependency cycle terminates (visited-set) and includes the cycle."""
    graph = {"t": frozenset({"a"}), "a": frozenset({"t"})}
    assert invalidation_closure(graph, "t") == frozenset({"t", "a"})


def test_materiality_unknown_is_the_entry_condition() -> None:
    """(§5.7 line 126) UNKNOWN / MATERIAL materiality enters the closure; IMMATERIAL does not."""
    assert materiality_is_material(MaterialityVerdict.UNKNOWN) is True
    assert materiality_is_material(MaterialityVerdict.MATERIAL) is True
    assert materiality_is_material(MaterialityVerdict.IMMATERIAL) is False


@st.composite
def _graph_and_trigger(draw: st.DrawFn) -> tuple[dict[str, frozenset[str]], str]:
    nodes = draw(
        st.lists(st.text(min_size=1, max_size=3), min_size=1, max_size=6, unique=True)
    )
    graph: dict[str, frozenset[str]] = {}
    for node in nodes:
        deps = draw(st.sets(st.sampled_from(nodes), max_size=len(nodes)))
        graph[node] = frozenset(deps)
    trigger = draw(st.sampled_from(nodes))
    return graph, trigger


@given(_graph_and_trigger())
def test_closure_is_complete_no_dependent_escapes(
    graph_and_trigger: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(property, §4.4) No direct dependent of a closure member escapes the closure (completeness)."""
    graph, trigger = graph_and_trigger
    closure = invalidation_closure(graph, trigger)
    assert trigger in closure
    for member in closure:
        for dependent in graph.get(member, frozenset()):
            assert (
                dependent in closure
            ), "a reachable dependent escaped the closure (fail-open)"


@given(_graph_and_trigger())
def test_closure_is_deterministic(
    graph_and_trigger: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(pure function) The closure is deterministic — two computations agree exactly."""
    graph, trigger = graph_and_trigger
    assert invalidation_closure(graph, trigger) == invalidation_closure(graph, trigger)


@given(_graph_and_trigger())
def test_uncertain_only_widens_never_narrows(
    graph_and_trigger: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(property, §4.4) Adding uncertain edges can only widen (⊇) the closure — never narrow it."""
    graph, trigger = graph_and_trigger
    base = invalidation_closure(graph, trigger)
    widened = invalidation_closure(
        graph, trigger, uncertain={trigger: frozenset({"uncertain-x"})}
    )
    assert base <= widened
    assert "uncertain-x" in widened
