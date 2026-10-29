"""Fail-closed reconstruction of completed close quantities for one RCL entry.

The scope's mutable reservation projection cannot answer which attempts were committed between
an entry and a close. This reader uses the RCL's discriminated transition history, replays the
complete scope, joins each later reservation through its own permit to one attempt, and only
counts an attempt with a final FULL_FILL receipt plus its own committed RELEASED transition.
Prior attempts must also carry durable evidence naming the entry reservation they discharged or
held against; scope coincidence alone never attaches a close to an entry.

No store is mutated. Any missing, ambiguous, malformed, cross-scope, or unproven fact returns a
typed refusal and no usable quantity. In particular, a cancel or partial attempt without a
proven terminal FULL_FILL remains held and cannot be treated as zero or skipped.

Firewall: stdlib + ``tos.engine``/``tos.rcl`` + ``tos_runtime.evidence``/``.rcl``/``.recon`` only.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from tos.engine.vocabulary import EgressResultKind
from tos.rcl import CapacityState, CommandType, TransitionCause

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import (
    ReservationTransitionHistory,
    ReservationTransitionRecord,
    SqliteCommitLog,
)
from tos_runtime.rcl.reservation_identity import permit_identity_of
from tos_runtime.rcl.reservation_lookup import (
    attempt_id_for_reservation,
    permit_identity_for_attempt,
)

__all__ = [
    "CloseHistoryRefusal",
    "CloseHistoryResult",
    "durable_close_history",
]

_RELEASE_INTENT_KIND = "CAPACITY_RELEASE_INTENT"
_RELEASE_HELD_KIND = "CAPACITY_RELEASE_HELD"
_RELEASE_COMMAND_PREFIX = "release-"
_FINAL_QUANTITY_PROOF = TransitionCause.FINAL_QUANTITY_PROOF
_RELEASED = CapacityState.RELEASED
_POSITION_CONSUMED = CapacityState.POSITION_CONSUMED
_COMMITTED_UNBOUND = CapacityState.COMMITTED_UNBOUND
_EGRESS_RESULT_KINDS = ("EGRESS_RESULT_CONSUMED", "RESULT_UNMATCHED")
_FINALITY_PROOF_KIND = "POSTTRADE_FINALITY_PROOF"
_FINALITY_PROOF_PREFIXES = ("synthetic-fqp-proof:", "broker-fqp-proof:")


class CloseHistoryRefusal(StrEnum):
    """Closed reasons the durable close history cannot produce a quantity."""

    RCL_HISTORY_UNAVAILABLE = "RCL_HISTORY_UNAVAILABLE"
    RCL_HISTORY_INVALID = "RCL_HISTORY_INVALID"
    ENTRY_IDENTITY_UNPROVEN = "ENTRY_IDENTITY_UNPROVEN"
    ENTRY_FILL_UNPROVEN = "ENTRY_FILL_UNPROVEN"
    SCOPE_HISTORY_INVALID = "SCOPE_HISTORY_INVALID"
    ENTRY_NOT_SOLE_CONSUMED = "ENTRY_NOT_SOLE_CONSUMED"
    CLOSED_OVER_ENTRY = "CLOSED_OVER_ENTRY"
    CURRENT_ATTEMPT_UNPROVEN = "CURRENT_ATTEMPT_UNPROVEN"
    RESERVATION_IDENTITY_UNPROVEN = "RESERVATION_IDENTITY_UNPROVEN"
    ATTEMPT_IDENTITY_UNPROVEN = "ATTEMPT_IDENTITY_UNPROVEN"
    ATTEMPT_NOT_DISTINCT = "ATTEMPT_NOT_DISTINCT"
    FILL_UNPROVEN = "FILL_UNPROVEN"
    RELEASE_UNPROVEN = "RELEASE_UNPROVEN"
    ENTRY_BINDING_UNPROVEN = "ENTRY_BINDING_UNPROVEN"
    ENTRY_BINDING_AMBIGUOUS = "ENTRY_BINDING_AMBIGUOUS"


@dataclass(frozen=True)
class CloseHistoryResult:
    """Proven entry and close magnitudes, or a refusal with every quantity absent."""

    entry_attempt_id: str | None
    entry_quantity: Decimal | None
    prior_quantity: Decimal | None
    current_quantity: Decimal | None
    total_quantity: Decimal | None
    rcl_writer_epoch: int | None
    rcl_last_seq: int | None
    refusal: CloseHistoryRefusal | None

    @property
    def proven(self) -> bool:
        """Whether every required history fact was positively established."""
        return self.refusal is None


@dataclass(frozen=True)
class _ReleaseEvidence:
    attempt_id: str
    reservation_id: str
    kind: str
    reason: str | None
    destination: str | None
    proof_id: str | None


@dataclass(frozen=True)
class _ReceiptObservation:
    attempt_id: str | None
    account: str | None
    instrument: str | None
    egress_result_kind: str | None
    filled_quantity: Decimal | None
    remaining_quantity: Decimal | None
    finality_proof_recorded: bool


@dataclass(frozen=True)
class _ScopeContext:
    snapshot: ReservationTransitionHistory
    current_reservation_id: str | None
    candidate_ids: tuple[str, ...]


def _refused(
    reason: CloseHistoryRefusal, *, entry_attempt_id: str | None = None
) -> CloseHistoryResult:
    return CloseHistoryResult(
        entry_attempt_id=entry_attempt_id,
        entry_quantity=None,
        prior_quantity=None,
        current_quantity=None,
        total_quantity=None,
        rcl_writer_epoch=None,
        rcl_last_seq=None,
        refusal=reason,
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _as_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (str, int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    return None


def _evidence_payload(payload_json: object) -> dict[str, Any]:
    if not isinstance(payload_json, str):
        raise ValueError("evidence JSON is not text")
    decoded = json.loads(payload_json, object_pairs_hook=_strict_object)
    payload = decoded.get("payload", decoded) if isinstance(decoded, dict) else None
    if not isinstance(payload, dict):
        raise ValueError("evidence payload is malformed")
    return payload


def _read_all_receipts(
    store: SqliteEvidenceStore,
) -> tuple[_ReceiptObservation, ...] | None:
    """Read all result receipts so an attempt cannot hide a conflicting foreign scope."""
    placeholders = ",".join("?" for _ in _EGRESS_RESULT_KINDS)
    try:
        receipt_rows = store.connection.execute(
            f"SELECT kind, payload_json FROM entries WHERE kind IN ({placeholders}) "
            "ORDER BY seq ASC",
            _EGRESS_RESULT_KINDS,
        ).fetchall()
        proof_rows = store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            (_FINALITY_PROOF_KIND,),
        ).fetchall()
    except sqlite3.Error:
        return None
    try:
        proven: set[str] = set()
        for (payload_json,) in proof_rows:
            payload = _evidence_payload(payload_json)
            key = payload.get("idempotency_key")
            if not isinstance(key, str):
                continue
            for prefix in _FINALITY_PROOF_PREFIXES:
                if key.startswith(prefix):
                    proven.add(key[len(prefix) :])
        observations: list[_ReceiptObservation] = []
        for _kind, payload_json in receipt_rows:
            payload = _evidence_payload(payload_json)
            attempt = payload.get("attempt_id")
            attempt_id = attempt if isinstance(attempt, str) and attempt else None
            instrument_key = payload.get("instrument_key")
            account = (
                instrument_key.get("account")
                if isinstance(instrument_key, dict)
                else None
            )
            instrument = (
                instrument_key.get("instrument")
                if isinstance(instrument_key, dict)
                else None
            )
            result_kind = payload.get("egress_result_kind")
            observations.append(
                _ReceiptObservation(
                    attempt_id=attempt_id,
                    account=account if isinstance(account, str) else None,
                    instrument=instrument if isinstance(instrument, str) else None,
                    egress_result_kind=(
                        result_kind if isinstance(result_kind, str) else None
                    ),
                    filled_quantity=_as_decimal(payload.get("filled_quantity")),
                    remaining_quantity=_as_decimal(payload.get("remaining_quantity")),
                    finality_proof_recorded=(
                        attempt_id is not None and attempt_id in proven
                    ),
                )
            )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return tuple(observations)


def _release_evidence(store: SqliteEvidenceStore) -> tuple[_ReleaseEvidence, ...]:
    """Read and strictly decode release records through the store's public connection."""
    rows = store.connection.execute(
        "SELECT kind, payload_json FROM entries WHERE kind IN (?, ?) ORDER BY seq ASC",
        (_RELEASE_INTENT_KIND, _RELEASE_HELD_KIND),
    ).fetchall()
    decoded: list[_ReleaseEvidence] = []
    for kind, payload_json in rows:
        value = json.loads(payload_json, object_pairs_hook=_strict_object)
        payload = value.get("payload") if isinstance(value, dict) else None
        if not isinstance(payload, dict):
            raise ValueError("release evidence payload is malformed")
        attempt_id = payload.get("attempt_id")
        reservation_id = payload.get("reservation_id")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise ValueError("release evidence has no attempt id")
        if reservation_id is not None and (
            not isinstance(reservation_id, str) or not reservation_id
        ):
            raise ValueError("release evidence reservation id is malformed")
        if reservation_id is None:
            decoded.append(
                _ReleaseEvidence(
                    attempt_id=attempt_id,
                    reservation_id="",
                    kind=kind,
                    reason=(
                        payload.get("reason")
                        if isinstance(payload.get("reason"), str)
                        else None
                    ),
                    destination=(
                        payload.get("destination")
                        if isinstance(payload.get("destination"), str)
                        else None
                    ),
                    proof_id=(
                        payload.get("proof_id")
                        if isinstance(payload.get("proof_id"), str)
                        else None
                    ),
                )
            )
            continue
        reason = payload.get("reason")
        destination = payload.get("destination")
        proof_id = payload.get("proof_id")
        if kind == _RELEASE_HELD_KIND and (not isinstance(reason, str) or not reason):
            raise ValueError("release hold has no reason")
        if kind == _RELEASE_INTENT_KIND and (
            not isinstance(destination, str)
            or not destination
            or not isinstance(proof_id, str)
            or not proof_id
        ):
            raise ValueError("release intent has no destination or proof id")
        decoded.append(
            _ReleaseEvidence(
                attempt_id=attempt_id,
                reservation_id=reservation_id,
                kind=kind,
                reason=reason if isinstance(reason, str) else None,
                destination=destination if isinstance(destination, str) else None,
                proof_id=proof_id if isinstance(proof_id, str) else None,
            )
        )
    return tuple(decoded)


def _final_full_fill_quantity(
    rows: tuple[_ReceiptObservation, ...],
    *,
    attempt_id: str,
    account: str,
    instrument: str,
) -> Decimal | None:
    """Return only one unambiguous terminal FULL_FILL quantity for ``attempt_id``."""
    matching = tuple(row for row in rows if row.attempt_id == attempt_id)
    if not matching:
        return None
    if any(row.account != account or row.instrument != instrument for row in matching):
        return None
    terminal = matching[-1]
    if terminal.egress_result_kind != EgressResultKind.FULL_FILL.value:
        return None
    if terminal.filled_quantity is None or terminal.remaining_quantity is None:
        return None
    try:
        quantity = Decimal(terminal.filled_quantity)
        remaining = Decimal(terminal.remaining_quantity)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not quantity.is_finite() or quantity <= 0 or remaining != 0:
        return None
    # A repeated terminal receipt is safe to dedupe only when every FULL_FILL says the same
    # final quantity. A later/earlier conflicting terminal magnitude is ambiguous, not a pick.
    full_fills = tuple(
        row
        for row in matching
        if row.egress_result_kind == EgressResultKind.FULL_FILL.value
    )
    for row in full_fills:
        if (
            row.filled_quantity is None
            or row.remaining_quantity is None
            or row.finality_proof_recorded is not True
        ):
            return None
        try:
            if (
                Decimal(row.filled_quantity) != quantity
                or Decimal(row.remaining_quantity) != 0
            ):
                return None
        except (InvalidOperation, TypeError, ValueError):
            return None
    if not full_fills or terminal.finality_proof_recorded is not True:
        return None
    return quantity


def _release_proven(
    transitions: tuple[ReservationTransitionRecord, ...],
    evidence: tuple[_ReleaseEvidence, ...],
    *,
    reservation_id: str,
    attempt_id: str,
    account: str,
    instrument: str,
) -> bool:
    command_id = f"{_RELEASE_COMMAND_PREFIX}{attempt_id}"
    releases = tuple(
        row
        for row in transitions
        if row.reservation_id == reservation_id and row.to_state is _RELEASED
    )
    if len(releases) != 1:
        return False
    transition = releases[0]
    if (
        transition.command_id != command_id
        or transition.kind is not CommandType.RELEASE_RESERVATION
        or transition.cause is not _FINAL_QUANTITY_PROOF
        or transition.finality_witness is not True
        or transition.scope.account != account
        or transition.scope.instrument != instrument
    ):
        return False
    intents = tuple(
        row
        for row in evidence
        if row.kind == _RELEASE_INTENT_KIND
        and row.attempt_id == attempt_id
        and row.reservation_id == reservation_id
    )
    proofs = {
        row.proof_id
        for row in intents
        if row.destination == _RELEASED.value and row.proof_id
    }
    # An intent with a different destination or no proof makes the attempt's release record
    # ambiguous even when one other intent looks usable.
    return (
        bool(intents)
        and all(row.destination == _RELEASED.value and row.proof_id for row in intents)
        and len(proofs) == 1
    )


def _entry_binding_proven(
    evidence: tuple[_ReleaseEvidence, ...],
    *,
    attempt_id: str,
    reservation_id: str,
    entry_reservation_id: str,
) -> tuple[bool, bool]:
    """Return ``(bound, ambiguous)`` from the attempt's durable release outcomes."""
    rows = tuple(row for row in evidence if row.attempt_id == attempt_id)
    if any(not row.reservation_id for row in rows):
        return False, True
    foreign_ids = {
        row.reservation_id
        for row in rows
        if row.reservation_id not in {reservation_id, entry_reservation_id}
    }
    if foreign_ids:
        return False, True
    parent_rows = tuple(
        row for row in rows if row.reservation_id == entry_reservation_id
    )
    parent_proofs = {
        row.proof_id
        for row in parent_rows
        if row.kind == _RELEASE_INTENT_KIND and row.proof_id
    }
    if len(parent_proofs) > 1:
        return False, True
    valid_parent_row = bool(parent_rows) and all(
        (row.kind == _RELEASE_HELD_KIND and bool(row.reason))
        or (
            row.kind == _RELEASE_INTENT_KIND
            and row.destination == _RELEASED.value
            and bool(row.proof_id)
        )
        for row in parent_rows
    )
    return valid_parent_row, False


def _attempt_for_reservation(
    evidence_store: SqliteEvidenceStore,
    *,
    reservation_id: str,
    account: str,
    instrument: str,
) -> str | None:
    permit_identity = permit_identity_of(
        reservation_id, account=account, instrument=instrument
    )
    if permit_identity is None:
        return None
    try:
        attempt_id = attempt_id_for_reservation(evidence_store, permit_identity)
        if attempt_id is None:
            return None
        # The inverse join alone can return this attempt even when another durable event binds
        # that same attempt to a different permit. Require the forward lookup to resolve back to
        # this exact permit before counting the reservation.
        if permit_identity_for_attempt(evidence_store, attempt_id) != permit_identity:
            return None
        return attempt_id
    except Exception:  # noqa: BLE001 - malformed/unreadable join is not evidence
        return None


def _scope_history(
    transitions: tuple[ReservationTransitionRecord, ...],
    *,
    account: str,
    instrument: str,
) -> tuple[
    tuple[ReservationTransitionRecord, ...],
    dict[str, set[tuple[str, str]]],
    dict[str, int],
]:
    """Check target-scope transition chains and retain global scope identity for each id."""
    scopes_by_id: dict[str, set[tuple[str, str]]] = {}
    rows: list[ReservationTransitionRecord] = []
    for row in transitions:
        scopes_by_id.setdefault(row.reservation_id, set()).add(
            (row.scope.account, row.scope.instrument)
        )
        if row.scope.account == account and row.scope.instrument == instrument:
            rows.append(row)
    first_seq: dict[str, int] = {}
    state_by_id: dict[str, CapacityState] = {}
    for row in rows:
        held = state_by_id.get(row.reservation_id)
        if held is None:
            if row.from_state is not _COMMITTED_UNBOUND:
                raise ValueError(
                    "reservation history does not start at COMMITTED_UNBOUND"
                )
            first_seq[row.reservation_id] = row.seq
        elif row.from_state is not held:
            raise ValueError("reservation history from_state disagrees with replay")
        state_by_id[row.reservation_id] = row.to_state
    return tuple(rows), scopes_by_id, first_seq


def _current_boundary(
    evidence_store: SqliteEvidenceStore,
    *,
    current_attempt_id: str | None,
    current_reservation_id: str | None,
    first_seq: dict[str, int],
    scopes_by_id: dict[str, set[tuple[str, str]]],
    entry_seq: int,
    last_seq: int | None,
    account: str,
    instrument: str,
) -> tuple[int | None, str | None] | None:
    """Resolve an explicit current attempt to its exact committed reservation boundary."""
    if current_attempt_id is None or current_reservation_id is None:
        return last_seq, None
    if scopes_by_id.get(current_reservation_id) != {(account, instrument)}:
        return None
    if (
        _attempt_for_reservation(
            evidence_store,
            reservation_id=current_reservation_id,
            account=account,
            instrument=instrument,
        )
        != current_attempt_id
    ):
        return None
    seq = first_seq.get(current_reservation_id)
    if seq is None or seq <= entry_seq:
        return None
    return seq, current_reservation_id


def _candidate_ids(
    first_seq: dict[str, int], *, entry_seq: int, boundary_seq: int | None
) -> tuple[str, ...]:
    if boundary_seq is None:
        return ()
    return tuple(
        reservation_id
        for reservation_id, seq in sorted(first_seq.items(), key=lambda item: item[1])
        if entry_seq < seq <= boundary_seq
    )


def _entry_was_only_position(
    rows: tuple[ReservationTransitionRecord, ...],
    *,
    candidate_ids: tuple[str, ...],
    first_seq: dict[str, int],
    entry_reservation_id: str,
    boundary_seq: int | None,
) -> bool:
    """Replay exact pre-commit scope state for each candidate and the final boundary."""
    candidates_at = {first_seq[rid]: rid for rid in candidate_ids}
    state: dict[str, CapacityState] = {}
    for row in rows:
        if boundary_seq is not None and row.seq > boundary_seq:
            break
        candidate_id = candidates_at.get(row.seq)
        if candidate_id is not None:
            consumed = {
                rid for rid, current in state.items() if current is _POSITION_CONSUMED
            }
            if row.reservation_id != candidate_id or consumed != {entry_reservation_id}:
                return False
        state[row.reservation_id] = row.to_state
    return state.get(entry_reservation_id) is _POSITION_CONSUMED


def _prove_candidates(
    evidence_store: SqliteEvidenceStore,
    *,
    candidate_ids: tuple[str, ...],
    current_reservation_id: str | None,
    current_attempt_id: str | None,
    entry_attempt_id: str,
    entry_reservation_id: str,
    account: str,
    instrument: str,
    transitions: tuple[ReservationTransitionRecord, ...],
    receipt_rows: tuple[_ReceiptObservation, ...],
    release_evidence: tuple[_ReleaseEvidence, ...],
) -> tuple[Decimal, Decimal | None] | CloseHistoryRefusal:
    """Prove each later reservation and sum only the distinct final close quantities."""
    seen_attempts = {entry_attempt_id}
    prior_total = Decimal(0)
    current_quantity: Decimal | None = None
    for reservation_id in candidate_ids:
        attempt_id = _attempt_for_reservation(
            evidence_store,
            reservation_id=reservation_id,
            account=account,
            instrument=instrument,
        )
        if attempt_id is None:
            return CloseHistoryRefusal.ATTEMPT_IDENTITY_UNPROVEN
        if attempt_id in seen_attempts:
            return CloseHistoryRefusal.ATTEMPT_NOT_DISTINCT
        seen_attempts.add(attempt_id)
        if (
            reservation_id == current_reservation_id
            and attempt_id != current_attempt_id
        ):
            return CloseHistoryRefusal.CURRENT_ATTEMPT_UNPROVEN
        quantity = _final_full_fill_quantity(
            receipt_rows,
            attempt_id=attempt_id,
            account=account,
            instrument=instrument,
        )
        if quantity is None:
            return CloseHistoryRefusal.FILL_UNPROVEN
        reservation_transitions = tuple(
            row for row in transitions if row.reservation_id == reservation_id
        )
        if not _release_proven(
            reservation_transitions,
            release_evidence,
            reservation_id=reservation_id,
            attempt_id=attempt_id,
            account=account,
            instrument=instrument,
        ):
            return CloseHistoryRefusal.RELEASE_UNPROVEN
        bound, ambiguous = _entry_binding_proven(
            release_evidence,
            attempt_id=attempt_id,
            reservation_id=reservation_id,
            entry_reservation_id=entry_reservation_id,
        )
        if ambiguous:
            return CloseHistoryRefusal.ENTRY_BINDING_AMBIGUOUS
        if reservation_id != current_reservation_id and not bound:
            return CloseHistoryRefusal.ENTRY_BINDING_UNPROVEN
        if reservation_id == current_reservation_id:
            current_quantity = quantity
        else:
            prior_total += quantity
    if current_reservation_id is not None and current_quantity is None:
        return CloseHistoryRefusal.CURRENT_ATTEMPT_UNPROVEN
    return prior_total, current_quantity


def _entry_attempt(
    evidence_store: SqliteEvidenceStore,
    *,
    entry_reservation_id: str,
    account: str,
    instrument: str,
) -> str | None:
    """Resolve the entry only through its own per-permit durable identity join."""
    return _attempt_for_reservation(
        evidence_store,
        reservation_id=entry_reservation_id,
        account=account,
        instrument=instrument,
    )


def _scope_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    *,
    entry_reservation_id: str,
    current_attempt_id: str | None,
    current_reservation_id: str | None,
    account: str,
    instrument: str,
) -> _ScopeContext | CloseHistoryRefusal:
    """Load and validate the complete RCL history window for this entry and close."""
    try:
        snapshot = rcl_log.reservation_transition_history(
            writer_epoch=rcl_log.current_epoch()
        )
    except Exception:  # noqa: BLE001 - unreadable/stale/corrupt history must hold
        return CloseHistoryRefusal.RCL_HISTORY_UNAVAILABLE
    try:
        rows, scopes_by_id, first_seq = _scope_history(
            snapshot.transitions, account=account, instrument=instrument
        )
    except Exception:  # noqa: BLE001 - invalid replay cannot prove scope history
        return CloseHistoryRefusal.SCOPE_HISTORY_INVALID
    if scopes_by_id.get(entry_reservation_id) != {(account, instrument)}:
        return CloseHistoryRefusal.ENTRY_IDENTITY_UNPROVEN
    entry_seq = first_seq.get(entry_reservation_id)
    if entry_seq is None:
        return CloseHistoryRefusal.ENTRY_IDENTITY_UNPROVEN
    boundary = _current_boundary(
        evidence_store,
        current_attempt_id=current_attempt_id,
        current_reservation_id=current_reservation_id,
        first_seq=first_seq,
        scopes_by_id=scopes_by_id,
        entry_seq=entry_seq,
        last_seq=snapshot.last_seq,
        account=account,
        instrument=instrument,
    )
    if boundary is None:
        return CloseHistoryRefusal.CURRENT_ATTEMPT_UNPROVEN
    boundary_seq, current_id = boundary
    candidates = _candidate_ids(
        first_seq, entry_seq=entry_seq, boundary_seq=boundary_seq
    )
    if any(
        scopes_by_id.get(reservation_id) != {(account, instrument)}
        for reservation_id in candidates
    ):
        return CloseHistoryRefusal.RESERVATION_IDENTITY_UNPROVEN
    if current_id is not None and current_id not in candidates:
        return CloseHistoryRefusal.CURRENT_ATTEMPT_UNPROVEN
    if not _entry_was_only_position(
        rows,
        candidate_ids=candidates,
        first_seq=first_seq,
        entry_reservation_id=entry_reservation_id,
        boundary_seq=boundary_seq,
    ):
        return CloseHistoryRefusal.ENTRY_NOT_SOLE_CONSUMED
    return _ScopeContext(
        snapshot=snapshot,
        current_reservation_id=current_id,
        candidate_ids=candidates,
    )


def _entry_proof(
    evidence_store: SqliteEvidenceStore,
    *,
    entry_reservation_id: str,
    account: str,
    instrument: str,
) -> tuple[str, Decimal, tuple[_ReceiptObservation, ...]] | None:
    """Resolve the entry's attempt and final fill from exact-scope evidence."""
    attempt_id = _entry_attempt(
        evidence_store,
        entry_reservation_id=entry_reservation_id,
        account=account,
        instrument=instrument,
    )
    if attempt_id is None:
        return None
    receipt_rows = _read_all_receipts(evidence_store)
    if receipt_rows is None:
        return None
    quantity = _final_full_fill_quantity(
        receipt_rows,
        attempt_id=attempt_id,
        account=account,
        instrument=instrument,
    )
    return None if quantity is None else (attempt_id, quantity, receipt_rows)


def durable_close_history(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    *,
    account: str,
    instrument: str,
    entry_reservation_id: str,
    current_attempt_id: str | None = None,
    current_reservation_id: str | None = None,
) -> CloseHistoryResult:
    """Reconstruct proven completed closes attached to ``entry_reservation_id``.

    With no current IDs, every later reservation in scope is treated as a prior candidate and
    must be proven. For post-trade discharge, pass both current IDs: that exact reservation is
    included in ``current_quantity`` and may not yet have an entry-specific HELD/INTENT outcome
    because this call is deciding whether to write one. The current reservation still needs its
    own terminal FULL_FILL, release intent, and committed RCL release transition.

    Returns a refusal with all quantities set to ``None`` if any reservation committed after the
    entry cannot be proven as a distinct completed close linked to this entry. Reads one fenced
    RCL history snapshot and never accesses a private RCL connection or writes either store.
    """
    if bool(current_attempt_id) != bool(current_reservation_id):
        return _refused(CloseHistoryRefusal.CURRENT_ATTEMPT_UNPROVEN)
    context = _scope_context(
        rcl_log,
        evidence_store,
        entry_reservation_id=entry_reservation_id,
        current_attempt_id=current_attempt_id,
        current_reservation_id=current_reservation_id,
        account=account,
        instrument=instrument,
    )
    if isinstance(context, CloseHistoryRefusal):
        return _refused(context)
    entry_proof = _entry_proof(
        evidence_store,
        entry_reservation_id=entry_reservation_id,
        account=account,
        instrument=instrument,
    )
    if entry_proof is None:
        return _refused(CloseHistoryRefusal.ENTRY_FILL_UNPROVEN)
    entry_attempt_id, entry_quantity, receipt_rows = entry_proof
    try:
        release_evidence = _release_evidence(evidence_store)
    except Exception:  # noqa: BLE001 - malformed/unreadable release proof must hold
        return _refused(
            CloseHistoryRefusal.RELEASE_UNPROVEN, entry_attempt_id=entry_attempt_id
        )
    totals = _prove_candidates(
        evidence_store,
        candidate_ids=context.candidate_ids,
        current_reservation_id=context.current_reservation_id,
        current_attempt_id=current_attempt_id,
        entry_attempt_id=entry_attempt_id,
        entry_reservation_id=entry_reservation_id,
        account=account,
        instrument=instrument,
        transitions=context.snapshot.transitions,
        receipt_rows=receipt_rows,
        release_evidence=release_evidence,
    )
    if isinstance(totals, CloseHistoryRefusal):
        return _refused(totals, entry_attempt_id=entry_attempt_id)
    prior_total, current_quantity = totals
    current_total = Decimal(0) if current_quantity is None else current_quantity
    total = prior_total + current_total
    if total > entry_quantity:
        return _refused(
            CloseHistoryRefusal.CLOSED_OVER_ENTRY, entry_attempt_id=entry_attempt_id
        )
    return CloseHistoryResult(
        entry_attempt_id=entry_attempt_id,
        entry_quantity=entry_quantity,
        prior_quantity=prior_total,
        current_quantity=current_total,
        total_quantity=total,
        rcl_writer_epoch=context.snapshot.writer_epoch,
        rcl_last_seq=context.snapshot.last_seq,
        refusal=None,
    )
