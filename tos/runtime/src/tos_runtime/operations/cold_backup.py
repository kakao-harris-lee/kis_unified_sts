"""One scheduled, config-driven cold-backup run (evidence growth plan §2 A3,"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Literal, TypeVar

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

_T = TypeVar("_T")

COLD_BACKUP_CONFIG_NAME = "evidence_cold_backup.yaml"

_REPORT_SUFFIX = ".cold-backup.report.json"

_PATH_KEYS: tuple[str, ...] = ("backup_root", "archive_dir", "verify_root")

_FREE_BYTES_KEY = "minimum_free_bytes"

_XZ_PRESET_KEY = "xz_preset"


class ColdBackupRefused(RuntimeError):
    """Raised by :func:`load_cold_backup_config` and :func:`cold_backup` — the config is"""


class ColdBackupFailed(RuntimeError):
    """The environment broke part-way through a run — **not** a refusal."""

    def __init__(self, stage: str, cause: BaseException) -> None:
        """Wrap ``cause`` as the failure of ``stage`` (``"snapshot"``/``"archive"``/"""
        super().__init__(f"{stage} failed — {type(cause).__name__}: {cause}")
        self.stage = stage

    def __reduce__(
        self,
    ) -> tuple[
        Callable[..., ColdBackupFailed],
        tuple[type[ColdBackupFailed], str, str],
        dict[str, Any],
    ]:
        """Rebuild through :func:`_rebuild_cold_backup_failed` instead of ``cls(*args)``."""
        return (
            _rebuild_cold_backup_failed,
            (type(self), self.args[0], self.stage),
            self.__dict__,
        )


def _rebuild_cold_backup_failed(
    cls: type[ColdBackupFailed], message: str, stage: str
) -> ColdBackupFailed:
    """Reconstruct a :class:`ColdBackupFailed` — or a subclass — from its stored parts."""
    rebuilt = cls.__new__(cls)
    BaseException.__init__(rebuilt, message)
    rebuilt.stage = stage
    return rebuilt


class FilesystemFreeSpace(BaseModel):
    """Free space on one filesystem the run writes to, and which configured roots share it."""

    model_config = ConfigDict(frozen=True)

    roots: tuple[str, ...]
    measured_path: str
    free_bytes: int


class ColdBackupConfig(BaseModel):
    """The loaded ``evidence_cold_backup.yaml`` (see that file's example for each key's"""

    model_config = ConfigDict(frozen=True)

    backup_root: Path
    archive_dir: Path
    verify_root: Path
    minimum_free_bytes: int
    xz_preset: int


class ColdBackupReport(BaseModel):
    """One cold-backup run's record — written as JSON into ``archive_dir`` and returned."""

    model_config = ConfigDict(frozen=True)

    generation: int
    manifest_path: str
    archive_path: str
    report_path: str
    source_bytes: int
    archive_bytes: int
    files_verified: tuple[str, ...]
    chain_verified: Literal[True] = True
    free_space_before: tuple[FilesystemFreeSpace, ...]
    free_space_after: tuple[FilesystemFreeSpace, ...]
    minimum_free_bytes: int
    free_bytes_below_minimum_after: bool


def _require_mapping(raw: object, path: Path) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise ColdBackupRefused(
            f"load_cold_backup_config: {path} is not a YAML mapping "
            f"(got {type(raw).__name__}) — refused"
        )
    return raw


def _require_filled(raw: Mapping[str, object], key: str, path: Path) -> object:
    """``raw[key]``, refusing both a missing KEY and a ``null``/named-TBD VALUE."""
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
    """The optional ``xz_preset`` (absent ⇒ :data:`DEFAULT_XZ_PRESET`; see"""
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
    """Load ``evidence_cold_backup.yaml`` fail-closed."""
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
    """The nearest ancestor of ``path`` (itself included) holding a ``.git`` entry, or ``None``."""
    resolved = path.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _refuse_unsafe_destination(path: Path, *, label: str, data_dir: Path) -> None:
    """Refuse a destination that is not somewhere a cold copy may live."""
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
        raise ColdBackupRefused(
            f"cold_backup: {label} {resolved} exists and is not a directory — refused before "
            "anything is written"
        )


def _refuse_overlapping_destinations(roots: Mapping[str, Path]) -> None:
    """Refuse two roots that are the same directory, or one inside another."""
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
    """``path`` itself, or its nearest existing ancestor directory."""
    for candidate in (path, *path.parents):
        if candidate.is_dir():
            return candidate
    raise ColdBackupRefused(
        f"cold_backup: no existing directory found at or above {path} — refused before "
        "anything is written"
    )


def _free_space(roots: Mapping[str, Path]) -> tuple[FilesystemFreeSpace, ...]:
    """Free space on each DISTINCT filesystem ``roots`` lands on, labelled by the config keys"""
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
    """The measured filesystems below ``minimum_free_bytes`` (empty when all pass)."""
    return tuple(entry for entry in free_space if entry.free_bytes < minimum_free_bytes)


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
    """The highest generation COLD STORAGE already holds, or ``None``."""
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
    """Refuse before the snapshot if anything for ``generation`` is already on disk."""
    for label, path in _cold_artifacts(config, generation):
        if path.exists():
            raise ColdBackupRefused(
                f"cold_backup: the {label} for generation {generation} already exists at "
                f"{path} — refused before anything is written. Nothing here overwrites a "
                "cold copy or its report; move it aside, or let the next run take a higher "
                "generation"
            )


#: ``PRAGMA user_version`` is not this code's — before a single chain row is read. So it is a
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
    """Check every destination, and return the ``label -> root`` map the rest of the run uses."""
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
    """Measure every filesystem the run writes to and refuse if any is below the floor."""
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
    """Run ``action``, letting :data:`_PASSTHROUGH_REFUSALS` through and wrapping anything"""
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
    """Take the next generation's durable-set snapshot, archive it, verify it, record it."""
    roots = _preflight_destinations(config, data_dir)
    free_before = _preflight_free_space(roots, config.minimum_free_bytes)

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
