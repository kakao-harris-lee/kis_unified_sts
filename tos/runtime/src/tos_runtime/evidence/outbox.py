"""Same-transaction outbox enqueue + at-least-once ``drain`` (design #40 D3, §2 item 3).

The ``outbox`` table lives in the SAME sqlite file as ``entries``
(:mod:`tos_runtime.evidence.store`), so :func:`enqueue` — called from inside
:meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.append`'s own
``BEGIN IMMEDIATE``/``COMMIT`` block, on the SAME cursor — either commits
together with the entry it references or rolls back together with it
(contract "outbox 같은 트랜잭션(append 실패 시 outbox 행 0)"). Unlike
``entries``, ``outbox`` is ordinary (no append-only trigger): marking a row
delivered is an ``UPDATE`` of bookkeeping metadata, not a rewrite of evidence
content — the referenced entry itself is never touched.

**No real external sink is implemented here** (design #40 §2 item 3 "실제
외부 싱크 구현 0") — :class:`OutboxConsumer` is the Protocol a future
transport adapter satisfies; :func:`drain` only guarantees at-least-once
delivery semantics and idempotency-key plumbing.

Firewall: stdlib (``sqlite3``, ``json``, ``time``) + ``pydantic`` only.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable, Iterator
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

__all__ = [
    "OutboxConsumer",
    "OutboxDelivery",
    "create_outbox_table",
    "drain",
    "enqueue",
]

_CREATE_OUTBOX_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS outbox (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_seq INTEGER NOT NULL,
    target TEXT NOT NULL,
    delivered_at_monotonic_ns INTEGER
)
"""


@runtime_checkable
class _ConnectionSource(Protocol):
    """The one attribute :func:`drain` needs from an evidence store — its live connection.

    A structural Protocol (rather than importing
    :class:`tos_runtime.evidence.store.SqliteEvidenceStore` directly) so this
    module never depends on ``store.py`` — ``store.py`` depends on THIS
    module (to enqueue inside its own transaction), and a two-way import edge
    would be a cycle.
    """

    @property
    def connection(self) -> sqlite3.Connection: ...


def create_outbox_table(conn: sqlite3.Connection) -> None:
    """Create the ``outbox`` table (idempotent) on the evidence store's own connection."""
    conn.execute(_CREATE_OUTBOX_TABLE_SQL)


def enqueue(
    cursor: sqlite3.Cursor | sqlite3.Connection, *, entry_seq: int, target: str
) -> None:
    """Insert one pending outbox row on the CALLER'S OWN open cursor/transaction.

    Never commits — the caller (:meth:`SqliteEvidenceStore.append`) controls
    the transaction boundary so this row lands in the same commit as the
    entry it references.

    Args:
        cursor: The sqlite3 cursor/connection already inside an open
            transaction.
        entry_seq: The ``entries.seq`` this outbox row is delivering.
        target: The delivery target name (caller vocabulary).
    """
    cursor.execute(
        "INSERT INTO outbox (entry_seq, target, delivered_at_monotonic_ns) "
        "VALUES (?, ?, NULL)",
        (entry_seq, target),
    )


class OutboxDelivery(BaseModel):
    """One pending delivery, joined against its referenced entry's content.

    ``idempotency_key`` is ``(segment_id, entry_seq)`` (design #40 §2 item 3)
    — stable across repeated at-least-once deliveries of the same row, so a
    consumer can dedupe without needing its own sequence tracking.
    """

    model_config = ConfigDict(frozen=True)

    outbox_seq: int
    entry_seq: int
    target: str
    segment_id: str | None = None
    kind: str
    record_class: str
    payload: dict[str, object]

    @property
    def idempotency_key(self) -> tuple[str | None, int]:
        """The ``(segment_id, entry_seq)`` dedupe key for this delivery."""
        return (self.segment_id, self.entry_seq)


@runtime_checkable
class OutboxConsumer(Protocol):
    """The injected delivery sink :func:`drain` calls for each pending row."""

    def deliver(self, delivery: OutboxDelivery) -> bool:
        """Attempt one delivery; return ``True`` iff it should be marked delivered.

        A ``False`` return (or a raised exception, which propagates to the
        caller of :func:`drain`) leaves the row pending for a later
        :func:`drain` call — at-least-once, never at-most-once.
        """
        ...


def _iter_pending(conn: sqlite3.Connection) -> Iterator[OutboxDelivery]:
    """Yield every undelivered outbox row, joined against its entry, in seq order."""
    cur = conn.execute(
        "SELECT outbox.seq, outbox.entry_seq, outbox.target, "
        "entries.segment_id, entries.kind, entries.record_class, entries.payload_json "
        "FROM outbox JOIN entries ON entries.seq = outbox.entry_seq "
        "WHERE outbox.delivered_at_monotonic_ns IS NULL "
        "ORDER BY outbox.seq ASC"
    )
    for row in cur:
        outbox_seq, entry_seq, target, segment_id, kind, record_class, payload_json = (
            row
        )
        stored = json.loads(payload_json)
        yield OutboxDelivery(
            outbox_seq=outbox_seq,
            entry_seq=entry_seq,
            target=target,
            segment_id=segment_id,
            kind=kind,
            record_class=record_class,
            payload=stored.get("payload", {}),
        )


def drain(
    store: _ConnectionSource,
    consumer: OutboxConsumer,
    *,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> int:
    """Deliver every pending outbox row at least once; mark delivered ones done.

    Args:
        store: The evidence store owning the outbox (its
            ``.connection`` is reused directly).
        consumer: The delivery sink.
        monotonic_ns: Injected monotonic-clock callable for
            ``delivered_at_monotonic_ns`` on a successful delivery.

    Returns:
        The number of rows marked delivered this call.
    """
    conn = store.connection
    delivered = 0
    for delivery in list(_iter_pending(conn)):
        if consumer.deliver(delivery):
            conn.execute(
                "UPDATE outbox SET delivered_at_monotonic_ns = ? WHERE seq = ?",
                (monotonic_ns(), delivery.outbox_seq),
            )
            delivered += 1
    return delivered
