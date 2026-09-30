"""Durable-set backup / restore / restore-drill (TOS Phase 5 W4 plan §2 decisions 1-2; the
marketfeed snapshot store joined the set in the tick-source wave, plan
``docs/plans/2026-09-16-tos-tick-source-plan.md`` §6 ④, operator decision 2026-09-16).

**The durable set is five separate sqlite files, not one.** Design #40 D3.1's own
failure-domain separation means the evidence store, the RCL commit log, the event inbox, the
kernel-owned composite-state store, and the marketfeed snapshot/preimage store each live in their
own file — there is no single connection whose ``Connection.backup`` could snapshot all five
atomically. A "backup" here is therefore: (1) every store CLOSED (documented precondition — see
:func:`backup_set`'s own docstring for why this module cannot mechanically detect a handle open in
another process), (2) one ``sqlite3.Connection.backup`` per file (the same
byte-consistent-online-snapshot idiom :mod:`tos_runtime.evidence.backup` already uses — never a
raw file copy), (3) one JSON :class:`BackupSetManifest` recording every file's digest plus a few
store-specific tail facts, so a LATER divergence between "the files as copied" and "the files as
they were" is detectable even though nothing enforced their mutual consistency at copy time.

**The composite-state store is touched only by path.** ``tos.staterestore.CompositeStateStore``
is kernel-owned; this module never imports it, never opens it as a table, and never reads its
``last_seq`` (recorded as ``None`` in every manifest, always) — it is backed up/restored as an
opaque file, exactly like the other four, because ``sqlite3.Connection.backup`` needs no
knowledge of a database's own schema to snapshot it byte-consistently.

**The marketfeed store joined the backup set to close a restore-path failure mode, not for
symmetry.** The kernel's value ⟺ digest check recomputes a value's digest from the STORED preimage
and compares it against what the snapshot-covered observation attests
(``tos/src/tos/marketfeed/value.py:514-523``); ``tos_runtime.marketfeed.store``'s own module
docstring proves, with a restart test, that losing preimages silently takes every value operand to
``UNKNOWN`` while a perfectly valid-looking snapshot id is still in hand. Leaving
``marketfeed.sqlite3`` out of the backup set did not remove that failure mode, it moved it to the
restore path: a deployment restored from a backup could not re-publish a view for any snapshot
issued before the restore. Like ``composite_state``, this module never imports
:class:`~tos_runtime.marketfeed.store.SqliteSnapshotStore` — it is backed up/restored as an opaque
file, and is optional for the same reason ``composite_state`` is: a runtime that never ticked never
creates it (:data:`_OPTIONAL_FILES`).

**Manifest compatibility is two-directional, and only one direction is executed.** A NEW
:func:`restore_set` reading an OLD manifest (written before ``marketfeed`` joined the set) is a
real, exercised path — that manifest has no ``"marketfeed"`` key in ``files`` at all, and
:func:`restore_set`'s own docstring/code handle it explicitly (proven by
``test_restore_set_handles_a_manifest_written_before_marketfeed_joined_the_set``). The REVERSE
direction — an OLD ``restore_set`` (from a checkout predating this change) reading a NEW manifest —
cannot be exercised by this suite, since that would require running old code; the following is a
STATIC TRACE, not a test result. Old code's own restore loop iterates ``manifest.files.items()``
generically, so it would harmlessly restore ``marketfeed.sqlite3`` to disk — but its own
``DurableSetPaths(...)`` construction is hardcoded to four fields (this module's shape before this
change) and would silently drop the restored path from the object it returns. No crash, no
refusal: a rollback to pre-wave code operating on a post-wave backup restores the marketfeed file
but loses its path from the returned set without any error.

**Restore is always non-live** (mirrors :func:`tos_runtime.evidence.backup.restore`'s own
ADR-002-016 discipline) and refuses a destination that resolves inside, or equal to, the live
source data directory the manifest itself recorded — a restore can never silently land back on
top of (or nested inside) the still-live runtime it was taken from.

**``restore_drill`` never imports :mod:`tos_runtime.compose`.** That package will (lane e4) import
THIS one (``compose/_operations_wiring.py``); the reverse edge would be a cycle. Instead,
``restore_drill`` accepts an already-partially-applied ``compose`` callable and only ever touches
the structural surface :class:`_ComposedForDrill` names — verified directly against
``tos_runtime.compose._types.ComposedRuntime``'s own real shape (that class already carries every
attribute this Protocol names), never against the concrete class itself.

Firewall: stdlib (``hashlib``, ``json``, ``sqlite3``, ``time``) + ``pydantic`` + ``tos.canonical``
+ ``tos.sbr.vocabulary`` + ``tos_runtime.evidence`` + ``tos_runtime.engine`` +
``tos_runtime.marketfeed.store`` (``MARKETFEED_FILE_NAME`` only — a name, not the store class)
only (R1 allowlist). No ``tos_runtime.compose``, no ``tos_runtime.custody``, no
``tos.staterestore``.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict
from tos.canonical import CanonicalizationScheme
from tos.sbr.vocabulary import ReadinessVerdict

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay import ReplayableCore, ReplayVerdict, replay_engine
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME

__all__ = [
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
    "restore_drill",
    "restore_set",
]

#: Filenames :mod:`tos_runtime.compose._wiring` / ``_engine_wiring`` /
#: ``tos_runtime.recovery.composite_state_writer`` already fix for a data_dir (duplicated here,
#: not imported, to keep this package's own firewall scope out of ``tos_runtime.compose`` and
#: ``tos_runtime.recovery`` — a restored set's directory happens to be a valid ``data_dir`` for a
#: recompose precisely BECAUSE these match). ``MARKETFEED_FILE_NAME`` is the one exception: it is
#: imported, not duplicated, because :mod:`tos_runtime.marketfeed.store` already owns that
#: constant as its own public name.
EVIDENCE_FILE_NAME = "evidence.sqlite3"
RCL_FILE_NAME = "rcl.sqlite3"
INBOX_FILE_NAME = "inbox.sqlite3"
COMPOSITE_STATE_FILE_NAME = "composite_state.sqlite3"

#: Matches :mod:`tos_runtime.evidence.store`'s own private genesis constant — the chain digest of
#: an empty evidence store.
_CHAIN_GENESIS = ""

#: Backup-set members that MAY be absent from a live directory because the store that owns them
#: opens its file lazily, on first write, rather than preemptively at boot — a runtime that never
#: reached that first write never creates the file. ``backup_set`` records absence honestly as
#: ``None`` rather than fabricating an empty backup, and ``_last_seq_for`` never queries either
#: (``composite_state`` is kernel-owned/opaque; ``marketfeed`` has no ``seq`` column at all — see
#: that function's own docstring). Every site that special-cased ``"composite_state"`` on its own
#: reads this set instead, so a future optional member is added in ONE place, not N.
_OPTIONAL_FILES: frozenset[str] = frozenset({"composite_state", "marketfeed"})

_MANIFEST_SUFFIX = ".set.manifest.json"

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
    """Raised by :func:`restore_set` / :func:`restore_drill` — an unsafe destination, a digest
    mismatch (mutation M1), or a live ``environment_label``."""


class DurableSetPaths(BaseModel):
    """The five files one durable set is made of (``marketfeed`` joined the set in the
    tick-source wave — module docstring)."""

    model_config = ConfigDict(frozen=True)

    evidence: Path
    rcl: Path
    inbox: Path
    composite_state: Path
    marketfeed: Path

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> DurableSetPaths:
        """The paths a real :func:`~tos_runtime.compose.root.compose_paper_runtime` boot over
        ``data_dir`` already uses — the convenience constructor an operator CLI calls.
        """
        return cls(
            evidence=data_dir / EVIDENCE_FILE_NAME,
            rcl=data_dir / RCL_FILE_NAME,
            inbox=data_dir / INBOX_FILE_NAME,
            composite_state=data_dir / COMPOSITE_STATE_FILE_NAME,
            marketfeed=data_dir / MARKETFEED_FILE_NAME,
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
    #: A key in :data:`_OPTIONAL_FILES` (``composite_state``, ``marketfeed``) is ``None`` when
    #: that file did not exist at backup time — ``composite_state`` because a runtime that never
    #: processed an ``EGRESS_RESULT`` all the way to a composite write never creates it
    #: (:mod:`tos_runtime.recovery.composite_state_writer`'s own module docstring), ``marketfeed``
    #: because a runtime that never ticked never issues a snapshot. Absence is never fabricated
    #: into a fake empty backup — it is recorded honestly as ``None``. The other three keys
    #: (``evidence``/``rcl``/``inbox``) are always present (a constructed store always creates its
    #: own file).
    files: dict[str, FileBackupEntry | None]
    #: The LIVE source paths at backup time (never the backup-copy paths) — :func:`restore_set`
    #: refuses a destination that resolves equal to, or inside, any of these directories. Always
    #: has all five keys, even when an optional member was absent (its recorded path is where it
    #: WOULD have lived).
    source_paths: dict[str, str]
    evidence: EvidenceBackupFacts
    rcl: RclBackupFacts
    inbox: InboxBackupFacts
    #: Caller-supplied — never derived (five closed sqlite files carry no runtime identity of
    #: their own). ``None`` when the caller has none to attest.
    runtime_identity: str | None = None
    #: Caller-supplied (e.g. the live runtime's own ``recovery.readiness_verdict.value``
    #: immediately before shutdown) — ``None`` when unavailable. :func:`restore_drill` compares
    #: the restored runtime's OWN readiness verdict against this by enum IDENTITY, never string
    #: equality, never truthiness.
    readiness_verdict_at_backup: str | None = None


def _backup_one_file(source_path: Path, dest_path: Path) -> None:
    """Byte-consistent online snapshot via ``Connection.backup`` — never a raw file copy (mirrors
    :func:`tos_runtime.evidence.backup.backup`'s own idiom)."""
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


#: Table holding a ``seq`` column, per store name — the only stores :func:`_last_seq_for`
#: actually queries. A name absent from BOTH this mapping and :data:`_OPTIONAL_FILES` is a bug,
#: not a silent ``None``: see :func:`_last_seq_for`'s own docstring.
_SEQ_TABLE_BY_NAME: dict[str, str] = {
    "evidence": "entries",
    "rcl": "entries",
    "inbox": "events",
}


def _last_seq_for(name: str, backup_path: Path) -> int | None:
    """The newest ``seq`` a store's own backup file carries, or ``None`` when the store has no
    such column (``_OPTIONAL_FILES``: ``composite_state`` is kernel-owned/opaque, ``marketfeed``
    is content-addressed with no ``seq`` column at all).

    Every :class:`DurableSetPaths` member must resolve here one way or the other — via
    :data:`_SEQ_TABLE_BY_NAME` or via :data:`_OPTIONAL_FILES` — never fall through. This is the
    fourth instance, in this one wave, of a registry paired with a hand-maintained satellite that
    nothing pinned together: the first was ``STORE_MIGRATIONS`` vs ``cli.py``'s hardcoded path
    dict (fixed by extracting ``compose/_migrate_paths.py``), the second/third were
    ``MARKETFEED_SCHEMA_VERSION`` vs ``MARKETFEED_MIGRATIONS[-1].version``. An unrecognized name
    fails LOUDLY and BY NAME here — never a bare ``KeyError`` from inside a dict literal — so the
    next new member cannot silently fall through either branch.

    Raises:
        RuntimeError: ``name`` is in neither :data:`_SEQ_TABLE_BY_NAME` nor
            :data:`_OPTIONAL_FILES`.
    """
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


def _highest_existing_generation(dest_dir: Path) -> int | None:
    if not dest_dir.is_dir():
        return None
    generations: list[int] = []
    for child in dest_dir.iterdir():
        if not child.is_file():
            continue
        name = child.name
        if name.startswith("gen") and name.endswith(_MANIFEST_SUFFIX):
            middle = name[len("gen") : -len(_MANIFEST_SUFFIX)]
            if middle.isdigit():
                generations.append(int(middle))
    return max(generations) if generations else None


def backup_set(
    paths: DurableSetPaths,
    dest_dir: Path,
    generation: int,
    *,
    runtime_identity: str | None = None,
    readiness_verdict_at_backup: str | None = None,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> BackupSetManifest:
    """Snapshot the durable set into ``dest_dir/gen{generation}/`` + one set manifest.

    **Precondition (documented, not mechanically enforced across processes): every store in
    ``paths`` is closed.** This function opens its OWN, independent read connections — it cannot
    detect a handle held open by a DIFFERENT process; the caller (an operator CLI, run against a
    stopped or not-yet-started runtime) is responsible for that.

    Args:
        paths: The five source files. ``evidence``/``rcl``/``inbox`` must already exist (refused
            otherwise — never silently backs up an absent store as a fresh empty file, which
            ``sqlite3.connect`` would do by default). ``composite_state`` and ``marketfeed`` MAY
            be absent (:data:`_OPTIONAL_FILES` — a runtime that never wrote a composite, or never
            ticked, never creates that file) — recorded honestly as ``None`` in the manifest
            rather than fabricated.
        dest_dir: Where ``gen{generation}/`` and the manifest are written. Never deleted, never
            overwritten.
        generation: Must be strictly greater than the highest existing ``gen*`` manifest already
            under ``dest_dir`` — never allocated by this function (decision 1: "세대는 호출자
            지정").
        runtime_identity: Caller-supplied; ``None`` when unavailable.
        readiness_verdict_at_backup: Caller-supplied (e.g. the live runtime's own
            ``recovery.readiness_verdict.value``); ``None`` when unavailable.
        monotonic_ns: Injected monotonic-clock callable for ``created_at_monotonic_ns``.

    Returns:
        The :class:`BackupSetManifest` just written.

    Raises:
        BackupSetRefused: A non-increasing ``generation``, or ``evidence``/``rcl``/``inbox`` does
            not exist.
    """
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
    }
    for name, source_path in file_specs.items():
        if name in _OPTIONAL_FILES:
            continue  # optional — see this function's own docstring / _OPTIONAL_FILES
        if not source_path.is_file():
            raise BackupSetRefused(
                f"backup_set: source file for {name!r} does not exist at {source_path} — "
                "refusing rather than silently creating an empty backup"
            )

    dest_dir.mkdir(parents=True, exist_ok=True)
    gen_dir = dest_dir / f"gen{generation}"
    gen_dir.mkdir(parents=False, exist_ok=False)

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
    manifest_path = dest_dir / f"gen{generation}{_MANIFEST_SUFFIX}"
    manifest_path.write_text(manifest.model_dump_json(indent=2))
    return manifest


def _resolves_inside_or_equal(dest_dir: Path, source_dir: Path) -> bool:
    dest_resolved = dest_dir.resolve()
    source_resolved = source_dir.resolve()
    return dest_resolved == source_resolved or source_resolved in dest_resolved.parents


class RestoredSet(BaseModel):
    """The result of one :func:`restore_set` call — always non-live (ADR-002-016)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    non_live: Literal[True] = True
    paths: DurableSetPaths
    manifest: BackupSetManifest


def restore_set(
    manifest_path: Path,
    dest_dir: Path,
    *,
    key_provider: KeyProvider,
) -> RestoredSet:
    """Restore one durable-set backup into a fresh, non-live directory.

    Verifies EVERY restored file's digest against the manifest (mismatch refuses — mutation M1)
    and, for the evidence store specifically, re-verifies its HMAC chain via
    :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.verify_or_raise` — the same check
    :mod:`tos_runtime.evidence.backup`'s own ``restore()`` performs.

    **Backward compatibility with a pre-marketfeed manifest.** A manifest written before
    ``marketfeed`` joined the backup set (plan §6 ④) has no ``"marketfeed"`` key in ``files`` at
    all — not even a ``None`` entry. That legitimately means "this manifest predates this store",
    the same fact ``composite_state=None`` records for a runtime that never wrote one; the
    restored set is given a ``marketfeed`` path with no file behind it rather than a
    fabricated one or a raised ``KeyError``. This is the NEW-code/OLD-manifest direction, and it is
    exercised by a real test; the reverse direction (an OLD ``restore_set`` reading a NEW manifest)
    is only a static trace — see this module's own docstring, "Manifest compatibility is
    two-directional" paragraph.

    Args:
        manifest_path: The ``*.set.manifest.json`` :func:`backup_set` wrote.
        dest_dir: Where the restored files are copied. Refused if it resolves equal to, or
            inside, ANY of the manifest's own recorded LIVE source directories.
        key_provider: The evidence store's key source for the post-restore chain
            re-verification.

    Returns:
        The :class:`RestoredSet` — always ``non_live=True``.

    Raises:
        RestoreRefused: An unsafe destination, or a restored file's digest disagrees with the
            manifest.
        tos_runtime.evidence.store.EvidenceCorruption: The restored evidence chain fails
            re-verification.
    """
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
            # composite_state/marketfeed was absent at backup time (module docstring) — the
            # restored directory simply has no such file either; a recompose creates it lazily
            # on first write, exactly like a runtime that never wrote one.
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

    # Backward compatibility with a manifest written BEFORE marketfeed joined the backup set
    # (plan §6 ④): such a manifest's own `files` has no "marketfeed" key at all — not even a
    # `None` entry — because the key did not exist yet. That is a real, different fact from "this
    # store existed and was empty at backup time": the old manifest legitimately PREDATES this
    # store, so the restored set simply has no such file, exactly like the composite_state-absent
    # case above (``BackupSetManifest.files``'s own docstring). Never fabricate a file for it, and
    # never raise a bare KeyError that hides which shape of manifest this is.
    if "marketfeed" not in restored_file_paths:
        restored_file_paths["marketfeed"] = dest_dir / MARKETFEED_FILE_NAME

    restored_paths = DurableSetPaths(
        evidence=restored_file_paths["evidence"],
        rcl=restored_file_paths["rcl"],
        inbox=restored_file_paths["inbox"],
        composite_state=restored_file_paths["composite_state"],
        marketfeed=restored_file_paths["marketfeed"],
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
    """The narrow read surface :class:`_ComposedForDrill` needs off whatever ``recovery``
    a real compose result carries — only :attr:`readiness_verdict`, never any other member.

    Declared as a read-only property (not a plain attribute) so frozen
    implementations (dataclass ``frozen=True`` / pydantic frozen models) — including the
    real :class:`~tos_runtime.recovery.barrier.RecoveryVerdict`, which is
    ``@dataclass(frozen=True)`` — satisfy this Protocol structurally
    (docs/plans/2026-09-23-tos-protocol-readonly-members-sweep-plan.md).
    """

    @property
    def readiness_verdict(self) -> ReadinessVerdict: ...


class _ComposedForDrill(Protocol):
    """The exact surface :func:`restore_drill` uses off whatever ``compose`` returns — verified
    directly against ``tos_runtime.compose._types.ComposedRuntime``'s own real attributes, never
    imported from it (see this module's own docstring on why).

    Declared as read-only properties (not plain attributes) so frozen
    implementations (dataclass ``frozen=True`` / pydantic frozen models) satisfy this
    Protocol structurally, not just today's mutable ``ComposedRuntime``
    (docs/plans/2026-09-23-tos-protocol-readonly-members-sweep-plan.md).
    """

    @property
    def evidence_store(self) -> SqliteEvidenceStore: ...

    @property
    def inbox(self) -> SqliteEventInbox: ...

    @property
    def emergency_log(self) -> EmergencyAppendLog: ...

    @property
    def recovery(self) -> _RecoveryVerdictLike | None: ...


class ComposeForDrill(Protocol):
    """An already-partially-applied recompose callable — everything ``compose_paper_runtime``
    needs besides ``data_dir``/``environment_label`` is the CALLER's own closure."""

    def __call__(self, data_dir: Path, environment_label: str) -> _ComposedForDrill: ...


class RestoreDrillVerdict(BaseModel):
    """The result of one :func:`restore_drill` call — also durably appended as a
    ``RESTORE_DRILL_VERDICT`` evidence record into the restored (non-live) store."""

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
    """The mismatch/result computation half of :func:`restore_drill` (split out for the 100-line
    function size budget — no behavior change: still exactly the same three checks, in the same
    order, over the same inputs)."""
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
    """Recompose over ``restored`` and independently verify replay + readiness (decision 2).

    Three checks, each individually "unavailable ⇒ UNKNOWN, never a false PASSED":

    (a) :func:`~tos_runtime.engine.replay.replay_engine` reports ``ok=True`` AND
        ``total_compared`` equals the manifest's own recorded ``EVENT_CONSUMED`` count.
    (b) The recomposed runtime's ``recovery.readiness_verdict`` is the SAME
        :class:`~tos.sbr.vocabulary.ReadinessVerdict` member (identity comparison, never string
        equality, never truthiness) as ``restored.manifest.readiness_verdict_at_backup``.
    (c) A ``RESTORE_DRILL_VERDICT`` evidence record — result, mismatched fields, the manifest's
        own digest — is durably appended into the restored (non-live) evidence store.

    A definite mismatch in (a)/(b) reports ``"FAILED"`` even if some OTHER input was also
    unavailable (a confirmed failure is never masked by an unrelated unknown); ``"UNKNOWN"`` is
    reported only when nothing was definitely wrong but at least one input could not be checked
    at all.

    Args:
        restored: The :class:`RestoredSet` from :func:`restore_set`.
        compose: Recomposes a runtime over ``restored``'s own directory (all five restored files
            share one directory — see :func:`restore_set`) under ``environment_label``.
        build_core: A fresh-core factory for :func:`~tos_runtime.engine.replay.replay_engine`.
        scheme: The canonicalization scheme the replay digest comparison uses.
        environment_label: MUST NOT be a live label (:data:`_LIVE_ENVIRONMENT_LABELS`) — refused
            otherwise.
        window_events: Forwarded to :func:`~tos_runtime.engine.replay.replay_engine`.

    Returns:
        The :class:`RestoreDrillVerdict`.

    Raises:
        RestoreRefused: ``environment_label`` is a live label.
    """
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
