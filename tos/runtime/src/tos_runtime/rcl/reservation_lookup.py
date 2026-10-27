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
actually holds a row for, and falls back to the scope-level
:func:`~tos_runtime.rcl.reservation_identity.scope_reservation_id` row when one exists, so a
ledger committed before #966 resolves to exactly the row it has always had.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.evidence
.store`` + ``tos_runtime.rcl.projection``/``.reservation_identity`` only. No ``shared.*``, no
write call of any kind (read-only throughout — the negative-grep discipline
:mod:`tos_runtime.recon.service` keeps).
"""

from __future__ import annotations

import json

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


def _payloads(store: SqliteEvidenceStore, kind: str) -> list[dict[str, object]]:
    """Every row of ``kind``, oldest first, unwrapped to its own payload mapping.

    Reads the store's own public ``connection`` property — the same read-only seam
    :mod:`tos_runtime.recon.witness_synthetic` and :mod:`tos_runtime.evidence.backup` already
    use, since the store exposes no "entries by kind, with payload" accessor of its own.
    """
    rows = store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
    ).fetchall()
    payloads: list[dict[str, object]] = []
    for (payload_json,) in rows:
        decoded = json.loads(payload_json).get("payload")
        if isinstance(decoded, dict):
            payloads.append(decoded)
    return payloads


def _single(values: set[str]) -> str | None:
    """The one member of ``values``, or ``None`` for none and ``None`` for several.

    Both degenerate cases are ``None`` deliberately: "no flow on record" and "one flow with two
    permit identities" are equally unresolvable, and neither may be narrowed to a pick.
    """
    return next(iter(values)) if len(values) == 1 else None


def _event_ids_of_attempt(store: SqliteEvidenceStore, attempt_id: str) -> set[str]:
    """The ``event_id``s whose flow created ``attempt_id`` (normally exactly one)."""
    return {
        str(payload["event_id"])
        for payload in _payloads(store, _ATTEMPT_REQUEST_CREATED)
        if payload.get("attempt_id") == attempt_id
        and isinstance(payload.get("event_id"), str)
    }


def _committed_permits(store: SqliteEvidenceStore) -> list[tuple[str, str]]:
    """Every ``(event_id, permit_identity)`` a step-9 commit was admitted under."""
    pairs: list[tuple[str, str]] = []
    for payload in _payloads(store, _FLOW_STEP_ADMITTED):
        if payload.get("step") != _ATOMIC_COMMIT:
            continue
        event_id = payload.get("event_id")
        permit_identity = payload.get("bound_identity")
        if isinstance(event_id, str) and isinstance(permit_identity, str):
            pairs.append((event_id, permit_identity))
    return pairs


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
    event_ids = _event_ids_of_attempt(store, attempt_id)
    if not event_ids:
        return None
    return _single(
        {
            permit_identity
            for event_id, permit_identity in _committed_permits(store)
            if event_id in event_ids
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
    event_ids = {
        event_id
        for event_id, committed in _committed_permits(store)
        if committed == permit_identity
    }
    if not event_ids:
        return None
    return _single(
        {
            str(payload["attempt_id"])
            for payload in _payloads(store, _ATTEMPT_REQUEST_CREATED)
            if payload.get("event_id") in event_ids
            and isinstance(payload.get("attempt_id"), str)
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

    1. the per-attempt id from the permit join, when the log holds a reservation under it;
    2. otherwise the pre-#966 scope-level row, when the log holds one (an old ledger replaying
       on today's code);
    3. otherwise ``None`` — the caller holds.

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
    if permit_identity is not None:
        candidate = permit_reservation_id(account, instrument, permit_identity)
        if projection.reservation_state(candidate) is not None:
            return candidate
    legacy = scope_reservation_id(account, instrument)
    if projection.reservation_state(legacy) is not None:
        return legacy
    return None
