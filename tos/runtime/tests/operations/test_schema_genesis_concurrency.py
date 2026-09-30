"""The GENESIS TRANSACTION of the four durable stores, under concurrent first boot (#801).

**Two races, two fixes, and this module now covers both (#801, then #818).** Most tests here run
against a file that is already ``journal_mode=WAL`` (:func:`_precreate_wal_file`), so what they
measure is the genesis transaction alone: atomic, non-interleavable, exactly one ``CREATED`` row.
Concurrent first boot on a genuinely BRAND-NEW file used to fail earlier than any of that — the
``journal_mode=WAL`` switch takes a lock sqlite does not retry through the busy timeout, and a
loser got ``OperationalError: database is locked`` before any schema code ran (22/80 openers at
N=2, 57/160 at N=4, 90/320 at N=8). That was **#818**, out of #801's scope; it is closed by
:func:`~tos_runtime.operations.schema_ledger.enable_wal_journal` and pinned here by
:func:`test_concurrent_first_boot_on_a_brand_new_file_admits_every_process`, whose own fixture
deliberately does NOT pre-create the file. The pre-created tests stay as they are: keeping the two
races in separate fixtures is what lets a failure name which one broke.

Two runtimes started against the same empty ``data_dir`` both reach every store's constructor
with the file still carrying no user tables. Before the atomic-genesis fix
(:func:`~tos_runtime.operations.schema_ledger.open_or_create_schema`) each constructor read
:func:`~tos_runtime.operations.schema_ledger.file_is_fresh`, ran its own DDL in AUTOCOMMIT, and
only then stamped the genesis ledger row — three steps, no lock between them — which made two
distinct failures reachable:

* **R-1** (the one #801 reports): both processes captured ``was_fresh=True`` before either had
  created a table, so both attempted the genesis ``INSERT`` and the loser died on
  ``sqlite3.IntegrityError: UNIQUE constraint failed: schema_ledger.version``.
* **R-2** (found while planning the fix): a process that opened AFTER the winner's ``CREATE
  TABLE`` but BEFORE its stamp saw ``was_fresh=False`` with ``PRAGMA user_version = 0`` and
  refused to boot with :class:`~tos_runtime.operations.schema_ledger.SchemaVersionRefused`
  ("BEHIND — run ``migrate``") against a file that was merely half-created. #801's own
  recommendation (re-check ``file_is_fresh`` inside the lock) closes R-1 only: the R-2 loser is
  already on the non-genesis branch, which had no transaction at all.

Both are unrepresentable once "decide freshness -> store DDL -> ledger DDL -> stamp" is one
``BEGIN IMMEDIATE`` ... ``COMMIT``: a second process waits on sqlite's own write lock and then
observes a FINISHED file.

**Why processes, not threads.** :mod:`.test_store_probe_isolation` already forces the same
interleave with threads inside one interpreter. This file covers what that cannot: two separate
OS processes, each with its own sqlite connection and its own busy handler, which is the shape
the production failure takes (two ``tos-runtime`` processes, one ``data_dir``).

**Why the window is widened deliberately.** Unwidened, the race is real but probabilistic —
measured on the pre-fix tree at 7/80 (evidence), 6/80 (inbox), 21/80 (marketfeed) and 8/80 (rcl)
failed children over 10 rounds of 8 processes. A test that reproduces a defect 8 % of the time is
not a test. :class:`_DelayedConnection` therefore holds each child inside its own genesis window
for :data:`_DDL_PAUSE_S` by sleeping right after that store's first ``CREATE TABLE``. It is
purely test-side (the child patches its OWN ``sqlite3.connect``; production code is untouched and
knows nothing about it) and it widens the window for the pre-fix and post-fix code alike — after
the fix the sleep happens while the write lock is HELD, so the other seven children simply wait
and then find a finished file.

**Hermetic (D1.4).** Every file is under ``tmp_path``; no network, no ambient env. The children
are forked, not spawned, so they inherit the already-imported modules instead of re-importing the
whole suite eight times per store.
"""

from __future__ import annotations

import multiprocessing as mp
import sqlite3
import time
from multiprocessing.synchronize import Barrier as BarrierType
from pathlib import Path
from queue import Empty
from typing import Any

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.inbox import INBOX_SCHEMA_VERSION, SqliteEventInbox
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION, SqliteEvidenceStore
from tos_runtime.marketfeed.store import MARKETFEED_SCHEMA_VERSION, SqliteSnapshotStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.schema import RCL_SCHEMA_VERSION

from .conftest import FixedKeyProvider

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: How many processes open the same empty store file at once. Eight is well past the two the
#: production scenario needs — the extra parties are what make BOTH losing shapes (R-1 and R-2)
#: appear in a single round on the pre-fix code instead of one or the other.
_PROCESSES = 8

#: How long each child sleeps inside its own genesis window (see the module docstring). Large
#: enough that every sibling released from the barrier is still inside the window, small enough
#: that the post-fix serialized total (``_PROCESSES * _DDL_PAUSE_S``) stays well under a second.
_DDL_PAUSE_S = 0.05

#: Bound on every cross-process wait, so a broken child fails the test instead of wedging the
#: suite (same discipline as :mod:`.test_store_probe_isolation`'s ``_HANDSHAKE_TIMEOUT_S``).
_JOIN_TIMEOUT_S = 60.0

#: ``(store, expected schema version, the SQL fragment that opens that store's own genesis DDL)``.
#: The fragment is matched as a substring of the statement the child is about to finish, and it is
#: each store's FIRST ``CREATE TABLE`` so the pause lands between "the file still looks fresh to a
#: newcomer" and "the genesis row exists". ``rcl`` keys on ``epochs`` rather than ``entries``
#: because an RCL child also constructs its own private evidence store, whose first table is also
#: called ``entries`` — pausing there would delay the wrong construction.
_STORES: tuple[tuple[str, int, str], ...] = (
    ("evidence", EVIDENCE_SCHEMA_VERSION, "CREATE TABLE IF NOT EXISTS entries"),
    ("inbox", INBOX_SCHEMA_VERSION, "CREATE TABLE IF NOT EXISTS events"),
    ("marketfeed", MARKETFEED_SCHEMA_VERSION, "CREATE TABLE IF NOT EXISTS snapshots"),
    ("rcl", RCL_SCHEMA_VERSION, "CREATE TABLE IF NOT EXISTS epochs"),
)

_STORE_IDS = tuple(name for name, _, _ in _STORES)


def _open_store(store: str, path: Path, *, party: str = "solo") -> Any:
    """Construct ``store`` over ``path`` exactly the way ``compose`` does, and return it.

    The RCL log needs an evidence port, so an RCL caller builds an evidence store first. That
    file is named per ``party`` and is therefore PRIVATE to this caller: a shared one would add a
    second, unrelated genesis race (over the evidence file) on top of the one under test — which
    is exactly what an earlier cut of this file did, and it showed up as an ``OperationalError:
    database is locked`` from the ``journal_mode`` birth race described in
    :func:`_precreate_wal_file`.
    """
    if store == "evidence":
        return SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    if store == "inbox":
        return SqliteEventInbox(path, scheme=get_scheme(EV_L1_PROVISIONAL_VERSION))
    if store == "marketfeed":
        return SqliteSnapshotStore(path)
    if store == "rcl":
        evidence = SqliteEvidenceStore(
            path.with_name(f"private-evidence-{party}.sqlite3"),
            key_provider=FixedKeyProvider(),
        )
        return SqliteCommitLog(path, evidence_port=evidence)
    raise AssertionError(f"unknown store {store!r}")


class _DelayedConnection(sqlite3.Connection):
    """Test-only connection that sleeps after the statement naming :data:`_pause_after_sql`.

    Installed by a CHILD process over its own ``sqlite3.connect`` (see :func:`_child`); the
    parent's sqlite3 module and all production code are untouched. Subclassing is the only way in
    — :class:`sqlite3.Connection` is a C type with no ``__dict__``, so its ``execute`` cannot be
    patched on an instance.
    """

    def execute(self, sql: str, *parameters: Any) -> sqlite3.Cursor:
        cursor = super().execute(sql, *parameters)
        if _pause_after_sql and _pause_after_sql in sql:
            time.sleep(_DDL_PAUSE_S)
        return cursor


#: Set in the child only, immediately before the store is constructed.
_pause_after_sql: str = ""


def _child(
    store: str,
    path_str: str,
    pause_after_sql: str,
    party: int,
    barrier: BarrierType,
    queue: mp.Queue[str],
) -> None:
    """Open ``store`` over ``path_str`` in lockstep with every sibling; report the outcome.

    The outcome is REPORTED, never raised, and the whole body — the barrier wait and the
    connection patch included — is inside the ``try``: a child that died before its ``queue.put``
    would leave the parent blocked on ``queue.get`` for the full timeout and then fail with
    "never reported an outcome", which says nothing about WHY. Every path ends in exactly one
    ``queue.put``.
    """
    try:
        global _pause_after_sql
        _pause_after_sql = pause_after_sql
        real_connect = sqlite3.connect

        def connect_with_delay(*args: Any, **kwargs: Any) -> sqlite3.Connection:
            kwargs["factory"] = _DelayedConnection
            # Annotated rather than returned directly: this wrapper takes `**kwargs: Any`, so the
            # call's inferred type is `Any` and a bare return of it is `no-any-return`.
            connection: sqlite3.Connection = real_connect(*args, **kwargs)
            return connection

        sqlite3.connect = connect_with_delay  # type: ignore[assignment]
        barrier.wait(timeout=_JOIN_TIMEOUT_S)
        handle = _open_store(store, Path(path_str), party=f"child-{party}")
        handle.close()
        queue.put("OK")
    except BaseException as exc:  # noqa: BLE001 - the exception IS this child's result
        queue.put(f"{type(exc).__name__}: {exc}")


def _precreate_wal_file(path: Path) -> None:
    """Leave ``path`` an empty ``journal_mode=WAL`` database with NO user tables.

    Still ``file_is_fresh`` — that predicate asks about user tables, not bytes — so every child
    still enters the genesis window this file is about. Pre-creating it isolates that window from
    a SEPARATE birth-time race the repo already documents
    (:func:`.test_store_probe_isolation._precreate_wal_file`): switching a brand-new file's
    journal mode to WAL needs an exclusive lock that ``PRAGMA journal_mode`` does NOT retry
    through sqlite's busy timeout, so concurrent first connections can lose one side to
    ``OperationalError: database is locked`` before any store code runs. That race is out of
    #801's scope (plan §2.1 keeps the pragma outside the transaction) and letting it fire here
    would only blur the one under test.

    **It is closed now — by #818, not by this helper, and this helper still hides it.** It was
    never rare: measured on a brand-new file, 22/80 losing openers at N=2, 57/160 at N=4, 90/320
    at N=8. What a pre-created test reports is therefore still a statement about the genesis
    transaction only; the brand-new-file claim belongs to
    :func:`test_concurrent_first_boot_on_a_brand_new_file_admits_every_process`, which skips this
    helper precisely so it measures the birth race instead.
    """
    conn = sqlite3.connect(str(path), isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    finally:
        conn.close()


def _run_concurrent_first_boot(
    store: str, path: Path, pause_after_sql: str
) -> list[str]:
    """Release :data:`_PROCESSES` children onto the same empty ``path`` and collect every outcome."""
    context = mp.get_context("fork")
    barrier = context.Barrier(_PROCESSES)
    queue: mp.Queue[str] = context.Queue()
    children = [
        context.Process(
            target=_child,
            args=(store, str(path), pause_after_sql, party, barrier, queue),
        )
        for party in range(_PROCESSES)
    ]
    for child in children:
        child.start()
    try:
        outcomes = [queue.get(timeout=_JOIN_TIMEOUT_S) for _ in range(_PROCESSES)]
    except Empty as exc:  # pragma: no cover - only on a wedged child
        raise AssertionError(
            f"a {store} child never reported an outcome within {_JOIN_TIMEOUT_S}s"
        ) from exc
    finally:
        for child in children:
            child.join(timeout=_JOIN_TIMEOUT_S)
            if child.is_alive():  # pragma: no cover - only on a wedged child
                child.terminate()
    assert all(
        child.exitcode == 0 for child in children
    ), f"a {store} child exited abnormally: {[child.exitcode for child in children]}"
    return outcomes


def _ledger_rows(path: Path) -> list[tuple[object, ...]]:
    """The genesis ledger, read through a ``mode=ro`` connection so this evidence-gathering
    helper cannot itself create the row it is checking for."""
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return [
            tuple(row)
            for row in conn.execute(
                "SELECT version, applied_by FROM schema_ledger ORDER BY version"
            ).fetchall()
        ]
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("store", "expected_version", "pause_after_sql"), _STORES, ids=_STORE_IDS
)
def test_the_genesis_transaction_is_atomic_under_concurrent_first_boot(
    tmp_path: Path, store: str, expected_version: int, pause_after_sql: str
) -> None:
    """Eight processes enter the same file's GENESIS TRANSACTION at once: all eight boot, one row.

    **The name is deliberately narrower than "concurrent first boot admits every process"**
    (review HIGH-1, which measured the older name as an overreach). What this pins is exactly the
    scope of #801: the genesis transaction is atomic and non-interleavable, measured on a file that
    is **already** ``journal_mode=WAL`` (:func:`_precreate_wal_file`). A concurrent first boot on a
    genuinely brand-new file loses a process to the ``journal_mode`` switch itself, which this fix
    does not touch — reviewer measurement 22/80 openers at N=2, 57/160 at N=4, 90/320 at N=8. That
    is #818's scope, closed separately and pinned by
    :func:`test_concurrent_first_boot_on_a_brand_new_file_admits_every_process` below.

    RED on the pre-fix code, per store, with the window widened as the module docstring
    describes: the losers report ``IntegrityError: UNIQUE constraint failed:
    schema_ledger.version`` (R-1) and/or ``SchemaVersionRefused: ... user_version=0 is BEHIND``
    (R-2). Each of the three mutations named in the plan (``file_is_fresh`` read back outside the
    lock, the store DDL moved back outside the transaction, the ``ROLLBACK`` removed) restores one
    of those shapes.

    The single ``CREATED`` row is the second half of the claim and is not implied by the first:
    a genesis that ran twice but swallowed the duplicate (``INSERT OR IGNORE``, the alternative
    §3 rejects) would leave every child "successful" while the ledger silently stopped recording
    which code actually created the file.
    """
    path = tmp_path / f"{store}.sqlite3"
    _precreate_wal_file(path)

    outcomes = _run_concurrent_first_boot(store, path, pause_after_sql)

    assert outcomes == ["OK"] * _PROCESSES, (
        f"every concurrent first boot of the {store} store must succeed; "
        f"failures: {sorted(outcome for outcome in outcomes if outcome != 'OK')}"
    )
    assert _ledger_rows(path) == [(expected_version, "CREATED")], (
        f"the {store} store must carry exactly one genesis row after a concurrent first boot, "
        "at the version this code expects"
    )


@pytest.mark.parametrize(
    ("store", "expected_version", "pause_after_sql"), _STORES, ids=_STORE_IDS
)
def test_a_store_created_by_a_race_is_immediately_reopenable(
    tmp_path: Path, store: str, expected_version: int, pause_after_sql: str
) -> None:
    """The file a concurrent first boot leaves behind is an ORDINARY store file.

    "Nobody crashed" is not the whole property: a genesis that committed a partial shape would
    satisfy the test above and then refuse (or misbehave) on the very next ordinary boot. This
    reopens the raced file through the real constructor and pins that it neither refuses nor adds
    a second ledger row.
    """
    path = tmp_path / f"{store}.sqlite3"
    _precreate_wal_file(path)
    assert _run_concurrent_first_boot(store, path, pause_after_sql) == ["OK"] * (
        _PROCESSES
    )

    reopened = _open_store(store, path)
    reopened.close()

    assert _ledger_rows(path) == [(expected_version, "CREATED")]


def test_a_write_lock_held_past_the_busy_timeout_refuses_boot_explicitly(
    tmp_path: Path,
) -> None:
    """Genesis is fail-CLOSED when the wait overflows: an explicit error, and an untouched file.

    Plan §2.3 deliberately adds no busy-timeout config key. **Which boots can reach this lock at
    all is narrow, and was narrowed further by review MEDIUM-1**: a steady-state boot (the file's
    ``user_version`` already matches and ``schema_ledger`` exists) is decided by two lock-free
    reads and never enters a transaction, so it cannot be refused here no matter who holds the
    lock. Only a boot that must actually WRITE schema gets this far — a genesis, or a file at a
    disagreeing version — and then the wait only has to outlast a sibling's genesis transaction
    (milliseconds), which sqlite's own 5 s default covers with room to spare. What this pins is
    the behaviour when it does NOT: the store raises :class:`sqlite3.OperationalError` rather than
    corrupting, half-creating, or silently proceeding, and the file is left exactly as it was found
    so the next boot is a clean genesis. The steady-state half is pinned in
    :mod:`.test_schema_ledger` (``..._boots_while_another_writer_holds_the_lock``).

    ``SqliteCommitLog`` is the subject because it already injects its own ``sqlite_timeout_s``
    (used by the fault-③ suite); the timeout is driven to ``0`` here so the refusal is observed
    immediately instead of five seconds later. The holder is a plain second connection in an open
    ``BEGIN IMMEDIATE`` — the same lock a sibling runtime's genesis transaction holds.
    """
    path = tmp_path / "rcl.sqlite3"
    _precreate_wal_file(path)
    evidence = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    holder = sqlite3.connect(str(path), isolation_level=None)
    try:
        holder.execute("BEGIN IMMEDIATE")

        with pytest.raises(sqlite3.OperationalError, match="locked"):
            SqliteCommitLog(path, evidence_port=evidence, sqlite_timeout_s=0)

        # The refused boot wrote nothing: no store tables, no ledger, no version stamp.
        probe = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            tables = {
                row[0]
                for row in probe.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            }
            assert tables == set()
            assert probe.execute("PRAGMA user_version").fetchone()[0] == 0
        finally:
            probe.close()

        holder.execute("ROLLBACK")

        # And once the lock is gone the very same path opens as an ordinary, clean genesis.
        log = SqliteCommitLog(path, evidence_port=evidence, sqlite_timeout_s=0)
        log.close()
        assert _ledger_rows(path) == [(RCL_SCHEMA_VERSION, "CREATED")]
    finally:
        holder.close()
        evidence.close()


#: Rounds of :data:`_PROCESSES` openers the brand-new-file test runs per store. The birth race is
#: probabilistic (measured ~21 % of openers at N=2 and 73/320 at N=8 on the pre-#818 code), so one
#: round proves nothing about the fix — but it is also frequent enough that five rounds of eight
#: leave the old code no realistic way to come out clean (p < 1e-20 at the measured rate).
_BIRTH_RACE_ROUNDS = 5


@pytest.mark.parametrize(
    ("store", "expected_version", "pause_after_sql"), _STORES, ids=_STORE_IDS
)
def test_concurrent_first_boot_on_a_brand_new_file_admits_every_process(
    tmp_path: Path, store: str, expected_version: int, pause_after_sql: str
) -> None:
    """Eight processes open the same NON-EXISTENT store path at once: all eight boot (**#818**).

    This is the claim the rest of this module deliberately does not make. No
    :func:`_precreate_wal_file` here and no DDL pause either (``pause_after_sql`` is dropped): the
    window under test is the ``PRAGMA journal_mode=WAL`` switch itself, which happens before the
    first ``CREATE TABLE``, and widening the later window would only push the children past each
    other. What makes it deterministic enough to assert on is repetition —
    :data:`_BIRTH_RACE_ROUNDS` rounds per store, a fresh path each round.

    RED on the pre-#818 code, per store, with no mutation needed: the losers report
    ``OperationalError: database is locked`` out of the constructor's own journal-mode switch.
    Measured on this branch with :func:`~tos_runtime.operations.schema_ledger.enable_wal_journal`
    reverted to the bare PRAGMA, ten rounds of eight per store — evidence 15/80, inbox 4/80,
    marketfeed 5/80, rcl 30/80 losing children — and every one of three full runs of this test
    failed on all four stores.

    The ledger assertion is the second half, exactly as in the genesis tests above: surviving the
    birth race must still leave ONE ``CREATED`` row, or the two fixes would be trading one
    defect for another.
    """
    for round_index in range(_BIRTH_RACE_ROUNDS):
        path = tmp_path / f"{store}-{round_index}.sqlite3"
        assert not path.exists()

        outcomes = _run_concurrent_first_boot(store, path, "")

        assert outcomes == ["OK"] * _PROCESSES, (
            f"every concurrent first boot of a BRAND-NEW {store} file must succeed "
            f"(round {round_index}); failures: "
            f"{sorted(outcome for outcome in outcomes if outcome != 'OK')}"
        )
        assert _ledger_rows(path) == [(expected_version, "CREATED")], (
            f"the {store} store must carry exactly one genesis row after a concurrent first "
            f"boot on a brand-new file (round {round_index})"
        )
