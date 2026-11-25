"""Durable-set backup / restore / restore-drill (TOS Phase 5 W4 plan §2 decisions 1-2; the"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict
from tos.canonical import CanonicalizationScheme

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay import ReplayableCore, ReplayVerdict, replay_engine
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME
from tos_runtime.recovery.readiness import ReadinessVerdict
from tos_runtime.venue_ledger.synthetic import VENUE_LEDGER_FILE_NAME

__all__ = [
    "MANIFEST_SUFFIX",
    "BackupSetManifest",
    "BackupSetRefused",
    "ComposeForDrill",
    "DurableSetPaths",
    "EvidenceBackupFacts",
    "FileBackupEntry",
    "InboxBackupFacts",
    "RclBackupFacts",
    "RestoreDrillVerdict",
    "RestoreRefused",
    "RestoredSet",
    "backup_set",
    "generation_number",
    "manifest_path_for",
    "next_generation",
    "restore_drill",
    "restore_set",
]

EVIDENCE_FILE_NAME = "evidence.sqlite3"
RCL_FILE_NAME = "rcl.sqlite3"
INBOX_FILE_NAME = "inbox.sqlite3"
COMPOSITE_STATE_FILE_NAME = "composite_state.sqlite3"

_CHAIN_GENESIS = ""

_OPTIONAL_FILES: frozenset[str] = frozenset(
    {"composite_state", "marketfeed", "venue_ledger"}
)

MANIFEST_SUFFIX = ".set.manifest.json"

_MANIFEST_SUFFIX = MANIFEST_SUFFIX

_GEN_PREFIX = "gen"

_LIVE_ENVIRONMENT_LABELS = frozenset({"paper", "restricted-live", "production"})

_RESTORE_DRILL_VERDICT_KIND = "RESTORE_DRILL_VERDICT"

_DEFINITE_FAILURE_MARKERS = frozenset(
    {"replay_verdict_diverged", "total_compared_mismatch", "readiness_verdict_mismatch"}
)
_UNKNOWN_MARKERS = frozenset(
    {"event_consumed_count_unknown", "readiness_verdict_unknown"}
)


class BackupSetRefused(RuntimeError):
    """Raised by :func:`backup_set` — a non-increasing ``generation``, or a source file absent."""


class RestoreRefused(RuntimeError):
    """Raised by :func:`restore_set` / :func:`restore_drill` — an unsafe destination, a digest"""


class DurableSetPaths(BaseModel):
    """The six files one durable set is made of (``marketfeed`` joined in the tick-source"""

    model_config = ConfigDict(frozen=True)

    evidence: Path
    rcl: Path
    inbox: Path
    composite_state: Path
    marketfeed: Path
    venue_ledger: Path

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> DurableSetPaths:
        """The paths a real :func:`~tos_runtime.compose.root.compose_paper_runtime` boot over"""
        return cls(
            evidence=data_dir / EVIDENCE_FILE_NAME,
            rcl=data_dir / RCL_FILE_NAME,
            inbox=data_dir / INBOX_FILE_NAME,
            composite_state=data_dir / COMPOSITE_STATE_FILE_NAME,
            marketfeed=data_dir / MARKETFEED_FILE_NAME,
            venue_ledger=data_dir / VENUE_LEDGER_FILE_NAME,
        )


class FileBackupEntry(BaseModel):
    """One file's own backup-copy record inside a :class:`BackupSetManifest`."""

    model_config = ConfigDict(frozen=True)

    path: str
    file_digest: str
    last_seq: int | None


class EvidenceBackupFacts(BaseModel):
    model_config = ConfigDict(frozen=True)

    last_seq: int | None
    chain_digest: str
    key_generation: int | None
    event_consumed_count: int


class RclBackupFacts(BaseModel):
    model_config = ConfigDict(frozen=True)

    last_seq: int | None
    writer_epoch: int | None


class InboxBackupFacts(BaseModel):
    model_config = ConfigDict(frozen=True)

    last_seq: int | None
    unconsumed_count: int


class BackupSetManifest(BaseModel):
    """The durable-set snapshot manifest :func:`backup_set` writes (plan §2.1)."""

    model_config = ConfigDict(frozen=True)

    generation: int
    created_at_monotonic_ns: int
    files: dict[str, FileBackupEntry | None]
    source_paths: dict[str, str]
    evidence: EvidenceBackupFacts
    rcl: RclBackupFacts
    inbox: InboxBackupFacts
    runtime_identity: str | None = None
    readiness_verdict_at_backup: str | None = None


def _backup_one_file(source_path: Path, dest_path: Path) -> None:
    """Byte-consistent online snapshot via ``Connection.backup`` — never a raw file copy (mirrors"""
    source_conn = sqlite3.connect(str(source_path))
    try:
        dest_conn = sqlite3.connect(str(dest_path))
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        source_conn.close()


def _read_optional_int(conn: sqlite3.Connection, query: str) -> int | None:
    try:
        row = conn.execute(query).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None or row[0] is None:
        return None
    return int(row[0])


_SEQ_TABLE_BY_NAME: dict[str, str] = {
    "evidence": "entries",
    "rcl": "entries",
    "inbox": "events",
}


def _last_seq_for(name: str, backup_path: Path) -> int | None:
    """The newest ``seq`` a store's own backup file carries, or ``None`` when the store has no"""
    if name in _OPTIONAL_FILES:
        return None
    table = _SEQ_TABLE_BY_NAME.get(name)
    if table is None:
        raise RuntimeError(
            f"_last_seq_for: no seq-table mapping registered for store {name!r} — every "
            "DurableSetPaths member must be handled either via _SEQ_TABLE_BY_NAME or "
            "_OPTIONAL_FILES (this function's own docstring)"
        )
    conn = sqlite3.connect(str(backup_path))
    try:
        return _read_optional_int(conn, f"SELECT MAX(seq) FROM {table}")
    finally:
        conn.close()


def _read_evidence_facts(evidence_backup_path: Path) -> EvidenceBackupFacts:
    conn = sqlite3.connect(str(evidence_backup_path))
    try:
        row = conn.execute(
            "SELECT seq, chain_digest, key_generation FROM entries ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if row is None:
            last_seq, chain_digest, key_generation = None, _CHAIN_GENESIS, None
        else:
            last_seq, chain_digest, key_generation = row
        (event_consumed_count,) = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'EVENT_CONSUMED'"
        ).fetchone()
    finally:
        conn.close()
    return EvidenceBackupFacts(
        last_seq=last_seq,
        chain_digest=chain_digest,
        key_generation=key_generation,
        event_consumed_count=int(event_consumed_count),
    )


def _read_rcl_facts(rcl_backup_path: Path) -> RclBackupFacts:
    conn = sqlite3.connect(str(rcl_backup_path))
    try:
        last_seq = _read_optional_int(conn, "SELECT MAX(seq) FROM entries")
        writer_epoch = _read_optional_int(conn, "SELECT MAX(epoch) FROM epochs")
    finally:
        conn.close()
    return RclBackupFacts(last_seq=last_seq, writer_epoch=writer_epoch)


def _read_inbox_facts(inbox_backup_path: Path) -> InboxBackupFacts:
    conn = sqlite3.connect(str(inbox_backup_path))
    try:
        last_seq = _read_optional_int(conn, "SELECT MAX(seq) FROM events")
        (unconsumed_count,) = conn.execute(
            "SELECT COUNT(*) FROM events WHERE consumed_evidence_seq IS NULL"
        ).fetchone()
    finally:
        conn.close()
    return InboxBackupFacts(last_seq=last_seq, unconsumed_count=int(unconsumed_count))


def generation_number(name: str, suffix: str) -> int | None:
    """``N`` from a ``gen{N}{suffix}`` filename, or ``None`` if ``name`` is not one."""
    if not name.startswith(_GEN_PREFIX) or not name.endswith(suffix):
        return None
    middle = (
        name[len(_GEN_PREFIX) : len(name) - len(suffix)]
        if suffix
        else name[len(_GEN_PREFIX) :]
    )
    return int(middle) if middle.isdigit() else None


def _highest_existing_generation(dest_dir: Path) -> int | None:
    if not dest_dir.is_dir():
        return None
    generations = [
        found
        for child in dest_dir.iterdir()
        if child.is_file()
        for found in (generation_number(child.name, _MANIFEST_SUFFIX),)
        if found is not None
    ]
    return max(generations) if generations else None


def _create_generation_dir(dest_dir: Path, generation: int) -> Path:
    """Create ``dest_dir/gen{generation}/``, refusing by name if it is already there."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    gen_dir = dest_dir / f"gen{generation}"
    if gen_dir.exists():
        raise BackupSetRefused(
            f"backup_set: {gen_dir} already exists — refusing to write into, or over, a "
            "generation directory this call did not create. A directory with no "
            f"gen{generation}{_MANIFEST_SUFFIX} beside it is the remains of a run that died "
            "part-way: inspect it, then move it aside (never into dest_dir) or pass a higher "
            "--generation. Nothing in this module deletes it for you"
        )
    gen_dir.mkdir(parents=False, exist_ok=False)
    return gen_dir


def manifest_path_for(dest_dir: Path, generation: int) -> Path:
    """The manifest path :func:`backup_set` writes for ``generation`` under ``dest_dir``."""
    return dest_dir / f"gen{generation}{_MANIFEST_SUFFIX}"


def _highest_attempted_generation(dest_dir: Path) -> int | None:
    """The highest ``gen{N}`` **directory** under ``dest_dir``, or ``None``."""
    if not dest_dir.is_dir():
        return None
    generations = [
        found
        for child in dest_dir.iterdir()
        if child.is_dir()
        for found in (generation_number(child.name, ""),)
        if found is not None
    ]
    return max(generations) if generations else None


def next_generation(dest_dir: Path) -> int:
    """The lowest generation :func:`backup_set` would accept for ``dest_dir``."""
    candidates = [
        found
        for found in (
            _highest_existing_generation(dest_dir),
            _highest_attempted_generation(dest_dir),
        )
        if found is not None
    ]
    return max(candidates) + 1 if candidates else 1


def backup_set(
    paths: DurableSetPaths,
    dest_dir: Path,
    generation: int,
    *,
    runtime_identity: str | None = None,
    readiness_verdict_at_backup: str | None = None,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> BackupSetManifest:
    """Snapshot the durable set into ``dest_dir/gen{generation}/`` + one set manifest."""
    existing = _highest_existing_generation(dest_dir)
    if existing is not None and generation <= existing:
        raise BackupSetRefused(
            f"backup_set: generation={generation} must be strictly greater than the existing "
            f"highest generation {existing} under {dest_dir}"
        )

    file_specs: dict[str, Path] = {
        "evidence": paths.evidence,
        "rcl": paths.rcl,
        "inbox": paths.inbox,
        "composite_state": paths.composite_state,
        "marketfeed": paths.marketfeed,
        "venue_ledger": paths.venue_ledger,
    }
    for name, source_path in file_specs.items():
        if name in _OPTIONAL_FILES:
            continue
        if not source_path.is_file():
            raise BackupSetRefused(
                f"backup_set: source file for {name!r} does not exist at {source_path} — "
                "refusing rather than silently creating an empty backup"
            )

    gen_dir = _create_generation_dir(dest_dir, generation)

    files: dict[str, FileBackupEntry | None] = {}
    for name, source_path in file_specs.items():
        if name in _OPTIONAL_FILES and not source_path.is_file():
            files[name] = None
            continue
        backup_path = gen_dir / f"{name}.sqlite3"
        _backup_one_file(source_path, backup_path)
        file_digest = hashlib.sha256(backup_path.read_bytes()).hexdigest()
        files[name] = FileBackupEntry(
            path=str(backup_path),
            file_digest=file_digest,
            last_seq=_last_seq_for(name, backup_path),
        )

    manifest = BackupSetManifest(
        generation=generation,
        created_at_monotonic_ns=monotonic_ns(),
        files=files,
        source_paths={name: str(path) for name, path in file_specs.items()},
        evidence=_read_evidence_facts(gen_dir / "evidence.sqlite3"),
        rcl=_read_rcl_facts(gen_dir / "rcl.sqlite3"),
        inbox=_read_inbox_facts(gen_dir / "inbox.sqlite3"),
        runtime_identity=runtime_identity,
        readiness_verdict_at_backup=readiness_verdict_at_backup,
    )
    manifest_path = manifest_path_for(dest_dir, generation)
    manifest_path.write_text(manifest.model_dump_json(indent=2))
    return manifest


def _resolves_inside_or_equal(dest_dir: Path, source_dir: Path) -> bool:
    return dest_dir.resolve().is_relative_to(source_dir.resolve())


class RestoredSet(BaseModel):
    """The result of one :func:`restore_set` call — always non-live (ADR-002-016)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    non_live: Literal[True] = True
    paths: DurableSetPaths
    manifest: BackupSetManifest


def _fill_pre_membership_paths(
    restored_file_paths: dict[str, Path], dest_dir: Path
) -> None:
    """Give a manifest written before a member joined the set that member's path anyway."""
    for name, file_name in (
        ("marketfeed", MARKETFEED_FILE_NAME),
        ("venue_ledger", VENUE_LEDGER_FILE_NAME),
    ):
        restored_file_paths.setdefault(name, dest_dir / file_name)


def restore_set(
    manifest_path: Path,
    dest_dir: Path,
    *,
    key_provider: KeyProvider,
) -> RestoredSet:
    """Restore one durable-set backup into a fresh, non-live directory."""
    manifest = BackupSetManifest.model_validate_json(manifest_path.read_text())

    for name, source_path_str in manifest.source_paths.items():
        source_parent = Path(source_path_str).parent
        if _resolves_inside_or_equal(dest_dir, source_parent):
            raise RestoreRefused(
                f"restore_set: destination {dest_dir} resolves equal to or inside the live "
                f"source data directory {source_parent} (for {name!r}) — refused"
            )

    dest_dir.mkdir(parents=True, exist_ok=True)
    restored_file_paths: dict[str, Path] = {}
    for name, entry in manifest.files.items():
        dest_path = dest_dir / f"{name}.sqlite3"
        if entry is None:
            restored_file_paths[name] = dest_path
            continue
        _backup_one_file(Path(entry.path), dest_path)
        actual_digest = hashlib.sha256(dest_path.read_bytes()).hexdigest()
        if actual_digest != entry.file_digest:
            raise RestoreRefused(
                f"restore_set: restored file digest for {name!r} is {actual_digest}, manifest "
                f"records {entry.file_digest} — refused (mutation M1)"
            )
        restored_file_paths[name] = dest_path

    _fill_pre_membership_paths(restored_file_paths, dest_dir)

    restored_paths = DurableSetPaths(
        evidence=restored_file_paths["evidence"],
        rcl=restored_file_paths["rcl"],
        inbox=restored_file_paths["inbox"],
        composite_state=restored_file_paths["composite_state"],
        marketfeed=restored_file_paths["marketfeed"],
        venue_ledger=restored_file_paths["venue_ledger"],
    )

    restored_evidence_store = SqliteEvidenceStore(
        restored_paths.evidence, key_provider=key_provider
    )
    try:
        key_generation, key_bytes = key_provider.current()
        restored_evidence_store.verify_or_raise({key_generation: key_bytes})
    finally:
        restored_evidence_store.close()

    return RestoredSet(paths=restored_paths, manifest=manifest)


class _RecoveryVerdictLike(Protocol):
    """The narrow read surface :class:`_ComposedForDrill` needs off whatever ``recovery``"""

    @property
    def readiness_verdict(self) -> ReadinessVerdict: ...


class _CommittedCommandReader(Protocol):
    """The one RCL read :func:`restore_drill` needs (PR-3b — ``SqliteCommitLog"""

    def committed_command(self, command_id: str) -> tuple[int, str | None] | None: ...


class _ComposedForDrill(Protocol):
    """The exact surface :func:`restore_drill` uses off whatever ``compose`` returns — verified"""

    @property
    def evidence_store(self) -> SqliteEvidenceStore: ...

    @property
    def inbox(self) -> SqliteEventInbox: ...

    @property
    def emergency_log(self) -> EmergencyAppendLog: ...

    @property
    def rcl_log(self) -> _CommittedCommandReader: ...

    @property
    def recovery(self) -> _RecoveryVerdictLike | None: ...


class ComposeForDrill(Protocol):
    """An already-partially-applied recompose callable — everything ``compose_paper_runtime``"""

    def __call__(self, data_dir: Path, environment_label: str) -> _ComposedForDrill: ...


class RestoreDrillVerdict(BaseModel):
    """The result of one :func:`restore_drill` call — also durably appended as a"""

    model_config = ConfigDict(frozen=True)

    result: Literal["PASSED", "FAILED", "UNKNOWN"]
    mismatched_fields: tuple[str, ...] = ()
    manifest_digest: str
    total_compared: int
    expected_event_consumed_count: int | None
    readiness_verdict_at_backup: str | None
    readiness_verdict_at_drill: str | None


def _evaluate_restore_drill(
    runtime: _ComposedForDrill,
    manifest: BackupSetManifest,
    verdict: ReplayVerdict,
) -> tuple[Literal["PASSED", "FAILED", "UNKNOWN"], list[str], str | None]:
    """The mismatch/result computation half of :func:`restore_drill` (split out for the 100-line"""
    mismatched: list[str] = []

    if not verdict.ok:
        mismatched.append("replay_verdict_diverged")

    expected_event_consumed_count = manifest.evidence.event_consumed_count
    if expected_event_consumed_count is None:
        mismatched.append("event_consumed_count_unknown")
    elif verdict.total_compared != expected_event_consumed_count:
        mismatched.append("total_compared_mismatch")

    expected_readiness_str = manifest.readiness_verdict_at_backup
    readiness_at_drill: str | None = None
    if runtime.recovery is not None:
        readiness_at_drill = runtime.recovery.readiness_verdict.value
    if expected_readiness_str is None or runtime.recovery is None:
        mismatched.append("readiness_verdict_unknown")
    else:
        expected_readiness = ReadinessVerdict(expected_readiness_str)
        if runtime.recovery.readiness_verdict is not expected_readiness:
            mismatched.append("readiness_verdict_mismatch")

    if any(marker in _DEFINITE_FAILURE_MARKERS for marker in mismatched):
        result: Literal["PASSED", "FAILED", "UNKNOWN"] = "FAILED"
    elif any(marker in _UNKNOWN_MARKERS for marker in mismatched):
        result = "UNKNOWN"
    else:
        result = "PASSED"

    return result, mismatched, readiness_at_drill


def restore_drill(
    restored: RestoredSet,
    *,
    compose: ComposeForDrill,
    build_core: Callable[[], ReplayableCore],
    scheme: CanonicalizationScheme,
    environment_label: str,
    window_events: int | None = None,
) -> RestoreDrillVerdict:
    """Recompose over ``restored`` and independently verify replay + readiness (decision 2)."""
    if environment_label in _LIVE_ENVIRONMENT_LABELS:
        raise RestoreRefused(
            f"restore_drill: environment_label={environment_label!r} is a live label — drills "
            "only ever run under a non-live label"
        )

    data_dir = restored.paths.evidence.parent
    runtime = compose(data_dir, environment_label)

    manifest_digest = hashlib.sha256(
        restored.manifest.model_dump_json().encode("utf-8")
    ).hexdigest()
    verdict = replay_engine(
        runtime.inbox,
        runtime.evidence_store,
        runtime.emergency_log,
        build_core,
        scheme=scheme,
        window_events=window_events,
        rcl_committed=runtime.rcl_log.committed_command,
    )
    result, mismatched, readiness_at_drill = _evaluate_restore_drill(
        runtime, restored.manifest, verdict
    )

    runtime.evidence_store.append(
        {
            "result": result,
            "mismatched_fields": list(mismatched),
            "manifest_digest": manifest_digest,
        },
        kind=_RESTORE_DRILL_VERDICT_KIND,
        record_class=_RESTORE_DRILL_VERDICT_KIND,
    )

    return RestoreDrillVerdict(
        result=result,
        mismatched_fields=tuple(mismatched),
        manifest_digest=manifest_digest,
        total_compared=verdict.total_compared,
        expected_event_consumed_count=restored.manifest.evidence.event_consumed_count,
        readiness_verdict_at_backup=restored.manifest.readiness_verdict_at_backup,
        readiness_verdict_at_drill=readiness_at_drill,
    )
