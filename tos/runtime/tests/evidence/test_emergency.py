"""``tos_runtime.evidence.emergency`` tests — dual-path HALT durability."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from tos.evidence import DurabilityClass
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore

from .conftest import FixedKeyProvider


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


# ============================================================================
# HIGH-1 (2026-09-08 independent review) — the JSONL copy must be scrubbed too
# ============================================================================


def test_emergency_log_never_contains_the_raw_secret_bytes(tmp_path: Path) -> None:
    """The secret must be absent from the RAW JSONL file bytes, not just sqlite.

    An earlier revision wrote the caller's raw ``payload`` straight to the
    JSONL line — only the sqlite side was ever scrubbed. This greps the
    emergency log's own file bytes (never the store) for the secret.
    """
    secret_value = "sk-emergency-secret-marker-13579246800"
    scrubbing_store = SqliteEvidenceStore(
        tmp_path / "scrubbing_evidence.sqlite3",
        key_provider=FixedKeyProvider(),
        secret_keys=frozenset({"api_key"}),
    )
    log = EmergencyAppendLog(tmp_path / "emergency.jsonl")
    record_halt(
        scrubbing_store,
        log,
        payload={"account": "acct-1", "api_key": secret_value},
        kind="FLOW_HALTED",
        record_class="HALT",
    )
    scrubbing_store.close()

    raw_bytes = (tmp_path / "emergency.jsonl").read_bytes()
    assert secret_value.encode("utf-8") not in raw_bytes


def test_sqlite_and_jsonl_copies_of_a_halt_record_carry_the_same_scrubbed_payload(
    tmp_path: Path,
) -> None:
    """Both durable copies of one HALT record must be byte-identically scrubbed."""
    scrubbing_store = SqliteEvidenceStore(
        tmp_path / "scrubbing_evidence2.sqlite3",
        key_provider=FixedKeyProvider(),
        secret_keys=frozenset({"api_key"}),
    )
    log = EmergencyAppendLog(tmp_path / "emergency2.jsonl")
    receipt = record_halt(
        scrubbing_store,
        log,
        payload={"account": "acct-1", "api_key": "shh-secret"},
        kind="FLOW_HALTED",
        record_class="HALT",
    )

    sqlite_row = scrubbing_store.connection.execute(
        "SELECT payload_json FROM entries WHERE seq = ?", (receipt.seq,)
    ).fetchone()
    sqlite_payload = json.loads(sqlite_row[0])["payload"]
    scrubbing_store.close()

    jsonl_line = (tmp_path / "emergency2.jsonl").read_text().strip().splitlines()[0]
    jsonl_payload = json.loads(jsonl_line)["payload"]

    assert sqlite_payload == jsonl_payload
    assert sqlite_payload["api_key"] == "***REDACTED***"
