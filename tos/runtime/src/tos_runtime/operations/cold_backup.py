"""One scheduled, config-driven cold-backup run (evidence growth plan §2 A3,
``docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md``).

**This module adds no backup, compression or verification machinery — it is the operator
entry point over the three that already exist.** :func:`cold_backup` allocates the next
generation, calls :func:`~tos_runtime.operations.backup_set.backup_set` for the snapshot,
:func:`~tos_runtime.operations.backup_archive.archive_backup_set` for the xz archive and its
read-back verification, and writes one JSON report. PR #816 landed those two halves behind
``backup-set --archive-dir``, with every coordinate typed on the command line and the
generation counted by hand; §7.1.6 of that landing left "보관 경로 용량 경보" and scheduling
explicitly carried over. This closes both, and is the surface a cron line can call unattended.

**Nothing here deletes anything, and there is no retention knob.** Neither
:func:`~tos_runtime.operations.backup_set.backup_set` ("Never deleted, never overwritten") nor
:mod:`~tos_runtime.operations.backup_archive` ("an archive is an addition") has one, and this
module deliberately does not invent a second, narrower deletion policy beside the one
ADR-002-016 §17 governs: pruning verified cold copies is Track B material (plan §4 — five
unmet preconditions), not an operations convenience. Cold copies therefore accumulate, which
is what :attr:`ColdBackupConfig.minimum_free_bytes` exists to make visible rather than
survivable-by-deletion.

**The live data directory is only ever READ** — this module opens no store in it, and the
report is written into the cold-storage directory, never beside the live files.

**Why the run's record is a JSON file and not an evidence row.** The one existing
operations→evidence mechanism is
:func:`tos_runtime.compose._operations_wiring._observe_backup`, which appends
``BACKUP_SET_OBSERVED`` *at boot*, from the highest-generation manifest under an operator-
supplied ``backup_root`` — the runtime observes operations artifacts on its next boot; the
operations CLI does not write into the live chain. It could not here anyway: a cold backup
runs with the runtime stopped and the stores closed (:func:`backup_set`'s own documented
precondition), and appending a row would move the very bytes
:func:`~tos_runtime.operations.backup_archive.archive_backup_set` just proved it copied. So
the run's record is :class:`ColdBackupReport`, serialized next to the archive it describes.
Teaching the boot-time observer to read that report is a follow-up, registered in the plan's
landing record, not something invented here.

Firewall: stdlib (``json``, ``shutil``) + ``pydantic`` + ``pyyaml`` + ``tos_runtime.evidence``
+ ``tos_runtime.operations.backup_set``/``backup_archive`` + ``tos_runtime._named_tbd`` only
(R1 allowlist).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Literal, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict

from tos_runtime._named_tbd import reject_named_tbd
from tos_runtime.custody.ports import CustodyError
from tos_runtime.evidence.store import EvidenceCorruption, KeyProvider
from tos_runtime.operations.backup_archive import (
    DEFAULT_XZ_PRESET,
    BackupArchiveRefused,
    archive_backup_set,
)
from tos_runtime.operations.backup_set import (
    BackupSetRefused,
    DurableSetPaths,
    backup_set,
    generation_number,
    manifest_path_for,
    next_generation,
)
from tos_runtime.operations.key_rotation import KeyContinuityRefused
from tos_runtime.operations.schema_ledger import SchemaVersionRefused

__all__ = [
    "COLD_BACKUP_CONFIG_NAME",
    "ColdBackupConfig",
    "ColdBackupFailed",
    "ColdBackupRefused",
    "ColdBackupReport",
    "FilesystemFreeSpace",
    "cold_backup",
    "load_cold_backup_config",
]

#: Return type of whatever :func:`_stage` is wrapping.
_T = TypeVar("_T")

#: The config file name directly under the operator's ``--config-dir`` (mirrors every other
#: ``tos_runtime`` loader's own ``*_CONFIG_NAME`` convention; shaped like
#: ``tos/runtime/config/evidence_cold_backup.example.yaml``).
COLD_BACKUP_CONFIG_NAME = "evidence_cold_backup.yaml"

#: Written beside the archive it describes, one per generation.
_REPORT_SUFFIX = ".cold-backup.report.json"

#: The three path keys. Required, and required to be FILLED — a cold backup with a guessed
#: destination is worse than no cold backup, because it looks like one.
_PATH_KEYS: tuple[str, ...] = ("backup_root", "archive_dir", "verify_root")

#: Required and required to be filled, for the same reason: an alarm with no threshold is not
#: an alarm (project memory ``guards-that-admit-what-they-name``).
_FREE_BYTES_KEY = "minimum_free_bytes"

#: OPTIONAL, unlike the four above — and the asymmetry is deliberate. A missing compression
#: preset has a correct answer this codebase has already named
#: (:data:`~tos_runtime.operations.backup_archive.DEFAULT_XZ_PRESET`); a missing capacity floor
#: or a missing destination does not, and inventing one would state an unapproved operational
#: bound as decided.
_XZ_PRESET_KEY = "xz_preset"


class ColdBackupRefused(RuntimeError):
    """Raised by :func:`load_cold_backup_config` and :func:`cold_backup` — the config is
    missing/malformed/unfilled, a destination is not somewhere a cold copy may live, or the
    cold-storage filesystem is below its configured free-space floor.

    Refusals from the two reused layers keep their own types
    (:class:`~tos_runtime.operations.backup_set.BackupSetRefused`,
    :class:`~tos_runtime.operations.backup_archive.BackupArchiveRefused`) and are never
    flattened into this one: "the archive did not read back" and "the destination is wrong"
    are different facts for the operator reading a cron mail.
    """


class ColdBackupFailed(RuntimeError):
    """The environment broke part-way through a run — **not** a refusal.

    :class:`ColdBackupRefused` means a rule said no before anything happened. This means the
    run was admissible and something underneath it failed: the runtime was still holding a
    sqlite handle, the disk filled mid-copy, custody was unreadable, a manifest would not
    parse. Those surface as ``sqlite3.OperationalError``/``OSError``/``ValidationError`` and
    a dozen other types with no common base narrower than ``Exception``, so they are wrapped
    once, here, with the STAGE they came from and the original exception as ``__cause__``.

    Why wrap at all rather than let them propagate: this command's primary caller is ``cron``,
    and a traceback in a mail body is a worse report than one line naming the stage. Why not
    fold them into :class:`ColdBackupRefused`: a full disk is not a policy decision, and the
    operator's next action differs (fix the host vs. fix the config).
    """

    def __init__(self, stage: str, cause: BaseException) -> None:
        """Wrap ``cause`` as the failure of ``stage`` (``"snapshot"``/``"archive"``/
        ``"report"``)."""
        super().__init__(f"{stage} failed — {type(cause).__name__}: {cause}")
        self.stage = stage


class FilesystemFreeSpace(BaseModel):
    """Free space on one filesystem the run writes to, and which configured roots share it."""

    model_config = ConfigDict(frozen=True)

    #: Config keys that resolved onto this filesystem — more than one when they share a
    #: device, which is why the floor is not simply checked three times.
    roots: tuple[str, ...]
    #: The directory actually measured: the root itself, or its nearest existing ancestor
    #: when the root has not been created yet.
    measured_path: str
    free_bytes: int


class ColdBackupConfig(BaseModel):
    """The loaded ``evidence_cold_backup.yaml`` (see that file's example for each key's
    meaning). Paths are absolute; whether they are ADMISSIBLE — against the live data
    directory and against each other — is :func:`cold_backup`'s check, not this object's.
    This is the parsed file, not a sanctioned destination set."""

    model_config = ConfigDict(frozen=True)

    #: Where the UNCOMPRESSED ``gen{N}/`` generations and their manifests live.
    backup_root: Path
    #: Cold storage: where ``gen{N}.set.tar.xz`` and ``gen{N}.cold-backup.report.json`` land.
    archive_dir: Path
    #: Parent of the per-generation scratch directory the archive is decompressed into for
    #: verification. The child itself must not exist yet and is removed on success.
    verify_root: Path
    #: Refuse to start when ANY filesystem this run writes to has less than this much free
    #: (``archive_dir``, ``backup_root`` and ``verify_root``, deduplicated by device).
    minimum_free_bytes: int
    #: stdlib ``lzma`` preset 0-9.
    xz_preset: int


class ColdBackupReport(BaseModel):
    """One cold-backup run's record — written as JSON into ``archive_dir`` and returned.

    Only ever constructed after :func:`~tos_runtime.operations.backup_archive.archive_backup_set`
    returned, i.e. after the archive was read back, every member digest re-checked against the
    manifest and the evidence chain re-verified: the same "receipt in-hand ⇒ already proved"
    shape :class:`~tos_runtime.operations.backup_archive.ArchiveVerification` uses. There is no
    report for a run that did not fully verify.
    """

    model_config = ConfigDict(frozen=True)

    generation: int
    manifest_path: str
    archive_path: str
    report_path: str
    source_bytes: int
    archive_bytes: int
    files_verified: tuple[str, ...]
    chain_verified: Literal[True] = True
    #: Free space on EVERY filesystem this run writes to, measured before the snapshot and
    #: after the archive was verified, one entry per distinct device. Three roots and not one:
    #: ``backup_root`` holds the UNCOMPRESSED generations and is the fastest-growing tree this
    #: command writes, so measuring only ``archive_dir`` would watch the wrong disk whenever
    #: the runbook's own advice to separate media is followed. Reported, never assumed.
    free_space_before: tuple[FilesystemFreeSpace, ...]
    free_space_after: tuple[FilesystemFreeSpace, ...]
    minimum_free_bytes: int
    #: Any ``free_space_after`` entry below the floor. THIS run completed and is verified; the
    #: next one refuses at its preflight. The capacity alarm the plan's §5 asks for is this
    #: flag plus that refusal, and the answer to it is more storage — never deleting cold
    #: copies, which is Track B (module docstring).
    free_bytes_below_minimum_after: bool


def _require_mapping(raw: object, path: Path) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise ColdBackupRefused(
            f"load_cold_backup_config: {path} is not a YAML mapping "
            f"(got {type(raw).__name__}) — refused"
        )
    return raw


def _require_filled(raw: Mapping[str, object], key: str, path: Path) -> object:
    """``raw[key]``, refusing both a missing KEY and a ``null``/named-TBD VALUE.

    Unlike :class:`~tos_runtime.evidence.retention.RetentionPolicy`, which accepts a ``null``
    value as an honest "this class has no approved minimum yet", every key here is a
    coordinate or a floor this module cannot act without. A ``null`` destination has no
    defensible fallback and a ``null`` floor would disable the alarm silently, so both refuse.
    """
    if key not in raw:
        raise ColdBackupRefused(
            f"load_cold_backup_config: {path} is missing the required key {key!r} — refused "
            "(fail-closed; see tos/runtime/config/evidence_cold_backup.example.yaml)"
        )
    value = raw[key]
    if value is None:
        raise ColdBackupRefused(
            f"load_cold_backup_config: {key!r} in {path} is still null (named-TBD) — "
            "operator-fill it before scheduling a cold backup; this loader never invents a "
            "destination or a free-space floor"
        )
    reject_named_tbd(
        value,
        field=key,
        context=f"load_cold_backup_config: {path}",
        error_cls=ColdBackupRefused,
    )
    return value


def _require_absolute_path(raw: Mapping[str, object], key: str, path: Path) -> Path:
    value = _require_filled(raw, key, path)
    if not isinstance(value, str):
        raise ColdBackupRefused(
            f"load_cold_backup_config: {key!r} in {path} must be a string path "
            f"(got {type(value).__name__}) — refused"
        )
    candidate = Path(value)
    # Tilde FIRST, and not as a second clause after the is_absolute() check: a path starting
    # with "~" is never absolute, so an is_absolute() refusal would reach it first and this
    # branch would be unreachable — a guard that names a case it can never actually catch.
    if candidate.parts and candidate.parts[0].startswith("~"):
        raise ColdBackupRefused(
            f"load_cold_backup_config: {key!r} in {path} starts with {candidate.parts[0]!r} — "
            "refused. This loader performs no tilde expansion, so the path would be taken "
            "literally; write the real absolute path"
        )
    if not candidate.is_absolute():
        raise ColdBackupRefused(
            f"load_cold_backup_config: {key!r} in {path} is {value!r}, which is not an "
            "absolute path — refused. A relative destination depends on the working directory "
            "of whoever happened to run the cron line"
        )
    return candidate


def _require_free_bytes(raw: Mapping[str, object], path: Path) -> int:
    value = _require_filled(raw, _FREE_BYTES_KEY, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ColdBackupRefused(
            f"load_cold_backup_config: {_FREE_BYTES_KEY!r} in {path} must be an integer "
            f"number of bytes (got {type(value).__name__}) — refused"
        )
    if value <= 0:
        raise ColdBackupRefused(
            f"load_cold_backup_config: {_FREE_BYTES_KEY!r} in {path} is {value} — refused. "
            "Zero and negative are not floors: `free < 0` is never true, so the preflight "
            "would never refuse and the alarm would be off while the file looked filled in. "
            "That is the same silent-disable this loader refuses a null for"
        )
    return value


def _resolve_xz_preset(raw: Mapping[str, object], path: Path) -> int:
    """The optional ``xz_preset`` (absent ⇒ :data:`DEFAULT_XZ_PRESET`; see
    :data:`_XZ_PRESET_KEY` for why this one key may be absent).

    A PRESENT-but-null value still refuses: "the operator wrote the key and left it empty" is
    not the same statement as "the operator did not configure compression", and treating it as
    the default would make a half-filled file look complete.
    """
    if _XZ_PRESET_KEY not in raw:
        return DEFAULT_XZ_PRESET
    value = _require_filled(raw, _XZ_PRESET_KEY, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ColdBackupRefused(
            f"load_cold_backup_config: {_XZ_PRESET_KEY!r} in {path} must be an integer 0-9 "
            f"(got {type(value).__name__}) — refused"
        )
    if value not in range(10):
        raise ColdBackupRefused(
            f"load_cold_backup_config: {_XZ_PRESET_KEY!r} in {path} is {value}, outside the "
            "0-9 range stdlib lzma accepts — refused"
        )
    return value


def load_cold_backup_config(path: Path) -> ColdBackupConfig:
    """Load ``evidence_cold_backup.yaml`` fail-closed.

    Args:
        path: The YAML file (shaped like
            ``tos/runtime/config/evidence_cold_backup.example.yaml``).

    Returns:
        The loaded :class:`ColdBackupConfig`.

    Raises:
        ColdBackupRefused: The file is missing or unreadable, is not a mapping, omits a
            required key, leaves one ``null``/``"TBD"``, carries a non-absolute path, or
            carries an out-of-range ``xz_preset``.
    """
    if not path.is_file():
        raise ColdBackupRefused(
            f"load_cold_backup_config: {path} does not exist — refused. A cold backup's "
            "destinations are configuration, never flags this module defaults for you "
            "(see tos/runtime/config/evidence_cold_backup.example.yaml)"
        )
    try:
        raw_document = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ColdBackupRefused(
            f"load_cold_backup_config: {path} could not be read as YAML ({exc!r}) — refused"
        ) from exc
    raw = _require_mapping(raw_document, path)
    paths = {key: _require_absolute_path(raw, key, path) for key in _PATH_KEYS}
    return ColdBackupConfig(
        backup_root=paths["backup_root"],
        archive_dir=paths["archive_dir"],
        verify_root=paths["verify_root"],
        minimum_free_bytes=_require_free_bytes(raw, path),
        xz_preset=_resolve_xz_preset(raw, path),
    )


def _enclosing_worktree(path: Path) -> Path | None:
    """The nearest ancestor of ``path`` (itself included) holding a ``.git`` entry, or ``None``.

    A plain ancestor walk, never ``git rev-parse``: ``subprocess`` is forbidden in runtime
    scope (``tools/tos_firewall_check.py`` rule R1), so the precedent this mirrors —
    ``scripts/tos/render_paper_config.py``'s ``_refuse_output_inside_repo``, which keeps a
    rendered config holding an account number out of the worktree — cannot be reused verbatim.
    ``.git`` is checked with :meth:`~pathlib.Path.exists` rather than ``is_dir``: a linked
    worktree's ``.git`` is a FILE, and those are exactly the checkouts this repo's parallel
    lanes work in.
    """
    resolved = path.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _refuse_unsafe_destination(path: Path, *, label: str, data_dir: Path) -> None:
    """Refuse a destination that is not somewhere a cold copy may live.

    Three refusals, each for a different way a cold copy stops being one:

    * **Inside (or equal to) the live data directory.** The copy would grow the very directory
      it is a copy of, and the next generation's snapshot would be taken over a tree that now
      contains the previous generation's archive.
    * **An ancestor of the live data directory.** The live runtime would then share a
      filesystem subtree with unbounded, never-pruned cold storage — a full cold-storage
      directory would take the runtime down with it.
    * **Inside a git worktree.** The same guard
      ``scripts/tos/render_paper_config.py::_refuse_output_inside_repo`` applies to rendered
      configs: one missing ``.gitignore`` line and multi-gigabyte archives of the evidence
      chain are a commit away.
    """
    resolved = path.resolve()
    live = data_dir.resolve()
    if resolved.is_relative_to(live):
        raise ColdBackupRefused(
            f"cold_backup: {label} {resolved} is inside the live data directory {live} — "
            "refused. A cold copy that lives in the directory it copies is not a cold copy"
        )
    if live.is_relative_to(resolved):
        raise ColdBackupRefused(
            f"cold_backup: {label} {resolved} CONTAINS the live data directory {live} — "
            "refused. Cold storage grows without bound (this module has no retention), and "
            "filling it would take the live runtime's own filesystem subtree with it"
        )
    worktree = _enclosing_worktree(resolved)
    if worktree is not None:
        raise ColdBackupRefused(
            f"cold_backup: {label} {resolved} is inside the git worktree {worktree} — "
            "refused. Evidence archives belong outside the repository; one missing "
            ".gitignore line would commit them"
        )
    if resolved.exists() and not resolved.is_dir():
        # Checked HERE, before the snapshot, because the failure otherwise lands much later
        # and much worse: free space resolves to the nearest existing ancestor (so the
        # preflight passes), `backup_set` copies the whole durable set, and only then does
        # the archive step's own `mkdir` hit the file. A whole snapshot's work, for a typo.
        raise ColdBackupRefused(
            f"cold_backup: {label} {resolved} exists and is not a directory — refused before "
            "anything is written"
        )


def _refuse_overlapping_destinations(roots: Mapping[str, Path]) -> None:
    """Refuse two roots that are the same directory, or one inside another.

    The three trees serve different purposes and the example config says to put cold storage
    on another medium where possible; nesting them silently defeats that, and equality makes
    the verify scratch and the archive share a directory. This is the check
    :class:`ColdBackupConfig`'s docstring claims — it was claimed before it existed, which is
    the same "guard that names a case it never catches" shape the tilde-ordering fix in this
    branch removed, so it is written here rather than struck from the prose.

    Roots that merely share a PARENT are fine and ordinary; only equality and containment
    refuse.
    """
    resolved = {label: root.resolve() for label, root in roots.items()}
    labels = list(resolved)
    for index, left in enumerate(labels):
        for right in labels[index + 1 :]:
            if resolved[left] == resolved[right]:
                raise ColdBackupRefused(
                    f"cold_backup: {left} and {right} are the same directory "
                    f"({resolved[left]}) — refused"
                )
            for inner, outer in ((left, right), (right, left)):
                if resolved[inner].is_relative_to(resolved[outer]):
                    raise ColdBackupRefused(
                        f"cold_backup: {inner} {resolved[inner]} is inside {outer} "
                        f"{resolved[outer]} — refused. The three trees are kept apart on "
                        "purpose (the cold copy wants a different medium from the warm one, "
                        "and the verify scratch belongs in neither)"
                    )


def _measurable_ancestor(path: Path) -> Path:
    """``path`` itself, or its nearest existing ancestor directory.

    A root need not exist before the first run, and the missing components will be created
    under this directory on the same filesystem, so this is what free space and device
    identity are read from.
    """
    for candidate in (path, *path.parents):
        if candidate.is_dir():
            return candidate
    raise ColdBackupRefused(
        f"cold_backup: no existing directory found at or above {path} — refused before "
        "anything is written"
    )


def _free_space(roots: Mapping[str, Path]) -> tuple[FilesystemFreeSpace, ...]:
    """Free space on each DISTINCT filesystem ``roots`` lands on, labelled by the config keys
    that share it.

    Deduplicated by ``st_dev`` rather than measured once per root: three roots on one disk are
    one number, and reporting it three times would read as three independent headrooms that
    could be spent separately. Ordered by first appearance in ``roots`` so the report is
    stable across runs.
    """
    by_device: dict[int, tuple[list[str], Path, int]] = {}
    for label, root in roots.items():
        measured = _measurable_ancestor(root)
        device = measured.stat().st_dev
        existing = by_device.get(device)
        if existing is None:
            by_device[device] = (
                [label],
                measured,
                shutil.disk_usage(measured).free,
            )
            continue
        existing[0].append(label)
    return tuple(
        FilesystemFreeSpace(
            roots=tuple(labels), measured_path=str(measured), free_bytes=free
        )
        for labels, measured, free in by_device.values()
    )


def _below_floor(
    free_space: tuple[FilesystemFreeSpace, ...], minimum_free_bytes: int
) -> tuple[FilesystemFreeSpace, ...]:
    """The measured filesystems below ``minimum_free_bytes`` (empty when all pass).

    Named for what it computes, not ``_refuse_*`` like the guards around it: **this raises
    nothing.** One of its two callers turns a non-empty result into the preflight refusal;
    the other uses it as the report's after-the-fact alarm flag, which deliberately does NOT
    abort a backup that already verified. A ``_refuse_`` name here would promise the second
    caller aborts (review round 2, F8).
    """
    return tuple(entry for entry in free_space if entry.free_bytes < minimum_free_bytes)


#: The per-generation artifacts this module writes OUTSIDE ``backup_root``: the archive and
#: the report in ``archive_dir``, the scratch directory under ``verify_root``. Named once,
#: because both the allocator and the preflight have to agree on the full set.
_ARCHIVE_SUFFIX = ".set.tar.xz"


def _cold_artifacts(
    config: ColdBackupConfig, generation: int
) -> tuple[tuple[str, Path], ...]:
    """``(label, path)`` for every generation-scoped artifact outside ``backup_root``."""
    return (
        ("archive", config.archive_dir / f"gen{generation}{_ARCHIVE_SUFFIX}"),
        ("report", config.archive_dir / f"gen{generation}{_REPORT_SUFFIX}"),
        ("verify scratch", config.verify_root / f"gen{generation}.verify"),
    )


def _highest_cold_generation(config: ColdBackupConfig) -> int | None:
    """The highest generation COLD STORAGE already holds, or ``None``.

    The allocator cannot read ``backup_root`` alone. Cold storage is the tree an operator is
    told to prune by moving old archives elsewhere (runbook §6), and ``backup_root`` is the
    one that actually grows — so "backup_root emptied or recreated while archive_dir still
    holds gen1..genK" is an ordinary consequence of following the runbook, not an exotic
    state. Allocating from ``backup_root`` alone then picks ``1``, copies the entire durable
    set, and only then refuses on the existing ``gen1.set.tar.xz`` — every night, for K
    nights: the same "one event wedges the schedule" shape the directory-counting fix closed
    one layer down (review round 2, F2).
    """
    generations: list[int] = []
    for directory, suffixes, want_dir in (
        (config.archive_dir, (_ARCHIVE_SUFFIX, _REPORT_SUFFIX), False),
        (config.verify_root, (".verify",), True),
    ):
        if not directory.is_dir():
            continue
        for child in directory.iterdir():
            if child.is_dir() is not want_dir:
                continue
            for suffix in suffixes:
                found = generation_number(child.name, suffix)
                if found is not None:
                    generations.append(found)
                    break
    return max(generations) if generations else None


def _refuse_existing_artifacts(config: ColdBackupConfig, generation: int) -> None:
    """Refuse before the snapshot if anything for ``generation`` is already on disk.

    After :func:`_highest_cold_generation` this should be unreachable; it is written anyway
    because the cost of being wrong is a full durable-set copy thrown away, and because the
    report used to be written with a plain ``write_text`` that would have overwritten an
    existing one without a word.
    """
    for label, path in _cold_artifacts(config, generation):
        if path.exists():
            raise ColdBackupRefused(
                f"cold_backup: the {label} for generation {generation} already exists at "
                f"{path} — refused before anything is written. Nothing here overwrites a "
                "cold copy or its report; move it aside, or let the next run take a higher "
                "generation"
            )


#: Exceptions that are VERDICTS, not environment faults, and therefore pass through
#: :func:`_stage` with their own types intact.
#:
#: ``EvidenceCorruption``, ``KeyContinuityRefused`` and ``CustodyError`` were added by review
#: round 2, F1. The archive's third check re-verifies the evidence chain out of the
#: decompressed copy, and when that fails the fact is "**do not trust this copy**" — the most
#: serious thing this command can discover. Wrapping it as a stage failure filed it under "the
#: host broke, fix it and re-run", which is the wrong instruction in the one case where
#: re-running is not the answer. ``CustodyError`` and ``KeyContinuityRefused`` are the same
#: shape one layer out: keys that cannot be loaded, or a generation the chain does not
#: continue from.
#:
#: ``SchemaVersionRefused`` is the fourth application of the same criterion (plan §7.1.27
#: A3-F1). The store this list's third check constructs refuses to open when the on-disk
#: ``PRAGMA user_version`` is not this code's — a judgement about the TARGET, reached before
#: a single row is read. Measured on the deploy host, where every boot-proof corpus is at
#: evidence schema v1 (runbook ``docs/runbooks/tos-evidence-cold-backup.md`` §4-5-2 ②): it
#: came out as ``archive failed``, and the operator's next action is not another night of the
#: same cron line, it is the ``migrate`` CLI on that data directory.
_PASSTHROUGH_REFUSALS: tuple[type[BaseException], ...] = (
    ColdBackupRefused,
    BackupSetRefused,
    BackupArchiveRefused,
    EvidenceCorruption,
    KeyContinuityRefused,
    CustodyError,
    SchemaVersionRefused,
)


def _preflight_destinations(
    config: ColdBackupConfig, data_dir: Path
) -> dict[str, Path]:
    """Check every destination, and return the ``label -> root`` map the rest of the run uses.

    Split out of :func:`cold_backup` for the 100-line function budget
    (``tools/tos_size_budget.py``); no behaviour difference from having it inline.
    """
    roots = {
        "archive_dir": config.archive_dir,
        "backup_root": config.backup_root,
        "verify_root": config.verify_root,
    }
    for label, destination in roots.items():
        _refuse_unsafe_destination(destination, label=label, data_dir=data_dir)
    _refuse_overlapping_destinations(roots)
    return roots


def _preflight_free_space(
    roots: Mapping[str, Path], minimum_free_bytes: int
) -> tuple[FilesystemFreeSpace, ...]:
    """Measure every filesystem the run writes to and refuse if any is below the floor.

    Split out of :func:`cold_backup` for the 100-line function budget; returns the readings
    so the report can record what the preflight actually saw rather than measuring twice.
    """
    free_before = _free_space(roots)
    below = _below_floor(free_before, minimum_free_bytes)
    if below:
        detail = "; ".join(
            f"{'+'.join(entry.roots)} at {entry.measured_path} has {entry.free_bytes} bytes "
            "free"
            for entry in below
        )
        raise ColdBackupRefused(
            f"cold_backup: {detail} — below the configured floor of {minimum_free_bytes}; "
            "refused before anything is written. This module has no retention and never "
            "deletes a cold copy (pruning verified copies is Track B, ADR-002-016 §17): add "
            "storage, or move existing archives to another medium"
        )
    return free_before


def _stage(stage: str, action: Callable[[], _T]) -> _T:
    """Run ``action``, letting :data:`_PASSTHROUGH_REFUSALS` through and wrapping anything
    else as :class:`ColdBackupFailed` tagged with ``stage``.

    Those types pass untouched because each already says exactly what was wrong and which
    layer said so. Everything else is an environment fault with no common base class
    (:class:`ColdBackupFailed`'s own docstring), and wrapping it here is what lets the CLI
    print one line naming the stage instead of a traceback.
    """
    try:
        return action()
    except _PASSTHROUGH_REFUSALS:
        raise
    except (
        Exception
    ) as exc:  # noqa: BLE001 - see ColdBackupFailed: no common base exists
        raise ColdBackupFailed(stage, exc) from exc


def cold_backup(
    data_dir: Path, config: ColdBackupConfig, *, key_provider: KeyProvider
) -> ColdBackupReport:
    """Take the next generation's durable-set snapshot, archive it, verify it, record it.

    The whole unattended run, in the order a refusal is cheapest: the destinations are checked
    against the live directory and against each other, free space on every filesystem the run
    writes to is checked against the configured floor, and only then is anything written. The
    three steps that follow are the existing ones, unchanged —
    :func:`~tos_runtime.operations.backup_set.backup_set`, then
    :func:`~tos_runtime.operations.backup_archive.archive_backup_set` (which verifies the
    archive by reading it back; there is no "archived but unverified" outcome), then the JSON
    report.

    **The live data directory is only read.** Every path written is under ``archive_dir``,
    ``backup_root`` or ``verify_root``.

    Args:
        data_dir: The live durable set's directory. Every store in it must be CLOSED — the
            documented, mechanically undetectable precondition
            :func:`~tos_runtime.operations.backup_set.backup_set` already carries. In practice:
            the runtime is stopped. When it is not, the snapshot raises and this function
            reports it as a ``snapshot`` stage failure rather than a traceback.
        config: The loaded :func:`load_cold_backup_config` result.
        key_provider: The evidence store's key source, for the archive's chain re-verification.

    Returns:
        The :class:`ColdBackupReport` — only on a fully verified run.

    Raises:
        ColdBackupRefused: A destination is refused, free space is below the floor, or an
            artifact for the chosen generation already exists.
        tos_runtime.operations.backup_set.BackupSetRefused: The snapshot itself refused.
        tos_runtime.operations.backup_archive.BackupArchiveRefused: The archive could not be
            written, read back, or did not hold what the manifest attests.
        tos_runtime.evidence.store.EvidenceCorruption: The archived chain did not
            re-verify — propagated unchanged (:data:`_PASSTHROUGH_REFUSALS`), because "do not
            trust this copy" is a verdict, not a host fault.
        tos_runtime.custody.ports.CustodyError: Custody could not be loaded. Raised from the
            PREFLIGHT, before anything is copied.
        tos_runtime.operations.schema_ledger.SchemaVersionRefused: The archived store is at a
            different schema version than this code — propagated unchanged
            (:data:`_PASSTHROUGH_REFUSALS`), because the fix is the ``migrate`` CLI on the
            source data directory, not a re-run. The uncompressed snapshot is already complete
            when this arrives.
        ColdBackupFailed: Anything underneath broke — a held sqlite handle, a full disk,
            an unparseable manifest. Carries the stage and the original exception as
            ``__cause__``.
    """
    roots = _preflight_destinations(config, data_dir)
    free_before = _preflight_free_space(roots, config.minimum_free_bytes)

    # Custody BEFORE the snapshot. `FileKeyProvider.__init__` only stores fields, so a wrong
    # or unreadable custody root was previously discovered by the archive's chain check —
    # after the whole durable set had been copied and compressed — and arrived labelled as an
    # archive-stage fault. The CLI's "custody failed" branch named a case it could not catch
    # (review round 2, F3).
    _stage("custody", key_provider.current)

    generation = max(
        _stage("snapshot", lambda: next_generation(config.backup_root)),
        (_highest_cold_generation(config) or 0) + 1,
    )
    _refuse_existing_artifacts(config, generation)
    paths = DurableSetPaths.from_data_dir(data_dir)
    _stage("snapshot", lambda: backup_set(paths, config.backup_root, generation))
    manifest_path = manifest_path_for(config.backup_root, generation)
    verification = _stage(
        "archive",
        lambda: archive_backup_set(
            manifest_path,
            config.archive_dir,
            _cold_artifacts(config, generation)[2][1],
            key_provider=key_provider,
            preset=config.xz_preset,
        ),
    )

    free_after = _free_space(roots)
    report_path = _cold_artifacts(config, generation)[1][1]
    report = ColdBackupReport(
        generation=generation,
        manifest_path=str(manifest_path),
        archive_path=verification.archive_path,
        report_path=str(report_path),
        source_bytes=verification.source_bytes,
        archive_bytes=verification.archive_bytes,
        files_verified=verification.files_verified,
        free_space_before=free_before,
        free_space_after=free_after,
        minimum_free_bytes=config.minimum_free_bytes,
        free_bytes_below_minimum_after=bool(
            _below_floor(free_after, config.minimum_free_bytes)
        ),
    )
    _stage("report", lambda: report_path.write_text(report.model_dump_json(indent=2)))
    return report
