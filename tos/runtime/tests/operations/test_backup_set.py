"""Durable-set backup/restore tests (TOS Phase 5 W4 plan §2 decisions 1-2).

The full recompose-and-drill path (:func:`~tos_runtime.operations.backup_set.restore_drill`) is
exercised in ``tests/recovery/test_drill.py`` against a real ``compose_paper_runtime`` boot — this
module covers :func:`~tos_runtime.operations.backup_set.backup_set` and
:func:`~tos_runtime.operations.backup_set.restore_set` directly, against real (but standalone,
non-composed) evidence/RCL/inbox stores plus a synthetic composite-state file, so the digest/
generation/refusal mechanics are tested without needing a full boot for every case.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.operations.backup_set import (
    BackupSetRefused,
    DurableSetPaths,
    RestoreRefused,
    backup_set,
    restore_set,
)
from tos_runtime.rcl.log import SqliteCommitLog

from .conftest import SCHEME, FixedKeyProvider

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _build_live_set(data_dir: Path, *, with_entries: bool = True) -> DurableSetPaths:
    """Build one real, closed durable set directly under ``data_dir`` (the SAME filenames
    :func:`~tos_runtime.operations.backup_set.DurableSetPaths.from_data_dir` expects).
    """
    key_provider = FixedKeyProvider()
    evidence = SqliteEvidenceStore(
        data_dir / "evidence.sqlite3", key_provider=key_provider
    )
    if with_entries:
        evidence.append({"n": 1}, kind="EVENT_CONSUMED", record_class="EVENT_CONSUMED")
        evidence.append({"n": 2}, kind="EVENT_CONSUMED", record_class="EVENT_CONSUMED")
    rcl = SqliteCommitLog(data_dir / "rcl.sqlite3", evidence_port=evidence)
    if with_entries:
        rcl.acquire_epoch(_fake_identity())
    inbox = SqliteEventInbox(data_dir / "inbox.sqlite3", scheme=SCHEME)
    evidence.close()
    rcl.close()
    inbox.close()

    # Composite-state is kernel-owned and opaque to this package — a bare sqlite file with no
    # recognized shape is exactly what this module treats it as.
    composite_conn = sqlite3.connect(str(data_dir / "composite_state.sqlite3"))
    composite_conn.close()

    return DurableSetPaths.from_data_dir(data_dir)


def _fake_identity():
    from tos.workload import RuntimeIdentity

    return RuntimeIdentity(
        cell_id="cell-1",
        runtime_generation=1,
        process_nonce="nonce-1",
        code_digest="digest-1",
    )


# -- backup_set ---------------------------------------------------------------------------------


def test_backup_set_writes_a_manifest_with_four_files_and_facts(tmp_path: Path) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"

    manifest = backup_set(paths, backups_dir, generation=1)

    assert manifest.generation == 1
    assert set(manifest.files) == {"evidence", "rcl", "inbox", "composite_state"}
    for entry in manifest.files.values():
        assert Path(entry.path).is_file()
        assert len(entry.file_digest) == 64  # sha256 hex

    assert manifest.evidence.last_seq == 1  # two entries appended, seq is 0-indexed
    assert manifest.evidence.event_consumed_count == 2
    assert manifest.rcl.writer_epoch == 1
    assert manifest.inbox.last_seq is None  # no events enqueued in this fixture
    assert manifest.files["composite_state"].last_seq is None

    manifest_path = backups_dir / "gen1.set.manifest.json"
    assert manifest_path.is_file()


def test_backup_set_refuses_a_non_increasing_generation(tmp_path: Path) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"

    backup_set(paths, backups_dir, generation=5)

    with pytest.raises(BackupSetRefused, match="strictly greater"):
        backup_set(paths, backups_dir, generation=5)
    with pytest.raises(BackupSetRefused, match="strictly greater"):
        backup_set(paths, backups_dir, generation=3)

    # A strictly greater generation still succeeds.
    manifest = backup_set(paths, backups_dir, generation=6)
    assert manifest.generation == 6


def test_backup_set_refuses_a_missing_source_file(tmp_path: Path) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    (live_dir / "inbox.sqlite3").unlink()

    with pytest.raises(BackupSetRefused, match="inbox"):
        backup_set(paths, tmp_path / "backups", generation=1)


def test_backup_set_never_deletes_an_existing_generation_directory(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    # Tamper with the manifest file name so _highest_existing_generation no longer sees gen1,
    # then try to reuse generation=1 — the pre-existing gen1/ directory must not be silently
    # overwritten; mkdir(exist_ok=False) refuses it.
    (backups_dir / "gen1.set.manifest.json").unlink()
    with pytest.raises(FileExistsError):
        backup_set(paths, backups_dir, generation=1)


# -- restore_set --------------------------------------------------------------------------------


def test_restore_set_round_trips_and_verifies_the_evidence_chain(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    manifest = backup_set(paths, backups_dir, generation=1)

    restore_dir = tmp_path / "restored"
    restored = restore_set(
        backups_dir / "gen1.set.manifest.json",
        restore_dir,
        key_provider=FixedKeyProvider(),
    )

    assert restored.non_live is True
    assert restored.manifest.generation == manifest.generation
    for name in ("evidence", "rcl", "inbox", "composite_state"):
        assert getattr(restored.paths, name).is_file()

    # The restored evidence store re-opens and verifies cleanly.
    reopened = SqliteEvidenceStore(
        restored.paths.evidence, key_provider=FixedKeyProvider()
    )
    key_generation, key_bytes = FixedKeyProvider().current()
    assert reopened.verify({key_generation: key_bytes}) is True
    reopened.close()


def test_restore_set_refuses_when_destination_is_the_live_data_dir(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    with pytest.raises(RestoreRefused, match="live source data directory"):
        restore_set(
            backups_dir / "gen1.set.manifest.json",
            live_dir,
            key_provider=FixedKeyProvider(),
        )


def test_restore_set_refuses_when_destination_is_inside_the_live_data_dir(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    nested = live_dir / "nested-restore"
    with pytest.raises(RestoreRefused, match="live source data directory"):
        restore_set(
            backups_dir / "gen1.set.manifest.json",
            nested,
            key_provider=FixedKeyProvider(),
        )


def test_restore_set_refuses_on_a_mutated_restored_file_digest(tmp_path: Path) -> None:
    """(M1) One byte flipped in a restored file must refuse — never silently accepted."""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    # Mutate the BACKUP copy of the inbox file (what restore_set actually copies from).
    backup_inbox_path = backups_dir / "gen1" / "inbox.sqlite3"
    raw = bytearray(backup_inbox_path.read_bytes())
    raw[-1] ^= 0xFF
    backup_inbox_path.write_bytes(bytes(raw))

    with pytest.raises(RestoreRefused, match="mutation M1"):
        restore_set(
            backups_dir / "gen1.set.manifest.json",
            tmp_path / "restored",
            key_provider=FixedKeyProvider(),
        )


def test_restore_set_refuses_when_evidence_key_generation_disagrees(
    tmp_path: Path,
) -> None:
    """A restored evidence store whose chain cannot verify under the supplied key provider
    raises the store's own EvidenceCorruption — restore_set does not swallow it."""
    from tos_runtime.evidence.store import EvidenceCorruption

    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    wrong_key_provider = FixedKeyProvider(
        key_generation=1, key=b"a-completely-different-key"
    )
    with pytest.raises(EvidenceCorruption):
        restore_set(
            backups_dir / "gen1.set.manifest.json",
            tmp_path / "restored",
            key_provider=wrong_key_provider,
        )
