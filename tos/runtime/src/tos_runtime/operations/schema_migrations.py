"""Per-store baseline ``SchemaMigration`` definitions + the operator-facing ``apply_migrations``
(TOS Phase 5 W4 plan §2 decision 3).

**Baseline v1, this wave only.** Each of the three runtime-owned durable stores (evidence, RCL,
inbox) gets exactly one registered migration: version 1, "baseline — current DDL as of the
schema-ledger wave". A future wave that actually changes a table's shape adds a SECOND
``SchemaMigration`` per affected store; this module does not invent placeholder future versions.

**Deliberately self-contained (duplicated DDL, not imported).** The literal ``CREATE
TABLE``/trigger strings below mirror — and must be kept in sync with — each store's own DDL
(:mod:`tos_runtime.evidence.store`, :mod:`tos_runtime.rcl.schema`, :mod:`tos_runtime.engine.inbox`,
including the inbox's own ``_ADDED_COLUMNS`` idiom, folded into ``events`` directly here since
baseline v1 IS "the current DDL, added columns included" per the plan). This is intentional, not
an oversight: :func:`apply_migrations` must be able to bring a PRE-EXISTING file (real tables,
``user_version == 0``, never ledgered) up to baseline WITHOUT constructing the real store class
first — that class's own constructor now calls
:func:`~tos_runtime.operations.schema_ledger.ensure_schema_current`, which would immediately
refuse a non-fresh, sub-baseline file with :class:`~tos_runtime.operations.schema_ledger
.SchemaVersionRefused` — precisely the refusal this function exists to resolve. Importing the
store classes here to reuse their DDL would recreate that exact bootstrapping problem.

**Shape verification before stamping (plan §2 decision 3: "PRAGMA table_info 로 현 형상 일치 검증
후 스탬프(불일치 = 거부)").** For a pre-existing file (``user_version == 0``, tables already
present), :func:`apply_migrations` compares each table's REAL, on-disk column set against this
module's own expected column set before running anything — a mismatch refuses
(:class:`SchemaMigrationRefused`) rather than silently running ``CREATE TABLE IF NOT EXISTS``
over a table whose shape this code does not actually recognize.

Firewall: stdlib (``sqlite3``, ``hashlib``, ``time``) only.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tos_runtime.operations.schema_ledger import (
    MIGRATE_APPLIED_BY,
    SCHEMA_LEDGER_TABLE_SQL,
    read_schema_version,
)

__all__ = [
    "EVIDENCE_MIGRATIONS",
    "INBOX_MIGRATIONS",
    "RCL_MIGRATIONS",
    "STORE_MIGRATIONS",
    "SchemaMigration",
    "SchemaMigrationRefused",
    "apply_migrations",
    "schema_version",
]


class SchemaMigrationRefused(RuntimeError):
    """Raised by :func:`apply_migrations` — a pre-existing file's real shape disagrees with the
    migration's expected shape, or the file is already ahead of every known migration.
    """


@dataclass(frozen=True)
class SchemaMigration:
    """One registered schema migration for one store.

    Args:
        version: The ``PRAGMA user_version`` this migration brings a store TO — migrations for a
            store are applied strictly in ascending, gapless order starting from
            ``current_version + 1``.
        description: Free-text, operator-facing.
        statements: The DDL statements applied, in order, inside one transaction.
        expected_tables: ``{table_name: (column_name, ...)}`` — the shape this migration
            produces (or, for a pre-existing file already holding these tables under
            ``user_version == 0``, the shape :func:`apply_migrations` verifies BEFORE stamping).
            Column order matters (matches ``PRAGMA table_info`` order); empty for a migration
            that adds no new table shape to verify (none in this wave).
    """

    version: int
    description: str
    statements: tuple[str, ...]
    expected_tables: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def statements_digest(self) -> str:
        """sha256 over the canonical join of :attr:`statements` — the ledger's own
        ``migration_digest`` value for this migration."""
        canonical = "\n".join(self.statements)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# -- evidence store baseline (mirrors tos_runtime.evidence.store + .outbox) -------------------

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
)

# -- RCL commit log baseline (mirrors tos_runtime.rcl.schema) ---------------------------------

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
)

# -- event inbox baseline (mirrors tos_runtime.engine.inbox, _ADDED_COLUMNS folded in) --------

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

STORE_MIGRATIONS: Mapping[str, tuple[SchemaMigration, ...]] = {
    "evidence": EVIDENCE_MIGRATIONS,
    "rcl": RCL_MIGRATIONS,
    "inbox": INBOX_MIGRATIONS,
}


def schema_version(path: Path) -> int:
    """Read-only: the ``PRAGMA user_version`` currently stamped on the sqlite file at ``path``.

    Opens and closes its own connection — never assumes the store at ``path`` is open or closed
    elsewhere in this process (a read-only ``PRAGMA`` is safe against a concurrently open WAL
    file either way).
    """
    conn = sqlite3.connect(str(path))
    try:
        return read_schema_version(conn)
    finally:
        conn.close()


def _verify_expected_shape_or_refuse(
    conn: sqlite3.Connection, *, store_name: str, migration: SchemaMigration
) -> None:
    """Refuse if any of ``migration.expected_tables`` ALREADY EXISTS with a different column set.

    A table that does not exist yet is not a mismatch (the migration's own ``CREATE TABLE IF NOT
    EXISTS`` will create it) — only an EXISTING table with the WRONG shape refuses.
    """
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
) -> None:
    """Bring the CLOSED store file at ``path`` up to ``store_name``'s latest known migration.

    Operates on its own, fresh ``sqlite3.connect`` — the caller is responsible for the store
    being closed everywhere else in this process first (this function does not itself detect a
    concurrently open handle; matches :mod:`tos_runtime.operations.backup_set`'s own documented
    precondition).

    Args:
        path: The sqlite file to migrate in place.
        store_name: One of :data:`STORE_MIGRATIONS`'s keys (``"evidence"`` / ``"rcl"`` /
            ``"inbox"``).
        monotonic_ns: Injected monotonic-clock callable for the ledger row's
            ``applied_at_monotonic_ns``.

    Raises:
        ValueError: ``store_name`` is not registered.
        SchemaMigrationRefused: The file is already ahead of every known migration for this
            store, or a pre-existing table's real shape disagrees with what a migration expects.
    """
    migrations = STORE_MIGRATIONS.get(store_name)
    if migrations is None:
        raise ValueError(f"apply_migrations: unknown store_name {store_name!r}")

    conn = sqlite3.connect(str(path))
    try:
        conn.execute(SCHEMA_LEDGER_TABLE_SQL)
        current_version = read_schema_version(conn)
        target_version = migrations[-1].version
        if current_version > target_version:
            raise SchemaMigrationRefused(
                f"{store_name}: on-disk user_version={current_version} is already AHEAD of "
                f"the newest known migration ({target_version}) — refusing"
            )
        for migration in migrations:
            if migration.version <= current_version:
                continue
            if current_version == 0:
                _verify_expected_shape_or_refuse(
                    conn, store_name=store_name, migration=migration
                )
            conn.execute("BEGIN IMMEDIATE")
            try:
                for statement in migration.statements:
                    conn.execute(statement)
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
            current_version = migration.version
    finally:
        conn.close()
