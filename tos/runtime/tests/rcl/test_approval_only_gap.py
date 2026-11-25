"""Fail-closed RCL history checks for proof-tip advancement."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tos.rcl import AppendReceipt, AppendRefusal, CommandType, CommitEntry
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.log import SqliteCommitLog

from .conftest import FakeEvidenceAppendPort


def _seq(receipt: AppendReceipt) -> int:
    assert receipt.seq is not None
    return receipt.seq


def _append(
    log: SqliteCommitLog,
    *,
    epoch: int,
    expected_seq: int,
    command_id: str,
    kind: CommandType,
) -> AppendReceipt:
    result = log.append_cas(
        CommitEntry(
            command_id=command_id,
            command_digest=f"digest-{command_id}",
            kind=kind,
        ),
        expected_seq=expected_seq,
        writer_epoch=epoch,
        payload_json=json.dumps({"command": command_id}),
    )
    assert isinstance(result, AppendReceipt)
    return result


def _insert_raw_entry(
    log: SqliteCommitLog,
    *,
    seq: int,
    epoch: int,
    command_id: str,
    kind: str,
    payload: str,
    is_reservation_transition: int = 0,
) -> None:
    log._conn.execute(
        "INSERT INTO entries (seq, writer_epoch, command_id, command_digest, kind, "
        "payload_digest, payload_json, is_reservation_transition) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            seq,
            epoch,
            command_id,
            f"digest-{command_id}",
            kind,
            None,
            payload,
            is_reservation_transition,
        ),
    )


def test_approval_only_gap_returns_verified_current_tip(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    first = _append(
        log,
        epoch=epoch,
        expected_seq=-1,
        command_id="cmd-proof-anchor",
        kind=CommandType.CONSUME_APPROVAL_DECISION,
    )
    proof_tip = _seq(first)
    second = _append(
        log,
        epoch=epoch,
        expected_seq=proof_tip,
        command_id="cmd-approval-2",
        kind=CommandType.CONSUME_APPROVAL_DECISION,
    )
    third = _append(
        log,
        epoch=epoch,
        expected_seq=_seq(second),
        command_id="cmd-approval-3",
        kind=CommandType.CONSUME_APPROVAL_DECISION,
    )

    snapshot = log.read_approval_only_gap(writer_epoch=epoch, proof_last_seq=proof_tip)

    assert snapshot is not None
    assert snapshot.epoch == epoch
    assert snapshot.last_seq == _seq(third)
    assert snapshot.entries == ()


def test_approval_only_gap_rejects_non_approval_command(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    anchor = _append(
        log,
        epoch=epoch,
        expected_seq=-1,
        command_id="cmd-proof-anchor",
        kind=CommandType.CONSUME_APPROVAL_DECISION,
    )
    _append(
        log,
        epoch=epoch,
        expected_seq=_seq(anchor),
        command_id="cmd-fill",
        kind=CommandType.RECORD_FILL_AND_TRANSFER_USAGE,
    )

    assert (
        log.read_approval_only_gap(writer_epoch=epoch, proof_last_seq=_seq(anchor))
        is None
    )


def test_approval_kind_with_reservation_discriminator_is_rejected(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    anchor = _append(
        log,
        epoch=epoch,
        expected_seq=-1,
        command_id="cmd-proof-anchor",
        kind=CommandType.CONSUME_APPROVAL_DECISION,
    )
    _insert_raw_entry(
        log,
        seq=_seq(anchor) + 1,
        epoch=epoch,
        command_id="cmd-discriminated-approval",
        kind=CommandType.CONSUME_APPROVAL_DECISION.value,
        payload="{}",
        is_reservation_transition=1,
    )

    assert (
        log.read_approval_only_gap(writer_epoch=epoch, proof_last_seq=_seq(anchor))
        is None
    )


@pytest.mark.parametrize(
    ("seq_offset", "kind", "payload"),
    [
        (1, "UnknownCommand", "{}"),
        (1, CommandType.CONSUME_APPROVAL_DECISION.value, "not-json"),
        (1, CommandType.CONSUME_APPROVAL_DECISION.value, "[]"),
        (2, CommandType.CONSUME_APPROVAL_DECISION.value, "{}"),
    ],
)
def test_approval_only_gap_rejects_unknown_malformed_and_noncontiguous_rows(
    log: SqliteCommitLog,
    identity: RuntimeIdentity,
    seq_offset: int,
    kind: str,
    payload: str,
) -> None:
    epoch = log.acquire_epoch(identity)
    anchor = _append(
        log,
        epoch=epoch,
        expected_seq=-1,
        command_id="cmd-proof-anchor",
        kind=CommandType.CONSUME_APPROVAL_DECISION,
    )
    _insert_raw_entry(
        log,
        seq=_seq(anchor) + seq_offset,
        epoch=epoch,
        command_id="cmd-invalid-row",
        kind=kind,
        payload=payload,
    )

    assert (
        log.read_approval_only_gap(writer_epoch=epoch, proof_last_seq=_seq(anchor))
        is None
    )


def test_approval_only_gap_rejects_stale_epoch_and_invalid_proof_tip(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    stale_epoch = log.acquire_epoch(identity)
    anchor = _append(
        log,
        epoch=stale_epoch,
        expected_seq=-1,
        command_id="cmd-proof-anchor",
        kind=CommandType.CONSUME_APPROVAL_DECISION,
    )
    current_epoch = log.acquire_epoch(identity)

    assert (
        log.read_approval_only_gap(
            writer_epoch=stale_epoch, proof_last_seq=_seq(anchor)
        )
        is None
    )
    assert (
        log.read_approval_only_gap(
            writer_epoch=current_epoch, proof_last_seq=_seq(anchor) + 1
        )
        is None
    )


def test_approval_only_snapshot_tip_cannot_cas_over_concurrent_append(
    log_path: Path,
    evidence_port: FakeEvidenceAppendPort,
    identity: RuntimeIdentity,
) -> None:
    first = SqliteCommitLog(log_path, evidence_port=evidence_port)
    second = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        epoch = first.acquire_epoch(identity)
        anchor = _append(
            first,
            epoch=epoch,
            expected_seq=-1,
            command_id="cmd-proof-anchor",
            kind=CommandType.CONSUME_APPROVAL_DECISION,
        )
        original_current_epoch = first.current_epoch
        concurrent_receipts: list[AppendReceipt] = []

        def append_after_snapshot_begins() -> int:
            current = original_current_epoch()
            view = second.read_linearizable(writer_epoch=epoch)
            expected = -1 if view.last_seq is None else view.last_seq
            concurrent_receipts.append(
                _append(
                    second,
                    epoch=epoch,
                    expected_seq=expected,
                    command_id="cmd-concurrent-approval",
                    kind=CommandType.CONSUME_APPROVAL_DECISION,
                )
            )
            return current

        first.current_epoch = append_after_snapshot_begins  # type: ignore[method-assign]
        snapshot = first.read_approval_only_gap(
            writer_epoch=epoch, proof_last_seq=_seq(anchor)
        )
        first.current_epoch = original_current_epoch  # type: ignore[method-assign]

        assert snapshot is not None
        assert snapshot.epoch == epoch
        assert snapshot.last_seq == _seq(anchor)
        assert len(concurrent_receipts) == 1
        result = first.append_cas(
            CommitEntry(
                command_id="cmd-close-after-race",
                command_digest="digest-close-after-race",
                kind=CommandType.RECORD_FILL_AND_TRANSFER_USAGE,
            ),
            expected_seq=-1 if snapshot.last_seq is None else snapshot.last_seq,
            writer_epoch=epoch,
        )
        assert isinstance(result, AppendRefusal)
    finally:
        first.close()
        second.close()
