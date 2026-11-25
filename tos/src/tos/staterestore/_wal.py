"""The ``journal_mode=WAL`` birth race, closed for the kernel store (**#823**)."""

from __future__ import annotations

import sqlite3

_WAL_JOURNAL_MODE = "wal"

_SQLITE_PRIMARY_CODE_MASK = 0xFF


class StoreJournalModeRefused(RuntimeError):
    """The store file did NOT come out in ``journal_mode=WAL``."""


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
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("ROLLBACK")
    mode = _switch_journal_to_wal(conn)
    return mode


def enable_wal_journal(conn: sqlite3.Connection) -> None:
    """Put ``conn``'s file into ``journal_mode=WAL``, waiting out the birth race (**#823**)."""
    mode: str | None = None
    try:
        mode = _switch_journal_to_wal(conn)
    except sqlite3.OperationalError as exc:
        if not _is_lock_contest(exc):
            raise
    if mode is None:
        mode = _wait_out_the_lock_and_retry(conn)
    if mode != _WAL_JOURNAL_MODE:
        raise StoreJournalModeRefused(
            f"sqlite kept journal_mode={mode!r} instead of switching this store file to "
            "WAL; refusing to open it — every durability argument in tos.staterestore "
            "assumes journal_mode=WAL together with synchronous=FULL"
        )
