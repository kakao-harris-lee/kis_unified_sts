"""``RecoveryBarrier`` — the boot-time recovery verdict (TOS Phase 5 W1; plan §2 decision 2:"""

from __future__ import annotations

from dataclasses import dataclass

from tos_runtime.recovery.inputs import RecoveryInputs
from tos_runtime.recovery.readiness import (
    ObligationResult,
    ReadinessVerdict,
    RecoveryAuthorityEffect,
    RecoveryObligation,
    obligation_graph_closed,
    recovery_authority_separated,
    recovery_completion_revives_nothing,
)
from tos_runtime.recovery.reconciliation import RECON_UNAVAILABLE, ReconciliationOutcome

__all__ = [
    "RECON_UNAVAILABLE",
    "RecoveryBarrier",
    "RecoveryBarrierInvariantError",
    "RecoveryVerdict",
]


class RecoveryBarrierInvariantError(RuntimeError):
    """Raised when one of :meth:`RecoveryBarrier.verdict`'s own defence-in-depth invariant"""


_UNRECONCILED = ReconciliationOutcome(cleared=False, reason=RECON_UNAVAILABLE)

_OBLIGATION_REPLAY_IDENTICAL = "PHASE5_W1_REPLAY_VERDICT_IDENTICAL"
_OBLIGATION_NO_POSSIBLY_LIVE = "PHASE5_W1_NO_POSSIBLY_LIVE_ATTEMPTS"
_OBLIGATION_NO_LEGACY_RECEIPTS = "PHASE5_W1_NO_LEGACY_RECEIPTS_IN_WINDOW"
_OBLIGATION_GENERATION_CONSISTENT = (
    "PHASE5_W1_RCL_GENERATION_CONSISTENT_WITH_EVIDENCE_TIP"
)
_OBLIGATION_INBOX_REPLAYABLE = "PHASE5_W1_INBOX_UNCONSUMED_REPLAYABLE"
_OBLIGATION_COMPOSITE_STATE_OK = "PHASE5_W1_COMPOSITE_STATE_RESTORE_OK"


def _satisfied(obligation_id: str, *, ok: bool) -> RecoveryObligation:
    """One flat (no-prerequisite) obligation, SATISFIED iff ``ok`` (module docstring's "the"""
    return RecoveryObligation(
        obligation_id=obligation_id,
        obligation_type="TOS_PHASE5_W1_RECOVERY_BARRIER",
        owner="tos_runtime.recovery.barrier",
        prerequisite_ids=frozenset(),
        acceptable_results=frozenset({ObligationResult.SATISFIED}),
        result=ObligationResult.SATISFIED if ok else ObligationResult.FAILED,
        independent_review_required=False,
    )


def _build_obligations(inputs: RecoveryInputs) -> frozenset[RecoveryObligation]:
    """The six plan §2 decision 2 barrier gates, each as one flat obligation."""
    genesis_consistent = (
        inputs.evidence_tip_seq is None and inputs.rcl_runtime_generation is None
    )
    both_present = (
        inputs.evidence_tip_seq is not None
        and inputs.rcl_runtime_generation is not None
    )
    all_possibly_live_cleared = all(
        inputs.possibly_live_reconciliation.get(attempt.event_id, _UNRECONCILED).cleared
        for attempt in inputs.possibly_live_attempts
    )
    return frozenset(
        {
            _satisfied(_OBLIGATION_REPLAY_IDENTICAL, ok=inputs.replay_verdict_ok),
            _satisfied(_OBLIGATION_NO_POSSIBLY_LIVE, ok=all_possibly_live_cleared),
            _satisfied(
                _OBLIGATION_NO_LEGACY_RECEIPTS, ok=inputs.legacy_receipts.count == 0
            ),
            _satisfied(
                _OBLIGATION_GENERATION_CONSISTENT,
                ok=genesis_consistent or both_present,
            ),
            _satisfied(_OBLIGATION_INBOX_REPLAYABLE, ok=inputs.inbox_events_parseable),
            _satisfied(
                _OBLIGATION_COMPOSITE_STATE_OK,
                ok=not inputs.composite_state_incomplete_attempt_ids,
            ),
        }
    )


def _reason_for(inputs: RecoveryInputs, *, ready: bool) -> str:
    if ready:
        return "all six recovery-barrier obligations satisfied"
    reasons: list[str] = []
    unreconciled = [
        attempt
        for attempt in inputs.possibly_live_attempts
        if not inputs.possibly_live_reconciliation.get(
            attempt.event_id, _UNRECONCILED
        ).cleared
    ]
    if unreconciled:
        reasons.append(f"{len(unreconciled)} possibly-live attempt(s) unreconciled")
    if inputs.legacy_receipts.count:
        reasons.append(
            f"{inputs.legacy_receipts.count} legacy (fingerprint-less) receipt(s) in window (ⓑ)"
        )
    if inputs.composite_state_incomplete_attempt_ids:
        reasons.append(
            f"{len(inputs.composite_state_incomplete_attempt_ids)} attempt(s) with an "
            "incomplete staterestore composite"
        )
    if not (
        inputs.evidence_tip_seq is not None
        and inputs.rcl_runtime_generation is not None
    ) and not (
        inputs.evidence_tip_seq is None and inputs.rcl_runtime_generation is None
    ):
        reasons.append("RCL generation / evidence tip presence inconsistent")
    return "; ".join(reasons) if reasons else "unsatisfied recovery-barrier obligation"


@dataclass(frozen=True)
class RecoveryVerdict:
    """The recovery barrier's own verdict — never a permission, only a denial-context label"""

    readiness_verdict: ReadinessVerdict
    ready: bool
    reason: str
    possibly_live_reconciliation: dict[str, str]
    authority_effect: RecoveryAuthorityEffect


class RecoveryBarrier:
    """The stateless boot-time recovery barrier (plan §2 decision 2)."""

    @staticmethod
    def verdict(inputs: RecoveryInputs) -> RecoveryVerdict:
        """Fold ``inputs`` into a :class:`RecoveryVerdict` via the kernel's own predicates."""
        obligations = _build_obligations(inputs)
        closed = obligation_graph_closed(obligations)

        effect = RecoveryAuthorityEffect()
        if not recovery_authority_separated(effect):
            raise RecoveryBarrierInvariantError(
                "RecoveryAuthorityEffect() must always separate authority — this check "
                "documents the defence-in-depth re-check design #17 calls for, and should be "
                "unreachable"
            )
        if not recovery_completion_revives_nothing():
            raise RecoveryBarrierInvariantError(
                "recovery_completion_revives_nothing() returned False -- SBR-INV-014 violated"
            )

        readiness = ReadinessVerdict.READY if closed else ReadinessVerdict.NOT_READY
        reconciliation = {
            attempt.event_id: inputs.possibly_live_reconciliation.get(
                attempt.event_id, _UNRECONCILED
            ).reason
            for attempt in inputs.possibly_live_attempts
        }
        return RecoveryVerdict(
            readiness_verdict=readiness,
            ready=readiness is ReadinessVerdict.READY,
            reason=_reason_for(inputs, ready=closed),
            possibly_live_reconciliation=reconciliation,
            authority_effect=effect,
        )
