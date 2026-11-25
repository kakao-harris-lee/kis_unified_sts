"""⚠ NON-AUTHORITATIVE PROVISIONAL stand-ins for the absent authority runtimes (design #31 §4.4)."""

from __future__ import annotations

from collections.abc import Mapping

from tos.engine.records import StageRequest, StageVerdict
from tos.engine.sequencer import Stage
from tos.engine.vocabulary import (
    INJECTED_STAGE_STEPS,
    CommitmentStep,
    StageAuthorityClass,
    StageOutcome,
)

__all__ = ["ProvisionalStandIn", "provisional_stage_map"]


class ProvisionalStandIn:
    """A single non-authoritative stand-in for one commitment step (design #31 §4.4)."""

    def __init__(
        self,
        step: CommitmentStep,
        *,
        admit: bool | None = None,
        denied: bool | None = None,
        bound_digest: str | None = None,
        bound_identity: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Configure the stand-in."""
        self._step = step
        self._admit = admit
        self._denied = denied
        self._bound_digest = bound_digest
        self._bound_identity = bound_identity
        self._reason = reason

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Produce the step's non-authoritative verdict."""
        reason: str | None
        if self._denied is True:
            outcome = StageOutcome.DENY
            reason = self._reason or "provisional stand-in refused this step"
        elif self._admit is True:
            outcome = StageOutcome.ADMIT
            reason = self._reason
        else:
            outcome = StageOutcome.UNKNOWN
            reason = self._reason or (
                "no decision was produced by the provisional stand-in — UNKNOWN is restrictive, "
                "never an assumed grant (design #31 §4.4)"
            )
        return StageVerdict(
            step=request.step,
            outcome=outcome,
            authority_class=StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
            native_verdict_type=None,
            bound_digest=self._bound_digest,
            bound_identity=self._bound_identity,
            reason=reason,
        )


def provisional_stage_map(
    *,
    conformance_proof_digest: str,
    action_flow_permit_identity: str,
    denied_steps: Mapping[CommitmentStep, str] | None = None,
    unknown_steps: frozenset[CommitmentStep] | None = None,
) -> dict[CommitmentStep, Stage]:
    """Build a complete stand-in map for every injected step (design #31 §4.4)."""
    denied = dict(denied_steps or {})
    unknown = frozenset(unknown_steps or frozenset())
    stages: dict[CommitmentStep, Stage] = {}
    for step in INJECTED_STAGE_STEPS:
        if step in denied:
            stages[step] = ProvisionalStandIn(step, denied=True, reason=denied[step])
            continue
        if step in unknown:
            stages[step] = ProvisionalStandIn(step)
            continue
        bound_digest = (
            conformance_proof_digest
            if step is CommitmentStep.ORDER_CONFORMANCE_PROOF
            else None
        )
        bound_identity = (
            action_flow_permit_identity
            if step is CommitmentStep.ATOMIC_COMMIT
            else None
        )
        stages[step] = ProvisionalStandIn(
            step,
            admit=True,
            bound_digest=bound_digest,
            bound_identity=bound_identity,
            reason="NON-AUTHORITATIVE PROVISIONAL stand-in — wiring only, closes no EV",
        )
    return stages
