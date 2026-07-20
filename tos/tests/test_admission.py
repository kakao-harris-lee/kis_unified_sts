"""CII-EV-003 admission mismatch reject + CII-EV-002 predicate-only continuity.

Design §2.2 admission is a pure function over one observation and an injected
policy expectation. A concrete unit/scale/mapping mismatch rejects (-> INVALID);
an expected-but-missing field is uncertain (-> UNKNOWN); a clean match is
admitted (-> VALID candidate). CII-EV-002 is predicate-only at L1 (design §7).
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.capsule.field_state import FieldState
from tos.capsule.observation import (
    Admission,
    AdmissionResult,
    Continuity,
    Mapping,
    Observation,
    SourceIdentity,
)
from tos.capsule.predicates import (
    AdmissionExpectation,
    admitted_field_state,
    compute_admission,
    continuity_admissible,
)

_FIELD_TO_MAPPING = ("unit", "scale", "multiplier", "sign", "venue")


@given(
    field=st.sampled_from(_FIELD_TO_MAPPING),
    expected=st.text(min_size=1, max_size=5),
    observed=st.text(min_size=1, max_size=5),
)
def test_mapping_mismatch_is_rejected(field: str, expected: str, observed: str) -> None:
    """A concrete unit/scale/mapping mismatch rejects -> INVALID (CII-EV-003)."""
    if expected == observed:
        return
    obs = Observation(mapping=Mapping(**{field: observed}))
    expectation = AdmissionExpectation(**{field: expected})
    result, reasons = compute_admission(obs, expectation)
    assert result == AdmissionResult.REJECTED
    assert f"{field}_mismatch" in reasons
    assert admitted_field_state(result) == FieldState.INVALID


@given(field=st.sampled_from(_FIELD_TO_MAPPING), value=st.text(min_size=1, max_size=5))
def test_exact_match_is_admitted(field: str, value: str) -> None:
    """A clean match with no gap is admitted -> VALID candidate."""
    obs = Observation(
        mapping=Mapping(**{field: value}),
        continuity=Continuity(continuity_gap=False),
    )
    expectation = AdmissionExpectation(**{field: value})
    result, reasons = compute_admission(obs, expectation)
    assert result == AdmissionResult.ADMITTED
    assert reasons == ()
    assert admitted_field_state(result) == FieldState.VALID


@given(
    field=st.sampled_from(_FIELD_TO_MAPPING), expected=st.text(min_size=1, max_size=5)
)
def test_missing_observed_is_uncertain(field: str, expected: str) -> None:
    """An expected-but-unverifiable field is uncertain -> UNKNOWN (fail-closed)."""
    obs = Observation(mapping=Mapping())  # observed field is None
    expectation = AdmissionExpectation(**{field: expected})
    result, _ = compute_admission(obs, expectation)
    assert result == AdmissionResult.UNCERTAIN
    assert admitted_field_state(result) == FieldState.UNKNOWN


@given(gap=st.booleans())
def test_continuity_gap_rejects(gap: bool) -> None:
    """A declared continuity gap always rejects (never inferred away, §2.2)."""
    obs = Observation(continuity=Continuity(continuity_gap=gap))
    result, reasons = compute_admission(obs, AdmissionExpectation())
    if gap:
        assert result == AdmissionResult.REJECTED
        assert "continuity_gap" in reasons
    else:
        assert result == AdmissionResult.ADMITTED


def test_out_of_trust_endpoint_rejects() -> None:
    """An endpoint outside the trusted set rejects."""
    obs = Observation(source=SourceIdentity(endpoint="evil"))
    expectation = AdmissionExpectation(trusted_endpoints=("good",))
    result, reasons = compute_admission(obs, expectation)
    assert result == AdmissionResult.REJECTED
    assert "out_of_trust_endpoint" in reasons


# ---- CII-EV-002 predicate-only ---------------------------------------------


@given(gap=st.booleans(), result=st.sampled_from(list(AdmissionResult)))
def test_continuity_admissible_predicate(gap: bool, result: AdmissionResult) -> None:
    """continuity_admissible fails closed on a gap or a non-admitted result (§7)."""
    obs = Observation(
        continuity=Continuity(continuity_gap=gap), admission=Admission(result=result)
    )
    expected = (not gap) and result == AdmissionResult.ADMITTED
    assert continuity_admissible(obs) is expected
