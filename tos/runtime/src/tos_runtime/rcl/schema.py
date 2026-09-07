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
  허용(그것이 투영)").

``epochs`` and ``entries`` reject both ``UPDATE`` and ``DELETE`` (append-only,
mechanically unrepresentable — matching
:mod:`tos_runtime.evidence.store`'s own discipline); ``reservations`` rejects
only ``DELETE`` (``UPDATE`` is its whole purpose, as the live projection).

Firewall: stdlib only (bare SQL strings; no ``sqlite3`` import needed here —
execution is the caller's job).
"""

from __future__ import annotations

__all__ = [
    "CREATE_ENTRIES_TABLE_SQL",
    "CREATE_EPOCHS_TABLE_SQL",
    "CREATE_RESERVATIONS_TABLE_SQL",
    "NO_MUTATION_TRIGGERS_SQL",
]

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
    last_seq INTEGER NOT NULL
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
