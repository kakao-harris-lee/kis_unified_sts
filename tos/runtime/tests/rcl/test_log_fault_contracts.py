"""``SqliteCommitLog`` tests — fault contracts ①②③④⑤⑥⑦ (slice plan §1).

Test names are grouped by the fault-contract number they exercise, matching
the table in ``log.py``'s own module docstring, plus the extra coverage the
slice plan calls out by name ("plus: evidence-append failure ...").
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from tos.rcl import (
    AppendReceipt,
    AppendRefusal,
    AppendRefusalReason,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    CommitEntry,
    CommitLog,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.log import CommitLogCorruption, InjectedCrash, SqliteCommitLog

from .conftest import FakeEvidenceAppendPort, FakeMonotonicClock

# ============================================================================
# ① stale epoch writer
# ============================================================================


def test_fault_1_stale_writer_epoch_is_refused(
    log_path: Path, evidence_port: FakeEvidenceAppendPort, identity: RuntimeIdentity
) -> None:
    first = SqliteCommitLog(log_path, evidence_port=evidence_port)
    second = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        stale_epoch = first.acquire_epoch(identity)
        current_epoch = second.acquire_epoch(identity)  # invalidates `first`'s epoch
        assert current_epoch > stale_epoch

        entry = CommitEntry(
            command_id="cmd-1",
            command_digest="dig-1",
            kind=CommandType.COMMIT_RESERVATION,
        )
        result = first.append_cas(entry, expected_seq=-1, writer_epoch=stale_epoch)

        assert isinstance(result, AppendRefusal)
        assert result.reason == AppendRefusalReason.STALE_EPOCH
    finally:
        first.close()
        second.close()


def test_fault_1_stale_writer_epoch_also_refuses_reads(
    log_path: Path, evidence_port: FakeEvidenceAppendPort, identity: RuntimeIdentity
) -> None:
    from tos_runtime.rcl.log import StaleEpochRead

    first = SqliteCommitLog(log_path, evidence_port=evidence_port)
    second = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        stale_epoch = first.acquire_epoch(identity)
        second.acquire_epoch(identity)
        with pytest.raises(StaleEpochRead):
            first.read_linearizable(writer_epoch=stale_epoch)
    finally:
        first.close()
        second.close()


# ============================================================================
# ② duplicate command / bytes mismatch
# ============================================================================


def test_fault_2_duplicate_command_id_same_bytes_is_idempotent_refusal(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    entry = CommitEntry(
        command_id="cmd-1", command_digest="dig-1", kind=CommandType.COMMIT_RESERVATION
    )
    first = log.append_cas(entry, expected_seq=-1, writer_epoch=epoch)
    assert isinstance(first, AppendReceipt)

    second = log.append_cas(entry, expected_seq=first.seq, writer_epoch=epoch)
    assert isinstance(second, AppendRefusal)
    assert second.reason == AppendRefusalReason.DUPLICATE_COMMAND_ID


def test_fault_2_duplicate_command_id_different_bytes_is_contained_conflict(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    first_entry = CommitEntry(
        command_id="cmd-1", command_digest="dig-1", kind=CommandType.COMMIT_RESERVATION
    )
    first = log.append_cas(first_entry, expected_seq=-1, writer_epoch=epoch)
    assert isinstance(first, AppendReceipt)

    conflicting_entry = CommitEntry(
        command_id="cmd-1",
        command_digest="dig-DIFFERENT",
        kind=CommandType.COMMIT_RESERVATION,
    )
    second = log.append_cas(
        conflicting_entry, expected_seq=first.seq, writer_epoch=epoch
    )
    assert isinstance(second, AppendRefusal)
    assert second.reason == AppendRefusalReason.COMMAND_BYTES_MISMATCH


# ============================================================================
# MEDIUM-3 (independent review, 2026-09-08) — a NULL command_digest on an
# EXISTING row must not collapse into "no prior entry" and reach the
# entries.command_id UNIQUE constraint unclassified.
#
# Red-before proof (empirically verified against the pre-fix code in a
# scratch worktree at the commit under review, 2026-09-08): the exact repro
# below returned ``AppendRefusal(reason=PARTIAL_COMMIT_SUSPECTED,
# detail="IntegrityError('UNIQUE constraint failed: entries.command_id')")``
# before this fix — the fix makes it ``DUPLICATE_COMMAND_ID`` instead.
# ============================================================================


def test_null_digest_duplicate_command_is_classified_as_duplicate_not_partial_commit(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    entry = CommitEntry(
        command_id="cmd-1", command_digest=None, kind=CommandType.COMMIT_RESERVATION
    )
    first = log.append_cas(entry, expected_seq=-1, writer_epoch=epoch)
    assert isinstance(first, AppendReceipt)

    second = log.append_cas(entry, expected_seq=first.seq, writer_epoch=epoch)

    assert isinstance(second, AppendRefusal)
    assert second.reason == AppendRefusalReason.DUPLICATE_COMMAND_ID


def test_null_digest_then_non_null_digest_is_command_bytes_mismatch(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    first_entry = CommitEntry(
        command_id="cmd-1", command_digest=None, kind=CommandType.COMMIT_RESERVATION
    )
    first = log.append_cas(first_entry, expected_seq=-1, writer_epoch=epoch)
    assert isinstance(first, AppendReceipt)

    conflicting_entry = CommitEntry(
        command_id="cmd-1",
        command_digest="dig-not-null",
        kind=CommandType.COMMIT_RESERVATION,
    )
    second = log.append_cas(
        conflicting_entry, expected_seq=first.seq, writer_epoch=epoch
    )

    assert isinstance(second, AppendRefusal)
    assert second.reason == AppendRefusalReason.COMMAND_BYTES_MISMATCH


def test_non_null_digest_then_null_digest_is_command_bytes_mismatch(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    first_entry = CommitEntry(
        command_id="cmd-1",
        command_digest="dig-not-null",
        kind=CommandType.COMMIT_RESERVATION,
    )
    first = log.append_cas(first_entry, expected_seq=-1, writer_epoch=epoch)
    assert isinstance(first, AppendReceipt)

    conflicting_entry = CommitEntry(
        command_id="cmd-1", command_digest=None, kind=CommandType.COMMIT_RESERVATION
    )
    second = log.append_cas(
        conflicting_entry, expected_seq=first.seq, writer_epoch=epoch
    )

    assert isinstance(second, AppendRefusal)
    assert second.reason == AppendRefusalReason.COMMAND_BYTES_MISMATCH


# ============================================================================
# ③ file access unavailable (locked file)
# ============================================================================


def test_fault_3_locked_file_prevents_opening_a_second_handle(
    log_path: Path, evidence_port: FakeEvidenceAppendPort
) -> None:
    # Hold an unreleased write reservation on the same file from a raw connection —
    # a second handle cannot even complete its own WAL-mode setup while the file is
    # exclusively locked (a real "storage unavailable" condition, not a refusal this
    # module's own API can convert — there is no open ``SqliteCommitLog`` yet to
    # return an ``AppendRefusal`` from).
    blocker = sqlite3.connect(str(log_path), isolation_level=None, timeout=0.0)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(sqlite3.OperationalError):
            SqliteCommitLog(log_path, evidence_port=evidence_port, sqlite_timeout_s=0.0)
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()


def test_fault_3_locked_file_refuses_append_with_store_unavailable(
    log_path: Path, evidence_port: FakeEvidenceAppendPort, identity: RuntimeIdentity
) -> None:
    log_under_test = SqliteCommitLog(
        log_path, evidence_port=evidence_port, sqlite_timeout_s=0.0
    )
    epoch = log_under_test.acquire_epoch(identity)

    blocker = sqlite3.connect(str(log_path), isolation_level=None, timeout=0.0)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        entry = CommitEntry(
            command_id="cmd-1",
            command_digest="dig-1",
            kind=CommandType.COMMIT_RESERVATION,
        )
        result = log_under_test.append_cas(entry, expected_seq=-1, writer_epoch=epoch)
        assert isinstance(result, AppendRefusal)
        assert result.reason == AppendRefusalReason.STORE_UNAVAILABLE
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
        log_under_test.close()


# ============================================================================
# ④ durable commit crash injection (before/after commit)
# ============================================================================


def test_fault_4_crash_before_commit_leaves_no_entry(
    log_path: Path, evidence_port: FakeEvidenceAppendPort, identity: RuntimeIdentity
) -> None:
    def crash_before_commit(point: str) -> None:
        if point == "before_commit":
            raise InjectedCrash("simulated crash before commit")

    crashing_log = SqliteCommitLog(
        log_path, evidence_port=evidence_port, crash_hook=crash_before_commit
    )
    epoch = crashing_log.acquire_epoch(identity)
    entry = CommitEntry(
        command_id="cmd-1", command_digest="dig-1", kind=CommandType.COMMIT_RESERVATION
    )
    with pytest.raises(InjectedCrash):
        crashing_log.append_cas(entry, expected_seq=-1, writer_epoch=epoch)
    crashing_log.close()

    reopened = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        assert list(reopened.replay()) == []
        assert reopened._current_seq_tip() == -1
    finally:
        reopened.close()


def test_fault_4_crash_after_commit_before_receipt_leaves_entry_durable(
    log_path: Path, evidence_port: FakeEvidenceAppendPort, identity: RuntimeIdentity
) -> None:
    def crash_after_commit(point: str) -> None:
        if point == "after_commit_before_receipt":
            raise InjectedCrash("simulated crash after commit, before receipt")

    crashing_log = SqliteCommitLog(
        log_path, evidence_port=evidence_port, crash_hook=crash_after_commit
    )
    epoch = crashing_log.acquire_epoch(identity)
    entry = CommitEntry(
        command_id="cmd-1", command_digest="dig-1", kind=CommandType.COMMIT_RESERVATION
    )
    with pytest.raises(InjectedCrash):
        crashing_log.append_cas(entry, expected_seq=-1, writer_epoch=epoch)
    crashing_log.close()

    reopened = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        entries = list(reopened.replay())
        assert len(entries) == 1
        assert entries[0].command_id == "cmd-1"
    finally:
        reopened.close()


# ============================================================================
# LOW (independent review, 2026-09-08) — evidence append durably commits to
# its own file before this log's own COMMIT; a failure AFTER that append but
# still inside this transaction rolls back only the RCL side. Evidence may
# therefore over-record an entry this log itself never holds — but the log
# can never hold an entry without a prior successful evidence append.
# ============================================================================


def test_evidence_over_records_but_never_under_records_on_post_evidence_rollback(
    log_path: Path, evidence_port: FakeEvidenceAppendPort, identity: RuntimeIdentity
) -> None:
    def crash_after_evidence_before_commit(point: str) -> None:
        if point == "before_commit":
            # By this point the evidence_port.append() call has already
            # returned successfully (it happens earlier in _commit_entry,
            # before this hook is called) — this simulates a crash in the
            # narrow window between that success and this log's own COMMIT.
            raise InjectedCrash(
                "simulated crash after evidence append, before RCL commit"
            )

    crashing_log = SqliteCommitLog(
        log_path,
        evidence_port=evidence_port,
        crash_hook=crash_after_evidence_before_commit,
    )
    epoch = crashing_log.acquire_epoch(identity)
    entry = CommitEntry(
        command_id="cmd-1", command_digest="dig-1", kind=CommandType.COMMIT_RESERVATION
    )
    with pytest.raises(InjectedCrash):
        crashing_log.append_cas(entry, expected_seq=-1, writer_epoch=epoch)
    crashing_log.close()

    # Evidence store holds the record — it over-recorded an attempt that was
    # then abandoned.
    assert len(evidence_port.calls) == 1
    recorded_payload, _kind, _record_class = evidence_port.calls[0]
    assert recorded_payload["command_id"] == "cmd-1"

    # But the RCL log itself holds NO entry — it never under-records the
    # reverse (an entry can never exist here without a prior evidence record).
    reopened = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        assert list(reopened.replay()) == []
    finally:
        reopened.close()


# ============================================================================
# ⑤ replay does not reproduce held state -> CommitLogCorruption
# ============================================================================


def test_fault_5_replay_mismatch_raises_commit_log_corruption(
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

    # A legitimate log passes verify_replay before any tampering.
    log.verify_replay()

    # Tamper directly with the held projection (bypassing the log's own API) so
    # the independently re-folded state disagrees with what is held.
    log._conn.execute(
        "UPDATE reservations SET state = ? WHERE reservation_id = ?",
        (CapacityState.QUARANTINED_UNKNOWN.value, "res-1"),
    )

    with pytest.raises(CommitLogCorruption):
        log.verify_replay()


def test_fault_5_verify_replay_passes_on_empty_log(log: SqliteCommitLog) -> None:
    log.verify_replay()  # no reservations at all — trivially consistent


# ============================================================================
# MEDIUM-4 (independent review, 2026-09-08) — the replay fold must not be
# forgeable via a plain append_cas call's public payload_json argument.
# ============================================================================


def test_ghost_reservation_payload_via_append_cas_does_not_forge_corruption(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """A plain ``append_cas`` call whose ``payload_json`` happens to decode to
    ``{"reservation_id": ..., "to_state": ...}`` must NOT be folded into
    ``verify_replay``'s reservation-state reconstruction — before the fix
    this forged a ``CommitLogCorruption`` on an otherwise healthy, untouched
    log (the entry's ``is_reservation_transition`` column, never
    caller-settable, is what now excludes it).
    """
    epoch = log.acquire_epoch(identity)
    ghost_payload_json = json.dumps(
        {"reservation_id": "GHOST", "to_state": CapacityState.RELEASED.value}
    )
    entry = CommitEntry(
        command_id="cmd-1", command_digest="dig-1", kind=CommandType.COMMIT_RESERVATION
    )

    result = log.append_cas(
        entry, expected_seq=-1, writer_epoch=epoch, payload_json=ghost_payload_json
    )

    assert isinstance(result, AppendReceipt)
    # No reservation was ever actually created (nothing went through
    # apply_reservation_transition), and verify_replay must not disagree.
    assert {rid: state for rid, state, _seq in log.reservation_rows()} == {}
    log.verify_replay()  # must NOT raise


def test_genuine_reservations_row_tamper_still_raises_after_medium_4_fix(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """Regression guard: a REAL disagreement (the held ``reservations`` row
    tampered directly, bypassing this log's own API) must still be detected
    — the MEDIUM-4 fix narrows what is folded IN, it must not also silence a
    genuine mismatch.
    """
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
    log.verify_replay()  # legitimate — passes

    log._conn.execute(
        "UPDATE reservations SET state = ? WHERE reservation_id = ?",
        (CapacityState.QUARANTINED_UNKNOWN.value, "res-1"),
    )

    with pytest.raises(CommitLogCorruption):
        log.verify_replay()


# ============================================================================
# ⑥ clock regression does not affect seq/epoch order
# ============================================================================


def test_fault_6_regressing_monotonic_source_does_not_affect_seq_order(
    log_path: Path, evidence_port: FakeEvidenceAppendPort, identity: RuntimeIdentity
) -> None:
    clock = FakeMonotonicClock(start=1_000_000)
    instance = SqliteCommitLog(
        log_path, evidence_port=evidence_port, monotonic_ns=clock
    )
    try:
        epoch_1 = instance.acquire_epoch(identity)
        entry_a = CommitEntry(
            command_id="cmd-a",
            command_digest="dig-a",
            kind=CommandType.COMMIT_RESERVATION,
        )
        receipt_a = instance.append_cas(entry_a, expected_seq=-1, writer_epoch=epoch_1)
        assert isinstance(receipt_a, AppendReceipt)

        clock.value = 0  # the monotonic source regresses
        epoch_2 = instance.acquire_epoch(identity)
        assert epoch_2 > epoch_1  # epoch still strictly increases

        entry_b = CommitEntry(
            command_id="cmd-b",
            command_digest="dig-b",
            kind=CommandType.COMMIT_RESERVATION,
        )
        receipt_b = instance.append_cas(
            entry_b, expected_seq=receipt_a.seq, writer_epoch=epoch_2
        )
        assert isinstance(receipt_b, AppendReceipt)
        assert receipt_b.seq == receipt_a.seq + 1  # seq still strictly increases
    finally:
        instance.close()


# ============================================================================
# ⑦ simulated sqlite failure mid-transaction (partial commit)
# ============================================================================


def test_fault_7_simulated_mid_transaction_failure_refuses_and_rolls_back(
    log_path: Path, evidence_port: FakeEvidenceAppendPort, identity: RuntimeIdentity
) -> None:
    # A real disk-full/IO-error can surface at flush time, right before COMMIT —
    # reused via the same crash_hook injection point as fault ④, but raising a
    # genuine sqlite3.Error (not InjectedCrash) to model contract ⑦ specifically:
    # this must be caught, rolled back, and refused, never propagated raw.
    def simulate_sqlite_failure(point: str) -> None:
        if point == "before_commit":
            raise sqlite3.OperationalError("simulated mid-transaction failure")

    instance = SqliteCommitLog(
        log_path, evidence_port=evidence_port, crash_hook=simulate_sqlite_failure
    )
    try:
        epoch = instance.acquire_epoch(identity)
        entry = CommitEntry(
            command_id="cmd-1",
            command_digest="dig-1",
            kind=CommandType.COMMIT_RESERVATION,
        )
        result = instance.append_cas(entry, expected_seq=-1, writer_epoch=epoch)

        assert isinstance(result, AppendRefusal)
        assert result.reason == AppendRefusalReason.PARTIAL_COMMIT_SUSPECTED
        assert instance._current_seq_tip() == -1  # rolled back — nothing committed
        assert list(instance.replay()) == []
    finally:
        instance.close()


# ============================================================================
# extra coverage the slice plan names explicitly
# ============================================================================


def test_evidence_append_failure_rolls_back_with_no_receipt_and_no_entry(
    log: SqliteCommitLog,
    evidence_port: FakeEvidenceAppendPort,
    identity: RuntimeIdentity,
) -> None:
    epoch = log.acquire_epoch(identity)
    evidence_port.fail_next_append(RuntimeError("evidence store unavailable"))
    entry = CommitEntry(
        command_id="cmd-1", command_digest="dig-1", kind=CommandType.COMMIT_RESERVATION
    )

    result = log.append_cas(entry, expected_seq=-1, writer_epoch=epoch)

    assert isinstance(result, AppendRefusal)
    assert result.reason == AppendRefusalReason.STORE_UNAVAILABLE
    assert log._current_seq_tip() == -1
    assert list(log.replay()) == []


def test_replay_of_empty_log_yields_nothing(log: SqliteCommitLog) -> None:
    assert list(log.replay()) == []


def test_sqlite_commit_log_satisfies_commitlog_protocol(log: SqliteCommitLog) -> None:
    assert isinstance(log, CommitLog)


def test_seq_mismatch_is_refused(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    entry = CommitEntry(
        command_id="cmd-1", command_digest="dig-1", kind=CommandType.COMMIT_RESERVATION
    )
    result = log.append_cas(entry, expected_seq=5, writer_epoch=epoch)  # wrong tip
    assert isinstance(result, AppendRefusal)
    assert result.reason == AppendRefusalReason.SEQ_MISMATCH


def test_current_epoch_is_zero_before_any_epoch_acquired(log: SqliteCommitLog) -> None:
    assert log.current_epoch() == 0


def test_read_linearizable_snapshot_reflects_committed_entries(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    entry = CommitEntry(
        command_id="cmd-1", command_digest="dig-1", kind=CommandType.COMMIT_RESERVATION
    )
    receipt = log.append_cas(entry, expected_seq=-1, writer_epoch=epoch)
    assert isinstance(receipt, AppendReceipt)

    view = log.read_linearizable(writer_epoch=epoch)
    assert view.epoch == epoch
    assert view.last_seq == 0
    assert len(view.entries) == 1
    assert view.entries[0].command_id == "cmd-1"
