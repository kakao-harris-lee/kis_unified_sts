"""§7.2-1 — value ⟺ covered ``payload_digest`` binding, the side-channel seal (design #32 §2.3).

RFC-004 §9:244 forbids a Critical Input arriving "by unattributed fetch or side channel". The
structural form of that prohibition is: a published value must digest back to the very
``raw.payload_digest`` the snapshot-covered observation attests. These tests exercise the seal from
both directions — the honest payload passes, and every way of detaching the value from its
provenance is refused with a *named* reason.

Regime tag: authoring evidence only; closes no EV (design #32 §1.1).
"""

from __future__ import annotations

import pytest
from tos.capsule import AdmissionResult, FieldState
from tos.capsule.observation import ObservationTime, RawRef
from tos.marketfeed import (
    ValueRejectionReason,
    ValueViewDisposition,
    publish_context_value_view,
    view_digest_matches,
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
    one_bar,
    payload_digest_of,
    preimage,
)


def _publish(capsule, snapshot, candidates):
    """Run the publication gate."""
    return publish_context_value_view(
        capsule=capsule, snapshot=snapshot, candidates=candidates, scheme=SCHEME
    )


def _reasons(resolution) -> set[ValueRejectionReason]:
    """The set of named rejection reasons in a resolution."""
    return {entry.reason for entry in resolution.rejected}


# ---------------------------------------------------------------------------
# The binding holds
# ---------------------------------------------------------------------------


def test_an_honest_payload_publishes_its_values() -> None:
    """(§2.3) A value whose preimage digests to the observation's digest reaches the view."""
    resolution = _publish(*one_bar())
    assert resolution.disposition is ValueViewDisposition.RESOLVED
    assert resolution.rejected == ()
    assert {value.field_key for value in resolution.values} == {"close", "session"}


def test_every_published_value_carries_its_observations_provenance() -> None:
    """(§2.2/§2.3) ``payload_digest`` / ``as_of`` / ``observation_ref`` are read off the snapshot."""
    capsule, snapshot, candidates = one_bar()
    resolution = _publish(capsule, snapshot, candidates)
    attested = snapshot.observations[0]
    for value in resolution.values:
        assert value.payload_digest == attested.raw.payload_digest
        assert value.as_of == attested.time.source_event_time
        assert value.observation_ref == attested.raw.raw_event_id


def test_the_view_digest_is_the_digest_of_its_own_content() -> None:
    """(§2.2) The recorded view digest re-derives from the view's own values."""
    resolution = _publish(*one_bar())
    assert resolution.view is not None
    assert view_digest_matches(resolution.view, SCHEME) is True


# ---------------------------------------------------------------------------
# Detaching the value from its provenance is refused (the side-channel mutations)
# ---------------------------------------------------------------------------


def test_a_forged_value_no_longer_digests_to_the_attested_payload() -> None:
    """(§2.3 ★ side channel) Changing the value changes the preimage digest — refused.

    This is the seal in its purest form: the producer keeps the observation exactly as the snapshot
    covers it and merely edits the number. The recomputed preimage digest no longer matches, so the
    value is not the value that observation attests, and it never reaches the environment.
    """
    honest = preimage(close=CLOSE_BAR_ONE, session="REGULAR")
    obs = observation(raw_event_id="raw-1", payload=honest, as_of=BAR_ONE_AS_OF)
    snapshot = issue_snapshot(observations=(obs,), field_evaluations=(evaluation("close"),))
    capsule = issue_capsule(snapshot)

    forged = preimage(close=CLOSE_BAR_ONE + 999_999, session="REGULAR")
    resolution = _publish(capsule, snapshot, (candidate("close", "raw-1", forged),))

    assert resolution.disposition is ValueViewDisposition.EXPLICIT_EMPTY
    assert _reasons(resolution) == {ValueRejectionReason.DIGEST_MISMATCH}
    assert resolution.values == ()


def test_a_value_absent_from_the_attested_payload_is_refused() -> None:
    """(§2.3) A field_key the covered payload does not carry has no attributable value."""
    capsule, snapshot, _ = one_bar()
    payload = preimage(close=CLOSE_BAR_ONE, session="REGULAR")
    resolution = _publish(capsule, snapshot, (candidate("lower_band", "raw-1", payload),))
    assert _reasons(resolution) == {ValueRejectionReason.VALUE_NOT_IN_PAYLOAD}


def test_a_value_attributed_to_no_observation_is_refused() -> None:
    """(§2.3) An ``observation_ref`` naming nothing in the snapshot attributes nothing."""
    capsule, snapshot, _ = one_bar()
    payload = preimage(close=CLOSE_BAR_ONE, session="REGULAR")
    resolution = _publish(capsule, snapshot, (candidate("close", "raw-absent", payload),))
    assert _reasons(resolution) == {ValueRejectionReason.OBSERVATION_NOT_FOUND}


def test_an_observation_without_a_payload_digest_publishes_nothing() -> None:
    """(§2.3/§4.2) No provenance pointer means no binding to verify — fail-closed."""
    payload = preimage(close=CLOSE_BAR_ONE)
    obs = observation(raw_event_id="raw-1", payload=payload, as_of=BAR_ONE_AS_OF).model_copy(
        update={"raw": RawRef(raw_event_id="raw-1", payload_digest=None)}
    )
    snapshot = issue_snapshot(observations=(obs,), field_evaluations=(evaluation("close"),))
    capsule = issue_capsule(snapshot)
    resolution = _publish(capsule, snapshot, (candidate("close", "raw-1", payload),))
    assert _reasons(resolution) == {ValueRejectionReason.PAYLOAD_DIGEST_ABSENT}


def test_an_observation_without_an_as_of_publishes_nothing() -> None:
    """(§4.2) A missing ``source_event_time`` removes the Validity-Window anchor — fail-closed."""
    payload = preimage(close=CLOSE_BAR_ONE)
    obs = observation(raw_event_id="raw-1", payload=payload, as_of=BAR_ONE_AS_OF).model_copy(
        update={"time": ObservationTime(source_event_time=None)}
    )
    snapshot = issue_snapshot(observations=(obs,), field_evaluations=(evaluation("close"),))
    capsule = issue_capsule(snapshot)
    resolution = _publish(capsule, snapshot, (candidate("close", "raw-1", payload),))
    assert _reasons(resolution) == {ValueRejectionReason.AS_OF_ABSENT}


def test_two_observations_under_one_identity_are_ambiguous_not_arbitrary() -> None:
    """(§2.3/§6) A duplicated raw-event id attributes nothing — neither one is silently picked."""
    payload = preimage(close=CLOSE_BAR_ONE)
    other = preimage(close=CLOSE_BAR_ONE + 1)
    snapshot = issue_snapshot(
        observations=(
            observation(raw_event_id="raw-1", payload=payload, as_of=BAR_ONE_AS_OF),
            observation(raw_event_id="raw-1", payload=other, as_of=BAR_ONE_AS_OF),
        ),
        field_evaluations=(evaluation("close"),),
    )
    capsule = issue_capsule(snapshot)
    resolution = _publish(capsule, snapshot, (candidate("close", "raw-1", payload),))
    assert _reasons(resolution) == {ValueRejectionReason.OBSERVATION_AMBIGUOUS}


# ---------------------------------------------------------------------------
# Disagreement is never folded (§6)
# ---------------------------------------------------------------------------


def test_two_admitted_observations_of_one_field_are_both_refused() -> None:
    """(§6, ADR-002-018 §11:311) Source disagreement is not averaged, voted, or arbitrarily picked."""
    left = preimage(close=CLOSE_BAR_ONE)
    right = preimage(close=CLOSE_BAR_ONE + 250)
    snapshot = issue_snapshot(
        observations=(
            observation(raw_event_id="raw-a", payload=left, as_of=BAR_ONE_AS_OF),
            observation(raw_event_id="raw-b", payload=right, as_of=BAR_ONE_AS_OF),
        ),
        field_evaluations=(evaluation("close"),),
    )
    capsule = issue_capsule(snapshot)
    resolution = _publish(
        capsule,
        snapshot,
        (candidate("close", "raw-a", left), candidate("close", "raw-b", right)),
    )
    assert resolution.disposition is ValueViewDisposition.EXPLICIT_EMPTY
    assert _reasons(resolution) == {ValueRejectionReason.DUPLICATE_FIELD_KEY}
    assert len(resolution.rejected) == 2, "both contenders are refused, not just the loser"
    assert resolution.values == ()


def test_a_disagreement_does_not_suppress_the_unrelated_fields() -> None:
    """(§6, ∅ discipline) Refusing a contested key leaves the uncontested ones published."""
    left = preimage(close=CLOSE_BAR_ONE, session="REGULAR")
    right = preimage(close=CLOSE_BAR_ONE + 250)
    snapshot = issue_snapshot(
        observations=(
            observation(raw_event_id="raw-a", payload=left, as_of=BAR_ONE_AS_OF),
            observation(raw_event_id="raw-b", payload=right, as_of=BAR_ONE_AS_OF),
        ),
        field_evaluations=(evaluation("close"), evaluation("session")),
    )
    capsule = issue_capsule(snapshot)
    resolution = _publish(
        capsule,
        snapshot,
        (
            candidate("close", "raw-a", left),
            candidate("close", "raw-b", right),
            candidate("session", "raw-a", left),
        ),
    )
    assert {value.field_key for value in resolution.values} == {"session"}
    assert _reasons(resolution) == {ValueRejectionReason.DUPLICATE_FIELD_KEY}


# ---------------------------------------------------------------------------
# The producer cannot self-report its way in (구조 파생 > 자기신고)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "admission, observed_state",
    [
        (AdmissionResult.REJECTED, FieldState.VALID),
        (AdmissionResult.UNCERTAIN, FieldState.VALID),
        (AdmissionResult.ADMITTED, FieldState.STALE),
    ],
)
def test_a_correct_digest_does_not_rescue_a_non_admitted_observation(
    admission: AdmissionResult, observed_state: FieldState
) -> None:
    """(§2.2/§2.3) The binding is necessary, never sufficient — the VALID gate still runs."""
    payload = preimage(close=CLOSE_BAR_ONE)
    obs = observation(
        raw_event_id="raw-1",
        payload=payload,
        as_of=BAR_ONE_AS_OF,
        admission=admission,
        field_state=observed_state,
    )
    snapshot = issue_snapshot(observations=(obs,), field_evaluations=(evaluation("close"),))
    capsule = issue_capsule(snapshot)
    resolution = _publish(capsule, snapshot, (candidate("close", "raw-1", payload),))
    assert payload_digest_of(payload) == obs.raw.payload_digest, "the digest itself is honest"
    assert _reasons(resolution) == {ValueRejectionReason.FIELD_STATE_NOT_VALID}
