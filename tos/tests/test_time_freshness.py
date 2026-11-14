"""Freshness verdict — negative not clamped, UNKNOWN != 0 (time design §4)."""

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


@given(neg=st.integers(-(10**6), -1))
def test_negative_delay_bound_is_unknown_not_fresh(neg: int) -> None:
    """A negative delay bound => UNKNOWN; it must NOT hide staleness (reproduced fail-open)."""
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
    assert (
        freshness_verdict(
            source_age=-5, delay_bounds=[0], max_age_bound=100, future_tolerance=neg
        )
        is FreshnessVerdict.UNKNOWN
    )


def test_legitimate_negative_source_age_still_evaluated() -> None:
    """A negative source_age (future-dated) is NOT blanket-rejected (kept legitimate)."""
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


def test_reported_fail_open_example_is_not_fresh() -> None:
    """The exact falsifying example is pinned: future-dated + no threshold != FRESH."""
    assert (
        freshness_verdict(
            source_age=-1, delay_bounds=[], max_age_bound=None, future_tolerance=50
        )
        is FreshnessVerdict.UNKNOWN
    )


def test_future_dated_within_tolerance_is_not_fresh_without_a_delay_bound() -> None:
    """An unknown delay bound also outranks the future-tolerance path (§9 241)."""
    assert (
        freshness_verdict(
            source_age=-1, delay_bounds=[None], max_age_bound=100, future_tolerance=50
        )
        is FreshnessVerdict.UNKNOWN
    )


@given(
    source_age=st.integers(-1000, 1000),
    bounds=st.lists(st.integers(0, 100), max_size=3),
    tol=st.integers(0, 10**6),
)
def test_no_source_age_is_fresh_without_a_threshold(
    source_age: int, bounds: list[int], tol: int
) -> None:
    """Matrix: for an unestablished ``max_age_bound``, *no* source age is FRESH."""
    verdict = freshness_verdict(
        source_age=source_age,
        delay_bounds=bounds,
        max_age_bound=None,
        future_tolerance=tol,
    )
    assert verdict is not FreshnessVerdict.FRESH
    expected = (
        FreshnessVerdict.CONFLICTED
        if source_age < 0 and -source_age > tol
        else FreshnessVerdict.UNKNOWN
    )
    assert verdict is expected


@given(
    source_age=st.integers(-1000, 1000),
    bounds=st.lists(st.integers(0, 100), max_size=3),
    max_age=st.integers(0, 5000),
    tol=st.integers(0, 10**6),
)
def test_established_threshold_matrix_preserves_prior_semantics(
    source_age: int, bounds: list[int], max_age: int, tol: int
) -> None:
    """Counterpart: with every bound established, the prior semantics are unchanged."""
    verdict = freshness_verdict(
        source_age=source_age,
        delay_bounds=bounds,
        max_age_bound=max_age,
        future_tolerance=tol,
    )
    if source_age < 0:
        expected = (
            FreshnessVerdict.CONFLICTED if -source_age > tol else FreshnessVerdict.FRESH
        )
    elif source_age + sum(bounds) > max_age:
        expected = FreshnessVerdict.STALE
    else:
        expected = FreshnessVerdict.FRESH
    assert verdict is expected
