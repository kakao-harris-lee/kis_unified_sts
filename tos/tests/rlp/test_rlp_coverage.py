"""coverage_supports_claim yolk (RLP-EV-006) — non-extrapolation subset (design #25 §5.3).

The yolk 3 property suite (the cleanest L1 slice — pure subset): ∅ both-ways, claimed ⊆ observed
subset both-ways, extrapolation denial with the sole equivalence exception, unexercised-is-uncovered,
verdict admissibility, and no-union over multiple claims.

Regime tag: structural / subset predicate substrate only; RLP-EV-006 NOT_IMPLEMENTED (``EV-L1/3``);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.rlp import (
    CoverageVerdict,
    coverage_supports_claim,
    no_union_coverage,
)

from ._rlp_strategies import TRIBOOL, clean_coverage_claim


def test_empty_seal_both_ways() -> None:
    """(§5.3 point 1) None claim / empty observed / empty claimed all deny."""
    assert coverage_supports_claim(None) is False
    assert (
        coverage_supports_claim(
            clean_coverage_claim(
                observed_scope=frozenset(), claimed_scope=frozenset({"a"})
            )
        )
        is False
    )
    assert (
        coverage_supports_claim(
            clean_coverage_claim(
                claimed_scope=frozenset(), observed_scope=frozenset({"a"})
            )
        )
        is False
    )


def test_clean_claim_is_supported() -> None:
    """(§5.3 positive) claimed ⊆ observed, disjoint unexercised, verdict COVERED passes."""
    assert coverage_supports_claim(clean_coverage_claim()) is True


def test_subset_holds_when_claimed_within_observed() -> None:
    """(§5.3 point 2) claimed == observed and claimed ⊂ observed both pass (no extrapolation)."""
    assert (
        coverage_supports_claim(
            clean_coverage_claim(
                claimed_scope=frozenset({"a", "b"}),
                observed_scope=frozenset({"a", "b"}),
                unexercised_conditions=frozenset(),
            )
        )
        is True
    )


def test_extrapolation_denied_without_proven_equivalence() -> None:
    """(§5.3 point 2/3) A claimed element outside observed denies unless equivalence is proven."""
    claim = clean_coverage_claim(
        claimed_scope=frozenset({"a", "b", "z"}),
        observed_scope=frozenset({"a", "b"}),
        unexercised_conditions=frozenset(),
        equivalence_positively_proven=None,
    )
    assert coverage_supports_claim(claim) is False


@given(equivalence=TRIBOOL)
def test_equivalence_is_the_sole_extrapolation_path(equivalence: bool | None) -> None:
    """(§5.3 point 3 / §4.3) Cross-scope inference admits only on equivalence_positively_proven True."""
    claim = clean_coverage_claim(
        claimed_scope=frozenset({"a", "z"}),
        observed_scope=frozenset({"a"}),
        unexercised_conditions=frozenset(),
        equivalence_positively_proven=equivalence,
    )
    assert coverage_supports_claim(claim) is (equivalence is True)


def test_unexercised_condition_in_claim_denies() -> None:
    """(§5.3 point 4 / RLP-INV-008) A claimed scope overlapping an unexercised condition denies."""
    claim = clean_coverage_claim(
        claimed_scope=frozenset({"a", "crash"}),
        observed_scope=frozenset({"a", "crash"}),
        unexercised_conditions=frozenset({"crash"}),
    )
    assert coverage_supports_claim(claim) is False


@given(verdict=st.sampled_from(list(CoverageVerdict)))
def test_verdict_must_be_covered(verdict: CoverageVerdict) -> None:
    """(§5.3 point 5 / §4.2) Only verdict COVERED passes; UNCOVERED / UNKNOWN deny."""
    claim = clean_coverage_claim(verdict=verdict)
    assert coverage_supports_claim(claim) is (verdict is CoverageVerdict.COVERED)


def test_no_union_over_multiple_claims() -> None:
    """(§4.4/§6.3 / §17 line 446) any-narrow-wins — a single failing claim denies the aggregate."""
    good = clean_coverage_claim()
    bad = clean_coverage_claim(verdict=CoverageVerdict.UNCOVERED)
    assert no_union_coverage([good, good]) is True
    assert no_union_coverage([good, bad]) is False
    assert no_union_coverage([]) is False  # ∅ ⇒ nothing proven


@given(claims=st.lists(st.booleans(), min_size=1, max_size=4))
def test_no_union_order_independent(claims: list[bool]) -> None:
    """(§4.4) no_union_coverage is order-independent — all must hold regardless of permutation."""
    built = [
        (
            clean_coverage_claim()
            if ok
            else clean_coverage_claim(verdict=CoverageVerdict.UNKNOWN)
        )
        for ok in claims
    ]
    expected = all(claims)
    assert no_union_coverage(built) is expected
    assert no_union_coverage(list(reversed(built))) is expected
