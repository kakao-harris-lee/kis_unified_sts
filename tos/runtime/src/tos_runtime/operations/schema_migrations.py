"""Per-store baseline ``SchemaMigration`` definitions + the operator-facing ``apply_migrations``"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tos_runtime.operations.schema_ledger import (
    MIGRATE_APPLIED_BY,
    create_schema_ledger_objects,
    read_schema_version,
)

__all__ = [
    "EVIDENCE_MIGRATIONS",
    "INBOX_MIGRATIONS",
    "MigrationOutcome",
    "MARKETFEED_MIGRATIONS",
    "RCL_MIGRATIONS",
    "STORE_MIGRATIONS",
    "VENUE_LEDGER_MIGRATIONS",
    "SchemaMigration",
    "SchemaMigrationRefused",
    "apply_migrations",
    "schema_version",
]


class SchemaMigrationRefused(RuntimeError):
    """Raised by :func:`apply_migrations` — a pre-existing file's real shape disagrees with the"""


@dataclass(frozen=True)
class MigrationOutcome:
    """What one :func:`apply_migrations` call actually did — the operator-facing report."""

    store_name: str
    from_version: int
    to_version: int
    applied: tuple[int, ...]
    ledgered: tuple[int, ...]
    repaired: tuple[str, ...]

    @property
    def changed(self) -> bool:
        """Whether this call altered the file at all."""
        return bool(self.applied or self.repaired)


@dataclass(frozen=True)
class SchemaMigration:
    """One registered schema migration for one store."""

    version: int
    description: str
    statements: tuple[str, ...]
    expected_tables: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    repair_statements: tuple[str, ...] = ()

    @property
    def statements_digest(self) -> str:
        """sha256 over the canonical join of :attr:`statements` — the ledger's own"""
        canonical = "\n".join(self.statements)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_EVIDENCE_BASELINE_STATEMENTS: tuple[str, ...] = (
    """
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
    """,
    """
    CREATE TRIGGER IF NOT EXISTS entries_no_update
    BEFORE UPDATE ON entries
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime evidence store: entries is append-only — UPDATE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS entries_no_delete
    BEFORE DELETE ON entries
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime evidence store: entries is append-only — DELETE forbidden');
    END
    """,
    """
    CREATE TABLE IF NOT EXISTS outbox (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_seq INTEGER NOT NULL,
        target TEXT NOT NULL,
        delivered_at_monotonic_ns INTEGER
    )
    """,
)

_EVIDENCE_V2_STATEMENTS: tuple[str, ...] = (
    """
    CREATE INDEX IF NOT EXISTS entries_kind_seq ON entries (kind, seq)
    """,
)

EVIDENCE_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration(
        version=1,
        description="baseline — entries (append-only) + outbox",
        statements=_EVIDENCE_BASELINE_STATEMENTS,
        expected_tables={
            "entries": (
                "seq",
                "segment_id",
                "kind",
                "record_class",
                "runtime_identity_json",
                "payload_json",
                "entry_digest",
                "chain_digest",
                "key_generation",
                "appended_at_monotonic_ns",
            ),
            "outbox": (
                "seq",
                "entry_seq",
                "target",
                "delivered_at_monotonic_ns",
            ),
        },
    ),
    SchemaMigration(
        version=2,
        description=(
            "entries gains the entries_kind_seq (kind, seq) covering index — the 14 "
            "boot/recovery readers' WHERE kind = ?/IN (...) ORDER BY seq shape, of the 19 "
            "modules that read this store at all (evidence growth plan §2 A2)"
        ),
        statements=_EVIDENCE_V2_STATEMENTS,
        repair_statements=_EVIDENCE_V2_STATEMENTS,
    ),
)


_RCL_BASELINE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS epochs (
        epoch INTEGER PRIMARY KEY,
        issued_at_monotonic_ns INTEGER NOT NULL,
        runtime_generation INTEGER,
        runtime_identity_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entries (
        seq INTEGER PRIMARY KEY,
        writer_epoch INTEGER NOT NULL,
        command_id TEXT NOT NULL UNIQUE,
        command_digest TEXT,
        kind TEXT,
        payload_digest TEXT,
        payload_json TEXT,
        is_reservation_transition INTEGER NOT NULL DEFAULT 0
            CHECK (is_reservation_transition IN (0, 1))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reservations (
        reservation_id TEXT PRIMARY KEY,
        state TEXT NOT NULL,
        last_seq INTEGER NOT NULL,
        scope_account TEXT NOT NULL,
        scope_instrument TEXT NOT NULL
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS epochs_no_update
    BEFORE UPDATE ON epochs
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: epochs is append-only — UPDATE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS epochs_no_delete
    BEFORE DELETE ON epochs
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: epochs is append-only — DELETE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS entries_no_update
    BEFORE UPDATE ON entries
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: entries is append-only — UPDATE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS entries_no_delete
    BEFORE DELETE ON entries
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: entries is append-only — DELETE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS reservations_no_delete
    BEFORE DELETE ON reservations
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: reservations rows are never deleted');
    END
    """,
)

_RCL_V2_STATEMENTS: tuple[str, ...] = (
    """
    ALTER TABLE reservations ADD COLUMN committed_vector_json TEXT
    """,
)

RCL_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration(
        version=1,
        description="baseline — epochs + entries (append-only) + reservations (UPDATE-only projection)",
        statements=_RCL_BASELINE_STATEMENTS,
        expected_tables={
            "epochs": (
                "epoch",
                "issued_at_monotonic_ns",
                "runtime_generation",
                "runtime_identity_json",
            ),
            "entries": (
                "seq",
                "writer_epoch",
                "command_id",
                "command_digest",
                "kind",
                "payload_digest",
                "payload_json",
                "is_reservation_transition",
            ),
            "reservations": (
                "reservation_id",
                "state",
                "last_seq",
                "scope_account",
                "scope_instrument",
            ),
        },
    ),
    SchemaMigration(
        version=2,
        description=(
            "reservations gains committed_vector_json (kernel round #4 K-4 "
            "CapacityReservationTransition.committed_vector)"
        ),
        statements=_RCL_V2_STATEMENTS,
    ),
)


_INBOX_BASELINE_STATEMENTS: tuple[str, ...] = (
    """
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
    """,
    """
    CREATE INDEX IF NOT EXISTS events_unconsumed
    ON events (seq) WHERE consumed_evidence_seq IS NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS attempt_composites (
        attempt_id TEXT PRIMARY KEY,
        composite_json TEXT NOT NULL,
        observation_revision INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS attempt_finality_witness (
        attempt_id TEXT PRIMARY KEY,
        witness INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS new_risk_halt (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        reason TEXT NOT NULL,
        event_id TEXT,
        evidence_seq INTEGER
    )
    """,
)

INBOX_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration(
        version=1,
        description=(
            "baseline — events (incl. the pre-ledger _ADDED_COLUMNS handling_started_* "
            "columns) + attempt_composites + attempt_finality_witness + new_risk_halt"
        ),
        statements=_INBOX_BASELINE_STATEMENTS,
        expected_tables={
            "events": (
                "seq",
                "event_id",
                "kind",
                "account",
                "instrument",
                "reference_json",
                "payload_json",
                "payload_digest",
                "consumed_evidence_seq",
                "consumed_generation",
                "handling_started_evidence_seq",
                "handling_started_generation",
            ),
            "attempt_composites": (
                "attempt_id",
                "composite_json",
                "observation_revision",
            ),
            "attempt_finality_witness": ("attempt_id", "witness"),
            "new_risk_halt": ("id", "reason", "event_id", "evidence_seq"),
        },
    ),
)


_MARKETFEED_BASELINE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS snapshots (
        snapshot_id TEXT PRIMARY KEY,
        canonical_digest TEXT NOT NULL,
        instrument TEXT NOT NULL,
        as_of_ms INTEGER NOT NULL,
        snapshot_json TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS snapshots_instrument_as_of
    ON snapshots (instrument, as_of_ms)
    """,
    """
    CREATE TABLE IF NOT EXISTS preimages (
        snapshot_id TEXT NOT NULL,
        raw_event_id TEXT NOT NULL,
        preimage_json TEXT NOT NULL,
        PRIMARY KEY (snapshot_id, raw_event_id)
    )
    """,
)

MARKETFEED_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration(
        version=1,
        description=(
            "baseline — snapshots (content-addressed, one row per issued "
            "CriticalInputSnapshot) + preimages (durable, keyed by (snapshot_id, raw_event_id))"
        ),
        statements=_MARKETFEED_BASELINE_STATEMENTS,
        expected_tables={
            "snapshots": (
                "snapshot_id",
                "canonical_digest",
                "instrument",
                "as_of_ms",
                "snapshot_json",
            ),
            "preimages": (
                "snapshot_id",
                "raw_event_id",
                "preimage_json",
            ),
        },
    ),
)


_VENUE_LEDGER_BASELINE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS venue_results (
        written_seq INTEGER PRIMARY KEY AUTOINCREMENT,
        trading_date TEXT NOT NULL,
        broker_execution_id TEXT NOT NULL,
        attempt_id TEXT NOT NULL,
        account TEXT NOT NULL,
        instrument TEXT NOT NULL,
        side TEXT,
        quantity TEXT,
        filled_quantity TEXT,
        remaining_quantity TEXT,
        result_kind TEXT NOT NULL,
        UNIQUE (broker_execution_id)
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS venue_results_no_update
    BEFORE UPDATE ON venue_results
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime venue ledger: venue_results is append-only — UPDATE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS venue_results_no_delete
    BEFORE DELETE ON venue_results
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime venue ledger: venue_results is append-only — DELETE forbidden');
    END
    """,
)

VENUE_LEDGER_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration(
        version=1,
        description=(
            "baseline — venue_results (append-only, one row per result the synthetic venue "
            "produced, UNIQUE on broker_execution_id)"
        ),
        statements=_VENUE_LEDGER_BASELINE_STATEMENTS,
        expected_tables={
            "venue_results": (
                "written_seq",
                "trading_date",
                "broker_execution_id",
                "attempt_id",
                "account",
                "instrument",
                "side",
                "quantity",
                "filled_quantity",
                "remaining_quantity",
                "result_kind",
            ),
        },
    ),
)

STORE_MIGRATIONS: Mapping[str, tuple[SchemaMigration, ...]] = {
    "evidence": EVIDENCE_MIGRATIONS,
    "rcl": RCL_MIGRATIONS,
    "inbox": INBOX_MIGRATIONS,
    "marketfeed": MARKETFEED_MIGRATIONS,
    "venue_ledger": VENUE_LEDGER_MIGRATIONS,
}


def schema_version(path: Path) -> int:
    """Read-only: the ``PRAGMA user_version`` currently stamped on the sqlite file at ``path``."""
    conn = sqlite3.connect(str(path))
    try:
        return read_schema_version(conn)
    finally:
        conn.close()


def _ledger_has_version(conn: sqlite3.Connection, version: int) -> bool:
    """Whether ``schema_ledger`` already carries a row for ``version``."""
    row = conn.execute(
        "SELECT 1 FROM schema_ledger WHERE version = ?", (version,)
    ).fetchone()
    return row is not None


def _repair_at_current_version(
    conn: sqlite3.Connection, head: SchemaMigration
) -> tuple[str, ...]:
    """Re-run ``head``'s :attr:`~SchemaMigration.repair_statements` against an already-current"""
    if not head.repair_statements:
        return ()
    before = _index_names(conn)
    for statement in head.repair_statements:
        conn.execute(statement)
    conn.commit()
    return tuple(sorted(_index_names(conn) - before))


def _index_names(conn: sqlite3.Connection) -> frozenset[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name IS NOT NULL"
    ).fetchall()
    return frozenset(str(row[0]) for row in rows)


def _verify_expected_shape_or_refuse(
    conn: sqlite3.Connection, *, store_name: str, migration: SchemaMigration
) -> None:
    """Refuse if any of ``migration.expected_tables`` ALREADY EXISTS with a different column set."""
    for table_name, expected_columns in migration.expected_tables.items():
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        if not rows:
            continue
        actual_columns = tuple(row[1] for row in rows)
        if actual_columns != tuple(expected_columns):
            raise SchemaMigrationRefused(
                f"{store_name}: pre-existing table {table_name!r} has columns "
                f"{actual_columns!r}, expected {tuple(expected_columns)!r} for migration "
                f"version {migration.version} — refusing to stamp a shape this code does not "
                "recognize (migrate refuses, never silently reshapes)"
            )


def apply_migrations(
    path: Path,
    store_name: str,
    *,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> MigrationOutcome:
    """Bring the CLOSED store file at ``path`` up to ``store_name``'s latest known migration."""
    migrations = STORE_MIGRATIONS.get(store_name)
    if migrations is None:
        raise ValueError(f"apply_migrations: unknown store_name {store_name!r}")

    conn = sqlite3.connect(str(path))
    try:
        # PRAGMA and needs no ledger table, so the AHEAD refusal happens before this function
        current_version = read_schema_version(conn)
        target_version = migrations[-1].version
        if current_version > target_version:
            raise SchemaMigrationRefused(
                f"{store_name}: on-disk user_version={current_version} is already AHEAD of "
                f"the newest known migration ({target_version}) — refusing"
            )
        ledger_repaired = create_schema_ledger_objects(conn)
        from_version = current_version
        applied: list[int] = []
        ledgered: list[int] = []
        for migration in migrations:
            if migration.version <= current_version:
                continue
            if current_version == 0:
                _verify_expected_shape_or_refuse(
                    conn, store_name=store_name, migration=migration
                )
            already_ledgered = _ledger_has_version(conn, migration.version)
            conn.execute("BEGIN IMMEDIATE")
            try:
                for statement in migration.statements:
                    conn.execute(statement)
                if not already_ledgered:
                    conn.execute(
                        "INSERT INTO schema_ledger "
                        "(version, applied_at_monotonic_ns, migration_digest, applied_by) "
                        "VALUES (?, ?, ?, ?)",
                        (
                            migration.version,
                            monotonic_ns(),
                            migration.statements_digest,
                            MIGRATE_APPLIED_BY,
                        ),
                    )
                conn.execute(f"PRAGMA user_version = {int(migration.version)}")
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            applied.append(migration.version)
            if not already_ledgered:
                ledgered.append(migration.version)
            current_version = migration.version

        repaired: tuple[str, ...] = ledger_repaired
        if not applied and current_version == target_version:
            repaired += _repair_at_current_version(conn, migrations[-1])
        return MigrationOutcome(
            store_name=store_name,
            from_version=from_version,
            to_version=current_version,
            applied=tuple(applied),
            ledgered=tuple(ledgered),
            repaired=repaired,
        )
    finally:
        conn.close()
