"""One fenced RCL transition snapshot, reused while nothing has been committed (#1008)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import ReservationTransitionHistory, SqliteCommitLog

__all__ = ["ReservationHistoryCache"]


def _evidence_tip(store: SqliteEvidenceStore) -> int | None:
    """The evidence store's newest ``seq``, or ``None`` when it cannot be read."""
    try:
        row = store.connection.execute("SELECT MAX(seq) FROM entries").fetchone()
    except sqlite3.Error:
        return None
    return None if row is None or row[0] is None else int(row[0])


@dataclass
class ReservationHistoryCache:
    """The most recent fenced transition snapshot plus the key it was taken under."""

    _key: tuple[int, int] | None = field(default=None, repr=False, compare=False)
    _history: ReservationTransitionHistory | None = field(
        default=None, repr=False, compare=False
    )

    def history(
        self, rcl_log: SqliteCommitLog, evidence_store: SqliteEvidenceStore
    ) -> ReservationTransitionHistory:
        """The current transition history, re-read only when the key moved (module docstring)."""
        epoch = rcl_log.current_epoch()
        tip = _evidence_tip(evidence_store)
        key = None if tip is None else (epoch, tip)
        remembered = self._history
        if remembered is not None and key is not None and key == self._key:
            return remembered
        history = rcl_log.reservation_transition_history(writer_epoch=epoch)
        self._key = key
        self._history = history
        return history
