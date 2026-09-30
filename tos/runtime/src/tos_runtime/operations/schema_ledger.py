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

**The earlier race, and where it is closed (#818).** The GENESIS TRANSACTION race (R-1/R-2
above) is closed by :func:`open_or_create_schema`. A concurrent first boot against a **brand-new**
file used to fail EARLIER than that function ever ran: each store sets ``PRAGMA journal_mode=WAL``
on its own connection before calling here, and switching a never-yet-WAL file's journal mode takes
a lock that sqlite does NOT retry through the busy timeout, so one side lost with
``sqlite3.OperationalError: database is locked`` before any schema code ran (measured on a
brand-new file: ~22/80 losing openers at N=2, 57/160 at N=4, 90/320 at N=8). That was out of
#801's scope; it is closed here by :func:`enable_wal_journal`, which every store now calls in
place of the bare PRAGMA. The two fixes are independent and both are needed — this one gets the
file into WAL, that one makes the schema genesis on it atomic.

**A steady-state boot takes no write lock (review MEDIUM-1).** Folding the DDL into the genesis
transaction would otherwise have made EVERY boot contend for the exclusive write lock — with a live
runtime appending evidence, an operator CLI (``rearm`` / ``ack-alert`` / ``rotate-key``), or a long
``apply_migrations`` index build — where before #801 a boot against an existing, current file took
no write lock at all. A store constructed with a short busy timeout
(``SqliteCommitLog(sqlite_timeout_s=0)``) would fail instantly against any of them. So
:func:`open_or_create_schema` decides the common case with two LOCK-FREE reads before it starts a
transaction: ``PRAGMA user_version == schema_version`` **and** the ``schema_ledger`` table exists.

That is sound in the direction it is used. The version stamp and the tables commit in the SAME
transaction, so ``user_version == schema_version`` cannot be observed unless a genesis (or an
``apply_migrations``) already finished — there is no state where the version is current but the
schema is not. Every other observation (version 0, a behind/ahead version, a missing ledger) falls
through to ``BEGIN IMMEDIATE``, so R-1/R-2 stay closed: a concurrent FIRST boot can never take the
fast path, because ``user_version`` is 0 until someone commits the stamp.

The consequence to know: a steady-state boot now runs NO DDL, so it no longer re-creates an
auxiliary structure that was removed by hand (an index an operator dropped, say). That was never a
reliable repair anyway — the evidence store's ``entries_kind_seq`` is genesis-only since #816 — and
:attr:`~tos_runtime.operations.schema_migrations.SchemaMigration.repair_statements` is the
sanctioned path for it.

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

import contextlib
import hashlib
import json
import logging
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from typing import NoReturn, Protocol

#: The FIRST logger in ``tos_runtime`` (review round-2 F6). Nothing in this package logged before,
#: and nothing else does now — this one line exists because :func:`enable_wal_journal` can block
#: for up to three busy timeouts per store, which on four stores is ~60 s of a boot that used to
#: fail in milliseconds. A supervisor with a shorter start budget kills the process before the
#: fail-closed refusal is ever printed, and the operator sees a boot that "hung" with no record of
#: why. ``logging.lastResort`` sends WARNING and above to stderr with no handler configured, so
#: this reaches an operator by default and stays silenceable without any config key of ours.
_LOG = logging.getLogger(__name__)

__all__ = [
    "SCHEMA_LEDGER_TABLE_SQL",
    "JournalModeRefused",
    "closing_on_failure",
    "SchemaVersionRefused",
    "compute_schema_shape_digest",
    "enable_wal_journal",
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


#: The journal mode every runtime-owned durable store must end up in. Compared against what
#: sqlite actually reports, never assumed — see :func:`enable_wal_journal`.
_WAL_JOURNAL_MODE = "wal"

#: Mask that reduces an sqlite EXTENDED result code to its primary code. Every ``SQLITE_BUSY_*``
#: variant is ``SQLITE_BUSY | (n << 8)``, so the low byte is the only part that answers "was this
#: a lock contest".
_SQLITE_PRIMARY_CODE_MASK = 0xFF


class SupportsClose(Protocol):
    """Anything with a no-argument ``close()`` — a connection, or a store that owns one."""

    def close(
        self,
    ) -> None: ...  # pragma: no cover - a structural type, never called here


@contextlib.contextmanager
def closing_on_failure(resource: SupportsClose) -> Iterator[None]:
    """Close ``resource`` if the block raises; leave it open if the block completes.

    **The one place the boot-refusal leak is closed** (review round-2 F3, round-3 F3). Every
    durable store assigns ``self._conn`` and only then runs code that can refuse a boot — the
    WAL switch, the schema genesis, the evidence store's key-continuity gate. A raise out of
    ``__init__`` hands the half-built instance to nobody, so nothing closes that connection, and
    refcounting does not save it: the raising frame is held by the exception's traceback, so the
    connection and its ``-wal``/``-shm`` files live as long as the caller keeps the exception —
    unbounded for a caller that catches and logs, which is exactly what
    :func:`tos_runtime.operations.backup_archive.verify_archive` and the operator CLIs do.

    The same shape appears one frame up, wherever a caller builds a store and then validates it
    (:func:`tos_runtime.evidence.backup.restore_evidence`), which is why this takes anything with
    ``close()`` rather than a connection specifically.

    ``contextlib.closing`` is deliberately NOT what this is: that one closes unconditionally, and
    a successful construction must hand back a live handle.
    """
    try:
        yield
    except BaseException:
        resource.close()
        raise


class JournalModeRefused(RuntimeError):
    """Raised at store construction when the file did NOT come out in ``journal_mode=WAL`` — a
    boot refusal, never a silent fallback to the rollback journal (:func:`enable_wal_journal`).
    """


def _database_file(conn: sqlite3.Connection) -> str:
    """The main database's filename, for the one log line — never for control flow.

    ``PRAGMA database_list`` answers with the attached databases; ``main``'s file is what the
    caller opened. Best effort by construction: this runs while the file is contended, so a
    failure to read it must not turn a recoverable wait into a boot refusal. ``"<unknown>"`` then.
    """
    try:
        for _seq, name, filename in conn.execute("PRAGMA database_list").fetchall():
            if name == "main":
                return str(filename) or "<in-memory>"
    except sqlite3.Error:  # pragma: no cover - defensive; the pragma takes no lock
        return "<unknown>"
    return "<unknown>"


def _is_lock_contest(exc: sqlite3.OperationalError) -> bool:
    """``True`` iff ``exc`` is sqlite's "somebody else holds the lock" — ANY ``SQLITE_BUSY_*``.

    The PRIMARY result code is what carries that meaning; the extended code adds a reason in the
    high bits. Python surfaces the EXTENDED one in both attributes (measured: a stale-snapshot
    write raises ``sqlite_errorname='SQLITE_BUSY_SNAPSHOT'``, ``sqlite_errorcode=517``, message
    ``database is locked``), so comparing the NAME to ``"SQLITE_BUSY"`` — which this function
    replaced after review — silently dropped every variant into the "not a lock contest,
    re-raise" branch. ``SQLITE_BUSY_RECOVERY`` is the one that matters here: a late opener whose
    PRAGMA meets the winner's WAL recovery gets it, and it is exactly the case the retry exists
    for.

    Masking is also what keeps this honest about errors that are NOT contention: ``SQLITE_LOCKED``
    (primary 6, a table lock inside the same connection handle) and every other primary code still
    fall through to the re-raise.

    A hand-built ``sqlite3.OperationalError`` carries no ``sqlite_errorcode`` at all (measured), so
    the attribute is read defensively and its absence means "not a lock contest" — the tests that
    exercise this path replay errors captured from real sqlite operations rather than fabricating
    them, precisely because the fabricated object is not the one production sees.
    """
    code = getattr(exc, "sqlite_errorcode", None)
    if not isinstance(code, int):
        return False
    return (code & _SQLITE_PRIMARY_CODE_MASK) == sqlite3.SQLITE_BUSY


def _switch_journal_to_wal(conn: sqlite3.Connection) -> str:
    """Run the switch PRAGMA once; return the journal mode sqlite actually left in place.

    sqlite reports a REFUSED switch by returning the mode it kept rather than by raising, so the
    answer is the only evidence there is. ``""`` for the (unreachable in sqlite, but not in a
    double) no-row case, which :func:`enable_wal_journal` then refuses like any other non-WAL
    answer instead of indexing into ``None``.
    """
    row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    return "" if row is None else str(row[0]).lower()


def _wait_out_the_lock_and_retry(conn: sqlite3.Connection) -> str:
    """Wait on sqlite's OWN busy handler, then run the switch PRAGMA exactly once more.

    ``BEGIN IMMEDIATE`` takes a write lock and, unlike ``PRAGMA journal_mode``, it DOES retry
    through the connection's configured busy timeout — which is the whole trick: the wait costs
    no new constant, because the connection already carries one. The ``ROLLBACK`` is immediate
    and the transaction writes nothing.

    **Called from OUTSIDE its caller's ``except`` block, deliberately** (review round-2 F2).
    Raising from inside it would attach the handled first ``SQLITE_BUSY`` as ``__context__``, and
    a refused boot would print two chained "database is locked" tracebacks under "During handling
    of the above exception" — inviting the operator to read the first, expected, already-handled
    one as the failure. Out here the exception state is cleared and a second failure propagates
    unchained.

    Returns:
        The journal mode sqlite left in place after the retry — the caller checks it, since a
        refused switch is reported by the RETURN value, not by raising.
    """
    path = _database_file(conn)
    # "Two more", not "three" (review round-3 F5): the first PRAGMA's own wait is already spent
    # by the time this line is written, so the bound an operator can still act on is the wait
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
        # A bare re-raise: same object, no new exception, so nothing is chained onto it. Logged
        # because the line above promised an outcome and a silent stall reads like a hang.
        _LOG.warning(
            "journal_mode=WAL still locked after the wait on %s; refusing boot.", path
        )
        raise
    _LOG.warning(
        "journal_mode=WAL switch recovered on %s; journal_mode is now %r.", path, mode
    )
    return mode


def enable_wal_journal(conn: sqlite3.Connection) -> None:
    """Put ``conn``'s file into ``journal_mode=WAL``, waiting out the birth race (**#818**).

    Switching a never-yet-WAL file from the rollback journal to WAL takes an exclusive lock, and
    ``PRAGMA journal_mode`` does **not** go through sqlite's busy handler: the loser of a
    concurrent first boot fails IMMEDIATELY with ``sqlite3.OperationalError: database is locked``
    instead of waiting out its own connection's timeout. Measured on a brand-new file before this
    helper existed: the bare PRAGMA lost 17/80 openers at N=2 (plan
    ``docs/plans/2026-09-30-tos-wal-birth-race-plan.md`` §1) and 73/320 at N=8 (re-measured while
    implementing it); through the real store constructors, #801's review measured 22/80 at N=2 and
    90/320 at N=8. It is the one concurrent-first-boot failure #801's atomic genesis left open,
    and it fires BEFORE any schema code runs.

    So when the PRAGMA loses that lock, this waits on sqlite's OWN busy handler — ``BEGIN
    IMMEDIATE`` takes a write lock and, unlike the PRAGMA, it DOES retry through the connection's
    timeout — and then calls the PRAGMA exactly once more. The ``ROLLBACK`` is immediate and the
    transaction wrote nothing.

    **What the retry actually does depends on who held the lock (review F3).** In the case this
    exists for — a brand-new file, a sibling runtime mid-switch — the holder WAS the switcher, so
    by the time the wait returns the file is already WAL and the second PRAGMA is a no-op. If the
    holder was an ordinary writer on a file still in rollback mode (an operator CLI's transaction,
    say), the second PRAGMA performs the REAL switch, and its own ``RESERVED`` upgrade bypasses
    the busy handler exactly like the first one did — so a third party that grabs the lock in the
    gap makes the retry lose immediately and the boot is refused. That is fail-closed and correct,
    but it is not the "already WAL, so it cannot fail" story: every store file this package owns is
    born in WAL inside its own constructor, which is why the precondition for that shape is rare
    rather than why it is impossible.

    Four deliberate edges, each with its own test in :mod:`.test_wal_journal`:

    * **Exactly one retry.** No loop, no attempt counter. A second failure means nobody released
      the lock within the connection's whole timeout, which is a boot refusal rather than
      something to keep hammering — that ``OperationalError`` propagates unchanged.
    * **No new waiting constant — but the bound is THREE of them, not one (review F4).** Every
      wait here is the busy timeout already configured on ``conn`` (python's 5 s default for the
      evidence, inbox and marketfeed stores; the injected ``sqlite_timeout_s`` for
      :class:`~tos_runtime.rcl.log.SqliteCommitLog`), and this module adds no timeout, sleep or
      interval of its own — plan §3 rejects the interval-retry alternative for exactly that
      reason. What it does NOT add up to is a single timeout: the first PRAGMA can itself wait
      (its ``SHARED``/``EXCLUSIVE`` acquisitions DO go through the handler; only the ``RESERVED``
      upgrade skips it), then ``BEGIN IMMEDIATE`` can wait, then the retried PRAGMA can wait.
      Worst case a refused boot takes about 3x the connection's timeout — ~15 s at the stdlib
      default. Size boot deadlines against that number, not against 5 s.
    * **The return value is checked.** sqlite reports a refused switch by RETURNING the mode it
      kept, not by raising (a ``:memory:`` connection answers ``memory``). Accepting that silently
      would leave a store on the rollback journal while every durability argument in this package
      assumes WAL plus ``synchronous=FULL``, so a non-``wal`` answer is :class:`JournalModeRefused`.
    * **Only a lock contest is retried — every ``SQLITE_BUSY_*``, by PRIMARY code (review F2).**
      :func:`_is_lock_contest` masks the extended result code, because python reports the
      EXTENDED name and an exact ``"SQLITE_BUSY"`` name comparison (what this first shipped with)
      dropped ``SQLITE_BUSY_RECOVERY`` — a late opener meeting the winner's WAL recovery, which is
      the very case the retry exists for — into the re-raise branch. Any OTHER primary code,
      ``SQLITE_LOCKED`` included, still propagates from the first attempt; retrying it would only
      delay and obscure it.

    The refusal does not name the store (this helper is deliberately given nothing but the
    connection, per plan §2.1) — the raising constructor in the traceback does.

    Args:
        conn: The store's own live connection, in autocommit mode (``isolation_level=None``),
            already opened on the file about to be booted. Autocommit is what makes the ``BEGIN
            IMMEDIATE`` below legal as an explicit statement; :func:`open_or_create_schema`, which
            every caller of this helper reaches immediately afterwards, enforces it by hand.

    Raises:
        JournalModeRefused: The file is not in WAL mode after the switch.
        sqlite3.OperationalError: The lock was still held when the single retry ran, or the wait
            itself could not take it — a fail-closed boot refusal; nothing was written. Also any
            ``OperationalError`` whose primary code is not ``SQLITE_BUSY``, unretried.
    """
    # One variable, not two (review round-3 F6): `None` IS "the first attempt yielded no mode",
    # so there is no second flag to keep consistent with it. A no-row answer is `""`, which is
    # not None and therefore not retried — correct, since that is not a lock contest.
    mode: str | None = None
    try:
        mode = _switch_journal_to_wal(conn)
    except sqlite3.OperationalError as exc:
        if not _is_lock_contest(exc):
            raise
    # OUTSIDE the except block, deliberately (review round-2 F2). Raising from inside it would
    # attach the handled first SQLITE_BUSY as `__context__`, and a refused boot would print two
    # chained "database is locked" tracebacks under "During handling of the above exception" —
    # inviting the operator to read the first, expected, already-handled one as the failure.
    # Out here the exception state is cleared, so the second failure propagates unchained.
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


def _schema_ledger_exists(conn: sqlite3.Connection) -> bool:
    """``True`` iff the ``schema_ledger`` table is already on ``conn``'s file.

    A lock-free read, used only by :func:`open_or_create_schema`'s steady-state fast path as the
    second half of "this file is already finished". It is not redundant with the version check: a
    file that predates the schema ledger entirely, or one an operator demoted by dropping the
    table, can carry a matching ``user_version`` with no ledger — that file must reach
    ``BEGIN IMMEDIATE`` so the ledger DDL runs, not be waved through.
    """
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_ledger'"
    ).fetchone()
    return row is not None


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


def _run_genesis_transaction(
    conn: sqlite3.Connection,
    *,
    schema_version: int,
    create_ddl: Callable[[sqlite3.Connection, bool], None],
    shape_tables: Sequence[str],
    monotonic_ns: Callable[[], int],
) -> tuple[bool, int]:
    """Run the whole genesis inside ONE ``BEGIN IMMEDIATE`` ... ``COMMIT``; return
    ``(was_fresh, on_disk_version)``.

    Extracted from :func:`open_or_create_schema` to keep both functions inside the repo's
    100-line function budget (``tools/tos_size_budget.py``, operator-configured threshold) — a
    pure decomposition, no behavior change: the same statements run on the same connection in the
    same order, inside the same one transaction.

    The version comparison deliberately stays with the CALLER: it happens after ``COMMIT``, so it
    is not part of the transaction this function owns.

    Raises:
        Whatever ``create_ddl`` raises, or sqlite3's own errors — always after a ``ROLLBACK``, so
        a failed genesis leaves zero user tables.
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
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            # The transaction was already ended — a ``create_ddl`` that committed or rolled back
            # itself before failing leaves sqlite reporting "cannot rollback - no transaction is
            # active". The ORIGINAL exception is the diagnosis; replacing it with this one would
            # throw the diagnosis away and report a symptom of the cleanup instead (review LOW-1).
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
    """Create this store's schema if the file is fresh, else check it — atomically (#801).

    Everything a genesis consists of runs inside ONE ``BEGIN IMMEDIATE`` ... ``COMMIT``::

        if user_version == schema_version and schema_ledger exists:
            return False            <- STEADY-STATE FAST PATH: two lock-free reads, no write lock
        BEGIN IMMEDIATE                 <- write lock; a second process waits HERE
          fresh = file_is_fresh(conn)   <- decided under the lock (module docstring, R-1/R-2)
          create_ddl(conn, fresh)       <- the caller's own CREATE TABLE/INDEX/TRIGGER
          schema_ledger DDL + triggers
          if fresh: PRAGMA user_version = schema_version; INSERT the CREATED row
        COMMIT
        if not fresh: compare versions  <- unchanged rules (module docstring cases 2/3/4)

    Two properties follow from the transaction, and neither held before: a concurrent opener never
    observes a half-created file (it blocks on sqlite's own write lock, then reads ``fresh=False``
    with the version already stamped), and any exception ``ROLLBACK``s, so a failed genesis leaves
    ZERO user tables instead of the partial set autocommitted DDL used to leave behind. The
    fast path's own rationale and its one consequence are in the module docstring, as is the
    earlier ``journal_mode`` race on a brand-new file, which this function does not touch and
    :func:`enable_wal_journal` closes (**#818**).

    Args:
        conn: The store's own live connection, in autocommit mode (``isolation_level=None``) so
            the explicit ``BEGIN IMMEDIATE`` below is the only transaction in play. Enforced —
            under sqlite3's implicit-transaction modes the ``BEGIN IMMEDIATE`` below raises
            mid-genesis and the whole atomicity argument is void.
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
        ValueError: ``conn`` is not in autocommit mode (``isolation_level`` is not ``None``).
        SchemaVersionRefused: On-disk ``user_version`` is behind OR ahead of ``schema_version``
            for a non-fresh file (module docstring cases 3/4).
        sqlite3.OperationalError: The write lock could not be taken within the connection's own
            busy timeout — a fail-closed boot refusal, never a partially created file. A
            steady-state boot does not reach the lock at all (fast path above).
    """
    if conn.isolation_level is not None:
        raise ValueError(
            f"{store_name}: open_or_create_schema needs a connection in autocommit mode "
            f"(sqlite3.connect(..., isolation_level=None)); got "
            f"isolation_level={conn.isolation_level!r}. Otherwise sqlite3 opens an implicit "
            "transaction of its own and the explicit BEGIN IMMEDIATE that makes genesis atomic "
            "raises 'cannot start a transaction within a transaction' mid-boot"
        )
    # Steady-state fast path (review MEDIUM-1) — two lock-free reads, no write lock. The module
    # docstring carries the argument for why `user_version == schema_version` is sufficient.
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
