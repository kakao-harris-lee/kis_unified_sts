"""Conservative usable lifetime — unknown/non-positive => invalid (time design §3(3)).

EV-L1 predicate substrate only; TIME-EV-006 remains NOT_IMPLEMENTED pending
EV-L2/L3 fault injection. Pure integer arithmetic over injected bounds; no clock.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.time import (
    MonotonicReading,
    conservative_usable_lifetime,
    elapsed_within_continuity,
)

_TERMS = (
    "source_transport_uncertainty",
    "max_drift_error",
    "suspension_uncertainty",
    "safety_margin",
)

#: Every magnitude term, including issued_lifetime + elapsed_monotonic (v1.2 MAJOR).
_ALL_MAGNITUDE_TERMS = ("issued_lifetime", "elapsed_monotonic", *_TERMS)


def _lifetime(**overrides: object) -> int | None:
    base: dict[str, object] = {
        "issued_lifetime": 10_000,
        "elapsed_monotonic": 0,
        "source_transport_uncertainty": 0,
        "max_drift_error": 0,
        "suspension_uncertainty": 0,
        "safety_margin": 0,
    }
    base.update(overrides)
    return conservative_usable_lifetime(**base)  # type: ignore[arg-type]


def test_all_zero_uncertainty_returns_issued_minus_elapsed() -> None:
    """With zero uncertainty, lifetime is issued − elapsed (§11.2 formula)."""
    assert _lifetime(issued_lifetime=10_000, elapsed_monotonic=1_000) == 9_000


@given(term=st.sampled_from(_TERMS))
def test_unknown_term_makes_invalid(term: str) -> None:
    """Any unknown (None) term => None (invalid), never a guess (§11.2 294)."""
    assert _lifetime(**{term: None}) is None


def test_unknown_issued_or_elapsed_makes_invalid() -> None:
    """Unknown issued lifetime or elapsed also invalidates (fail-closed)."""
    assert _lifetime(issued_lifetime=None) is None
    assert _lifetime(elapsed_monotonic=None) is None


@given(over=st.integers(0, 10**6))
def test_nonpositive_result_is_invalid_not_clamped(over: int) -> None:
    """A non-positive result is invalid (None), never clamped to zero (§11.2 294)."""
    # elapsed + margins meet/exceed the issued lifetime.
    assert _lifetime(issued_lifetime=1_000, elapsed_monotonic=1_000 + over) is None


@given(
    base_unc=st.integers(0, 4_000),
    bump=st.integers(1, 4_000),
    term=st.sampled_from(_TERMS),
)
def test_monotone_decreasing_in_each_uncertainty(
    base_unc: int, bump: int, term: str
) -> None:
    """A larger uncertainty term yields a shorter (or invalid) lifetime (§3(3))."""
    smaller = _lifetime(issued_lifetime=20_000, **{term: base_unc})
    larger = _lifetime(issued_lifetime=20_000, **{term: base_unc + bump})
    assert smaller is not None  # 20_000 budget dominates this range
    if larger is None:
        return  # bumped past the budget => invalid, still "not longer"
    assert larger < smaller


# ---- v1.2 MAJOR: negative magnitude terms must fail-closed (not extend a lease) ----


@given(term=st.sampled_from(_ALL_MAGNITUDE_TERMS), neg=st.integers(-(10**6), -1))
def test_negative_magnitude_term_is_invalid(term: str, neg: int) -> None:
    """A negative magnitude term => None; a negative drift/elapsed must NOT extend a lease.

    Regression for the reproduced fail-open (drift=-5000 => 5100, elapsed=-5000 =>
    6000). The prior non-negative-only strategy hid this.
    """
    assert _lifetime(**{term: neg}) is None


def test_negative_drift_does_not_extend_over_baseline() -> None:
    """Explicit reproduced case: negative drift no longer beats the drift=0 baseline."""
    baseline = _lifetime(issued_lifetime=1000, elapsed_monotonic=900, max_drift_error=0)
    assert baseline == 100
    assert (
        _lifetime(issued_lifetime=1000, elapsed_monotonic=900, max_drift_error=-5000)
        is None
    )


@given(back=st.integers(1, 10**6))
def test_discontinuity_elapsed_does_not_leak_into_lease(back: int) -> None:
    """A same-continuity discontinuity (negative elapsed) fed to lifetime => None (§13).

    ``elapsed_within_continuity`` returns a negative value when the monotonic value
    goes backwards (a discontinuity); that negative must not lengthen the lease.
    """
    disc = elapsed_within_continuity(
        MonotonicReading(monotonic_continuity_id="c1", local_monotonic_value=1000),
        MonotonicReading(
            monotonic_continuity_id="c1", local_monotonic_value=1000 - back
        ),
    )
    assert disc is not None and disc < 0
    assert _lifetime(issued_lifetime=5000, elapsed_monotonic=disc) is None
