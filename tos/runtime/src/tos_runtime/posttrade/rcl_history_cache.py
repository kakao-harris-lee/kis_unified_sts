"""One fenced RCL transition snapshot, reused while nothing has been committed (#1008).

:meth:`~tos_runtime.rcl.log.SqliteCommitLog.reservation_transition_history` is not a
cheap read: it runs :meth:`~tos_runtime.rcl.log.SqliteCommitLog.verify_replay` (a full
re-fold of ``entries`` plus two canonical digests) and then decodes every discriminated
transition row. The entry-recovery **discovery scan** asks for it at least twice per
recorded pending row on every loop pass, so a scope that accumulates closes pays that
read N times over for an answer that cannot have changed — review-1007 M3 measured
≈10 ms per read on a 300-entry log, i.e. ~0.4 s per pass on the loop thread after ~20
closes, against a 500 ms pass budget.

**The key.** ``(writer_epoch, evidence tip)``, both read before the snapshot. The
evidence tip is the change detector: :meth:`~tos_runtime.rcl.log.SqliteCommitLog
._append_evidence_or_refuse` writes the ``RCL_*`` evidence row inside the append's own
transaction, strictly before its ``COMMIT``, so evidence may over-record an append the
RCL itself never holds **but never the reverse**. An unchanged evidence tip therefore
proves no RCL entry committed; the converse does not hold, and does not need to — an
evidence-only append (a ``CAPACITY_RELEASE_HELD`` row, a receipt) merely costs one
fresh read. The epoch rides along because :meth:`~tos_runtime.rcl.log.SqliteCommitLog
.acquire_epoch` writes no evidence row. Reading the key BEFORE the snapshot keeps the
error in the conservative direction: a commit landing in between labels a *newer*
snapshot with an *older* tip, which the next pass re-reads, and never the reverse.
``None`` (an unreadable tip) never equals a remembered key, so an unreadable store
re-asks — the same fail-closed direction :meth:`~tos_runtime.posttrade.unsent_release
.UnsentReleaseSweeper._evidence_tip` takes for its own tip-keyed verdict cache.

**What this does not cache.** Only the discovery scan's own commit lookups read through
here. Every path that authorizes a release still takes its own fresh, replay-verified
snapshot: :func:`~tos_runtime.posttrade.close_history.durable_close_history` and
``_scope_has_no_new_attempt`` are untouched, and the release itself is still fenced on
that snapshot's exact ``(writer_epoch, last_seq)`` by the CAS. The decision and the
evidence it records are byte-identical either way — this is a read-count change only.

In-memory only, per consumer object: a fresh process starts with an empty cache, the
same discipline :attr:`~tos_runtime.posttrade.release_consumer.FinalityReleaseConsumer
._wait_start_ms` follows.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib +
``tos_runtime.evidence.store`` + ``tos_runtime.rcl.log`` only. No ``shared.*``, no write
call of any kind.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import ReservationTransitionHistory, SqliteCommitLog

__all__ = ["ReservationHistoryCache"]


def _evidence_tip(store: SqliteEvidenceStore) -> int | None:
    """The evidence store's newest ``seq``, or ``None`` when it cannot be read.

    ``MAX(seq)`` on an INTEGER PRIMARY KEY is a single B-tree seek, not a scan.
    """
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
        """The current transition history, re-read only when the key moved (module docstring).

        Raises:
            Exception: Whatever :meth:`~tos_runtime.rcl.log.SqliteCommitLog
                .reservation_transition_history` raises on a stale epoch, a replay
                mismatch, or a malformed row — a refused read never replaces the
                remembered snapshot, and never serves it either (its key no longer
                matches, which is why the read was taken).
        """
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
