"""One sqlite connection per thread for a store opened by one thread (issue #950).

:class:`~tos_runtime.evidence.store.SqliteEvidenceStore` is opened on the session's main thread,
and its connection stays that thread's. The fill observer's FETCH thread reaches the store too —
every custody load it triggers appends ``CUSTODY_LOAD``, a stale token appends
``TRANSPORT_TOKEN_STALE`` — and a sqlite3 connection is single-thread by default. Sharing that one
connection across threads (``check_same_thread=False``) would put two threads' transactions on
one handle: a ``BEGIN IMMEDIATE`` issued while the other thread's is open fails, and a read on the
loop thread could see the other thread's uncommitted row. So every other thread gets its OWN
connection to the same WAL file: each reads only committed rows, and ``BEGIN IMMEDIATE`` serializes
writers across connections exactly as it already does across processes. The store additionally
holds one in-process write lock, so its own threads queue instead of waiting on sqlite's busy
timeout.

``synchronous`` is a per-connection setting, so every connection opened here gets ``FULL`` — a
worker's append is as durable as the owner's. :meth:`ThreadConnections.close` closes them all;
a thread asking afterwards is refused (``sqlite3.ProgrammingError``), never silently reopened.

Firewall: stdlib only.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path

__all__ = ["ThreadConnections"]


class ThreadConnections:
    """The owner thread's connection plus one lazily opened connection per other thread."""

    def __init__(self, path: Path, owner: Callable[[], sqlite3.Connection]) -> None:
        """``owner`` returns the opening thread's connection — read per call, so the store
        stays the one place that connection lives."""
        self._path = path
        self._owner = owner
        self._owner_thread = threading.get_ident()
        self._local = threading.local()
        self._others: list[sqlite3.Connection] = []
        self._guard = threading.Lock()
        self._closed = False
        #: Serializes this process's writes (module docstring).
        self.write_lock = threading.RLock()

    def current(self) -> sqlite3.Connection:
        """This thread's connection."""
        if threading.get_ident() == self._owner_thread:
            return self._owner()
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            return conn
        with self._guard:
            if self._closed:
                raise sqlite3.ProgrammingError("Cannot operate on a closed database.")
            # check_same_thread=False only so close() can run on the owner thread; the
            # connection is otherwise used by the thread that opened it, alone.
            conn = sqlite3.connect(
                str(self._path), isolation_level=None, check_same_thread=False
            )
            conn.execute("PRAGMA synchronous=FULL")
            self._others.append(conn)
        self._local.conn = conn
        return conn

    def close(self) -> None:
        """Close every connection, the owner's included."""
        with self._guard:
            self._closed = True
            others, self._others = self._others, []
        for conn in others:
            conn.close()
        self._owner().close()
