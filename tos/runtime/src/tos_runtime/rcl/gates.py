"""``SqliteCommitLog`` pre-insert gates + replay-fold helpers (design #40 D2.1)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from enum import StrEnum
from typing import Any

from tos.canonical import CanonicalizationScheme
from tos.rcl import (
    AppendRefusal,
    AppendRefusalReason,
    CapacityReservationTransition,
    CapacityState,
    CapacityVector,
    CommandType,
    CommitEntry,
    ReservationScope,
    TransitionCause,
    duplicate_command,
    release_admissible,
    reservation_transition_structurally_legal,
    transition_allowed,
)

__all__ = [
    "INITIAL_RESERVATION_STATES",
    "UNRECORDED_VECTOR",
    "align_unrecorded_vectors",
    "ReservationRefusalReason",
    "ReservationTransitionRefusal",
    "check_reservation_from_state",
    "classify_duplicate_command",
    "committed_vector_payload",
    "digest_of_reservation_map",
    "existing_command_row",
    "fold_reservations_from_entries",
    "held_reservation_map",
    "reservation_committed_vector",
    "reservation_rows",
    "reservation_lifecycle_refusal",
    "reservation_transition_payload_json",
    "row_to_commit_entry",
    "upsert_reservation_projection",
]

UNRECORDED_VECTOR = "UNRECORDED_BEFORE_B1"

INITIAL_RESERVATION_STATES: frozenset[CapacityState] = frozenset(
    {CapacityState.COMMITTED_UNBOUND}
)


def existing_command_row(
    conn: sqlite3.Connection, command_id: str
) -> tuple[bool, str | None]:
    """Return ``(row_exists, stored_digest)`` — never collapses "no row" into ``None``."""
    row = conn.execute(
        "SELECT command_digest FROM entries WHERE command_id = ?", (command_id,)
    ).fetchone()
    if row is None:
        return False, None
    return True, row[0]


def classify_duplicate_command(
    row_exists: bool,
    existing_digest: str | None,
    attempted_digest: str | None,
) -> AppendRefusalReason | None:
    """Classify a repeat ``command_id`` against the stored digest (MEDIUM-3 fix)."""
    if not row_exists:
        return None
    if existing_digest is None and attempted_digest is None:
        return AppendRefusalReason.DUPLICATE_COMMAND_ID
    if existing_digest is None or attempted_digest is None:
        return AppendRefusalReason.COMMAND_BYTES_MISMATCH
    return duplicate_command(existing_digest, attempted_digest)


def check_reservation_from_state(
    conn: sqlite3.Connection,
    reservation_id: str,
    claimed_from_state: CapacityState,
) -> AppendRefusal | None:
    """Refuse a transition whose claimed ``from_state`` disagrees with the held record."""
    held_row = conn.execute(
        "SELECT state FROM reservations WHERE reservation_id = ?",
        (reservation_id,),
    ).fetchone()
    if held_row is None:
        if claimed_from_state in INITIAL_RESERVATION_STATES:
            return None
        return AppendRefusal(
            reason=AppendRefusalReason.INTEGRITY_VIOLATION,
            detail=(
                f"reservation {reservation_id!r} has no held state yet — only an "
                "initial lifecycle state "
                f"({sorted(s.value for s in INITIAL_RESERVATION_STATES)}) may "
                f"originate a transition, but the claimed from_state="
                f"{claimed_from_state} is not one (fail-closed: a transition "
                "cannot originate from a state that was never held)"
            ),
        )
    held_state = CapacityState(held_row[0])
    if held_state != claimed_from_state:
        return AppendRefusal(
            reason=AppendRefusalReason.INTEGRITY_VIOLATION,
            detail=(
                f"reservation {reservation_id!r} is actually held at {held_state}, "
                f"but the caller claimed from_state={claimed_from_state} — a stale "
                "or mistaken claim must never be admitted (fail-closed; "
                "ADR-002-012 :37 no automatic re-arm; cf. "
                "tos.engine.state.ProvisionalReservationLedger._store's own "
                "forward-only held-state check, engine/state.py lines 219-233)"
            ),
        )
    return None


def fold_reservations_from_entries(
    conn: sqlite3.Connection,
) -> dict[str, dict[str, str | None]]:
    """Re-derive the final reservation-state map by replaying every entry."""
    rows = conn.execute(
        "SELECT payload_json FROM entries WHERE is_reservation_transition = 1 "
        "ORDER BY seq ASC"
    ).fetchall()
    folded: dict[str, dict[str, str | None]] = {}
    for (payload_json,) in rows:
        payload = json.loads(payload_json)
        reservation_id = payload.get("reservation_id")
        to_state = payload.get("to_state")
        scope = payload.get("scope") or {}
        scope_account = scope.get("account")
        scope_instrument = scope.get("instrument")
        if (
            reservation_id is not None
            and to_state is not None
            and scope_account is not None
            and scope_instrument is not None
        ):
            raw_vector = payload.get("committed_vector")
            if "committed_vector" not in payload:
                vector: str | None = UNRECORDED_VECTOR
            elif raw_vector is None:
                prior = folded.get(reservation_id)
                vector = None if prior is None else prior["committed_vector"]
            else:
                vector = _normalized_vector(json.dumps(raw_vector))
            folded[reservation_id] = {
                "state": to_state,
                "scope_account": scope_account,
                "scope_instrument": scope_instrument,
                "committed_vector": vector,
            }
    return folded


def align_unrecorded_vectors(
    held: dict[str, dict[str, str | None]],
    replayed: Mapping[str, Mapping[str, str | None]],
) -> None:
    """Exclude from the comparison the vector of every reservation whose latest folded entry"""
    for reservation_id, value in replayed.items():
        if (
            value.get("committed_vector") == UNRECORDED_VECTOR
            and reservation_id in held
        ):
            held[reservation_id]["committed_vector"] = UNRECORDED_VECTOR


def held_reservation_map(conn: sqlite3.Connection) -> dict[str, dict[str, str | None]]:
    """The held ``reservations`` table in :func:`fold_reservations_from_entries`'s map shape —"""
    rows = conn.execute(
        "SELECT reservation_id, state, scope_account, scope_instrument, "
        "committed_vector_json FROM reservations"
    ).fetchall()
    return {
        reservation_id: {
            "state": state,
            "scope_account": scope_account,
            "scope_instrument": scope_instrument,
            "committed_vector": _normalized_vector(vector_json),
        }
        for reservation_id, state, scope_account, scope_instrument, vector_json in rows
    }


def committed_vector_payload(committed_vector: CapacityVector | None) -> Any:
    """The ``payload_json`` form of a transition's ``committed_vector`` — the same JSON the"""
    if committed_vector is None:
        return None
    return json.loads(committed_vector.model_dump_json())


def reservation_transition_payload_json(
    transition: CapacityReservationTransition,
    cause: TransitionCause,
    finality_witness: bool | None,
) -> str:
    """The ``payload_json`` of one reservation-lifecycle entry — what"""
    assert transition.scope is not None
    assert transition.from_state is not None and transition.to_state is not None
    return json.dumps(
        {
            "reservation_id": transition.reservation_id,
            "from_state": transition.from_state.value,
            "to_state": transition.to_state.value,
            "cause": cause.value,
            "finality_witness": finality_witness,
            "committed_vector": committed_vector_payload(transition.committed_vector),
            "scope": {
                "account": transition.scope.account,
                "instrument": transition.scope.instrument,
            },
        },
        sort_keys=True,
    )


def _normalized_vector(vector_json: str | None) -> str | None:
    """One comparable form per vector for both replay sides: ``None`` stays ``None``; anything"""
    if vector_json is None:
        return None
    try:
        return CapacityVector.model_validate_json(vector_json).model_dump_json()
    except ValueError:
        return f"UNPARSEABLE:{vector_json}"


def digest_of_reservation_map(
    scheme: CanonicalizationScheme, mapping: Mapping[str, Mapping[str, str | None]]
) -> str:
    """Canonical digest of a ``{reservation_id: {state, scope_account,"""
    return scheme.compute_digest(
        {
            "reservations": {
                reservation_id: dict(sorted(value.items()))
                for reservation_id, value in sorted(mapping.items())
            }
        }
    )


class ReservationRefusalReason(StrEnum):
    """Runtime-local (NOT the kernel's closed) reservation-lifecycle refusal reasons."""

    NOT_STRUCTURALLY_LEGAL = "NOT_STRUCTURALLY_LEGAL"
    CAUSE_NOT_ADMISSIBLE = "CAUSE_NOT_ADMISSIBLE"
    FINALITY_WITNESS_REQUIRED = "FINALITY_WITNESS_REQUIRED"


class ReservationTransitionRefusal(RuntimeError):
    """Raised by :meth:`~tos_runtime.rcl.log.SqliteCommitLog.apply_reservation_transition`"""

    def __init__(self, reason: ReservationRefusalReason, detail: str = "") -> None:
        super().__init__(f"reservation transition refused: {reason} {detail}".strip())
        self.reason = reason


def reservation_lifecycle_refusal(
    transition: CapacityReservationTransition,
    cause: TransitionCause,
    finality_witness: bool | None,
) -> tuple[ReservationRefusalReason, str] | None:
    """Evaluate the three kernel reservation-lifecycle gates, in order."""
    from_state = transition.from_state
    to_state = transition.to_state
    if not reservation_transition_structurally_legal(from_state, to_state):
        return (
            ReservationRefusalReason.NOT_STRUCTURALLY_LEGAL,
            f"({from_state} -> {to_state}) is not on the closed whitelist",
        )
    if (
        from_state is None
        or to_state is None
        or not transition_allowed(from_state, to_state, cause)
    ):
        return (
            ReservationRefusalReason.CAUSE_NOT_ADMISSIBLE,
            f"cause {cause} does not authorize ({from_state} -> {to_state})",
        )
    if not release_admissible(transition, finality_witness):
        return (
            ReservationRefusalReason.FINALITY_WITNESS_REQUIRED,
            f"destination {to_state} requires finality_witness is True",
        )
    return None


def row_to_commit_entry(row: tuple[Any, ...]) -> CommitEntry:
    """Build a :class:`~tos.rcl.CommitEntry` from one ``entries`` row."""
    seq, writer_epoch, command_id, command_digest, kind, payload_digest = row
    return CommitEntry(
        seq=seq,
        writer_epoch=writer_epoch,
        command_id=command_id,
        command_digest=command_digest,
        kind=CommandType(kind) if kind is not None else None,
        payload_digest=payload_digest,
    )


def reservation_rows(
    conn: sqlite3.Connection,
) -> Iterator[tuple[str, CapacityState, int, ReservationScope]]:
    """Yield every held ``(reservation_id, state, last_seq, scope)`` — the projection's read"""
    rows = conn.execute(
        "SELECT reservation_id, state, last_seq, scope_account, "
        "scope_instrument FROM reservations ORDER BY reservation_id ASC"
    ).fetchall()
    for reservation_id, state, last_seq, scope_account, scope_instrument in rows:
        yield (
            reservation_id,
            CapacityState(state),
            int(last_seq),
            ReservationScope(account=scope_account, instrument=scope_instrument),
        )


_ReservationUpsert = (
    tuple[str, CapacityState, CapacityState, ReservationScope, CapacityVector | None]
    | None
)


def upsert_reservation_projection(
    conn: sqlite3.Connection, *, next_seq: int, reservation_update: _ReservationUpsert
) -> None:
    """``UPSERT`` the ``reservations`` row for ``reservation_update``, a no-op when ``None``."""
    if reservation_update is None:
        return
    reservation_id, _claimed_from_state, to_state, scope, committed_vector = (
        reservation_update
    )
    committed_vector_json = (
        None if committed_vector is None else committed_vector.model_dump_json()
    )
    conn.execute(
        "INSERT INTO reservations (reservation_id, state, last_seq, "
        "scope_account, scope_instrument, committed_vector_json) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(reservation_id) DO UPDATE SET "
        "state=excluded.state, last_seq=excluded.last_seq, "
        "scope_account=excluded.scope_account, "
        "scope_instrument=excluded.scope_instrument, "
        "committed_vector_json=COALESCE(excluded.committed_vector_json, "
        "reservations.committed_vector_json)",
        (
            reservation_id,
            to_state.value,
            next_seq,
            scope.account,
            scope.instrument,
            committed_vector_json,
        ),
    )


def reservation_committed_vector(
    conn: sqlite3.Connection, reservation_id: str
) -> CapacityVector | None:
    """The committed Capacity Vector last written for ``reservation_id``, if any (kernel round"""
    row = conn.execute(
        "SELECT committed_vector_json FROM reservations WHERE reservation_id = ?",
        (reservation_id,),
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return CapacityVector.model_validate_json(row[0])
