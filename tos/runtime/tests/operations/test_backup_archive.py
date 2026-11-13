"""Compressed cold-archive tests (evidence growth plan §2 A3,"""

from __future__ import annotations

import hashlib
import lzma
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
    """``name -> sha256`` for every file directly under ``directory`` — the "did the live set"""
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

    with tarfile.open(archive_path, mode="r:xz") as archive:
        assert _MANIFEST_NAME in archive.getnames()

    assert (backups_dir / "gen1").is_dir()


def test_the_live_files_are_never_modified(tmp_path: Path) -> None:
    live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    before = _digests_under(live_dir)
    assert before

    _archive(tmp_path, manifest_path)

    assert _digests_under(live_dir) == before


@pytest.mark.parametrize(
    "position",
    [
        pytest.param(7, id="xz-stream-header"),
        pytest.param(12, id="xz-block-header"),
        pytest.param(0.1, id="compressed-data-early"),
        pytest.param(0.5, id="compressed-data-midpoint"),
        pytest.param(0.75, id="compressed-data-late"),
        pytest.param(-4, id="xz-stream-footer-flags"),
        pytest.param(-1, id="xz-stream-footer-magic"),
    ],
)
def test_a_corrupted_archive_is_refused(tmp_path: Path, position: int | float) -> None:
    """Byte rot anywhere in the xz stream is refused, and by the SAME path wherever it fell."""
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    verification = _archive(tmp_path, manifest_path)

    archive_path = Path(verification.archive_path)
    raw = bytearray(archive_path.read_bytes())
    index = int(position * len(raw)) if isinstance(position, float) else position
    raw[index] ^= 0xFF
    archive_path.write_bytes(bytes(raw))

    with pytest.raises(BackupArchiveRefused, match="could not be read back"):
        verify_archive(
            archive_path,
            manifest_path,
            tmp_path / "verify-corrupt",
            key_provider=FixedKeyProvider(),
        )


def test_rot_past_the_tar_end_of_archive_marker_is_refused(tmp_path: Path) -> None:
    """The regression #821 exists for — and the reason it is a safety fix, not only a"""
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    verification = _archive(tmp_path, manifest_path)
    archive_path = Path(verification.archive_path)

    raw = bytearray(archive_path.read_bytes())
    raw[-1] ^= 0xFF
    archive_path.write_bytes(bytes(raw))

    with pytest.raises(lzma.LZMAError):
        lzma.decompress(archive_path.read_bytes())

    naive_dir = tmp_path / "naive-extract"
    naive_dir.mkdir()
    try:
        with tarfile.open(archive_path, mode="r:xz") as archive:
            archive.extractall(naive_dir, filter="data")
    except lzma.LZMAError:
        pass
    else:
        assert (naive_dir / _MANIFEST_NAME).is_file()

    with pytest.raises(BackupArchiveRefused, match="could not be read back"):
        verify_archive(
            archive_path,
            manifest_path,
            tmp_path / "verify-footer-rot",
            key_provider=FixedKeyProvider(),
        )


def _repack(
    archive_path: Path, target: Path, *, container: int, check: int = -1
) -> Path:
    """The SAME tar bytes, put back in a different xz container."""
    tar_bytes = lzma.decompress(archive_path.read_bytes())
    target.write_bytes(lzma.compress(tar_bytes, format=container, check=check))
    return target


def test_bytes_after_the_end_of_the_xz_stream_are_refused(tmp_path: Path) -> None:
    """Review finding 2: the fail-open one layer up from the one #821 named."""
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    verification = _archive(tmp_path, manifest_path)
    archive_path = Path(verification.archive_path)
    archive_path.write_bytes(archive_path.read_bytes() + b"\x00appended\xff" * 4)

    with pytest.raises(BackupArchiveRefused, match="could not be read back"):
        verify_archive(
            archive_path,
            manifest_path,
            tmp_path / "verify-trailing",
            key_provider=FixedKeyProvider(),
        )


def test_xz_stream_padding_is_refused_and_the_refusal_says_so(tmp_path: Path) -> None:
    """Review round 2, finding 2: a divergence from ``xz -t``, named rather than hidden."""
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    verification = _archive(tmp_path, manifest_path)
    archive_path = Path(verification.archive_path)
    archive_path.write_bytes(archive_path.read_bytes() + b"\x00" * 4)

    with pytest.raises(BackupArchiveRefused, match="could not be read back") as refusal:
        verify_archive(
            archive_path,
            manifest_path,
            tmp_path / "verify-padding",
            key_provider=FixedKeyProvider(),
        )
    assert "stream padding" in str(refusal.value)
    assert "one unpadded stream" in str(refusal.value)


def test_a_lzma_alone_container_is_refused(tmp_path: Path) -> None:
    """Review finding 3, first half: a container that carries no integrity check at all."""
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    verification = _archive(tmp_path, manifest_path)
    repacked = _repack(
        Path(verification.archive_path),
        tmp_path / "alone.tar.xz",
        container=lzma.FORMAT_ALONE,
    )

    with pytest.raises(BackupArchiveRefused, match="could not be read back"):
        verify_archive(
            repacked,
            manifest_path,
            tmp_path / "verify-alone",
            key_provider=FixedKeyProvider(),
        )


def test_an_xz_stream_with_no_integrity_check_is_refused(tmp_path: Path) -> None:
    """Review finding 3, second half: ``xz --check=none``."""
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    verification = _archive(tmp_path, manifest_path)
    repacked = _repack(
        Path(verification.archive_path),
        tmp_path / "nocheck.tar.xz",
        container=lzma.FORMAT_XZ,
        check=lzma.CHECK_NONE,
    )

    with pytest.raises(BackupArchiveRefused, match="could not be read back") as refusal:
        verify_archive(
            repacked,
            manifest_path,
            tmp_path / "verify-nocheck",
            key_provider=FixedKeyProvider(),
        )
    assert "CHECK_NONE" in str(refusal.value)


def test_a_checkless_container_is_refused_before_the_stream_is_decoded(
    tmp_path: Path,
) -> None:
    """Review round 2, finding 4(a): decide on the check type from the stream HEADER."""
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    verification = _archive(tmp_path, manifest_path)
    repacked = _repack(
        Path(verification.archive_path),
        tmp_path / "nocheck-rotten.tar.xz",
        container=lzma.FORMAT_XZ,
        check=lzma.CHECK_NONE,
    )
    raw = bytearray(repacked.read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    repacked.write_bytes(bytes(raw))
    with pytest.raises(lzma.LZMAError):
        lzma.decompress(repacked.read_bytes())

    with pytest.raises(BackupArchiveRefused, match="could not be read back") as refusal:
        verify_archive(
            repacked,
            manifest_path,
            tmp_path / "verify-nocheck-rotten",
            key_provider=FixedKeyProvider(),
        )
    assert "CHECK_NONE" in str(refusal.value)
    assert "LZMAError" not in str(refusal.value)


def test_an_unreadable_archive_leaves_no_verify_dir_to_block_the_retry(
    tmp_path: Path,
) -> None:
    """Review finding 4: the integrity pass runs before ``verify_dir`` is created."""
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    verification = _archive(tmp_path, manifest_path)
    archive_path = Path(verification.archive_path)
    raw = bytearray(archive_path.read_bytes())
    raw[-1] ^= 0xFF
    archive_path.write_bytes(bytes(raw))

    verify_dir = tmp_path / "verify-rot"
    for _attempt in range(2):
        with pytest.raises(
            BackupArchiveRefused, match="could not be read back"
        ) as refusal:
            verify_archive(
                archive_path,
                manifest_path,
                verify_dir,
                key_provider=FixedKeyProvider(),
            )
        assert "already exists" not in str(refusal.value)
        assert not verify_dir.exists()


def test_an_archive_whose_content_was_swapped_is_refused_by_the_digest_check(
    tmp_path: Path,
) -> None:
    """The check lzma's own CRC cannot make."""
    _live_dir, backups_dir, manifest_path = _prepare(tmp_path)

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
    """A directory this call did not create could hide a stale file behind a member the"""
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
    """Never write an archive that is already incomplete: the refusal happens BEFORE the"""
    _live_dir, backups_dir, manifest_path = _prepare(tmp_path)
    (backups_dir / "gen1" / "rcl.sqlite3").unlink()

    with pytest.raises(BackupArchiveRefused, match="rcl"):
        _archive(tmp_path, manifest_path)

    assert not (tmp_path / "archives" / _ARCHIVE_NAME).exists()


@pytest.mark.parametrize("preset", [-1, 10])
def test_an_out_of_range_xz_preset_is_refused_before_anything_is_written(
    tmp_path: Path, preset: int
) -> None:
    """``--xz-preset`` arrives as a plain int, so the 0-9 range is checked here rather than"""
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


def test_a_failed_verification_leaves_no_archive_and_does_not_block_a_retry(
    tmp_path: Path,
) -> None:
    """MEDIUM-4, proven on both halves."""
    _live_dir, backups_dir, manifest_path = _prepare(tmp_path)
    archive_dir = tmp_path / "archives"

    evidence_backup = backups_dir / "gen1" / "evidence.sqlite3"
    original = evidence_backup.read_bytes()
    evidence_backup.write_bytes(original + b"tampered")

    with pytest.raises(BackupArchiveRefused, match="digests"):
        archive_backup_set(
            manifest_path,
            archive_dir,
            tmp_path / "verify-fail",
            key_provider=FixedKeyProvider(),
        )

    assert not (archive_dir / _ARCHIVE_NAME).exists()
    assert list(archive_dir.glob("*.partial")) == []

    evidence_backup.write_bytes(original)
    verification = archive_backup_set(
        manifest_path,
        archive_dir,
        tmp_path / "verify-retry",
        key_provider=FixedKeyProvider(),
    )
    assert Path(verification.archive_path) == archive_dir / _ARCHIVE_NAME
    assert (archive_dir / _ARCHIVE_NAME).is_file()


def test_verify_dir_is_removed_on_success_and_kept_on_failure(tmp_path: Path) -> None:
    """MEDIUM-5. A passing run leaves no multi-GB decompressed copy behind; a failing one keeps"""
    _live_dir, backups_dir, manifest_path = _prepare(tmp_path)

    success_dir = tmp_path / "verify-ok"
    _archive(tmp_path, manifest_path)
    assert not success_dir.exists()
    assert not (tmp_path / "verify").exists()

    evidence_backup = backups_dir / "gen1" / "evidence.sqlite3"
    evidence_backup.write_bytes(evidence_backup.read_bytes() + b"tampered")
    failure_dir = tmp_path / "verify-kept"
    with pytest.raises(BackupArchiveRefused) as refusal:
        archive_backup_set(
            manifest_path,
            tmp_path / "archives-2",
            failure_dir,
            key_provider=FixedKeyProvider(),
        )
    assert failure_dir.is_dir()
    assert str(failure_dir) in str(refusal.value)


@pytest.mark.parametrize(
    ("arcname", "label"),
    [("../escaped.sqlite3", "parent"), ("/tmp/escaped.sqlite3", "absolute")],
)
def test_a_member_that_tries_to_escape_the_verify_dir_cannot(
    tmp_path: Path, arcname: str, label: str
) -> None:
    """L1: ``extractall(filter="data")`` is what stops a crafted member from writing outside"""
    _live_dir, backups_dir, manifest_path = _prepare(tmp_path)

    archive_dir = tmp_path / "archives"
    archive_dir.mkdir()
    archive_path = archive_dir / _ARCHIVE_NAME
    escape_target = tmp_path / "escaped.sqlite3"
    payload = backups_dir / "gen1" / "rcl.sqlite3"
    with tarfile.open(archive_path, mode="w:xz") as archive:
        archive.add(manifest_path, arcname=_MANIFEST_NAME)
        for child in sorted((backups_dir / "gen1").iterdir()):
            archive.add(child, arcname=child.name)
        archive.add(payload, arcname=arcname)

    verify_dir = tmp_path / f"verify-{label}"
    with pytest.raises(BackupArchiveRefused):
        verify_archive(
            archive_path,
            manifest_path,
            verify_dir,
            key_provider=FixedKeyProvider(),
        )

    assert not escape_target.exists()
    assert not Path("/tmp/escaped.sqlite3").exists()


def test_an_archive_carrying_an_unaccounted_member_is_refused(tmp_path: Path) -> None:
    """L7: the digest loop only proves every EXPECTED member is present and correct, so on its"""
    _live_dir, backups_dir, manifest_path = _prepare(tmp_path)

    archive_dir = tmp_path / "archives"
    archive_dir.mkdir()
    archive_path = archive_dir / _ARCHIVE_NAME
    stowaway = tmp_path / "stowaway.sqlite3"
    stowaway.write_bytes(b"not part of this backup")
    with tarfile.open(archive_path, mode="w:xz") as archive:
        archive.add(manifest_path, arcname=_MANIFEST_NAME)
        for child in sorted((backups_dir / "gen1").iterdir()):
            archive.add(child, arcname=child.name)
        archive.add(stowaway, arcname="stowaway.sqlite3")

    with pytest.raises(BackupArchiveRefused, match="does not account for"):
        verify_archive(
            archive_path,
            manifest_path,
            tmp_path / "verify-stowaway",
            key_provider=FixedKeyProvider(),
        )
