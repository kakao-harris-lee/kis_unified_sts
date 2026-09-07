"""``SqliteCommitLog.apply_reservation_transition`` tests (design #40 D2.1 item 4)."""

from __future__ import annotations

import pytest
from tos.rcl import (
    AppendReceipt,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.log import (
    ReservationRefusalReason,
    ReservationTransitionRefusal,
    SqliteCommitLog,
)


def test_legal_transition_under_strong_cause_commits_and_updates_projection(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=epoch,
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.ATTEMPT_BOUND,
    )

    result = log.apply_reservation_transition(
        transition,
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id="cmd-1",
        command_digest="dig-1",
        expected_seq=-1,
    )

    assert isinstance(result, AppendReceipt)
    rows = {rid: state for rid, state, _seq in log.reservation_rows()}
    assert rows["res-1"] == CapacityState.ATTEMPT_BOUND


def test_structurally_illegal_transition_raises_refusal(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    # RELEASED is terminal — no transition may leave it (ADR-002-002 §10.1).
    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=epoch,
        from_state=CapacityState.RELEASED,
        to_state=CapacityState.COMMITTED_UNBOUND,
    )

    with pytest.raises(ReservationTransitionRefusal) as excinfo:
        log.apply_reservation_transition(
            transition,
            TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
            command_type=CommandType.COMMIT_RESERVATION,
            command_id="cmd-1",
            command_digest="dig-1",
            expected_seq=-1,
        )
    assert excinfo.value.reason == ReservationRefusalReason.NOT_STRUCTURALLY_LEGAL


def test_structurally_legal_but_weak_cause_refuses_conservatism_decrease(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    # PARTIALLY_CONSUMED -> COMMITTED_UNBOUND is a conservatism DECREASE — legal
    # under SOME cause (structurally), but a weak cause (TIMEOUT) may only
    # increase conservatism (ADR-002-002 §10.2).
    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=epoch,
        from_state=CapacityState.PARTIALLY_CONSUMED,
        to_state=CapacityState.COMMITTED_UNBOUND,
    )

    with pytest.raises(ReservationTransitionRefusal) as excinfo:
        log.apply_reservation_transition(
            transition,
            TransitionCause.TIMEOUT,
            command_type=CommandType.RESIZE_RESERVATION,
            command_id="cmd-1",
            command_digest="dig-1",
            expected_seq=-1,
        )
    assert excinfo.value.reason == ReservationRefusalReason.CAUSE_NOT_ADMISSIBLE


def test_release_without_finality_witness_true_is_refused(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=epoch,
        from_state=CapacityState.POTENTIALLY_LIVE,
        to_state=CapacityState.RELEASED,
    )

    with pytest.raises(ReservationTransitionRefusal) as excinfo:
        log.apply_reservation_transition(
            transition,
            TransitionCause.FINAL_QUANTITY_PROOF,
            command_type=CommandType.RELEASE_RESERVATION,
            command_id="cmd-1",
            command_digest="dig-1",
            expected_seq=-1,
            finality_witness=None,
        )
    assert excinfo.value.reason == ReservationRefusalReason.FINALITY_WITNESS_REQUIRED


def test_release_with_finality_witness_true_is_admitted(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=epoch,
        from_state=CapacityState.POTENTIALLY_LIVE,
        to_state=CapacityState.RELEASED,
    )

    result = log.apply_reservation_transition(
        transition,
        TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        command_id="cmd-1",
        command_digest="dig-1",
        expected_seq=-1,
        finality_witness=True,
    )
    assert isinstance(result, AppendReceipt)
    rows = {rid: state for rid, state, _seq in log.reservation_rows()}
    assert rows["res-1"] == CapacityState.RELEASED
