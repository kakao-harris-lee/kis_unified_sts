"""``ReservationProjectionReader`` / ``SqliteReservationProjectionReader`` tests."""

from __future__ import annotations

from tos.engine.records import InstrumentKey
from tos.rcl import (
    AppendReceipt,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import (
    ReservationProjectionReader,
    SqliteReservationProjectionReader,
)

#: A fixed scope for tests that exercise projection mechanics, not scope
#: semantics themselves (laneO port-fix round, design #40 runtime slice #2
#: §5, 2026-09-08).
DEFAULT_SCOPE = ReservationScope(account="acct-1", instrument="101S06")


def test_projection_reader_satisfies_protocol(log: SqliteCommitLog) -> None:
    reader = SqliteReservationProjectionReader(log)
    assert isinstance(reader, ReservationProjectionReader)


def test_unknown_reservation_reads_as_none(log: SqliteCommitLog) -> None:
    reader = SqliteReservationProjectionReader(log)
    assert reader.reservation_state("nonexistent") is None
    assert reader.reservation_last_seq("nonexistent") is None
    assert reader.all_reservations() == {}


def test_projection_reflects_committed_transition(
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

    reader = SqliteReservationProjectionReader(log)
    assert reader.reservation_state("res-1") == CapacityState.ATTEMPT_BOUND
    assert reader.reservation_last_seq("res-1") == result.seq
    assert reader.all_reservations() == {"res-1": CapacityState.ATTEMPT_BOUND}


# ============================================================================
# InstrumentKey-keyed reads (laneO port-fix round, design #40 runtime slice
# #2 §5 disposition, 2026-09-08) — the kernel port gap this module's own
# docstring used to report is now closed: CapacityReservationTransition.scope
# lets the projection group by the engine's own InstrumentKey, not only by
# the log's native reservation_id.
# ============================================================================


def test_unknown_instrument_reads_as_none(log: SqliteCommitLog) -> None:
    reader = SqliteReservationProjectionReader(log)
    key = InstrumentKey(account="acct-1", instrument="101S06")
    assert reader.instrument_state(key) is None
    assert reader.instrument_last_seq(key) is None


def test_projection_reads_by_instrument_key_after_a_transition(
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

    reader = SqliteReservationProjectionReader(log)
    key = InstrumentKey(
        account=DEFAULT_SCOPE.account, instrument=DEFAULT_SCOPE.instrument
    )
    assert reader.instrument_state(key) == CapacityState.ATTEMPT_BOUND
    assert reader.instrument_last_seq(key) == result.seq

    # A key for a different scope entirely reads back nothing.
    other_key = InstrumentKey(account="acct-2", instrument="201S03")
    assert reader.instrument_state(other_key) is None
    assert reader.instrument_last_seq(other_key) is None


def test_two_reservations_with_different_scopes_do_not_collide(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """Two DIFFERENT reservation_ids, each bound to its own distinct scope —
    reading back by InstrumentKey must return only the matching reservation's
    state, never the other's (no cross-scope collision)."""
    epoch = log.acquire_epoch(identity)
    scope_a = ReservationScope(account="acct-1", instrument="101S06")
    scope_b = ReservationScope(account="acct-2", instrument="201S03")

    first = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id="res-a",
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.ATTEMPT_BOUND,
            scope=scope_a,
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id="cmd-a",
        command_digest="dig-a",
        expected_seq=-1,
    )
    assert isinstance(first, AppendReceipt)

    second = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id="res-b",
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.POTENTIALLY_LIVE,
            scope=scope_b,
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.COMMIT_RESERVATION,
        command_id="cmd-b",
        command_digest="dig-b",
        expected_seq=first.seq,
    )
    assert isinstance(second, AppendReceipt)

    reader = SqliteReservationProjectionReader(log)
    key_a = InstrumentKey(account=scope_a.account, instrument=scope_a.instrument)
    key_b = InstrumentKey(account=scope_b.account, instrument=scope_b.instrument)
    assert reader.instrument_state(key_a) == CapacityState.ATTEMPT_BOUND
    assert reader.instrument_state(key_b) == CapacityState.POTENTIALLY_LIVE
    assert reader.instrument_last_seq(key_a) == first.seq
    assert reader.instrument_last_seq(key_b) == second.seq
    assert reader.all_reservations() == {
        "res-a": CapacityState.ATTEMPT_BOUND,
        "res-b": CapacityState.POTENTIALLY_LIVE,
    }
