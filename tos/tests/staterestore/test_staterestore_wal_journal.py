"""The WAL birth race on a brand-new kernel store file (**#823**)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from tos.staterestore._wal import StoreJournalModeRefused, enable_wal_journal
from tos.staterestore.store import CompositeStateStore

_WAL_PRAGMA = "PRAGMA journal_mode=WAL"

_WAIT_AND_RETRY = [_WAL_PRAGMA, "BEGIN IMMEDIATE", "ROLLBACK", _WAL_PRAGMA]


def _capture_locked_error(tmp_path: Path) -> sqlite3.OperationalError:
    """A genuine ``SQLITE_BUSY`` ``OperationalError``, taken from a real lock contest."""
    path = tmp_path / "lock-source.sqlite3"
    holder = sqlite3.connect(str(path), isolation_level=None)
    victim = sqlite3.connect(str(path), isolation_level=None, timeout=0)
    try:
        holder.execute("BEGIN EXCLUSIVE")
        try:
            victim.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            assert exc.sqlite_errorname == "SQLITE_BUSY"
            return exc
        raise AssertionError(  # pragma: no cover - only if sqlite stops locking
            "an exclusive lock did not produce SQLITE_BUSY"
        )
    finally:
        holder.execute("ROLLBACK")
        victim.close()
        holder.close()


def _capture_extended_busy_error(tmp_path: Path) -> sqlite3.OperationalError:
    """A genuine ``SQLITE_BUSY_SNAPSHOT`` — a real EXTENDED variant of the same primary code."""
    path = tmp_path / "snapshot-source.sqlite3"
    writer = sqlite3.connect(str(path), isolation_level=None, timeout=0)
    reader = sqlite3.connect(str(path), isolation_level=None, timeout=0)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE t(x)")
        writer.execute("INSERT INTO t VALUES (1)")
        reader.execute("BEGIN")
        reader.execute("SELECT * FROM t").fetchall()
        writer.execute("INSERT INTO t VALUES (2)")
        try:
            reader.execute("INSERT INTO t VALUES (3)")
        except sqlite3.OperationalError as exc:
            assert exc.sqlite_errorcode == 517, exc.sqlite_errorcode
            assert exc.sqlite_errorname == "SQLITE_BUSY_SNAPSHOT", exc.sqlite_errorname
            return exc
        raise AssertionError(  # pragma: no cover - only if sqlite stops detecting this
            "a stale-snapshot write did not raise SQLITE_BUSY_SNAPSHOT"
        )
    finally:
        reader.close()
        writer.close()


def _capture_readonly_error(tmp_path: Path) -> sqlite3.OperationalError:
    """A genuine ``SQLITE_READONLY`` — what a store file you may not write really raises."""
    path = tmp_path / "readonly-source.sqlite3"
    sqlite3.connect(str(path)).close()
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        conn.execute("CREATE TABLE t(x)")
    except sqlite3.OperationalError as exc:
        assert exc.sqlite_errorname.startswith("SQLITE_READONLY"), exc.sqlite_errorname
        return exc
    finally:
        conn.close()
    raise AssertionError(  # pragma: no cover - only if sqlite stops refusing this
        "writing through a mode=ro connection did not raise"
    )


def _capture_non_lock_error() -> sqlite3.OperationalError:
    """A genuine ``OperationalError`` that is NOT a lock contest (``SQLITE_ERROR``)."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    try:
        conn.execute("SELECT 1 FROM no_such_table")
    except sqlite3.OperationalError as exc:
        assert exc.sqlite_errorname != "SQLITE_BUSY"
        return exc
    finally:
        conn.close()
    raise AssertionError(  # pragma: no cover - only if sqlite stops rejecting this
        "selecting from a missing table did not raise"
    )


# -- a real connection whose WAL pragma fails a scripted number of times ------------------------


class _ScriptedConnection(sqlite3.Connection):
    """A REAL connection on a real file, whose :data:`_WAL_PRAGMA` raises scripted errors first."""

    errors: list[sqlite3.OperationalError]
    log: list[str]

    def execute(self, sql: str, *parameters: Any) -> sqlite3.Cursor:
        self.log.append(sql)
        if sql == _WAL_PRAGMA and self.errors:
            raise self.errors.pop(0)
        return super().execute(sql, *parameters)


def _scripted(
    path: Path, errors: list[sqlite3.OperationalError]
) -> _ScriptedConnection:
    conn = sqlite3.connect(str(path), isolation_level=None, factory=_ScriptedConnection)
    conn.errors = errors
    conn.log = []
    return conn


def test_a_lock_lost_once_is_waited_out_and_the_switch_retried(tmp_path: Path) -> None:
    """The losing side waits on sqlite's OWN busy handler and then switches successfully."""
    conn = _scripted(tmp_path / "store.sqlite3", [_capture_locked_error(tmp_path)])
    try:
        enable_wal_journal(conn)

        assert conn.log == _WAIT_AND_RETRY
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_a_lock_still_held_when_the_retry_runs_refuses_the_open(tmp_path: Path) -> None:
    """Two losses in a row is a refusal, not a third attempt."""
    errors = [_capture_locked_error(tmp_path), _capture_locked_error(tmp_path)]
    conn = _scripted(tmp_path / "store.sqlite3", errors)
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked") as refusal:
            enable_wal_journal(conn)

        assert conn.log == _WAIT_AND_RETRY
        assert refusal.value.__context__ is None
        assert refusal.value.__cause__ is None
    finally:
        conn.close()


def test_a_lock_held_past_the_busy_timeout_refuses_with_nothing_written(
    tmp_path: Path,
) -> None:
    """The other shape of the same refusal: the WAIT ITSELF cannot take the lock."""
    path = tmp_path / "store.sqlite3"
    holder = sqlite3.connect(str(path), isolation_level=None)
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=0)
    try:
        holder.execute("BEGIN EXCLUSIVE")

        with pytest.raises(sqlite3.OperationalError, match="locked"):
            enable_wal_journal(conn)

        holder.execute("ROLLBACK")
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
        assert (
            conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
            == 0
        )
        assert not path.with_name(path.name + "-wal").exists()
        assert not path.with_name(path.name + "-shm").exists()

        enable_wal_journal(conn)
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()
        holder.close()


def test_a_journal_mode_that_is_not_wal_refuses() -> None:
    """A switch sqlite REFUSES is reported by its return value, and must not pass silently."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    try:
        with pytest.raises(StoreJournalModeRefused, match="'memory'"):
            enable_wal_journal(conn)
    finally:
        conn.close()


def test_an_operational_error_that_is_not_a_lock_is_not_retried(tmp_path: Path) -> None:
    """Only a lock contest earns the wait; anything else surfaces from the first attempt."""
    conn = _scripted(tmp_path / "store.sqlite3", [_capture_non_lock_error()])
    try:
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            enable_wal_journal(conn)

        assert conn.log == [_WAL_PRAGMA]
    finally:
        conn.close()


def test_a_readonly_store_is_refused_exactly_as_it_was_before_the_fix(
    tmp_path: Path,
) -> None:
    """A store file that may not be written raises the SAME error, at the SAME attempt."""
    conn = _scripted(tmp_path / "store.sqlite3", [_capture_readonly_error(tmp_path)])
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly") as refusal:
            enable_wal_journal(conn)

        assert not isinstance(refusal.value, StoreJournalModeRefused)
        assert conn.log == [_WAL_PRAGMA]
    finally:
        conn.close()


def test_an_extended_busy_code_is_still_a_lock_contest(tmp_path: Path) -> None:
    """``SQLITE_BUSY_SNAPSHOT`` (517) must take the wait, exactly like plain ``SQLITE_BUSY`` (5)."""
    conn = _scripted(
        tmp_path / "store.sqlite3", [_capture_extended_busy_error(tmp_path)]
    )
    try:
        enable_wal_journal(conn)

        assert conn.log == _WAIT_AND_RETRY
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_a_locked_table_is_not_treated_as_a_lock_contest(tmp_path: Path) -> None:
    """The masking cuts the other way too: ``SQLITE_LOCKED`` (primary 6) is NOT retried."""
    busy = _capture_extended_busy_error(tmp_path)
    locked = sqlite3.OperationalError("database table is locked")
    locked.sqlite_errorcode = (busy.sqlite_errorcode & ~0xFF) | 6
    locked.sqlite_errorname = "SQLITE_LOCKED_SHAREDCACHE"

    conn = _scripted(tmp_path / "store.sqlite3", [locked])
    try:
        with pytest.raises(sqlite3.OperationalError, match="table is locked"):
            enable_wal_journal(conn)

        assert conn.log == [_WAL_PRAGMA]
    finally:
        conn.close()


def test_an_ordinary_fresh_file_switches_on_the_first_attempt(tmp_path: Path) -> None:
    """The uncontended path — no wait, one PRAGMA. Guards against a retry that always runs."""
    conn = _scripted(tmp_path / "store.sqlite3", [])
    try:
        enable_wal_journal(conn)

        assert conn.log == [_WAL_PRAGMA]
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_the_store_still_boots_into_wal_through_the_helper(tmp_path: Path) -> None:
    """The real constructor still leaves its own file in WAL after the rewiring."""
    path = tmp_path / "composite.sqlite3"
    store = CompositeStateStore(path)
    try:
        # 2 == FULL (sqlite's own encoding for `PRAGMA synchronous`).
        assert store._conn.execute("PRAGMA synchronous").fetchone()[0] == 2
    finally:
        store.close()

    probe = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        assert probe.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        probe.close()


def test_a_refused_open_closes_the_store_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A constructor that refuses must not leave its sqlite connection open."""
    path = tmp_path / "composite.sqlite3"
    holder = sqlite3.connect(str(path), isolation_level=None, timeout=0)
    try:
        holder.execute("BEGIN EXCLUSIVE")
        real_connect = sqlite3.connect

        def connect_without_waiting(*args: Any, **kwargs: Any) -> sqlite3.Connection:
            kwargs["timeout"] = 0
            connection: sqlite3.Connection = real_connect(*args, **kwargs)
            return connection

        monkeypatch.setattr(sqlite3, "connect", connect_without_waiting)

        with pytest.raises(sqlite3.OperationalError, match="locked") as refusal:
            CompositeStateStore(path)

        conn = _connection_from_traceback(refusal.value)
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            conn.execute("SELECT 1")
    finally:
        holder.execute("ROLLBACK")
        holder.close()


def _connection_from_traceback(exc: BaseException) -> sqlite3.Connection:
    """The ``self._conn`` of the constructor frame that raised ``exc``."""
    tb = exc.__traceback__
    found: sqlite3.Connection | None = None
    while tb is not None:
        candidate = tb.tb_frame.f_locals.get("self")
        conn = getattr(candidate, "_conn", None)
        if isinstance(conn, sqlite3.Connection):
            found = conn
        tb = tb.tb_next
    assert found is not None, "no constructor frame with a `_conn` in the traceback"
    return found
