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


@pytest.mark.parametrize(
    "position",
    [
        # An `int` is an index into the archive, negative counting from the end; a `float` is
        # a fraction of its length. Both are anchored to the xz FORMAT rather than to an
        # absolute byte offset, because the archive's size moves: tar headers carry mtimes, so
        # the same fixture compresses to slightly different bytes on every run. A single
        # absolute offset is what made this test flaky in CI (#821) while passing locally.
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
    """Byte rot anywhere in the xz stream is refused, and by the SAME path wherever it fell.

    xz verifies a block's CRC only at the block's END, and ``tarfile``'s ``r:xz`` reads only as
    far as the tar end-of-archive marker. So before :func:`verify_archive` decompressed the
    whole stream up front, the refusal an operator got depended on where the byte landed: rot
    in a tar header made the reader stop early and surface as "the manifest did not survive",
    and rot past the marker surfaced as nothing at all (the next test). Every position here now
    reports the one fact true of all of them.
    """
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
    """The regression #821 exists for — and the reason it is a safety fix, not only a
    determinism one.

    ``tarfile`` stops at the tar end-of-archive marker, so it never decodes what follows it:
    the record padding, the stream index, the 12-byte stream footer. Before the pre-extraction
    integrity pass, rot there was invisible to every check this module makes — each extracted
    member was intact, each digest matched the manifest, the evidence chain re-verified, and
    :func:`verify_archive` RETURNED an :class:`ArchiveVerification`. That stamped an archive
    ``xz -d`` refuses as a usable backup, and :func:`archive_backup_set` then renamed it out of
    ``.partial`` into cold storage under the name reserved for verified archives.

    The corruption is the file's last byte — the ``Z`` of the xz footer magic — so it is
    anchored to the format and lands in the footer whatever the archive's size.
    """
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    verification = _archive(tmp_path, manifest_path)
    archive_path = Path(verification.archive_path)

    raw = bytearray(archive_path.read_bytes())
    raw[-1] ^= 0xFF
    archive_path.write_bytes(bytes(raw))

    # Two facts stated independently of this module, because together they ARE the defect.
    # First: the archive really is unreadable now.
    with pytest.raises(lzma.LZMAError):
        lzma.decompress(archive_path.read_bytes())
    # Second: extraction alone still completes, and delivers every member. This is the exact
    # call `_extract_archive` makes; it walks the tar lazily, stops at the end-of-archive
    # marker, and never decodes the rot behind it.
    #
    # Whether some OTHER tar walk would have noticed is not a property to rely on, and the
    # asymmetry is the point: measured 2026-09-30, `getmembers()` RAISES `LZMAError` on this
    # five-member fixture but returns cleanly on a smaller single-member archive, because what
    # it sees depends only on how much of the stream the decompressor happened to buffer. So
    # this test asserts the call the module actually makes, not the one that happens to catch
    # it here.
    naive_dir = tmp_path / "naive-extract"
    naive_dir.mkdir()
    with tarfile.open(archive_path, mode="r:xz") as archive:
        archive.extractall(naive_dir, filter="data")
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
    """The SAME tar bytes, put back in a different xz container.

    Every member is byte-identical to the archive :func:`archive_backup_set` wrote, so every
    check downstream of the integrity pass passes. Only the container changed — which is what
    makes these fixtures a test of the pass and nothing else.
    """
    tar_bytes = lzma.decompress(archive_path.read_bytes())
    target.write_bytes(lzma.compress(tar_bytes, format=container, check=check))
    return target


def test_bytes_after_the_end_of_the_xz_stream_are_refused(tmp_path: Path) -> None:
    """Review finding 2: the fail-open one layer up from the one #821 named.

    A complete stream with bytes appended is not one archive, and ``xz -t`` refuses it
    (measured: rc=1, "Compressed data is corrupt"). :func:`lzma.open` does not —
    ``_compression.DecompressReader`` treats trailing bytes as a possible SECOND stream and,
    when they do not parse as one, breaks out of its loop silently. Reading the archive
    through :class:`lzma.LZMAFile` therefore reproduced exactly the fail-open the integrity
    pass was added to close, so the pass drives a raw :class:`lzma.LZMADecompressor` and
    inspects what is left over.

    Every member here is intact, so nothing downstream would object: without this check the
    archive passes verification whole.
    """
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


def test_a_lzma_alone_container_is_refused(tmp_path: Path) -> None:
    """Review finding 3, first half: a container that carries no integrity check at all.

    :func:`lzma.open`'s default ``FORMAT_AUTO`` accepts a ``.lzma``-alone stream, and
    ``tarfile``'s ``r:xz`` extracts one happily (both measured), so a re-packed cold archive
    in that container would be stamped integrity-checked with no checksum in the file to
    check. The pass pins ``FORMAT_XZ``.
    """
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
    """Review finding 3, second half: ``xz --check=none``.

    Decoding such a stream proves only that the LZMA2 filter chain parsed — there is no
    checksum over the contents, which is the whole thing this pass claims to run. Archives
    this module writes always carry CRC64 (measured: ``LZMADecompressor.check ==
    CHECK_CRC64``), so refusing ``CHECK_NONE`` rejects nothing it produces.
    """
    _live_dir, _backups_dir, manifest_path = _prepare(tmp_path)
    verification = _archive(tmp_path, manifest_path)
    repacked = _repack(
        Path(verification.archive_path),
        tmp_path / "nocheck.tar.xz",
        container=lzma.FORMAT_XZ,
        check=lzma.CHECK_NONE,
    )

    with pytest.raises(BackupArchiveRefused, match="could not be read back"):
        verify_archive(
            repacked,
            manifest_path,
            tmp_path / "verify-nocheck",
            key_provider=FixedKeyProvider(),
        )


def test_an_unreadable_archive_leaves_no_verify_dir_to_block_the_retry(
    tmp_path: Path,
) -> None:
    """Review finding 4: the integrity pass runs before ``verify_dir`` is created.

    ``verify_archive``'s docstring promises the directory is "kept on failure … every refusal
    names it". An archive whose bytes will not come back is decompressed into nothing, so
    there is nothing to keep and nothing to name — and creating it first left an EMPTY
    directory behind whose only effect was to make the operator's retry fail with
    "verify_dir already exists" instead of naming the real fault.
    """
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
        # Named by its real fault both times, not by a leftover from the first attempt.
        assert "already exists" not in str(refusal.value)
        assert not verify_dir.exists()


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


# -- review 2026-09-30 dispositions -------------------------------------------------------------


def test_a_failed_verification_leaves_no_archive_and_does_not_block_a_retry(
    tmp_path: Path,
) -> None:
    """MEDIUM-4, proven on both halves.

    Before the ``.partial``/rename split, a failed verification left an UNVERIFIED ``.tar.xz``
    in cold storage that looked exactly like a good one — and, because this function refuses to
    overwrite an existing archive for a generation, that leftover then blocked every retry.
    """
    _live_dir, backups_dir, manifest_path = _prepare(tmp_path)
    archive_dir = tmp_path / "archives"

    # Corrupt one member so verification fails AFTER the archive has been written.
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

    # Nothing under either name survives a failure.
    assert not (archive_dir / _ARCHIVE_NAME).exists()
    assert list(archive_dir.glob("*.partial")) == []

    # And the retry, once the cause is fixed, is not blocked by a leftover.
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
    """MEDIUM-5. A passing run leaves no multi-GB decompressed copy behind; a failing one keeps
    it, because that copy is the evidence of what went wrong — and the refusal says where.
    """
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
    """L1: ``extractall(filter="data")`` is what stops a crafted member from writing outside
    ``verify_dir``. This test goes red under ``filter="fully_trusted"``.

    The escape is asserted by its ABSENCE at the target path, not by the refusal type — a
    crafted member may be rejected outright or silently confined depending on the shape, and
    either is acceptable; landing outside ``verify_dir`` is not.
    """
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
    """L7: the digest loop only proves every EXPECTED member is present and correct, so on its
    own it passes an archive that ALSO carries a stray file. A restore must never be handed
    material nothing attests."""
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
