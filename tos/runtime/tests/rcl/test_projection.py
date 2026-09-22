"""``ReservationProjectionReader`` / ``SqliteReservationProjectionReader`` tests."""

from __future__ import annotations

from tos.engine.records import InstrumentKey
from tos.rcl import (
    AppendReceipt,
    CapacityComponent,
    CapacityReservationTransition,
    CapacityState,
    CapacityVector,
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
# Committed Capacity Vector round-trip (kernel round #4 K-4). Prior to this,
# every transition in this module committed with the default
# ``committed_vector=None``, so no test exercised the "commit a NON-empty
# vector, read it back through the projection" path -- a mutation that made
# both ``reservation_committed_vector`` and ``instrument_committed_vector``
# unconditionally return ``CapacityVector()`` passed the full runtime suite
# (round #4 review finding ②). These pin that round trip so the same
# mutation reds here.
# ============================================================================

_NON_EMPTY_VECTOR = CapacityVector(
    components=(CapacityComponent(dimension_id="notional", magnitude="100"),)
)


def test_reservation_committed_vector_reads_back_the_committed_value(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=epoch,
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.ATTEMPT_BOUND,
        scope=DEFAULT_SCOPE,
        committed_vector=_NON_EMPTY_VECTOR,
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
    assert reader.reservation_committed_vector("res-1") == _NON_EMPTY_VECTOR
    key = InstrumentKey(
        account=DEFAULT_SCOPE.account, instrument=DEFAULT_SCOPE.instrument
    )
    assert reader.instrument_committed_vector(key) == _NON_EMPTY_VECTOR


def test_committed_vector_reads_as_none_when_never_committed(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """A transition committed with the default ``committed_vector=None`` reads
    back as ``None`` through both key surfaces -- distinct from the non-empty
    vector case above, not merely "falsy"."""
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
    assert reader.reservation_committed_vector("res-1") is None
    key = InstrumentKey(
        account=DEFAULT_SCOPE.account, instrument=DEFAULT_SCOPE.instrument
    )
    assert reader.instrument_committed_vector(key) is None


def test_explicitly_empty_committed_vector_is_distinguishable_from_none(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """(round #4 review disposition — resolves the apparent commitlog.py/gates.py wording
    conflict) A transition committed with ``committed_vector=CapacityVector()`` (explicitly
    empty, zero components) must read back as that real, non-``None`` empty vector, never as
    ``None`` -- ``CapacityReservationTransition.committed_vector``'s own docstring promises a
    runtime projection distinguishes "no vector recorded" from "an explicitly empty one";
    :func:`~tos_runtime.rcl.gates.reservation_committed_vector`'s docstring separately notes an
    UNRELATED, narrower indistinguishability (reservation nonexistent vs. existing-with-no-
    vector, both -> ``None``) -- this pins that the two claims do not collide: an explicit
    empty vector is not folded into either ``None`` case."""
    epoch = log.acquire_epoch(identity)
    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=epoch,
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.ATTEMPT_BOUND,
        scope=DEFAULT_SCOPE,
        committed_vector=CapacityVector(),
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
    read_back = reader.reservation_committed_vector("res-1")
    assert read_back is not None
    assert read_back == CapacityVector()


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
    assert first.seq is not None  # a successful append never returns a None seq

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
