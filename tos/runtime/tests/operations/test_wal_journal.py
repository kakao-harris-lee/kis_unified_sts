"""The WAL birth race on a brand-new store file (**#818**,"""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from tos_runtime.operations.schema_ledger import JournalModeRefused, enable_wal_journal

from .conftest import FixedKeyProvider

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_WAL_PRAGMA = "PRAGMA journal_mode=WAL"

_WAIT_AND_RETRY = [_WAL_PRAGMA, "BEGIN IMMEDIATE", "ROLLBACK", _WAL_PRAGMA]

_DIAGNOSTIC_STATEMENTS = frozenset({"PRAGMA database_list"})


def _mechanism(log: list[str]) -> list[str]:
    """``log`` with the log-line diagnostics removed — what the helper did, not what it said."""
    return [sql for sql in log if sql not in _DIAGNOSTIC_STATEMENTS]


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
        raise AssertionError(  # pragma: no cover - only if sqlite stops detecting stale snapshots
            "a stale-snapshot write did not raise SQLITE_BUSY_SNAPSHOT"
        )
    finally:
        reader.close()
        writer.close()


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

        assert _mechanism(conn.log) == _WAIT_AND_RETRY
        assert _DIAGNOSTIC_STATEMENTS.issubset(conn.log)
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_a_lock_still_held_when_the_retry_runs_refuses_the_boot(tmp_path: Path) -> None:
    """Two losses in a row is a boot refusal, not a third attempt."""
    errors = [_capture_locked_error(tmp_path), _capture_locked_error(tmp_path)]
    conn = _scripted(tmp_path / "store.sqlite3", errors)
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked") as refusal:
            enable_wal_journal(conn)

        assert _mechanism(conn.log) == _WAIT_AND_RETRY
        assert refusal.value.__context__ is None
        assert refusal.value.__cause__ is None
    finally:
        conn.close()


def test_a_lock_held_past_the_busy_timeout_refuses_the_boot_with_nothing_written(
    tmp_path: Path,
) -> None:
    """The other shape of the same refusal: the WAIT ITSELF cannot take the lock (plan T-4)."""
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


def test_a_journal_mode_that_is_not_wal_refuses_the_boot() -> None:
    """A switch sqlite REFUSES is reported by its return value, and must not pass silently."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    try:
        with pytest.raises(JournalModeRefused, match="'memory'"):
            enable_wal_journal(conn)
    finally:
        conn.close()


def test_an_operational_error_that_is_not_a_lock_is_not_retried(tmp_path: Path) -> None:
    """Only a lock contest earns the wait; anything else surfaces from the first attempt."""
    conn = _scripted(tmp_path / "store.sqlite3", [_capture_non_lock_error()])
    try:
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            enable_wal_journal(conn)

        assert _mechanism(conn.log) == [_WAL_PRAGMA]
    finally:
        conn.close()


def test_an_extended_busy_code_is_still_a_lock_contest(tmp_path: Path) -> None:
    """``SQLITE_BUSY_SNAPSHOT`` (517) must take the wait, exactly like plain ``SQLITE_BUSY`` (5)."""
    conn = _scripted(
        tmp_path / "store.sqlite3", [_capture_extended_busy_error(tmp_path)]
    )
    try:
        enable_wal_journal(conn)

        assert _mechanism(conn.log) == _WAIT_AND_RETRY
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

        assert _mechanism(conn.log) == [_WAL_PRAGMA]
    finally:
        conn.close()


def test_an_ordinary_fresh_file_switches_on_the_first_attempt(tmp_path: Path) -> None:
    """The uncontended path — no wait, one PRAGMA. Guards against a retry that always runs."""
    conn = _scripted(tmp_path / "store.sqlite3", [])
    try:
        enable_wal_journal(conn)

        assert _mechanism(conn.log) == [_WAL_PRAGMA]
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_every_durable_store_boots_into_wal_through_the_helper(tmp_path: Path) -> None:
    """The four real constructors still leave their own file in WAL after the rewiring (T-2)."""
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
    from tos_runtime.engine.inbox import SqliteEventInbox
    from tos_runtime.evidence.store import SqliteEvidenceStore
    from tos_runtime.marketfeed.store import SqliteSnapshotStore
    from tos_runtime.rcl.log import SqliteCommitLog

    evidence_path = tmp_path / "evidence.sqlite3"
    evidence = SqliteEvidenceStore(evidence_path, key_provider=FixedKeyProvider())
    inbox_path = tmp_path / "inbox.sqlite3"
    inbox = SqliteEventInbox(inbox_path, scheme=get_scheme(EV_L1_PROVISIONAL_VERSION))
    marketfeed_path = tmp_path / "marketfeed.sqlite3"
    marketfeed = SqliteSnapshotStore(marketfeed_path)
    rcl_path = tmp_path / "rcl.sqlite3"
    rcl = SqliteCommitLog(rcl_path, evidence_port=evidence)
    for handle in (rcl, marketfeed, inbox, evidence):
        handle.close()

    for path in (evidence_path, inbox_path, marketfeed_path, rcl_path):
        probe = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            mode = probe.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            probe.close()
        assert mode.lower() == "wal", f"{path.name} did not come out in WAL mode"


def _construct(
    store: str, path: Path, tmp_path: Path, stack: contextlib.ExitStack
) -> object:
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
    from tos_runtime.engine.inbox import SqliteEventInbox
    from tos_runtime.evidence.store import SqliteEvidenceStore
    from tos_runtime.marketfeed.store import SqliteSnapshotStore
    from tos_runtime.rcl.log import SqliteCommitLog

    if store == "evidence":
        return SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    if store == "inbox":
        return SqliteEventInbox(path, scheme=get_scheme(EV_L1_PROVISIONAL_VERSION))
    if store == "marketfeed":
        return SqliteSnapshotStore(path)
    if store == "rcl":
        evidence = stack.enter_context(
            contextlib.closing(
                SqliteEvidenceStore(
                    tmp_path / "rcl-private-evidence.sqlite3",
                    key_provider=FixedKeyProvider(),
                )
            )
        )
        return SqliteCommitLog(path, evidence_port=evidence, sqlite_timeout_s=0)
    raise AssertionError(f"unknown store {store!r}")


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


@pytest.mark.parametrize("store", ["evidence", "inbox", "marketfeed", "rcl"])
def test_a_refused_boot_closes_the_store_connection(
    tmp_path: Path, store: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A constructor that refuses must not leave its sqlite connection open (**F3**)."""
    path = tmp_path / f"{store}.sqlite3"
    holder = sqlite3.connect(str(path), isolation_level=None, timeout=0)
    try:
        holder.execute("BEGIN EXCLUSIVE")
        real_connect = sqlite3.connect

        def connect_without_waiting(*args: Any, **kwargs: Any) -> sqlite3.Connection:
            kwargs["timeout"] = 0
            connection: sqlite3.Connection = real_connect(*args, **kwargs)
            return connection

        monkeypatch.setattr(sqlite3, "connect", connect_without_waiting)

        with contextlib.ExitStack() as stack:
            with pytest.raises(sqlite3.OperationalError, match="locked") as refusal:
                _construct(store, path, tmp_path, stack)

            conn = _connection_from_traceback(refusal.value)
            with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
                conn.execute("SELECT 1")
    finally:
        holder.execute("ROLLBACK")
        holder.close()
