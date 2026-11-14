"""§7.2-2 — UNKNOWN at the send boundary is restrictive and releases nothing (design #31 §4.2 rule 3)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.canonical import ArtifactIntegrityError
from tos.engine import (
    PROJECTION_ORDER,
    PROJECTION_RANK,
    QUARANTINE_RESOLUTION_EDGES,
    EgressKnowledge,
    EgressResultKind,
    EgressResultPayload,
    EngineEvent,
    EventKind,
    HaltReason,
    InstrumentKey,
    ProvisionalReservation,
    ProvisionalReservationLedger,
    ResultDisposition,
    knowledge_for_result,
)
from tos.engine.state import _RESULT_TRANSITIONS
from tos.rcl import CapacityState

from ._engine_fixtures import (
    PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE,
    RecordingTransmit,
    build_core,
    decision_tick,
    instrument_key,
    ordering,
)


def _outstanding(
    ledger: ProvisionalReservationLedger, key: InstrumentKey
) -> ProvisionalReservation:
    """``ledger.outstanding(key)``, asserted present."""
    reservation = ledger.outstanding(key)
    assert reservation is not None
    return reservation


def _sent_core():
    """A core that has completed one flow, so a reservation is projected POTENTIALLY_LIVE."""
    transmit = RecordingTransmit()
    core, sink = build_core(transmit=transmit)
    result = core.handle(decision_tick(sequence=1))
    assert result.flow is not None and result.flow.handed_off is True
    assert result.flow.attempt is not None
    return core, sink, transmit, result.flow.attempt.attempt_id


def _egress_event(
    kind: EgressResultKind, attempt_id: str, *, sequence: int = 2, **fills
):
    """Build an ``EGRESS_RESULT`` event for the projected attempt."""
    return EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=instrument_key(),
            attempt_id=attempt_id,
            kind=kind,
            reference=ordering(sequence),
            **fills,
        ),
    )


@pytest.mark.parametrize("kind", [EgressResultKind.UNKNOWN, EgressResultKind.TIMEOUT])
def test_unknown_and_timeout_quarantine_the_reservation(kind) -> None:
    """([KW2b-#2]) UNKNOWN / timeout force the capacity projection into QUARANTINED_UNKNOWN."""
    core, _, _, attempt_id = _sent_core()
    result = core.handle(_egress_event(kind, attempt_id))

    assert result.halt_reason is None
    assert result.reservation is not None
    assert result.reservation.capacity_state is CapacityState.QUARANTINED_UNKNOWN
    assert result.reservation.knowledge is EgressKnowledge.UNKNOWN


@pytest.mark.parametrize("kind", [EgressResultKind.UNKNOWN, EgressResultKind.TIMEOUT])
def test_unknown_and_timeout_are_not_rejections(kind) -> None:
    """(§7.2-2; RFC-005 §11:325) UNKNOWN is never folded into REJECTED knowledge."""
    assert knowledge_for_result(kind) is EgressKnowledge.UNKNOWN
    assert knowledge_for_result(kind) is not EgressKnowledge.REJECTED


def test_unknown_causes_no_blind_resubmission() -> None:
    """(§7.2-2; RFC-002 §9.1:574) After an UNKNOWN the core sends nothing further by itself."""
    core, _, transmit, attempt_id = _sent_core()
    assert len(transmit.attempts) == 1
    core.handle(_egress_event(EgressResultKind.UNKNOWN, attempt_id))
    assert (
        len(transmit.attempts) == 1
    ), "an UNKNOWN result must not trigger a resubmission"


def test_a_second_tick_after_unknown_is_still_denied_at_the_capacity_stage() -> None:
    """(§7.2-2 + §7.2-9) An unresolved UNKNOWN keeps the scope occupied — no retry exposure."""
    core, _, transmit, attempt_id = _sent_core()
    core.handle(_egress_event(EgressResultKind.UNKNOWN, attempt_id))
    again = core.handle(decision_tick(sequence=3))
    assert again.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
    assert len(transmit.attempts) == 1


@pytest.mark.parametrize(
    ("kind", "fills"),
    [
        (EgressResultKind.ACK, {}),
        (EgressResultKind.UNKNOWN, {}),
        (EgressResultKind.TIMEOUT, {}),
        (EgressResultKind.REJECT, {}),
        (EgressResultKind.CANCEL_ACK, {}),
        (EgressResultKind.EXPIRED, {}),
        (
            EgressResultKind.PARTIAL_FILL,
            {"filled_quantity": Decimal("1"), "remaining_quantity": Decimal("1")},
        ),
        (
            EgressResultKind.FULL_FILL,
            {"filled_quantity": Decimal("2"), "remaining_quantity": Decimal("0")},
        ),
    ],
)
def test_no_egress_result_ever_releases_the_scope(kind, fills) -> None:
    """(§4.4; RFC-002 §9.1:557-558) **No** result frees the scope — release is the RCL's act."""
    core, _, _, attempt_id = _sent_core()
    core.handle(_egress_event(kind, attempt_id, **fills))
    assert core.ledger.outstanding(instrument_key()) is not None
    assert core.ledger.admits_new_exposure(instrument_key()) is False


def test_the_projection_has_no_free_form_release_path_under_any_other_spelling() -> (
    None
):
    """(§4.4 structural seal; kernel round #3 §2 decision 5) ``release`` now exists — a single,"""
    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    assert hasattr(ledger, "release")
    for forbidden in (
        "free",
        "clear",
        "reset",
        "remove",
        "release_reservation",
    ):
        assert not hasattr(ledger, forbidden), (
            f"ProvisionalReservationLedger.{forbidden} must not exist — releasing capacity is the "
            "Risk Capacity Ledger's act and a producer-local counter creates no headroom "
            "(RFC-002 §9.1:557-558); the ONE gated exception is release() itself"
        )


def test_a_result_for_an_unknown_attempt_is_refused() -> None:
    """(§2.1(ii); Phase 3 A-K-2) A result naming another attempt transitions nothing."""
    core, _, _, _ = _sent_core()
    before = core.ledger.outstanding(instrument_key())
    result = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            "attempt-someone-else",
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert result.halt_reason is HaltReason.RESULT_UNMATCHED
    assert result.result_disposition is ResultDisposition.MISMATCHED_ATTEMPT
    assert core.ledger.outstanding(instrument_key()).model_dump() == before.model_dump()
    assert core.ledger.outstanding(instrument_key()) == before


def test_a_result_with_no_projected_reservation_is_refused() -> None:
    """(§2.2; Phase 3 A-K-2) An egress result is not a licence to create a reservation."""
    core, _ = build_core(transmit=RecordingTransmit())
    result = core.handle(
        _egress_event(EgressResultKind.ACK, "attempt-unknown", sequence=1)
    )
    assert result.halt_reason is HaltReason.RESULT_UNMATCHED
    assert result.result_disposition is ResultDisposition.ORPHAN_NO_RESERVATION
    assert result.reservation is None
    assert core.ledger.outstanding(instrument_key()) is None


def test_a_duplicate_result_is_recorded_as_duplicate_not_reapplied() -> None:
    """(Phase 3 A-K-2) The identical result applied twice is DUPLICATE the second time."""
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert first.halt_reason is None
    assert first.result_disposition is ResultDisposition.APPLIED
    after_first = core.ledger.outstanding(instrument_key())

    second = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.DUPLICATE
    assert (
        core.ledger.outstanding(instrument_key()).model_dump()
        == after_first.model_dump()
    )


def test_duplicate_is_keyed_on_broker_execution_id_not_the_reference_coordinate() -> (
    None
):
    """([K2-p3-#6] finding #6; ADR-002-002 §15.3:725) DUPLICATE keys on broker identity."""
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
            broker_execution_id="broker-exec-1",
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
            broker_execution_id="broker-exec-1",
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.DUPLICATE


def test_different_broker_execution_ids_are_both_applied() -> None:
    """([K2-p3-#6]) Two distinct broker execution ids are two distinct facts, not a duplicate."""
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
            broker_execution_id="broker-exec-1",
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
            broker_execution_id="broker-exec-2",
        )
    )
    assert second.halt_reason is None
    assert second.result_disposition is ResultDisposition.APPLIED


def test_timeouts_with_no_broker_id_dedup_as_a_runtime_local_replay_guard() -> None:
    """([K2-p3-#6]) With no broker id, the signature still dedups a byte-identical resend."""
    core, _, _, attempt_id = _sent_core()
    first = core.handle(_egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=2))
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=3)
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.DUPLICATE


def test_a_late_fill_after_timeout_on_the_same_attempt_is_applied() -> None:
    """(Phase 3 A-K-2; ADR-002-002 §15.2 'later valid fill accepted'; [KW2b-#2]) TIMEOUT then"""
    core, _, _, attempt_id = _sent_core()
    timeout_result = core.handle(
        _egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=2)
    )
    assert timeout_result.halt_reason is None
    assert timeout_result.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )

    fill_result = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert fill_result.halt_reason is None
    assert fill_result.result_disposition is ResultDisposition.APPLIED
    reservation = core.ledger.outstanding(instrument_key())
    assert reservation.capacity_state is CapacityState.POSITION_CONSUMED
    assert reservation.knowledge is EgressKnowledge.FILLED
    assert core.ledger.admits_new_exposure(instrument_key()) is False


def test_a_late_fill_after_reject_does_not_crash_and_is_recorded_non_monotonic() -> (
    None
):
    """([K2-p3-#4] finding #4; ADR-002-002 §15.2) REJECT -> late FULL_FILL is not a crash."""
    core, _, _, attempt_id = _sent_core()
    rejected = core.handle(
        _egress_event(EgressResultKind.REJECT, attempt_id, sequence=2)
    )
    assert rejected.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.RELEASE_PENDING_PROOF
    )

    late_fill = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert late_fill.halt_reason is HaltReason.RESULT_UNMATCHED
    assert late_fill.result_disposition is ResultDisposition.NON_MONOTONIC_PROJECTION
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.RELEASE_PENDING_PROOF
    )


def test_a_late_partial_fill_after_full_fill_does_not_crash_and_is_recorded_non_monotonic() -> (
    None
):
    """([K2-p3-#4] finding #4) FULL_FILL -> late PARTIAL_FILL is not a crash either."""
    core, _, _, attempt_id = _sent_core()
    full = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert full.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    )

    late_partial = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("1"),
        )
    )
    assert late_partial.halt_reason is HaltReason.RESULT_UNMATCHED
    assert late_partial.result_disposition is ResultDisposition.NON_MONOTONIC_PROJECTION
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    )


def test_a_regressing_filled_quantity_is_refused_not_applied() -> None:
    """([K2-p3-#5] finding #5; ADR-002-002 §15.1:710) Filled quantity may never go down."""
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding_consumed_magnitude(instrument_key()) == Decimal("4")

    second = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("9"),
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.QUANTITY_REGRESSION
    assert core.ledger.outstanding_consumed_magnitude(instrument_key()) == Decimal("4")


def test_a_growing_remaining_quantity_is_refused_not_applied() -> None:
    """(Phase 3 wave 2 N2; ADR-002-002 §15.1) ``remaining_quantity`` may never grow."""
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("60"),
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.QUANTITY_REGRESSION
    assert core.ledger.outstanding(instrument_key()).remaining_quantity == Decimal("6")
    assert core.ledger.outstanding(instrument_key()).filled_quantity == Decimal("4")


def test_a_remaining_quantity_shrink_unmatched_by_a_filled_increase_is_refused() -> (
    None
):
    """(Phase 3 wave 2 N2; CPL-2/CPL-4) ``remaining_quantity`` may not shrink for free."""
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("2"),
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.QUANTITY_REGRESSION
    assert core.ledger.outstanding(instrument_key()).remaining_quantity == Decimal("6")


def test_a_remaining_quantity_shrink_fully_matched_by_filled_growth_is_applied() -> (
    None
):
    """(Phase 3 wave 2 N2, the non-regressing control) Ordinary partial-fill progression still works."""
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("6"),
            remaining_quantity=Decimal("4"),
        )
    )
    assert second.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).remaining_quantity == Decimal("4")
    assert core.ledger.outstanding(instrument_key()).filled_quantity == Decimal("6")


def test_an_inflating_authorized_total_is_refused_not_applied() -> None:
    """([KW2b-#10]; Phase 3 wave 2 review finding #10; ADR-002-002 §15.1:710) ``filled`` may not"""
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("6"),
            remaining_quantity=Decimal("5"),
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.QUANTITY_REGRESSION
    assert core.ledger.outstanding(instrument_key()).filled_quantity == Decimal("4")
    assert core.ledger.outstanding(instrument_key()).remaining_quantity == Decimal("6")


def test_apply_egress_result_never_raises_artifact_integrity_error() -> None:
    """([K2-p3-#4] finding #4) The egress-result path never raises — only records a disposition."""
    core, _, _, attempt_id = _sent_core()
    core.handle(_egress_event(EgressResultKind.REJECT, attempt_id, sequence=2))
    result = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert result.result_disposition is ResultDisposition.NON_MONOTONIC_PROJECTION


def test_the_six_dispositions_are_exhaustive_and_distinguishable() -> None:
    """(Phase 3 A-K-2, extended [K2-p3-#4/#5]) All six :class:`ResultDisposition` members reach."""
    core, _, _, attempt_id = _sent_core()

    orphan_core, _ = build_core(transmit=RecordingTransmit())
    orphan = orphan_core.handle(
        _egress_event(EgressResultKind.ACK, "attempt-x", sequence=1)
    )
    assert orphan.result_disposition is ResultDisposition.ORPHAN_NO_RESERVATION

    mismatched = core.handle(
        _egress_event(EgressResultKind.ACK, "attempt-someone-else", sequence=2)
    )
    assert mismatched.result_disposition is ResultDisposition.MISMATCHED_ATTEMPT

    applied = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=3))
    assert applied.result_disposition is ResultDisposition.APPLIED

    duplicate = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=3))
    assert duplicate.result_disposition is ResultDisposition.DUPLICATE

    non_monotonic_core, _, _, non_monotonic_attempt_id = _sent_core()
    non_monotonic_core.handle(
        _egress_event(EgressResultKind.REJECT, non_monotonic_attempt_id, sequence=2)
    )
    non_monotonic = non_monotonic_core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            non_monotonic_attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert (
        non_monotonic.result_disposition is ResultDisposition.NON_MONOTONIC_PROJECTION
    )

    regression_core, _, _, regression_attempt_id = _sent_core()
    regression_core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            regression_attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    regression = regression_core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            regression_attempt_id,
            sequence=3,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("9"),
        )
    )
    assert regression.result_disposition is ResultDisposition.QUANTITY_REGRESSION

    assert {
        orphan.result_disposition,
        mismatched.result_disposition,
        applied.result_disposition,
        duplicate.result_disposition,
        non_monotonic.result_disposition,
        regression.result_disposition,
    } == set(ResultDisposition)


def test_the_projection_never_revives_to_a_less_consumed_state() -> None:
    """(§2.4 non-revival) A later result may not move the projection backwards."""
    core, _, _, attempt_id = _sent_core()
    core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    )
    core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=3))
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    )


def test_an_unknown_after_settlement_quarantines_forward_not_backward() -> None:
    """([KW2b-#2]) UNKNOWN after a definite settlement is a forward move into quarantine."""
    core, _, _, attempt_id = _sent_core()
    core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    )

    result = core.handle(
        _egress_event(EgressResultKind.UNKNOWN, attempt_id, sequence=3)
    )
    assert result.halt_reason is None
    assert result.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )


@pytest.mark.parametrize("backwards", ["bind_attempt", "mark_potentially_live"])
def test_a_backwards_projection_transition_is_refused(backwards) -> None:
    """(§2.4 non-revival) A settled projection cannot be walked back to an earlier state."""
    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    key = instrument_key()
    ledger.commit_unbound(key, proposal_id="prop-1")
    ledger.bind_attempt(key, attempt_id="attempt-1")
    ledger.mark_potentially_live(key)
    ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key,
            attempt_id="attempt-1",
            kind=EgressResultKind.FULL_FILL,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert _outstanding(ledger, key).capacity_state is CapacityState.POSITION_CONSUMED

    with pytest.raises(ArtifactIntegrityError, match="may not revive"):
        if backwards == "bind_attempt":
            ledger.bind_attempt(key, attempt_id="attempt-2")
        else:
            ledger.mark_potentially_live(key)
    assert _outstanding(ledger, key).capacity_state is CapacityState.POSITION_CONSUMED


def test_the_projection_rank_orders_the_states_conservatively() -> None:
    """(§2.4) The rank the non-revival guard consumes is the declared conservatism order."""
    assert PROJECTION_RANK[CapacityState.COMMITTED_UNBOUND] < (
        PROJECTION_RANK[CapacityState.ATTEMPT_BOUND]
    )
    assert PROJECTION_RANK[CapacityState.ATTEMPT_BOUND] < (
        PROJECTION_RANK[CapacityState.POTENTIALLY_LIVE]
    )
    assert PROJECTION_RANK[CapacityState.POTENTIALLY_LIVE] < (
        PROJECTION_RANK[CapacityState.PARTIALLY_CONSUMED]
    )
    assert PROJECTION_RANK[CapacityState.PARTIALLY_CONSUMED] < (
        PROJECTION_RANK[CapacityState.POSITION_CONSUMED]
    )
    assert PROJECTION_RANK[CapacityState.POSITION_CONSUMED] < (
        PROJECTION_RANK[CapacityState.RELEASE_PENDING_PROOF]
    )
    assert PROJECTION_RANK[CapacityState.RELEASE_PENDING_PROOF] < (
        PROJECTION_RANK[CapacityState.QUARANTINED_UNKNOWN]
    ), (
        "QUARANTINED_UNKNOWN must outrank every settled state ([KW2b-#2]; mirrors "
        "tos.rcl.predicates._CONSERVATISM_RANK, where it is the single highest member)"
    )


def test_quarantined_unknown_sits_after_release_pending_proof_before_released() -> None:
    """([KW2b-#2]; kernel round #3 §2 decision 5) QUARANTINED_UNKNOWN sits after"""
    assert PROJECTION_ORDER[-1] is CapacityState.RELEASED
    assert PROJECTION_ORDER[-2] is CapacityState.QUARANTINED_UNKNOWN
    assert PROJECTION_ORDER[-3] is CapacityState.RELEASE_PENDING_PROOF


def _quarantined_core(kind: EgressResultKind = EgressResultKind.TIMEOUT):
    """A core whose reservation has already been forced into QUARANTINED_UNKNOWN by ``kind``."""
    core, sink, transmit, attempt_id = _sent_core()
    quarantine = core.handle(_egress_event(kind, attempt_id))
    assert quarantine.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )
    return core, sink, transmit, attempt_id


@pytest.mark.parametrize(
    ("kind", "fills"),
    [
        (EgressResultKind.ACK, {}),
        (
            EgressResultKind.PARTIAL_FILL,
            {"filled_quantity": Decimal("1"), "remaining_quantity": Decimal("1")},
        ),
        (
            EgressResultKind.FULL_FILL,
            {"filled_quantity": Decimal("2"), "remaining_quantity": Decimal("0")},
        ),
        (EgressResultKind.REJECT, {}),
        (EgressResultKind.CANCEL_ACK, {}),
        (EgressResultKind.EXPIRED, {}),
    ],
)
def test_positive_evidence_resolves_the_quarantine(kind, fills) -> None:
    """([KW2b-#2]; ADR-002-002 §18.6/§15.2) Every ``QUARANTINE_RESOLUTION_EDGES`` member actually"""
    core, _, _, attempt_id = _quarantined_core()
    result = core.handle(_egress_event(kind, attempt_id, sequence=3, **fills))

    assert result.halt_reason is None
    assert result.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        QUARANTINE_RESOLUTION_EDGES[kind]
    )


@pytest.mark.parametrize("kind", [EgressResultKind.UNKNOWN, EgressResultKind.TIMEOUT])
def test_a_repeated_unknown_or_timeout_stays_quarantined(kind) -> None:
    """([KW2b-#2]) Neither UNKNOWN nor TIMEOUT is positive evidence, so repeating either while"""
    core, _, _, attempt_id = _quarantined_core(kind)
    repeat = core.handle(_egress_event(kind, attempt_id, sequence=3))

    assert repeat.halt_reason is HaltReason.RESULT_UNMATCHED
    assert repeat.result_disposition is ResultDisposition.DUPLICATE
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )


def test_quarantine_resolution_edges_excludes_unknown_and_timeout() -> None:
    """([KW2b-#2]; derived positive invariant per Phase 3 wave 2 re-review #2 N2 / KW2d-N2) The"""
    excluded_by_transition = {
        kind
        for kind in EgressResultKind
        if _RESULT_TRANSITIONS[kind][1] is CapacityState.QUARANTINED_UNKNOWN
    }
    assert excluded_by_transition == {
        EgressResultKind.UNKNOWN,
        EgressResultKind.TIMEOUT,
    }
    assert (
        set(QUARANTINE_RESOLUTION_EDGES)
        == set(EgressResultKind) - excluded_by_transition
    )

    assert EgressResultKind.UNKNOWN not in QUARANTINE_RESOLUTION_EDGES
    assert EgressResultKind.TIMEOUT not in QUARANTINE_RESOLUTION_EDGES


def test_quarantine_resolution_edges_values_are_settled_states_below_quarantine() -> (
    None
):
    """([KW2d-N2]) Every resolution target is a real ``PROJECTION_ORDER`` member ranking"""
    for kind, target in QUARANTINE_RESOLUTION_EDGES.items():
        assert (
            target in PROJECTION_ORDER
        ), f"{kind}: {target} is not a member of PROJECTION_ORDER at all"
        assert (
            PROJECTION_RANK[target] < PROJECTION_RANK[CapacityState.QUARANTINED_UNKNOWN]
        ), f"{kind}: {target} must rank strictly below QUARANTINED_UNKNOWN"


def test_full_fill_then_timeout_then_ack_stays_position_consumed() -> None:
    """([KW2c-R2]) Re-review probe case A: a proven FULL_FILL must survive a TIMEOUT/ACK cycle."""
    core, _, _, attempt_id = _sent_core()
    full_fill = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert full_fill.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    )

    timeout = core.handle(
        _egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=3)
    )
    assert timeout.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )

    ack = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=4))
    assert ack.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    ), "a bare ACK must never revive a proven FULL_FILL back to POTENTIALLY_LIVE"
    assert core.ledger.outstanding(instrument_key()).filled_quantity == Decimal("2")
    assert core.ledger.outstanding(instrument_key()).remaining_quantity == Decimal("0")


def test_reject_then_timeout_then_ack_stays_release_pending_proof() -> None:
    """([KW2c-R2]) Re-review probe case B: a proven REJECT must survive a TIMEOUT/ACK cycle."""
    core, _, _, attempt_id = _sent_core()
    reject = core.handle(_egress_event(EgressResultKind.REJECT, attempt_id, sequence=2))
    assert reject.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.RELEASE_PENDING_PROOF
    )

    core.handle(_egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=3))
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )

    ack = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=4))
    assert ack.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.RELEASE_PENDING_PROOF
    ), "a bare ACK must never revive a proven REJECT back to POTENTIALLY_LIVE"


def test_partial_fill_then_timeout_then_ack_stays_partially_consumed() -> None:
    """([KW2c-R2]) Re-review probe case C: a proven PARTIAL_FILL must survive a TIMEOUT/ACK"""
    core, _, _, attempt_id = _sent_core()
    partial = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    assert partial.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.PARTIALLY_CONSUMED
    )

    core.handle(_egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=3))
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )

    ack = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=4))
    assert ack.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.PARTIALLY_CONSUMED
    ), "a bare ACK must never revive a proven PARTIAL_FILL back to POTENTIALLY_LIVE"
    assert core.ledger.outstanding(instrument_key()).filled_quantity == Decimal("4")
    assert core.ledger.outstanding(instrument_key()).remaining_quantity == Decimal("6")


def test_potentially_live_then_timeout_then_ack_still_resolves_to_potentially_live() -> (
    None
):
    """([KW2c-R2]) The designed case must keep working: with no settlement to floor against"""
    core, _, _, attempt_id = _quarantined_core()
    ack = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=3))
    assert ack.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POTENTIALLY_LIVE
    )


def test_a_second_timeout_does_not_overwrite_the_resolution_floor() -> None:
    """([KW2c-R2]) A repeated TIMEOUT while already quarantined is DUPLICATE — it must not reset"""
    core, _, _, attempt_id = _sent_core()
    core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    core.handle(_egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=3))
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )

    repeat = core.handle(
        _egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=4)
    )
    assert repeat.result_disposition is ResultDisposition.DUPLICATE
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )

    ack = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=5))
    assert ack.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    ), "the DUPLICATE TIMEOUT must not have wiped the FULL_FILL floor"


def test_a_second_distinct_quarantine_signal_does_not_overwrite_the_floor_either() -> (
    None
):
    """([KW2c-R2]; N2) TIMEOUT then UNKNOWN — a *different* kind, so not a DUPLICATE — must"""
    core, _, _, attempt_id = _sent_core()
    core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    core.handle(_egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=3))

    second_signal = core.handle(
        _egress_event(EgressResultKind.UNKNOWN, attempt_id, sequence=4)
    )
    assert second_signal.halt_reason is None
    assert second_signal.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )

    ack = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=5))
    assert ack.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    ), "the UNKNOWN signal must not have wiped the FULL_FILL floor either"


def test_attempt_bound_then_timeout_then_full_fill_still_resolves_upward() -> None:
    """([KW2c-R2]) The floor only ever raises the resolution target, never lowers it below the"""
    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    key = instrument_key()
    ledger.commit_unbound(key, proposal_id="prop-r2")
    ledger.bind_attempt(key, attempt_id="attempt-r2")
    assert _outstanding(ledger, key).capacity_state is CapacityState.ATTEMPT_BOUND

    timeout_application = ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key, attempt_id="attempt-r2", kind=EgressResultKind.TIMEOUT
        )
    )
    assert timeout_application.disposition is ResultDisposition.APPLIED
    assert _outstanding(ledger, key).capacity_state is CapacityState.QUARANTINED_UNKNOWN

    fill_application = ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key,
            attempt_id="attempt-r2",
            kind=EgressResultKind.FULL_FILL,
            filled_quantity=Decimal("3"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert fill_application.disposition is ResultDisposition.APPLIED
    assert _outstanding(ledger, key).capacity_state is CapacityState.POSITION_CONSUMED


def test_pre_quarantine_capacity_invariant_is_non_none_iff_quarantined() -> None:
    """([KW2c-R2]) ``pre_quarantine_capacity`` is set exactly while quarantined — never before"""
    core, _, _, attempt_id = _sent_core()
    assert core.ledger.outstanding(instrument_key()).pre_quarantine_capacity is None

    core.handle(_egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=2))
    quarantined = core.ledger.outstanding(instrument_key())
    assert quarantined.capacity_state is CapacityState.QUARANTINED_UNKNOWN
    assert quarantined.pre_quarantine_capacity is CapacityState.POTENTIALLY_LIVE

    core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=3))
    resolved = core.ledger.outstanding(instrument_key())
    assert resolved.capacity_state is CapacityState.POTENTIALLY_LIVE
    assert resolved.pre_quarantine_capacity is None
