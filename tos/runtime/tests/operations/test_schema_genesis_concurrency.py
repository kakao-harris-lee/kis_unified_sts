"""The GENESIS TRANSACTION of the four durable stores, under concurrent first boot (#801)."""

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

_PROCESSES = 8

_DDL_PAUSE_S = 0.05

_JOIN_TIMEOUT_S = 60.0

_STORES: tuple[tuple[str, int, str], ...] = (
    ("evidence", EVIDENCE_SCHEMA_VERSION, "CREATE TABLE IF NOT EXISTS entries"),
    ("inbox", INBOX_SCHEMA_VERSION, "CREATE TABLE IF NOT EXISTS events"),
    ("marketfeed", MARKETFEED_SCHEMA_VERSION, "CREATE TABLE IF NOT EXISTS snapshots"),
    ("rcl", RCL_SCHEMA_VERSION, "CREATE TABLE IF NOT EXISTS epochs"),
)

_STORE_IDS = tuple(name for name, _, _ in _STORES)


def _open_store(store: str, path: Path, *, party: str = "solo") -> Any:
    """Construct ``store`` over ``path`` exactly the way ``compose`` does, and return it."""
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
    """Test-only connection that sleeps after the statement naming :data:`_pause_after_sql`."""

    def execute(self, sql: str, *parameters: Any) -> sqlite3.Cursor:
        cursor = super().execute(sql, *parameters)
        if _pause_after_sql and _pause_after_sql in sql:
            time.sleep(_DDL_PAUSE_S)
        return cursor


_pause_after_sql: str = ""


def _child(
    store: str,
    path_str: str,
    pause_after_sql: str,
    party: int,
    barrier: BarrierType,
    queue: mp.Queue[str],
) -> None:
    """Open ``store`` over ``path_str`` in lockstep with every sibling; report the outcome."""
    try:
        global _pause_after_sql
        _pause_after_sql = pause_after_sql
        real_connect = sqlite3.connect

        def connect_with_delay(*args: Any, **kwargs: Any) -> sqlite3.Connection:
            kwargs["factory"] = _DelayedConnection
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
    """Leave ``path`` an empty ``journal_mode=WAL`` database with NO user tables."""
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
    """The genesis ledger, read through a ``mode=ro`` connection so this evidence-gathering"""
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
    """Eight processes enter the same file's GENESIS TRANSACTION at once: all eight boot, one row."""
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
    """The file a concurrent first boot leaves behind is an ORDINARY store file."""
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
    """Genesis is fail-CLOSED when the wait overflows: an explicit error, and an untouched file."""
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

        log = SqliteCommitLog(path, evidence_port=evidence, sqlite_timeout_s=0)
        log.close()
        assert _ledger_rows(path) == [(RCL_SCHEMA_VERSION, "CREATED")]
    finally:
        holder.close()
        evidence.close()


_BIRTH_RACE_STORES: tuple[tuple[str, int], ...] = tuple(
    (store, version) for store, version, _ in _STORES
)

#: bare-PRAGMA rate rather than the store-CONSTRUCTOR rate the test actually drives, and the
_BIRTH_RACE_ROUNDS = 20


@pytest.mark.parametrize(
    ("store", "expected_version"), _BIRTH_RACE_STORES, ids=_STORE_IDS
)
def test_concurrent_first_boot_on_a_brand_new_file_admits_every_process(
    tmp_path: Path, store: str, expected_version: int
) -> None:
    """Eight processes open the same NON-EXISTENT store path at once: all eight boot (**#818**)."""
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
