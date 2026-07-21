"""Freshness verdict — negative not clamped, UNKNOWN != 0 (time design §4).

EV-L1 predicate substrate only; TIME-EV-007 remains NOT_IMPLEMENTED pending
EV-L2/L3 fault injection. This is the strongest-precedent substrate (shipped
``compare_order`` overlap⇒AMBIGUOUS + capsule ``Freshness.within_bound=None``⇒
UNKNOWN). Bounds are hypothesis-generated injected values (no hard-coded
threshold).
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.time import FreshnessVerdict, freshness_verdict


def test_missing_source_age_is_unknown() -> None:
    """A missing source age => UNKNOWN (§9 243)."""
    assert (
        freshness_verdict(
            source_age=None, delay_bounds=[0], max_age_bound=1000, future_tolerance=0
        )
        is FreshnessVerdict.UNKNOWN
    )


@given(bounds=st.lists(st.integers(0, 1000), min_size=1, max_size=4))
def test_missing_delay_bound_is_unknown(bounds: list[int]) -> None:
    """An unestablished (None) delay-class bound => UNKNOWN, not fresh (§9 241)."""
    with_none = [*bounds, None]
    assert (
        freshness_verdict(
            source_age=0,
            delay_bounds=with_none,
            max_age_bound=10**9,
            future_tolerance=0,
        )
        is FreshnessVerdict.UNKNOWN
    )


@given(
    source_age=st.integers(0, 1000), bounds=st.lists(st.integers(0, 100), max_size=3)
)
def test_missing_max_age_is_unknown_not_fresh(
    source_age: int, bounds: list[int]
) -> None:
    """No freshness threshold => UNKNOWN (permissive use rejected, §8 210). UNKNOWN != 0."""
    assert (
        freshness_verdict(
            source_age=source_age,
            delay_bounds=bounds,
            max_age_bound=None,
            future_tolerance=0,
        )
        is FreshnessVerdict.UNKNOWN
    )


@given(future=st.integers(1, 10**6), tol=st.integers(0, 10**6))
def test_future_beyond_tolerance_is_conflicted(future: int, tol: int) -> None:
    """A future source time is CONFLICTED iff it exceeds the tolerance (§9 243)."""
    verdict = freshness_verdict(
        source_age=-future, delay_bounds=[0], max_age_bound=10**9, future_tolerance=tol
    )
    if future > tol:
        assert verdict is FreshnessVerdict.CONFLICTED
    else:
        # within skew tolerance: fresh (negative age was evaluated, not clamped)
        assert verdict is FreshnessVerdict.FRESH


@given(future=st.integers(1, 10**6))
def test_negative_age_without_tolerance_is_conflicted(future: int) -> None:
    """A negative age with no tolerance is CONFLICTED (fail-closed; not clamped to 0)."""
    assert (
        freshness_verdict(
            source_age=-future,
            delay_bounds=[0],
            max_age_bound=10**9,
            future_tolerance=None,
        )
        is FreshnessVerdict.CONFLICTED
    )


@given(
    source_age=st.integers(0, 1000),
    bounds=st.lists(st.integers(0, 200), max_size=4),
    max_age=st.integers(0, 5000),
)
def test_stale_vs_fresh_by_total_age(
    source_age: int, bounds: list[int], max_age: int
) -> None:
    """total = source_age + Σ bounds; STALE iff over max_age, else FRESH (§9)."""
    verdict = freshness_verdict(
        source_age=source_age,
        delay_bounds=bounds,
        max_age_bound=max_age,
        future_tolerance=0,
    )
    total = source_age + sum(bounds)
    if total > max_age:
        assert verdict is FreshnessVerdict.STALE
    else:
        assert verdict is FreshnessVerdict.FRESH


# ---- v1.2 MAJOR: negative injected bounds must fail-closed to UNKNOWN ----


@given(neg=st.integers(-(10**6), -1))
def test_negative_delay_bound_is_unknown_not_fresh(neg: int) -> None:
    """A negative delay bound => UNKNOWN; it must NOT hide staleness (reproduced fail-open).

    Prior bug: source_age=1000, delay=[-5000], max_age=1000 => FRESH. Now UNKNOWN.
    """
    assert (
        freshness_verdict(
            source_age=1000,
            delay_bounds=[neg],
            max_age_bound=1000,
            future_tolerance=0,
        )
        is FreshnessVerdict.UNKNOWN
    )


@given(neg=st.integers(-(10**6), -1))
def test_negative_max_age_bound_is_unknown(neg: int) -> None:
    """A negative max-age bound is unestablished => UNKNOWN (fail-closed)."""
    assert (
        freshness_verdict(
            source_age=10, delay_bounds=[0], max_age_bound=neg, future_tolerance=0
        )
        is FreshnessVerdict.UNKNOWN
    )


@given(neg=st.integers(-(10**6), -1))
def test_negative_future_tolerance_is_unknown(neg: int) -> None:
    """A negative future tolerance is an unestablished bound => UNKNOWN (fail-closed)."""
    # Also holds for a future-dated source: a corrupt tolerance cannot bless it.
    assert (
        freshness_verdict(
            source_age=-5, delay_bounds=[0], max_age_bound=100, future_tolerance=neg
        )
        is FreshnessVerdict.UNKNOWN
    )


def test_legitimate_negative_source_age_still_evaluated() -> None:
    """A negative source_age (future-dated) is NOT blanket-rejected (kept legitimate)."""
    # within tolerance => FRESH; beyond tolerance => CONFLICTED (unchanged behavior).
    assert (
        freshness_verdict(
            source_age=-5, delay_bounds=[0], max_age_bound=100, future_tolerance=10
        )
        is FreshnessVerdict.FRESH
    )
    assert (
        freshness_verdict(
            source_age=-50, delay_bounds=[0], max_age_bound=100, future_tolerance=10
        )
        is FreshnessVerdict.CONFLICTED
    )
