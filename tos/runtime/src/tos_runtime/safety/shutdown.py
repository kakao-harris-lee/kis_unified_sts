"""``ControlledShutdown`` — the TOS Phase 5 W3.2 lane d3 controlled-shutdown procedure
(ADR-002-027 §5.8/§12 ``tos.sir``; plan
``docs/plans/2026-09-11-tos-phase5-w32-remaining-owners-plan.md`` §2 decision 9, §4 lane d3).

**What this module actually proves, and what it deliberately does not.** This runtime has no
tracked notion of a "Safety Incident" today (``tos_runtime.safety.incident`` reads an
OPERATOR policy document, not a live incident declared by this shutdown) — so an ordinary
``ComposedRuntime.shutdown()`` call is a **routine** controlled stop, never itself the
declaration of a ``tos.sir`` Safety Incident. Three real facts this runtime DOES own are
folded into the kernel's :class:`~tos.sir.ControlledShutdownProcedure` and its predicates:

1. **The durable new-risk-halt latch** (:mod:`tos_runtime.engine.inbox`) is the SAME
   mechanism ``deny_before_stop`` names — this procedure does not invent a second latch; it
   sets the one latch every other halt path in this runtime already uses, confirmed
   durably present before any resource is closed (§12 step 1).
2. **Every non-``RELEASED`` RCL reservation** (:mod:`tos_runtime.rcl.projection`) is a real,
   currently-held obligation this shutdown does not resolve — it can only durably record
   each one as a :class:`~tos.sir.OngoingSafetyObligation` and hand the set to the NEXT
   boot's TOS Phase 5 W1 recovery barrier (:mod:`tos_runtime.recovery.barrier`), never
   invent a resolution that has not happened.
3. **Four sqlite-backed resources this runtime itself opened** (the event inbox, the RCL
   commit log, the evidence store, and — vacuously, see :func:`ControlledShutdown
   ._close_custody` — custody) are closed in a fixed order that keeps evidence-writing
   possible for as long as anything might still need it (evidence store closes LAST).

**Why :func:`~tos.sir.obligations_survive_shutdown` is never called (disclosed, not silently
skipped).** That predicate takes an :class:`~tos.sir.IncidentContainmentPlan`, whose
``_REQUIRED_COVERED`` fields bind it to "**one exact Incident Generation**" (kernel
docstring, §5.7/§11 line 322) — a real incident-scope identity this routine shutdown does
not have and cannot honestly invent (there is no live ``tos.sir`` Safety Incident this
shutdown is responding to; :mod:`tos_runtime.safety.incident` is a separate, operator-fed
policy document, not a per-shutdown incident record). Constructing a plan with a fabricated
``incident_generation``/``active_set_digest`` just to make the predicate callable would be
exactly the M6 anti-pattern (a constant standing in for a fact that does not exist) this
codebase's own memory (``tos-phase4-scopes-round-2026-09-09``) warns against. This module
therefore never builds an :class:`~tos.sir.IncidentContainmentPlan` and never calls
:func:`~tos.sir.obligations_survive_shutdown`; :attr:`ShutdownOutcome
.obligations_survive_shutdown_called` is always ``False``, so a caller can see this
disclosure without reading this docstring.

**Why the recovery-handoff predicate is real but honestly ``False`` at shutdown time.**
:func:`~tos.sir.recovery_handoff_requires_accepted_barrier` needs BOTH
``recovery_barrier_closed`` and ``accepted_by_recovery_session`` positively ``True`` — both
are **injected sbr (ADR-002-017) verdicts** (kernel docstring) that only the TOS Phase 5 W1
recovery barrier (:mod:`tos_runtime.recovery.barrier`), running at the NEXT boot, can ever
supply. This module builds the :class:`~tos.sir.IncidentRecoveryHandoffPackage` with every
field it CAN honestly source now (the transferred obligations; an all-false authority
effect) and leaves both barrier-owned coordinates ``None`` — never faked ``True`` — so the
predicate call in :attr:`ShutdownOutcome.recovery_handoff_requires_accepted_barrier` is a
REAL, honestly negative answer ("no acceptance has happened yet"), not a vacuous skip. The
package itself is durably recorded as evidence (:data:`_HANDOFF_EVIDENCE_KIND`) for that
future barrier wave to read and decide acceptance — this module never decides acceptance
for it.

**Why "close custody" is a documented no-op, not a fabricated call.**
:class:`~tos_runtime.custody.file_custody.FileCustody` and
:class:`~tos_runtime.custody.key_provider.FileKeyProvider` hold no persistent OS resource on
:class:`~tos_runtime.compose._types.ComposedRuntime` — every credential is loaded on demand
into a :class:`~tos_runtime.custody.ports.CredentialHandle` that its IMMEDIATE caller
(e.g. the KIS mock transport's ``send_once``) closes before returning (both classes' own
``__init__``/``load`` bodies open no file handle across calls — grepped repo-wide,
2026-09-11). There is therefore no ``FileCustody.close()`` method to call, and inventing one
here would be exactly the kind of fabricated action this codebase's honesty discipline
forbids. :func:`ControlledShutdown._close_custody` is recorded as its own
:data:`~tos.sir.SHUTDOWN_STEP_KINDS` step (``HARD_FENCE_UNOBSERVABLE_PATHS`` — the closest
ADR label to "the credential/broker route is fenced off") purely to preserve the ADR's own
10-step vocabulary and this procedure's auditability; it can never fail because it calls
nothing.

**Step-kind mapping (why each runtime action gets the ADR label it does).**

======  ======================================================================  ======================================================
step    runtime action                                                          :data:`~tos.sir.SHUTDOWN_STEP_KINDS` label
======  ======================================================================  ======================================================
1       set the new-risk-halt latch (after recording ``STARTED`` evidence)      ``LATCH_DENIAL_OF_NEW_RISK_BEFORE_STOPPING_PRODUCERS``
2       durably record every non-``RELEASED`` RCL reservation as an obligation  ``PRESERVE_RCL_COMMITMENTS_AND_QUARANTINE_UNCERTAINTY``
3       close the event inbox (disposition honestly gated on zero-unconsumed)  ``ESTABLISH_DISPOSITION_OF_EVERY_PENDING_OR_UNKNOWN_ACTION``
4       close the RCL commit log (the durable file itself is left intact)      ``PRESERVE_HALT_LATCHES_RECONCILIATION_TIME_EVIDENCE_NOTIFICATION_RECOVERY``
5       record the ``STEPS``/handoff evidence, THEN close the evidence store   ``RECORD_EVERY_STOP_FENCE_CHANGE_INTERACTION_AMBIGUITY_AND_TRANSFER``
6       close custody (vacuous — module docstring)                             ``HARD_FENCE_UNOBSERVABLE_PATHS``
======  ======================================================================  ======================================================

**Fail-closed halt policy.** Steps 1-4 attempt only while not yet ``halted``; the first step
whose outcome is not positively ``True`` (an exception, or — step 3 only — unconsumed events
still present) sets ``halted`` and every later 1-4 step is recorded ``completed=None``
("assume not completed where that is safer", :class:`~tos.sir.ShutdownStep`'s own polarity
docstring) rather than attempted. Step 5 (record + close evidence) and step 6 (the custody
no-op) are ALWAYS attempted regardless of ``halted`` — "stop and record": this procedure
never skips writing down what happened, and never leaves the evidence store or custody path
in a state a later step could still corrupt.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tos.rcl import CapacityState
from tos.sir import (
    SHUTDOWN_PROHIBITIONS,
    SHUTDOWN_STEP_KINDS,
    AllFalseIncidentAuthority,
    ControlledShutdownProcedure,
    IncidentRecoveryHandoffPackage,
    OngoingSafetyObligation,
    ShutdownStep,
    controlled_shutdown_not_broker_finality,
    recovery_handoff_requires_accepted_barrier,
    step_completion_proven,
)

from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader

__all__ = ["ControlledShutdown", "ShutdownOutcome"]

# The ADR's own 10-step vocabulary, unpacked by name so this module can never silently
# drift from ``tos.sir.vocabulary.SHUTDOWN_STEP_KINDS`` (no re-typed string literal).
(
    LATCH_DENIAL_OF_NEW_RISK_BEFORE_STOPPING_PRODUCERS,
    _REVOKE_OR_FENCE_STALE_GENERATIONS,
    ESTABLISH_DISPOSITION_OF_EVERY_PENDING_OR_UNKNOWN_ACTION,
    PRESERVE_RCL_COMMITMENTS_AND_QUARANTINE_UNCERTAINTY,
    _INVENTORY_POSITIONS_ORDERS_FILLS_CASH_MARGIN_SETTLEMENT_EXPOSURE,
    _PRESERVE_PROTECTION_AND_OBTAIN_CANCELLATION_ARBITER_APPROVAL,
    PRESERVE_HALT_LATCHES_RECONCILIATION_TIME_EVIDENCE_NOTIFICATION_RECOVERY,
    HARD_FENCE_UNOBSERVABLE_PATHS,
    RECORD_EVERY_STOP_FENCE_CHANGE_INTERACTION_AMBIGUITY_AND_TRANSFER,
    _LEAVE_SCOPE_NON_LIVE_BEHIND_THE_RECOVERY_BARRIER,
) = SHUTDOWN_STEP_KINDS

#: This module's own evidence ``kind``/``record_class`` vocabulary (runtime-level labels,
#: never a kernel ``EvidenceKind`` member — the same discipline
#: ``ComposedRuntime._NEW_RISK_HALT_CLEARED_KIND`` already documents).
_STARTED_EVIDENCE_KIND = "CONTROLLED_SHUTDOWN_STARTED"
_STEPS_EVIDENCE_KIND = "CONTROLLED_SHUTDOWN_STEPS"
_HANDOFF_EVIDENCE_KIND = "CONTROLLED_SHUTDOWN_HANDOFF"

#: What this procedure preserves rather than blindly discards (§12 line 350 "preserved
#: functions") — structural labels only, never checked by the kernel predicate.
_PRESERVED_FUNCTIONS: tuple[str, ...] = (
    "NEW_RISK_HALT_LATCH",
    "RCL_COMMIT_LOG_FILE",
    "EVIDENCE_CHAIN_FILE",
)
_HARD_FENCED_PATHS: tuple[str, ...] = ("BROKER_CREDENTIAL_ROUTE",)


@dataclass(frozen=True)
class ShutdownOutcome:
    """The result of one :meth:`ControlledShutdown.run` call — every field a real, sourced
    fact, never a re-derived summary (module docstring's own honesty discipline).

    Attributes:
        procedure: The :class:`~tos.sir.ControlledShutdownProcedure` built from the steps
            actually attempted.
        step_completion_proven: :func:`~tos.sir.step_completion_proven` evaluated per step,
            in :attr:`procedure`'s ``ordered_steps`` order.
        not_broker_finality: :func:`~tos.sir.controlled_shutdown_not_broker_finality`
            evaluated on :attr:`procedure` — ``True`` iff the procedure denies before
            stopping, declares the mandated prohibitions, and carries a structurally sound
            step ordering (SIR-INV-007; this proves nothing about the broker, per that
            predicate's own docstring).
        obligations: Every non-``RELEASED`` RCL reservation, transferred as an
            :class:`~tos.sir.OngoingSafetyObligation` (empty if step 2 never ran).
        handoff_package: The :class:`~tos.sir.IncidentRecoveryHandoffPackage` recorded for
            the next boot's recovery barrier to consume.
        handoff_accepted: :func:`~tos.sir.recovery_handoff_requires_accepted_barrier`
            evaluated on :attr:`handoff_package` — honestly ``False`` at shutdown time
            (module docstring): no Recovery Session has accepted anything yet.
        obligations_survive_shutdown_called: Always ``False`` — see module docstring for
            why this predicate is never called by a routine (non-incident) shutdown.
        all_steps_proven: ``True`` iff every attempted step is positively proven complete
            AND no step was left un-attempted (``completed is None``).
    """

    procedure: ControlledShutdownProcedure
    step_completion_proven: tuple[bool, ...]
    not_broker_finality: bool
    obligations: tuple[OngoingSafetyObligation, ...]
    handoff_package: IncidentRecoveryHandoffPackage
    handoff_accepted: bool
    all_steps_proven: bool
    obligations_survive_shutdown_called: bool = field(default=False)


class ControlledShutdown:
    """Performs and durably records the ADR-002-027 controlled-shutdown procedure for one
    :class:`~tos_runtime.compose._types.ComposedRuntime` (plan §2 decision 9, lane d3).

    Constructed with exactly the resources :class:`~tos_runtime.compose._types
    .ComposedRuntime` already owns — this class invents no new resource and reads no
    ``os.environ`` (module docstring's firewall note).
    """

    def __init__(
        self,
        *,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
        evidence_store: SqliteEvidenceStore,
        custody: FileCustody,
        key_provider: FileKeyProvider,
    ) -> None:
        self._inbox = inbox
        self._rcl_log = rcl_log
        self._evidence_store = evidence_store
        self._custody = custody
        self._key_provider = key_provider
        #: The ``STARTED`` evidence row's own ``seq`` (set by :meth:`_deny_before_stop`) —
        #: the one honest, real, unique coordinate this shutdown has to build a
        #: ``handoff_id`` from (never a fabricated counter or ``id()``).
        self._started_evidence_seq: int | None = None

    def run(self, *, reason: str) -> ShutdownOutcome:
        """Execute the six-step procedure once and return its :class:`ShutdownOutcome`.

        Args:
            reason: A free-text operator/runtime reason, recorded verbatim on the
                ``STARTED`` evidence row and as the new-risk-halt latch's own reason.

        Returns:
            The :class:`ShutdownOutcome` — see that class and the module docstring's
            "fail-closed halt policy" section for exactly what each field means on a
            partial (halted) shutdown.
        """
        steps: list[ShutdownStep] = []
        halted = False
        obligations: tuple[OngoingSafetyObligation, ...] = ()

        completed = self._attempt(lambda: self._deny_before_stop(reason), halted)
        steps.append(
            _step(1, LATCH_DENIAL_OF_NEW_RISK_BEFORE_STOPPING_PRODUCERS, completed)
        )
        halted = halted or completed is not True

        obligations, completed = self._attempt_obligations(halted)
        steps.append(
            _step(2, PRESERVE_RCL_COMMITMENTS_AND_QUARANTINE_UNCERTAINTY, completed)
        )
        halted = halted or completed is not True

        completed = self._attempt(self._close_inbox, halted)
        steps.append(
            _step(
                3, ESTABLISH_DISPOSITION_OF_EVERY_PENDING_OR_UNKNOWN_ACTION, completed
            )
        )
        halted = halted or completed is not True

        completed = self._attempt(self._close_rcl_log, halted)
        steps.append(
            _step(
                4,
                PRESERVE_HALT_LATCHES_RECONCILIATION_TIME_EVIDENCE_NOTIFICATION_RECOVERY,
                completed,
            )
        )
        halted = halted or completed is not True

        handoff_package = self._build_handoff_package(obligations)
        completed = self._attempt(
            lambda: self._record_steps_and_close_evidence(steps, handoff_package), False
        )
        steps.append(
            _step(
                5,
                RECORD_EVERY_STOP_FENCE_CHANGE_INTERACTION_AMBIGUITY_AND_TRANSFER,
                completed,
            )
        )

        completed = self._attempt(self._close_custody, False)
        steps.append(_step(6, HARD_FENCE_UNOBSERVABLE_PATHS, completed))

        procedure = ControlledShutdownProcedure(
            ordered_steps=tuple(steps),
            deny_before_stop=steps[0].completed,
            preserved_functions=_PRESERVED_FUNCTIONS,
            hard_fenced_paths=_HARD_FENCED_PATHS,
            prohibited=frozenset(SHUTDOWN_PROHIBITIONS),
        )
        step_proofs = tuple(step_completion_proven(step) for step in steps)
        return ShutdownOutcome(
            procedure=procedure,
            step_completion_proven=step_proofs,
            not_broker_finality=controlled_shutdown_not_broker_finality(procedure),
            obligations=obligations,
            handoff_package=handoff_package,
            handoff_accepted=recovery_handoff_requires_accepted_barrier(
                handoff_package
            ),
            all_steps_proven=all(step_proofs)
            and all(s.completed is not None for s in steps),
        )

    @staticmethod
    def _attempt(action: Callable[[], bool], halted: bool) -> bool | None:
        """Run ``action`` unless ``halted`` — ``None`` (not attempted) when halted,
        ``False`` when ``action`` raises or returns ``False``, else ``True``."""
        if halted:
            return None
        try:
            return bool(action())
        except Exception:
            return False

    def _deny_before_stop(self, reason: str) -> bool:
        """§12 step 1 — record ``STARTED`` evidence FIRST, then latch, then confirm durably."""
        receipt = self._evidence_store.append(
            {"reason": reason},
            kind=_STARTED_EVIDENCE_KIND,
            record_class=_STARTED_EVIDENCE_KIND,
        )
        self._started_evidence_seq = receipt.seq
        self._inbox.record_new_risk_halt(
            reason=reason, event_id=None, evidence_seq=receipt.seq
        )
        return self._inbox.new_risk_halt() is not None

    def _attempt_obligations(
        self, halted: bool
    ) -> tuple[tuple[OngoingSafetyObligation, ...], bool | None]:
        """§12 step 4 — every non-``RELEASED`` reservation becomes an obligation.

        ``transferred_with_owner_and_evidence`` is ``True`` only in the sense the module
        docstring states: this durable evidence row exists — the owner of the OBLIGATION
        itself is the next boot's recovery barrier, never this shutdown.
        """
        if halted:
            return (), None
        try:
            projection = SqliteReservationProjectionReader(self._rcl_log)
            unresolved = {
                reservation_id: state
                for reservation_id, state in projection.all_reservations().items()
                if state is not CapacityState.RELEASED
            }
            obligations = tuple(
                OngoingSafetyObligation(
                    obligation_id=reservation_id,
                    kind=state.value,
                    resolved=False,
                    transferred_with_owner_and_evidence=True,
                )
                for reservation_id, state in sorted(unresolved.items())
            )
            payload: dict[str, Any] = {
                "obligation_count": len(obligations),
                "obligation_ids": [o.obligation_id for o in obligations],
            }
            self._evidence_store.append(
                payload,
                kind="CONTROLLED_SHUTDOWN_OBLIGATIONS",
                record_class="CONTROLLED_SHUTDOWN_OBLIGATIONS",
            )
            return obligations, True
        except Exception:
            return (), False

    def _close_inbox(self) -> bool:
        """§12 step 3 — disposition is honestly established only when nothing is pending."""
        disposition_established = self._inbox.unconsumed_count == 0
        self._inbox.close()
        return disposition_established

    def _close_rcl_log(self) -> bool:
        """§12 step 7 — the durable commit log FILE is left intact; only the connection closes."""
        self._rcl_log.close()
        return True

    def _record_steps_and_close_evidence(
        self,
        steps_so_far: list[ShutdownStep],
        handoff_package: IncidentRecoveryHandoffPackage,
    ) -> bool:
        """§12 step 9 — record every step's outcome AND the handoff package, THEN close.

        Evidence is written BEFORE the store closes (never after — module docstring /
        mutation M3): a caller reopening the store after :meth:`run` returns can read this
        row back and see the STEPS record, even on a shutdown that halted early.
        """
        payload: dict[str, Any] = {
            "steps": [
                {
                    "step_ordinal": s.step_ordinal,
                    "step_kind": s.step_kind,
                    "completed": s.completed,
                }
                for s in steps_so_far
            ],
            "handoff_id": handoff_package.handoff_id,
            "unresolved_obligation_ids": [
                o.obligation_id for o in handoff_package.unresolved_obligations
            ],
        }
        self._evidence_store.append(
            payload, kind=_STEPS_EVIDENCE_KIND, record_class=_STEPS_EVIDENCE_KIND
        )
        self._evidence_store.append(
            {
                "handoff_id": handoff_package.handoff_id,
                "unresolved_obligation_ids": [
                    o.obligation_id for o in handoff_package.unresolved_obligations
                ],
                "recovery_barrier_closed": handoff_package.recovery_barrier_closed,
                "accepted_by_recovery_session": handoff_package.accepted_by_recovery_session,
            },
            kind=_HANDOFF_EVIDENCE_KIND,
            record_class=_HANDOFF_EVIDENCE_KIND,
        )
        self._evidence_store.close()
        return True

    def _close_custody(self) -> bool:
        """§12 step — vacuous by design; see the module docstring's "close custody" section.

        :attr:`_custody`/:attr:`_key_provider` are held only so a caller (and a future wave
        that DOES give ``FileCustody`` a live resource) has a concrete place to look; this
        method calls nothing on either and can never fail.
        """
        del self  # no live resource on this runtime to release (module docstring)
        return True

    def _build_handoff_package(
        self, obligations: tuple[OngoingSafetyObligation, ...]
    ) -> IncidentRecoveryHandoffPackage:
        """Build the recovery handoff package with every field this shutdown can honestly
        source now; ``recovery_barrier_closed``/``accepted_by_recovery_session`` stay
        ``None`` — module docstring's "honestly ``False`` at shutdown time" section.

        Constructed via the plain pydantic constructor (status stays ``DRAFT`` — the
        established runtime idiom, e.g. :mod:`tos_runtime.safety.incident`'s own
        ``ActiveSafetyIncidentSet`` construction), never ``.issue()``: this shutdown has no
        honest ``handoff_generation``/``incident_id`` to satisfy the ``ISSUED``-status
        required-covered check, and DRAFT construction never claims one.

        ``handoff_id`` is derived from the ``STARTED`` evidence row's own durable ``seq``
        (:attr:`_started_evidence_seq`) when step 1 ran far enough to obtain one — the one
        real, unique coordinate this shutdown has; ``None`` (never a fabricated id) if step
        1 never got that far.
        """
        handoff_id = (
            f"controlled-shutdown-evidence-seq-{self._started_evidence_seq}"
            if self._started_evidence_seq is not None
            else None
        )
        return IncidentRecoveryHandoffPackage(
            handoff_id=handoff_id,
            handoff_generation=None,
            incident_id=None,
            active_set_generation=None,
            unresolved_obligations=obligations,
            recovery_barrier_closed=None,
            accepted_by_recovery_session=None,
            authority_effect=AllFalseIncidentAuthority(),
        )


def _step(ordinal: int, kind: str, completed: bool | None) -> ShutdownStep:
    """One :class:`~tos.sir.ShutdownStep` — a thin constructor wrapper kept here so
    :meth:`ControlledShutdown.run` reads as a flat, ordered list of steps."""
    return ShutdownStep(step_ordinal=ordinal, step_kind=kind, completed=completed)
