"""Group reconcile — order-independent no-permissive-union + explicit-empty (design #26 §4.4 / #22 MAJOR-1).

The #22 MAJOR-1 lesson: a multi-member verdict must reconcile **all** members conservatively, never
the first. The combined Active Deviation Set is member == applicable (no omission, no surplus),
order-independent, with the §13 line 364 explicit-empty set valid (v1.1 MAJOR-1). The Deviation
Generation fence takes the MAX (a newer generation retires a predecessor), and the boundary is
union-only (any-add-wins).

Regime tag: reconcile predicate substrate only; WDR-EV-012 NOT_IMPLEMENTED; EV-L1-complete claim
forbidden.
"""

from __future__ import annotations

import tos.wdr as w
from hypothesis import given
from hypothesis import strategies as st

from ._wdr_strategies import clean_active_set, clean_boundary


@given(order=st.permutations(["d1", "d2", "d3"]))
def test_member_order_permutation_verdict_invariant(order: list[str]) -> None:
    """(§4.4 order-independence) Any permutation of member_decisions ⇒ same verdict."""
    applicable = frozenset({"d1", "d2", "d3"})
    aset = clean_active_set(member_decisions=tuple(order))
    assert w.combined_set_no_permissive_union(aset, applicable, True) is True


@given(order=st.permutations(["d1", "d2", "d3"]))
def test_omitted_member_denies_regardless_of_order(order: list[str]) -> None:
    """(§4.4 / §13 line 364) An applicable member omitted ⇒ invalid, in any permutation of the rest."""
    # applicable includes d4 which is never a member ⇒ omission ⇒ deny for every order.
    applicable = frozenset({"d1", "d2", "d3", "d4"})
    aset = clean_active_set(member_decisions=tuple(order))
    assert w.combined_set_no_permissive_union(aset, applicable, True) is False


def test_explicit_empty_valid_but_omission_and_surplus_invalid() -> None:
    """(§4.4 v1.1 three directions) explicit-empty valid; omission invalid; surplus invalid."""
    # explicit empty — valid (ADR §13 line 364)
    assert (
        w.combined_set_no_permissive_union(
            clean_active_set(member_decisions=()), frozenset(), True
        )
        is True
    )
    # omission — members ∅ but applicable ≠ ∅ ⇒ invalid
    assert (
        w.combined_set_no_permissive_union(
            clean_active_set(member_decisions=()), frozenset({"d1"}), True
        )
        is False
    )
    # surplus — applicable ∅ but members ≠ ∅ ⇒ invalid
    assert (
        w.combined_set_no_permissive_union(
            clean_active_set(member_decisions=("d1",)), frozenset(), True
        )
        is False
    )


@given(
    predecessor=st.integers(min_value=0, max_value=50),
    candidate=st.integers(min_value=0, max_value=50),
)
def test_deviation_generation_advances_max_fence(
    predecessor: int, candidate: int
) -> None:
    """(§5.8 / §4.4) deviation_generation_advances is a strict MAX fence — only a newer gen advances."""
    result = w.deviation_generation_advances(predecessor, candidate)
    assert result is (candidate > predecessor)


def test_deviation_generation_none_fails_closed() -> None:
    """(§5.8) A None generation on either side fails closed (no advance)."""
    assert w.deviation_generation_advances(None, 5) is False
    assert w.deviation_generation_advances(5, None) is False
    assert w.deviation_generation_advances(None, None) is False


def test_boundary_union_only_any_add_wins() -> None:
    """(§5.6 / §4.4) The boundary is union-only — a complete boundary is unshrunk (any-add-wins)."""
    assert w.boundary_is_union_only(clean_boundary()) is True
    # dropping any single item shrinks the union ⇒ not union-only.
    for item in w.NonWaivableBoundaryAnchor.BOUNDARY_ITEMS:
        assert w.boundary_is_union_only(clean_boundary(**{item: False})) is False
