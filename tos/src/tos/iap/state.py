"""iap single-use consumption state machine + temporal / generation-fence predicates (§6.2/§5.6/§6.5/§6.6)."""

from __future__ import annotations

from tos.canonical import RecordPairKind, classify_record_pair
from tos.iap.vocabulary import ApprovalResult, ConsumptionOutcome, ConsumptionStatus
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "TradingApprovalGeneration",
    "consumption_transition",
    "economic_effect_outlives",
    "stale_generation_fenced",
    "recovery_revives_nothing",
]

TradingApprovalGeneration = OrderingEvent


def consumption_transition(
    *,
    current_status: ConsumptionStatus,
    decision_result: ApprovalResult,
    decision_current: bool | None,
    approved_intent_envelope_equivalent: bool | None,
    command_identity: str | None,
    command_digest: str | None,
    prior_command_identity: str | None = None,
    prior_command_digest: str | None = None,
) -> tuple[ConsumptionStatus, ConsumptionOutcome]:
    """The single-use consumption state machine step (§12 line 306-314 / IAP-INV-006 / IAP-AC-005)."""
    if current_status is ConsumptionStatus.ELIGIBLE:
        admissible = (
            decision_result is ApprovalResult.APPROVE
            and decision_current is True
            and approved_intent_envelope_equivalent is True
        )
        if admissible:
            return (ConsumptionStatus.CONSUMED, ConsumptionOutcome.CONSUMED_NEW)
        return (ConsumptionStatus.ELIGIBLE, ConsumptionOutcome.REJECTED_INELIGIBLE)

    kind = classify_record_pair(
        prior_command_identity,
        prior_command_digest,
        command_identity,
        command_digest,
    )
    if kind is RecordPairKind.IDEMPOTENT_DUP:
        return (ConsumptionStatus.CONSUMED, ConsumptionOutcome.IDEMPOTENT_REPLAY)
    if kind is RecordPairKind.CRITICAL_CONFLICT:
        return (ConsumptionStatus.CONSUMED, ConsumptionOutcome.REJECTED_CONFLICT)
    return (ConsumptionStatus.CONSUMED, ConsumptionOutcome.REJECTED_REUSE)


def economic_effect_outlives(*, terminal_release_proven: bool | None) -> bool:
    """Whether the committed economic effect outlives approval expiry / invalidation (§5.6 / §16 / §19 / IAP-INV-011)."""
    return terminal_release_proven is not True


def stale_generation_fenced(older: OrderingEvent, newer: OrderingEvent) -> bool:
    """Whether a newer Trading Approval Generation fences an older writer (§6.5 / §17 / IAP-INV-012)."""
    return compare_order(older, newer) is Ordering.BEFORE


def recovery_revives_nothing() -> bool:
    """Whether nothing revives a prior decision / Intent permission / authority / live state (§6.6 / §20)."""
    return True
