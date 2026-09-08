"""``tos_runtime.evidence.backup`` tests — snapshot/restore, always a new non-live generation."""

from __future__ import annotations

from pathlib import Path

from tos_runtime.evidence.backup import backup, restore
from tos_runtime.evidence.store import SqliteEvidenceStore

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
