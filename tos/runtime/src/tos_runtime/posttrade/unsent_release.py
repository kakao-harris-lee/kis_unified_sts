"""Releasing a reservation whose flow halted after step 9 and before the Send Boundary (#974)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from tos.canonical import CanonicalizationScheme, derive_id
from tos.dsl import Proposal
from tos.engine.records import InstrumentKey, ProvisionalReservation, UnsentDiscardRef
from tos.engine.state import ProvisionalReservationLedger
from tos.engine.vocabulary import (
    RESERVATION_DISCARDED_UNSENT_KIND,
    CommitmentStep,
    EgressKnowledge,
    UnsentDiscardReason,
)
from tos.rcl import (
    AppendRefusal,
    CapacityReservationTransition,
    CapacityState,
    CapacityVector,
    CommandType,
    ReservationScope,
    TransitionCause,
)

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.uncertain_send import never_accepted_attempt_ids
from tos_runtime.rcl.log import ReservationTransitionRefusal, SqliteCommitLog
from tos_runtime.rcl.projection import ReservationProjectionReader
from tos_runtime.rcl.reservation_identity import permit_reservation_id

__all__ = [
    "CAPACITY_RELEASE_INTENT_KIND",
    "HALT_STEPS_BEFORE_THE_SEND_BOUNDARY",
    "NEVER_ACCEPTED_CAUSE",
    "NEVER_SENT_RELEASE_CAUSES",
    "REFUSED_BEFORE_TRANSPORT_CAUSE",
    "SEND_EVIDENCE_KINDS",
    "TRANSPORT_ENTRY_EVIDENCE_KINDS",
    "UNSENT_RELEASE_CAUSE",
    "UNSENT_RELEASE_COMMAND_PREFIX",
    "UnsentReleaseCandidate",
    "UnsentReleasePass",
    "UnsentReleaseVerdict",
    "evaluate_unsent_release",
    "find_unsent_release_candidate",
    "unsent_release_command_id",
]

HALT_STEPS_BEFORE_THE_SEND_BOUNDARY: frozenset[str] = frozenset(
    {
        CommitmentStep.COMMITMENT_UNAVAILABILITY.value,
        CommitmentStep.ORDER_CONFORMANCE_PROOF.value,
        CommitmentStep.ATTEMPT_REQUEST.value,
        CommitmentStep.ATTEMPT_BIND_VERIFICATION.value,
        CommitmentStep.TRANSMISSION_CAPABILITY.value,
    }
)

SEND_EVIDENCE_KINDS: tuple[str, ...] = (
    "SEND_HANDED_OFF",
    "SEND_SEALED",
    "TRANSPORT_SEND",
    "TRANSPORT_DRY_RUN",
)

UNSENT_RELEASE_CAUSE = UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION.value

REFUSED_BEFORE_TRANSPORT_CAUSE = UnsentDiscardReason.SEND_REFUSED_BEFORE_TRANSPORT.value

NEVER_ACCEPTED_CAUSE = UnsentDiscardReason.UNCERTAIN_SEND_NEVER_ACCEPTED.value

NEVER_SENT_RELEASE_CAUSES: frozenset[str] = frozenset(
    reason.value for reason in UnsentDiscardReason
)

TRANSPORT_ENTRY_EVIDENCE_KINDS: tuple[str, ...] = (
    "SEND_SEALED",
    "SEND_STARTED",
    "POTENTIALLY_LIVE_OBSERVED",
    "NETWORK_CALL_ENTERED",
    "EGRESS_RESULT_RECORDED",
    "UNCERTAIN_SEND",
    "TRANSPORT_SEND",
    "TRANSPORT_DRY_RUN",
    "TRANSPORT_SEND_REFUSED_NO_SEAL",
    "TRANSPORT_BINDING_MISMATCH",
    "EGRESS_RESULT_CONSUMED",
    "RESULT_UNMATCHED",
)

_SEND_REFUSED_KIND = "SEND_REFUSED"
_SEND_HANDED_OFF_KIND = "SEND_HANDED_OFF"
_PRE_CLAIM_REFUSAL_STEP = CommitmentStep.SEND_BOUNDARY_VERIFICATION.value
_UNCERTAIN_RESULT_STEP = CommitmentStep.EVIDENCE_RECORD.value

_DISCARDABLE_CAPACITY_STATES: frozenset[CapacityState] = frozenset(
    {CapacityState.COMMITTED_UNBOUND, CapacityState.ATTEMPT_BOUND}
)

_ATTEMPT_BOUND_DISCARD_REASONS: frozenset[UnsentDiscardReason] = frozenset(
    {
        UnsentDiscardReason.SEND_REFUSED_BEFORE_TRANSPORT,
        UnsentDiscardReason.UNCERTAIN_SEND_NEVER_ACCEPTED,
    }
)

UNSENT_RELEASE_COMMAND_PREFIX = "release-unsent-"

CAPACITY_RELEASE_INTENT_KIND = "CAPACITY_RELEASE_INTENT"

_FLOW_STEP_ADMITTED_KIND = "FLOW_STEP_ADMITTED"
_FLOW_HALTED_KIND = "FLOW_HALTED"
_ATTEMPT_REQUEST_CREATED_KIND = "ATTEMPT_REQUEST_CREATED"
_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"
_HANDLING_INTERRUPTED_PREFIX = "HANDLING_INTERRUPTED"
_HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND_KIND = (
    "HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND"
)
_ATOMIC_COMMIT_STEP = CommitmentStep.ATOMIC_COMMIT.value

_PROPOSAL_ID_PREFIX: str = Proposal._ID_PREFIX  # noqa: SLF001


def unsent_release_command_id(reservation_id: str) -> str:
    """The RCL idempotency key of ``reservation_id``'s never-sent release — the ONE spelling."""
    return f"{UNSENT_RELEASE_COMMAND_PREFIX}{reservation_id}"


@dataclass(frozen=True)
class UnsentReleaseCandidate:
    """One flow that plan §3.1's five conditions positively hold for."""

    event_id: str
    proposal_id: str
    permit_identity: str
    attempt_id: str | None
    halt_step: str
    consumed_evidence_seq: int
    reason: UnsentDiscardReason = UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION


@dataclass(frozen=True)
class UnsentReleaseVerdict:
    """The §3.1 answer, plus whether anything could still change it (review-1023 M2)."""

    candidate: UnsentReleaseCandidate | None
    final: bool


_UNDECIDED = UnsentReleaseVerdict(candidate=None, final=False)


def find_unsent_release_candidate(
    evidence_store: SqliteEvidenceStore, *, account: str, instrument: str
) -> UnsentReleaseCandidate | None:
    """Plan §3.1's combined predicate over ``account``/``instrument``'s own durable evidence."""
    return evaluate_unsent_release(
        evidence_store, account=account, instrument=instrument
    ).candidate


def evaluate_unsent_release(
    evidence_store: SqliteEvidenceStore, *, account: str, instrument: str
) -> UnsentReleaseVerdict:
    """:func:`find_unsent_release_candidate`, plus the settledness bit a cache needs."""
    try:
        return _verdict(evidence_store, account=account, instrument=instrument)
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        return _UNDECIDED


def _verdict(
    evidence_store: SqliteEvidenceStore, *, account: str, instrument: str
) -> UnsentReleaseVerdict:
    """:func:`evaluate_unsent_release`'s body, without the read-failure guard."""
    conn = evidence_store.connection
    commit = _latest_atomic_commit(conn, account=account, instrument=instrument)
    if commit is None:
        return _UNDECIDED
    commit_seq, event_id, permit_identity = commit
    consumed = _consumed_receipt(conn, event_id=event_id, after_seq=commit_seq)
    if consumed is None:
        return _UNDECIDED
    consumed_seq, receipt = consumed
    settled = _settled(None)
    halt_step = _pre_send_halt_step(
        conn, event_id=event_id, lo=commit_seq, hi=consumed_seq
    )
    if halt_step is None:
        handed_off = _handed_off_attempt_id(
            conn, receipt, event_id=event_id, lo=commit_seq, hi=consumed_seq
        )
        if handed_off is None or _handling_was_interrupted(
            conn, event_id=event_id, receipt=receipt
        ):
            return settled
        return _settled(
            _refused_before_transport(
                conn,
                event_id=event_id,
                permit_identity=permit_identity,
                receipt=receipt,
                attempt_id=handed_off,
                lo=commit_seq,
                hi=consumed_seq,
            )
            or _uncertain_send_never_accepted(
                evidence_store,
                event_id=event_id,
                permit_identity=permit_identity,
                receipt=receipt,
                attempt_id=handed_off,
                consumed_seq=consumed_seq,
            )
        )
    if _handling_was_interrupted(conn, event_id=event_id, receipt=receipt):
        return settled
    if _send_evidence_between(conn, lo=commit_seq, hi=consumed_seq):
        return settled
    if not _receipt_says_no_hand_off(receipt, halt_step=halt_step):
        return settled
    proposal_id = _proposal_id(receipt)
    if proposal_id is None:
        return settled
    return _settled(
        UnsentReleaseCandidate(
            event_id=event_id,
            proposal_id=proposal_id,
            permit_identity=permit_identity,
            attempt_id=_attempt_id(
                conn, event_id=event_id, lo=commit_seq, hi=consumed_seq
            ),
            halt_step=halt_step,
            consumed_evidence_seq=consumed_seq,
        )
    )


def _handed_off_attempt_id(
    conn: sqlite3.Connection,
    receipt: dict[str, object],
    *,
    event_id: str,
    lo: int,
    hi: int,
) -> str | None:
    """The attempt a flow that halted at no step handed off, corroborated by its own step 12."""
    fingerprint = receipt.get("flow_fingerprint")
    if not isinstance(fingerprint, dict) or fingerprint.get("handed_off") is not True:
        return None
    if fingerprint.get("halt_step") is not None or receipt.get("halt_reason"):
        return None
    attempt_id = fingerprint.get("attempt_id")
    if not isinstance(attempt_id, str) or not attempt_id:
        return None
    if _attempt_id(conn, event_id=event_id, lo=lo, hi=hi) != attempt_id:
        return None
    return attempt_id


def _uncertain_send_never_accepted(
    evidence_store: SqliteEvidenceStore,
    *,
    event_id: str,
    permit_identity: str,
    receipt: dict[str, object],
    attempt_id: str,
    consumed_seq: int,
) -> UnsentReleaseCandidate | None:
    """A send the broker's own order history proved it never accepted (11-20 (e))."""
    if attempt_id not in never_accepted_attempt_ids(evidence_store):
        return None
    proposal_id = _proposal_id(receipt)
    if proposal_id is None:
        return None
    return UnsentReleaseCandidate(
        event_id=event_id,
        proposal_id=proposal_id,
        permit_identity=permit_identity,
        attempt_id=attempt_id,
        halt_step=_UNCERTAIN_RESULT_STEP,
        consumed_evidence_seq=consumed_seq,
        reason=UnsentDiscardReason.UNCERTAIN_SEND_NEVER_ACCEPTED,
    )


def _refused_before_transport(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    permit_identity: str,
    receipt: dict[str, object],
    attempt_id: str,
    lo: int,
    hi: int,
) -> UnsentReleaseCandidate | None:
    """A handed-off flow whose attempt the gateway refused before any transport call (11-20)."""
    if not _only_pre_claim_refusals(conn, attempt_id=attempt_id, lo=lo, hi=hi):
        return None
    if _transport_evidence(conn, attempt_id=attempt_id, lo=lo, hi=hi):
        return None
    handed = [
        _payload(payload_json).get("attempt_id")
        for (payload_json,) in conn.execute(
            "SELECT payload_json FROM entries WHERE kind = ? AND seq > ? AND seq < ?",
            (_SEND_HANDED_OFF_KIND, lo, hi),
        )
    ]
    if handed != [attempt_id]:
        return None
    proposal_id = _proposal_id(receipt)
    if proposal_id is None:
        return None
    return UnsentReleaseCandidate(
        event_id=event_id,
        proposal_id=proposal_id,
        permit_identity=permit_identity,
        attempt_id=attempt_id,
        halt_step=_PRE_CLAIM_REFUSAL_STEP,
        consumed_evidence_seq=hi,
        reason=UnsentDiscardReason.SEND_REFUSED_BEFORE_TRANSPORT,
    )


def _only_pre_claim_refusals(
    conn: sqlite3.Connection, *, attempt_id: str, lo: int, hi: int
) -> bool:
    """At least one ``SEND_REFUSED`` in the flow, every one for this attempt, at step 15, before"""
    refusals = [
        _payload(payload_json)
        for (payload_json,) in conn.execute(
            "SELECT payload_json FROM entries WHERE kind = ? AND seq > ? AND seq < ?",
            (_SEND_REFUSED_KIND, lo, hi),
        )
    ]
    return bool(refusals) and all(
        refusal.get("attempt_id") == attempt_id
        and refusal.get("step") == _PRE_CLAIM_REFUSAL_STEP
        and refusal.get("preserved_worst_credible_capacity") is None
        and refusal.get("preserved_obligation_magnitude_unknown") is False
        for refusal in refusals
    )


def _transport_evidence(
    conn: sqlite3.Connection, *, attempt_id: str, lo: int, hi: int
) -> bool:
    """Any :data:`TRANSPORT_ENTRY_EVIDENCE_KINDS` row inside the flow, or naming the attempt."""
    placeholders = ",".join("?" for _ in TRANSPORT_ENTRY_EVIDENCE_KINDS)
    for seq, payload_json in conn.execute(
        f"SELECT seq, payload_json FROM entries WHERE kind IN ({placeholders})",
        TRANSPORT_ENTRY_EVIDENCE_KINDS,
    ):
        if lo < int(seq) < hi or _payload(payload_json).get("attempt_id") == attempt_id:
            return True
    return False


def _settled(candidate: UnsentReleaseCandidate | None) -> UnsentReleaseVerdict:
    """A verdict reached with the anchor's receipt in hand — see :class:`UnsentReleaseVerdict`."""
    return UnsentReleaseVerdict(candidate=candidate, final=True)


def _payload(payload_json: str) -> dict[str, object]:
    decoded = json.loads(payload_json)
    payload = decoded.get("payload") if isinstance(decoded, dict) else None
    if not isinstance(payload, dict):
        raise ValueError("evidence payload is malformed")
    return payload


def _in_scope(payload: dict[str, object], *, account: str, instrument: str) -> bool:
    key = payload.get("instrument_key")
    if not isinstance(key, dict):
        return False
    return key.get("account") == account and key.get("instrument") == instrument


def _latest_atomic_commit(
    conn: sqlite3.Connection, *, account: str, instrument: str
) -> tuple[int, str, str] | None:
    """The newest step-9 commit for this scope: ``(seq, event_id, permit_identity)``."""
    for seq, payload_json in conn.execute(
        "SELECT seq, payload_json FROM entries WHERE kind = ? ORDER BY seq DESC",
        (_FLOW_STEP_ADMITTED_KIND,),
    ):
        payload = _payload(payload_json)
        if payload.get("step") != _ATOMIC_COMMIT_STEP:
            continue
        if not _in_scope(payload, account=account, instrument=instrument):
            continue
        event_id = payload.get("event_id")
        permit_identity = payload.get("bound_identity")
        if not isinstance(event_id, str) or not event_id:
            return None
        if not isinstance(permit_identity, str) or not permit_identity:
            return None
        return int(seq), event_id, permit_identity
    return None


def _consumed_receipt(
    conn: sqlite3.Connection, *, event_id: str, after_seq: int
) -> tuple[int, dict[str, object]] | None:
    """``(seq, payload)`` of ``event_id``'s own ``EVENT_CONSUMED`` receipt (condition 5)."""
    for seq, payload_json in conn.execute(
        "SELECT seq, payload_json FROM entries WHERE kind = ? AND seq > ? "
        "ORDER BY seq ASC",
        (_EVENT_CONSUMED_KIND, after_seq),
    ):
        payload = _payload(payload_json)
        if payload.get("event_id") == event_id:
            return int(seq), payload
    return None


def _pre_send_halt_step(
    conn: sqlite3.Connection, *, event_id: str, lo: int, hi: int
) -> str | None:
    """``event_id``'s halting step, iff it is one of steps 10-14 (condition 2)."""
    for (payload_json,) in conn.execute(
        "SELECT payload_json FROM entries WHERE kind = ? AND seq > ? AND seq < ? "
        "ORDER BY seq ASC",
        (_FLOW_HALTED_KIND, lo, hi),
    ):
        payload = _payload(payload_json)
        if payload.get("event_id") != event_id:
            continue
        step = payload.get("step")
        if not isinstance(step, str) or step not in HALT_STEPS_BEFORE_THE_SEND_BOUNDARY:
            return None
        return step
    return None


def _send_evidence_between(conn: sqlite3.Connection, *, lo: int, hi: int) -> bool:
    """Whether ANY :data:`SEND_EVIDENCE_KINDS` row sits in ``(lo, hi)`` (condition 3)."""
    placeholders = ",".join("?" for _ in SEND_EVIDENCE_KINDS)
    row = conn.execute(
        f"SELECT 1 FROM entries WHERE kind IN ({placeholders}) AND seq > ? AND seq < ? LIMIT 1",
        (*SEND_EVIDENCE_KINDS, lo, hi),
    ).fetchone()
    return row is not None


def _handling_was_interrupted(
    conn: sqlite3.Connection, *, event_id: str, receipt: dict[str, object]
) -> bool:
    """Whether this event's handling was durably marked interrupted (condition 4)."""
    halt_reason = receipt.get("halt_reason")
    if isinstance(halt_reason, str) and halt_reason.startswith(
        _HANDLING_INTERRUPTED_PREFIX
    ):
        return True
    for (payload_json,) in conn.execute(
        "SELECT payload_json FROM entries WHERE kind = ?",
        (_HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND_KIND,),
    ):
        if _payload(payload_json).get("event_id") == event_id:
            return True
    return False


def _receipt_says_no_hand_off(receipt: dict[str, object], *, halt_step: str) -> bool:
    """The receipt's own flow fingerprint corroborates the halt and the absence of a hand-off."""
    fingerprint = receipt.get("flow_fingerprint")
    if not isinstance(fingerprint, dict):
        return False
    return (
        fingerprint.get("handed_off") is False
        and fingerprint.get("halt_step") == halt_step
    )


def _proposal_id(receipt: dict[str, object]) -> str | None:
    """Reconstruct the halted flow's ``proposal_id`` from its receipt (see :data:`_PROPOSAL_ID_PREFIX`)."""
    digest = receipt.get("outcome_digest")
    if not isinstance(digest, str) or not digest:
        return None
    return derive_id(_PROPOSAL_ID_PREFIX, digest)


def _attempt_id(
    conn: sqlite3.Connection, *, event_id: str, lo: int, hi: int
) -> str | None:
    """``event_id``'s step-12 attempt id, or ``None`` when the flow halted before step 12."""
    for (payload_json,) in conn.execute(
        "SELECT payload_json FROM entries WHERE kind = ? AND seq > ? AND seq < ? "
        "ORDER BY seq ASC",
        (_ATTEMPT_REQUEST_CREATED_KIND, lo, hi),
    ):
        payload = _payload(payload_json)
        if payload.get("event_id") != event_id:
            continue
        attempt_id = payload.get("attempt_id")
        return attempt_id if isinstance(attempt_id, str) and attempt_id else None
    return None


def _awaits_broker_verdict(held: ProvisionalReservation) -> bool:
    """Whether a ``final`` verdict for ``held`` can still be overturned by a LATER row."""
    return held.capacity_state is CapacityState.QUARANTINED_UNKNOWN


@dataclass(frozen=True)
class UnsentReleasePass:
    """The release action: RCL first, engine second, row only on a ``True`` (module docstring)."""

    rcl_log: SqliteCommitLog
    projection: ReservationProjectionReader
    evidence_store: SqliteEvidenceStore
    ledger: ProvisionalReservationLedger
    scheme: CanonicalizationScheme
    account: str
    instrument: str
    _verdict_cache: dict[
        tuple[str | None, str | None], tuple[int | None, UnsentReleaseVerdict]
    ] = field(default_factory=dict, init=False, repr=False, compare=False)

    @property
    def instrument_key(self) -> InstrumentKey:
        """This pass's one scope, as the engine ledger keys it."""
        return InstrumentKey(account=self.account, instrument=self.instrument)

    def __call__(self) -> None:
        """The :meth:`~tos_runtime.engine.driver.EngineDriver.bind_after_turn` callback shape."""
        self.run()

    def run(self) -> bool:
        """Release this scope's reservation iff plan §3.1 positively proves it was never sent."""
        held = self.ledger.outstanding(self.instrument_key)
        if held is None:
            return False
        candidate = self._candidate_for(held)
        if candidate is None or not self._same_reservation(held, candidate):
            return False
        reservation_id = permit_reservation_id(
            self.account, self.instrument, candidate.permit_identity
        )
        state = self._reservation_state(reservation_id)
        if state is None:
            return False
        if state is not CapacityState.RELEASED and not self._commit_rcl_release(
            reservation_id, from_state=state, cause=candidate.reason.value
        ):
            return False
        return self._discard_and_record(candidate, reservation_id=reservation_id)

    def _candidate_for(
        self, held: ProvisionalReservation
    ) -> UnsentReleaseCandidate | None:
        """:func:`evaluate_unsent_release` for ``held``, computed at most once (review-1023 M2)."""
        key = (held.proposal_id, held.attempt_id)
        cached = self._verdict_cache.get(key)
        if cached is not None:
            tip, verdict = cached
            final = verdict.final and not _awaits_broker_verdict(held)
            if final or tip == self._evidence_tip():
                return verdict.candidate
        verdict = evaluate_unsent_release(
            self.evidence_store, account=self.account, instrument=self.instrument
        )
        self._verdict_cache.clear()
        self._verdict_cache[key] = (self._evidence_tip(), verdict)
        return verdict.candidate

    def _evidence_tip(self) -> int | None:
        """The evidence store's newest ``seq``, or ``None`` when it cannot be read."""
        try:
            row = self.evidence_store.connection.execute(
                "SELECT MAX(seq) FROM entries"
            ).fetchone()
        except sqlite3.Error:
            return None
        return None if row is None or row[0] is None else int(row[0])

    def _same_reservation(
        self, held: ProvisionalReservation, candidate: UnsentReleaseCandidate
    ) -> bool:
        """review-1022 item 4 — the scope's CURRENT reservation is the one evidence judged."""
        return (
            held.instrument_key == self.instrument_key
            and held.proposal_id == candidate.proposal_id
            and held.attempt_id == candidate.attempt_id
            and self._ledger_still_admits_a_discard(held, candidate.reason)
        )

    @staticmethod
    def _ledger_still_admits_a_discard(
        held: ProvisionalReservation, reason: UnsentDiscardReason
    ) -> bool:
        """review-1023 LOW-1 — the kernel's own two axes, read BEFORE the irreversible RCL write."""
        if reason is UnsentDiscardReason.UNCERTAIN_SEND_NEVER_ACCEPTED:
            return (
                held.knowledge is EgressKnowledge.UNKNOWN
                and held.capacity_state is CapacityState.QUARANTINED_UNKNOWN
            )
        if reason is UnsentDiscardReason.SEND_REFUSED_BEFORE_TRANSPORT:
            return (
                held.knowledge is EgressKnowledge.SENT_UNCONFIRMED
                and held.capacity_state is CapacityState.POTENTIALLY_LIVE
            )
        return (
            held.knowledge is EgressKnowledge.NOT_SENT
            and held.capacity_state in _DISCARDABLE_CAPACITY_STATES
        )

    def _reservation_state(self, reservation_id: str) -> CapacityState | None:
        try:
            return self.projection.reservation_state(reservation_id)
        except Exception:  # noqa: BLE001 - an unreadable projection releases nothing
            return None

    def _commit_rcl_release(
        self,
        reservation_id: str,
        *,
        from_state: CapacityState,
        cause: str = UNSENT_RELEASE_CAUSE,
    ) -> bool:
        """``from_state -> RELEASED`` under ``FINAL_QUANTITY_PROOF`` with a zero committed vector."""
        try:
            view = self.rcl_log.read_linearizable(
                writer_epoch=self.rcl_log.current_epoch()
            )
        except Exception:  # noqa: BLE001 - an unreadable/stale tip releases nothing
            return False
        transition = CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=view.epoch,
            from_state=from_state,
            to_state=CapacityState.RELEASED,
            scope=ReservationScope(account=self.account, instrument=self.instrument),
            committed_vector=CapacityVector(),
        )
        try:
            receipt = self.rcl_log.apply_reservation_transition(
                transition,
                TransitionCause.FINAL_QUANTITY_PROOF,
                command_type=CommandType.RELEASE_RESERVATION,
                command_id=unsent_release_command_id(reservation_id),
                command_digest=self.scheme.compute_digest(
                    {
                        "reservation_id": reservation_id,
                        "to_state": CapacityState.RELEASED.value,
                        "cause": cause,
                    }
                ),
                expected_seq=-1 if view.last_seq is None else view.last_seq,
                finality_witness=True,
            )
        except ReservationTransitionRefusal:
            return False
        return not isinstance(receipt, AppendRefusal)

    def _discard_and_record(
        self, candidate: UnsentReleaseCandidate, *, reservation_id: str
    ) -> bool:
        """The engine half: discard, then record it — the row ONLY on a ``True``."""
        ref = UnsentDiscardRef(
            proposal_id=candidate.proposal_id,
            reason=candidate.reason,
            attempt_id=(
                candidate.attempt_id
                if candidate.reason in _ATTEMPT_BOUND_DISCARD_REASONS
                else None
            ),
        )
        if not self.ledger.discard_unsent(ref):
            return False
        self.evidence_store.append(
            ref.model_dump(mode="json", exclude_none=True),
            kind=RESERVATION_DISCARDED_UNSENT_KIND,
            record_class=RESERVATION_DISCARDED_UNSENT_KIND,
        )
        self._append_intent(candidate, reservation_id=reservation_id)
        return True

    def finish_interrupted_intent(self) -> bool:
        """Boot only: write the ``CAPACITY_RELEASE_INTENT`` a crash lost after the discard row."""
        try:
            conn = self.evidence_store.connection
            last = conn.execute(
                "SELECT seq, payload_json FROM entries WHERE kind = ? "
                "ORDER BY seq DESC LIMIT 1",
                (RESERVATION_DISCARDED_UNSENT_KIND,),
            ).fetchone()
            if last is None:
                return False
            discard_seq, discard_json = last
            candidate = evaluate_unsent_release(
                self.evidence_store, account=self.account, instrument=self.instrument
            ).candidate
            if candidate is None or (
                candidate.proposal_id != _payload(discard_json).get("proposal_id")
            ):
                return False
            reservation_id = permit_reservation_id(
                self.account, self.instrument, candidate.permit_identity
            )
            if self._reservation_state(reservation_id) is not CapacityState.RELEASED:
                return False
            for (payload_json,) in conn.execute(
                "SELECT payload_json FROM entries WHERE kind = ? AND seq > ?",
                (CAPACITY_RELEASE_INTENT_KIND, int(discard_seq)),
            ):
                if _payload(payload_json).get("reservation_id") == reservation_id:
                    return False
        except (sqlite3.Error, ValueError, TypeError, KeyError):
            return False
        self._append_intent(candidate, reservation_id=reservation_id)
        return True

    def _append_intent(
        self, candidate: UnsentReleaseCandidate, *, reservation_id: str
    ) -> None:
        self.evidence_store.append(
            {
                "attempt_id": candidate.attempt_id,
                "reservation_id": reservation_id,
                "proof_id": None,
                "destination": CapacityState.RELEASED.value,
                "cause": candidate.reason.value,
                "event_id": candidate.event_id,
                "halt_step": candidate.halt_step,
                "consumed_evidence_seq": candidate.consumed_evidence_seq,
            },
            kind=CAPACITY_RELEASE_INTENT_KIND,
            record_class=CAPACITY_RELEASE_INTENT_KIND,
        )
