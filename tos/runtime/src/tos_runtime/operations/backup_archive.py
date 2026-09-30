"""Compressed cold archive of one durable-set backup (evidence growth plan §2 A3,
``docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md``).

**Strictly on top of :mod:`tos_runtime.operations.backup_set`, never beside it.** This module
takes no snapshot of its own: it consumes a :class:`~tos_runtime.operations.backup_set
.BackupSetManifest` that ``backup_set`` already wrote, compresses that generation into one
``gen{N}.set.tar.xz``, and then proves the archive readable — decompress, digest every member
against the manifest, re-verify the evidence chain. The live data directory and the
uncompressed backup tree are only ever READ.

**Why its own module rather than more of** :mod:`~tos_runtime.operations.backup_set`. That
module is 770 lines against the 1000-line ceiling in ``config/tos_size_budget.yaml``, which
``tos/runtime/src`` is in scope for with zero registered exceptions; folding this in left it at
992/1000, i.e. one ordinary edit away from a red gate. The concern is separable anyway — take a
snapshot vs. keep a cold copy of one — and the ``backup-set`` CLI is still the single operator
entry point for both halves.

**Nothing here deletes, updates or rewrites anything.** An archive is an addition; Track B
(destructive purge) stays closed on its own five preconditions (plan §4). What this module
builds is the "independently verified snapshot … raw material" ADR-002-016 §17 requires to
already EXIST before any purge could be considered.

Firewall: stdlib (``hashlib``, ``lzma``, ``tarfile``) + ``pydantic`` + ``tos_runtime.evidence``
+ ``tos_runtime.operations.backup_set`` only (R1 allowlist).
"""

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


#: One generation's compressed cold archive: ``gen{N}.set.tar.xz`` beside (or far away from)
#: the uncompressed backup tree. Evidence growth plan §2 A3.
_ARCHIVE_SUFFIX = ".set.tar.xz"

#: Appended while the archive is being written and verified. The final name is a rename, so a
#: file under :data:`_ARCHIVE_SUFFIX` is always one that passed :func:`verify_archive`.
_PARTIAL_SUFFIX = ".partial"

#: stdlib ``lzma``'s own default. Named, and overridable per call, because it is a cost/ratio
#: tradeoff an operator may want to move (the plan's §1 measured 14× on evidence at this
#: preset) — never a constant this module decides on the operator's behalf.
DEFAULT_XZ_PRESET = 6

#: Read size for the pre-extraction integrity pass. Every chunk is discarded as soon as it is
#: read, so this bounds that pass's memory rather than trading memory for speed — an archive of
#: any size is checked within this much RAM.
_INTEGRITY_CHUNK_BYTES = 1 << 20


class BackupArchiveRefused(RuntimeError):
    """Raised by :func:`archive_backup_set` — the archive could not be written, could not be
    read back, or read back as something other than what the manifest attests.

    There is no "archived but unverified" outcome: that function either returns an
    :class:`ArchiveVerification` or raises this, so a caller can never mistake "the tar.xz
    exists" for "the tar.xz holds a usable backup" — the only property that makes an archive
    worth keeping for the eventual Track B purge (ADR-002-016 §17).
    """


#: The presets ``lzma`` actually accepts. ``preset`` arrives as a plain ``int`` (an operator's
#: ``--xz-preset``), so the range is checked HERE rather than left to surface as ``lzma``'s own
#: ``LZMAError`` from inside a half-written archive.
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
    """The result of one :func:`archive_backup_set` call — only ever constructed after the
    archive was read back and every check passed (:class:`BackupArchiveRefused` otherwise): the
    same "receipt in-hand ⇒ already proved" shape
    :class:`~tos.evidence.EvidenceAppendReceipt` uses."""

    model_config = ConfigDict(frozen=True)

    archive_path: str
    generation: int
    #: Sum of the uncompressed member sizes, and the archive's own size — the operator-facing
    #: ratio, reported rather than assumed.
    source_bytes: int
    archive_bytes: int
    #: Manifest keys whose file digest was re-checked out of the DECOMPRESSED copy.
    files_verified: tuple[str, ...]
    chain_verified: Literal[True] = True


def _archive_members(
    manifest_path: Path, manifest: BackupSetManifest
) -> dict[str, Path]:
    """``member name -> live backup-copy path`` for one generation, manifest included.

    Flat names (never the absolute paths the manifest records), so an archive restores the same
    way regardless of where the backup tree lived when it was taken.
    """
    members: dict[str, Path] = {manifest_path.name: manifest_path}
    for name, entry in manifest.files.items():
        if entry is None:
            continue  # optional member absent at backup time (BackupSetManifest.files)
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
    """Refuse an archive carrying anything the manifest does not account for.

    The digest loop only checks that every EXPECTED member is present and correct; on its own it
    would happily pass an archive that also carried a stray file. ``filter="data"`` already stops
    a member from landing outside ``extracted_dir``, but "inside the verify dir and unaccounted
    for" is still not something a backup this code wrote could contain, and a restore should
    never be handed material nothing attests (review L7).
    """
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
    archive_path: Path, detail: str, *, verify_dir: Path | None = None
) -> BackupArchiveRefused:
    """The one "the bytes would not come back" refusal, raised from both read paths.

    Shared so that where the rot fell never changes what the operator is told: the integrity
    pass and the extraction below report the same fact in the same words.

    ``verify_dir`` is named only when this call actually left one behind, which is the promise
    :func:`verify_archive`'s docstring makes ("kept on failure … every refusal names it"). The
    integrity pass runs before the directory is created, so it has nothing to point at and
    says nothing — and, because it created nothing, a retry with the same ``--verify-dir`` is
    not blocked by an empty leftover.
    """
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
    """Decode the whole xz stream, discarding it, so its integrity check ALWAYS runs.

    ``tarfile``'s ``r:xz`` reads only as far as the tar end-of-archive marker, and xz verifies a
    block's CRC only once that block ENDS. Two consequences, both measured on a real archive
    this module wrote:

    * Rot past the point the tar reader stops at — the record padding after the end-of-archive
      marker, the stream index, the 12-byte stream footer — was never decoded at all, so a
      **corrupt archive verified clean** and got renamed out of ``.partial`` as if it were a
      usable backup. It is not: ``xz -t`` refuses it, so the cold copy would be found dead at
      the one moment it is needed.
    * Rot inside a tar HEADER makes the reader stop early (a garbled header can read as the
      end-of-archive marker), so the refusal arrived from the manifest comparison instead of
      from here, and which of the two fired depended on where the byte fell.

    Three things this deliberately does NOT delegate to :func:`lzma.open`, each measured
    against ``xz -t`` on the same bytes (review 2026-09-30 findings 2-3):

    * **A raw** :class:`lzma.LZMADecompressor`, **not** :class:`lzma.LZMAFile`. That file
      wrapper treats bytes after a complete stream as a possible second stream and, when they
      do not parse as one, *silently ignores them* (``_compression.DecompressReader``'s
      ``except self._trailing_error: break``). A valid stream with garbage appended therefore
      read back clean while ``xz -t`` reported "Compressed data is corrupt" — the same
      fail-open this function exists to close, one layer up. ``unused_data`` plus a probe read
      of the file catch it here. This necessarily also refuses a legitimately CONCATENATED
      multi-stream xz file: nothing this module writes is one (``tarfile``'s ``w:xz`` emits a
      single stream), and for a cold archive someone re-packed that way, refusing and asking
      for a single-stream copy is the fail-closed answer.
    * **``format=FORMAT_XZ``, pinned.** The default ``FORMAT_AUTO`` also accepts a
      ``.lzma``-alone container, which carries no integrity check at all; a re-packed archive
      in that container would pass this pass with nothing ever checksummed.
    * **``CHECK_NONE`` refused.** An xz stream can be written with no check
      (``xz --check=none``); decoding it proves only that the LZMA2 filter chain parsed.
      Archives this module writes always carry CRC64 (measured: ``check == CHECK_CRC64``), so
      this rejects nothing it produces — it rejects a cold archive someone re-packed weaker,
      which :func:`verify_archive` is public to re-check months later.

    Reading to the end first collapses all of it into one deterministic outcome, before
    anything is extracted. The cost is one extra decode pass; it holds
    :data:`_INTEGRITY_CHUNK_BYTES` at a time and keeps nothing.
    """
    decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
    try:
        with archive_path.open("rb") as raw:
            while not decompressor.eof:
                chunk = b""
                if decompressor.needs_input:
                    chunk = raw.read(_INTEGRITY_CHUNK_BYTES)
                    if not chunk:
                        raise EOFError(
                            "the file ends before the xz stream's end-of-stream marker"
                        )
                decompressor.decompress(chunk, max_length=_INTEGRITY_CHUNK_BYTES)
            # `unused_data` holds what was fed past the stream's end; anything still unread in
            # the file counts too, since the last chunk may have stopped exactly at the end.
            trailing = bool(decompressor.unused_data) or bool(raw.read(1))
    except (lzma.LZMAError, EOFError, OSError, ValueError) as exc:
        raise _refuse_unreadable(archive_path, repr(exc)) from exc

    if decompressor.check == lzma.CHECK_NONE:
        raise _refuse_unreadable(
            archive_path,
            "the xz stream carries no integrity check (CHECK_NONE), so decoding it proves "
            "nothing about its contents",
        )
    if trailing:
        raise _refuse_unreadable(
            archive_path,
            "bytes follow the end of the xz stream — the file is not exactly one archive",
        )


def _extract_archive(
    archive_path: Path, verify_dir: Path, *, expected_manifest: Path
) -> None:
    """Decompress ``archive_path`` into ``verify_dir`` and check the manifest survived.

    ``filter="data"`` is what keeps a member from escaping ``verify_dir`` (absolute paths,
    ``..`` components, links) — never a hand-rolled path check.

    The integrity pass runs BEFORE ``verify_dir`` is created: an archive whose bytes will not
    come back has nothing to decompress into, and creating the directory first left an empty
    one behind that then blocked the operator's retry (review 2026-09-30 finding 4).
    """
    _require_intact_xz_stream(archive_path)
    verify_dir.mkdir(parents=True)
    try:
        with tarfile.open(archive_path, mode="r:xz") as archive:
            archive.extractall(verify_dir, filter="data")
    except TypeError as exc:
        # `extractall(filter=...)` landed in 3.11.4/3.12. On anything older this is a TypeError
        # about an unexpected keyword — an ENVIRONMENT fault, not a corrupt archive. Reporting
        # it as corruption would send an operator hunting a bad backup that is perfectly fine,
        # so it is named for what it is and never folded into the refusal below.
        raise RuntimeError(
            "verify_archive: this interpreter does not support tarfile's `filter=` argument "
            "(added in Python 3.11.4). Extraction is not attempted without it — the filter is "
            "what keeps an archive member from escaping verify_dir"
        ) from exc
    # `lzma.LZMAError` is named explicitly: it derives straight from `Exception`, so byte rot
    # inside the xz stream escapes an `OSError`/`TarError` catch entirely — the first shape
    # of corruption anyone tests, and the one that would otherwise propagate raw. (The
    # integrity pass above now reaches xz rot first; what is left here is a stream that
    # decodes cleanly but is not a readable tar.) This refusal DOES name verify_dir: unlike
    # the pass, it has created the directory and may have written members into it.
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
    """The manifest entry for a NON-optional member, or a refusal naming it.

    ``evidence``/``rcl``/``inbox`` are always present in a manifest :func:`backup_set` wrote;
    this guards a hand-edited or truncated one, so the failure names the member instead of
    surfacing as ``None`` having no attribute ``path``.
    """
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
    """Decompress ``archive_path`` into ``verify_dir`` and prove it holds what the manifest says.

    :func:`archive_backup_set` calls this on every archive it writes, so "compressed" and
    "verified" are never two separate operator steps that could drift apart. It is public in its
    own right for the other direction — re-checking an archive that has been sitting in cold
    storage, months after it was written, without producing a new one.

    Three checks, each fail-closed:

    1. The file is **exactly one intact xz stream**, decoded to its end and discarded before
       anything is extracted (:func:`_require_intact_xz_stream`) — so xz's own integrity check
       always runs, rather than only as far as the tar reader happens to go, and neither
       trailing bytes nor a checkless container can pass for a verified archive. Then the
       manifest inside it is byte-identical to ``manifest_path`` (``tarfile``'s ``r:xz``,
       ``filter="data"``).
    2. Every member's sha256 equals the digest the :class:`BackupSetManifest` records — the same
       check :func:`~tos_runtime.operations.backup_set.restore_set` performs on a restore
       (mutation M1), moved onto the round trip. This is the one an archive's own xz CRC cannot
       make: a re-packed archive holding a DIFFERENT but perfectly valid sqlite file
       decompresses cleanly and is caught only here.
    3. The evidence chain re-verifies out of the decompressed copy, via
       :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.verify_or_raise` under
       ``key_provider``'s own current generation — verbatim what ``restore_set`` does, so an
       archive is never held to a weaker standard than a restore.

    Args:
        archive_path: The ``gen{N}.set.tar.xz`` to check.
        manifest_path: The manifest that archive is held to. Read, never written.
        verify_dir: Scratch directory to decompress into. Must not already exist — a directory
            this call did not create could hide a stale file behind a member the archive failed
            to carry, turning a missing member into a passing verification. **Removed on
            success, kept on failure** so the decompressed copy is there to inspect; every
            refusal names it.
        key_provider: The evidence store's key source for check 3.

    Returns:
        The :class:`ArchiveVerification` — only on a fully passing round trip.

    Raises:
        BackupArchiveRefused: Any of checks 1-2 failed, or ``verify_dir`` already exists.
        tos_runtime.evidence.store.EvidenceCorruption: Check 3 failed (propagated unchanged — a
            corrupt CHAIN is a different fact from a corrupt ARCHIVE, never flattened into one).
    """
    if verify_dir.exists():
        raise BackupArchiveRefused(
            f"verify_archive: verify_dir {verify_dir} already exists — refusing to read back "
            "into a directory whose contents this call did not write"
        )
    manifest = BackupSetManifest.model_validate_json(manifest_path.read_text())
    _extract_archive(archive_path, verify_dir, expected_manifest=manifest_path)
    _refuse_unexpected_members(manifest, verify_dir, manifest_name=manifest_path.name)
    files_verified = _verify_archived_files(manifest, verify_dir)
    # Measured BEFORE the evidence store is opened: opening it writes WAL sidecars into
    # verify_dir, which are an artefact of this check and not part of what was archived.
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
    # Only once every check has passed. A failure path deliberately leaves verify_dir behind
    # (its refusal says where) — the decompressed copy is the evidence of what went wrong, and
    # a caller that retries passes a fresh directory anyway.
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
    """Compress one already-taken durable-set backup to ``archive_dir``, then prove it readable.

    Opt-in and strictly additive (evidence growth plan §2 A3): this reads the generation
    :func:`~tos_runtime.operations.backup_set.backup_set` already wrote. **It never touches the
    live data directory, and never touches the uncompressed backup tree either** — every path it
    writes is under ``archive_dir`` or ``verify_dir``. Disk does not go down; a verified cold
    copy accumulates (ADR-002-016 §17's "independently verified snapshot … raw material", which
    the eventual Track B purge needs to exist BEFORE it can delete anything).

    The manifest is archived alongside the files, so the archive is self-describing, and
    :func:`verify_archive` is then run against what was just written — there is no path through
    this function that produces an unverified archive.

    **The final name appears only after verification passes.** Compression writes to
    ``gen{N}.set.tar.xz.partial`` and renames on success; a failed verification unlinks the
    partial. Without that, a failed run left an unverified ``.tar.xz`` sitting in the cold-storage
    directory looking exactly like a good one — and, because this function refuses to overwrite
    an existing archive for a generation, that leftover then blocked every retry (review
    MEDIUM-4).

    Args:
        manifest_path: The ``gen{N}.set.manifest.json``
            :func:`~tos_runtime.operations.backup_set.backup_set` wrote.
        archive_dir: Where ``gen{N}.set.tar.xz`` is written — an argument, never derived from
            the backup tree, because the whole point is to hold the cold copy somewhere else.
            Created if absent; an existing archive for this generation is never overwritten.
        verify_dir: Forwarded to :func:`verify_archive`.
        key_provider: Forwarded to :func:`verify_archive`.
        preset: stdlib ``lzma`` preset 0-9 (:data:`DEFAULT_XZ_PRESET`).

    Returns:
        The :class:`ArchiveVerification` — only on a fully passing round trip.

    Raises:
        BackupArchiveRefused: ``preset`` is outside 0-9, a source file the manifest names is
            missing, the archive for this generation already exists, or any
            :func:`verify_archive` check failed.
    """
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
