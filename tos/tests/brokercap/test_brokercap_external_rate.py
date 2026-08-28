"""External-detection / rate-admission bounds (design #10 §5.5; BC-EV-011/012).

Bounds are injected (never hardcoded — §8); a None bound fails closed; a missed bound or
protective-headroom encroachment denies new risk.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.brokercap import external_detection_ok, rate_admission_ok

_NN = st.integers(min_value=0, max_value=1000)


# ---------------------------------------------------------------------------
# external_detection_ok
# ---------------------------------------------------------------------------


def test_within_bounds_ok() -> None:
    """(§16) Observed latency within both bounds => True."""
    assert external_detection_ok(detect_bound=10, contain_bound=20, observed_latency=5)


def test_missed_detect_bound_denies() -> None:
    """(§16.3 line 907-910) Observed latency past the detect bound => False (deny new risk)."""
    assert not external_detection_ok(
        detect_bound=10, contain_bound=20, observed_latency=11
    )


def test_missed_contain_bound_denies() -> None:
    """(§16.3) Observed latency past the contain bound => False."""
    assert not external_detection_ok(
        detect_bound=100, contain_bound=20, observed_latency=25
    )


def test_none_bound_fails_closed() -> None:
    """(§8) Any None bound / observation => False (no hardcoded default)."""
    assert not external_detection_ok(None, 20, 5)
    assert not external_detection_ok(10, None, 5)
    assert not external_detection_ok(10, 20, None)


@given(detect=_NN, contain=_NN, observed=_NN)
def test_external_detection_matches_bound_definition(
    detect: int, contain: int, observed: int
) -> None:
    """external_detection_ok iff observed <= detect AND observed <= contain."""
    assert external_detection_ok(detect, contain, observed) == (
        observed <= detect and observed <= contain
    )


# ---------------------------------------------------------------------------
# rate_admission_ok
# ---------------------------------------------------------------------------


def test_rate_admission_ok_positive() -> None:
    """(§17.2) Ordinary below ceiling ∧ protective headroom reserved => True."""
    assert rate_admission_ok(
        ordinary_below_ceiling=True, protective_headroom_reserved=True
    )


def test_ordinary_encroaching_headroom_denies() -> None:
    """(§17.2 canary) Ordinary traffic encroaching on protective headroom => False."""
    assert not rate_admission_ok(
        ordinary_below_ceiling=False, protective_headroom_reserved=True
    )


@given(
    ordinary=st.sampled_from([True, False, None]),
    headroom=st.sampled_from([True, False, None]),
)
def test_rate_admission_fail_closed(
    ordinary: bool | None, headroom: bool | None
) -> None:
    """rate_admission_ok is True only when both flags are exactly True."""
    assert rate_admission_ok(ordinary, headroom) == (
        ordinary is True and headroom is True
    )
