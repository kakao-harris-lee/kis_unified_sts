"""The probe-isolation regression suite for ``test_run_e2e.py``'s tick probe (review-797;
one observed CI failure on PR #797).

**The defect.** ``test_cli_main_run_argv_path_composes_and_actually_ticks`` polls the durable
snapshot store from a sender thread while ``cli.main(["run", ...])`` composes the runtime in the
main thread. That probe used to CONSTRUCT a
:class:`~tos_runtime.marketfeed.store.SqliteSnapshotStore` over the compose-owned file the moment
the file appeared. That constructor is a writer: it captures
:func:`~tos_runtime.operations.schema_ledger.file_is_fresh`, runs three ``CREATE TABLE``/
``CREATE INDEX`` statements, and calls
:func:`~tos_runtime.operations.schema_ledger.ensure_schema_current`, which on a ``was_fresh=True``
file stamps ``PRAGMA user_version`` and ``INSERT``s the genesis ``schema_ledger`` row
(``schema_ledger.py:167-181``). With both parties opening a still-fresh file, BOTH observe
``was_fresh=True`` and both attempt that ``INSERT``; the loser dies on
``sqlite3.IntegrityError: UNIQUE constraint failed: schema_ledger.version``, which in CI surfaced
as ``run: refused — compose_paper_runtime raised IntegrityError: ...`` and a red
``assert exit_code == 0``.

**Why these tests, and not a loop.** The production failure needs the probe to open the file
inside the microsecond-wide window between compose's ``sqlite3.connect`` and its first committed
``CREATE TABLE`` — measured here at 2 failures in 30 runs of the real e2e test, i.e. exactly the
kind of "passes locally, reds once in CI" flake a repeat-until-it-happens test cannot pin. The
first two tests below therefore FORCE that interleave with a monkeypatched ``file_is_fresh``
that blocks at the genesis decision point, so the race is reproduced by construction rather than
by timing luck. Every test names a mutation it turns red:

* :func:`test_two_concurrent_store_constructions_on_a_fresh_file_lose_the_genesis_race` pins the
  MECHANISM — the old probe pattern, deterministically raising the exact CI error.
* :func:`test_the_read_only_probe_cannot_disturb_a_store_mid_genesis` pins the FIX — the real
  helper ``test_run_e2e.read_only_latest_as_of``, run inside that same window, leaves the file
  byte-identical, lets the paused construction finish, and leaves exactly ONE genesis ledger row.
  Restoring the old store-constructing probe in that helper turns this test red — on the byte
  diff, which is the assertion that fires first; the ``IntegrityError`` assertion behind it
  detects the same mutation independently (see that test's own docstring for the measurement).

The remaining four pin the probe's own contract, which is what makes it a usable substitute for
the store — a probe that never wrote because it never read anything would satisfy the two above:

* :func:`test_the_read_only_probe_reports_a_committed_tick_without_writing` — it really does read
  a committed row, through a second connection, while the writer is still open.
* :func:`test_the_read_only_probe_answers_exactly_what_the_store_answers` — its SQL MEANS what
  ``SqliteSnapshotStore.latest_as_of`` means, checked against the live store over rows inserted
  out of ``as_of_ms`` order and across two instruments. Keying the probe on insertion order
  (``ORDER BY rowid DESC LIMIT 1``) or dropping its ``WHERE instrument = ?`` turns this red.
* :func:`test_the_read_only_probe_is_total_over_every_half_created_file_state` — every
  mid-creation state answers ``None`` instead of raising into the sender thread. Narrowing the
  helper's ``except sqlite3.Error`` back to ``OperationalError`` turns this red.
* :func:`test_the_read_only_probe_handles_a_uri_special_character_in_the_path` — the ``mode=ro``
  URI is built with ``Path.as_uri()``. Replacing it with string interpolation turns this red.

Hermetic (D1.4): every file lives under ``tmp_path``; no network, no ambient env.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from tos_runtime.marketfeed import store as store_module
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME, SqliteSnapshotStore

from . import _fixtures as fx
from .test_run_e2e import read_only_latest_as_of

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: Every blocking handshake below is bounded — a broken patch must fail the test, never wedge the
#: suite (the same discipline ``test_run_e2e.py``'s own sender thread follows).
#:
#: The bound alone does not buy that claim, which is why every helper thread here is also
#: ``daemon=True`` (review-800 LOW-3). A bounded ``join`` lets the MAIN thread stop waiting and
#: fail the assert, but a non-daemon worker that outlived it would still block interpreter exit
#: at the end of the pytest session — a hang, after a green-looking failure, with no traceback
#: pointing here. Today every wait in these helpers is itself bounded (``Barrier(timeout=...)``,
#: ``Event.wait(timeout=...)``) so they do terminate; ``daemon=True`` is what keeps "never wedge
#: the suite" true if a future edit adds a wait that is not. Same flag, same reason, as
#: ``test_run_e2e.py``'s sender thread.
_HANDSHAKE_TIMEOUT_S = 10.0

#: The shape of :func:`~tos_runtime.operations.schema_ledger.file_is_fresh`, which both tests
#: below monkeypatch on :mod:`tos_runtime.marketfeed.store` to pin the genesis interleave.
_FreshPredicate = Callable[[sqlite3.Connection], bool]

#: How many times the read-only probe is run inside the paused genesis window. One call would
#: already prove "does not raise"; a burst also proves the file is unchanged by REPEATED probing,
#: which is what the real sender thread does (one call per 5ms until it sees a tick).
_PROBE_BURST = 50

#: A second ``snapshots.instrument`` value, so the equivalence test can prove the probe's
#: ``WHERE instrument = ?`` actually bounds the query. Any string distinct from
#: ``fx.INSTRUMENT`` works — this column is free text the store never interprets.
_OTHER_INSTRUMENT = "NQ"


#: The files that carry durable database CONTENT in WAL mode: the database itself and its
#: write-ahead log (every write lands in the ``-wal`` until a checkpoint moves it into the
#: database file, so a probe that created a table or inserted a row changes one of these two).
#:
#: ``-shm`` is deliberately NOT here. It is sqlite's shared-memory index into the ``-wal``: it
#: holds no database content, sqlite rebuilds it from the ``-wal`` whenever it is missing, and
#: EVERY reader mutates its read marks — including
#: :meth:`~tos_runtime.marketfeed.store.SqliteSnapshotStore.latest_as_of`, the in-process read
#: this probe replaces. Asserting on it would not be asserting "the probe does not write", it
#: would be asserting "nothing reads", which no probe of any shape can satisfy. (Measured: the
#: probe below leaves the database file and the ``-wal`` byte-identical and changes only ``-shm``
#: read marks.)
_CONTENT_FILE_SUFFIXES = ("", "-wal")


def _file_state(db_path: Path) -> dict[str, bytes | None]:
    """Every byte of durable database content for ``db_path`` (:data:`_CONTENT_FILE_SUFFIXES`).

    ``None`` for a file that does not exist, so a file APPEARING counts as a change too — that is
    how a probe that creates the database out of thin air gets caught, not just one that edits an
    existing database.
    """
    return {
        suffix: (
            (db_path.parent / f"{db_path.name}{suffix}").read_bytes()
            if (db_path.parent / f"{db_path.name}{suffix}").exists()
            else None
        )
        for suffix in _CONTENT_FILE_SUFFIXES
    }


def _insert_snapshot_row(
    store: SqliteSnapshotStore, *, as_of_ms: int, instrument: str = fx.INSTRUMENT
) -> None:
    """Commit one ``snapshots`` row through ``store``'s own live connection.

    Writes the columns directly rather than going through :meth:`SqliteSnapshotStore.put`
    because ``put`` needs a fully issued :class:`~tos.capsule.CriticalInputSnapshot` plus its
    preimages, none of which this file's subject (the READ path) depends on — the probe reads
    ``instrument``/``as_of_ms``, and those are what this row has to carry. Reaching for the
    private connection matches the local idiom (``test_run_e2e.py`` reads
    ``runtime.marketfeed._store``).
    """
    store._conn.execute("BEGIN IMMEDIATE")
    store._conn.execute(
        "INSERT INTO snapshots "
        "(snapshot_id, canonical_digest, instrument, as_of_ms, snapshot_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (f"snap-{instrument}-{as_of_ms}", "digest-1", instrument, as_of_ms, "{}"),
    )
    store._conn.execute("COMMIT")


def _precreate_wal_file(db_path: Path) -> None:
    """Create ``db_path`` as an empty ``journal_mode=WAL`` database with no user tables — the
    state compose leaves behind the instant before its own genesis DDL, and the state a probe
    joining the race actually finds. Still ``file_is_fresh`` (no user tables)."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    finally:
        conn.close()


def _schema_ledger_rows(db_path: Path) -> list[tuple[object, ...]]:
    """The store's genesis ledger, read the same structurally read-only way the probe under
    test reads snapshots — so this evidence-gathering helper cannot itself write the row it is
    checking for."""
    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return [
            tuple(row)
            for row in conn.execute(
                "SELECT version, applied_by FROM schema_ledger ORDER BY version"
            ).fetchall()
        ]
    finally:
        conn.close()


def test_two_concurrent_store_constructions_on_a_fresh_file_lose_the_genesis_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The OLD probe pattern, deterministically: two ``SqliteSnapshotStore(path)`` constructions
    that both observe ``was_fresh=True`` on the same file, and the exact error CI reported.

    The interleave is forced, not raced: a 2-party :class:`threading.Barrier` inside the patched
    ``file_is_fresh`` holds each construction at its own genesis decision — after it has answered
    "is this file fresh?" and before EITHER has run a ``CREATE TABLE`` that would make the answer
    ``False`` for the other. That is precisely the window compose and the old probe both entered
    in CI; here neither party can leave it early, so the outcome does not depend on timing.

    The file is pre-created in WAL mode first, which is also the real sequence (compose connects
    and sets ``journal_mode`` before the probe ever sees the path, so the probe's own
    ``PRAGMA journal_mode=WAL`` is a no-op) — an empty WAL file is still ``file_is_fresh`` because
    that predicate asks about USER TABLES, not about bytes (``schema_ledger.py:98-105``), so both
    parties still enter the genesis window. Without it the two constructions can instead collide
    on the ``journal_mode`` PRAGMA itself, which does not honour sqlite's busy timeout and fails
    one side with ``OperationalError: database is locked`` before it ever reaches the barrier —
    a different (and here merely noisy) race that would stop this test from pinning the one it
    is named for.
    """
    db_path = tmp_path / MARKETFEED_FILE_NAME
    _precreate_wal_file(db_path)
    barrier = threading.Barrier(2, timeout=_HANDSHAKE_TIMEOUT_S)
    real_file_is_fresh: _FreshPredicate = store_module.file_is_fresh

    def _barriered_file_is_fresh(conn: sqlite3.Connection) -> bool:
        fresh = real_file_is_fresh(conn)
        barrier.wait()
        return fresh

    monkeypatch.setattr(store_module, "file_is_fresh", _barriered_file_is_fresh)

    outcomes: dict[str, BaseException | None] = {}

    def _construct(name: str) -> None:
        try:
            store = SqliteSnapshotStore(db_path)
            store.close()
            outcomes[name] = None
        except BaseException as exc:  # noqa: BLE001 - the exception IS the outcome
            outcomes[name] = exc

    names = ("first", "second")
    threads = [
        threading.Thread(target=_construct, args=(name,), daemon=True) for name in names
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=_HANDSHAKE_TIMEOUT_S * 2)
        assert not thread.is_alive(), "a construction thread never finished"

    raised = [exc for exc in outcomes.values() if exc is not None]
    assert len(raised) == 1, (
        "exactly one of the two concurrent genesis constructions must lose the race; "
        f"got {outcomes}"
    )
    loser = raised[0]
    assert isinstance(loser, sqlite3.IntegrityError), (
        "the losing construction must fail the way CI saw it "
        f"(sqlite3.IntegrityError), got {type(loser).__name__}: {loser}"
    )
    assert "schema_ledger.version" in str(loser), (
        "the refusal must name the duplicated schema-ledger genesis row — that is the whole "
        f"mechanism this test pins; got {loser}"
    )


def test_the_read_only_probe_cannot_disturb_a_store_mid_genesis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The FIX, at the SAME interleave: ``read_only_latest_as_of`` runs inside the window that
    broke the old probe and changes nothing.

    One store construction runs on a worker thread and is pinned inside its patched
    ``file_is_fresh`` — it has already decided ``was_fresh=True`` and has not yet created a
    table. While it waits, this thread captures every byte of durable database content
    (:data:`_CONTENT_FILE_SUFFIXES`), runs the REAL probe helper :data:`_PROBE_BURST` times, and
    captures those bytes again. Then the construction is released and must complete normally.

    Three independent assertions, each of which a restored store-constructing probe fails:

    1. the probe never raises and reports ``None`` (no ``snapshots`` table exists yet);
    2. the database file and its ``-wal`` are byte-identical across the burst
       (:data:`_CONTENT_FILE_SUFFIXES`) — the probe wrote no durable content, not merely
       "nothing that mattered";
    3. the paused construction finishes without an ``IntegrityError`` and the finished file
       carries exactly ONE ``CREATED`` ledger row at the store's own schema version.

    The patch is one-shot deliberately, so that this test still has teeth under the mutation it
    exists to catch: with the old probe restored, the probe's own construction is NOT paused
    (it is the second call), so it performs the genesis write itself instead of deadlocking
    against a second pause.

    **What actually fails under that mutation, measured:** assertion 2 is the one that fires —
    ``the read-only probe changed durable bytes on disk (-wal) — it is not read-only`` — because
    pytest stops at the first failing assert and 2 precedes 3. Assertion 3 independently holds
    the defect and was confirmed by neutralising 2 and re-running: it then reports
    ``IntegrityError: UNIQUE constraint failed: schema_ledger.version``, the literal CI error.
    Two independent detectors, one visible at a time — not two failures in one run.
    """
    db_path = tmp_path / MARKETFEED_FILE_NAME
    reached_genesis = threading.Event()
    may_continue = threading.Event()
    real_file_is_fresh: _FreshPredicate = store_module.file_is_fresh
    pauses_left = [1]

    def _pausing_file_is_fresh(conn: sqlite3.Connection) -> bool:
        fresh = real_file_is_fresh(conn)
        if pauses_left[0] > 0:
            pauses_left[0] -= 1
            reached_genesis.set()
            released = may_continue.wait(timeout=_HANDSHAKE_TIMEOUT_S)
            assert released, "the probing thread never released the construction"
        return fresh

    monkeypatch.setattr(store_module, "file_is_fresh", _pausing_file_is_fresh)

    construction_error: list[BaseException] = []

    def _construct() -> None:
        try:
            store = SqliteSnapshotStore(db_path)
            store.close()
        except BaseException as exc:  # noqa: BLE001 - reported by the asserts below
            construction_error.append(exc)

    worker = threading.Thread(target=_construct, daemon=True)
    worker.start()
    try:
        paused = reached_genesis.wait(timeout=_HANDSHAKE_TIMEOUT_S)
        assert paused, "the construction never reached its genesis decision"

        before = _file_state(db_path)
        observations = [
            read_only_latest_as_of(db_path, instrument=fx.INSTRUMENT)
            for _ in range(_PROBE_BURST)
        ]
        after = _file_state(db_path)
    finally:
        may_continue.set()
        worker.join(timeout=_HANDSHAKE_TIMEOUT_S * 2)

    assert not worker.is_alive(), "the paused construction thread never finished"

    # (1) the probe is total over every mid-genesis state — no exception, no invented reading.
    assert observations == [None] * _PROBE_BURST, (
        "a probe of a store that has not created its snapshots table yet must report None, "
        f"got {sorted({repr(observed) for observed in observations})}"
    )

    # (2) it wrote nothing — the byte-level claim, not an inference from "it looked fine".
    changed = [suffix or "db" for suffix in before if before[suffix] != after[suffix]]
    assert not changed, (
        "the read-only probe changed durable bytes on disk "
        f"({', '.join(changed)}) — it is not read-only"
    )

    # (3) the construction it raced finished cleanly, with a single genesis ledger row.
    assert not construction_error, (
        "the store construction the probe ran alongside failed — this is the exact CI defect "
        f"({type(construction_error[0]).__name__}: {construction_error[0]})"
    )
    assert _schema_ledger_rows(db_path) == [
        (store_module.MARKETFEED_SCHEMA_VERSION, "CREATED")
    ]


def test_the_read_only_probe_reports_a_committed_tick_without_writing(
    tmp_path: Path,
) -> None:
    """The probe's POSITIVE half: it must actually see a committed row through another live
    connection, or a probe that always returned ``None`` would pass every assertion above while
    making ``test_run_e2e``'s tick evidence vacuous.

    The writer stays OPEN across the read — that is the real shape (``cli.main`` never closes the
    composed store), and a WAL reader that needed exclusive access would fail here.
    """
    db_path = tmp_path / MARKETFEED_FILE_NAME
    on_missing_file = read_only_latest_as_of(db_path, instrument=fx.INSTRUMENT)
    assert on_missing_file is None, (
        "a probe of a path with no database file must report None — "
        "and must not create the file"
    )
    assert not db_path.exists()

    writer = SqliteSnapshotStore(db_path)
    try:
        assert read_only_latest_as_of(db_path, instrument=fx.INSTRUMENT) is None
        _insert_snapshot_row(writer, as_of_ms=1_700_000_000_000)

        before = _file_state(db_path)
        ledger_before = _schema_ledger_rows(db_path)
        assert (
            read_only_latest_as_of(db_path, instrument=fx.INSTRUMENT)
            == 1_700_000_000_000
        )
        assert read_only_latest_as_of(db_path, instrument="other-instrument") is None
        assert _file_state(db_path) == before
        assert _schema_ledger_rows(db_path) == ledger_before
    finally:
        writer.close()

    # Same answer once the writing connection is gone (the state `test_run_e2e`'s own final
    # assertion reads, after `cli.main()` has returned and the composed store has been dropped).
    assert (
        read_only_latest_as_of(db_path, instrument=fx.INSTRUMENT) == 1_700_000_000_000
    )


def test_the_read_only_probe_answers_exactly_what_the_store_answers(
    tmp_path: Path,
) -> None:
    """The probe's SQL must mean what :meth:`SqliteSnapshotStore.latest_as_of` means — checked
    against the REAL store, not asserted in prose (review-800 MEDIUM-1).

    The earlier positive test used ONE row, which cannot tell "newest by ``as_of_ms``" apart
    from "last inserted" or "any row at all". This one is built so those readings disagree:

    * five rows, inserted OUT of ``as_of_ms`` order;
    * the newest row for ``fx.INSTRUMENT`` (``…007_000``) is inserted in the MIDDLE, so a probe
      keyed on insertion order (``ORDER BY rowid DESC LIMIT 1``) returns ``…003_000`` instead;
    * the newest row in the whole table (``…009_000``) belongs to the OTHER instrument, so a
      probe that dropped ``WHERE instrument = ?`` returns that instead.

    Both readings are therefore red, and the equivalence is asserted against
    ``store.latest_as_of(...)`` itself — the production method, called live — rather than
    against a second copy of the SQL. Production code stays untouched: sharing a query constant
    with :mod:`tos_runtime.marketfeed.store` would make the store export a detail for a test's
    benefit, and would also make the two agree BY CONSTRUCTION, which is the one thing this
    test must not do.
    """
    db_path = tmp_path / MARKETFEED_FILE_NAME
    store = SqliteSnapshotStore(db_path)
    try:
        # Row 2 is the newest in the whole table but belongs to the OTHER instrument; row 3
        # is the newest for fx.INSTRUMENT yet sits in the MIDDLE of the insertion order; row 5
        # is inserted last and is NOT the newest. Each of those breaks a different wrong query.
        for as_of_ms, instrument in (
            (1_700_000_005_000, fx.INSTRUMENT),
            (1_700_000_009_000, _OTHER_INSTRUMENT),
            (1_700_000_007_000, fx.INSTRUMENT),
            (1_700_000_001_000, _OTHER_INSTRUMENT),
            (1_700_000_003_000, fx.INSTRUMENT),
        ):
            _insert_snapshot_row(store, instrument=instrument, as_of_ms=as_of_ms)

        for instrument in (fx.INSTRUMENT, _OTHER_INSTRUMENT, "never-stored"):
            assert read_only_latest_as_of(db_path, instrument=instrument) == (
                store.latest_as_of(instrument=instrument)
            ), f"probe and store disagree for {instrument!r}"

        # Spelled out too, so a simultaneous regression in BOTH readings could not pass by
        # agreeing with each other.
        assert store.latest_as_of(instrument=fx.INSTRUMENT) == 1_700_000_007_000
        probed = read_only_latest_as_of(db_path, instrument=fx.INSTRUMENT)
        assert probed == 1_700_000_007_000
        other = read_only_latest_as_of(db_path, instrument=_OTHER_INSTRUMENT)
        assert other == 1_700_000_009_000
        assert read_only_latest_as_of(db_path, instrument="never-stored") is None
    finally:
        store.close()


def test_the_read_only_probe_is_total_over_every_half_created_file_state(
    tmp_path: Path,
) -> None:
    """The probe polls a file ANOTHER process is in the middle of creating, so every
    intermediate on-disk state must answer ``None`` — never raise.

    This matters more than an ordinary "handles bad input" test because of WHERE the probe runs:
    inside ``test_run_e2e``'s sender THREAD. An exception there does not fail a test — it prints
    a traceback, kills the poller, and leaves ``run_forever`` with nobody to stop it.

    The states below are not hypothetical, and they are not one exception class. ``sqlite3``'s
    own hierarchy makes that easy to get wrong: "no such table" is an ``OperationalError``, but a
    half-written header is a ``sqlite3.DatabaseError`` ("file is not a database"), which is that
    class's SIBLING, not its subclass — so an ``except sqlite3.OperationalError`` probe passes
    the empty-file case and still explodes on the truncated-header one. Hence
    ``except sqlite3.Error``, and hence this test enumerating the states rather than trusting
    one of them to stand for the rest.
    """
    empty = tmp_path / "empty.sqlite3"
    empty.touch()

    truncated_header = tmp_path / "truncated.sqlite3"
    truncated_header.write_bytes(b"SQLite format 3\x00" + b"\x00" * 10)

    not_a_database = tmp_path / "garbage.sqlite3"
    not_a_database.write_bytes(b"not a database at all" * 32)

    wal_no_tables = tmp_path / "wal_only.sqlite3"
    _precreate_wal_file(wal_no_tables)

    reported: dict[str, list[str]] = {}
    for state_name, path in (
        ("missing file", tmp_path / "never_created.sqlite3"),
        ("zero-byte file", empty),
        ("truncated header", truncated_header),
        ("not a database", not_a_database),
        ("WAL set, no tables yet", wal_no_tables),
    ):
        seen: list[str] = []
        assert (
            read_only_latest_as_of(path, instrument=fx.INSTRUMENT, on_state=seen.append)
            is None
        ), f"the probe must answer None (never raise) for: {state_name}"
        assert len(seen) == 1, f"one state report expected for {state_name}: {seen}"
        reported[state_name] = seen

    # LOW-4's actual requirement: a caller that times out must be able to tell "the runtime
    # never created the store" from "the store was there and the row never arrived". Those two
    # are the endpoints of the list above, so it is THEIR reports that have to differ — not all
    # five, since a truncated header and a garbage file both legitimately report the same
    # "file is not a database".
    assert "does not exist" in reported["missing file"][0]
    assert "opened" in reported["WAL set, no tables yet"][0]


def test_the_read_only_probe_handles_a_uri_special_character_in_the_path(
    tmp_path: Path,
) -> None:
    """Pins how the read-only URI is BUILT, not just that it is read-only.

    A ``mode=ro`` connection needs a URI, and the obvious ``f"file:{db_path}?mode=ro"`` is wrong
    for any path carrying a URI-special character: sqlite parses everything after the FIRST
    ``?`` as query parameters, so such a path silently addresses a different, auto-created,
    empty database and every read answers "no such table". That failure would not look like a
    broken probe — it would look like a runtime that never ticked. ``Path.as_uri()``
    percent-encodes the path, which is why the helper uses it.

    Restoring the f-string form turns this test red: the probe reports ``None`` for a row that
    is demonstrably committed (the store's own ``latest_as_of`` reads it back in the same
    breath).
    """
    awkward_dir = tmp_path / "data?dir#1 with spaces"
    awkward_dir.mkdir()
    db_path = awkward_dir / MARKETFEED_FILE_NAME

    writer = SqliteSnapshotStore(db_path)
    try:
        _insert_snapshot_row(writer, as_of_ms=1_700_000_001_000)
        # The store itself (a plain filename, no URI parsing) is the control: the row IS there.
        assert writer.latest_as_of(instrument=fx.INSTRUMENT) == 1_700_000_001_000
        probed = read_only_latest_as_of(db_path, instrument=fx.INSTRUMENT)
    finally:
        writer.close()

    assert probed == 1_700_000_001_000, (
        "the read-only probe lost a committed row because the database path carries a "
        f"URI-special character ({db_path.name!r} under {awkward_dir.name!r}) — the URI is "
        "being built by string interpolation instead of Path.as_uri()"
    )
