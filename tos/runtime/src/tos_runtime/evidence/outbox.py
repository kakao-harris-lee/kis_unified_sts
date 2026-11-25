"""Same-transaction outbox enqueue + at-least-once ``drain`` (design #40 D3, §2 item 3)."""

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
    """The one attribute :func:`drain` needs from an evidence store — its live connection."""

    @property
    def connection(self) -> sqlite3.Connection: ...


def create_outbox_table(conn: sqlite3.Connection) -> None:
    """Create the ``outbox`` table (idempotent) on the evidence store's own connection."""
    conn.execute(_CREATE_OUTBOX_TABLE_SQL)


def enqueue(
    cursor: sqlite3.Cursor | sqlite3.Connection, *, entry_seq: int, target: str
) -> None:
    """Insert one pending outbox row on the CALLER'S OWN open cursor/transaction."""
    cursor.execute(
        "INSERT INTO outbox (entry_seq, target, delivered_at_monotonic_ns) "
        "VALUES (?, ?, NULL)",
        (entry_seq, target),
    )


class OutboxDelivery(BaseModel):
    """One pending delivery, joined against its referenced entry's content."""

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
        """Attempt one delivery; return ``True`` iff it should be marked delivered."""
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
    """Deliver every pending outbox row at least once; mark delivered ones done."""
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
