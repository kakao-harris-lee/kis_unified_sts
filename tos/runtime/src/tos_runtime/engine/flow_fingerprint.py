"""``FlowFingerprint`` — the flow-outcome fingerprint an ``EVENT_CONSUMED`` receipt carries"""

from __future__ import annotations

from tos.canonical import FrozenModel
from tos.engine import EventKind, EventResult
from tos.engine.vocabulary import CommitmentStep, HaltReason

__all__ = ["FlowFingerprint", "flow_fingerprint_for", "first_mismatched_field"]

_FINGERPRINT_FIELDS_IN_REPORTING_ORDER: tuple[str, ...] = (
    "handed_off",
    "halt_step",
    "halt_reason",
    "attempt_id",
)


class FlowFingerprint(FrozenModel):
    """A ``DECISION_TICK``'s commitment-flow outcome, independent of its Proposal digest"""

    handed_off: bool
    halt_step: CommitmentStep | None = None
    halt_reason: HaltReason | None = None
    attempt_id: str | None = None


def flow_fingerprint_for(result: EventResult) -> FlowFingerprint | None:
    """Derive the fingerprint for one ``EventResult`` — ``None`` for anything but a"""
    if result.kind is not EventKind.DECISION_TICK:
        return None
    flow = result.flow
    if flow is None:
        return FlowFingerprint(
            handed_off=False,
            halt_step=None,
            halt_reason=result.halt_reason,
            attempt_id=None,
        )
    return FlowFingerprint(
        handed_off=flow.handed_off,
        halt_step=flow.halt_step,
        halt_reason=flow.halt_reason,
        attempt_id=None if flow.attempt is None else flow.attempt.attempt_id,
    )


def first_mismatched_field(
    expected: FlowFingerprint, actual: FlowFingerprint
) -> str | None:
    """The name of the FIRST field (in :data:`_FINGERPRINT_FIELDS_IN_REPORTING_ORDER`) at which"""
    for field in _FINGERPRINT_FIELDS_IN_REPORTING_ORDER:
        if getattr(expected, field) != getattr(actual, field):
            return field
    return None
