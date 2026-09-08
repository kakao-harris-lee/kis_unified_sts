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

#: A fixed scope for tests that exercise transition mechanics, not scope
#: semantics themselves (laneO port-fix round, design #40 runtime slice #2
#: §5, 2026-09-08 — ``scope`` is now a required binding on every committed
#: reservation-lifecycle transition).
DEFAULT_SCOPE = ReservationScope(account="acct-1", instrument="101S06")


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
    # RELEASED is terminal — no transition may leave it (ADR-002-002 §10.1).
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
    # PARTIALLY_CONSUMED -> COMMITTED_UNBOUND is a conservatism DECREASE — legal
    # under SOME cause (structurally), but a weak cause (TIMEOUT) may only
    # increase conservatism (ADR-002-002 §10.2).
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
    # Build real history first (HIGH-1 fix, 2026-09-08): from_state is checked
    # against the held record, so a reservation must actually be held at
    # POTENTIALLY_LIVE before a POTENTIALLY_LIVE -> RELEASED claim can pass.
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
        expected_seq=setup.seq,
        finality_witness=True,
    )
    assert isinstance(result, AppendReceipt)
    rows = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert rows["res-1"] == CapacityState.RELEASED


# ============================================================================
# HIGH-1 (independent review, 2026-09-08) — claimed from_state must agree
# with the held record; a stale/mistaken claim must never be admitted even
# when it is structurally legal and cause-admissible in isolation.
# ============================================================================


def test_stale_from_state_claim_after_release_is_refused(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """The exact HIGH-1 repro: RELEASE a reservation, then claim it is still
    COMMITTED_UNBOUND and try to re-arm it toward POTENTIALLY_LIVE. Before the
    fix this was admitted (AppendReceipt) — an automatic re-arm of a
    finalized reservation (ADR-002-012 :37). It must now refuse.
    """
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
        expected_seq=to_potentially_live.seq,
        finality_witness=True,
    )
    assert isinstance(released, AppendReceipt)
    rows = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert rows["res-1"] == CapacityState.RELEASED

    # The stale/mistaken re-arm claim: structurally legal (an increase) and
    # cause-admissible in isolation, but the held record says RELEASED, not
    # COMMITTED_UNBOUND.
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
        expected_seq=released.seq,
    )

    assert isinstance(re_arm_attempt, AppendRefusal)
    assert re_arm_attempt.reason == AppendRefusalReason.INTEGRITY_VIOLATION
    # And the held record is unchanged — still RELEASED, never re-armed.
    rows_after = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert rows_after["res-1"] == CapacityState.RELEASED


def test_honest_from_state_after_prior_transition_still_commits(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """A regression guard: a truthful, sequential chain of transitions must
    still be admitted — the HIGH-1 fix only refuses a DISAGREEING claim, not
    every claim.
    """
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
            from_state=CapacityState.ATTEMPT_BOUND,  # honestly matches the held state
            to_state=CapacityState.POTENTIALLY_LIVE,
            scope=DEFAULT_SCOPE,
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.MARK_SEND_STARTED,
        command_id="cmd-2",
        command_digest="dig-2",
        expected_seq=first.seq,
    )
    assert isinstance(second, AppendReceipt)
    rows = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert rows["res-1"] == CapacityState.POTENTIALLY_LIVE


def test_no_row_with_non_initial_from_state_is_refused(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """A brand-new ``reservation_id`` (no held row) may only be claimed to
    originate from ``COMMITTED_UNBOUND`` — the sole entry point the engine's
    own ``ProvisionalReservationLedger.commit_unbound`` admits with no prior
    projection (``tos.engine.state``). Claiming ATTEMPT_BOUND with no history
    at all must be refused, never silently admitted.
    """
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
