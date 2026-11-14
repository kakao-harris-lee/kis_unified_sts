"""Resolve an ``attempt_id`` onto its RCL reservation, from durable evidence alone (#966)."""

from __future__ import annotations

import json
import threading
import weakref
from dataclasses import dataclass, field

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.projection import ReservationProjectionReader
from tos_runtime.rcl.reservation_identity import (
    permit_reservation_id,
    scope_reservation_id,
)

__all__ = [
    "attempt_id_for_reservation",
    "permit_identity_for_attempt",
    "reservation_id_for_attempt",
]

_FLOW_STEP_ADMITTED = "FLOW_STEP_ADMITTED"
_ATTEMPT_REQUEST_CREATED = "ATTEMPT_REQUEST_CREATED"
_ATOMIC_COMMIT = "ATOMIC_COMMIT"


def _single(values: set[str]) -> str | None:
    """The one member of ``values``, or ``None`` for none and ``None`` for several."""
    return next(iter(values)) if len(values) == 1 else None


_decode = json.loads


@dataclass
class _JoinIndex:
    """The join's two halves, folded from every row with ``seq <= last_seq`` (module docstring)."""

    last_seq: int = -1
    events_by_attempt: dict[str, set[str]] = field(default_factory=dict)
    attempts_by_event: dict[str, set[str]] = field(default_factory=dict)
    permits_by_event: dict[str, set[str]] = field(default_factory=dict)
    events_by_permit: dict[str, set[str]] = field(default_factory=dict)

    def absorb(self, store: SqliteEvidenceStore) -> None:
        """Fold in every row of the two kinds committed after ``last_seq``. All new rows are"""
        rows = store.connection.execute(
            "SELECT seq, kind, payload_json FROM entries "
            "WHERE kind IN (?, ?) AND seq > ? ORDER BY seq ASC",
            (_ATTEMPT_REQUEST_CREATED, _FLOW_STEP_ADMITTED, self.last_seq),
        ).fetchall()
        decoded = [
            (seq, kind, _decode(payload_json).get("payload"))
            for seq, kind, payload_json in rows
        ]
        for seq, kind, payload in decoded:
            self.last_seq = max(self.last_seq, int(seq))
            if not isinstance(payload, dict):
                continue
            event_id = payload.get("event_id")
            if not isinstance(event_id, str):
                continue
            if kind == _ATTEMPT_REQUEST_CREATED:
                attempt_id = payload.get("attempt_id")
                if isinstance(attempt_id, str):
                    self.events_by_attempt.setdefault(attempt_id, set()).add(event_id)
                    self.attempts_by_event.setdefault(event_id, set()).add(attempt_id)
            elif payload.get("step") == _ATOMIC_COMMIT:
                permit_identity = payload.get("bound_identity")
                if isinstance(permit_identity, str):
                    self.permits_by_event.setdefault(event_id, set()).add(
                        permit_identity
                    )
                    self.events_by_permit.setdefault(permit_identity, set()).add(
                        event_id
                    )


_INDEXES: weakref.WeakKeyDictionary[SqliteEvidenceStore, _JoinIndex] = (
    weakref.WeakKeyDictionary()
)
_INDEX_LOCK = threading.Lock()


def _with_index(store: SqliteEvidenceStore) -> _JoinIndex:
    """The store's index, brought up to the committed tip (module docstring). Callers read it"""
    if store.connection.in_transaction:
        uncached = _JoinIndex()
        uncached.absorb(store)
        return uncached
    index = _INDEXES.get(store)
    (tip,) = store.connection.execute("SELECT MAX(seq) FROM entries").fetchone()
    if index is None or (tip if tip is not None else -1) < index.last_seq:
        index = _INDEXES[store] = _JoinIndex()
    index.absorb(store)
    return index


def permit_identity_for_attempt(
    store: SqliteEvidenceStore, attempt_id: str
) -> str | None:
    """The Action Flow Permit identity ``attempt_id``'s own flow committed its reservation under."""
    with _INDEX_LOCK:
        index = _with_index(store)
        event_ids = index.events_by_attempt.get(attempt_id, set())
        if not event_ids:
            return None
        return _single(
            {
                permit_identity
                for event_id in event_ids
                for permit_identity in index.permits_by_event.get(event_id, ())
            }
        )


def attempt_id_for_reservation(
    store: SqliteEvidenceStore, permit_identity: str
) -> str | None:
    """The attempt id of the flow that committed the reservation named by ``permit_identity``."""
    with _INDEX_LOCK:
        index = _with_index(store)
        event_ids = index.events_by_permit.get(permit_identity, set())
        if not event_ids:
            return None
        return _single(
            {
                attempt_id
                for event_id in event_ids
                for attempt_id in index.attempts_by_event.get(event_id, ())
            }
        )


def reservation_id_for_attempt(
    store: SqliteEvidenceStore,
    projection: ReservationProjectionReader,
    *,
    account: str,
    instrument: str,
    attempt_id: str,
) -> str | None:
    """The reservation id ``attempt_id`` committed against, **only if the log holds that row**."""
    permit_identity = permit_identity_for_attempt(store, attempt_id)
    if permit_identity is None:
        return None
    candidate = permit_reservation_id(account, instrument, permit_identity)
    if projection.reservation_state(candidate) is not None:
        return candidate
    legacy = scope_reservation_id(account, instrument)
    if projection.reservation_state(legacy) is not None:
        return legacy
    return None
