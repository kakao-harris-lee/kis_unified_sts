"""``ControlledShutdown`` — latch first, then close, and record what happened.

**What survived plan S2-a, and why.** This used to drive the kernel
``tos.sir`` ``ControlledShutdownProcedure`` record and its predicates. That package was
removed because its judgement inputs were a static YAML ``members: []`` in every shipped
tenant tree. The *ordering* it enforced is not ceremony and stays here, as plain code:

1. **Latch denial of new risk BEFORE stopping producers.** The durable new-risk-halt latch
   (:mod:`tos_runtime.engine.inbox`) is set — and confirmed durably present — before any
   resource is closed. This is the SAME latch every other halt path in this runtime uses;
   this procedure never invents a second one.
2. **Preserve RCL commitments.** Every non-``RELEASED`` RCL reservation
   (:mod:`tos_runtime.rcl.projection`) is a real, currently-held obligation this shutdown
   does not resolve. It is durably recorded for the NEXT boot's recovery barrier
   (:mod:`tos_runtime.recovery.barrier`) to read — never resolved here, never invented.
3. **Close in an order that keeps evidence writable.** Event inbox, then RCL commit log,
   then — after the step record and the obligation handoff are written — the evidence
   store LAST. Custody holds no persistent OS resource (every credential is loaded on
   demand into a :class:`~tos_runtime.custody.ports.CredentialHandle` its immediate caller
   closes), so there is nothing to close and this module calls nothing on it.

**Fail-closed halt policy.** Steps 1-4 attempt only while not yet ``halted``; the first
step whose outcome is not positively ``True`` (an exception, or — the inbox close only —
unconsumed events still present) sets ``halted``, and every later 1-4 step is recorded
``completed=None`` ("assume not completed where that is safer") rather than attempted. The
record-and-close step is ALWAYS attempted regardless of ``halted`` — "stop and record":
this procedure never skips writing down what happened.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.rcl`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tos.rcl import CapacityState

from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader

__all__ = ["ControlledShutdown", "ShutdownOutcome", "ShutdownStep"]

#: This module's own evidence ``kind``/``record_class`` vocabulary (runtime-level labels).
_STARTED_EVIDENCE_KIND = "CONTROLLED_SHUTDOWN_STARTED"
_STEPS_EVIDENCE_KIND = "CONTROLLED_SHUTDOWN_STEPS"
_OBLIGATIONS_EVIDENCE_KIND = "CONTROLLED_SHUTDOWN_OBLIGATIONS"
_HANDOFF_EVIDENCE_KIND = "CONTROLLED_SHUTDOWN_HANDOFF"

#: The fixed step labels, in the one order this procedure runs them (module docstring).
STEP_LATCH_NEW_RISK_HALT = "LATCH_NEW_RISK_HALT_BEFORE_STOPPING_PRODUCERS"
STEP_PRESERVE_RCL_COMMITMENTS = "PRESERVE_RCL_COMMITMENTS"
STEP_CLOSE_INBOX = "ESTABLISH_DISPOSITION_AND_CLOSE_INBOX"
STEP_CLOSE_RCL_LOG = "CLOSE_RCL_COMMIT_LOG"
STEP_RECORD_AND_CLOSE_EVIDENCE = "RECORD_STEPS_AND_CLOSE_EVIDENCE"


@dataclass(frozen=True)
class ShutdownStep:
    """One step's ordinal, label, and outcome.

    ``completed`` is tri-state: ``True`` positively completed, ``False`` attempted and
    failed, ``None`` never attempted because an earlier step halted the procedure.
    """

    step_ordinal: int
    step_kind: str
    completed: bool | None


@dataclass(frozen=True)
class ShutdownOutcome:
    """The result of one :meth:`ControlledShutdown.run` call.

    Attributes:
        steps: Every step, in run order (module docstring).
        obligations: ``(reservation_id, capacity_state)`` for every non-``RELEASED`` RCL
            reservation handed to the next boot's recovery barrier (empty if the step
            never ran).
        handoff_id: The handoff's one real, unique coordinate — derived from the
            ``STARTED`` evidence row's own durable ``seq``, or ``None`` if the latch step
            never got that far. Never a fabricated id.
        latched_before_close: ``True`` iff the new-risk-halt latch was positively
            confirmed durably present BEFORE any resource was closed — the one ordering
            property this procedure exists to hold.
        all_steps_proven: ``True`` iff every step positively completed and none was left
            un-attempted.
    """

    steps: tuple[ShutdownStep, ...]
    obligations: tuple[tuple[str, str], ...]
    handoff_id: str | None
    latched_before_close: bool
    all_steps_proven: bool


class ControlledShutdown:
    """Performs and durably records the controlled-shutdown procedure for one
    :class:`~tos_runtime.compose._types.ComposedRuntime` (module docstring).

    Constructed with exactly the resources that runtime already owns — this class invents
    no new resource and reads no ``os.environ``.
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
        #: Held only so a caller (and a future wave that DOES give custody a live
        #: resource) has a concrete place to look; nothing is called on either today.
        self._custody = custody
        self._key_provider = key_provider
        self._started_evidence_seq: int | None = None

    def run(self, *, reason: str) -> ShutdownOutcome:
        """Execute the procedure once and return its :class:`ShutdownOutcome`.

        Args:
            reason: A free-text operator/runtime reason, recorded verbatim on the
                ``STARTED`` evidence row and as the new-risk-halt latch's own reason.

        Returns:
            The :class:`ShutdownOutcome` — see that class and the module docstring's
            "fail-closed halt policy" for what each field means on a partial shutdown.
        """
        steps: list[ShutdownStep] = []
        halted = False

        latched = self._attempt(lambda: self._deny_before_stop(reason), halted)
        steps.append(ShutdownStep(1, STEP_LATCH_NEW_RISK_HALT, latched))
        halted = halted or latched is not True

        obligations, completed = self._attempt_obligations(halted)
        steps.append(ShutdownStep(2, STEP_PRESERVE_RCL_COMMITMENTS, completed))
        halted = halted or completed is not True

        completed = self._attempt(self._close_inbox, halted)
        steps.append(ShutdownStep(3, STEP_CLOSE_INBOX, completed))
        halted = halted or completed is not True

        completed = self._attempt(self._close_rcl_log, halted)
        steps.append(ShutdownStep(4, STEP_CLOSE_RCL_LOG, completed))
        halted = halted or completed is not True

        handoff_id = (
            f"controlled-shutdown-evidence-seq-{self._started_evidence_seq}"
            if self._started_evidence_seq is not None
            else None
        )
        # Always attempted, halted or not — "stop and record" (module docstring).
        completed = self._attempt(
            lambda: self._record_steps_and_close_evidence(
                steps, obligations, handoff_id
            ),
            False,
        )
        steps.append(ShutdownStep(5, STEP_RECORD_AND_CLOSE_EVIDENCE, completed))

        return ShutdownOutcome(
            steps=tuple(steps),
            obligations=obligations,
            handoff_id=handoff_id,
            latched_before_close=latched is True,
            all_steps_proven=all(step.completed is True for step in steps),
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
        """Step 1 — record ``STARTED`` evidence FIRST, then latch, then confirm durably."""
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
    ) -> tuple[tuple[tuple[str, str], ...], bool | None]:
        """Step 2 — every non-``RELEASED`` reservation is recorded as a surviving
        obligation for the next boot's recovery barrier to own."""
        if halted:
            return (), None
        try:
            projection = SqliteReservationProjectionReader(self._rcl_log)
            obligations = tuple(
                (reservation_id, state.value)
                for reservation_id, state in sorted(
                    projection.all_reservations().items()
                )
                if state is not CapacityState.RELEASED
            )
            self._evidence_store.append(
                {
                    "obligation_count": len(obligations),
                    "obligation_ids": [o[0] for o in obligations],
                },
                kind=_OBLIGATIONS_EVIDENCE_KIND,
                record_class=_OBLIGATIONS_EVIDENCE_KIND,
            )
            return obligations, True
        except Exception:
            return (), False

    def _close_inbox(self) -> bool:
        """Step 3 — disposition is honestly established only when nothing is pending."""
        disposition_established = self._inbox.unconsumed_count == 0
        self._inbox.close()
        return disposition_established

    def _close_rcl_log(self) -> bool:
        """Step 4 — the durable commit log FILE is left intact; only the connection closes."""
        self._rcl_log.close()
        return True

    def _record_steps_and_close_evidence(
        self,
        steps_so_far: list[ShutdownStep],
        obligations: tuple[tuple[str, str], ...],
        handoff_id: str | None,
    ) -> bool:
        """Step 5 — record every step's outcome AND the obligation handoff, THEN close.

        Evidence is written BEFORE the store closes, never after: a caller reopening the
        store after :meth:`run` returns can read these rows back, even on a shutdown that
        halted early.
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
            "handoff_id": handoff_id,
            "unresolved_obligation_ids": [o[0] for o in obligations],
        }
        self._evidence_store.append(
            payload, kind=_STEPS_EVIDENCE_KIND, record_class=_STEPS_EVIDENCE_KIND
        )
        self._evidence_store.append(
            {
                "handoff_id": handoff_id,
                "unresolved_obligations": [
                    {"obligation_id": o[0], "capacity_state": o[1]} for o in obligations
                ],
                # The next boot's recovery barrier owns acceptance; this shutdown never
                # decides it, so both coordinates are honestly absent here.
                "recovery_barrier_closed": None,
                "accepted_by_recovery_session": None,
            },
            kind=_HANDOFF_EVIDENCE_KIND,
            record_class=_HANDOFF_EVIDENCE_KIND,
        )
        self._evidence_store.close()
        return True
