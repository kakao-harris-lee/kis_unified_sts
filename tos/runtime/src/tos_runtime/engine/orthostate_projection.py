"""``OrthostateProjector`` — TOS Phase 3 Wave 2 Lane C-R (plan §2.2 "커널 결합").

For each ``EGRESS_RESULT`` the driver consumes, this projector derives the proposed
ADR-002-005 :class:`~tos.orthostate.records.CompositeState` via the kernel adapter
(:func:`tos.engine.orthostate_projection.composite_state_for` /
:func:`~tos.engine.orthostate_projection.result_transition_for`, landed by kernel round KW2-C2 —
this module writes against exactly those two names, per the wave-2 dispatch), checks §12
ownership legality for the one dimension this projector can genuinely fail (see
"Ownership check, narrowed" below) plus cross-dimension coupling
(:func:`tos.orthostate.coupling_violations`), and durably keeps the LAST composite per attempt
(:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.record_composite` /
:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.last_composite`) so a restart resumes from a
conservative reconstruction (:func:`tos.orthostate.reconstruct_conservative`) of the last known
composite.

**Actor stand-in (disclosed, synthetic single-process runtime).** ADR-002-005 §12 splits
Broker-Order / Knowledge / Attempt-send-boundary ownership across three DISTINCT roles (Broker
Adapter Evidence, Reconciliation Service, Broker Adapter Egress) that in a real multi-process
deployment would be separate services with their own identity. This compose root has no such
separate processes on the SYNTHETIC paper path — the synthetic gateway and this projector are
the only things that ever touch this data — so this projector checks ownership using
:data:`_ATTEMPT_EGRESS_ACTOR` as a FIXED constant, standing in for the single synthetic-runtime
process that plays all three roles. A real multi-process deployment (Phase 5+) would inject the
actual per-caller actor identity instead.

**Ownership check, narrowed (independent review finding #4, 2026-09-09).** This projector used
to also run the Broker-Order and Knowledge single-owner checks — both are ACTOR-ONLY per
:func:`tos.orthostate.may_transition`'s own docstring ("the other four dimensions ... are
actor-only ... not region-gated"), so with this projector's fixed actor constants they were
UNCONDITIONALLY ``True`` and could never fail (a reachability probe over every state pair
confirmed zero refusals for either). Only the Transmission-Attempt dimension is region-split by
``to_state`` (preparation region owned by ``EXECUTION_COORDINATOR`` alone, send-boundary region
by ``BROKER_ADAPTER_EGRESS`` alone) and can genuinely refuse a transition — e.g. a FUTURE mapping
-table drift wiring a result kind at the preparation region, which this projector's fixed
``BROKER_ADAPTER_EGRESS`` actor may never write. The mapping table
:func:`~tos.engine.orthostate_projection.result_transition_for` reads is closed and
kernel-authored, so this should never actually fire today — see
``tos/runtime/tests/engine/test_orthostate_projection.py``'s own test (a test-only monkeypatch of
the kernel's ``_RESULT_ATTEMPT_TRANSITION`` table) for the reachability proof that this check CAN
fail, unlike the two removed ones.

**Replace is only ever a new attempt (RFC-005 §11 "retry is a new send").** Neither this module
nor :class:`~tos_runtime.engine.driver.EngineDriver` exposes any method that re-sends an
already-recorded attempt or replays an existing ``attempt_id``'s composite forward by hand — see
``tos/runtime/tests/engine/test_orthostate_projection.py``'s pin test for the grep-style +
behavioural proof.

**CPL-6 needs a LIVE authority-epoch reading (bug found wiring this into the driver, team-lead
CR-4 dispatch).** :func:`tos.orthostate.coupling_violations` defaults its
:class:`~tos.orthostate.state.CouplingSideConditions` to all-``None`` when none is supplied —
fail-closed, so ``CPL-6`` (an Attempt at or beyond ``SEND_STARTED`` requires
``authority_epoch_current is True``) would ALWAYS flag every genuine hand-off as a violation if
this projector called ``coupling_violations`` bare. This module therefore takes a REQUIRED
``authority_epoch_current: Callable[[], bool | None]`` — the SAME live check
:class:`~tos_runtime.compose._preconditions.RuntimeCoordinatorPreconditions
.authority_epoch_current` already performs for the kernel's own Coordinator gate (KW2-B) — and
re-reads it fresh on every ``project`` call (never cached; an epoch can lapse between two
observations). Injected as a plain callable rather than importing
``RuntimeCoordinatorPreconditions`` directly, to avoid a ``tos_runtime.engine ->
tos_runtime.compose`` import edge running backwards against this runtime's own composition-root
layering (``compose`` depends on ``engine``, never the reverse).

**CPL-7 is structurally not evaluated in this wave (independent review finding #11,
2026-09-09).** :class:`~tos.orthostate.state.CouplingSideConditions` has four fields; this
projector supplies only ``authority_epoch_current``. ``final_quantity_proof`` /
``consistent_release_proof_rule`` left ``None`` is conservative (CPL-2/CPL-4 fail closed on an
unproven release either way). ``non_reducible_exposure`` left ``None`` means CPL-7 ("confirmed
non-reducible exposure => Capacity = TRAPPED_CONSUMED") can never fire here — there is no
trapped-exposure SIGNAL SOURCE wired into this runtime yet (a future reconciliation lane's
concern, not fabricated here).

**Durable new-risk halt latch (independent review finding #3, 2026-09-09).** A recorded
``COUPLING_VIOLATION`` / ``ORTHOSTATE_OWNERSHIP_VIOLATION`` used to be durably logged and then
block NOTHING — ADR-002-005 §10 "an invariant violation is a Critical incident and an immediate
new-risk halt condition" was a docstring claim this module's own behaviour did not back. Both
violation paths now ALSO call
:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.record_new_risk_halt` — a durable, SINGLETON,
runtime-wide latch (never per-attempt: an invariant violation is a fact about THIS runtime's own
internal consistency, not scoped to one attempt) that :class:`~tos_runtime.engine.driver
.EngineDriver` checks before handling any NEW ``DECISION_TICK`` (never an ``EGRESS_RESULT`` —
results are still consumed; knowledge may improve even while new risk is blocked). Clearing the
latch is explicitly NOT provided in this wave — see the inbox module's own docstring; a Phase 5
operator re-arm is the disclosed follow-on.

**Cancel-crossing fill correction (independent review finding #8, 2026-09-09).** ADR-002-005 §7:
"A later valid fill SHALL be accepted even after a locally observed CANCELLED/REJECTED; the
Broker Order dimension is corrected and the event is not discarded." Before this fix, a fill
landing after this projector's own ``NON_MONOTONIC_PROJECTION`` disposition (e.g. a
``CANCEL_ACK`` then a late ``FULL_FILL`` for the same attempt) was skipped entirely — the
composite stayed at whatever the cancel left it, permanently, with no record that a fill had in
fact occurred. :meth:`project` now special-cases ``NON_MONOTONIC_PROJECTION`` for a
``FULL_FILL``/``PARTIAL_FILL`` kind: it records a Broker-Order-dimension CORRECTION (broker
``FILLED``/``PARTIALLY_FILLED``, knowledge ``CONFLICTED`` — "new evidence disagrees", ADR-002-005
§8) on top of the reconstructed prior composite, leaving the Capacity axis (and every other
dimension) untouched, and evaluates :func:`~tos.orthostate.coupling_violations` on the corrected
composite exactly as the normal path does. **Measured, not assumed (report to the reviewer, dispatch
item 5's own contingency):** this correction is NOT coupling-violation-free in general. CPL-3
("Broker=FILLED => Capacity=POSITION_CONSUMED") is verified live against the real predicate to
FLAG this exact correction (broker corrected to FILLED while capacity is deliberately left
unchanged at, e.g., ``RELEASE_PENDING_PROOF``) — the capacity ledger genuinely IS out of step
with the now-known broker truth, and CPL-3 is not a false positive here; leaving capacity
untouched (this projector owns no capacity-correction path — that is RCL's own §15.2 concern,
residual ②) is the deliberately conservative half of "the two axes are orthogonal" (finding #8's
own suggested disposition). ``knowledge=CONFLICTED`` additionally satisfies CPL-5's own trigger
set, which ALSO flags unless capacity already reads ``QUARANTINED_UNKNOWN``. Both violations are
therefore EXPECTED and recorded (never suppressed) for a cancel-crossing fill — which correctly
engages the new-risk halt latch above: a cancel-crossing fill is exactly the kind of "our records
disagree with the broker" situation that should block new risk pending reconciliation. Only
``NON_MONOTONIC_PROJECTION`` with a fill kind is corrected this way; every other non-``APPLIED``
disposition (``ORPHAN_NO_RESERVATION`` / ``MISMATCHED_ATTEMPT`` / ``DUPLICATE`` /
``QUANTITY_REGRESSION``, or a ``NON_MONOTONIC_PROJECTION`` for a non-fill kind) is left exactly as
before — filed under the kernel's own ``RESULT_UNMATCHED`` evidence, not this projector's
concern.

**Restart inheritance for Knowledge (independent review finding #5, 2026-09-09).**
:func:`tos.orthostate.reconstruct_conservative` used to have no OBSERVABLE effect: its output was
consulted only to build the (now three-times-narrowed, see above) ownership-check genesis, never
to influence the PERSISTED composite (mutation M11 — dropping the call entirely left the shipped
test suite green). This projector now tracks which ``attempt_id``s IT ITSELF has already touched
this INSTANCE lifetime (:attr:`_seen_attempts`, never durable — a fresh instance's first touch of
a KNOWN, previously-persisted attempt is this instance's own operational definition of "resumed",
whether the resumption is a genuine cross-process restart or simply a fresh projector object).
On that FIRST touch only, if the freshly-derived Knowledge value would be LESS conservative than
the reconstructed prior's (via :func:`tos.orthostate.conservative_direction_ok`, no
:class:`~tos.orthostate.state.ConservatismBasis` — this runtime models none, so any reduction
fails closed), the prior's more-conservative Knowledge is inherited instead. Scoped to Knowledge
only, and to first-touch only: **Attempt is deliberately excluded** — ``reconstruct_conservative``
itself never adjusts Attempt (it is passed through unchanged), and Attempt legitimately reduces
conservatism under positive proof (e.g. ``SENT_UNCONFIRMED`` -> ``SEND_FAILED_PROVEN`` after a
proven ``REJECT`` — the rank table's own comment: "entered only under positive proof"); forcing a
conservative-only merge there would have incorrectly blocked that legitimate transition (verified
directly against the real predicate before choosing this scope). And scoped to first-touch only,
never every call: since the closed forward-mapping table
(:data:`~tos.engine.orthostate_projection._KNOWLEDGE_ORTHOSTATE_PROJECTION`) can only ever
produce ``CONSISTENT``/``UNOBSERVED`` — both LESS conservative than the ``CONFLICTED`` a restart
downgrades positive knowledge to — merging on EVERY call would permanently lock Knowledge at
``CONFLICTED`` after the first positive result, for the rest of the attempt's life, which is not
a restart-recovery property, it is a regression.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.engine``/
``tos.orthostate`` + ``tos_runtime.engine.inbox``/``tos_runtime.evidence.*`` only. No
``shared.*``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tos.engine import EventResult
from tos.engine.orthostate_projection import composite_state_for, result_transition_for
from tos.engine.records import EgressResultPayload, EngineEvent
from tos.engine.vocabulary import EgressResultKind, EventKind, ResultDisposition
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    CouplingSideConditions,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransitionAuthority,
    TransmissionAttemptState,
    conservative_direction_ok,
    coupling_violations,
    may_transition,
    reconstruct_conservative,
)

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["OrthostateProjector", "NEW_RISK_HALTED_BY_COUPLING_VIOLATION"]

_COUPLING_VIOLATION_KIND = "COUPLING_VIOLATION"
_OWNERSHIP_VIOLATION_KIND = "ORTHOSTATE_OWNERSHIP_VIOLATION"

#: The runtime-wide new-risk halt latch's reason string (independent review finding #3,
#: 2026-09-09) — a plain string, not a kernel ``HaltReason`` member (this is a RUNTIME-level
#: latch, never a kernel-vocabulary halt; see :mod:`tos_runtime.engine.driver`'s own use of this
#: constant for how it reaches an ``EVENT_CONSUMED`` receipt's ``halt_reason`` field, which is
#: typed ``str | None`` at the runtime evidence layer, not the kernel's closed enum).
NEW_RISK_HALTED_BY_COUPLING_VIOLATION = "NEW_RISK_HALTED_BY_COUPLING_VIOLATION"

# Actor stand-in — see module docstring's "Actor stand-in" / "Ownership check, narrowed" sections.
_ATTEMPT_EGRESS_ACTOR = TransitionAuthority.BROKER_ADAPTER_EGRESS

#: Every attempt this projector ever sees already has Intent ``ACTIVE`` (an attempt only exists
#: past Approval + Aggregate-Risk + capacity commitment — ADR-002-005 §5). This runtime has no
#: Intent Registry object (``composite_state_for``'s own docstring), so Intent is never
#: transitioned by this projector; it is fixed at ``ACTIVE`` for every composite this module
#: produces.
_FIXED_INTENT_STATE = IntentState.ACTIVE

#: The virtual "from" Attempt state used for the ownership check on a GENESIS observation (no
#: prior composite recorded yet for this attempt) — the true starting point of the dimension
#: before any result has been observed (ADR-002-005 §6 genesis value), so the very first
#: observation is ownership-checked too, not skipped.
_GENESIS_ATTEMPT_STATE = TransmissionAttemptState.NONE

#: Independent review finding #8 (2026-09-09): the Broker-Order correction a cancel-crossing fill
#: applies, keyed by the fill kind that crossed the cancel. Only these two kinds carry fill
#: magnitudes at all (module docstring, "Cancel-crossing fill correction").
_CANCEL_CROSSING_FILL_BROKER_STATE: dict[EgressResultKind, BrokerOrderState] = {
    EgressResultKind.FULL_FILL: BrokerOrderState.FILLED,
    EgressResultKind.PARTIAL_FILL: BrokerOrderState.PARTIALLY_FILLED,
}


@dataclass
class OrthostateProjector:
    """Projects each consumed ``EGRESS_RESULT`` onto the ADR-002-005 orthostate dimensions and
    durably keeps the last composite per attempt (inbox side table).

    Attributes:
        inbox: The durable event admission queue (also the composite side table's owner and the
            runtime-wide new-risk halt latch's owner — see module docstring).
        evidence_store: The durable evidence store — coupling/ownership violations are recorded
            here.
        emergency_log: The dual-path HALT log — coupling/ownership violations are recorded here
            too.
        authority_epoch_current: A LIVE re-check of the Safety Authority epoch (module docstring
            "CPL-6 needs a LIVE authority-epoch reading") — REQUIRED, no default, so an omitted
            check does not silently default to the all-``None`` fail-closed side condition that
            would flag every genuine hand-off as a CPL-6 violation.
    """

    inbox: SqliteEventInbox
    evidence_store: SqliteEvidenceStore
    emergency_log: EmergencyAppendLog
    authority_epoch_current: Callable[[], bool | None]
    #: THIS INSTANCE's own record of which ``attempt_id``s it has already projected at least one
    #: observation for — never durable, never consulted for anything but the restart-inheritance
    #: decision (module docstring "Restart inheritance for Knowledge"). Excluded from
    #: ``__init__``/``repr``/equality: it is derived bookkeeping, not part of this projector's
    #: own identity or configuration.
    _seen_attempts: set[str] = field(
        default_factory=set, init=False, repr=False, compare=False
    )

    def project(
        self, *, event: EngineEvent, result: EventResult
    ) -> CompositeState | None:
        """Project one consumed event's result onto orthostate, or ``None`` if inapplicable.

        Args:
            event: The (already-stamped) event the driver just consumed.
            result: The ``EventResult`` ``core.handle`` returned for it.

        Returns:
            The newly-derived, durably-recorded ``CompositeState``; ``None`` for a
            ``DECISION_TICK`` (never reaches this projector), for an ``EGRESS_RESULT`` with no
            reservation at all, or for a non-``APPLIED``, non-fill-crossing disposition
            (``ORPHAN_NO_RESERVATION`` / ``MISMATCHED_ATTEMPT`` / ``DUPLICATE`` /
            ``QUANTITY_REGRESSION``, or a ``NON_MONOTONIC_PROJECTION`` for a non-fill kind) — see
            :meth:`_project_non_applied` and the module docstring's "Cancel-crossing fill
            correction" for the one non-``APPLIED`` case that IS projected.
        """
        if event.kind is not EventKind.EGRESS_RESULT:
            return None
        payload = event.egress_result
        if payload is None or result.reservation is None:
            return None
        attempt_id = payload.attempt_id

        prior_raw = self.inbox.last_composite(attempt_id)
        prior_composite: CompositeState | None = None
        prior_revision = 0
        if prior_raw is not None:
            raw, prior_revision = prior_raw
            prior_composite = reconstruct_conservative(
                CompositeState.model_validate(raw)
            )

        if result.result_disposition is not ResultDisposition.APPLIED:
            return self._project_non_applied(
                payload=payload,
                result=result,
                attempt_id=attempt_id,
                prior_composite=prior_composite,
                prior_revision=prior_revision,
            )

        attempt_transition, _broker, _knowledge = result_transition_for(payload.kind)
        if prior_composite is None:
            genesis_attempt_state = _GENESIS_ATTEMPT_STATE
            observation_revision = 1
        else:
            genesis_attempt_state = prior_composite.transmission_attempt_state
            observation_revision = prior_revision + 1

        next_composite = composite_state_for(
            result.reservation,
            intent_state=_FIXED_INTENT_STATE,
            attempt_state=attempt_transition,
        )
        next_composite = self._inherit_conservative_knowledge_on_first_touch(
            prior_composite, next_composite, attempt_id=attempt_id
        )

        self._check_ownership(
            genesis_attempt_state, next_composite, attempt_id=attempt_id
        )
        self._evaluate_coupling(next_composite, attempt_id=attempt_id)

        self.inbox.record_composite(
            attempt_id,
            next_composite.model_dump(mode="json"),
            observation_revision=observation_revision,
        )
        return next_composite

    def _project_non_applied(
        self,
        *,
        payload: EgressResultPayload,
        result: EventResult,
        attempt_id: str,
        prior_composite: CompositeState | None,
        prior_revision: int,
    ) -> CompositeState | None:
        """Independent review finding #8: correct the Broker Order dimension for a
        cancel-crossing fill (module docstring); every other non-``APPLIED`` disposition is
        left exactly as before (returns ``None``, nothing recorded)."""
        corrected_broker = _CANCEL_CROSSING_FILL_BROKER_STATE.get(payload.kind)
        if (
            result.result_disposition is not ResultDisposition.NON_MONOTONIC_PROJECTION
            or corrected_broker is None
            or prior_composite is None
        ):
            return None

        next_composite = prior_composite.model_copy(
            update={
                "broker_order_state": corrected_broker,
                "knowledge_state": KnowledgeState.CONFLICTED,
            }
        )
        self._evaluate_coupling(next_composite, attempt_id=attempt_id)
        self.inbox.record_composite(
            attempt_id,
            next_composite.model_dump(mode="json"),
            observation_revision=prior_revision + 1,
        )
        return next_composite

    def _inherit_conservative_knowledge_on_first_touch(
        self,
        prior_composite: CompositeState | None,
        next_composite: CompositeState,
        *,
        attempt_id: str,
    ) -> CompositeState:
        """Independent review finding #5: on THIS instance's first touch of a KNOWN attempt,
        never let a freshly-derived Knowledge value be LESS conservative than the reconstructed
        prior's (module docstring "Restart inheritance for Knowledge")."""
        first_touch = attempt_id not in self._seen_attempts
        self._seen_attempts.add(attempt_id)
        if prior_composite is None or not first_touch:
            return next_composite
        if conservative_direction_ok(
            StateDimension.KNOWLEDGE,
            prior_composite.knowledge_state,
            next_composite.knowledge_state,
            None,
        ):
            return next_composite
        return next_composite.model_copy(
            update={"knowledge_state": prior_composite.knowledge_state}
        )

    def _check_ownership(
        self,
        genesis_attempt_state: TransmissionAttemptState,
        next_composite: CompositeState,
        *,
        attempt_id: str,
    ) -> None:
        """Halt (and durably latch a new-risk halt) if this projector's own derived
        Transmission-Attempt write is not legal under §12 ownership's region split (module
        docstring "Ownership check, narrowed").
        """
        to_state = next_composite.transmission_attempt_state
        if not may_transition(
            _ATTEMPT_EGRESS_ACTOR,
            StateDimension.TRANSMISSION_ATTEMPT,
            genesis_attempt_state,
            to_state,
        ):
            receipt = record_halt(
                self.evidence_store,
                self.emergency_log,
                payload={
                    "attempt_id": attempt_id,
                    "dimension": StateDimension.TRANSMISSION_ATTEMPT.value,
                    "from_state": str(genesis_attempt_state),
                    "to_state": str(to_state),
                },
                kind=_OWNERSHIP_VIOLATION_KIND,
                record_class=_OWNERSHIP_VIOLATION_KIND,
            )
            self.inbox.record_new_risk_halt(
                reason=NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
                event_id=f"attempt:{attempt_id}",
                evidence_seq=receipt.seq,
            )

    def _evaluate_coupling(self, composite: CompositeState, *, attempt_id: str) -> None:
        """Evaluate :func:`~tos.orthostate.coupling_violations` and, on a violation, durably
        record it AND latch the runtime-wide new-risk halt (independent review finding #3).
        """
        side = CouplingSideConditions(
            authority_epoch_current=self.authority_epoch_current()
        )
        violations = coupling_violations(composite, side)
        if violations:
            receipt = record_halt(
                self.evidence_store,
                self.emergency_log,
                payload={
                    "attempt_id": attempt_id,
                    "violations": sorted(violations),
                    "composite": composite.model_dump(mode="json"),
                },
                kind=_COUPLING_VIOLATION_KIND,
                record_class=_COUPLING_VIOLATION_KIND,
            )
            self.inbox.record_new_risk_halt(
                reason=NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
                event_id=f"attempt:{attempt_id}",
                evidence_seq=receipt.seq,
            )
