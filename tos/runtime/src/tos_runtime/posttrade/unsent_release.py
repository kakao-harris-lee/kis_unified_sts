"""Releasing a reservation whose flow halted after step 9 and before the Send Boundary (#974).

The gap (2026-11-01 unsent-reservation-release plan §1): step 9's ``ATOMIC_COMMIT`` occupies the
scope, steps 10-14 can still halt the flow, and what is left behind is ``NOT_SENT`` — which
:meth:`tos.engine.state.ProvisionalReservationLedger.release` structurally cannot take and which
every later boot's replay faithfully rebuilds (#994). The scope is then sealed for the life of
the leaf: the engine's own step-8 pre-check denies every further attempt, so an open position can
no longer be closed through the engine at all.

Q1 (#1022) gave the kernel its one way out, :meth:`~tos.engine.state.ProvisionalReservationLedger
.discard_unsent`, gated on a typed :class:`~tos.engine.records.UnsentDiscardRef` and on the
reservation's own axes. The kernel reads no evidence store, so it cannot tell "nothing was ever
sent" from "we have no record of a send". **That judgement is this module**, and it is the whole
safety argument: the kernel's gates are necessary, never sufficient.

**What counts as proof that nothing was sent** — plan §3.1, all five, over the ONE flow that
currently occupies the scope (:func:`find_unsent_release_candidate`):

1. ``FLOW_STEP_ADMITTED(step=ATOMIC_COMMIT)`` for this scope — the reservation is this flow's.
   The newest such row is the anchor: it is, by the at-most-one retention, the flow whose
   reservation the ledger holds.
2. a ``FLOW_HALTED`` for that same ``event_id``, after the commit, whose step is one of
   :data:`HALT_STEPS_BEFORE_THE_SEND_BOUNDARY` (10-14). ``TRANSMIT_UNAVAILABLE`` is step 15 and
   ``TRANSMIT_RAISED`` is step 18 — both are OUTSIDE this set, deliberately (see below).
3. not one row of :data:`SEND_EVIDENCE_KINDS` between that commit and the flow's own
   ``EVENT_CONSUMED`` receipt, AND the receipt's own independently-recorded
   :class:`~tos_runtime.engine.flow_fingerprint.FlowFingerprint` says ``handed_off=False`` at
   that same halt step. Two unrelated records, both of which a real hand-off would change.
4. no sign the handling itself was interrupted — the receipt's ``halt_reason`` is not a
   ``HANDLING_INTERRUPTED_*`` one and no ``HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND`` row names
   this event (``tos_runtime.engine.driver``). An interruption means "we do not know whether it
   was sent", which is not the same statement as "it was not sent".
5. an ``EVENT_CONSUMED`` receipt exists at all — the flow was recorded to its end.

Any read that fails or is ambiguous answers "no candidate" (fail-closed, the reservation stays
sealed). **The ledger is never the decision.** It is read twice, for two different jobs: as a
cheap "is there anything to release at all" short-circuit, and — review-1022 item 4 — to confirm
the scope's CURRENT reservation is the very one the evidence judged (same proposal, same attempt
if one was bound) before the kernel is handed a ``proposal_id`` it resolves across every scope.

**The trap this is shaped around** (review-1022 item 3). A store whose only send attempt ended in
``TRANSMIT_RAISED`` has no ``SEND_HANDED_OFF`` row anywhere, so the boot replay rebuilds its
reservation with ``transmit=None`` and leaves it ``ATTEMPT_BOUND``/``NOT_SENT`` — a shape the
kernel's own gates accept. The order may be live at the broker. Condition 2 is what refuses it:
the halt step is 18, not 10-14. Condition 3 refuses it a second time whenever the transport wrote
anything at all. ``tests/posttrade/test_unsent_release.py`` drives exactly that input.

**Order, and what a crash in the middle leaves** (plan §3.3; review-1022 item 5). The RCL release
commits FIRST, the engine discard second. A process that dies in between leaves the RCL at
``RELEASED`` and the engine still holding, which the next boot's pass finishes: it finds the
reservation already ``RELEASED``, skips the RCL step and does the engine half. The reverse order
is never built — an engine projection that forgot a reservation the RCL still holds would admit a
new exposure against capacity the authority has not given back. A repeat after the discard has
already happened finds no outstanding reservation at all and writes nothing, so no second
``RESERVATION_DISCARDED_UNSENT`` row is ever appended for one discard.

**When this runs** (plan §3.3): right after a flow ends, in the same drain pass, through
:meth:`~tos_runtime.engine.driver.EngineDriver.bind_after_turn` — which fires after that event's
own ``EVENT_CONSUMED`` is durable and before the next event is pulled, which is exactly the
window review-1022 item 1 requires the discard row to land in; and once at boot, from
:func:`~tos_runtime.compose._release_wiring.apply_release_wiring`, which is only ever reached
when the boot replay verdict was ``ok`` (a divergence raises ``EngineReplayDiverged`` out of
``_finalize`` first). The same predicate both times.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.canonical``/
``tos.dsl``/``tos.engine``/``tos.rcl`` + ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from tos.canonical import CanonicalizationScheme, derive_id
from tos.dsl import Proposal
from tos.engine.records import InstrumentKey, ProvisionalReservation, UnsentDiscardRef
from tos.engine.state import ProvisionalReservationLedger
from tos.engine.vocabulary import (
    RESERVATION_DISCARDED_UNSENT_KIND,
    CommitmentStep,
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
from tos_runtime.rcl.log import ReservationTransitionRefusal, SqliteCommitLog
from tos_runtime.rcl.projection import ReservationProjectionReader
from tos_runtime.rcl.reservation_identity import permit_reservation_id

__all__ = [
    "CAPACITY_RELEASE_INTENT_KIND",
    "HALT_STEPS_BEFORE_THE_SEND_BOUNDARY",
    "SEND_EVIDENCE_KINDS",
    "UNSENT_RELEASE_CAUSE",
    "UNSENT_RELEASE_COMMAND_PREFIX",
    "UnsentReleaseCandidate",
    "UnsentReleasePass",
    "find_unsent_release_candidate",
    "unsent_release_command_id",
]

#: The five steps that run after step 9's atomic commit and before the Send Boundary (plan §1 F1;
#: ``tos/src/tos/engine/vocabulary.py`` ``COMMITMENT_FLOW_ORDER``). A halt at any of them leaves a
#: committed, never-handed-off reservation. Steps 15-19 are deliberately absent: a halt there
#: (``TRANSMIT_UNAVAILABLE`` at 15, ``TRANSMIT_RAISED`` at 18) is "we do not know", not "not sent".
HALT_STEPS_BEFORE_THE_SEND_BOUNDARY: frozenset[str] = frozenset(
    {
        CommitmentStep.COMMITMENT_UNAVAILABILITY.value,  # 10
        CommitmentStep.ORDER_CONFORMANCE_PROOF.value,  # 11
        CommitmentStep.ATTEMPT_REQUEST.value,  # 12
        CommitmentStep.ATTEMPT_BIND_VERIFICATION.value,  # 13
        CommitmentStep.TRANSMISSION_CAPABILITY.value,  # 14
    }
)

#: Every durable kind whose presence means something left (or may have left) this process for the
#: venue: the sequencer's own post-transmit record, the gateway's seal, and the transport's two
#: (``tos.engine.sequencer``, ``tos.egressgw.gateway``,
#: :mod:`tos_runtime.transport.kis_mock.adapter`). Literals, not imports: three different layers
#: declare them and only two are kernel enum members.
SEND_EVIDENCE_KINDS: tuple[str, ...] = (
    "SEND_HANDED_OFF",
    "SEND_SEALED",
    "TRANSPORT_SEND",
    "TRANSPORT_DRY_RUN",
)

#: The cause carried on this module's ``CAPACITY_RELEASE_INTENT`` row — the SAME string as
#: :attr:`tos.engine.vocabulary.UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION`, which is also the
#: kernel-side reason on the discard ref. It is what tells a later reader that this release rests
#: on an evidence predicate rather than on a post-trade finality proof (there is no proof: nothing
#: was ever executed). :mod:`tos_runtime.posttrade.close_history` reads exactly this string.
UNSENT_RELEASE_CAUSE = UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION.value

#: The RCL idempotency-key prefix for this release path — deliberately NOT
#: :func:`tos_runtime.posttrade.release_consumer.release_command_id`'s ``release-{attempt_id}``
#: spelling, which names an attempt; a never-sent reservation may hold no attempt at all, and the
#: two must stay distinguishable in the committed log (``close_history`` tells them apart by it).
UNSENT_RELEASE_COMMAND_PREFIX = "release-unsent-"

#: Evidence kind appended after the discard — the SAME literal
#: :mod:`tos_runtime.posttrade.release_consumer` defines, redeclared here (not imported) under
#: that module's own lockstep-literal convention, which :mod:`~tos_runtime.posttrade
#: .release_currentness` already follows for the same pair of strings.
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

#: The ``prop-`` prefix :class:`~tos.dsl.Proposal` derives its content-addressed id under
#: (``tos.canonical.derive_id``). Read off the artifact class rather than re-typed, so a prefix
#: change cannot silently desynchronize the id this module reconstructs from the
#: ``EVENT_CONSUMED`` receipt's own ``outcome_digest`` — which is the only place a halted flow's
#: proposal identity survives in durable evidence (no evidence record carries ``proposal_id``).
_PROPOSAL_ID_PREFIX: str = Proposal._ID_PREFIX  # noqa: SLF001


def unsent_release_command_id(reservation_id: str) -> str:
    """The RCL idempotency key of ``reservation_id``'s never-sent release — the ONE spelling."""
    return f"{UNSENT_RELEASE_COMMAND_PREFIX}{reservation_id}"


@dataclass(frozen=True)
class UnsentReleaseCandidate:
    """One flow that plan §3.1's five conditions positively hold for.

    Data only: holding one of these asserts that the EVIDENCE proved nothing was sent, not that
    the release may proceed — :meth:`UnsentReleasePass.run` still has to confirm the scope's
    current reservation is this very one (review-1022 item 4) before the kernel sees it.

    Attributes:
        event_id: The ``DECISION_TICK`` whose handling committed and then halted this flow.
        proposal_id: Reconstructed from the receipt's ``outcome_digest`` (see
            :data:`_PROPOSAL_ID_PREFIX`) — the identity ``discard_unsent`` keys on.
        permit_identity: Step 9's bound Action Flow Permit identity, which is what names this
            reservation in the RCL (:func:`~tos_runtime.rcl.reservation_identity
            .permit_reservation_id`).
        attempt_id: The step-12 attempt, or ``None`` when the flow halted before step 12.
        halt_step: The halting step's own value, one of
            :data:`HALT_STEPS_BEFORE_THE_SEND_BOUNDARY`.
        consumed_evidence_seq: The flow's own ``EVENT_CONSUMED`` seq — recorded so the written
            row's position relative to it is auditable after the fact.
    """

    event_id: str
    proposal_id: str
    permit_identity: str
    attempt_id: str | None
    halt_step: str
    consumed_evidence_seq: int


def find_unsent_release_candidate(
    evidence_store: SqliteEvidenceStore, *, account: str, instrument: str
) -> UnsentReleaseCandidate | None:
    """Plan §3.1's combined predicate over ``account``/``instrument``'s own durable evidence.

    Read-only: this function appends nothing, mutates nothing, and touches neither the RCL nor
    the engine projection.

    Args:
        evidence_store: The durable evidence store the live run recorded into.
        account: The scope account.
        instrument: The scope instrument.

    Returns:
        The judged :class:`UnsentReleaseCandidate`, or ``None`` — which is the answer for "the
        conditions do not hold" and for "the store could not be read" alike (module docstring's
        fail-closed discipline: an unreadable or ambiguous history keeps the reservation sealed).
    """
    try:
        return _candidate(evidence_store, account=account, instrument=instrument)
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        return None


def _candidate(
    evidence_store: SqliteEvidenceStore, *, account: str, instrument: str
) -> UnsentReleaseCandidate | None:
    """:func:`find_unsent_release_candidate`'s body, without the read-failure guard."""
    conn = evidence_store.connection
    commit = _latest_atomic_commit(conn, account=account, instrument=instrument)
    if commit is None:
        return None  # condition 1
    commit_seq, event_id, permit_identity = commit
    consumed = _consumed_receipt(conn, event_id=event_id, after_seq=commit_seq)
    if consumed is None:
        return None  # condition 5
    consumed_seq, receipt = consumed
    halt_step = _pre_send_halt_step(
        conn, event_id=event_id, lo=commit_seq, hi=consumed_seq
    )
    if halt_step is None:
        return None  # condition 2
    if _handling_was_interrupted(conn, event_id=event_id, receipt=receipt):
        return None  # condition 4
    if _send_evidence_between(conn, lo=commit_seq, hi=consumed_seq):
        return None  # condition 3 (durable send records)
    if not _receipt_says_no_hand_off(receipt, halt_step=halt_step):
        return None  # condition 3 (the receipt's own independent fingerprint)
    proposal_id = _proposal_id(receipt)
    if proposal_id is None:
        return None
    return UnsentReleaseCandidate(
        event_id=event_id,
        proposal_id=proposal_id,
        permit_identity=permit_identity,
        attempt_id=_attempt_id(conn, event_id=event_id, lo=commit_seq, hi=consumed_seq),
        halt_step=halt_step,
        consumed_evidence_seq=consumed_seq,
    )


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
    """The newest step-9 commit for this scope: ``(seq, event_id, permit_identity)``.

    The anchor for every other condition. It is the right one by the kernel's own at-most-one
    exposure retention: no second flow can commit on an occupied scope, so the newest recorded
    ``ATOMIC_COMMIT`` is necessarily the flow whose reservation the ledger still holds. A later
    tick that halted at step 8 against that very reservation records no commit of its own and so
    cannot move the anchor — which is precisely the shape #974 leaves behind on every boot.
    """
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
    """``(seq, payload)`` of ``event_id``'s own ``EVENT_CONSUMED`` receipt (condition 5).

    Bounded to receipts newer than this flow's own step-9 commit, which is where its receipt
    necessarily is (the driver appends it after ``core.handle`` returns). That also keeps the
    scan short on a long-lived store, since this runs once per drained turn.
    """
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
    """``event_id``'s halting step, iff it is one of steps 10-14 (condition 2).

    Bounded to ``(lo, hi)`` — the window between this flow's own step-9 commit and its own
    consumption receipt — so a halt belonging to any other flow can never answer for this one.
    """
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
    """Whether ANY :data:`SEND_EVIDENCE_KINDS` row sits in ``(lo, hi)`` (condition 3).

    A window scan rather than a per-kind correlation, and sound for the same documented reason
    :meth:`tos_runtime.engine.driver.EngineDriver._send_evidence_exists_after` relies on: the
    driver is single-threaded and completes one event's whole bookkeeping before pulling the
    next (its ``_draining`` guard makes a re-entrant drain structurally unreachable), so a send
    record between this flow's commit and its consumption receipt can only be this flow's. Two
    of the four kinds — the gateway's seal and the transport's own rows — carry no ``event_id``
    to correlate on at all, which is why the window, not the correlation, is the primitive here.
    """
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
    """The receipt's own flow fingerprint corroborates the halt and the absence of a hand-off.

    A second, independent source for condition 3: the fingerprint is derived from the live
    ``EventResult`` (:mod:`tos_runtime.engine.flow_fingerprint`), not from the evidence rows
    scanned above, and a real hand-off flips ``handed_off`` whatever the sink recorded. A
    receipt carrying no fingerprint at all (a pre-CR6 row) proves nothing and refuses.
    """
    fingerprint = receipt.get("flow_fingerprint")
    if not isinstance(fingerprint, dict):
        return False
    return (
        fingerprint.get("handed_off") is False
        and fingerprint.get("halt_step") == halt_step
    )


def _proposal_id(receipt: dict[str, object]) -> str | None:
    """Reconstruct the halted flow's ``proposal_id`` from its receipt (see :data:`_PROPOSAL_ID_PREFIX`).

    A ``DECISION_TICK``'s ``outcome_digest`` is the emitted Proposal's own canonical digest
    (``tos.engine.core.EventResult.outcome_digest``), and a Proposal is content-addressed, so the
    id is ``derive_id(prefix, digest)`` exactly. The cross-check in :meth:`UnsentReleasePass.run`
    is what makes a wrong reconstruction harmless: it would simply not match the scope's own
    reservation, and nothing would be released.
    """
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


@dataclass(frozen=True)
class UnsentReleasePass:
    """The release action: RCL first, engine second, row only on a ``True`` (module docstring).

    Attributes:
        rcl_log: The durable RCL commit log — the ONE writable RCL handle this pass holds.
        projection: A read-only reservation-projection reader over that SAME log.
        evidence_store: The durable evidence store this pass reads the predicate from and
            appends its two rows to.
        ledger: The engine core's OWN :class:`~tos.engine.state.ProvisionalReservationLedger` —
            never a second, independently-constructed one (the discard has to land on the
            projection the sequencer's step-8 pre-check actually consults).
        scheme: The canonicalization scheme for the RCL command digest.
        account: The single scope account this compose root is bound to.
        instrument: The single scope instrument this compose root is bound to.
    """

    rcl_log: SqliteCommitLog
    projection: ReservationProjectionReader
    evidence_store: SqliteEvidenceStore
    ledger: ProvisionalReservationLedger
    scheme: CanonicalizationScheme
    account: str
    instrument: str

    @property
    def instrument_key(self) -> InstrumentKey:
        """This pass's one scope, as the engine ledger keys it."""
        return InstrumentKey(account=self.account, instrument=self.instrument)

    def __call__(self) -> None:
        """The :meth:`~tos_runtime.engine.driver.EngineDriver.bind_after_turn` callback shape."""
        self.run()

    def run(self) -> bool:
        """Release this scope's reservation iff plan §3.1 positively proves it was never sent.

        Returns:
            ``True`` iff the engine discard was accepted AND its durable row was appended — the
            only outcome that changes anything. ``False`` covers every other case, including the
            ordinary one this is called in most often (nothing outstanding, or an outstanding
            reservation that WAS sent), and is never an error.
        """
        held = self.ledger.outstanding(self.instrument_key)
        if held is None:
            # Nothing to give back. Also the idempotency answer (review-1022 item 5): once the
            # discard has happened, every later call — this process's next turn, or the next
            # boot's pass after the replay re-applied the row — stops here and writes nothing.
            return False
        candidate = find_unsent_release_candidate(
            self.evidence_store, account=self.account, instrument=self.instrument
        )
        if candidate is None or not self._same_reservation(held, candidate):
            return False
        reservation_id = permit_reservation_id(
            self.account, self.instrument, candidate.permit_identity
        )
        state = self._reservation_state(reservation_id)
        if state is None:
            return False
        if state is not CapacityState.RELEASED and not self._commit_rcl_release(
            reservation_id, from_state=state
        ):
            return False
        return self._discard_and_record(candidate, reservation_id=reservation_id)

    def _same_reservation(
        self, held: ProvisionalReservation, candidate: UnsentReleaseCandidate
    ) -> bool:
        """review-1022 item 4 — the scope's CURRENT reservation is the one evidence judged.

        ``discard_unsent`` resolves a ``proposal_id`` across every scope the ledger holds and
        removes the first match (review-1022 LOW-1). This is the caller-side close: the kernel is
        only ever handed a proposal id that this scope's own current reservation carries, with
        the same attempt binding, so a judgement that has gone stale relative to the ledger
        refuses here instead of removing some other entry that happens to share the id.
        """
        return (
            held.instrument_key == self.instrument_key
            and held.proposal_id == candidate.proposal_id
            and held.attempt_id == candidate.attempt_id
        )

    def _reservation_state(self, reservation_id: str) -> CapacityState | None:
        try:
            return self.projection.reservation_state(reservation_id)
        except Exception:  # noqa: BLE001 - an unreadable projection releases nothing
            return None

    def _commit_rcl_release(
        self, reservation_id: str, *, from_state: CapacityState
    ) -> bool:
        """``from_state -> RELEASED`` under ``FINAL_QUANTITY_PROOF`` with a zero committed vector.

        The witness is ``True`` because the predicate above positively established the
        non-execution, which is the only thing a never-sent reservation can ever prove: there is
        no :class:`~tos.posttrade.records.PostTradeFinalityProof` to derive it from, which is why
        :func:`~tos_runtime.rcl.finality_witness.release_reservation` — whose whole job is
        deriving the witness from a proof, and which refuses a ``None`` one — is not the helper
        here; the underlying :meth:`~tos_runtime.rcl.log.SqliteCommitLog
        .apply_reservation_transition` it wraps is, with the same cause and command type the
        release consumer commits a real release under. The committed vector is explicitly EMPTY
        (quantity 0, plan §2 안 A), not ``None``: ``None`` carries the reservation's previous
        vector forward (#972), and the honest statement about an attempt that never left the core
        is that it committed no capacity at all.
        """
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
                        "cause": UNSENT_RELEASE_CAUSE,
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
        """The engine half: discard, then record it — the row ONLY on a ``True``.

        review-1022 items 1 and 2. The row is what a later boot's replay re-applies at this exact
        point in the event order (:mod:`tos_runtime.engine.replay_discards`), so writing one the
        kernel did not accept would make every subsequent boot report a divergence it cannot
        resolve. The ``CAPACITY_RELEASE_INTENT`` row follows it, naming the cause — it is the
        post-trade fact for this scope, which :func:`~tos_runtime.posttrade.release_currentness
        .latest_release_is_conflict_free` reads as a release that proceeded, never as a conflict.
        """
        ref = UnsentDiscardRef(
            proposal_id=candidate.proposal_id,
            reason=UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION,
        )
        if not self.ledger.discard_unsent(ref):
            return False
        self.evidence_store.append(
            ref.model_dump(mode="json"),
            kind=RESERVATION_DISCARDED_UNSENT_KIND,
            record_class=RESERVATION_DISCARDED_UNSENT_KIND,
        )
        self.evidence_store.append(
            {
                "attempt_id": candidate.attempt_id,
                "reservation_id": reservation_id,
                "proof_id": None,
                "destination": CapacityState.RELEASED.value,
                "cause": UNSENT_RELEASE_CAUSE,
                "event_id": candidate.event_id,
                "halt_step": candidate.halt_step,
                "consumed_evidence_seq": candidate.consumed_evidence_seq,
            },
            kind=CAPACITY_RELEASE_INTENT_KIND,
            record_class=CAPACITY_RELEASE_INTENT_KIND,
        )
        return True
