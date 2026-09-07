"""``ReservationProjectionReader`` / ``SqliteReservationProjectionReader`` tests."""

from __future__ import annotations

from tos.rcl import (
    AppendReceipt,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import (
    ReservationProjectionReader,
    SqliteReservationProjectionReader,
)


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
