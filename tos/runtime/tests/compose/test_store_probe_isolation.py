"""The probe-isolation regression suite for ``test_run_e2e.py``'s tick probe (review-797;"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from tos_runtime.marketfeed import store as store_module
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME, SqliteSnapshotStore
from tos_runtime.operations import schema_ledger as schema_ledger_module

from . import _fixtures as fx
from .test_run_e2e import read_only_latest_as_of

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_HANDSHAKE_TIMEOUT_S = 10.0

_FreshPredicate = Callable[[sqlite3.Connection], bool]

_BLOCKED_OBSERVATION_S = 0.5

_PROBE_BURST = 50

_OTHER_INSTRUMENT = "NQ"


_CONTENT_FILE_SUFFIXES = ("", "-wal")


def _file_state(db_path: Path) -> dict[str, bytes | None]:
    """Every byte of durable database content for ``db_path`` (:data:`_CONTENT_FILE_SUFFIXES`)."""
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
    """Commit one ``snapshots`` row through ``store``'s own live connection."""
    store._conn.execute("BEGIN IMMEDIATE")
    store._conn.execute(
        "INSERT INTO snapshots "
        "(snapshot_id, canonical_digest, instrument, as_of_ms, snapshot_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (f"snap-{instrument}-{as_of_ms}", "digest-1", instrument, as_of_ms, "{}"),
    )
    store._conn.execute("COMMIT")


def _precreate_wal_file(db_path: Path) -> None:
    """Create ``db_path`` as an empty ``journal_mode=WAL`` database with no user tables — the"""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    finally:
        conn.close()


def _schema_ledger_rows(db_path: Path) -> list[tuple[object, ...]]:
    """The store's genesis ledger, read the same structurally read-only way the probe under"""
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


def test_a_second_store_construction_cannot_enter_the_first_ones_genesis_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The genesis window is no longer INTERLEAVABLE — which is why the old probe's race is gone."""
    db_path = tmp_path / MARKETFEED_FILE_NAME
    _precreate_wal_file(db_path)
    reached_genesis = threading.Event()
    may_continue = threading.Event()
    second_about_to_construct = threading.Event()
    real_file_is_fresh: _FreshPredicate = schema_ledger_module.file_is_fresh
    calls: list[bool] = []

    def _pausing_file_is_fresh(conn: sqlite3.Connection) -> bool:
        fresh = real_file_is_fresh(conn)
        calls.append(fresh)
        if len(calls) == 1:
            reached_genesis.set()
            released = may_continue.wait(timeout=_HANDSHAKE_TIMEOUT_S)
            assert released, "the main thread never released the first construction"
        return fresh

    monkeypatch.setattr(schema_ledger_module, "file_is_fresh", _pausing_file_is_fresh)

    outcomes: dict[str, BaseException | None] = {}

    def _construct(name: str) -> None:
        if name == "second":
            second_about_to_construct.set()
        try:
            store = SqliteSnapshotStore(db_path)
            store.close()
            outcomes[name] = None
        except BaseException as exc:  # noqa: BLE001 - the exception IS the outcome
            outcomes[name] = exc

    threads = {
        name: threading.Thread(target=_construct, args=(name,), daemon=True)
        for name in ("first", "second")
    }
    threads["first"].start()
    assert reached_genesis.wait(
        timeout=_HANDSHAKE_TIMEOUT_S
    ), "the first construction never reached its genesis decision"
    try:
        threads["second"].start()
        assert second_about_to_construct.wait(
            timeout=_HANDSHAKE_TIMEOUT_S
        ), "the second construction thread never started"
        time.sleep(_BLOCKED_OBSERVATION_S)

        assert calls == [True], (
            "the second construction observed its own freshness while the first was still "
            f"inside its genesis transaction — the window is interleavable again ({calls})"
        )
    finally:
        may_continue.set()
        for thread in threads.values():
            thread.join(timeout=_HANDSHAKE_TIMEOUT_S * 2)

    assert all(
        not thread.is_alive() for thread in threads.values()
    ), "a construction thread never finished"
    assert outcomes == {"first": None, "second": None}, (
        "both concurrent first boots must now succeed — neither may lose a genesis race; "
        f"got {outcomes}"
    )
    assert calls == [True, False], calls
    assert _schema_ledger_rows(db_path) == [
        (store_module.MARKETFEED_SCHEMA_VERSION, "CREATED")
    ]


def test_the_read_only_probe_cannot_disturb_a_store_mid_genesis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The PROBE's half, at the SAME interleave: ``read_only_latest_as_of`` runs inside the window"""
    db_path = tmp_path / MARKETFEED_FILE_NAME
    reached_genesis = threading.Event()
    may_continue = threading.Event()
    real_file_is_fresh: _FreshPredicate = schema_ledger_module.file_is_fresh
    pauses_left = [1]

    def _pausing_file_is_fresh(conn: sqlite3.Connection) -> bool:
        fresh = real_file_is_fresh(conn)
        if pauses_left[0] > 0:
            pauses_left[0] -= 1
            reached_genesis.set()
            released = may_continue.wait(timeout=_HANDSHAKE_TIMEOUT_S)
            assert released, "the probing thread never released the construction"
        return fresh

    monkeypatch.setattr(schema_ledger_module, "file_is_fresh", _pausing_file_is_fresh)

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

    assert observations == [None] * _PROBE_BURST, (
        "a probe of a store that has not created its snapshots table yet must report None, "
        f"got {sorted({repr(observed) for observed in observations})}"
    )

    changed = [suffix or "db" for suffix in before if before[suffix] != after[suffix]]
    assert not changed, (
        "the read-only probe changed durable bytes on disk "
        f"({', '.join(changed)}) — it is not read-only"
    )

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
    """The probe's POSITIVE half: it must actually see a committed row through another live"""
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

    assert (
        read_only_latest_as_of(db_path, instrument=fx.INSTRUMENT) == 1_700_000_000_000
    )


def test_the_read_only_probe_answers_exactly_what_the_store_answers(
    tmp_path: Path,
) -> None:
    """The probe's SQL must mean what :meth:`SqliteSnapshotStore.latest_as_of` means — checked"""
    db_path = tmp_path / MARKETFEED_FILE_NAME
    store = SqliteSnapshotStore(db_path)
    try:
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
    """The probe polls a file ANOTHER process is in the middle of creating, so every"""
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

    assert "does not exist" in reported["missing file"][0]
    assert "opened" in reported["WAL set, no tables yet"][0]


def test_the_read_only_probe_handles_a_uri_special_character_in_the_path(
    tmp_path: Path,
) -> None:
    """Pins how the read-only URI is BUILT, not just that it is read-only."""
    awkward_dir = tmp_path / "data?dir#1 with spaces"
    awkward_dir.mkdir()
    db_path = awkward_dir / MARKETFEED_FILE_NAME

    writer = SqliteSnapshotStore(db_path)
    try:
        _insert_snapshot_row(writer, as_of_ms=1_700_000_001_000)
        assert writer.latest_as_of(instrument=fx.INSTRUMENT) == 1_700_000_001_000
        probed = read_only_latest_as_of(db_path, instrument=fx.INSTRUMENT)
    finally:
        writer.close()

    assert probed == 1_700_000_001_000, (
        "the read-only probe lost a committed row because the database path carries a "
        f"URI-special character ({db_path.name!r} under {awkward_dir.name!r}) — the URI is "
        "being built by string interpolation instead of Path.as_uri()"
    )
