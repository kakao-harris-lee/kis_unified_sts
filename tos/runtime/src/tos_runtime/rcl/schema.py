"""``SqliteCommitLog`` sqlite schema: table DDL + append-only trigger SQL.

Extracted from :mod:`tos_runtime.rcl.log` to keep that module under the
repo's 1000-line module size budget (``tools/tos_size_budget.py``,
operator-configured threshold, CLAUDE.md "thresholds belong in config, not
code") — a pure decomposition, no behavior change: every string here is
executed by :class:`~tos_runtime.rcl.log.SqliteCommitLog`'s own
``__init__`` in exactly the order it always was, over the exact same
``sqlite3.Connection``.

Three tables (design #40 D2.1, slice plan §1 item 1):

* ``epochs`` — Writer Epoch history (:meth:`SqliteCommitLog.acquire_epoch`).
* ``entries`` — the append-only command log
  (:meth:`SqliteCommitLog.append_cas` / ``apply_reservation_transition``).
  ``is_reservation_transition`` discriminates a genuine reservation-lifecycle
  entry from a plain ``append_cas`` entry whose ``payload_json`` merely
  *looks* like one (independent review MEDIUM-4, 2026-09-08 — see
  ``log.py``'s own module docstring's "the replay fold is discriminated, not
  payload-shape-matched" section for the full rationale).
* ``reservations`` — the one mutable projection table (design #40 D2.1
  "컴팩션/보존: 항목 삭제 0" + slice plan §1 item 6 "reservations 만 UPDATE
  허용(그것이 투영)"). ``scope_account``/``scope_instrument`` (laneO
  port-fix round, design #40 runtime slice #2 §5 disposition, 2026-09-08)
  persist the kernel's ``CapacityReservationTransition.scope`` binding —
  ``NOT NULL`` because :meth:`SqliteCommitLog.apply_reservation_transition`
  refuses any transition whose ``scope`` is absent before a row is ever
  written (see ``log.py``'s own module docstring). ``committed_vector_json``
  (kernel round #4 K-4, schema v2) persists the kernel's
  ``CapacityReservationTransition.committed_vector`` — nullable (``None`` on
  the kernel side means "no vector committed", not a zero vector, and every
  pre-K-4 row is genuinely ``NULL`` after the v1→v2 migration).

``epochs`` and ``entries`` reject both ``UPDATE`` and ``DELETE`` (append-only,
mechanically unrepresentable — matching
:mod:`tos_runtime.evidence.store`'s own discipline); ``reservations`` rejects
only ``DELETE`` (``UPDATE`` is its whole purpose, as the live projection).

**Schema-ledger integration lives here too (TOS Phase 5 W4 plan §2 decision 3, size-budget
decomposition).** :func:`apply_schema_ledger` wraps the
:mod:`tos_runtime.operations.schema_ledger` boot check for THIS store specifically — moved out of
``log.py``'s own ``__init__`` for the same 1000-line module-size-budget reason every other
extraction in this file's own module docstring already documents (a pure decomposition, no
behavior change: the check still runs on the SAME connection, in the SAME order, inside the SAME
``__init__`` call). Since #801 it also OWNS the three ``CREATE TABLE`` statements and the
triggers above, because they now run inside the genesis transaction
(:func:`~tos_runtime.operations.schema_ledger.open_or_create_schema`) rather than in autocommit
ahead of it — same statements, same order, one transaction.

Firewall: stdlib (``sqlite3``) only, plus ``tos_runtime.operations`` for the schema-ledger check
(the DDL constants above remain bare SQL strings needing no import).
"""

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

#: TOS Phase 5 W4 plan §2 decision 3 — see
#: ``tos_runtime.evidence.store.EVIDENCE_SCHEMA_VERSION``'s own docstring for the shared
#: convention.
#:
#: **v2 (kernel round #4 K-4).** ``reservations`` gained ``committed_vector_json`` (the
#: durable form of ``CapacityReservationTransition.committed_vector``, kernel round #4 K-4) — a
#: pre-existing v1 store file must be brought up via
#: ``tos_runtime.operations.schema_migrations.apply_migrations(path, "rcl")`` BEFORE this code
#: can open it again (:func:`apply_schema_ledger` / ``ensure_schema_current`` refuses a
#: non-fresh file whose stamped version disagrees — a boot refusal, never an auto-migrate).
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
    # reservations is the ONE mutable projection table (design #40 D2.1 "컴팩션/
    # 보존: 항목 삭제 0" + slice plan §1 item 6 "reservations 만 UPDATE 허용
    # (그것이 투영)") — UPDATE is deliberately NOT blocked here; only DELETE is.
    """
    CREATE TRIGGER IF NOT EXISTS reservations_no_delete
    BEFORE DELETE ON reservations
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: reservations rows are never deleted');
    END
    """,
)


def _create_rcl_schema(conn: sqlite3.Connection, fresh: bool) -> None:
    """This log's own DDL, run by :func:`~tos_runtime.operations.schema_ledger
    .open_or_create_schema` inside the genesis transaction — exactly the statements
    ``SqliteCommitLog.__init__`` used to run inline, in the same order.

    ``fresh`` is unused: every statement here is idempotent on a pre-existing file (this store
    has no genesis-only structure like the evidence store's ``entries_kind_seq``).
    """
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
    """Create-or-check the RCL commit log's schema, atomically (module docstring, #801).

    Args:
        conn: The log's own live connection, in autocommit mode. This function now runs the
            log's DDL itself (inside the genesis transaction) — the caller no longer runs it,
            and no longer captures ``file_is_fresh`` either, because that decision moved inside
            the same transaction (which is the whole point of the fix).
        monotonic_ns: Injected monotonic-clock callable for a genesis ledger row.
    """
    open_or_create_schema(
        conn,
        store_name="rcl",
        schema_version=RCL_SCHEMA_VERSION,
        create_ddl=_create_rcl_schema,
        shape_tables=("epochs", "entries", "reservations"),
        monotonic_ns=monotonic_ns,
    )
