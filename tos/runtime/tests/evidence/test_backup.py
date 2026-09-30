"""``tos_runtime.evidence.backup`` tests — snapshot/restore, always a new non-live generation."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from tos_runtime.evidence.backup import backup, restore
from tos_runtime.evidence.store import EvidenceCorruption, SqliteEvidenceStore

from .conftest import FixedKeyProvider


def test_backup_writes_a_manifest_matching_the_live_tail(
    tmp_path: Path, store: SqliteEvidenceStore
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    store.append({"b": 2}, kind="TEST", record_class="TESTCLASS")
    live_last_seq, live_chain_digest, live_key_generation = store.last_committed()

    manifest = backup(store, tmp_path, generation=1)

    assert manifest.last_seq == live_last_seq
    assert manifest.chain_digest == live_chain_digest
    assert manifest.key_generation == live_key_generation
    assert Path(manifest.backup_path).exists()


def test_restore_lands_a_new_non_live_generation_with_matching_tail(
    tmp_path: Path, store: SqliteEvidenceStore
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    manifest_path = tmp_path / "evidence-backup-gen1.manifest.json"
    backup(store, tmp_path, generation=1)

    result = restore(
        manifest_path,
        dest_path=tmp_path / "restored.sqlite3",
        new_generation=42,
        key_provider=FixedKeyProvider(),
    )
    try:
        assert result.new_generation == 42
        assert result.non_live is True
        assert result.store.last_committed()[0] == store.last_committed()[0]
        assert result.store.verify({1: b"test-fixed-key-bytes"}) is True
    finally:
        result.store.close()


def test_restore_never_mutates_the_original_backup_file(
    tmp_path: Path, store: SqliteEvidenceStore
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    manifest = backup(store, tmp_path, generation=1)
    backup_bytes_before = Path(manifest.backup_path).read_bytes()

    result = restore(
        tmp_path / "evidence-backup-gen1.manifest.json",
        dest_path=tmp_path / "restored.sqlite3",
        new_generation=2,
        key_provider=FixedKeyProvider(),
    )
    result.store.append(
        {"only_in_restored": True}, kind="TEST", record_class="TESTCLASS"
    )
    result.store.close()

    backup_bytes_after = Path(manifest.backup_path).read_bytes()
    assert backup_bytes_before == backup_bytes_after


def test_restore_with_live_store_records_no_divergence_when_tails_match(
    tmp_path: Path, store: SqliteEvidenceStore
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    backup(store, tmp_path, generation=1)

    result = restore(
        tmp_path / "evidence-backup-gen1.manifest.json",
        dest_path=tmp_path / "restored.sqlite3",
        new_generation=2,
        key_provider=FixedKeyProvider(),
        live_store=store,
    )
    result.store.close()

    metas = list(store.iter_entry_meta())
    comparison_rows = [m for m in metas if m.kind == "RESTORE_COMPARISON"]
    assert len(comparison_rows) == 1


def test_restore_with_live_store_detects_divergence_after_further_live_appends(
    tmp_path: Path, store: SqliteEvidenceStore
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    backup(store, tmp_path, generation=1)
    # the live store keeps moving after the snapshot was taken
    store.append({"b": 2}, kind="TEST", record_class="TESTCLASS")

    result = restore(
        tmp_path / "evidence-backup-gen1.manifest.json",
        dest_path=tmp_path / "restored.sqlite3",
        new_generation=2,
        key_provider=FixedKeyProvider(),
        live_store=store,
    )
    result.store.close()

    metas = list(store.iter_entry_meta())
    comparison_seq = [m.seq for m in metas if m.kind == "RESTORE_COMPARISON"][0]
    row = store.connection.execute(
        "SELECT payload_json FROM entries WHERE seq = ?", (comparison_seq,)
    ).fetchone()
    assert '"branches_diverged":true' in row[0]


def test_a_failed_verification_closes_the_restored_store(tmp_path: Path, store) -> None:
    """A restore that refuses must not hand back an exception holding an OPEN connection.

    ``restore`` constructs the store first and verifies it second, so a corrupt chain raises
    with the store fully built and nobody holding a reference to close it. The raising frame is
    kept alive by the exception's traceback, so the connection and its ``-wal``/``-shm`` live as
    long as the caller keeps the exception — unbounded for an operator CLI that catches and
    reports (review round-3 F2, the same leak class the store constructors close one frame down).

    The corruption is made the way a real one would show: a row of the restored copy is rewritten
    after the backup, so the chain digest no longer matches. The connection is then reached
    through the traceback, which is the only reference a raising call leaves behind.
    """
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    manifest_path = tmp_path / "evidence-backup-gen1.manifest.json"
    manifest = backup(store, tmp_path, generation=1)

    # Corrupt the BACKUP file, so the restored copy fails its own verification. The append-only
    # trigger has to go first — which is the point: this is tampering with a file at rest, the
    # thing the chain digest exists to detect, not a write through the store's own API.
    tamper = sqlite3.connect(manifest.backup_path, isolation_level=None)
    try:
        tamper.execute("DROP TRIGGER entries_no_update")
        tamper.execute("UPDATE entries SET chain_digest = 'deadbeef' || chain_digest")
    finally:
        tamper.close()

    with pytest.raises(EvidenceCorruption) as refusal:
        restore(
            manifest_path,
            dest_path=tmp_path / "restored.sqlite3",
            new_generation=42,
            key_provider=FixedKeyProvider(),
        )

    restored: sqlite3.Connection | None = None
    tb = refusal.value.__traceback__
    while tb is not None:
        candidate = tb.tb_frame.f_locals.get("restored_store")
        conn = getattr(candidate, "_conn", None)
        if isinstance(conn, sqlite3.Connection):
            restored = conn
        tb = tb.tb_next
    assert restored is not None, "no restore frame holding the restored store"
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        restored.execute("SELECT 1")
