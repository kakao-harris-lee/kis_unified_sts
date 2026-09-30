"""The WAL birth race on a brand-new store file (**#818**,
``docs/plans/2026-09-30-tos-wal-birth-race-plan.md``).

:func:`~tos_runtime.operations.schema_ledger.enable_wal_journal` is what every durable store now
calls instead of a bare ``PRAGMA journal_mode=WAL``. What it has to survive is narrow and easy to
state: switching a never-yet-WAL file to WAL takes an exclusive lock, and that PRAGMA does **not**
go through sqlite's busy handler, so a concurrent first boot loses one side outright with
``sqlite3.OperationalError: database is locked``. The cross-PROCESS proof that the fix closes it
lives next door in :mod:`.test_schema_genesis_concurrency` (the brand-new-file case); this module
pins the helper's own edges, deterministically and without a race:

* a lock lost once is waited out and the switch retried (and it is a REAL wait — the
  ``BEGIN IMMEDIATE``/``ROLLBACK`` pair is observed, not assumed);
* a lock still held after that wait refuses the boot, in both shapes it can take, leaving the
  file and its sidecars untouched;
* a journal mode that comes back as anything but ``wal`` refuses the boot — sqlite reports a
  refused switch by RETURNING the mode it kept, never by raising, and the pre-#818 code did not
  look at the answer at all;
* an ``OperationalError`` that is not a lock contest is re-raised on the FIRST attempt, never
  retried — while EVERY ``SQLITE_BUSY_*`` extended code still counts as one (review F2).

**Every sqlite error used here is a real one.** The doubles below replay
:class:`sqlite3.OperationalError` instances captured from genuine sqlite operations — an exclusive
lock held by a second connection, a stale WAL snapshot, a select against a missing table — because
the helper discriminates on ``sqlite_errorcode``, and a hand-built
``OperationalError("database is locked")`` carries no such attribute at all (measured). A test
that fabricated one would be exercising a different object than production ever sees. The single
exception is the ``SQLITE_LOCKED`` case, which re-labels a captured real error rather than
inventing one, because sqlite will not hand out that code on demand here.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from tos_runtime.operations.schema_ledger import JournalModeRefused, enable_wal_journal

from .conftest import FixedKeyProvider

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_WAL_PRAGMA = "PRAGMA journal_mode=WAL"


# -- real captured sqlite errors --------------------------------------------------------------


def _capture_locked_error(tmp_path: Path) -> sqlite3.OperationalError:
    """A genuine ``SQLITE_BUSY`` ``OperationalError``, taken from a real lock contest.

    Captured rather than constructed: ``sqlite3.OperationalError("database is locked")`` built by
    hand has no ``sqlite_errorname`` at all (measured), so it is not the object the helper's
    discriminator sees in production.
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

    sqlite raises this when a connection that already holds a read snapshot tries to write after
    the WAL moved past it. It is not the variant the birth race produces (that is
    ``SQLITE_BUSY_RECOVERY``, which needs a recovery window too narrow to force deterministically)
    but it is the same thing that matters here: ``sqlite_errorname`` carries the EXTENDED name and
    ``sqlite_errorcode`` is ``517``, whose low byte is ``SQLITE_BUSY``. Anything that discriminates
    on the name fails this; anything that masks the code passes it.
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
    """A REAL connection on a real file, whose :data:`_WAL_PRAGMA` raises scripted errors first.

    Everything else — ``BEGIN IMMEDIATE``, ``ROLLBACK``, the retried PRAGMA — runs against sqlite
    for real, so the wait this module claims to observe is the production wait and not a stub.
    Subclassing is the only way in (``sqlite3.Connection`` is a C type whose ``execute`` cannot be
    patched per instance — see :class:`.test_schema_genesis_concurrency._DelayedConnection`); a
    python subclass does get a ``__dict__``, so the script and the log are per-instance.
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


# -- the four edges -----------------------------------------------------------------------------


def test_a_lock_lost_once_is_waited_out_and_the_switch_retried(tmp_path: Path) -> None:
    """The losing side waits on sqlite's OWN busy handler and then switches successfully.

    RED before #818: the bare ``PRAGMA journal_mode=WAL`` had no retry at all, so the captured
    ``SQLITE_BUSY`` escaped the constructor and the file stayed on the rollback journal.

    The statement log is the load-bearing half. "The file ended up in WAL" alone would also pass
    if the helper had swallowed the error and the file happened to be WAL already; what pins the
    mechanism is that ``BEGIN IMMEDIATE``/``ROLLBACK`` — the wait, and the ONLY thing in this
    code that waits — actually ran, between two PRAGMA attempts.
    """
    conn = _scripted(tmp_path / "store.sqlite3", [_capture_locked_error(tmp_path)])
    try:
        enable_wal_journal(conn)

        assert conn.log == [_WAL_PRAGMA, "BEGIN IMMEDIATE", "ROLLBACK", _WAL_PRAGMA]
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_a_lock_still_held_when_the_retry_runs_refuses_the_boot(tmp_path: Path) -> None:
    """Two losses in a row is a boot refusal, not a third attempt.

    The retry is deliberately ONE attempt (plan §2.1): a second failure means nobody released the
    lock for the whole of this connection's busy timeout, and hammering it would only turn a
    fail-closed refusal into an unbounded stall. The log pins the count — exactly two PRAGMA
    attempts, one wait, and no third try.
    """
    errors = [_capture_locked_error(tmp_path), _capture_locked_error(tmp_path)]
    conn = _scripted(tmp_path / "store.sqlite3", errors)
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            enable_wal_journal(conn)

        assert conn.log == [_WAL_PRAGMA, "BEGIN IMMEDIATE", "ROLLBACK", _WAL_PRAGMA]
    finally:
        conn.close()


def test_a_lock_held_past_the_busy_timeout_refuses_the_boot_with_nothing_written(
    tmp_path: Path,
) -> None:
    """The other shape of the same refusal: the WAIT ITSELF cannot take the lock (plan T-4).

    No double here at all — a second connection holds a real ``BEGIN EXCLUSIVE`` on a brand-new
    file and the store's connection is given ``timeout=0``, so both the PRAGMA and the
    ``BEGIN IMMEDIATE`` that waits for it lose immediately. The file must be left exactly as it
    was found (no tables, no WAL sidecars), so the next boot is a clean genesis — which the tail
    of this test then performs.
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
        # The sidecar half of "untouched" — asserted, not merely claimed (review F5). A switch
        # that got far enough to create -wal/-shm and then failed would leave the next boot
        # reading a file whose header and sidecars disagree.
        assert not path.with_name(path.name + "-wal").exists()
        assert not path.with_name(path.name + "-shm").exists()

        # And once the lock is gone, the very same connection switches cleanly.
        enable_wal_journal(conn)
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()
        holder.close()


def test_a_journal_mode_that_is_not_wal_refuses_the_boot() -> None:
    """A switch sqlite REFUSES is reported by its return value, and must not pass silently.

    RED before #818: the return value was never read, so a store that stayed on another journal
    mode booted anyway — with ``synchronous=FULL`` set on a rollback journal, which is not the
    durability shape any of these stores' crash arguments assume.

    ``:memory:`` is the deterministic, unfaked instance of that: sqlite answers the switch with
    ``memory``, no error.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None)
    try:
        with pytest.raises(JournalModeRefused, match="'memory'"):
            enable_wal_journal(conn)
    finally:
        conn.close()


def test_an_operational_error_that_is_not_a_lock_is_not_retried(tmp_path: Path) -> None:
    """Only a lock contest earns the wait; anything else surfaces from the first attempt.

    RED on the "retry every ``OperationalError``" mutation named in the plan: that version takes
    the wait and calls the PRAGMA a second time, so the log grows past one entry. The error
    reaching the caller is the same either way, which is exactly why the log is the assertion.
    """
    conn = _scripted(tmp_path / "store.sqlite3", [_capture_non_lock_error()])
    try:
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            enable_wal_journal(conn)

        assert conn.log == [_WAL_PRAGMA]
    finally:
        conn.close()


def test_an_extended_busy_code_is_still_a_lock_contest(tmp_path: Path) -> None:
    """``SQLITE_BUSY_SNAPSHOT`` (517) must take the wait, exactly like plain ``SQLITE_BUSY`` (5).

    RED on the first cut of #818, which compared ``sqlite_errorname`` to the literal
    ``"SQLITE_BUSY"``. Python reports the EXTENDED name, so every ``SQLITE_BUSY_*`` variant fell
    into the "not a lock contest, re-raise" branch and skipped the wait the helper exists for. The
    variant that makes this a real defect rather than a tidiness point is
    ``SQLITE_BUSY_RECOVERY``: a late opener whose PRAGMA meets the winner's WAL recovery gets it,
    which is precisely a birth race. This test uses ``SQLITE_BUSY_SNAPSHOT`` instead only because
    that one is reproducible on demand (:func:`_capture_extended_busy_error`) — same primary code,
    same branch, and it is a real sqlite error object, not a fabricated one.
    """
    conn = _scripted(
        tmp_path / "store.sqlite3", [_capture_extended_busy_error(tmp_path)]
    )
    try:
        enable_wal_journal(conn)

        assert conn.log == [_WAL_PRAGMA, "BEGIN IMMEDIATE", "ROLLBACK", _WAL_PRAGMA]
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_a_locked_table_is_not_treated_as_a_lock_contest(tmp_path: Path) -> None:
    """The masking cuts the other way too: ``SQLITE_LOCKED`` (primary 6) is NOT retried.

    Guards the fix for the extended-code defect from overshooting into "anything whose message
    says locked". ``SQLITE_LOCKED`` means a table lock inside one connection handle, which no
    amount of waiting on another party resolves. Built by masking the real
    ``SQLITE_BUSY_SNAPSHOT`` capture's primary code up to 6, so the object is still a genuine
    sqlite exception and only the code under test differs.
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


def test_every_durable_store_boots_into_wal_through_the_helper(tmp_path: Path) -> None:
    """The four real constructors still leave their own file in WAL after the rewiring (T-2).

    The helper is only worth anything where it is actually wired in; this is the call-site half
    of that claim, checked through a SECOND, read-only connection so it reads the file's own
    header property rather than the constructing handle's view of it.
    """
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
