"""``tos_runtime.evidence.emergency`` tests — dual-path HALT durability."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tos.evidence import DurabilityClass
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore


def test_record_halt_writes_to_both_paths(
    tmp_path: Path, store: SqliteEvidenceStore
) -> None:
    log = EmergencyAppendLog(tmp_path / "emergency.jsonl")
    receipt = record_halt(
        store,
        log,
        payload={"reason": "TEST_HALT"},
        kind="FLOW_HALTED",
        record_class="HALT",
    )
    assert receipt.seq == 0
    lines = (tmp_path / "emergency.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    assert "TEST_HALT" in lines[0]
    assert str(receipt.seq) in lines[0] or f'"seq":{receipt.seq}' in lines[0]


def test_record_halt_fsyncs_exactly_once_per_call(
    tmp_path: Path, store: SqliteEvidenceStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = EmergencyAppendLog(tmp_path / "emergency.jsonl")
    calls: list[int] = []
    real_fsync = os.fsync

    def counting_fsync(fd: int) -> None:
        calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", counting_fsync)
    record_halt(
        store, log, payload={"reason": "H1"}, kind="FLOW_HALTED", record_class="HALT"
    )
    assert len(calls) == 1
    record_halt(
        store, log, payload={"reason": "H2"}, kind="FLOW_HALTED", record_class="HALT"
    )
    assert len(calls) == 2


def test_record_halt_refuses_non_emergency_durability_class(
    tmp_path: Path, store: SqliteEvidenceStore
) -> None:
    log = EmergencyAppendLog(tmp_path / "emergency.jsonl")
    with pytest.raises(ValueError, match="EMERGENCY_DURABLE"):
        record_halt(
            store,
            log,
            payload={},
            kind="X",
            record_class="Y",
            durability_class=DurabilityClass.DERIVED_REBUILDABLE,
        )
    assert not (tmp_path / "emergency.jsonl").exists()


def test_record_halt_raises_and_does_not_report_success_when_emergency_log_write_fails(
    tmp_path: Path, store: SqliteEvidenceStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = EmergencyAppendLog(tmp_path / "emergency.jsonl")

    def failing_fsync(fd: int) -> None:
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(os, "fsync", failing_fsync)
    with pytest.raises(OSError):
        record_halt(
            store, log, payload={"reason": "X"}, kind="FLOW_HALTED", record_class="HALT"
        )
    # the sqlite side is already durably committed (irreversible) even though
    # record_halt raised overall — the whole point is the CALLER never
    # receives a receipt claiming both paths succeeded.
    last_seq, _, _ = store.last_committed()
    assert last_seq == 0


def test_record_halt_raises_when_store_append_fails_before_touching_emergency_log(
    tmp_path: Path, store: SqliteEvidenceStore
) -> None:
    log = EmergencyAppendLog(tmp_path / "emergency.jsonl")

    def crash_hook(point: str) -> None:
        if point == "before_commit":
            raise RuntimeError("simulated store failure")

    store._crash_hook = crash_hook
    with pytest.raises(RuntimeError):
        record_halt(
            store, log, payload={"reason": "X"}, kind="FLOW_HALTED", record_class="HALT"
        )
    store._crash_hook = None
    assert not (tmp_path / "emergency.jsonl").exists()
