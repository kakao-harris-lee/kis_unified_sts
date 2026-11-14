"""Sqlite ``Connection.backup``-based backup/restore (design #40 D3, §2 item 4)."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore
from tos_runtime.operations.schema_ledger import closing_on_failure

__all__ = ["BackupManifest", "RestoreComparison", "RestoredStore", "backup", "restore"]


class BackupManifest(BaseModel):
    """The snapshot manifest ``backup()`` writes beside the backup file."""

    model_config = ConfigDict(frozen=True)

    file_digest: str
    last_seq: int | None
    chain_digest: str
    key_generation: int | None
    generation: int
    source_path: str
    backup_path: str


class RestoreComparison(BaseModel):
    """The durable record of one restore's tail comparison against a live store."""

    model_config = ConfigDict(frozen=True)

    manifest_file_digest: str
    restored_last_seq: int | None
    restored_chain_digest: str
    live_last_seq: int | None = None
    live_chain_digest: str | None = None
    branches_diverged: bool | None = None


class RestoredStore(BaseModel):
    """The result of one :func:`restore` call — always a new, non-live generation."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    store: SqliteEvidenceStore
    new_generation: int
    non_live: Literal[True] = True


def backup(
    store: SqliteEvidenceStore, dest_dir: Path, generation: int
) -> BackupManifest:
    """Snapshot ``store`` into ``dest_dir`` and write its manifest."""
    backup_path = dest_dir / f"evidence-backup-gen{generation}.sqlite3"
    dest_conn = sqlite3.connect(str(backup_path))
    try:
        store.connection.backup(dest_conn)
    finally:
        dest_conn.close()
    file_digest = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    last_seq, chain_digest, key_generation = store.last_committed()
    manifest = BackupManifest(
        file_digest=file_digest,
        last_seq=last_seq,
        chain_digest=chain_digest,
        key_generation=key_generation,
        generation=generation,
        source_path=str(store.path),
        backup_path=str(backup_path),
    )
    manifest_path = dest_dir / f"evidence-backup-gen{generation}.manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2))
    return manifest


def restore(
    manifest_path: Path,
    *,
    dest_path: Path,
    new_generation: int,
    key_provider: KeyProvider,
    live_store: SqliteEvidenceStore | None = None,
) -> RestoredStore:
    """Restore a snapshot into a fresh, independently-numbered, non-live store."""
    manifest = BackupManifest.model_validate_json(manifest_path.read_text())
    source_conn = sqlite3.connect(manifest.backup_path)
    try:
        dest_conn = sqlite3.connect(str(dest_path))
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        source_conn.close()

    restored_store = SqliteEvidenceStore(dest_path, key_provider=key_provider)
    with closing_on_failure(restored_store):
        key_generation, key_bytes = key_provider.current()
        restored_store.verify_or_raise({key_generation: key_bytes})

        restored_last_seq, restored_chain_digest, _ = restored_store.last_committed()
        comparison = _build_comparison(
            manifest, restored_last_seq, restored_chain_digest, live_store
        )
        if live_store is not None:
            live_store.append(
                comparison.model_dump(mode="json"),
                kind="RESTORE_COMPARISON",
                record_class="RESTORE_COMPARISON",
            )

    return RestoredStore(
        store=restored_store, new_generation=new_generation, non_live=True
    )


def _build_comparison(
    manifest: BackupManifest,
    restored_last_seq: int | None,
    restored_chain_digest: str,
    live_store: SqliteEvidenceStore | None,
) -> RestoreComparison:
    """Build the :class:`RestoreComparison` for one restore call."""
    if live_store is None:
        return RestoreComparison(
            manifest_file_digest=manifest.file_digest,
            restored_last_seq=restored_last_seq,
            restored_chain_digest=restored_chain_digest,
        )
    live_last_seq, live_chain_digest, _ = live_store.last_committed()
    diverged = (
        restored_last_seq != live_last_seq or restored_chain_digest != live_chain_digest
    )
    return RestoreComparison(
        manifest_file_digest=manifest.file_digest,
        restored_last_seq=restored_last_seq,
        restored_chain_digest=restored_chain_digest,
        live_last_seq=live_last_seq,
        live_chain_digest=live_chain_digest,
        branches_diverged=diverged,
    )
