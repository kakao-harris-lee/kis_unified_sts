"""§7.2-4 — the single VALID gate, its ∅ floor, and its polarity (design #32 §2.2/§6, MINOR-4).

One definition, three sources, positive membership::

    worst( admitted_field_state(admission), observation.field_state, ⋃ matching evaluations ) == VALID

Two properties carry the weight and each has its own mutation canary here:

* **the ∅ floor.** ``tos.capsule.worst`` aggregates an *empty* iterable to ``VALID`` — the lattice
  identity (``field_state.py:70-87``, whose own docstring says callers must supply an explicit
  ``UNKNOWN`` floor). Without the floor, a field with **no** evaluation would pass the gate
  vacuously. The floor is what makes silence restrictive.
* **the polarity.** The gate admits on ``is VALID``, never on ``!= INVALID``. Under a ``!= INVALID``
  reading, ``UNKNOWN`` / ``STALE`` / ``CONFLICTED`` would all admit — the negative-gate regression
  this series has met repeatedly (#18/#22/#23). The parametrized sweep below fails under that
  mutation for three of the four non-VALID states.

Regime tag: authoring evidence only; closes no EV (design #32 §1.1).
"""

from __future__ import annotations

import pytest
from tos.capsule import AdmissionResult, FieldState
from tos.capsule.predicates import admitted_field_state
from tos.marketfeed import (
    ValueRejectionReason,
    ValueViewDisposition,
    publish_context_value_view,
    value_field_state,
)

from ._marketfeed_fixtures import (
    BAR_ONE_AS_OF,
    CLOSE_BAR_ONE,
    SCHEME,
    candidate,
    evaluation,
    issue_capsule,
    issue_snapshot,
    observation,
    preimage,
)

_NON_VALID_STATES = (
    FieldState.UNKNOWN,
    FieldState.STALE,
    FieldState.CONFLICTED,
    FieldState.INVALID,
)


def _observation(**kwargs):
    """A digest-honest observation of ``close``."""
    payload = preimage(close=CLOSE_BAR_ONE)
    return payload, observation(
        raw_event_id="raw-1", payload=payload, as_of=BAR_ONE_AS_OF, **kwargs
    )


# ---------------------------------------------------------------------------
# The gate as a function (design #32 §2.2)
# ---------------------------------------------------------------------------


def test_the_gate_is_valid_only_when_all_three_sources_are_valid() -> None:
    """(§2.2) Admission VALID + observation VALID + a VALID evaluation naming the key."""
    _, obs = _observation()
    assert value_field_state(obs, "close", (evaluation("close"),)) is FieldState.VALID


def test_an_unevaluated_field_is_unknown_not_vacuously_valid() -> None:
    """(§2.2 ★ ∅ floor) No evaluation names the key ⇒ explicit UNKNOWN, never the empty identity.

    Removing the floor makes ``worst`` return ``VALID`` here (its documented empty-set behaviour),
    which is the vacuous-validity fail-open. This assertion is that mutation's canary.
    """
    _, obs = _observation()
    assert value_field_state(obs, "close", ()) is FieldState.UNKNOWN
    assert value_field_state(obs, "close", (evaluation("some_other_field"),)) is FieldState.UNKNOWN


@pytest.mark.parametrize("state", _NON_VALID_STATES)
def test_a_non_valid_evaluation_dominates(state: FieldState) -> None:
    """(§2.2) Any non-VALID evaluation state propagates — aggregation is monotone toward restriction."""
    _, obs = _observation()
    assert value_field_state(obs, "close", (evaluation("close", state),)) is state


@pytest.mark.parametrize("state", _NON_VALID_STATES)
def test_a_non_valid_observation_state_dominates(state: FieldState) -> None:
    """(§2.2) The observation's own recorded state is one of the three aggregated sources."""
    _, obs = _observation(field_state=state)
    assert value_field_state(obs, "close", (evaluation("close"),)) is state


@pytest.mark.parametrize(
    "admission, expected",
    [
        (AdmissionResult.ADMITTED, FieldState.VALID),
        (AdmissionResult.UNCERTAIN, FieldState.UNKNOWN),
        (AdmissionResult.REJECTED, FieldState.INVALID),
    ],
)
def test_the_admission_result_enters_through_the_shipped_mapping(
    admission: AdmissionResult, expected: FieldState
) -> None:
    """(§2.2, §12.1 REUSE) Admission enters via ``admitted_field_state``, never re-authored here."""
    _, obs = _observation(admission=admission)
    assert admitted_field_state(admission) is expected
    assert value_field_state(obs, "close", (evaluation("close"),)) is expected


def test_the_worst_of_several_matching_evaluations_wins() -> None:
    """(§2.2) Every evaluation naming the key participates; the most restrictive decides."""
    _, obs = _observation()
    state = value_field_state(
        obs,
        "close",
        (evaluation("close"), evaluation("close", FieldState.CONFLICTED), evaluation("close")),
    )
    assert state is FieldState.CONFLICTED


# ---------------------------------------------------------------------------
# The gate as a publication decision — polarity (design #32 §6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("state", _NON_VALID_STATES)
def test_only_valid_publishes_a_value(state: FieldState) -> None:
    """(§2.2/§6 ★ polarity) ``!= INVALID`` would admit UNKNOWN/STALE/CONFLICTED; ``is VALID`` does not."""
    payload, obs = _observation()
    snapshot = issue_snapshot(
        observations=(obs,), field_evaluations=(evaluation("close", state),)
    )
    capsule = issue_capsule(snapshot)
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=snapshot,
        candidates=(candidate("close", "raw-1", payload),),
        scheme=SCHEME,
    )
    assert resolution.values == ()
    assert resolution.disposition is ValueViewDisposition.EXPLICIT_EMPTY
    assert {entry.reason for entry in resolution.rejected} == {
        ValueRejectionReason.FIELD_STATE_NOT_VALID
    }


def test_an_unevaluated_field_is_not_published() -> None:
    """(§2.2 ★ ∅ floor, publication form) Vacuous validity does not reach the environment."""
    payload, obs = _observation()
    snapshot = issue_snapshot(observations=(obs,), field_evaluations=())
    capsule = issue_capsule(snapshot)
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=snapshot,
        candidates=(candidate("close", "raw-1", payload),),
        scheme=SCHEME,
    )
    assert resolution.values == ()
    assert {entry.reason for entry in resolution.rejected} == {
        ValueRejectionReason.FIELD_STATE_NOT_VALID
    }


def test_a_field_evaluation_for_a_different_key_does_not_govern_this_one() -> None:
    """(§2.4) The key↔``field_ref`` correspondence is exact, not "some evaluation exists"."""
    payload = preimage(close=CLOSE_BAR_ONE, session="REGULAR")
    obs = observation(raw_event_id="raw-1", payload=payload, as_of=BAR_ONE_AS_OF)
    snapshot = issue_snapshot(observations=(obs,), field_evaluations=(evaluation("close"),))
    capsule = issue_capsule(snapshot)
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=snapshot,
        candidates=(candidate("close", "raw-1", payload), candidate("session", "raw-1", payload)),
        scheme=SCHEME,
    )
    assert {value.field_key for value in resolution.values} == {"close"}
    assert {entry.field_key for entry in resolution.rejected} == {"session"}
