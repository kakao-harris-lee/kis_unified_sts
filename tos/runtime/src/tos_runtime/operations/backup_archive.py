"""Compressed cold archive of one durable-set backup (evidence growth plan §2 A3,"""

from __future__ import annotations

import hashlib
import lzma
import shutil
import tarfile
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict

from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore
from tos_runtime.operations.backup_set import BackupSetManifest, FileBackupEntry

__all__ = [
    "DEFAULT_XZ_PRESET",
    "ArchiveVerification",
    "BackupArchiveRefused",
    "archive_backup_set",
    "verify_archive",
]


_ARCHIVE_SUFFIX = ".set.tar.xz"

_PARTIAL_SUFFIX = ".partial"

DEFAULT_XZ_PRESET = 6

_INTEGRITY_CHUNK_BYTES = 1 << 20

_XZ_STREAM_HEADER_BYTES = 12


class BackupArchiveRefused(RuntimeError):
    """Raised by :func:`archive_backup_set` — the archive could not be written, could not be"""


_XzPreset = Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
_VALID_PRESETS: frozenset[int] = frozenset(range(10))


def _checked_preset(preset: int) -> _XzPreset:
    """``preset`` narrowed to what ``lzma`` accepts, or a refusal naming the value."""
    if preset not in _VALID_PRESETS:
        raise BackupArchiveRefused(
            f"archive_backup_set: xz preset {preset} is outside 0-9 — refused before anything "
            "is written"
        )
    return cast(_XzPreset, preset)


class ArchiveVerification(BaseModel):
    """The result of one :func:`archive_backup_set` call — only ever constructed after the"""

    model_config = ConfigDict(frozen=True)

    archive_path: str
    generation: int
    source_bytes: int
    archive_bytes: int
    files_verified: tuple[str, ...]
    chain_verified: Literal[True] = True


def _archive_members(
    manifest_path: Path, manifest: BackupSetManifest
) -> dict[str, Path]:
    """``member name -> live backup-copy path`` for one generation, manifest included."""
    members: dict[str, Path] = {manifest_path.name: manifest_path}
    for name, entry in manifest.files.items():
        if entry is None:
            continue
        source = Path(entry.path)
        if not source.is_file():
            raise BackupArchiveRefused(
                f"archive_backup_set: manifest records {name!r} at {source}, which does not "
                "exist — refusing to write an archive that is already incomplete"
            )
        members[source.name] = source
    return members


def _verify_archived_files(
    manifest: BackupSetManifest, extracted_dir: Path
) -> tuple[str, ...]:
    """Digest every extracted member against the manifest — the archive round trip's own M1."""
    verified: list[str] = []
    for name, entry in manifest.files.items():
        if entry is None:
            continue
        extracted = extracted_dir / Path(entry.path).name
        if not extracted.is_file():
            raise BackupArchiveRefused(
                f"verify_archive: {name!r} is missing from the decompressed archive "
                f"(expected {extracted.name}) — refused. The decompressed copy is kept at "
                f"{extracted_dir} for inspection"
            )
        actual = hashlib.sha256(extracted.read_bytes()).hexdigest()
        if actual != entry.file_digest:
            raise BackupArchiveRefused(
                f"verify_archive: decompressed {name!r} digests {actual}, manifest records "
                f"{entry.file_digest} — the archive does not hold what it claims to; refused. "
                f"The decompressed copy is kept at {extracted_dir} for inspection"
            )
        verified.append(name)
    return tuple(verified)


def _refuse_unexpected_members(
    manifest: BackupSetManifest, extracted_dir: Path, *, manifest_name: str
) -> None:
    """Refuse an archive carrying anything the manifest does not account for."""
    expected = {manifest_name} | {
        Path(entry.path).name for entry in manifest.files.values() if entry is not None
    }
    actual = {child.name for child in extracted_dir.iterdir()}
    unexpected = sorted(actual - expected)
    if unexpected:
        raise BackupArchiveRefused(
            f"verify_archive: the archive carries {len(unexpected)} member(s) the manifest does "
            f"not account for ({', '.join(unexpected)}) — refused. The decompressed copy is "
            f"kept at {extracted_dir} for inspection"
        )


def _refuse_unreadable(
    archive_path: Path, detail: str, *, verify_dir: Path | None
) -> BackupArchiveRefused:
    """The one "the bytes would not come back" refusal, raised from both read paths."""
    kept = (
        f". The decompressed copy is kept at {verify_dir} for inspection"
        if verify_dir is not None
        else ""
    )
    return BackupArchiveRefused(
        f"verify_archive: {archive_path} could not be read back ({detail}) — the archive "
        f"is not a usable backup; refused{kept}"
    )


def _require_intact_xz_stream(archive_path: Path) -> None:
    """Decode the whole xz stream, discarding it, so its integrity check ALWAYS runs."""
    decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
    checkless = False
    trailing = False
    try:
        with archive_path.open("rb") as raw:
            header = raw.read(_XZ_STREAM_HEADER_BYTES)
            if header:
                decompressor.decompress(header, max_length=_INTEGRITY_CHUNK_BYTES)
            checkless = decompressor.check == lzma.CHECK_NONE
            while not checkless and not decompressor.eof:
                chunk = b""
                if decompressor.needs_input:
                    chunk = raw.read(_INTEGRITY_CHUNK_BYTES)
                    if not chunk:
                        raise EOFError(
                            "the file ends before the xz stream's end-of-stream marker"
                        )
                decompressor.decompress(chunk, max_length=_INTEGRITY_CHUNK_BYTES)
            if not checkless:
                trailing = bool(decompressor.unused_data) or bool(raw.read(1))
    except (lzma.LZMAError, EOFError, OSError, ValueError) as exc:
        raise _refuse_unreadable(archive_path, repr(exc), verify_dir=None) from exc

    if checkless:
        raise _refuse_unreadable(
            archive_path,
            "the xz stream carries no integrity check (CHECK_NONE), so decoding it proves "
            "nothing about its contents",
            verify_dir=None,
        )
    if trailing:
        raise _refuse_unreadable(
            archive_path,
            "bytes follow the end of the xz stream (trailing data or stream padding) — this "
            "module writes exactly one unpadded stream and refuses anything else",
            verify_dir=None,
        )


def _extract_archive(
    archive_path: Path, verify_dir: Path, *, expected_manifest: Path
) -> None:
    """Decompress ``archive_path`` into ``verify_dir`` and check the manifest survived."""
    verify_dir.mkdir(parents=True)
    try:
        with tarfile.open(archive_path, mode="r:xz") as archive:
            archive.extractall(verify_dir, filter="data")
    except TypeError as exc:
        raise RuntimeError(
            "verify_archive: this interpreter does not support tarfile's `filter=` argument "
            "(added in Python 3.11.4). Extraction is not attempted without it — the filter is "
            "what keeps an archive member from escaping verify_dir"
        ) from exc
    except (lzma.LZMAError, tarfile.TarError, EOFError, OSError, ValueError) as exc:
        raise _refuse_unreadable(
            archive_path, repr(exc), verify_dir=verify_dir
        ) from exc

    extracted = verify_dir / expected_manifest.name
    if (
        not extracted.is_file()
        or extracted.read_text() != expected_manifest.read_text()
    ):
        raise BackupArchiveRefused(
            f"verify_archive: the manifest did not survive the round trip out of "
            f"{archive_path} — refused"
        )


def _require_entry(manifest: BackupSetManifest, name: str) -> FileBackupEntry:
    """The manifest entry for a NON-optional member, or a refusal naming it."""
    entry = manifest.files.get(name)
    if entry is None:
        raise BackupArchiveRefused(
            f"verify_archive: manifest has no {name!r} entry — a durable-set manifest always "
            "carries evidence/rcl/inbox; refused"
        )
    return entry


def verify_archive(
    archive_path: Path,
    manifest_path: Path,
    verify_dir: Path,
    *,
    key_provider: KeyProvider,
) -> ArchiveVerification:
    """Decompress ``archive_path`` into ``verify_dir`` and prove it holds what the manifest says."""
    if verify_dir.exists():
        raise BackupArchiveRefused(
            f"verify_archive: verify_dir {verify_dir} already exists — refusing to read back "
            "into a directory whose contents this call did not write"
        )
    _require_intact_xz_stream(archive_path)
    manifest = BackupSetManifest.model_validate_json(manifest_path.read_text())
    _extract_archive(archive_path, verify_dir, expected_manifest=manifest_path)
    _refuse_unexpected_members(manifest, verify_dir, manifest_name=manifest_path.name)
    files_verified = _verify_archived_files(manifest, verify_dir)
    source_bytes = sum(
        child.stat().st_size for child in verify_dir.iterdir() if child.is_file()
    )

    evidence_store = SqliteEvidenceStore(
        verify_dir / Path(_require_entry(manifest, "evidence").path).name,
        key_provider=key_provider,
    )
    try:
        key_generation, key_bytes = key_provider.current()
        evidence_store.verify_or_raise({key_generation: key_bytes})
    finally:
        evidence_store.close()

    verification = ArchiveVerification(
        archive_path=str(archive_path),
        generation=manifest.generation,
        source_bytes=source_bytes,
        archive_bytes=archive_path.stat().st_size,
        files_verified=files_verified,
    )
    shutil.rmtree(verify_dir, ignore_errors=True)
    return verification


def archive_backup_set(
    manifest_path: Path,
    archive_dir: Path,
    verify_dir: Path,
    *,
    key_provider: KeyProvider,
    preset: int = DEFAULT_XZ_PRESET,
) -> ArchiveVerification:
    """Compress one already-taken durable-set backup to ``archive_dir``, then prove it readable."""
    manifest = BackupSetManifest.model_validate_json(manifest_path.read_text())
    members = _archive_members(manifest_path, manifest)
    archive_path = archive_dir / f"gen{manifest.generation}{_ARCHIVE_SUFFIX}"
    if archive_path.exists():
        raise BackupArchiveRefused(
            f"archive_backup_set: {archive_path} already exists — refusing to overwrite an "
            "existing generation's archive"
        )
    if verify_dir.exists():
        raise BackupArchiveRefused(
            f"archive_backup_set: verify_dir {verify_dir} already exists — refusing to read "
            "back into a directory whose contents this call did not write"
        )

    checked_preset = _checked_preset(preset)
    archive_dir.mkdir(parents=True, exist_ok=True)
    partial_path = archive_path.with_name(archive_path.name + _PARTIAL_SUFFIX)
    partial_path.unlink(missing_ok=True)
    try:
        with tarfile.open(partial_path, mode="w:xz", preset=checked_preset) as archive:
            for member_name, source in sorted(members.items()):
                archive.add(source, arcname=member_name)
        verification = verify_archive(
            partial_path, manifest_path, verify_dir, key_provider=key_provider
        )
    except BaseException:
        partial_path.unlink(missing_ok=True)
        raise
    partial_path.rename(archive_path)
    return verification.model_copy(update={"archive_path": str(archive_path)})
