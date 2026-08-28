"""CII-EV-008 correction/invalidation fan-out + economic-effect orthogonality.

Design §4.5 (CII-INV-008/009): a material correction invalidates the transitive
closure of affected downstream permissions, while economic effects (orders,
fills, exposure, capacity) are orthogonal and survive the invalidation.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.capsule.observation import CorrectionLinks, Observation
from tos.capsule.predicates import (
    correction_invalidation_closure,
    economic_effects_after_invalidation,
    transitive_dependents,
)

_NODES = [f"n{i}" for i in range(5)]
_edge_maps = st.dictionaries(
    st.sampled_from(_NODES),
    st.lists(st.sampled_from(_NODES), max_size=4, unique=True),
    max_size=5,
)


@given(
    edges=_edge_maps, roots=st.lists(st.sampled_from(_NODES), max_size=3, unique=True)
)
def test_closure_is_transitively_closed(edges: dict, roots: list) -> None:
    """The invalidation closure is closed under the dependency relation (fan-out)."""
    closure = transitive_dependents(roots, edges)
    # every dependent of a closure member is also in the closure (no missed hop)
    for node in closure:
        for dependent in edges.get(node, []):
            assert dependent in closure


@given(edges=_edge_maps)
def test_direct_dependents_are_included(edges: dict) -> None:
    """Every direct dependent of a root is invalidated (design §4.5)."""
    roots = ["n0"]
    closure = transitive_dependents(roots, edges)
    for dependent in edges.get("n0", []):
        assert dependent in closure


def test_correction_links_drive_closure() -> None:
    """A correction's links seed the invalidation closure (CII-INV-008)."""
    edges = {"n0": ["n1"], "n1": ["n2"], "n3": ["n4"]}
    correction = Observation(
        correction_links=CorrectionLinks(correction_of="n0", predecessor_ids=("n3",))
    )
    closure = correction_invalidation_closure(correction, edges)
    assert closure == frozenset({"n1", "n2", "n4"})


@given(
    effects=st.sets(st.text(min_size=1, max_size=5), max_size=5),
    invalidated=st.sets(st.text(min_size=1, max_size=5), max_size=5),
)
def test_economic_effects_survive_invalidation(effects: set, invalidated: set) -> None:
    """Context invalidation never erases economic effects (CII-INV-009, orthogonal)."""
    survived = economic_effects_after_invalidation(effects, invalidated)
    assert survived == frozenset(effects)
