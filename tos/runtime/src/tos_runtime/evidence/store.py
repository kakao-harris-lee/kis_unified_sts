"""The durable, append-only, chained Evidence Store (design #40 D3, §2 item 1)."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.evidence import (
    ChainedEntry,
    EvidenceAppendReceipt,
    Sha256HmacChainScheme,
    scrub_secret_fields,
    verify_chain,
)
from tos.workload import RuntimeIdentity

from tos_runtime.evidence import outbox as _outbox
from tos_runtime.evidence.thread_connections import ThreadConnections
from tos_runtime.operations.key_rotation import (
    KeyContinuityCheck,
    KeyContinuityRefused,
    KeyContinuityVerdict,
    verify_key_generation_continuity,
)
from tos_runtime.operations.schema_ledger import (
    closing_on_failure,
    enable_wal_journal,
    open_or_create_schema,
)

__all__ = [
    "ChainVerification",
    "EVIDENCE_SCHEMA_VERSION",
    "EvidenceCorruption",
    "InjectedCrash",
    "KeyContinuityCheck",
    "KeyContinuityRefused",
    "KeyProvider",
    "SqliteEvidenceStore",
]

#: TOS Phase 5 W4 plan §2 decision 3 — this store's own ``PRAGMA user_version`` /
EVIDENCE_SCHEMA_VERSION = 2

_CHAIN_GENESIS = ""

_CANONICALIZATION_VERSION = EV_L1_PROVISIONAL_VERSION

_CREATE_ENTRIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    seq INTEGER PRIMARY KEY,
    segment_id TEXT,
    kind TEXT NOT NULL,
    record_class TEXT NOT NULL,
    runtime_identity_json TEXT,
    payload_json TEXT NOT NULL,
    entry_digest TEXT NOT NULL,
    chain_digest TEXT NOT NULL,
    key_generation INTEGER NOT NULL,
    appended_at_monotonic_ns INTEGER NOT NULL
)
"""

_CREATE_KIND_SEQ_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS entries_kind_seq ON entries (kind, seq)
"""

_CREATE_NO_UPDATE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS entries_no_update
BEFORE UPDATE ON entries
BEGIN
    SELECT RAISE(ABORT, 'tos_runtime evidence store: entries is append-only — UPDATE forbidden');
END
"""

_CREATE_NO_DELETE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS entries_no_delete
BEFORE DELETE ON entries
BEGIN
    SELECT RAISE(ABORT, 'tos_runtime evidence store: entries is append-only — DELETE forbidden');
END
"""


class EvidenceCorruption(RuntimeError):
    """Raised by :meth:`SqliteEvidenceStore.verify_or_raise` on chain mismatch (contract ⑤)."""


class InjectedCrash(RuntimeError):
    """Raised by a test-supplied ``crash_hook`` to simulate a process death (contract ④)."""


class ChainVerification(BaseModel):
    """The detailed result of :meth:`SqliteEvidenceStore.verify_detailed` (contract ⑤)."""

    model_config = ConfigDict(frozen=True)

    ok: bool
    verified_links: int
    last_seq: int | None


@runtime_checkable
class KeyProvider(Protocol):
    """The injected source of the store's initial signing key (design #40 D4)."""

    def current(self) -> tuple[int, bytes]:
        """Return ``(key_generation, key_bytes)`` for the initial signing key."""
        ...

    def generations(self) -> tuple[int, ...]:
        """Return every key generation this provider can currently supply, sorted ascending."""
        ...

    def key_for(self, generation: int) -> bytes:
        """Return the key bytes for a SPECIFIC ``generation`` — added alongside"""
        ...


class _EntryRow(NamedTuple):
    """One raw ``entries`` row, meta fields only (no payload) — retention's read shape."""

    seq: int
    segment_id: str | None
    kind: str
    record_class: str
    key_generation: int
    appended_at_monotonic_ns: int
    entry_digest: str
    chain_digest: str


class _Entry(NamedTuple):
    """One raw ``entries`` row, meta fields PLUS the payload — :meth:`SqliteEvidenceStore"""

    meta: _EntryRow
    payload_json: str


#: ``PRAGMA table_info`` so the failure is a red test, not a runtime surprise.
_ENTRY_META_COLUMNS_SQL = ", ".join(_EntryRow._fields)

_ENTRY_COLUMNS_SQL = f"{_ENTRY_META_COLUMNS_SQL}, payload_json"


def _tip_key_generation(conn: sqlite3.Connection) -> int | None:
    """The ``key_generation`` of the most recently committed ``entries`` row, or ``None`` for"""
    row = conn.execute(
        "SELECT key_generation FROM entries ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    return None if row is None else int(row[0])


def _tip_has_rotation_commit_for(conn: sqlite3.Connection, generation: int) -> bool:
    """Whether a ``KEY_ROTATION`` entry recording ``new_key_generation == generation`` exists."""
    cur = conn.execute(
        "SELECT payload_json FROM entries WHERE kind = ?", ("KEY_ROTATION",)
    )
    for (payload_json,) in cur:
        payload = json.loads(payload_json)
        if payload.get("payload", {}).get("new_key_generation") == generation:
            return True
    return False


def _rotation_permitted(
    continuity: KeyContinuityCheck,
    provider_generations: tuple[int, ...],
    permit_rotation_pending_for_generation: int | None,
    conn: sqlite3.Connection,
) -> bool:
    """Whether the constructor's ``permit_rotation_pending_for_generation`` override"""
    if continuity.verdict != KeyContinuityVerdict.ROTATION_PENDING:
        return False
    if permit_rotation_pending_for_generation is None:
        return False
    if not provider_generations:
        return False
    if max(provider_generations) != permit_rotation_pending_for_generation:
        return False
    return _tip_key_generation(conn) is not None


def _resolve_signing_key(
    continuity: KeyContinuityCheck, conn: sqlite3.Connection, key_provider: KeyProvider
) -> tuple[int, bytes]:
    """The ``(key_generation, key_bytes)`` pair the constructor signs new entries with."""
    if continuity.verdict == KeyContinuityVerdict.CONTINUOUS:
        return key_provider.current()
    key_generation = _tip_key_generation(conn)
    if key_generation is None:
        raise KeyContinuityRefused(
            "SqliteEvidenceStore: rotation-pending permitted with no tip key generation "
            "— invariant violation, refusing"
        )
    return key_generation, key_provider.key_for(key_generation)


def _create_evidence_schema(conn: sqlite3.Connection, fresh: bool) -> None:
    """This store's own DDL, run by :func:`~tos_runtime.operations.schema_ledger"""
    conn.execute(_CREATE_ENTRIES_TABLE_SQL)
    if fresh:
        conn.execute(_CREATE_KIND_SEQ_INDEX_SQL)
    conn.execute(_CREATE_NO_UPDATE_TRIGGER_SQL)
    conn.execute(_CREATE_NO_DELETE_TRIGGER_SQL)
    _outbox.create_outbox_table(conn)


class SqliteEvidenceStore:
    """The append-only, HMAC-chained, durable evidence log (design #40 D3.1)."""

    def __init__(
        self,
        path: Path,
        *,
        key_provider: KeyProvider,
        secret_keys: frozenset[str] = frozenset(),
        canonicalization_version: str = _CANONICALIZATION_VERSION,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        crash_hook: Callable[[str], None] | None = None,
        permit_rotation_pending_for_generation: int | None = None,
    ) -> None:
        """Open (or create) the evidence store at ``path``."""
        self.path = path
        self._secret_keys = secret_keys
        self._canon_scheme = get_scheme(canonicalization_version)
        self._monotonic_ns = monotonic_ns
        self._crash_hook = crash_hook
        self._conn = sqlite3.connect(str(path), isolation_level=None)
        with closing_on_failure(self._conn):
            enable_wal_journal(self._conn)
            self._conn.execute("PRAGMA synchronous=FULL")
            open_or_create_schema(
                self._conn,
                store_name="evidence",
                schema_version=EVIDENCE_SCHEMA_VERSION,
                create_ddl=_create_evidence_schema,
                shape_tables=("entries", "outbox"),
                monotonic_ns=monotonic_ns,
            )
            provider_generations = key_provider.generations()
            continuity = verify_key_generation_continuity(
                _tip_key_generation(self._conn),
                lambda generation: _tip_has_rotation_commit_for(self._conn, generation),
                provider_generations,
            )
            if (
                continuity.verdict != KeyContinuityVerdict.CONTINUOUS
                and not _rotation_permitted(
                    continuity,
                    provider_generations,
                    permit_rotation_pending_for_generation,
                    self._conn,
                )
            ):
                raise KeyContinuityRefused(
                    f"SqliteEvidenceStore: key generation continuity refused "
                    f"({continuity.verdict}) for {path}: {continuity.reason}"
                )
            self.key_continuity: KeyContinuityCheck = continuity
            key_generation, key = _resolve_signing_key(
                continuity, self._conn, key_provider
            )
            self._scheme = Sha256HmacChainScheme(key=key, key_generation=key_generation)
        self._conns = ThreadConnections(path, lambda: self._conn)

    @property
    def connection(self) -> sqlite3.Connection:
        """The calling thread's sqlite3 connection (:mod:`~tos_runtime.evidence"""
        return self._conns.current()

    @property
    def key_generation(self) -> int:
        """The key generation currently signing new appends."""
        return self._scheme.key_generation

    def close(self) -> None:
        """Close every thread's sqlite3 connection."""
        self._conns.close()

    def _read_tail(self) -> tuple[int, str]:
        """Return ``(next_seq, last_chain_digest)``, read fresh from disk every call."""
        row = (
            self._conns.current()
            .execute("SELECT seq, chain_digest FROM entries ORDER BY seq DESC LIMIT 1")
            .fetchone()
        )
        if row is None:
            return 0, _CHAIN_GENESIS
        last_seq, last_chain_digest = row
        return last_seq + 1, last_chain_digest

    def scrub_payload(
        self, payload: Mapping[str, object]
    ) -> tuple[dict[str, object], tuple[str, ...]]:
        """Scrub ``payload`` with this store's OWN configured ``secret_keys``."""
        return scrub_secret_fields(payload, self._secret_keys)

    def _compute_entry_digest(
        self,
        *,
        kind: str,
        record_class: str,
        segment_id: str | None,
        scrubbed_payload: Mapping[str, object],
        masked_keys: Sequence[str],
        runtime_identity: RuntimeIdentity | None,
    ) -> str:
        """Digest the covered content over canonical bytes (module docstring)."""
        covered: dict[str, object] = {
            "kind": kind,
            "record_class": record_class,
            "segment_id": segment_id,
            "payload": dict(scrubbed_payload),
            "masked_keys": list(masked_keys),
            "runtime_identity": (
                runtime_identity.model_dump(mode="json")
                if runtime_identity is not None
                else None
            ),
        }
        return self._canon_scheme.compute_digest(covered)

    def append(
        self,
        payload: Mapping[str, object],
        *,
        kind: str,
        record_class: str,
        segment_id: str | None = None,
        runtime_identity: RuntimeIdentity | None = None,
        outbox_targets: Sequence[str] = (),
    ) -> EvidenceAppendReceipt:
        """Durably append one scrubbed, digested, chained entry (design #40 D3.1)."""
        return self._append_with_scheme(
            payload,
            kind=kind,
            record_class=record_class,
            segment_id=segment_id,
            runtime_identity=runtime_identity,
            outbox_targets=outbox_targets,
            scheme=self._scheme,
        )

    def _append_with_scheme(
        self,
        payload: Mapping[str, object],
        *,
        kind: str,
        record_class: str,
        segment_id: str | None,
        runtime_identity: RuntimeIdentity | None,
        outbox_targets: Sequence[str],
        scheme: Sha256HmacChainScheme,
    ) -> EvidenceAppendReceipt:
        """The whole durable-append body, signed under an EXPLICIT ``scheme``."""
        scrubbed_payload, masked_keys = scrub_secret_fields(payload, self._secret_keys)
        entry_digest = self._compute_entry_digest(
            kind=kind,
            record_class=record_class,
            segment_id=segment_id,
            scrubbed_payload=scrubbed_payload,
            masked_keys=masked_keys,
            runtime_identity=runtime_identity,
        )
        appended_at_ns = self._monotonic_ns()
        with self._conns.write_lock:
            conn = self._conns.current()
            conn.execute("BEGIN IMMEDIATE")
            try:
                next_seq, last_chain_digest = self._read_tail()
                chain_digest = scheme.verify_append(last_chain_digest, (entry_digest,))
                runtime_identity_json = (
                    json.dumps(runtime_identity.model_dump(mode="json"), sort_keys=True)
                    if runtime_identity is not None
                    else None
                )
                payload_json = json.dumps(
                    {"payload": scrubbed_payload, "masked_keys": list(masked_keys)},
                    sort_keys=True,
                    separators=(",", ":"),
                )
                cur = conn.execute(
                    "INSERT INTO entries (seq, segment_id, kind, record_class, "
                    "runtime_identity_json, payload_json, entry_digest, chain_digest, "
                    "key_generation, appended_at_monotonic_ns) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        next_seq,
                        segment_id,
                        kind,
                        record_class,
                        runtime_identity_json,
                        payload_json,
                        entry_digest,
                        chain_digest,
                        scheme.key_generation,
                        appended_at_ns,
                    ),
                )
                for target in outbox_targets:
                    _outbox.enqueue(cur, entry_seq=next_seq, target=target)
                if self._crash_hook is not None:
                    self._crash_hook("before_commit")
                conn.execute("COMMIT")
            except BaseException as commit_error:
                try:
                    conn.execute("ROLLBACK")
                except Exception as rollback_error:
                    commit_error.add_note(
                        f"ROLLBACK also failed after this error: {rollback_error!r} — "
                        "the original commit-path error above is what propagates; "
                        "this store's on-disk state is not authoritative until "
                        "reopened and independently verified"
                    )
                raise
            if self._crash_hook is not None:
                self._crash_hook("after_commit_before_receipt")
            return EvidenceAppendReceipt(
                segment_id=segment_id,
                seq=next_seq,
                chain_digest=chain_digest,
                key_generation=scheme.key_generation,
            )

    def rotate(self, new_generation: int, new_key: bytes) -> EvidenceAppendReceipt:
        """Rotate the signing key: append a rotation-commit entry under the new key."""
        current_generation = self._scheme.key_generation
        if new_generation <= current_generation:
            raise ValueError(
                "SqliteEvidenceStore.rotate requires a strictly increasing "
                f"key_generation (current={current_generation}, "
                f"new={new_generation}) — design #40 D4.1 겹침 0"
            )
        new_scheme = Sha256HmacChainScheme(key=new_key, key_generation=new_generation)
        receipt = self._append_with_scheme(
            {
                "previous_key_generation": current_generation,
                "new_key_generation": new_generation,
            },
            kind="KEY_ROTATION",
            record_class="SYSTEM_KEY_ROTATION",
            segment_id=None,
            runtime_identity=None,
            outbox_targets=(),
            scheme=new_scheme,
        )
        self._scheme = new_scheme
        return receipt

    def replay(self) -> Iterator[ChainedEntry]:
        """Yield every committed entry, in commit order, for :func:`verify_chain`."""
        cur = self._conns.current().execute(
            "SELECT entry_digest, key_generation, chain_digest FROM entries ORDER BY seq ASC"
        )
        for entry_digest, key_generation, chain_digest in cur:
            yield ChainedEntry(
                entry_digest=entry_digest,
                key_generation=key_generation,
                chain_digest=chain_digest,
            )

    def verify(self, keys_by_generation: Mapping[int, bytes]) -> bool:
        """Re-verify the whole chain (contract ⑤); ``True`` iff every link re-derives."""
        return verify_chain(tuple(self.replay()), keys_by_generation)

    def verify_detailed(
        self, keys_by_generation: Mapping[int, bytes]
    ) -> ChainVerification:
        """Like :meth:`verify`, but reports how many links were actually verified."""
        entries = tuple(self.replay())
        ok = bool(verify_chain(entries, keys_by_generation))
        last_seq, _, _ = self.last_committed()
        return ChainVerification(
            ok=ok, verified_links=len(entries) if ok else 0, last_seq=last_seq
        )

    def verify_or_raise(self, keys_by_generation: Mapping[int, bytes]) -> None:
        """Like :meth:`verify`, but raises :class:`EvidenceCorruption` on mismatch."""
        if not self.verify(keys_by_generation):
            raise EvidenceCorruption(
                "SqliteEvidenceStore.verify_or_raise: chain verification failed "
                f"for {self.path} (contract ⑤ — replay mismatch)"
            )

    def last_committed(self) -> tuple[int | None, str, int | None]:
        """Return ``(last_seq, last_chain_digest, last_key_generation)``."""
        row = (
            self._conns.current()
            .execute(
                "SELECT seq, chain_digest, key_generation FROM entries "
                "ORDER BY seq DESC LIMIT 1"
            )
            .fetchone()
        )
        if row is None:
            return None, _CHAIN_GENESIS, None
        last_seq, last_chain_digest, last_key_generation = row
        return last_seq, last_chain_digest, last_key_generation

    def last_committed_excluding(
        self, kinds: frozenset[str]
    ) -> tuple[int | None, str, int | None]:
        """Same as :meth:`last_committed`, but ignores rows whose ``kind`` is in"""
        if not kinds:
            return self.last_committed()
        placeholders = ", ".join("?" for _ in kinds)
        row = (
            self._conns.current()
            .execute(
                f"SELECT seq, chain_digest, key_generation FROM entries "
                f"WHERE kind NOT IN ({placeholders}) ORDER BY seq DESC LIMIT 1",
                tuple(sorted(kinds)),
            )
            .fetchone()
        )
        if row is None:
            return None, _CHAIN_GENESIS, None
        last_seq, last_chain_digest, last_key_generation = row
        return last_seq, last_chain_digest, last_key_generation

    def iter_entry_meta(self) -> Iterator[_EntryRow]:
        """Yield every entry's meta fields (no payload) — :mod:`tos_runtime.evidence.retention`'s read shape."""
        cur = self._conns.current().execute(
            f"SELECT {_ENTRY_META_COLUMNS_SQL} FROM entries ORDER BY seq ASC"
        )
        for row in cur:
            yield _EntryRow(*row)

    def entry(self, seq: int) -> _Entry | None:
        """The ONE ``entries`` row ``seq`` names — meta fields AND ``payload_json``, read by"""
        row = (
            self._conns.current()
            .execute(
                f"SELECT {_ENTRY_COLUMNS_SQL} FROM entries WHERE seq = ?",
                (seq,),
            )
            .fetchone()
        )
        return None if row is None else _Entry(_EntryRow(*row[:-1]), row[-1])
