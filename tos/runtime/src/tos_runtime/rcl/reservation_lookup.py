"""Resolve an ``attempt_id`` onto its RCL reservation, from durable evidence alone (#966).

Three post-trade consumers hold an ``attempt_id`` and nothing else: the release consumer
(:mod:`tos_runtime.posttrade.release_consumer`), the recovery reconciliation bridge
(:mod:`tos_runtime.recovery.reconciliation`), and the ``SEND_REFUSED`` obligation recorder
(:mod:`tos_runtime.rcl.obligation`). Since #966 a reservation is named by the Action Flow
Permit identity, not by the scope (:mod:`tos_runtime.rcl.reservation_identity` — see its
docstring for why the attempt id itself cannot be the name), so those three need a mapping
``attempt_id -> permit identity``.

**The mapping is already durable; this module only reads it.** Two evidence rows of the same
commitment flow carry the two halves, joined by the ``event_id`` they share:

* ``FLOW_STEP_ADMITTED`` with ``step = "ATOMIC_COMMIT"`` — its ``bound_identity`` is the Action
  Flow Permit identity (``tos_runtime.risk.ledger_stages.AtomicCommitStage`` sets it; the
  sequencer copies the verdict's fields verbatim onto the record).
* ``ATTEMPT_REQUEST_CREATED`` — its ``attempt_id`` is the step-12 attempt identity.

``tos.engine.records.EngineEvidenceRecord.bound_identity``'s own field docstring names this
exact pair as the step-12 attempt identity's content-addressed inputs, recorded durably
*precisely so* "a rebooted replay could reconstruct the live ``attempt_id`` from durable
evidence alone". This module takes that same join in the other direction. Nothing new is
written, and the join survives a restart because both rows are durable.

**Fail-closed throughout.** Every function returns ``None`` — never a guessed or constructed
id — when the join is empty (no such flow on record) or ambiguous (one flow somehow carrying
two distinct permit identities). A ``None`` makes the caller hold; a fabricated id would be
re-read against the log as if it were this attempt's reservation.

**Pre-#966 ledgers.** :func:`reservation_id_for_attempt` only ever returns an id the log
actually holds a row for. When the join resolves but no per-permit row exists, it falls back to
the scope-level :func:`~tos_runtime.rcl.reservation_identity.scope_reservation_id` row, so a
ledger committed before #966 resolves to exactly the row it has always had. That fallback is
reachable ONLY through a resolved join (review-973 L1) — a failed join never reaches it.

**Each evidence row is decoded once per store, not once per lookup (#976).** The recon
resolver asks once per attempt in scope, and the join used to decode every
``FLOW_STEP_ADMITTED``/``ATTEMPT_REQUEST_CREATED`` row on every call — O(rows x attempts) per
fill. :class:`_JoinIndex` keeps the join's maps per store and reads only rows with a larger
``seq`` than the last one it absorbed. That is exact because the store is append-only (its
``entries_no_update``/``entries_no_delete`` triggers) and writes are serialized, so a committed
row never appears below an already-read ``seq``; a ``MAX(seq)`` that went backwards (the file
was replaced under the same store object) drops the index and rebuilds it. A lookup made while
the caller's connection is inside an open transaction bypasses the cache entirely — rows it
can see there may still roll back — and answers from a one-off index, as the old full scan did.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.evidence
.store`` + ``tos_runtime.rcl.projection``/``.reservation_identity`` only. No ``shared.*``, no
write call of any kind (read-only throughout — the negative-grep discipline
:mod:`tos_runtime.recon.service` keeps).
"""

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

#: The two evidence kinds the join reads, as the store holds them (``EvidenceKind`` values —
#: named as plain strings, the kind-is-a-string convention
#: :mod:`tos_runtime.evidence.sinks` already follows).
_FLOW_STEP_ADMITTED = "FLOW_STEP_ADMITTED"
_ATTEMPT_REQUEST_CREATED = "ATTEMPT_REQUEST_CREATED"
#: ``CommitmentStep.ATOMIC_COMMIT``'s own value — the step whose admitted verdict carries the
#: permit identity.
_ATOMIC_COMMIT = "ATOMIC_COMMIT"


def _single(values: set[str]) -> str | None:
    """The one member of ``values``, or ``None`` for none and ``None`` for several.

    Both degenerate cases are ``None`` deliberately: "no flow on record" and "one flow with two
    permit identities" are equally unresolvable, and neither may be narrowed to a pick.
    """
    return next(iter(values)) if len(values) == 1 else None


#: The payload decoder — a module seam so a test can count how many rows a lookup decodes.
_decode = json.loads


@dataclass
class _JoinIndex:
    """The join's two halves, folded from every row with ``seq <= last_seq`` (module docstring).

    Each map holds exactly what the pre-#976 per-call scan derived, so lookups over it return
    the same answers: ``ATTEMPT_REQUEST_CREATED`` rows contribute ``attempt_id <-> event_id``
    pairs, step-9 ``FLOW_STEP_ADMITTED`` rows ``event_id <-> permit identity`` pairs, and a
    row whose id fields are not strings contributes nothing to the map that needs them.
    """

    last_seq: int = -1
    events_by_attempt: dict[str, set[str]] = field(default_factory=dict)
    attempts_by_event: dict[str, set[str]] = field(default_factory=dict)
    permits_by_event: dict[str, set[str]] = field(default_factory=dict)
    events_by_permit: dict[str, set[str]] = field(default_factory=dict)

    def absorb(self, store: SqliteEvidenceStore) -> None:
        """Fold in every row of the two kinds committed after ``last_seq``. All new rows are
        decoded before any map changes, so a decode error leaves the index as it was."""
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


#: One index per live store object (dropped with the store); the lock serializes refresh and
#: read across the store's per-thread connections (#950).
_INDEXES: weakref.WeakKeyDictionary[SqliteEvidenceStore, _JoinIndex] = (
    weakref.WeakKeyDictionary()
)
_INDEX_LOCK = threading.Lock()


def _with_index(store: SqliteEvidenceStore) -> _JoinIndex:
    """The store's index, brought up to the committed tip (module docstring). Callers read it
    under :data:`_INDEX_LOCK`."""
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
    """The Action Flow Permit identity ``attempt_id``'s own flow committed its reservation under.

    Args:
        store: The durable evidence store both joined rows live in.
        attempt_id: The attempt to resolve.

    Returns:
        The permit identity, or ``None`` when the join is empty or ambiguous (module
        docstring's fail-closed rule).
    """
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
    """The attempt id of the flow that committed the reservation named by ``permit_identity``.

    The reverse direction of :func:`permit_identity_for_attempt`, over the same two rows: the
    release consumer needs it to read the *entry* attempt's recorded fill quantity when it is
    deciding whether a close discharged that entry in full.

    Args:
        store: The durable evidence store both joined rows live in.
        permit_identity: The permit identity, e.g. from
            :func:`~tos_runtime.rcl.reservation_identity.permit_identity_of`.

    Returns:
        The attempt id, or ``None`` when the join is empty or ambiguous.
    """
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
    """The reservation id ``attempt_id`` committed against, **only if the log holds that row**.

    Resolution order (module docstring):

    1. the join must resolve. An empty or ambiguous join is ``None`` outright — UNKNOWN/HOLD
       (review-973 L1). It must NOT fall through to the scope row: an attempt this process
       cannot place is exactly the one whose reservation it must not touch, and the scope row
       belongs to whatever other attempt committed it;
    2. the per-attempt id from that permit, when the log holds a reservation under it;
    3. otherwise the pre-#966 scope-level row, when the log holds one — a ledger committed
       before #966 replaying on today's code: its flow evidence resolves normally, but the
       reservation it committed is named by the old scope formula;
    4. otherwise ``None`` — the caller holds.

    The row-existence condition is what keeps this honest in both directions: a resolved id is
    always one the RCL itself has a record for, never a name this function merely spelled.

    Args:
        store: The durable evidence store the permit join reads.
        projection: The reservation projection, asked only whether a row exists.
        account: The compose root's scope account.
        instrument: The compose root's scope instrument.
        attempt_id: The attempt to resolve.

    Returns:
        The reservation id, or ``None``.

    Raises:
        Exception: Whatever ``projection``/``store`` raise on an unreachable store — never
            swallowed into a ``None``, which callers read as "no reservation" rather than
            "could not tell".
    """
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
