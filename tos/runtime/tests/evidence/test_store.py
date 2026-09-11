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


# ============================================================================
# LOW-4 (2026-09-08 independent review) — verify_detailed distinguishes
# "0 links, vacuously ok" from "N links, genuinely verified"
# ============================================================================


def test_verify_detailed_on_empty_store_is_ok_with_zero_verified_links(
    store: SqliteEvidenceStore,
) -> None:
    result = store.verify_detailed({1: b"test-fixed-key-bytes"})
    assert result.ok is True
    assert result.verified_links == 0
    assert result.last_seq is None


def test_verify_detailed_on_non_empty_store_reports_the_real_link_count(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    store.append({"b": 2}, kind="TEST", record_class="TESTCLASS")
    store.append({"c": 3}, kind="TEST", record_class="TESTCLASS")
    result = store.verify_detailed({1: b"test-fixed-key-bytes"})
    assert result.ok is True
    assert result.verified_links == 3
    assert result.last_seq == 2


def test_verify_detailed_on_corrupted_chain_is_not_ok_with_zero_verified_links(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    result = store.verify_detailed({1: b"wrong-key"})
    assert result.ok is False
    assert result.verified_links == 0


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


def test_successful_rotate_leaves_exactly_one_marker_and_new_key_only_thereafter(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    store.rotate(2, b"new-key-bytes")
    store.append({"b": 2}, kind="TEST", record_class="TESTCLASS")

    metas = list(store.iter_entry_meta())
    rotation_markers = [m for m in metas if m.kind == "KEY_ROTATION"]
    assert len(rotation_markers) == 1
    assert rotation_markers[0].key_generation == 2

    # the post-rotation entry does NOT verify under the old key alone —
    # it was signed under the new generation.
    assert store.verify({1: b"test-fixed-key-bytes"}) is False
    assert store.verify({1: b"test-fixed-key-bytes", 2: b"new-key-bytes"}) is True


# ============================================================================
# MEDIUM-3 (2026-09-08 independent review) — rotate() must be atomic
# ============================================================================


def test_rotate_is_atomic_a_failed_rotation_commit_leaves_generation_unchanged(
    store: SqliteEvidenceStore,
) -> None:
    """Force the rotation-commit append itself to fail (read-only pragma, per
    the reviewer's own repro) and prove the store's scheme/generation, its
    verifiability under the OLD key, and its entry count are all untouched —
    a failed rotate() must never leave a "new generation with no committed
    marker" state (the bug this test guards against).
    """
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    entries_before = store.connection.execute(
        "SELECT COUNT(*) FROM entries"
    ).fetchone()[0]

    store.connection.execute("PRAGMA query_only=ON")
    try:
        with pytest.raises(sqlite3.OperationalError):
            store.rotate(2, b"new-key-bytes")
    finally:
        store.connection.execute("PRAGMA query_only=OFF")

    assert (
        store.key_generation == 1
    ), "generation must be UNCHANGED after a failed rotate"
    entries_after = store.connection.execute("SELECT COUNT(*) FROM entries").fetchone()[
        0
    ]
    assert entries_after == entries_before, "no rotation-commit marker may exist"
    assert store.verify({1: b"test-fixed-key-bytes"}) is True

    # the store must still be usable under the OLD key after the failed rotate
    receipt = store.append({"c": 3}, kind="TEST", record_class="TESTCLASS")
    assert receipt.key_generation == 1


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


def test_last_committed_excluding_ignores_the_named_kinds(
    store: SqliteEvidenceStore,
) -> None:
    """W3.1 independent review HIGH-1: a self-perturbing observer (a writer whose own
    appends the SAME reader would otherwise see as tip advancement) needs a view of the
    tip that excludes its own writes. ``last_committed_excluding`` is that view."""
    store.append({"a": 1}, kind="OTHER", record_class="OTHERCLASS")
    seq_before_alert, digest_before_alert, _ = store.last_committed_excluding(
        frozenset({"ALERT"})
    )
    assert seq_before_alert == 0

    store.append({"a": 2}, kind="ALERT", record_class="ALERTCLASS")
    # last_committed() (unfiltered) sees the ALERT row -- that is the flap this method
    # exists to avoid for a caller wired against its own alert sink.
    unfiltered_seq, _, _ = store.last_committed()
    assert unfiltered_seq == 1

    seq_after_alert, digest_after_alert, _ = store.last_committed_excluding(
        frozenset({"ALERT"})
    )
    assert seq_after_alert == 0
    assert digest_after_alert == digest_before_alert


def test_last_committed_excluding_reflects_a_genuine_non_excluded_append(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="OTHER", record_class="OTHERCLASS")
    store.append({"a": 2}, kind="ALERT", record_class="ALERTCLASS")
    store.append({"a": 3}, kind="OTHER", record_class="OTHERCLASS")
    seq, _, _ = store.last_committed_excluding(frozenset({"ALERT"}))
    assert seq == 2


def test_last_committed_excluding_empty_store_matches_last_committed(
    store: SqliteEvidenceStore,
) -> None:
    excluded = store.last_committed_excluding(frozenset({"ALERT"}))
    plain = store.last_committed()
    assert excluded == plain


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


class _RollbackFailingConnection:
    """A thin proxy that forces ``ROLLBACK`` to raise, forwarding everything else.

    LOW-6 (2026-09-08 independent review) test double: simulates a real
    sqlite connection whose ``ROLLBACK`` statement itself fails, so the test
    can prove the ORIGINAL commit-path exception still propagates instead of
    being replaced by this one.
    """

    def __init__(
        self, real_conn: sqlite3.Connection, rollback_error: Exception
    ) -> None:
        self._real = real_conn
        self._rollback_error = rollback_error

    def execute(self, sql: str, *args: object, **kwargs: object) -> sqlite3.Cursor:
        if sql.strip().upper() == "ROLLBACK":
            raise self._rollback_error
        return self._real.execute(sql, *args, **kwargs)  # type: ignore[arg-type]

    def __getattr__(self, name: str) -> object:
        return getattr(self._real, name)


def test_rollback_failure_does_not_mask_the_original_commit_error(
    store: SqliteEvidenceStore,
) -> None:
    """Force BOTH the commit-path AND the rollback itself to fail; the
    ORIGINAL error type must be what propagates, not the rollback failure's.
    """

    class _OriginalCommitFailure(RuntimeError):
        pass

    class _RollbackFailure(RuntimeError):
        pass

    def crash_hook(point: str) -> None:
        if point == "before_commit":
            raise _OriginalCommitFailure("the real, original commit-path error")

    store._crash_hook = crash_hook
    store._conn = _RollbackFailingConnection(  # type: ignore[assignment]
        store._conn, _RollbackFailure("rollback itself also failed")
    )

    with pytest.raises(_OriginalCommitFailure) as exc_info:
        store.append({"x": 1}, kind="TEST", record_class="TESTCLASS")

    # never the rollback failure's type
    assert not isinstance(exc_info.value, _RollbackFailure)
    # the rollback failure is recorded, not silently dropped
    notes = getattr(exc_info.value, "__notes__", [])
    assert any("ROLLBACK also failed" in note for note in notes)


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
