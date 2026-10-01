"""The WAL birth race on a brand-new kernel store file (**#823**).

:func:`~tos.staterestore._wal.enable_wal_journal` is what
:class:`~tos.staterestore.store.CompositeStateStore` now opens through instead of a bare
``PRAGMA journal_mode=WAL``. What it has to survive is narrow and easy to state:
switching a never-yet-WAL file to WAL takes an exclusive lock, and that PRAGMA does
**not** go through sqlite's busy handler, so a concurrent first open loses one side
outright with ``sqlite3.OperationalError: database is locked``. The cross-PROCESS proof
that the fix closes it lives next door in
:mod:`.test_staterestore_wal_birth_race`; this module pins the helper's own edges,
deterministically and without a race:

* a lock lost once is waited out and the switch retried (and it is a REAL wait — the
  ``BEGIN IMMEDIATE`` / ``ROLLBACK`` pair is observed, not assumed);
* a lock still held after that wait refuses, in both shapes it can take, leaving the
  file and its sidecars untouched;
* a journal mode that comes back as anything but ``wal`` refuses — sqlite reports a
  refused switch by RETURNING the mode it kept, never by raising, and the pre-#823 code
  did not look at the answer at all;
* an ``OperationalError`` that is not a lock contest is re-raised on the FIRST attempt,
  never retried — while EVERY ``SQLITE_BUSY_*`` extended code still counts as one;
* a refused construction leaves no open connection behind.

**Every sqlite error that must be RETRIED is a real one.** The doubles below replay
:class:`sqlite3.OperationalError` instances captured from genuine sqlite operations — an
exclusive lock held by a second connection, a stale WAL snapshot, a select against a
missing table — because the helper discriminates on ``sqlite_errorcode``, and a
hand-built ``OperationalError("database is locked")`` carries no such attribute at all.
A test that fabricated one would be exercising a different object than production sees.

**One object here IS fabricated, and it is the ``SQLITE_LOCKED`` one.** sqlite will not
hand out ``SQLITE_LOCKED`` on demand in a hermetic test — it needs shared-cache mode or
a vtab — so that test builds a fresh ``OperationalError`` and sets
``sqlite_errorcode`` / ``sqlite_errorname`` by hand. That is sound for what it checks,
because it is the NEGATIVE direction: it asserts the helper does NOT retry, and a
fabricated object cannot make a non-retry look like a retry. It would not be sound for a
positive case, which is why none of those use one.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from tos.staterestore._wal import StoreJournalModeRefused, enable_wal_journal
from tos.staterestore.store import CompositeStateStore

_WAL_PRAGMA = "PRAGMA journal_mode=WAL"

#: The MECHANISM, and nothing else: two switch attempts bracketing exactly one wait.
#: This is the property the retry exists for, and the count is what most of these tests
#: turn on. The kernel helper runs no diagnostic statements of its own — it emits no log
#: line at all (``tos/src`` has no logging convention; see the module's own docstring) —
#: so unlike the runtime's sibling suite there is nothing to filter out of the log here.
_WAIT_AND_RETRY = [_WAL_PRAGMA, "BEGIN IMMEDIATE", "ROLLBACK", _WAL_PRAGMA]


# -- real captured sqlite errors --------------------------------------------------------------


def _capture_locked_error(tmp_path: Path) -> sqlite3.OperationalError:
    """A genuine ``SQLITE_BUSY`` ``OperationalError``, taken from a real lock contest.

    Captured rather than constructed: ``sqlite3.OperationalError("database is locked")``
    built by hand has no ``sqlite_errorname`` at all, so it is not the object the
    helper's discriminator sees in production.
    """
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
    """A genuine ``SQLITE_BUSY_SNAPSHOT`` — a real EXTENDED variant of the same primary code.

    sqlite raises this when a connection that already holds a read snapshot tries to
    write after the WAL moved past it. It is not the variant the birth race produces
    (that is ``SQLITE_BUSY_RECOVERY``, whose recovery window is too narrow to force
    deterministically) but it is the same thing that matters here: ``sqlite_errorname``
    carries the EXTENDED name and ``sqlite_errorcode`` is ``517``, whose low byte is
    ``SQLITE_BUSY``. Anything that discriminates on the name fails this; anything that
    masks the code passes it.
    """
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
    """A genuine ``SQLITE_READONLY`` — what a store file you may not write really raises.

    Provoked through a ``mode=ro`` URI rather than ``chmod``, so it is the same object
    on any filesystem and in a container running as root (where ``chmod`` restrains
    nobody and a permissions-based test would silently stop testing).
    """
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
    """A REAL connection on a real file, whose :data:`_WAL_PRAGMA` raises scripted errors first.

    Everything else — ``BEGIN IMMEDIATE``, ``ROLLBACK``, the retried PRAGMA — runs
    against sqlite for real, so the wait this module claims to observe is the production
    wait and not a stub. Subclassing is the only way in (``sqlite3.Connection`` is a C
    type whose ``execute`` cannot be patched per instance); a python subclass does get a
    ``__dict__``, so the script and the log are per-instance.
    """

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


# -- the edges -----------------------------------------------------------------------------


def test_a_lock_lost_once_is_waited_out_and_the_switch_retried(tmp_path: Path) -> None:
    """The losing side waits on sqlite's OWN busy handler and then switches successfully.

    RED before #823: the bare ``PRAGMA journal_mode=WAL`` had no retry at all, so the
    captured ``SQLITE_BUSY`` escaped the constructor and the file stayed on the rollback
    journal.

    The statement log is the load-bearing half. "The file ended up in WAL" alone would
    also pass if the helper had swallowed the error and the file happened to be WAL
    already; what pins the mechanism is that ``BEGIN IMMEDIATE`` / ``ROLLBACK`` — the
    wait, and the ONLY thing in this code that waits — actually ran, between two PRAGMA
    attempts.
    """
    conn = _scripted(tmp_path / "store.sqlite3", [_capture_locked_error(tmp_path)])
    try:
        enable_wal_journal(conn)

        assert conn.log == _WAIT_AND_RETRY
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_a_lock_still_held_when_the_retry_runs_refuses_the_open(tmp_path: Path) -> None:
    """Two losses in a row is a refusal, not a third attempt.

    The retry is deliberately ONE attempt: a second failure means nobody released the
    lock for the whole of this connection's busy timeout, and hammering it would only
    turn a fail-closed refusal into an unbounded stall. The log pins the count — exactly
    two PRAGMA attempts, one wait, and no third try.
    """
    errors = [_capture_locked_error(tmp_path), _capture_locked_error(tmp_path)]
    conn = _scripted(tmp_path / "store.sqlite3", errors)
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked") as refusal:
            enable_wal_journal(conn)

        assert conn.log == _WAIT_AND_RETRY
        # The refusal must NOT be chained onto the first, deliberately-handled
        # SQLITE_BUSY. If the retry ran inside the `except` block, python would attach
        # that first error as `__context__` and the traceback would carry two "database
        # is locked" frames under "During handling of the above exception" — the top one
        # the real refusal, the bottom one an expected, already-handled event that reads
        # exactly like an unhandled crash.
        assert refusal.value.__context__ is None
        assert refusal.value.__cause__ is None
    finally:
        conn.close()


def test_a_lock_held_past_the_busy_timeout_refuses_with_nothing_written(
    tmp_path: Path,
) -> None:
    """The other shape of the same refusal: the WAIT ITSELF cannot take the lock.

    No double here at all — a second connection holds a real ``BEGIN EXCLUSIVE`` on a
    brand-new file and the store's connection is given ``timeout=0``, so both the PRAGMA
    and the ``BEGIN IMMEDIATE`` that waits for it lose immediately. The file must be left
    exactly as it was found (no tables, no WAL sidecars), so the next open is a clean
    creation — which the tail of this test then performs.
    """
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
        # The sidecar half of "untouched" — asserted, not merely claimed. A switch that
        # got far enough to create -wal/-shm and then failed would leave the next open
        # reading a file whose header and sidecars disagree.
        assert not path.with_name(path.name + "-wal").exists()
        assert not path.with_name(path.name + "-shm").exists()

        # And once the lock is gone, the very same connection switches cleanly.
        enable_wal_journal(conn)
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()
        holder.close()


def test_a_journal_mode_that_is_not_wal_refuses() -> None:
    """A switch sqlite REFUSES is reported by its return value, and must not pass silently.

    RED before #823: the return value was never read, so a store that stayed on another
    journal mode opened anyway — with ``synchronous=FULL`` set on a rollback journal,
    which is not the durability shape this package's crash arguments assume.

    An in-RAM connection is the deterministic, unfaked instance of that: sqlite answers
    the switch with ``memory``, no error.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None)
    try:
        with pytest.raises(StoreJournalModeRefused, match="'memory'"):
            enable_wal_journal(conn)
    finally:
        conn.close()


def test_an_operational_error_that_is_not_a_lock_is_not_retried(tmp_path: Path) -> None:
    """Only a lock contest earns the wait; anything else surfaces from the first attempt.

    RED on the "retry every ``OperationalError``" mutation: that version takes the wait
    and calls the PRAGMA a second time, so the log grows past one entry. The error
    reaching the caller is the same either way, which is exactly why the log is the
    assertion.
    """
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
    """A store file that may not be written raises the SAME error, at the SAME attempt.

    Review F2 on PR #827 read this as a regression — that a readable-but-not-switchable
    store was refused where it used to read back fine. Measured on both trees, it is
    not: ``PRAGMA journal_mode=WAL`` on a read-only rollback-journal file raises
    ``attempt to write a readonly database`` (``SQLITE_READONLY``, primary code 8), and
    the pre-#823 constructor did not catch it either — it died at the same statement,
    before ``synchronous=FULL`` and the schema, which both go on to succeed there. What
    #823 changed on that path is nothing, and this pins it:

    * the error is NOT a lock contest, so it is re-raised from the FIRST attempt (the
      log is the evidence — no ``BEGIN IMMEDIATE``, no second PRAGMA);
    * it is an ``OperationalError``, never the new :class:`StoreJournalModeRefused`, so a
      caller that distinguishes "cannot write this file" from "this file did not end up
      in WAL" still can.

    Reading such a file is still possible for a caller that opens it read-only; that is
    a different constructor than this one, and #823 did not add it.
    """
    conn = _scripted(tmp_path / "store.sqlite3", [_capture_readonly_error(tmp_path)])
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly") as refusal:
            enable_wal_journal(conn)

        assert not isinstance(refusal.value, StoreJournalModeRefused)
        assert conn.log == [_WAL_PRAGMA]
    finally:
        conn.close()


def test_an_extended_busy_code_is_still_a_lock_contest(tmp_path: Path) -> None:
    """``SQLITE_BUSY_SNAPSHOT`` (517) must take the wait, exactly like plain ``SQLITE_BUSY`` (5).

    RED on a discriminator that compares ``sqlite_errorname`` to the literal
    ``"SQLITE_BUSY"`` — the first cut of the runtime's sibling helper did exactly that.
    Python reports the EXTENDED name, so every ``SQLITE_BUSY_*`` variant falls into the
    "not a lock contest, re-raise" branch and skips the wait the helper exists for. The
    variant that makes this a real defect rather than a tidiness point is
    ``SQLITE_BUSY_RECOVERY``: a late opener whose PRAGMA meets the winner's WAL recovery
    gets it, which is precisely a birth race. This test uses ``SQLITE_BUSY_SNAPSHOT``
    instead only because that one is reproducible on demand — same primary code, same
    branch, and it is a real sqlite error object, not a fabricated one.
    """
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
    """The masking cuts the other way too: ``SQLITE_LOCKED`` (primary 6) is NOT retried.

    Guards the extended-code fix from overshooting into "anything whose message says
    locked". ``SQLITE_LOCKED`` means a table lock inside one connection handle, which no
    amount of waiting on another party resolves.

    **This error object is FABRICATED** — unlike every other double in this module.
    sqlite does not produce ``SQLITE_LOCKED`` in a hermetic single-connection test, so
    the test constructs an ``OperationalError`` and sets the two attributes the helper
    reads, taking the extended high bits from a real capture so the shape is right.
    Sound here and only here: the assertion is that the helper does NOT retry, and no
    property of a fabricated object can turn a missing retry into a passing test.
    """
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


# -- the call site -----------------------------------------------------------------------------


def test_the_store_still_boots_into_wal_through_the_helper(tmp_path: Path) -> None:
    """The real constructor still leaves its own file in WAL after the rewiring.

    The helper is only worth anything where it is actually wired in; this is the
    call-site half of that claim, checked through a SECOND, read-only connection so it
    reads the file's own header property rather than the constructing handle's view of
    it. ``synchronous`` is read on the constructing handle instead — it is a
    per-connection setting, not a file property, so a read-only probe would report its
    own default and say nothing about the store.
    """
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
    """A constructor that refuses must not leave its sqlite connection open.

    :class:`~tos.staterestore.store.CompositeStateStore` assigns ``self._conn`` and only
    then reaches code that can refuse — the WAL switch this change added two new raise
    paths to. Nothing closed it on that path before. CPython's refcounting does not save
    it either: the raising frame is held by the exception's traceback, so the connection
    and its ``-wal`` / ``-shm`` handles live exactly as long as the caller keeps the
    exception, which for a caller that catches and logs is unbounded.

    The refusal is provoked by a second connection holding ``BEGIN EXCLUSIVE`` on a
    brand-new file. The store takes no timeout argument, so it would otherwise sit
    through two 5 s stdlib waits; the test therefore patches its OWN ``sqlite3.connect``
    to pass ``timeout=0``. Production code is untouched and the refusal is identical,
    just immediate.

    What is asserted is not the refusal (other tests do that) but the state after it:
    operating on the connection must raise "closed database".
    """
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
    """The ``self._conn`` of the constructor frame that raised ``exc``.

    Reaching into the traceback rather than counting file descriptors makes the
    assertion say the thing it means — THIS connection object is closed — and keeps it
    platform-independent (``/proc/self/fd`` would not run off Linux, and a skip that
    only fires elsewhere is a guard that can quietly stop guarding). It is also the
    honest way to test the property at all: a constructor that raises hands its instance
    to nobody, so the traceback is the only reference.
    """
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
