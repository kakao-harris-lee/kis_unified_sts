"""``IndependentApprovalStage`` — the engine ``Stage`` realization of step 4
(design #40 §5 order 4 item 4), replacing
``tos.engine.standins.ProvisionalStandIn`` for
``CommitmentStep.INDEPENDENT_APPROVAL``.

This stage never emits :data:`~tos.engine.vocabulary.StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL`
— it is backed by a real :class:`~tos_runtime.authority.iap.IntentRegistry`
whose consumption is an actual RCL commit, not a wiring-only stand-in.
:data:`~tos.engine.vocabulary.StageAuthorityClass.AVAILABLE_PURE_PREDICATE` is
the closest of the three sanctioned
:class:`~tos.engine.vocabulary.StageAuthorityClass` members (the sequencer
recognizes only ``AVAILABLE_PURE_PREDICATE`` / ``NON_AUTHORITATIVE_PROVISIONAL``
/ ``DEFERRED_SEND_BOUNDARY``, ``tos/src/tos/engine/vocabulary.py`` :292-307);
this stage is neither a stand-in nor the D-E4 send boundary, so
``AVAILABLE_PURE_PREDICATE`` — "an already-shipped pure sibling predicate" —
is used in its broader sense of "a real, already-shipped kernel judgement
call, not a provisional placeholder", consistent with how every kernel
predicate this stage calls (``exact_binding_holds``/``consumption_transition``)
already is exactly that.

``StageOutcome.ADMIT`` is returned only when
:meth:`~tos_runtime.authority.iap.IntentRegistry.consume` reports
``CONSUMED_NEW`` or ``IDEMPOTENT_REPLAY`` (an already-fully-legitimate replay
of the SAME consuming command) — never for any rejection, and never by
default when no decision is available (``StageOutcome.UNKNOWN``, restrictive,
per the sequencer's own rule 1: only positive membership advances).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from tos.engine.records import StageRequest, StageVerdict
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass, StageOutcome
from tos.iap import ConsumptionOutcome, IndependentApprovalDecision

from tos_runtime.authority.iap import ConsumeResult, IntentRegistry

__all__ = ["IndependentApprovalStage", "item14_fields"]

#: Outcomes that admit the sequencer to advance past step 4 (module docstring).
_ADMISSIBLE_OUTCOMES: frozenset[ConsumptionOutcome] = frozenset(
    {ConsumptionOutcome.CONSUMED_NEW, ConsumptionOutcome.IDEMPOTENT_REPLAY}
)

DecisionProvider = Callable[[StageRequest], IndependentApprovalDecision | None]
CommandFieldProvider = Callable[[StageRequest, IndependentApprovalDecision], str]
BoolFieldProvider = Callable[[StageRequest, IndependentApprovalDecision], bool | None]


class IndependentApprovalStage:
    """Step 4 (``INDEPENDENT_APPROVAL``) realized over a real
    :class:`~tos_runtime.authority.iap.IntentRegistry` (design #40 §5 order 4
    item 4).

    Every input the registry's ``consume`` needs is collected through injected
    callables — this stage itself makes no judgement, it only routes the
    sequencer's :class:`~tos.engine.records.StageRequest` into
    ``IntentRegistry.consume`` and wraps the result as a
    :class:`~tos.engine.records.StageVerdict`.
    """

    def __init__(
        self,
        registry: IntentRegistry,
        *,
        decision_provider: DecisionProvider,
        command_identity_provider: CommandFieldProvider,
        command_digest_provider: CommandFieldProvider,
        envelope_equivalent_provider: BoolFieldProvider,
        decision_current_provider: BoolFieldProvider | None = None,
    ) -> None:
        """Configure the stage.

        Args:
            registry: The real, RCL-backed Intent Registry.
            decision_provider: Resolves the operator approval decision bound
                to this request's proposal, or ``None`` when no decision is
                available yet (restrictive ``UNKNOWN``, never a pass).
            command_identity_provider: The consuming command's own identity,
                given the request and its resolved decision.
            command_digest_provider: The consuming command's canonical digest.
            envelope_equivalent_provider: Whether the approved-Intent envelope
                is byte-for-byte equivalent (``None``/``False`` => not
                consumable).
            decision_current_provider: Whether the decision is current/
                unexpired/unrevoked (``None``/``False`` => not consumable).
                Defaults to ``registry.decision_current`` (2026-09-08 — the
                composition root need not supply a lambda; see
                :meth:`~tos_runtime.authority.iap.IntentRegistry.decision_current`'s
                own docstring for exactly what it checks).
        """
        self._registry = registry
        self._decision_provider = decision_provider
        self._command_identity_provider = command_identity_provider
        self._command_digest_provider = command_digest_provider
        self._decision_current_provider = (
            decision_current_provider
            if decision_current_provider is not None
            else (lambda _request, decision: registry.decision_current(decision))
        )
        self._envelope_equivalent_provider = envelope_equivalent_provider

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Judge step 4 by consuming the resolved decision, once."""
        decision = self._decision_provider(request)
        if decision is None:
            return StageVerdict(
                step=CommitmentStep.INDEPENDENT_APPROVAL,
                outcome=StageOutcome.UNKNOWN,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason=(
                    "no independent approval decision is available for this "
                    "proposal — UNKNOWN is restrictive, never an assumed grant"
                ),
            )
        result = self._registry.consume(
            decision,
            command_identity=self._command_identity_provider(request, decision),
            command_digest=self._command_digest_provider(request, decision),
            decision_current=self._decision_current_provider(request, decision),
            approved_intent_envelope_equivalent=self._envelope_equivalent_provider(
                request, decision
            ),
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
    """Map an :class:`~tos_runtime.authority.iap.ConsumeResult` to a
    :class:`~tos.engine.vocabulary.StageOutcome` + reason (module docstring)."""
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
    """The gateway ``SendBoundaryContext`` item-14 fields for this consumption.

    Args:
        result: The :meth:`~tos_runtime.authority.iap.IntentRegistry.consume`
            result for this attempt.

    Returns:
        A mapping with exactly ``approval_consumed_for_this_intent`` (``None``
        when the log itself could not be reached — genuinely unknown, never
        coerced to ``False``) and ``approval_intent_binding_digest`` (the
        consumption record's own ``decision_digest``, or ``None`` when
        consumption was not admitted).
    """
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
