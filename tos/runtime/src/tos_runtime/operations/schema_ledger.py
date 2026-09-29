"""The generic, per-store append-only ``schema_ledger`` table (TOS Phase 5 W4 plan §2 decision 3).

Every runtime-owned durable sqlite store (evidence, RCL, inbox — **not** the kernel-owned
composite-state store, which this package never opens as a table at all; see
:mod:`tos_runtime.operations.backup_set`'s own module docstring) hands its OWN ``CREATE TABLE IF
NOT EXISTS`` DDL to :func:`open_or_create_schema` from its own ``__init__``, so the freshness
decision, that DDL, this module's own ledger DDL and the genesis stamp all happen on the SAME
connection, inside the SAME construction call — and, since #801, inside ONE ``BEGIN IMMEDIATE``
transaction.

**Genesis is atomic (#801, plan ``docs/plans/2026-09-30-tos-schema-genesis-toctou-plan.md``).**
Two runtimes booting against the same EMPTY ``data_dir`` used to reach two distinct failures,
because "decide freshness -> run DDL -> stamp" held no lock across the three steps:

* **R-1** — both processes read :func:`file_is_fresh` as ``True`` before either created a table,
  so both attempted the genesis ``INSERT`` and the loser died on ``sqlite3.IntegrityError:
  UNIQUE constraint failed: schema_ledger.version``.
* **R-2** — a process opening after the winner's ``CREATE TABLE`` but before its stamp saw
  ``was_fresh=False`` with ``user_version = 0`` and refused to boot as "BEHIND", against a file
  that was merely half-created. Re-reading ``file_is_fresh`` inside a lock (#801's own
  recommendation) does not reach this one: that process is already on the non-genesis branch.

:func:`open_or_create_schema` closes both by making the half-created state unobservable — a
second process waits on sqlite's own write lock and then sees a FINISHED file. Its fixture is
:mod:`tos_runtime.tests.operations.test_schema_genesis_concurrency`.

**Boot is a check, never a migration.** Neither :func:`open_or_create_schema` nor
:func:`ensure_schema_current` ever runs an ``ALTER TABLE``/data-shape change of its own — the
three-way disposition is:

1. **Fresh file** (:func:`file_is_fresh` was ``True`` — no user tables existed before the
   caller's own DDL ran): this is a genesis, not a migration. Stamp ``PRAGMA user_version =
   schema_version`` and append one ``schema_ledger`` row with ``applied_by="CREATED"``.
2. **``user_version == schema_version``**: pass silently — this is the ordinary "already at the
   expected version" boot.
3. **``user_version < schema_version``**: :class:`SchemaVersionRefused` — a pre-existing file at
   an older schema. The operator's ``migrate`` CLI
   (:func:`tos_runtime.operations.schema_migrations.apply_migrations`) is the ONLY path that
   changes this; boot never auto-applies (plan §2 decision 3: "부팅 시 자동 적용 0").
4. **``user_version > schema_version``**: :class:`SchemaVersionRefused` — this file was created
   or migrated by code newer than what is running right now; refusing (never silently trusting a
   newer shape) is the same fail-closed discipline as case 3.

``schema_ledger`` itself is append-only, mechanically (``BEFORE UPDATE``/``BEFORE DELETE``
triggers that unconditionally ``RAISE(ABORT, ...)``) — the same discipline
:mod:`tos_runtime.evidence.store`'s own ``entries`` table already uses.

Firewall: stdlib (``sqlite3``, ``hashlib``, ``json``) only.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Sequence
from typing import NoReturn

__all__ = [
    "SCHEMA_LEDGER_TABLE_SQL",
    "SchemaVersionRefused",
    "compute_schema_shape_digest",
    "ensure_schema_current",
    "file_is_fresh",
    "open_or_create_schema",
    "read_schema_version",
    "user_tables",
]

SCHEMA_LEDGER_TABLE_SQL = """
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

#: The ``applied_by`` value :func:`ensure_schema_current` writes for a genesis stamp — never a
#: migration (case 1 above).
CREATED_APPLIED_BY = "CREATED"

#: The ``applied_by`` value :func:`tos_runtime.operations.schema_migrations.apply_migrations`
#: writes for an operator-run migration.
MIGRATE_APPLIED_BY = "MIGRATE"


class SchemaVersionRefused(RuntimeError):
    """Raised at store construction (or by ``apply_migrations``) when the on-disk
    ``PRAGMA user_version`` disagrees with what this code expects — a boot refusal, never an
    auto-applied fix (module docstring cases 3/4)."""


def user_tables(conn: sqlite3.Connection) -> frozenset[str]:
    """The names of every non-sqlite-internal table currently in ``conn``'s own file."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return frozenset(row[0] for row in rows)


def file_is_fresh(conn: sqlite3.Connection) -> bool:
    """``True`` iff ``conn`` has no user tables yet.

    **Must be called BEFORE the caller's own ``CREATE TABLE`` DDL runs** (including before this
    module's own :data:`SCHEMA_LEDGER_TABLE_SQL`) — otherwise a genuinely fresh file looks
    identical to one this very call already populated.

    :func:`open_or_create_schema` calls this INSIDE its own ``BEGIN IMMEDIATE``, which is what
    makes the answer still true by the time the genesis row is written (module docstring, R-1).
    It remains public because :mod:`tos_runtime.operations.schema_migrations` and the test suites
    ask the same question outside that transaction.
    """
    return len(user_tables(conn)) == 0


def compute_schema_shape_digest(
    conn: sqlite3.Connection, table_names: Sequence[str]
) -> str:
    """Digest the CURRENT on-disk column shape of ``table_names`` (sorted, stable).

    Reads ``PRAGMA table_info`` for each table (never the source DDL text) — the digest reflects
    what sqlite actually holds, not what a caller's SQL string happened to say, so it stays
    correct even if a future migration changes the DDL wording without changing the resulting
    shape (e.g. reformatting) or vice versa. Table order in ``table_names`` does not matter (
    sorted internally) — order of *columns within* a table is preserved (as sqlite reports it),
    since column ORDER is part of a table's real shape.
    """
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


def _refuse_version(store_name: str, current: int, schema_version: int) -> NoReturn:
    """Raise the BEHIND/AHEAD refusal for a non-fresh file (module docstring cases 3/4).

    Shared verbatim by :func:`ensure_schema_current` and :func:`open_or_create_schema` so the two
    entry points cannot drift into refusing on different wording — or, worse, on different
    conditions.
    """
    if current < schema_version:
        raise SchemaVersionRefused(
            f"{store_name}: on-disk schema user_version={current} is BEHIND this code's "
            f"schema_version={schema_version} — run the operator `migrate` CLI "
            "(tos_runtime.operations.schema_migrations.apply_migrations) before booting; "
            "boot never auto-applies a migration"
        )
    raise SchemaVersionRefused(
        f"{store_name}: on-disk schema user_version={current} is AHEAD of this code's "
        f"schema_version={schema_version} — this file was created or migrated by newer code "
        "than what is running now"
    )


def open_or_create_schema(
    conn: sqlite3.Connection,
    *,
    store_name: str,
    schema_version: int,
    create_ddl: Callable[[sqlite3.Connection, bool], None],
    shape_tables: Sequence[str],
    monotonic_ns: Callable[[], int],
) -> bool:
    """Create this store's schema if the file is fresh, else check it — atomically (#801).

    Everything a genesis consists of runs inside ONE ``BEGIN IMMEDIATE`` ... ``COMMIT``::

        BEGIN IMMEDIATE                 <- write lock; a second process waits HERE
          fresh = file_is_fresh(conn)   <- decided under the lock (module docstring, R-1/R-2)
          create_ddl(conn, fresh)       <- the caller's own CREATE TABLE/INDEX/TRIGGER
          schema_ledger DDL + triggers
          if fresh: PRAGMA user_version = schema_version; INSERT the CREATED row
        COMMIT
        if not fresh: compare versions  <- unchanged rules (module docstring cases 2/3/4)

    Two properties follow, and neither held before:

    * A concurrent opener never observes a half-created file. It blocks on sqlite's own write
      lock until the winner commits, then reads ``fresh=False`` with the version already stamped
      and takes the ordinary "already current" path.
    * Any exception — from ``create_ddl`` or from this function — ``ROLLBACK``s, so a failed
      genesis leaves ZERO user tables rather than the partial set autocommitted DDL used to
      leave behind.

    ``PRAGMA journal_mode`` is deliberately NOT set here: it cannot be changed inside a
    transaction, so each store keeps setting it on its own connection immediately after
    connecting, before this call.

    Args:
        conn: The store's own live connection, in autocommit mode (``isolation_level=None``) so
            the explicit ``BEGIN IMMEDIATE`` below is the only transaction in play.
        store_name: The store's own name (``"evidence"`` / ``"rcl"`` / ``"inbox"`` /
            ``"marketfeed"``) — used only in a refusal's error message.
        schema_version: The CODE's own expected schema version for this store.
        create_ddl: The store's own DDL, called as ``create_ddl(conn, fresh)``. It receives the
            freshness verdict because some statements are genesis-only: the evidence store's
            ``entries_kind_seq`` index must NOT be built on a non-fresh file (that is
            ``migrate``'s job, and boot is a check — see
            :mod:`tos_runtime.evidence.store`'s own note on it).
        shape_tables: The tables whose on-disk shape is digested into the genesis ledger row
            (:func:`compute_schema_shape_digest`), read AFTER ``create_ddl`` has run.
        monotonic_ns: Injected monotonic-clock callable — never ``time.monotonic_ns`` read
            directly (matches every other store's own constructor-injection discipline).

    Returns:
        ``True`` iff THIS call performed the genesis (and therefore wrote the ``CREATED`` row).

    Raises:
        SchemaVersionRefused: On-disk ``user_version`` is behind OR ahead of ``schema_version``
            for a non-fresh file (module docstring cases 3/4).
        sqlite3.OperationalError: The write lock could not be taken within the connection's own
            busy timeout — a fail-closed boot refusal, never a partially created file.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        fresh = file_is_fresh(conn)
        create_ddl(conn, fresh)
        conn.execute(SCHEMA_LEDGER_TABLE_SQL)
        conn.execute(_SCHEMA_LEDGER_NO_UPDATE_TRIGGER_SQL)
        conn.execute(_SCHEMA_LEDGER_NO_DELETE_TRIGGER_SQL)
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
        conn.execute("ROLLBACK")
        raise
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
    """Check (never migrate) ``conn``'s own ``schema_ledger``/``user_version`` state.

    **Kept for callers that own their own transaction boundary.** Since #801 no store constructor
    calls this — they all go through :func:`open_or_create_schema`, which folds the DDL and this
    check into one transaction. This function stays because it still has genuine callers
    (:mod:`tos_runtime.operations.schema_migrations`'s tests, and the generic-helper tests), and
    because it is the only form usable when the DDL is NOT the caller's to run. It carries the
    pre-#801 TOCTOU by construction — ``was_fresh`` is decided by the caller, outside any lock —
    so a NEW store must use :func:`open_or_create_schema`, not this.

    Args:
        conn: The store's own live connection — this function creates the ``schema_ledger``
            table on it (idempotent) and, in the fresh-file case, writes the genesis stamp.
        store_name: The store's own name (``"evidence"`` / ``"rcl"`` / ``"inbox"``) — used only
            in a refusal's error message.
        schema_version: The CODE's own expected schema version for this store.
        was_fresh: The :func:`file_is_fresh` result, captured by the CALLER before it ran its own
            ``CREATE TABLE`` DDL (this function cannot determine that itself — by the time it
            runs, the caller's tables already exist).
        migration_digest: The digest recorded on a genesis (``CREATED``) ledger row — the
            caller's own :func:`compute_schema_shape_digest` over the tables it just created.
        monotonic_ns: Injected monotonic-clock callable — never ``time.monotonic_ns`` read
            directly (matches every other store's own constructor-injection discipline).

    Raises:
        SchemaVersionRefused: On-disk ``user_version`` is behind OR ahead of ``schema_version``
            for a non-fresh file (module docstring cases 3/4).
    """
    conn.execute(SCHEMA_LEDGER_TABLE_SQL)
    conn.execute(_SCHEMA_LEDGER_NO_UPDATE_TRIGGER_SQL)
    conn.execute(_SCHEMA_LEDGER_NO_DELETE_TRIGGER_SQL)
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
