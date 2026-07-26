"""Group reconcile order-independence (design #23 §4.4 / #22 MAJOR-1 seal).

The #22 MAJOR-1 lesson: when many entries map to one group / scope / dimension, the verdict must
reconcile **all** entries conservatively, never the first. cur's reconcile points —
``restrictive_floor_reconciled`` (MAX floor), ``multi_domain_no_union`` (any-restriction-wins),
``conflicting_owner_restricts`` / ``restrictive_union_scope`` (union of credible scopes) — are all
order-independent and the most-restrictive entry dominates.

Regime tag: predicate substrate only; reconcile seal; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import random

import hypothesis.strategies as st
from hypothesis import given
from tos.cur import (
    DomainProof,
    OwnerSubmission,
    ProofResult,
    conflicting_owner_restricts,
    multi_domain_no_union,
    restrictive_floor_reconciled,
    restrictive_union_scope,
)

# ---------------------------------------------------------------------------
# restrictive_floor_reconciled — MAX (not first), order-independent (§6.2)
# ---------------------------------------------------------------------------


def test_floor_reconciled_takes_the_max_not_the_first() -> None:
    """(§6.2 / MAJOR-1) The reconciled floor is the MAX (most restrictive), not the first entry."""
    assert restrictive_floor_reconciled([3, 9, 5]) == 9
    assert (
        restrictive_floor_reconciled([9, 3, 5]) == 9
    )  # first-entry would wrongly give 9 or 3


def test_floor_reconciled_empty_and_none_deny() -> None:
    """(§6.2 ∅ / fail-closed) An ∅ set or any None entry ⇒ None (deny — an unknown floor could be higher)."""
    assert restrictive_floor_reconciled([]) is None
    assert restrictive_floor_reconciled([3, None, 5]) is None


@given(floors=st.lists(st.integers(min_value=0, max_value=50), min_size=1, max_size=8))
def test_floor_reconciled_is_order_independent(floors: list[int]) -> None:
    """(§6.2 property) The reconciled floor is invariant under permutation and equals max()."""
    shuffled = list(floors)
    random.Random(1234).shuffle(shuffled)
    assert restrictive_floor_reconciled(floors) == restrictive_floor_reconciled(
        shuffled
    )
    assert restrictive_floor_reconciled(floors) == max(floors)


# ---------------------------------------------------------------------------
# multi_domain_no_union — any-restriction-wins, order-independent (§6.7)
# ---------------------------------------------------------------------------


def _domain(name: str, result: ProofResult | None) -> DomainProof:
    return DomainProof(domain=name, result=result)


def test_multi_domain_all_current_passes() -> None:
    """(§6.7 both-ways) All-CURRENT domains pass; a single non-CURRENT denies the whole."""
    proofs = [_domain("d1", ProofResult.CURRENT), _domain("d2", ProofResult.CURRENT)]
    assert multi_domain_no_union(proofs) is True


def test_multi_domain_any_non_current_denies() -> None:
    """(§6.7 / §16 no-union) A single RESTRICTED / UNKNOWN / None domain denies the whole request."""
    for bad in (ProofResult.RESTRICTED, ProofResult.UNKNOWN, None):
        proofs = [_domain("d1", ProofResult.CURRENT), _domain("d2", bad)]
        assert multi_domain_no_union(proofs) is False


def test_multi_domain_empty_denies() -> None:
    """(§6.7 ∅) An ∅ domain set ⇒ deny (nothing proven)."""
    assert multi_domain_no_union([]) is False


@given(
    results=st.lists(
        st.sampled_from(
            [ProofResult.CURRENT, ProofResult.RESTRICTED, ProofResult.UNKNOWN, None]
        ),
        min_size=1,
        max_size=6,
    )
)
def test_multi_domain_is_order_independent_and_any_restriction_wins(
    results: list,
) -> None:
    """(§6.7 property) Order-independent; passes iff EVERY domain is CURRENT (any-restriction-wins)."""
    proofs = [_domain(f"d{i}", r) for i, r in enumerate(results)]
    shuffled = list(proofs)
    random.Random(99).shuffle(shuffled)
    assert multi_domain_no_union(proofs) == multi_domain_no_union(shuffled)
    expected = all(r is ProofResult.CURRENT for r in results)
    assert multi_domain_no_union(proofs) is expected


# ---------------------------------------------------------------------------
# conflicting_owner_restricts + restrictive_union_scope — union, order-independent (§6.3)
# ---------------------------------------------------------------------------


def test_conflicting_owner_restricts_any_conflict() -> None:
    """(§6.3) Any conflicting / forked / regressed owner ⇒ restrict; a clean set does not."""
    clean = [
        OwnerSubmission(
            owner_identity="o1",
            is_conflicting=False,
            is_fork=False,
            sequence_regression=False,
            missing_predecessor=False,
            unverifiable_scope=False,
        )
    ]
    assert conflicting_owner_restricts(clean) is False
    conflicted = clean + [OwnerSubmission(owner_identity="o2", is_conflicting=True)]
    assert conflicting_owner_restricts(conflicted) is True


def test_conflicting_owner_none_flag_is_conservative_restrict() -> None:
    """(§6.3 / §4.3) A None conflict flag is UNKNOWN ⇒ conservatively restrictive (negative polarity)."""
    unknown = [OwnerSubmission(owner_identity="o1")]  # all flags None
    assert conflicting_owner_restricts(unknown) is True


def test_conflicting_owner_empty_does_not_restrict() -> None:
    """(§6.3 availability) An ∅ submission set asserts no conflict (does not spuriously restrict)."""
    assert conflicting_owner_restricts([]) is False


def test_restrictive_union_scope_unions_credible_scopes() -> None:
    """(§6.3 / §10 line 280 / MAJOR-1) The restrictive closure unions the credible scopes (not first)."""
    subs = [
        OwnerSubmission(
            owner_identity="o1", affected_scope=("a", "b"), is_conflicting=True
        ),
        OwnerSubmission(owner_identity="o2", affected_scope=("b", "c"), is_fork=True),
        # a non-restrictive submission contributes nothing.
        OwnerSubmission(
            owner_identity="o3",
            affected_scope=("z",),
            is_conflicting=False,
            is_fork=False,
            sequence_regression=False,
            missing_predecessor=False,
            unverifiable_scope=False,
        ),
    ]
    assert restrictive_union_scope(subs) == frozenset({"a", "b", "c"})


@given(
    scopes=st.lists(
        st.lists(st.sampled_from(["a", "b", "c", "d"]), max_size=3),
        min_size=1,
        max_size=5,
    )
)
def test_restrictive_union_scope_is_order_independent(scopes: list[list[str]]) -> None:
    """(§6.3 property) The union scope is invariant under permutation (all restrictive here)."""
    subs = [
        OwnerSubmission(
            owner_identity=f"o{i}", affected_scope=tuple(s), is_conflicting=True
        )
        for i, s in enumerate(scopes)
    ]
    shuffled = list(subs)
    random.Random(7).shuffle(shuffled)
    assert restrictive_union_scope(subs) == restrictive_union_scope(shuffled)
    assert restrictive_union_scope(subs) == frozenset().union(*(set(s) for s in scopes))
