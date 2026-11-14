"""``SqliteCommitLog.apply_reservation_transition`` tests (design #40 D2.1 item 4)."""

from __future__ import annotations

import pytest
from tos.rcl import (
    AppendReceipt,
    AppendRefusal,
    AppendRefusalReason,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.log import (
    ReservationRefusalReason,
    ReservationTransitionRefusal,
    SqliteCommitLog,
)

DEFAULT_SCOPE = ReservationScope(account="acct-1", instrument="101S06")


def _seq(receipt: AppendReceipt) -> int:
    """``receipt.seq``, asserted present — a successful"""
    assert receipt.seq is not None
    return receipt.seq


def test_legal_transition_under_strong_cause_commits_and_updates_projection(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=epoch,
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.ATTEMPT_BOUND,
        scope=DEFAULT_SCOPE,
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
    rows = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert rows["res-1"] == CapacityState.ATTEMPT_BOUND


def test_structurally_illegal_transition_raises_refusal(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=epoch,
        from_state=CapacityState.RELEASED,
        to_state=CapacityState.COMMITTED_UNBOUND,
        scope=DEFAULT_SCOPE,
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
    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=epoch,
        from_state=CapacityState.PARTIALLY_CONSUMED,
        to_state=CapacityState.COMMITTED_UNBOUND,
        scope=DEFAULT_SCOPE,
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
        scope=DEFAULT_SCOPE,
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
    setup = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id="res-1",
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.POTENTIALLY_LIVE,
            scope=DEFAULT_SCOPE,
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.COMMIT_RESERVATION,
        command_id="cmd-0",
        command_digest="dig-0",
        expected_seq=-1,
    )
    assert isinstance(setup, AppendReceipt)

    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=epoch,
        from_state=CapacityState.POTENTIALLY_LIVE,
        to_state=CapacityState.RELEASED,
        scope=DEFAULT_SCOPE,
    )
    result = log.apply_reservation_transition(
        transition,
        TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        command_id="cmd-1",
        command_digest="dig-1",
        expected_seq=_seq(setup),
        finality_witness=True,
    )
    assert isinstance(result, AppendReceipt)
    rows = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert rows["res-1"] == CapacityState.RELEASED


def test_stale_from_state_claim_after_release_is_refused(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """The exact HIGH-1 repro: RELEASE a reservation, then claim it is still"""
    epoch = log.acquire_epoch(identity)
    to_potentially_live = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id="res-1",
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.POTENTIALLY_LIVE,
            scope=DEFAULT_SCOPE,
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.COMMIT_RESERVATION,
        command_id="cmd-0",
        command_digest="dig-0",
        expected_seq=-1,
    )
    assert isinstance(to_potentially_live, AppendReceipt)

    released = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id="res-1",
            writer_epoch=epoch,
            from_state=CapacityState.POTENTIALLY_LIVE,
            to_state=CapacityState.RELEASED,
            scope=DEFAULT_SCOPE,
        ),
        TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        command_id="cmd-1",
        command_digest="dig-1",
        expected_seq=_seq(to_potentially_live),
        finality_witness=True,
    )
    assert isinstance(released, AppendReceipt)
    rows = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert rows["res-1"] == CapacityState.RELEASED

    re_arm_attempt = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id="res-1",
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.POTENTIALLY_LIVE,
            scope=DEFAULT_SCOPE,
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.COMMIT_RESERVATION,
        command_id="cmd-2",
        command_digest="dig-2",
        expected_seq=_seq(released),
    )

    assert isinstance(re_arm_attempt, AppendRefusal)
    assert re_arm_attempt.reason == AppendRefusalReason.INTEGRITY_VIOLATION
    rows_after = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert rows_after["res-1"] == CapacityState.RELEASED


def test_honest_from_state_after_prior_transition_still_commits(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """A regression guard: a truthful, sequential chain of transitions must"""
    epoch = log.acquire_epoch(identity)
    first = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id="res-1",
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.ATTEMPT_BOUND,
            scope=DEFAULT_SCOPE,
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id="cmd-1",
        command_digest="dig-1",
        expected_seq=-1,
    )
    assert isinstance(first, AppendReceipt)

    second = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id="res-1",
            writer_epoch=epoch,
            from_state=CapacityState.ATTEMPT_BOUND,
            to_state=CapacityState.POTENTIALLY_LIVE,
            scope=DEFAULT_SCOPE,
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.MARK_SEND_STARTED,
        command_id="cmd-2",
        command_digest="dig-2",
        expected_seq=_seq(first),
    )
    assert isinstance(second, AppendReceipt)
    rows = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert rows["res-1"] == CapacityState.POTENTIALLY_LIVE


def test_no_row_with_non_initial_from_state_is_refused(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """A brand-new ``reservation_id`` (no held row) may only be claimed to"""
    epoch = log.acquire_epoch(identity)
    result = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id="res-never-seen",
            writer_epoch=epoch,
            from_state=CapacityState.ATTEMPT_BOUND,
            to_state=CapacityState.POTENTIALLY_LIVE,
            scope=DEFAULT_SCOPE,
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.MARK_SEND_STARTED,
        command_id="cmd-1",
        command_digest="dig-1",
        expected_seq=-1,
    )
    assert isinstance(result, AppendRefusal)
    assert result.reason == AppendRefusalReason.INTEGRITY_VIOLATION
    rows = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert "res-never-seen" not in rows
