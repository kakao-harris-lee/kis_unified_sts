"""Compressed cold-archive tests (evidence growth plan §2 A3,
``docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md``).

Covers :func:`~tos_runtime.operations.backup_archive.archive_backup_set` against a real (but
standalone, non-composed) durable set, the same fixture shape
``tests/operations/test_backup_set.py`` already uses — reused from there rather than re-typed,
so the two suites cannot drift about what a durable set is.

Every refusal path here is proven RED on a real fixture, not merely documented: an archive
whose bytes were corrupted, an archive whose CONTENT was swapped for a different valid sqlite
file (lzma's own CRC is happy with that — only the manifest digest catches it), an archive that
already exists, and a ``verify_dir`` that already exists.
"""

from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import pytest
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.operations.backup_archive import (
    ArchiveVerification,
    BackupArchiveRefused,
    archive_backup_set,
    verify_archive,
)
from tos_runtime.operations.backup_set import backup_set

from .conftest import FixedKeyProvider
from .test_backup_set import _build_live_set

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_MANIFEST_NAME = "gen1.set.manifest.json"
_ARCHIVE_NAME = "gen1.set.tar.xz"


def _digests_under(directory: Path) -> dict[str, str]:
    """``name -> sha256`` for every file directly under ``directory`` — the "did the live set
    move?" fixture."""
    return {
        child.name: hashlib.sha256(child.read_bytes()).hexdigest()
        for child in sorted(directory.iterdir())
        if child.is_file()
    }


def _prepare(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a live set, back it up, and return ``(live_dir, backups_dir, manifest_path)``."""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir, with_marketfeed=True)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)
    return live_dir, backups_dir, backups_dir / _MANIFEST_NAME


def _archive(
    tmp_path: Path, manifest_path: Path, suffix: str = ""
) -> ArchiveVerification:
    return archive_backup_set(
        manifest_path,
        tmp_path / f"archives{suffix}",
        tmp_path / f"verify{suffix}",
        key_provider=FixedKeyProvider(),
    )


def test_round_trip_compresses_reads_back_and_verifies(tmp_path: Path) -> None:
    _live_dir, backups_dir, manifest_path = _prepare(tmp_path)

    verification = _archive(tmp_path, manifest_path)

    assert verification.generation == 1
    assert verification.chain_verified is True
    # Every non-optional member plus the two optional ones this fixture does create.
    assert set(verification.files_verified) == {
        "evidence",
        "rcl",
        "inbox",
        "composite_state",
        "marketfeed",
    }
    archive_path = Path(verification.archive_path)
    assert archive_path == tmp_path / "archives" / _ARCHIVE_NAME
    assert archive_path.is_file()
    assert verification.archive_bytes == archive_path.stat().st_size
    assert verification.archive_bytes < verification.source_bytes

    # The archive is self-describing: the manifest travels with the files.
    with tarfile.open(archive_path, mode="r:xz") as archive:
        assert _MANIFEST_NAME in archive.getnames()

    # The uncompressed generation is left exactly as backup_set wrote it.
    assert (backups_dir / "gen1").is_dir()


def test_the_live_files_are_never_modified(tmp_path: Path) -> None:
    live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    before = _digests_under(live_dir)
    assert before  # the fixture really did create files

    _archive(tmp_path, manifest_path)

    assert _digests_under(live_dir) == before


def test_a_corrupted_archive_is_refused(tmp_path: Path) -> None:
    """Byte rot inside the xz stream: read-back raises, and that is reported as a refusal
    naming the archive — never as a silently empty verification."""
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    verification = _archive(tmp_path, manifest_path)

    archive_path = Path(verification.archive_path)
    raw = bytearray(archive_path.read_bytes())
    midpoint = len(raw) // 2
    raw[midpoint] ^= 0xFF
    archive_path.write_bytes(bytes(raw))

    with pytest.raises(BackupArchiveRefused, match="could not be read back"):
        verify_archive(
            archive_path,
            manifest_path,
            tmp_path / "verify-corrupt",
            key_provider=FixedKeyProvider(),
        )


def test_an_archive_whose_content_was_swapped_is_refused_by_the_digest_check(
    tmp_path: Path,
) -> None:
    """The check lzma's own CRC cannot make.

    A re-packed archive is a perfectly valid xz stream, so read-back succeeds; only the
    per-file digest against the manifest catches that ``evidence.sqlite3`` is no longer the
    file the manifest attests. This is the mutation that would go green if
    ``_verify_archived_files`` were dropped.
    """
    _live_dir, backups_dir, manifest_path = _prepare(tmp_path)

    # An entirely different, but perfectly valid, evidence store.
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other_evidence = other_dir / "evidence.sqlite3"
    store = SqliteEvidenceStore(other_evidence, key_provider=FixedKeyProvider())
    store.append({"n": 99}, kind="EVENT_CONSUMED", record_class="EVENT_CONSUMED")
    store.close()

    archive_dir = tmp_path / "archives"
    archive_dir.mkdir()
    archive_path = archive_dir / _ARCHIVE_NAME
    gen_dir = backups_dir / "gen1"
    with tarfile.open(archive_path, mode="w:xz") as archive:
        archive.add(manifest_path, arcname=_MANIFEST_NAME)
        for child in sorted(gen_dir.iterdir()):
            source = other_evidence if child.name == "evidence.sqlite3" else child
            archive.add(source, arcname=child.name)

    with pytest.raises(BackupArchiveRefused, match="digests"):
        verify_archive(
            archive_path,
            manifest_path,
            tmp_path / "verify-swapped",
            key_provider=FixedKeyProvider(),
        )


def test_an_existing_archive_for_this_generation_is_never_overwritten(
    tmp_path: Path,
) -> None:
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    _archive(tmp_path, manifest_path)

    with pytest.raises(BackupArchiveRefused, match="already exists"):
        archive_backup_set(
            manifest_path,
            tmp_path / "archives",
            tmp_path / "verify-second",
            key_provider=FixedKeyProvider(),
        )


def test_a_pre_existing_verify_dir_is_refused(tmp_path: Path) -> None:
    """A directory this call did not create could hide a stale file behind a member the
    archive failed to carry — which would turn a missing member into a passing verification.
    """
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    (tmp_path / "verify-stale").mkdir()

    with pytest.raises(BackupArchiveRefused, match="already exists"):
        archive_backup_set(
            manifest_path,
            tmp_path / "archives",
            tmp_path / "verify-stale",
            key_provider=FixedKeyProvider(),
        )


def test_a_manifest_naming_a_missing_backup_file_is_refused(tmp_path: Path) -> None:
    """Never write an archive that is already incomplete: the refusal happens BEFORE the
    archive file is created, so a half-set archive never reaches the archive directory.
    """
    _live_dir, backups_dir, manifest_path = _prepare(tmp_path)
    (backups_dir / "gen1" / "rcl.sqlite3").unlink()

    with pytest.raises(BackupArchiveRefused, match="rcl"):
        _archive(tmp_path, manifest_path)

    assert not (tmp_path / "archives" / _ARCHIVE_NAME).exists()


@pytest.mark.parametrize("preset", [-1, 10])
def test_an_out_of_range_xz_preset_is_refused_before_anything_is_written(
    tmp_path: Path, preset: int
) -> None:
    """``--xz-preset`` arrives as a plain int, so the 0-9 range is checked here rather than
    left to surface as an ``LZMAError`` from inside a half-written archive."""
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)

    with pytest.raises(BackupArchiveRefused, match="outside 0-9"):
        archive_backup_set(
            manifest_path,
            tmp_path / "archives",
            tmp_path / "verify-preset",
            key_provider=FixedKeyProvider(),
            preset=preset,
        )

    assert not (tmp_path / "archives").exists()
