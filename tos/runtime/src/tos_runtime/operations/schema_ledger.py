"""The generic, per-store append-only ``schema_ledger`` table (TOS Phase 5 W4 plan §2 decision 3)."""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import sqlite3
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, Literal, NoReturn, Protocol

_LOG = logging.getLogger(__name__)

__all__ = [
    "SCHEMA_LEDGER_TRIGGER_NAMES",
    "JournalModeRefused",
    "SchemaLedgerUnprotected",
    "closing_on_failure",
    "SchemaVersionDirection",
    "SchemaVersionRefused",
    "compute_schema_shape_digest",
    "create_schema_ledger_objects",
    "enable_wal_journal",
    "ensure_schema_current",
    "file_is_fresh",
    "open_or_create_schema",
    "read_schema_version",
    "user_tables",
]

_SCHEMA_LEDGER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_ledger (
    version INTEGER PRIMARY KEY,
    applied_at_monotonic_ns INTEGER NOT NULL,
    migration_digest TEXT NOT NULL,
    applied_by TEXT NOT NULL
)
"""

_SCHEMA_LEDGER_NO_UPDATE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS schema_ledger_no_update
BEFORE UPDATE ON schema_ledger
BEGIN
    SELECT RAISE(ABORT, 'tos_runtime schema ledger: schema_ledger is append-only — UPDATE forbidden');
END
"""

_SCHEMA_LEDGER_NO_DELETE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS schema_ledger_no_delete
BEFORE DELETE ON schema_ledger
BEGIN
    SELECT RAISE(ABORT, 'tos_runtime schema ledger: schema_ledger is append-only — DELETE forbidden');
END
"""

_SCHEMA_LEDGER_TABLE_NAME = "schema_ledger"


class SchemaLedgerUnprotected(RuntimeError):
    """The ``schema_ledger`` cannot be shown to be append-only, so nothing claims it is."""


SCHEMA_LEDGER_TRIGGER_NAMES: tuple[str, ...] = (
    "schema_ledger_no_update",
    "schema_ledger_no_delete",
)


def create_schema_ledger_objects(conn: sqlite3.Connection) -> tuple[str, ...]:
    """Create the ``schema_ledger`` table AND its two append-only triggers, idempotently."""
    conn.execute("SAVEPOINT tos_schema_ledger_objects")
    try:
        pre_existing = _schema_ledger_exists(conn)
        conn.execute(_SCHEMA_LEDGER_TABLE_SQL)
        before = _ledger_trigger_owners(conn)
        _refuse_foreign_trigger_names(before)
        conn.execute(_SCHEMA_LEDGER_NO_UPDATE_TRIGGER_SQL)
        conn.execute(_SCHEMA_LEDGER_NO_DELETE_TRIGGER_SQL)
        _refuse_unless_protected(_ledger_trigger_owners(conn))
    except BaseException:
        conn.execute("ROLLBACK TO tos_schema_ledger_objects")
        conn.execute("RELEASE tos_schema_ledger_objects")
        raise
    conn.execute("RELEASE tos_schema_ledger_objects")
    if not pre_existing:
        return ()
    return tuple(name for name in SCHEMA_LEDGER_TRIGGER_NAMES if name not in before)


def _ledger_trigger_owners(conn: sqlite3.Connection) -> dict[str, str]:
    """``{trigger name: the table it is attached to}`` for the two reserved ledger names."""
    placeholders = ", ".join("?" for _ in SCHEMA_LEDGER_TRIGGER_NAMES)
    rows = conn.execute(
        "SELECT name, tbl_name FROM sqlite_master WHERE type = 'trigger' "
        f"AND name IN ({placeholders})",
        SCHEMA_LEDGER_TRIGGER_NAMES,
    ).fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def _refuse_foreign_trigger_names(owners: Mapping[str, str]) -> None:
    """Refuse when a reserved trigger name is already taken by another table."""
    foreign = {
        name: table
        for name, table in owners.items()
        if table != _SCHEMA_LEDGER_TABLE_NAME
    }
    if foreign:
        raise SchemaLedgerUnprotected(
            f"schema ledger: trigger name(s) {sorted(foreign)} already exist attached to "
            f"{sorted(set(foreign.values()))}, not to {_SCHEMA_LEDGER_TABLE_NAME!r} — "
            "`CREATE TRIGGER IF NOT EXISTS` would silently no-op and leave the ledger "
            "writable while reporting that nothing needed repair; refusing instead"
        )


def _refuse_unless_protected(owners: Mapping[str, str]) -> None:
    """Refuse unless BOTH reserved triggers now sit on ``schema_ledger``."""
    missing = [
        name
        for name in SCHEMA_LEDGER_TRIGGER_NAMES
        if owners.get(name) != _SCHEMA_LEDGER_TABLE_NAME
    ]
    if missing:
        raise SchemaLedgerUnprotected(
            f"schema ledger: {missing} still not attached to {_SCHEMA_LEDGER_TABLE_NAME!r} "
            "after creating them — refusing to report the ledger as protected"
        )


def _trigger_names(conn: sqlite3.Connection) -> frozenset[str]:
    """Every trigger currently defined on this file."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name IS NOT NULL"
    ).fetchall()
    return frozenset(str(row[0]) for row in rows)


CREATED_APPLIED_BY = "CREATED"

MIGRATE_APPLIED_BY = "MIGRATE"


SchemaVersionDirection = Literal["BEHIND", "AHEAD"]


class SchemaVersionRefused(RuntimeError):
    """Raised by :func:`open_or_create_schema` and :func:`ensure_schema_current` (both"""

    def __init__(self, message: str, *, direction: SchemaVersionDirection) -> None:
        """Refuse ``message``; ``direction`` says which way the disagreement runs."""
        super().__init__(message)
        self.direction: SchemaVersionDirection = direction

    def __reduce__(
        self,
    ) -> tuple[
        Callable[..., SchemaVersionRefused],
        tuple[type[SchemaVersionRefused], str, SchemaVersionDirection],
        dict[str, Any],
    ]:
        """Rebuild through :func:`_rebuild_schema_version_refused` instead of ``cls(*args)``."""
        return (
            _rebuild_schema_version_refused,
            (type(self), self.args[0], self.direction),
            self.__dict__,
        )


def _rebuild_schema_version_refused(
    cls: type[SchemaVersionRefused],
    message: str,
    direction: SchemaVersionDirection,
) -> SchemaVersionRefused:
    """Reconstruct a :class:`SchemaVersionRefused` — or a subclass of it — from its parts."""
    return cls(message, direction=direction)


_WAL_JOURNAL_MODE = "wal"

_SQLITE_PRIMARY_CODE_MASK = 0xFF


class SupportsClose(Protocol):
    """Anything with a no-argument ``close()`` — a connection, or a store that owns one."""

    def close(
        self,
    ) -> None: ...  # pragma: no cover - a structural type, never called here


@contextlib.contextmanager
def closing_on_failure(resource: SupportsClose) -> Iterator[None]:
    """Close ``resource`` if the block raises; leave it open if the block completes."""
    try:
        yield
    except BaseException:
        resource.close()
        raise


class JournalModeRefused(RuntimeError):
    """Raised at store construction when the file did NOT come out in ``journal_mode=WAL`` — a"""


def _database_file(conn: sqlite3.Connection) -> str:
    """The main database's filename, for the one log line — never for control flow."""
    try:
        for _seq, name, filename in conn.execute("PRAGMA database_list").fetchall():
            if name == "main":
                return str(filename) or "<in-memory>"
    except sqlite3.Error:  # pragma: no cover - defensive; the pragma takes no lock
        return "<unknown>"
    return "<unknown>"


def _is_lock_contest(exc: sqlite3.OperationalError) -> bool:
    """``True`` iff ``exc`` is sqlite's "somebody else holds the lock" — ANY ``SQLITE_BUSY_*``."""
    code = getattr(exc, "sqlite_errorcode", None)
    if not isinstance(code, int):
        return False
    return (code & _SQLITE_PRIMARY_CODE_MASK) == sqlite3.SQLITE_BUSY


def _switch_journal_to_wal(conn: sqlite3.Connection) -> str:
    """Run the switch PRAGMA once; return the journal mode sqlite actually left in place."""
    row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    return "" if row is None else str(row[0]).lower()


def _wait_out_the_lock_and_retry(conn: sqlite3.Connection) -> str:
    """Wait on sqlite's OWN busy handler, then run the switch PRAGMA exactly once more."""
    path = _database_file(conn)
    # "Two more", not "three" (review round-3 F5): the first PRAGMA's own wait is already spent
    # below plus the retried PRAGMA.
    _LOG.warning(
        "journal_mode=WAL switch lost the lock on %s; waiting on sqlite's busy handler and "
        "retrying once. From here this can take up to two more of this connection's busy "
        "timeouts before it refuses the boot.",
        path,
    )
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("ROLLBACK")
    try:
        mode = _switch_journal_to_wal(conn)
    except sqlite3.OperationalError:
        _LOG.warning(
            "journal_mode=WAL still locked after the wait on %s; refusing boot.", path
        )
        raise
    _LOG.warning(
        "journal_mode=WAL switch recovered on %s; journal_mode is now %r.", path, mode
    )
    return mode


def enable_wal_journal(conn: sqlite3.Connection) -> None:
    """Put ``conn``'s file into ``journal_mode=WAL``, waiting out the birth race (**#818**)."""
    mode: str | None = None
    try:
        mode = _switch_journal_to_wal(conn)
    except sqlite3.OperationalError as exc:
        if not _is_lock_contest(exc):
            raise
    if mode is None:
        mode = _wait_out_the_lock_and_retry(conn)
    if mode != _WAL_JOURNAL_MODE:
        raise JournalModeRefused(
            f"sqlite kept journal_mode={mode!r} instead of switching this store file to WAL; "
            "refusing to boot on it — every durability argument in tos_runtime's durable "
            "stores assumes journal_mode=WAL together with synchronous=FULL"
        )


def user_tables(conn: sqlite3.Connection) -> frozenset[str]:
    """The names of every non-sqlite-internal table currently in ``conn``'s own file."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return frozenset(row[0] for row in rows)


def file_is_fresh(conn: sqlite3.Connection) -> bool:
    """``True`` iff ``conn`` has no user tables yet."""
    return len(user_tables(conn)) == 0


def compute_schema_shape_digest(
    conn: sqlite3.Connection, table_names: Sequence[str]
) -> str:
    """Digest the CURRENT on-disk column shape of ``table_names`` (sorted, stable)."""
    shapes: list[tuple[str, tuple[tuple[object, ...], ...]]] = []
    for name in sorted(table_names):
        rows = conn.execute(f"PRAGMA table_info({name})").fetchall()
        shapes.append((name, tuple(tuple(row) for row in rows)))
    canonical = json.dumps(shapes, sort_keys=False, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_schema_version(path_conn: sqlite3.Connection) -> int:
    """Read-only helper: the ``PRAGMA user_version`` currently stamped on ``path_conn``'s file."""
    row = path_conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def _schema_ledger_exists(conn: sqlite3.Connection) -> bool:
    """``True`` iff the ``schema_ledger`` table is already on ``conn``'s file."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_ledger'"
    ).fetchone()
    return row is not None


def _refuse_version(store_name: str, current: int, schema_version: int) -> NoReturn:
    """Raise the BEHIND/AHEAD refusal for a non-fresh file (module docstring cases 3/4)."""
    if current < schema_version:
        raise SchemaVersionRefused(
            f"{store_name}: on-disk schema user_version={current} is BEHIND this code's "
            f"schema_version={schema_version} — run the operator `migrate` CLI "
            "(tos_runtime.operations.schema_migrations.apply_migrations) before booting; "
            "boot never auto-applies a migration",
            direction="BEHIND",
        )
    raise SchemaVersionRefused(
        f"{store_name}: on-disk schema user_version={current} is AHEAD of this code's "
        f"schema_version={schema_version} — this file was created or migrated by newer code "
        "than what is running now",
        direction="AHEAD",
    )


def _run_genesis_transaction(
    conn: sqlite3.Connection,
    *,
    schema_version: int,
    create_ddl: Callable[[sqlite3.Connection, bool], None],
    shape_tables: Sequence[str],
    monotonic_ns: Callable[[], int],
) -> tuple[bool, int]:
    """Run the whole genesis inside ONE ``BEGIN IMMEDIATE`` ... ``COMMIT``; return"""
    conn.execute("BEGIN IMMEDIATE")
    try:
        fresh = file_is_fresh(conn)
        create_ddl(conn, fresh)
        create_schema_ledger_objects(conn)
        if fresh:
            conn.execute(f"PRAGMA user_version = {int(schema_version)}")
            conn.execute(
                "INSERT INTO schema_ledger "
                "(version, applied_at_monotonic_ns, migration_digest, applied_by) "
                "VALUES (?, ?, ?, ?)",
                (
                    schema_version,
                    monotonic_ns(),
                    compute_schema_shape_digest(conn, shape_tables),
                    CREATED_APPLIED_BY,
                ),
            )
        current = read_schema_version(conn)
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        raise
    return fresh, current


def open_or_create_schema(
    conn: sqlite3.Connection,
    *,
    store_name: str,
    schema_version: int,
    create_ddl: Callable[[sqlite3.Connection, bool], None],
    shape_tables: Sequence[str],
    monotonic_ns: Callable[[], int],
) -> bool:
    """Create this store's schema if the file is fresh, else check it — atomically (#801)."""
    if conn.isolation_level is not None:
        raise ValueError(
            f"{store_name}: open_or_create_schema needs a connection in autocommit mode "
            f"(sqlite3.connect(..., isolation_level=None)); got "
            f"isolation_level={conn.isolation_level!r}. Otherwise sqlite3 opens an implicit "
            "transaction of its own and the explicit BEGIN IMMEDIATE that makes genesis atomic "
            "raises 'cannot start a transaction within a transaction' mid-boot"
        )
    if read_schema_version(conn) == schema_version and _schema_ledger_exists(conn):
        return False
    fresh, current = _run_genesis_transaction(
        conn,
        schema_version=schema_version,
        create_ddl=create_ddl,
        shape_tables=shape_tables,
        monotonic_ns=monotonic_ns,
    )
    if fresh:
        return True
    if current != schema_version:
        _refuse_version(store_name, current, schema_version)
    return False


def ensure_schema_current(
    conn: sqlite3.Connection,
    *,
    store_name: str,
    schema_version: int,
    was_fresh: bool,
    migration_digest: str,
    monotonic_ns: Callable[[], int],
) -> None:
    """Check (never migrate) ``conn``'s own ``schema_ledger``/``user_version`` state."""
    create_schema_ledger_objects(conn)
    current = read_schema_version(conn)
    if was_fresh:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(f"PRAGMA user_version = {int(schema_version)}")
            conn.execute(
                "INSERT INTO schema_ledger "
                "(version, applied_at_monotonic_ns, migration_digest, applied_by) "
                "VALUES (?, ?, ?, ?)",
                (schema_version, monotonic_ns(), migration_digest, CREATED_APPLIED_BY),
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        return
    if current == schema_version:
        return
    _refuse_version(store_name, current, schema_version)
