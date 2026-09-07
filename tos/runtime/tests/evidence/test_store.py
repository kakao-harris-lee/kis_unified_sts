"""``SqliteEvidenceStore`` tests — fault contracts ②④⑤⑦ (design #40 §2 item 1).

Test names are grouped by the fault-contract letter they exercise, matching
the table in ``store.py``'s own module docstring.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from tos_runtime.evidence.store import (
    EvidenceCorruption,
    InjectedCrash,
    SqliteEvidenceStore,
)

from .conftest import FixedKeyProvider

# ============================================================================
# basic append / replay / verify
# ============================================================================


def test_append_returns_receipt_with_seq_zero_for_first_entry(
    store: SqliteEvidenceStore,
) -> None:
    receipt = store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    assert receipt.seq == 0
    assert receipt.durable is True
    assert receipt.key_generation == 1


def test_append_increments_seq(store: SqliteEvidenceStore) -> None:
    r1 = store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    r2 = store.append({"b": 2}, kind="TEST", record_class="TESTCLASS")
    assert r2.seq == r1.seq + 1


def test_replay_and_verify_round_trip(store: SqliteEvidenceStore) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    store.append({"b": 2}, kind="TEST", record_class="TESTCLASS")
    assert store.verify({1: b"test-fixed-key-bytes"}) is True


def test_verify_fails_with_wrong_key(store: SqliteEvidenceStore) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    assert store.verify({1: b"wrong-key"}) is False


def test_verify_or_raise_raises_evidence_corruption_on_wrong_key(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    with pytest.raises(EvidenceCorruption):
        store.verify_or_raise({1: b"wrong-key"})


def test_rotate_signs_new_entries_under_new_generation(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    rotation_receipt = store.rotate(2, b"new-key-bytes")
    assert rotation_receipt.key_generation == 2
    post_rotation = store.append({"b": 2}, kind="TEST", record_class="TESTCLASS")
    assert post_rotation.key_generation == 2
    assert store.verify({1: b"test-fixed-key-bytes", 2: b"new-key-bytes"}) is True


def test_rotate_rejects_non_increasing_generation(store: SqliteEvidenceStore) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    with pytest.raises(ValueError):
        store.rotate(1, b"same-or-lower")


# ============================================================================
# ② — same-seq reinsertion refused (PK)
# ============================================================================


def test_duplicate_seq_insertion_refused_by_primary_key(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    with pytest.raises(sqlite3.IntegrityError):
        store.connection.execute(
            "INSERT INTO entries (seq, segment_id, kind, record_class, "
            "runtime_identity_json, payload_json, entry_digest, chain_digest, "
            "key_generation, appended_at_monotonic_ns) "
            "VALUES (0, NULL, 'X', 'Y', NULL, '{}', 'd', 'c', 1, 0)"
        )


# ============================================================================
# append-only trigger — UPDATE/DELETE forbidden
# ============================================================================


def test_update_on_entries_is_rejected(store: SqliteEvidenceStore) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.connection.execute("UPDATE entries SET kind = 'X' WHERE seq = 0")


def test_delete_on_entries_is_rejected(store: SqliteEvidenceStore) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.connection.execute("DELETE FROM entries WHERE seq = 0")


# ============================================================================
# ④ — durable commit before/after crash
# ============================================================================


def test_crash_before_commit_leaves_entry_absent(tmp_path: Path) -> None:
    path = tmp_path / "crash_before.sqlite3"

    def crash_hook(point: str) -> None:
        if point == "before_commit":
            raise InjectedCrash("simulated process death before COMMIT")

    crashing_store = SqliteEvidenceStore(
        path, key_provider=FixedKeyProvider(), crash_hook=crash_hook
    )
    with pytest.raises(InjectedCrash):
        crashing_store.append({"x": 1}, kind="TEST", record_class="TESTCLASS")
    crashing_store.close()

    reopened = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    last_seq, _, _ = reopened.last_committed()
    assert last_seq is None, "entry must be ABSENT after a before-commit crash"
    reopened.close()


def test_crash_after_commit_before_receipt_leaves_entry_present_and_chain_consistent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "crash_after.sqlite3"

    def crash_hook(point: str) -> None:
        if point == "after_commit_before_receipt":
            raise InjectedCrash("simulated process death after COMMIT, before receipt")

    crashing_store = SqliteEvidenceStore(
        path, key_provider=FixedKeyProvider(), crash_hook=crash_hook
    )
    with pytest.raises(InjectedCrash):
        crashing_store.append({"x": 1}, kind="TEST", record_class="TESTCLASS")
    crashing_store.close()

    reopened = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    last_seq, _, _ = reopened.last_committed()
    assert last_seq == 0, "entry must be PRESENT after an after-commit crash"
    assert reopened.verify({1: b"test-fixed-key-bytes"}) is True
    reopened.close()


def test_append_after_a_crash_continues_the_chain_correctly(tmp_path: Path) -> None:
    """The disjunction holds even for a store instance reused post-crash."""
    path = tmp_path / "crash_continue.sqlite3"
    after_commit_calls: list[str] = []

    def crash_hook(point: str) -> None:
        if point != "after_commit_before_receipt":
            return
        after_commit_calls.append(point)
        if len(after_commit_calls) == 1:
            raise InjectedCrash("one-shot crash on the first append only")

    crashing_store = SqliteEvidenceStore(
        path, key_provider=FixedKeyProvider(), crash_hook=crash_hook
    )
    with pytest.raises(InjectedCrash):
        crashing_store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    # the SAME instance is reused for the next append (no crash this time)
    crashing_store._crash_hook = None
    second_receipt = crashing_store.append(
        {"b": 2}, kind="TEST", record_class="TESTCLASS"
    )
    assert second_receipt.seq == 1
    assert crashing_store.verify({1: b"test-fixed-key-bytes"}) is True
    crashing_store.close()


# ============================================================================
# ⑦ — storage failure never yields a partial commit
# ============================================================================


def test_sqlite_failure_during_append_rolls_back_and_raises(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")

    def crash_hook(point: str) -> None:
        if point == "before_commit":
            raise sqlite3.OperationalError("simulated disk-full / locked-file failure")

    store._crash_hook = crash_hook
    with pytest.raises(sqlite3.OperationalError):
        store.append({"b": 2}, kind="TEST", record_class="TESTCLASS")
    store._crash_hook = None

    # the failed append never landed — the next append still gets seq=1, not 2
    receipt = store.append({"c": 3}, kind="TEST", record_class="TESTCLASS")
    assert receipt.seq == 1
    assert store.verify({1: b"test-fixed-key-bytes"}) is True


# ============================================================================
# scrubbing — plaintext secret never reaches the sqlite file bytes
# ============================================================================


def test_secret_fields_are_scrubbed_before_they_reach_the_raw_sqlite_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scrubbed.sqlite3"
    secret_value = "sk-super-secret-plaintext-marker-987654321"
    scrubbing_store = SqliteEvidenceStore(
        path,
        key_provider=FixedKeyProvider(),
        secret_keys=frozenset({"api_key"}),
    )
    scrubbing_store.append(
        {
            "account": "acct-1",
            "api_key": secret_value,
            "nested": {"api_key": secret_value},
        },
        kind="TEST",
        record_class="TESTCLASS",
    )
    scrubbing_store.close()

    raw_bytes = path.read_bytes()
    assert secret_value.encode("utf-8") not in raw_bytes


def test_non_secret_fields_are_not_scrubbed(store: SqliteEvidenceStore) -> None:
    store2 = SqliteEvidenceStore(
        store.path.parent / "scrub2.sqlite3",
        key_provider=FixedKeyProvider(),
        secret_keys=frozenset({"api_key"}),
    )
    store2.append(
        {"account": "acct-1", "api_key": "shh"}, kind="TEST", record_class="TESTCLASS"
    )
    row = store2.connection.execute(
        "SELECT payload_json FROM entries WHERE seq = 0"
    ).fetchone()
    assert "acct-1" in row[0]
    assert "shh" not in row[0]
    store2.close()
