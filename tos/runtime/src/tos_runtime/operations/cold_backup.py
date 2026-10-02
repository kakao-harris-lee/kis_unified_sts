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
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from tos_runtime._named_tbd import reject_named_tbd
from tos_runtime.evidence.store import KeyProvider
from tos_runtime.operations.backup_archive import (
    DEFAULT_XZ_PRESET,
    archive_backup_set,
)
from tos_runtime.operations.backup_set import (
    DurableSetPaths,
    backup_set,
    manifest_path_for,
    next_generation,
)

__all__ = [
    "COLD_BACKUP_CONFIG_NAME",
    "ColdBackupConfig",
    "ColdBackupRefused",
    "ColdBackupReport",
    "cold_backup",
    "load_cold_backup_config",
]

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


class ColdBackupConfig(BaseModel):
    """The loaded ``evidence_cold_backup.yaml`` (see that file's example for each key's
    meaning). Paths are absolute and already checked against each other and the live data
    directory by :func:`cold_backup`, not here — this object is the parsed file, not a
    sanctioned destination set."""

    model_config = ConfigDict(frozen=True)

    #: Where the UNCOMPRESSED ``gen{N}/`` generations and their manifests live.
    backup_root: Path
    #: Cold storage: where ``gen{N}.set.tar.xz`` and ``gen{N}.cold-backup.report.json`` land.
    archive_dir: Path
    #: Parent of the per-generation scratch directory the archive is decompressed into for
    #: verification. The child itself must not exist yet and is removed on success.
    verify_root: Path
    #: Refuse to start when ``archive_dir``'s filesystem has less than this much free.
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
    #: Free bytes on ``archive_dir``'s filesystem, measured before the snapshot and after the
    #: archive was verified. Reported, never assumed — the ratio an operator sizes storage from
    #: is a measurement of this host, not a constant from the plan's §1 table.
    free_bytes_before: int
    free_bytes_after: int
    minimum_free_bytes: int
    #: ``free_bytes_after < minimum_free_bytes``. THIS run completed and is verified; the next
    #: one would refuse at its preflight. The capacity alarm the plan's §5 asks for is this
    #: flag plus the preflight refusal, and the answer to it is more storage — never deleting
    #: cold copies, which is Track B (module docstring).
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
    if value < 0:
        raise ColdBackupRefused(
            f"load_cold_backup_config: {_FREE_BYTES_KEY!r} in {path} is {value}, which is "
            "negative — refused"
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


def _is_within(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


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
    if _is_within(resolved, live):
        raise ColdBackupRefused(
            f"cold_backup: {label} {resolved} is inside the live data directory {live} — "
            "refused. A cold copy that lives in the directory it copies is not a cold copy"
        )
    if _is_within(live, resolved):
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


def _free_bytes(path: Path) -> int:
    """Free bytes on the filesystem that will hold ``path``.

    ``path`` need not exist yet (the first run creates ``archive_dir``), so this measures the
    nearest existing ancestor — the same filesystem, since the missing components will be
    created under it.
    """
    for candidate in (path, *path.parents):
        if candidate.is_dir():
            return shutil.disk_usage(candidate).free
    raise ColdBackupRefused(
        f"cold_backup: no existing directory found at or above {path} — refused before "
        "anything is written"
    )


def cold_backup(
    data_dir: Path, config: ColdBackupConfig, *, key_provider: KeyProvider
) -> ColdBackupReport:
    """Take the next generation's durable-set snapshot, archive it, verify it, record it.

    The whole unattended run, in the order a refusal is cheapest: destinations are checked
    against each other and the live directory, the cold-storage filesystem's free space is
    checked against the configured floor, and only then is anything written. The three steps
    that follow are the existing ones, unchanged —
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
            the runtime is stopped.
        config: The loaded :func:`load_cold_backup_config` result.
        key_provider: The evidence store's key source, for the archive's chain re-verification.

    Returns:
        The :class:`ColdBackupReport` — only on a fully verified run.

    Raises:
        ColdBackupRefused: A destination is refused, or free space is below the floor.
        tos_runtime.operations.backup_set.BackupSetRefused: The snapshot itself refused.
        tos_runtime.operations.backup_archive.BackupArchiveRefused: The archive could not be
            written, read back, or did not hold what the manifest attests.
    """
    for label, destination in (
        ("archive_dir", config.archive_dir),
        ("backup_root", config.backup_root),
        ("verify_root", config.verify_root),
    ):
        _refuse_unsafe_destination(destination, label=label, data_dir=data_dir)

    free_before = _free_bytes(config.archive_dir)
    if free_before < config.minimum_free_bytes:
        raise ColdBackupRefused(
            f"cold_backup: cold storage at {config.archive_dir} has {free_before} bytes free, "
            f"below the configured floor of {config.minimum_free_bytes} — refused before "
            "anything is written. This module has no retention and never deletes a cold copy "
            "(pruning verified copies is Track B, ADR-002-016 §17): add storage, or move "
            "existing archives to another medium"
        )

    generation = next_generation(config.backup_root)
    paths = DurableSetPaths.from_data_dir(data_dir)
    backup_set(paths, config.backup_root, generation)
    manifest_path = manifest_path_for(config.backup_root, generation)
    verification = archive_backup_set(
        manifest_path,
        config.archive_dir,
        config.verify_root / f"gen{generation}.verify",
        key_provider=key_provider,
        preset=config.xz_preset,
    )

    free_after = _free_bytes(config.archive_dir)
    report_path = config.archive_dir / f"gen{generation}{_REPORT_SUFFIX}"
    report = ColdBackupReport(
        generation=generation,
        manifest_path=str(manifest_path),
        archive_path=verification.archive_path,
        report_path=str(report_path),
        source_bytes=verification.source_bytes,
        archive_bytes=verification.archive_bytes,
        files_verified=verification.files_verified,
        free_bytes_before=free_before,
        free_bytes_after=free_after,
        minimum_free_bytes=config.minimum_free_bytes,
        free_bytes_below_minimum_after=free_after < config.minimum_free_bytes,
    )
    report_path.write_text(report.model_dump_json(indent=2))
    return report
