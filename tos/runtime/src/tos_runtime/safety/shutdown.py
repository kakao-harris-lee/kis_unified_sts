"""``ControlledShutdown`` — latch first, then close, and record what happened."""

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

_STARTED_EVIDENCE_KIND = "CONTROLLED_SHUTDOWN_STARTED"
_STEPS_EVIDENCE_KIND = "CONTROLLED_SHUTDOWN_STEPS"
_OBLIGATIONS_EVIDENCE_KIND = "CONTROLLED_SHUTDOWN_OBLIGATIONS"
_HANDOFF_EVIDENCE_KIND = "CONTROLLED_SHUTDOWN_HANDOFF"

STEP_LATCH_NEW_RISK_HALT = "LATCH_NEW_RISK_HALT_BEFORE_STOPPING_PRODUCERS"
STEP_PRESERVE_RCL_COMMITMENTS = "PRESERVE_RCL_COMMITMENTS"
STEP_CLOSE_INBOX = "ESTABLISH_DISPOSITION_AND_CLOSE_INBOX"
STEP_CLOSE_RCL_LOG = "CLOSE_RCL_COMMIT_LOG"
STEP_RECORD_AND_CLOSE_EVIDENCE = "RECORD_STEPS_AND_CLOSE_EVIDENCE"


@dataclass(frozen=True)
class ShutdownStep:
    """One step's ordinal, label, and outcome."""

    step_ordinal: int
    step_kind: str
    completed: bool | None


@dataclass(frozen=True)
class ShutdownOutcome:
    """The result of one :meth:`ControlledShutdown.run` call."""

    steps: tuple[ShutdownStep, ...]
    obligations: tuple[tuple[str, str], ...]
    handoff_id: str | None
    latched_before_close: bool
    all_steps_proven: bool


class ControlledShutdown:
    """Performs and durably records the controlled-shutdown procedure for one"""

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
        self._started_evidence_seq: int | None = None

    def run(self, *, reason: str) -> ShutdownOutcome:
        """Execute the procedure once and return its :class:`ShutdownOutcome`."""
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
        """Run ``action`` unless ``halted`` — ``None`` (not attempted) when halted,"""
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
        """Step 2 — every non-``RELEASED`` reservation is recorded as a surviving"""
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
        """Step 5 — record every step's outcome AND the obligation handoff, THEN close."""
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
                "recovery_barrier_closed": None,
                "accepted_by_recovery_session": None,
            },
            kind=_HANDOFF_EVIDENCE_KIND,
            record_class=_HANDOFF_EVIDENCE_KIND,
        )
        self._evidence_store.close()
        return True
