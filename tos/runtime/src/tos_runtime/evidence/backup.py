"""Sqlite ``Connection.backup``-based backup/restore (design #40 D3, §2 item 4).

:func:`backup` uses stdlib ``sqlite3.Connection.backup`` (a byte-consistent
online snapshot — no manual file copy, no risk of copying a half-written WAL
frame) to produce a second sqlite file plus a JSON :class:`BackupManifest`
recording the snapshot's tail (``last_seq``/``chain_digest``/
``key_generation``) and its file digest.

:func:`restore` **always** lands a NEW, ``non_live=True`` generation
(ADR-002-016 :449-459) — a restored store is never silently treated as a
continuation of the live one, and its chain is independently re-verified
before it is handed back. When a ``live_store`` is supplied, :func:`restore`
compares the restored tail against the live tail and evidences that
comparison as a :class:`RestoreComparison` record in the LIVE store (the
"surviving branch" ADR-002-016 language: divergence itself is durably
recorded, not silently resolved).

Firewall: stdlib (``hashlib``, ``json``, ``sqlite3``) + ``pydantic`` +
``tos_runtime.evidence.store`` only.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore

__all__ = ["BackupManifest", "RestoreComparison", "RestoredStore", "backup", "restore"]


class BackupManifest(BaseModel):
    """The snapshot manifest ``backup()`` writes beside the backup file.

    ``file_digest``/``last_seq``/``chain_digest``/``key_generation`` are the
    four fields the slice plan names explicitly; ``source_path``/
    ``backup_path``/``generation`` are added bookkeeping ``restore()`` needs
    to locate and label the snapshot — an extension, not a replacement, of
    the named shape.
    """

    model_config = ConfigDict(frozen=True)

    file_digest: str
    last_seq: int | None
    chain_digest: str
    key_generation: int | None
    generation: int
    source_path: str
    backup_path: str


class RestoreComparison(BaseModel):
    """The durable record of one restore's tail comparison against a live store.

    ``branches_diverged`` is ``None`` when no ``live_store`` was supplied to
    :func:`restore` (nothing to compare against) — never coerced to
    ``False`` (that would misreport "known not to have diverged" when the
    comparison was simply never made).
    """

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
    """Snapshot ``store`` into ``dest_dir`` and write its manifest.

    Args:
        store: The live evidence store to snapshot.
        dest_dir: An existing directory to write the backup file + manifest
            into.
        generation: The caller-assigned label for this snapshot (this
            module does not allocate generations itself — design #40 D4's
            generation axis is a caller concern).

    Returns:
        The manifest describing the snapshot just written.
    """
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
    """Restore a snapshot into a fresh, independently-numbered, non-live store.

    The manifest's own ``backup_path`` file is copied (via
    ``Connection.backup``, never a raw file copy) into ``dest_path`` — the
    original backup file is left untouched, restorable again later. The
    restored store's chain is verified before being handed back.

    Args:
        manifest_path: The ``BackupManifest`` JSON file written by
            :func:`backup`.
        dest_path: Where the restored, independent sqlite file is created.
        new_generation: The generation label the restored store is tagged
            with — always DIFFERENT from whatever generation the snapshot
            was taken under (ADR-002-016 "항상 새 세대"); this module does
            not itself enforce strict-increase (the caller owns the
            generation axis) but always sets ``non_live=True`` regardless.
        key_provider: The key source for the restored store's own
            :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`
            construction (verification uses the caller-supplied
            ``keys_by_generation`` inferred from this provider's current
            key only — a restored store spanning a rotation needs its
            verification keys supplied by the caller separately if it must
            verify pre-rotation links too).
        live_store: The current live store, if this restore is being
            compared against one still in service. When given, a
            :class:`RestoreComparison` is appended into the LIVE store.

    Returns:
        The restored store, its new generation, and ``non_live=True``.

    Raises:
        tos_runtime.evidence.store.EvidenceCorruption: If the restored
            chain fails verification.
    """
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
