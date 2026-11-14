"""``SqliteEventInbox`` — the durable, single-writer event admission queue (TOS Phase 3 Wave 1"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from tos.canonical import CanonicalizationScheme
from tos.engine.records import EngineEvent, event_identity

from tos_runtime.operations.schema_ledger import (
    closing_on_failure,
    enable_wal_journal,
    open_or_create_schema,
)

__all__ = [
    "INBOX_SCHEMA_VERSION",
    "InboxReceipt",
    "NewRiskHaltClearOutcome",
    "SqliteEventInbox",
]

INBOX_SCHEMA_VERSION = 1

_CREATE_EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    account TEXT NOT NULL,
    instrument TEXT NOT NULL,
    reference_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    consumed_evidence_seq INTEGER,
    consumed_generation INTEGER,
    handling_started_evidence_seq INTEGER,
    handling_started_generation INTEGER
)
"""

#: ``PRAGMA table_info`` check (:func:`_ensure_column`) rather than a bare ``ALTER TABLE`` so
_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("handling_started_evidence_seq", "INTEGER"),
    ("handling_started_generation", "INTEGER"),
)

_CREATE_UNCONSUMED_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS events_unconsumed
ON events (seq) WHERE consumed_evidence_seq IS NULL
"""

_CREATE_ATTEMPT_COMPOSITES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS attempt_composites (
    attempt_id TEXT PRIMARY KEY,
    composite_json TEXT NOT NULL,
    observation_revision INTEGER NOT NULL
)
"""

_CREATE_ATTEMPT_FINALITY_WITNESS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS attempt_finality_witness (
    attempt_id TEXT PRIMARY KEY,
    witness INTEGER
)
"""

_CREATE_NEW_RISK_HALT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS new_risk_halt (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    reason TEXT NOT NULL,
    event_id TEXT,
    evidence_seq INTEGER
)
"""


class NewRiskHaltClearOutcome(StrEnum):
    """The typed outcome of a new-risk-halt clear attempt (re-review finding RR3, 2026-09-09)."""

    CLEARED = "CLEARED"
    NO_LATCH = "NO_LATCH"
    EMPTY_ATTESTATION = "EMPTY_ATTESTATION"
    SEQ_MISMATCH = "SEQ_MISMATCH"
    STORAGE_REFUSED = "STORAGE_REFUSED"
    QUORUM_REFUSED = "QUORUM_REFUSED"


@dataclass(frozen=True)
class InboxReceipt:
    """The result of one :meth:`SqliteEventInbox.enqueue` call."""

    seq: int
    event_id: str
    duplicate: bool


def _create_inbox_schema(conn: sqlite3.Connection, fresh: bool) -> None:
    """This inbox's own DDL, run by :func:`~tos_runtime.operations.schema_ledger"""
    del fresh
    conn.execute(_CREATE_EVENTS_TABLE_SQL)
    conn.execute(_CREATE_UNCONSUMED_INDEX_SQL)
    conn.execute(_CREATE_ATTEMPT_COMPOSITES_TABLE_SQL)
    conn.execute(_CREATE_ATTEMPT_FINALITY_WITNESS_TABLE_SQL)
    conn.execute(_CREATE_NEW_RISK_HALT_TABLE_SQL)
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
    for column, decl in _ADDED_COLUMNS:
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE events ADD COLUMN {column} {decl}")


class SqliteEventInbox:
    """The append-and-mark-consumed durable admission queue (design plan §1.1)."""

    def __init__(self, path: Path, *, scheme: CanonicalizationScheme) -> None:
        """Open (or create) the event inbox at ``path``."""
        self.path = path
        self._scheme = scheme
        self._conn = sqlite3.connect(str(path), isolation_level=None)
        with closing_on_failure(self._conn):
            enable_wal_journal(self._conn)
            self._conn.execute("PRAGMA synchronous=FULL")
            open_or_create_schema(
                self._conn,
                store_name="inbox",
                schema_version=INBOX_SCHEMA_VERSION,
                create_ddl=_create_inbox_schema,
                shape_tables=(
                    "events",
                    "attempt_composites",
                    "attempt_finality_witness",
                    "new_risk_halt",
                ),
                monotonic_ns=time.monotonic_ns,
            )

    def close(self) -> None:
        """Close the underlying sqlite3 connection."""
        self._conn.close()

    def _next_seq(self) -> int:
        """Return the next row seq, read fresh from disk every call (no cached counter)."""
        row = self._conn.execute("SELECT MAX(seq) FROM events").fetchone()
        current = row[0]
        return 1 if current is None else current + 1

    @property
    def count(self) -> int:
        """How many events this inbox has ever admitted (consumed or not)."""
        row = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()
        return int(row[0])

    @property
    def unconsumed_count(self) -> int:
        """How many admitted events are NOT yet consumed (the subset :attr:`count` does not"""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM events WHERE consumed_evidence_seq IS NULL"
        ).fetchone()
        return int(row[0])

    def enqueue(self, event: EngineEvent) -> InboxReceipt:
        """Durably admit one event, allocating its ``seq`` internally."""
        event_id = event_identity(event, scheme=self._scheme)
        key = event.instrument_key()
        reference = event.reference()
        dumped = event.model_dump(mode="json")
        payload_json = json.dumps(dumped, sort_keys=True, separators=(",", ":"))
        payload_digest = self._scheme.compute_digest(dumped)
        reference_json = json.dumps(
            reference.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            existing = self._conn.execute(
                "SELECT seq FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if existing is not None:
                self._conn.execute("COMMIT")
                return InboxReceipt(seq=existing[0], event_id=event_id, duplicate=True)
            next_seq = self._next_seq()
            self._conn.execute(
                "INSERT INTO events (seq, event_id, kind, account, instrument, "
                "reference_json, payload_json, payload_digest, consumed_evidence_seq, "
                "consumed_generation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                (
                    next_seq,
                    event_id,
                    event.kind.value,
                    key.account,
                    key.instrument,
                    reference_json,
                    payload_json,
                    payload_digest,
                ),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        return InboxReceipt(seq=next_seq, event_id=event_id, duplicate=False)

    def next_unconsumed(self) -> tuple[int, EngineEvent] | None:
        """Return the oldest not-yet-consumed event, in ``seq`` order."""
        row = self._conn.execute(
            "SELECT seq, payload_json FROM events "
            "WHERE consumed_evidence_seq IS NULL ORDER BY seq ASC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        seq, payload_json = row
        return seq, EngineEvent.model_validate(json.loads(payload_json))

    def mark_consumed(self, seq: int, *, evidence_seq: int, generation: int) -> None:
        """Record that ``seq`` was durably consumed, binding it to its evidence receipt."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "UPDATE events SET consumed_evidence_seq = ?, consumed_generation = ? "
                "WHERE seq = ?",
                (evidence_seq, generation, seq),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def mark_handling_started(
        self, seq: int, *, evidence_seq: int, generation: int
    ) -> None:
        """Record this row's own write-ahead ``EVENT_HANDLING_STARTED`` evidence receipt"""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "UPDATE events SET handling_started_evidence_seq = ?, "
                "handling_started_generation = ? WHERE seq = ?",
                (evidence_seq, generation, seq),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def handling_started_receipt(self, seq: int) -> tuple[int, int] | None:
        """``(evidence_seq, generation)`` of ``seq``'s own ``EVENT_HANDLING_STARTED`` marker, or"""
        row = self._conn.execute(
            "SELECT handling_started_evidence_seq, handling_started_generation "
            "FROM events WHERE seq = ?",
            (seq,),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return row[0], row[1]

    def is_consumed(self, seq: int) -> bool:
        """Whether ``seq`` is already marked consumed."""
        row = self._conn.execute(
            "SELECT consumed_evidence_seq FROM events WHERE seq = ?", (seq,)
        ).fetchone()
        return row is not None and row[0] is not None

    def replay(self) -> Iterator[tuple[int, EngineEvent]]:
        """Yield every admitted event, in ``seq`` order, consumed or not."""
        cur = self._conn.execute(
            "SELECT seq, payload_json FROM events ORDER BY seq ASC"
        )
        for seq, payload_json in cur:
            yield seq, EngineEvent.model_validate(json.loads(payload_json))

    def record_composite(
        self, attempt_id: str, composite: dict, *, observation_revision: int
    ) -> None:
        """Durably REPLACE ``attempt_id``'s last known orthostate composite observation."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "INSERT INTO attempt_composites (attempt_id, composite_json, "
                "observation_revision) VALUES (?, ?, ?) "
                "ON CONFLICT(attempt_id) DO UPDATE SET "
                "composite_json = excluded.composite_json, "
                "observation_revision = excluded.observation_revision",
                (
                    attempt_id,
                    json.dumps(composite, sort_keys=True, separators=(",", ":")),
                    observation_revision,
                ),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def last_composite(self, attempt_id: str) -> tuple[dict, int] | None:
        """``(composite, observation_revision)`` last recorded for ``attempt_id``, or ``None``"""
        row = self._conn.execute(
            "SELECT composite_json, observation_revision FROM attempt_composites "
            "WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        if row is None:
            return None
        composite_json, observation_revision = row
        return json.loads(composite_json), observation_revision

    def record_finality_witness(self, attempt_id: str, witness: bool | None) -> None:
        """Durably REPLACE ``attempt_id``'s last derived ``finality_witness``."""
        stored = None if witness is None else int(witness)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "INSERT INTO attempt_finality_witness (attempt_id, witness) "
                "VALUES (?, ?) "
                "ON CONFLICT(attempt_id) DO UPDATE SET witness = excluded.witness",
                (attempt_id, stored),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def finality_witness(self, attempt_id: str) -> bool | None:
        """The last ``finality_witness`` recorded for ``attempt_id``, or ``None`` if none has"""
        row = self._conn.execute(
            "SELECT witness FROM attempt_finality_witness WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return bool(row[0])

    def record_new_risk_halt(
        self, *, reason: str, event_id: str | None, evidence_seq: int | None
    ) -> None:
        """Durably latch a runtime-wide new-risk halt — a no-op if one is ALREADY latched."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "INSERT OR IGNORE INTO new_risk_halt (id, reason, event_id, evidence_seq) "
                "VALUES (1, ?, ?, ?)",
                (reason, event_id, evidence_seq),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def clear_new_risk_halt(
        self, *, latched_evidence_seq: int, operator_attestation: str
    ) -> NewRiskHaltClearOutcome:
        """Clear the latch — ONLY if it is still the exact violation named (re-review finding R3)."""
        if not operator_attestation.strip():
            return NewRiskHaltClearOutcome.EMPTY_ATTESTATION
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT evidence_seq FROM new_risk_halt WHERE id = 1"
            ).fetchone()
            if row is None:
                self._conn.execute("COMMIT")
                return NewRiskHaltClearOutcome.NO_LATCH
            (current_evidence_seq,) = row
            if current_evidence_seq != latched_evidence_seq:
                self._conn.execute("COMMIT")
                return NewRiskHaltClearOutcome.SEQ_MISMATCH
            self._conn.execute(
                "DELETE FROM new_risk_halt WHERE id = 1 AND evidence_seq = ?",
                (latched_evidence_seq,),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        return NewRiskHaltClearOutcome.CLEARED

    def new_risk_halt(self) -> dict[str, object] | None:
        """The currently-latched new-risk halt, or ``None`` if none has ever been recorded."""
        row = self._conn.execute(
            "SELECT reason, event_id, evidence_seq FROM new_risk_halt WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        reason, event_id, evidence_seq = row
        return {"reason": reason, "event_id": event_id, "evidence_seq": evidence_seq}
