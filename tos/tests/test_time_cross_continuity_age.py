"""Cross-continuity snapshot age — §8 5-step receipt-anchor path (time design §3(4)).

EV-L1 predicate substrate only; TIME-EV-010 remains NOT_IMPLEMENTED pending
EV-L2/L3 (+Security) fault injection. The issuer monotonic value is never
subtracted from a consumer clock; age is purely additive over injected bounds
plus consumer-local elapsed (§8 220).
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.time import (
    ConsumerReceiptAnchor,
    TimeContinuityIdentity,
    effective_snapshot_age_bound,
    effective_snapshot_age_bound_from_continuity,
    snapshot_age_admissible,
)

from ._time_strategies import issue_time_snapshot

_VALID_ANCHOR = ConsumerReceiptAnchor(
    consumer_monotonic_continuity_id="consumer-c1",
    consumer_local_monotonic_value_at_receipt=500,
)

_TERMS = (
    "issuer_signed_age",
    "issuer_age_uncertainty",
    "transport_bound",
    "queue_bound",
    "conversion_bound",
    "consumer_elapsed_since_receipt",
)


def _age(**overrides: object) -> int | None:
    base: dict[str, object] = {
        "issuer_signed_age": 10,
        "issuer_age_uncertainty": 5,
        "transport_bound": 2,
        "queue_bound": 3,
        "conversion_bound": 1,
        "consumer_elapsed_since_receipt": 4,
        "consumer_anchor_valid": True,
    }
    base.update(overrides)
    return effective_snapshot_age_bound(
        issue_time_snapshot(), _VALID_ANCHOR, **base  # type: ignore[arg-type]
    )


def test_age_is_additive_sum_of_bounds() -> None:
    """The age bound is the conservative additive sum (no subtraction, §8 220)."""
    assert _age() == 10 + 5 + 2 + 3 + 1 + 4


@given(term=st.sampled_from(_TERMS))
def test_missing_additive_term_is_unknown(term: str) -> None:
    """Any missing additive bound => UNKNOWN (None), fail-closed (§8 v)."""
    assert _age(**{term: None}) is None


def test_invalid_consumer_anchor_is_unknown() -> None:
    """A consumer restart/discontinuity (invalid anchor) => UNKNOWN (§8 220)."""
    assert _age(consumer_anchor_valid=False) is None


def test_missing_consumer_continuity_is_unknown() -> None:
    """A receipt anchor with no consumer continuity id => UNKNOWN (§8 220)."""
    result = effective_snapshot_age_bound(
        issue_time_snapshot(),
        ConsumerReceiptAnchor(consumer_monotonic_continuity_id=None),
        issuer_signed_age=1,
        issuer_age_uncertainty=1,
        transport_bound=1,
        queue_bound=1,
        conversion_bound=1,
        consumer_elapsed_since_receipt=1,
        consumer_anchor_valid=True,
    )
    assert result is None


@given(age=st.integers(0, 10**6), max_age=st.integers(0, 10**6))
def test_admissible_iff_within_max(age: int, max_age: int) -> None:
    """A known age is admissible iff it does not exceed the injected max age (§8 210)."""
    assert snapshot_age_admissible(age, max_age) is (age <= max_age)


def test_unknown_age_or_max_is_inadmissible() -> None:
    """UNKNOWN age or unestablished max age is inadmissible (fail-closed, §8 210)."""
    assert snapshot_age_admissible(None, 1000) is False
    assert snapshot_age_admissible(100, None) is False


# ---- v1.2 MAJOR: a negative additive term must not shrink cross-host age ----


@given(term=st.sampled_from(_TERMS), neg=st.integers(-(10**6), -1))
def test_negative_additive_term_is_unknown(term: str, neg: int) -> None:
    """A negative additive term => None; it must NOT shrink the cross-host age bound."""
    assert _age(**{term: neg}) is None


# ---- MEDIUM-2: anchor_valid composition wrapper closes the injected-bool seam ----


def _continuity(**overrides: object) -> TimeContinuityIdentity:
    base = {
        "host_or_runtime_id": "h1",
        "boot_id": "b1",
        "process_id": "p1",
        "monotonic_anchor_id": "consumer-c1",
        "monotonic_anchor_value": 1000,
    }
    base.update(overrides)
    return TimeContinuityIdentity(**base)  # type: ignore[arg-type]


def test_composition_wrapper_matches_manual_valid_case() -> None:
    """The wrapper derives consumer_anchor_valid=True for a continuous consumer anchor."""
    result = effective_snapshot_age_bound_from_continuity(
        issue_time_snapshot(),
        _VALID_ANCHOR,
        consumer_continuity_now=_continuity(monotonic_anchor_value=1500),
        consumer_anchor=_continuity(monotonic_anchor_value=1000),
        suspension_ms=0,
        max_suspension_ms=2000,
        issuer_signed_age=10,
        issuer_age_uncertainty=5,
        transport_bound=2,
        queue_bound=3,
        conversion_bound=1,
        consumer_elapsed_since_receipt=4,
    )
    assert result == 10 + 5 + 2 + 3 + 1 + 4


def test_composition_wrapper_rejects_consumer_restart() -> None:
    """A consumer restart (changed boot_id) => invalid anchor => UNKNOWN, seam not skippable."""
    result = effective_snapshot_age_bound_from_continuity(
        issue_time_snapshot(),
        _VALID_ANCHOR,
        consumer_continuity_now=_continuity(boot_id="b2"),
        consumer_anchor=_continuity(),
        suspension_ms=0,
        max_suspension_ms=2000,
        issuer_signed_age=10,
        issuer_age_uncertainty=5,
        transport_bound=2,
        queue_bound=3,
        conversion_bound=1,
        consumer_elapsed_since_receipt=4,
    )
    assert result is None
