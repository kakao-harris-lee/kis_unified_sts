"""One sqlite connection per thread for a store opened by one thread (issue #950)."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path

__all__ = ["ThreadConnections"]


class ThreadConnections:
    """The owner thread's connection plus one lazily opened connection per other thread."""

    def __init__(self, path: Path, owner: Callable[[], sqlite3.Connection]) -> None:
        """``owner`` returns the opening thread's connection — read per call, so the store"""
        self._path = path
        self._owner = owner
        self._owner_thread = threading.get_ident()
        self._local = threading.local()
        self._others: list[sqlite3.Connection] = []
        self._guard = threading.Lock()
        self._closed = False
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
