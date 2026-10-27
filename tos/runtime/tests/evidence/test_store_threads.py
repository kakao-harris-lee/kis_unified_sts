"""Issue #950 — the evidence store's connection policy across threads.

The fill observer's FETCH thread reaches the evidence store through the credential path (a
``CUSTODY_LOAD`` row per custody load, ``TRANSPORT_TOKEN_STALE`` on a stale token). Before #950
the store had one connection with ``check_same_thread=True``, so any such append from that thread
raised ``ProgrammingError``. The policy now: the opening thread keeps its connection, every other
thread gets its own connection to the same WAL file, and appends are serialized in-process.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from tos_runtime.evidence.store import SqliteEvidenceStore

from .conftest import FixedKeyProvider


def test_an_append_from_another_thread_lands_in_the_same_chain(
    store: SqliteEvidenceStore,
) -> None:
    """Mutation: drop the per-thread connection -> ``ProgrammingError`` in the worker -> red."""
    store.append({"n": 0}, kind="MAIN", record_class="MAIN")
    errors: list[BaseException] = []

    def _worker() -> None:
        try:
            store.append({"n": 1}, kind="WORKER", record_class="WORKER")
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
            errors.append(exc)

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join()

    assert errors == []
    kinds = [
        row[0]
        for row in store.connection.execute("SELECT kind FROM entries ORDER BY seq")
    ]
    assert kinds == ["MAIN", "WORKER"]
    assert store.verify({1: FixedKeyProvider().current()[1]})


def test_concurrent_appends_from_two_threads_keep_one_unbroken_chain(
    store: SqliteEvidenceStore,
) -> None:
    """Two threads appending at once: every row lands, seqs are dense, and the HMAC chain
    verifies — no interleaved transaction, no forked tail. Mutation: remove the write lock and
    share one connection (``check_same_thread=False``) -> "cannot start a transaction within a
    transaction" or a broken chain -> red."""
    per_thread = 40
    start = threading.Barrier(2)
    errors: list[BaseException] = []

    def _worker(name: str) -> None:
        start.wait()
        try:
            for i in range(per_thread):
                store.append({"i": i}, kind=name, record_class=name)
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(n,)) for n in ("LOOP", "FETCH")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    seqs = [r[0] for r in store.connection.execute("SELECT seq FROM entries")]
    assert sorted(seqs) == list(range(2 * per_thread))
    assert store.verify({1: FixedKeyProvider().current()[1]})


def test_a_worker_connection_is_durable_like_the_owner_connection(
    store: SqliteEvidenceStore,
) -> None:
    """``synchronous`` is per connection — a worker connection must carry ``FULL`` too."""
    seen: list[int] = []

    def _worker() -> None:
        seen.append(store.connection.execute("PRAGMA synchronous").fetchone()[0])

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join()
    assert seen == [2]  # FULL


def test_close_closes_every_threads_connection(tmp_path: Path) -> None:
    """No connection outlives the store: after ``close()`` the worker's connection is closed
    too, and a thread asking afterwards is refused rather than silently reopening the file.
    """
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    worker_conn: list[sqlite3.Connection] = []

    def _open() -> None:
        worker_conn.append(instance.connection)

    thread = threading.Thread(target=_open)
    thread.start()
    thread.join()
    instance.close()

    try:
        worker_conn[0].execute("SELECT 1")
    except sqlite3.ProgrammingError:
        pass
    else:  # pragma: no cover - the assertion
        raise AssertionError("the worker connection survived close()")

    refused: list[BaseException] = []

    def _late() -> None:
        try:
            instance.append({}, kind="LATE", record_class="LATE")
        except sqlite3.ProgrammingError as exc:
            refused.append(exc)

    late = threading.Thread(target=_late)
    late.start()
    late.join()
    assert len(refused) == 1
