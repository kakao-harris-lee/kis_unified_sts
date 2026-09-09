"""``FlowFingerprint`` — the flow-outcome fingerprint an ``EVENT_CONSUMED`` receipt carries
alongside its own ``outcome_digest`` (TOS Phase 3 wave 3 review finding #1(b), 2026-09-09).

**The gap this closes.** :func:`tos_runtime.engine.replay.replay_engine` compares only
``EventResult.outcome_digest``. For a ``DECISION_TICK`` that digest is the decision pipeline's own
Proposal digest, fixed strictly BEFORE the 19-step commitment flow ever runs — so it carries no
information at all about how (or whether) the flow completed: halt step, halt reason, hand-off,
or the bound attempt. The independent wave-3 review measured this directly (probes P5/P6): an
inbox holding only a ``DECISION_TICK`` (no ``EGRESS_RESULT`` re-injected afterward) whose durable
``FLOW_STEP_ADMITTED``/``SEND_HANDED_OFF`` evidence is deleted still replays ``ok=True`` — the
digest comparison is structurally blind to the deletion because nothing about it ever touches the
Proposal digest.

This module gives the driver a second, INDEPENDENT thing to record and compare for a
``DECISION_TICK``: a small, typed, order-sensitive fingerprint of the commitment flow's own
outcome — not a re-invention of the kernel test suite's own mutation-matrix fingerprint
(``tos/tests/engine/test_sequencer_mutation_matrix.py``'s ``_fingerprint``, which additionally
walks the full per-step verdict trace for THAT suite's narrower, single-process comparison
purpose), but the SAME four fields that fixture already established as load-bearing for "did the
flow finish the way it finished live": ``handed_off``, ``halt_step``, ``halt_reason``,
``attempt_id`` — everything :func:`~tos_runtime.engine.replay_stage.RecordedStage` /
:func:`~tos_runtime.engine.replay_transmit.RecordedTransmit` failing to reconstruct the live flow
would visibly change.

**Why only ``DECISION_TICK``.** An ``EGRESS_RESULT`` event has no ``.flow`` at all (that field is
specific to the commitment-flow-hosting event kind) — its own ``outcome_digest``
(``tos.engine.records.egress_result_outcome_digest``, wave-3 KW3-RD) already carries real,
ledger-state-sensitive information post-``[KW3-RD]`` (see :mod:`tos_runtime.engine.replay`'s own
module docstring, corrected for finding #2), so it needs no second fingerprint dimension.
:func:`flow_fingerprint_for` returns ``None`` for anything that is not a ``DECISION_TICK``.
"""

from __future__ import annotations

from tos.canonical import FrozenModel
from tos.engine import EventKind, EventResult
from tos.engine.vocabulary import CommitmentStep, HaltReason

__all__ = ["FlowFingerprint", "flow_fingerprint_for", "first_mismatched_field"]

#: Field order for :func:`first_mismatched_field` — deliberately fixed so the SAME kind of
#: divergence (e.g. "handed_off flipped") is always named first, regardless of how many fields
#: happen to differ at once.
_FINGERPRINT_FIELDS_IN_REPORTING_ORDER: tuple[str, ...] = (
    "handed_off",
    "halt_step",
    "halt_reason",
    "attempt_id",
)


class FlowFingerprint(FrozenModel):
    """A ``DECISION_TICK``'s commitment-flow outcome, independent of its Proposal digest
    (module docstring).

    Mirrors exactly the four fields the kernel's own mutation-matrix fixture
    (``test_sequencer_mutation_matrix.py``'s ``_fingerprint``) already established as
    load-bearing for this comparison, off :class:`~tos.engine.sequencer.FlowResult`.
    """

    handed_off: bool
    halt_step: CommitmentStep | None = None
    halt_reason: HaltReason | None = None
    attempt_id: str | None = None


def flow_fingerprint_for(result: EventResult) -> FlowFingerprint | None:
    """Derive the fingerprint for one ``EventResult`` — ``None`` for anything but a
    ``DECISION_TICK`` (module docstring's "why only DECISION_TICK").

    A ``DECISION_TICK`` whose commitment flow never ran at all (``result.flow is None`` — a
    Coordinator-gate refusal, a runtime-level latch refusal, or a defined no-action outcome) gets
    the same fingerprint shape a flow that never handed off would: ``handed_off=False``,
    ``halt_step=None``, and the event's own top-level ``halt_reason`` (``None`` for a genuine
    no-action tick) — never fabricated flow data for a flow that never started.
    """
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
    """The name of the FIRST field (in :data:`_FINGERPRINT_FIELDS_IN_REPORTING_ORDER`) at which
    ``expected`` and ``actual`` differ, or ``None`` if they are identical."""
    for field in _FINGERPRINT_FIELDS_IN_REPORTING_ORDER:
        if getattr(expected, field) != getattr(actual, field):
            return field
    return None
