"""``IndependentApprovalStage`` — the engine ``Stage`` realization of step 4"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from tos.engine.records import StageRequest, StageVerdict
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass, StageOutcome
from tos.iap import ConsumptionOutcome, IndependentApprovalDecision

from tos_runtime.authority.iap import ConsumeResult, IntentRegistry, LoadedApproval

__all__ = ["IndependentApprovalStage", "item14_fields"]

_ADMISSIBLE_OUTCOMES: frozenset[ConsumptionOutcome] = frozenset(
    {ConsumptionOutcome.CONSUMED_NEW, ConsumptionOutcome.IDEMPOTENT_REPLAY}
)

DecisionProvider = Callable[[StageRequest], LoadedApproval | None]
CommandFieldProvider = Callable[[StageRequest, IndependentApprovalDecision], str]
BoolFieldProvider = Callable[[StageRequest, IndependentApprovalDecision], bool | None]
DecisionCurrentProvider = Callable[
    [StageRequest, IndependentApprovalDecision, LoadedApproval | None], bool | None
]


class IndependentApprovalStage:
    """Step 4 (``INDEPENDENT_APPROVAL``) realized over a real"""

    def __init__(
        self,
        registry: IntentRegistry,
        *,
        decision_provider: DecisionProvider,
        command_identity_provider: CommandFieldProvider,
        command_digest_provider: CommandFieldProvider,
        envelope_equivalent_provider: BoolFieldProvider,
        decision_current_provider: DecisionCurrentProvider | None = None,
    ) -> None:
        """Configure the stage."""
        self._registry = registry
        self._decision_provider = decision_provider
        self._command_identity_provider = command_identity_provider
        self._command_digest_provider = command_digest_provider
        self._decision_current_provider = (
            decision_current_provider
            if decision_current_provider is not None
            else (
                lambda _request, decision, receipt: registry.decision_current(
                    decision, receipt=receipt
                )
            )
        )
        self._envelope_equivalent_provider = envelope_equivalent_provider

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Judge step 4 by consuming the resolved decision, once."""
        loaded = self._decision_provider(request)
        if loaded is None:
            return StageVerdict(
                step=CommitmentStep.INDEPENDENT_APPROVAL,
                outcome=StageOutcome.UNKNOWN,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason=(
                    "no independent approval decision is available for this "
                    "proposal — UNKNOWN is restrictive, never an assumed grant"
                ),
            )
        decision = loaded.decision
        result = self._registry.consume(
            decision,
            command_identity=self._command_identity_provider(request, decision),
            command_digest=self._command_digest_provider(request, decision),
            decision_current=self._decision_current_provider(request, decision, loaded),
            approved_intent_envelope_equivalent=self._envelope_equivalent_provider(
                request, decision
            ),
            receipt=loaded,
        )
        outcome, reason = _stage_outcome_for(result)
        return StageVerdict(
            step=CommitmentStep.INDEPENDENT_APPROVAL,
            outcome=outcome,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            native_verdict_type=(
                None if result.outcome is None else "ConsumptionOutcome"
            ),
            native_verdict_value=(
                None if result.outcome is None else result.outcome.value
            ),
            bound_digest=(
                None if result.record is None else result.record.decision_digest
            ),
            bound_identity=decision.decision_id,
            reason=reason,
        )


def _stage_outcome_for(result: ConsumeResult) -> tuple[StageOutcome, str]:
    """Map an :class:`~tos_runtime.authority.iap.ConsumeResult` to a"""
    if result.outcome is None:
        return (
            StageOutcome.UNKNOWN,
            "the RCL log could not be reached for consumption — UNKNOWN, never a pass",
        )
    if result.outcome in _ADMISSIBLE_OUTCOMES:
        return (
            StageOutcome.ADMIT,
            f"independent approval consumed ({result.outcome.value})",
        )
    return (
        StageOutcome.DENY,
        f"independent approval consumption refused ({result.outcome.value})",
    )


def item14_fields(result: ConsumeResult) -> Mapping[str, object]:
    """The gateway ``SendBoundaryContext`` item-14 fields for this consumption."""
    if result.outcome is None:
        return {
            "approval_consumed_for_this_intent": None,
            "approval_intent_binding_digest": None,
        }
    consumed = result.outcome in _ADMISSIBLE_OUTCOMES
    return {
        "approval_consumed_for_this_intent": consumed,
        "approval_intent_binding_digest": (
            result.record.decision_digest if consumed and result.record else None
        ),
    }
