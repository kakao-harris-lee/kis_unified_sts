"""The ``journal_mode=WAL`` birth race, closed for the kernel store (**#823**).

Switching a file that has never been WAL from the rollback journal to WAL takes an
exclusive lock, and ``PRAGMA journal_mode`` does **not** go through sqlite's busy
handler. The loser of a concurrent first open therefore fails IMMEDIATELY with
``sqlite3.OperationalError: database is locked`` instead of waiting out its own
connection's timeout. :func:`enable_wal_journal` waits on sqlite's OWN busy handler
(``BEGIN IMMEDIATE`` / ``ROLLBACK`` — that pair DOES retry through the timeout) and then
calls the PRAGMA exactly once more.

**Why this is a second implementation and not an import** (#823 approach 1). The runtime
shell already owns the identical mechanism in
``tos_runtime.operations.schema_ledger.enable_wal_journal``, where four durable stores
share it (#818, PR #820). The kernel cannot import it: the asymmetric import firewall
forbids ``tos -> tos_runtime`` outright (design §3, rule (g)), and moving the helper down
into the kernel would be a change to the ratified pure-commons set — a design-document
revision, not a bug fix. So the mechanism is duplicated, deliberately, in stdlib
``sqlite3`` only. The duplication is held together the way this repo already holds
duplicated DDL together: ``tests/tools/test_tos_wal_mechanism_drift.py`` reads both
modules as text and fails if the two mechanisms stop being the same one.

**No logging here, on purpose.** The runtime helper emits three ``logging.WARNING``
lines, because a refused boot there can block a supervisor for ~3x the connection's busy
timeout per store with no record of why (#820 round-2 F6). The kernel has **no logging
convention at all** (measured: zero ``import logging`` under ``tos/src``), and inventing
one for this module would make a tos-wide decision as a side effect of a bug fix. The
silence is bounded differently here anyway: the kernel store is opened per write by
:class:`tos_runtime.recovery.composite_state_writer.CompositeStateWriter`, one file, not
four at boot, and the refusal reaches that caller as an ordinary exception.

This module is non-transmitting, like the rest of the package: it takes a connection
somebody else opened and executes pragmas on it. No socket, no route, no credential, no
ambient env (``tos/__init__.py`` line 6; TOS-FW-B / TOS-FW-C).
"""

from __future__ import annotations

import sqlite3

#: The journal mode the store must end up in. Compared against what sqlite actually
#: reports, never assumed — see :func:`enable_wal_journal`.
_WAL_JOURNAL_MODE = "wal"

#: Mask that reduces an sqlite EXTENDED result code to its primary code. Every
#: ``SQLITE_BUSY_*`` variant is ``SQLITE_BUSY | (n << 8)``, so the low byte is the only
#: part that answers "was this a lock contest".
_SQLITE_PRIMARY_CODE_MASK = 0xFF


class JournalModeRefused(RuntimeError):
    """The store file did NOT come out in ``journal_mode=WAL``.

    Fail-closed, and for the same reason :class:`~tos.staterestore.store
    .StoreIntegrityError` is: every durability argument this package makes assumes WAL
    together with ``synchronous=FULL``. A store left on the rollback journal with
    ``synchronous=FULL`` set on it is a *different* substrate than the one design #39
    §3.2 candidate A names, and accepting it silently would make ``persistence_real``
    an over-claim rather than a measurement.
    """


def _is_lock_contest(exc: sqlite3.OperationalError) -> bool:
    """``True`` iff ``exc`` is sqlite's "somebody else holds the lock" — ANY ``SQLITE_BUSY_*``.

    The PRIMARY result code is what carries that meaning; the extended code adds a
    reason in the high bits. Python surfaces the EXTENDED one in both attributes (a
    stale-snapshot write raises ``sqlite_errorname='SQLITE_BUSY_SNAPSHOT'``,
    ``sqlite_errorcode=517``, message ``database is locked``), so comparing the NAME to
    ``"SQLITE_BUSY"`` drops every variant into the "not a lock contest, re-raise"
    branch. ``SQLITE_BUSY_RECOVERY`` is the one that matters here: a late opener whose
    PRAGMA meets the winner's WAL recovery gets it, and that is exactly a birth race.

    Masking also keeps this honest about errors that are NOT contention:
    ``SQLITE_LOCKED`` (primary 6, a table lock inside the same connection handle) and
    every other primary code still fall through to the re-raise.

    A hand-built ``sqlite3.OperationalError`` carries no ``sqlite_errorcode`` at all, so
    the attribute is read defensively and its absence means "not a lock contest".
    """
    code = getattr(exc, "sqlite_errorcode", None)
    if not isinstance(code, int):
        return False
    return (code & _SQLITE_PRIMARY_CODE_MASK) == sqlite3.SQLITE_BUSY


def _switch_journal_to_wal(conn: sqlite3.Connection) -> str:
    """Run the switch PRAGMA once; return the journal mode sqlite actually left in place.

    sqlite reports a REFUSED switch by returning the mode it kept rather than by
    raising, so the answer is the only evidence there is. ``""`` for the no-row case,
    which :func:`enable_wal_journal` then refuses like any other non-WAL answer instead
    of indexing into ``None``.
    """
    row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    return "" if row is None else str(row[0]).lower()


def _wait_out_the_lock_and_retry(conn: sqlite3.Connection) -> str:
    """Wait on sqlite's OWN busy handler, then run the switch PRAGMA exactly once more.

    ``BEGIN IMMEDIATE`` takes a write lock and, unlike ``PRAGMA journal_mode``, it DOES
    retry through the connection's configured busy timeout — which is the whole trick:
    the wait costs no new constant, because the connection already carries one. The
    ``ROLLBACK`` is immediate and the transaction writes nothing.

    **Called from OUTSIDE its caller's ``except`` block, deliberately.** Raising from
    inside it would attach the handled first ``SQLITE_BUSY`` as ``__context__``, and a
    refused open would print two chained "database is locked" tracebacks under "During
    handling of the above exception" — inviting the reader to take the first, expected,
    already-handled one for the failure.

    Returns:
        The journal mode sqlite left in place after the retry — the caller checks it,
        since a refused switch is reported by the RETURN value, not by raising.
    """
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("ROLLBACK")
    return _switch_journal_to_wal(conn)


def enable_wal_journal(conn: sqlite3.Connection) -> None:
    """Put ``conn``'s file into ``journal_mode=WAL``, waiting out the birth race (**#823**).

    Measured on this repository's own :class:`~tos.staterestore.store
    .CompositeStateStore` constructor before this helper existed — 8 processes opening
    the same brand-new path at once, 40 rounds: **96 / 320 losing openers, and only
    6 / 40 rounds came out clean**. Every failure was ``OperationalError: database is
    locked`` out of the bare ``PRAGMA journal_mode=WAL``.

    Three deliberate edges, each with its own test in
    :mod:`tos.tests.staterestore.test_staterestore_wal_journal`:

    * **Exactly one retry.** No loop, no attempt counter. A second failure means nobody
      released the lock within the connection's whole timeout, which is a refusal rather
      than something to keep hammering — that ``OperationalError`` propagates unchanged.
    * **The return value is checked.** sqlite reports a refused switch by RETURNING the
      mode it kept, not by raising, so a non-``wal`` answer is :class:`JournalModeRefused`.
    * **Only a lock contest is retried**, by PRIMARY code (:func:`_is_lock_contest`).

    **The bound is THREE busy timeouts, not one.** The first PRAGMA can itself wait (its
    ``SHARED``/``EXCLUSIVE`` acquisitions DO go through the handler; only the
    ``RESERVED`` upgrade skips it), then ``BEGIN IMMEDIATE`` can wait, then the retried
    PRAGMA can wait. Worst case a refusal takes about 3x the connection's timeout —
    ~15 s at the stdlib default. This module adds no timeout, sleep or interval of its
    own, and prints nothing while it waits (see the module docstring).

    Args:
        conn: The store's own live connection, in autocommit mode
            (``isolation_level=None``), already opened on the file. Autocommit is what
            makes the ``BEGIN IMMEDIATE`` above legal as an explicit statement.

    Raises:
        JournalModeRefused: The file is not in WAL mode after the switch.
        sqlite3.OperationalError: The lock was still held when the single retry ran, or
            the wait itself could not take it — fail-closed; nothing was written. Also
            any ``OperationalError`` whose primary code is not ``SQLITE_BUSY``, unretried.
    """
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
            f"sqlite kept journal_mode={mode!r} instead of switching this store file to "
            "WAL; refusing to open it — every durability argument in tos.staterestore "
            "assumes journal_mode=WAL together with synchronous=FULL"
        )
