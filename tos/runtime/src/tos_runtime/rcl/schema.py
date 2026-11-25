"""``SqliteCommitLog`` sqlite schema: table DDL + append-only trigger SQL."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from tos_runtime.operations.schema_ledger import open_or_create_schema

__all__ = [
    "CREATE_ENTRIES_TABLE_SQL",
    "CREATE_EPOCHS_TABLE_SQL",
    "CREATE_RESERVATIONS_TABLE_SQL",
    "NO_MUTATION_TRIGGERS_SQL",
    "RCL_SCHEMA_VERSION",
    "apply_schema_ledger",
]

RCL_SCHEMA_VERSION = 2

CREATE_EPOCHS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS epochs (
    epoch INTEGER PRIMARY KEY,
    issued_at_monotonic_ns INTEGER NOT NULL,
    runtime_generation INTEGER,
    runtime_identity_json TEXT
)
"""

CREATE_ENTRIES_TABLE_SQL = """
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
"""

CREATE_RESERVATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    last_seq INTEGER NOT NULL,
    scope_account TEXT NOT NULL,
    scope_instrument TEXT NOT NULL,
    committed_vector_json TEXT
)
"""

NO_MUTATION_TRIGGERS_SQL: tuple[str, ...] = (
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


def _create_rcl_schema(conn: sqlite3.Connection, fresh: bool) -> None:
    """This log's own DDL, run by :func:`~tos_runtime.operations.schema_ledger"""
    del fresh
    conn.execute(CREATE_EPOCHS_TABLE_SQL)
    conn.execute(CREATE_ENTRIES_TABLE_SQL)
    conn.execute(CREATE_RESERVATIONS_TABLE_SQL)
    for trigger_sql in NO_MUTATION_TRIGGERS_SQL:
        conn.execute(trigger_sql)


def apply_schema_ledger(
    conn: sqlite3.Connection,
    *,
    monotonic_ns: Callable[[], int],
) -> None:
    """Create-or-check the RCL commit log's schema, atomically (module docstring, #801)."""
    open_or_create_schema(
        conn,
        store_name="rcl",
        schema_version=RCL_SCHEMA_VERSION,
        create_ddl=_create_rcl_schema,
        shape_tables=("epochs", "entries", "reservations"),
        monotonic_ns=monotonic_ns,
    )
