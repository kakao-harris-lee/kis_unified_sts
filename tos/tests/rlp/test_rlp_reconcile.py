"""Group reconcile regression — no-union, MAX-generation, negative-retention (design #25 §4.4 / #22 MAJOR-1).

The #22 MAJOR-1 lesson: a group / scope verdict must reconcile **all** entries conservatively, never
the first. This suite property-checks that ``no_union_coverage`` is any-narrow-wins and
order-independent, ``negative_results_retained`` requires every negative class (a passing subset
cannot erase them), and the Promotion Generation fence takes the MAX (a newer generation retires a
predecessor).

Regime tag: predicate substrate only; reconcile seal; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.rlp import (
    MANDATED_EVIDENCE_FLOOR,
    NEGATIVE_RESULT_CLASSES,
    CoverageVerdict,
    negative_results_retained,
    no_union_coverage,
    promotion_generation_advances,
)

from ._rlp_strategies import clean_coverage_claim, clean_package


@given(flags=st.lists(st.booleans(), min_size=1, max_size=5))
def test_no_union_any_narrow_wins_order_independent(flags: list[bool]) -> None:
    """(§4.4) no_union_coverage denies unless EVERY claim holds — order-independent, any-narrow-wins."""
    claims = [
        (
            clean_coverage_claim()
            if ok
            else clean_coverage_claim(verdict=CoverageVerdict.UNCOVERED)
        )
        for ok in flags
    ]
    expected = all(flags)
    assert no_union_coverage(claims) is expected
    assert no_union_coverage(list(reversed(claims))) is expected
    # a single narrow-failing claim anywhere dominates the aggregate.
    if not all(flags):
        assert no_union_coverage(claims) is False


@given(missing=st.sampled_from(list(NEGATIVE_RESULT_CLASSES)))
def test_negative_retention_requires_all_never_a_subset(missing) -> None:
    """(§4.4 / RLP-INV-009) A passing subset cannot erase a negative class — all-required-present."""
    package = clean_package(present_element_classes=MANDATED_EVIDENCE_FLOOR - {missing})
    assert negative_results_retained(package) is False
    # the full manifest retains all — order/entry independent (a frozenset has no first entry).
    assert negative_results_retained(clean_package()) is True


@given(
    predecessor=st.integers(min_value=0, max_value=50),
    candidate=st.integers(min_value=0, max_value=50),
)
def test_promotion_generation_max_fence(predecessor: int, candidate: int) -> None:
    """(§5.10 / §4.4) Only a strictly-newer Promotion Generation advances (MAX fence, not first)."""
    advances = promotion_generation_advances(predecessor, candidate)
    assert advances is (candidate > predecessor)


def test_promotion_generation_none_fails_closed() -> None:
    """(§5.10) A None generation on either side fails closed (never advances)."""
    assert promotion_generation_advances(None, 5) is False
    assert promotion_generation_advances(5, None) is False
    assert promotion_generation_advances(5, 5) is False  # equal is not an advance
