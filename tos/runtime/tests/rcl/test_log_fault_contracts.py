"""``SqliteCommitLog`` tests — fault contracts ①②③④⑤⑥⑦ (slice plan §1)."""

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
    ReservationScope,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.log import CommitLogCorruption, InjectedCrash, SqliteCommitLog

from .conftest import FakeEvidenceAppendPort, FakeMonotonicClock

DEFAULT_SCOPE = ReservationScope(account="acct-1", instrument="101S06")


def _seq(receipt: AppendReceipt) -> int:
    """``receipt.seq``, asserted present — a successful ``append_cas`` never"""
    assert receipt.seq is not None
    return receipt.seq


def test_fault_1_stale_writer_epoch_is_refused(
    log_path: Path, evidence_port: FakeEvidenceAppendPort, identity: RuntimeIdentity
) -> None:
    first = SqliteCommitLog(log_path, evidence_port=evidence_port)
    second = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        stale_epoch = first.acquire_epoch(identity)
        current_epoch = second.acquire_epoch(identity)
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


def test_fault_2_duplicate_command_id_same_bytes_is_idempotent_refusal(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    entry = CommitEntry(
        command_id="cmd-1", command_digest="dig-1", kind=CommandType.COMMIT_RESERVATION
    )
    first = log.append_cas(entry, expected_seq=-1, writer_epoch=epoch)
    assert isinstance(first, AppendReceipt)

    second = log.append_cas(entry, expected_seq=_seq(first), writer_epoch=epoch)
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
        conflicting_entry, expected_seq=_seq(first), writer_epoch=epoch
    )
    assert isinstance(second, AppendRefusal)
    assert second.reason == AppendRefusalReason.COMMAND_BYTES_MISMATCH


def test_null_digest_duplicate_command_is_classified_as_duplicate_not_partial_commit(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    entry = CommitEntry(
        command_id="cmd-1", command_digest=None, kind=CommandType.COMMIT_RESERVATION
    )
    first = log.append_cas(entry, expected_seq=-1, writer_epoch=epoch)
    assert isinstance(first, AppendReceipt)

    second = log.append_cas(entry, expected_seq=_seq(first), writer_epoch=epoch)

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
        conflicting_entry, expected_seq=_seq(first), writer_epoch=epoch
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
        conflicting_entry, expected_seq=_seq(first), writer_epoch=epoch
    )

    assert isinstance(second, AppendRefusal)
    assert second.reason == AppendRefusalReason.COMMAND_BYTES_MISMATCH


def test_fault_3_locked_file_prevents_opening_a_second_handle(
    log_path: Path, evidence_port: FakeEvidenceAppendPort
) -> None:
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


def test_evidence_over_records_but_never_under_records_on_post_evidence_rollback(
    log_path: Path, evidence_port: FakeEvidenceAppendPort, identity: RuntimeIdentity
) -> None:
    def crash_after_evidence_before_commit(point: str) -> None:
        if point == "before_commit":
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

    assert len(evidence_port.calls) == 1
    recorded_payload, _kind, _record_class = evidence_port.calls[0]
    assert recorded_payload["command_id"] == "cmd-1"

    reopened = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        assert list(reopened.replay()) == []
    finally:
        reopened.close()


def test_fault_5_replay_mismatch_raises_commit_log_corruption(
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

    log.verify_replay()

    log._conn.execute(
        "UPDATE reservations SET state = ? WHERE reservation_id = ?",
        (CapacityState.QUARANTINED_UNKNOWN.value, "res-1"),
    )

    with pytest.raises(CommitLogCorruption):
        log.verify_replay()


def test_fault_5_verify_replay_passes_on_empty_log(log: SqliteCommitLog) -> None:
    log.verify_replay()


def test_fault_5_scope_tamper_raises_commit_log_corruption(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """(laneO port-fix round, design #40 runtime slice #2 §5, 2026-09-08) A"""
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

    log.verify_replay()

    log._conn.execute(
        "UPDATE reservations SET scope_account = ? WHERE reservation_id = ?",
        ("acct-tampered", "res-1"),
    )

    with pytest.raises(CommitLogCorruption):
        log.verify_replay()


def test_ghost_reservation_payload_via_append_cas_does_not_forge_corruption(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """A plain ``append_cas`` call whose ``payload_json`` happens to decode to"""
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
    assert {rid: state for rid, state, _seq, _scope in log.reservation_rows()} == {}
    log.verify_replay()


def test_genuine_reservations_row_tamper_still_raises_after_medium_4_fix(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """Regression guard: a REAL disagreement (the held ``reservations`` row"""
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
    log.verify_replay()

    log._conn.execute(
        "UPDATE reservations SET state = ? WHERE reservation_id = ?",
        (CapacityState.QUARANTINED_UNKNOWN.value, "res-1"),
    )

    with pytest.raises(CommitLogCorruption):
        log.verify_replay()


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

        clock.value = 0
        epoch_2 = instance.acquire_epoch(identity)
        assert epoch_2 > epoch_1

        entry_b = CommitEntry(
            command_id="cmd-b",
            command_digest="dig-b",
            kind=CommandType.COMMIT_RESERVATION,
        )
        receipt_b = instance.append_cas(
            entry_b, expected_seq=_seq(receipt_a), writer_epoch=epoch_2
        )
        assert isinstance(receipt_b, AppendReceipt)
        assert receipt_a.seq is not None
        assert receipt_b.seq == receipt_a.seq + 1
    finally:
        instance.close()


def test_fault_7_simulated_mid_transaction_failure_refuses_and_rolls_back(
    log_path: Path, evidence_port: FakeEvidenceAppendPort, identity: RuntimeIdentity
) -> None:
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
        assert instance._current_seq_tip() == -1
        assert list(instance.replay()) == []
    finally:
        instance.close()


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
    result = log.append_cas(entry, expected_seq=5, writer_epoch=epoch)
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
