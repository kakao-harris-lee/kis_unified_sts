"""Phase 3 wave 3 KW3-EV — per-step evidence carries ``event_id`` + step-9/11 bound values.

Runtime lane C-R's record/replay stand-ins (``RecordedStage`` ``3e2af6cf``, ``RecordedTransmit``
``a2b72a9a``) hit a durable-evidence gap this file closes at the kernel:

* the sequencer's per-step evidence (``FLOW_STEP_ADMITTED`` / ``FLOW_HALTED`` /
  ``ATTEMPT_REQUEST_CREATED`` / ``SEND_HANDED_OFF`` on ``EngineEvidenceRecord``) carried no
  ``event_id``, so a replay had to correlate flow instances by encounter order — fragile under a
  truncated ``window_events``;
* for steps 9 (``ATOMIC_COMMIT``) and 11 (``ORDER_CONFORMANCE_PROOF``) an ADMIT verdict's
  ``bound_identity`` / ``bound_digest`` (the two values ``sequencer._bindings_from`` feeds into
  step 12's content-addressed ``attempt_id``) existed only on the in-memory ``StageVerdict`` — a
  rebooted replay could not rebuild the live ``attempt_id`` from durable evidence alone, so every
  later ``EGRESS_RESULT`` looked orphaned.

Both are additive-only: no new hashing, no behaviour change to the flow itself — verified by the
existing suite staying green and by the mutation guards below.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

from tos.engine import EvidenceKind, HaltReason, event_identity
from tos.engine.vocabulary import CommitmentStep

from ._engine_fixtures import (
    PERMIT_IDENTITY,
    PROOF_DIGEST,
    SCHEME,
    RecordingTransmit,
    admitting_stages,
    build_core,
    decision_tick,
)


def test_every_per_step_record_carries_the_handled_events_event_id() -> None:
    """([KW3-EV]) A full ADMIT run through the slice-1 e2e fixture: every
    ``ATTEMPT_REQUEST_CREATED`` / ``FLOW_STEP_ADMITTED`` / ``SEND_HANDED_OFF`` record the flow
    emits carries exactly the handled ``DECISION_TICK``'s content-addressed ``event_id``.
    """
    event = decision_tick(sequence=1)
    expected_event_id = event_identity(event, scheme=SCHEME)

    core, sink = build_core(transmit=RecordingTransmit())
    result = core.handle(event)

    assert result.flow is not None and result.flow.handed_off is True
    per_step_kinds = {
        EvidenceKind.ATTEMPT_REQUEST_CREATED,
        EvidenceKind.FLOW_STEP_ADMITTED,
        EvidenceKind.SEND_HANDED_OFF,
    }
    per_step_records = [r for r in sink.records if r.kind in per_step_kinds]
    # sanity: the fixture actually exercises all three kinds, or the assertion below is vacuous
    assert {r.kind for r in per_step_records} == per_step_kinds
    for record in per_step_records:
        assert record.event_id == expected_event_id, (
            f"{record.kind} record carries event_id={record.event_id!r}, "
            f"expected {expected_event_id!r}"
        )


def test_a_halted_flow_records_the_handled_events_event_id_too() -> None:
    """([KW3-EV]) ``FLOW_HALTED`` carries the same ``event_id`` as a successful run's records —
    correlation must not depend on the flow actually reaching a hand-off.
    """
    event = decision_tick(sequence=1)
    expected_event_id = event_identity(event, scheme=SCHEME)

    stages = admitting_stages(
        denied_steps={
            CommitmentStep.VENUE_ADMISSIBILITY_DECISION: "refused for the test"
        }
    )
    core, sink = build_core(stages=stages, transmit=RecordingTransmit())
    result = core.handle(event)

    assert result.flow is not None and result.flow.handed_off is False
    assert result.flow.halt_reason is HaltReason.STAGE_DENIED
    (halt,) = [r for r in sink.records if r.kind is EvidenceKind.FLOW_HALTED]
    assert halt.event_id == expected_event_id


def test_step_9_and_11_admit_records_carry_exactly_the_verdicts_bound_values() -> None:
    """([KW3-EV]) The ``FLOW_STEP_ADMITTED`` records for ``ATOMIC_COMMIT`` (step 9) and
    ``ORDER_CONFORMANCE_PROOF`` (step 11) carry ``bound_identity`` / ``bound_digest`` equal to
    what the fixture's stand-in stages actually reported — asserted against the fixture's own
    constants, the same values ``_bindings_from`` reads to build the attempt request.
    """
    core, sink = build_core(transmit=RecordingTransmit())
    result = core.handle(decision_tick(sequence=1))
    assert result.flow is not None and result.flow.attempt is not None

    admitted = {
        r.step: r for r in sink.records if r.kind is EvidenceKind.FLOW_STEP_ADMITTED
    }
    atomic_commit = admitted[CommitmentStep.ATOMIC_COMMIT]
    order_conformance = admitted[CommitmentStep.ORDER_CONFORMANCE_PROOF]

    assert atomic_commit.bound_identity == PERMIT_IDENTITY
    assert atomic_commit.bound_digest is None
    assert order_conformance.bound_digest == PROOF_DIGEST
    assert order_conformance.bound_identity is None

    # the exact two values _bindings_from reads to build the attempt request:
    assert (
        result.flow.attempt.action_flow_permit_identity == atomic_commit.bound_identity
    )
    assert (
        result.flow.attempt.conformance_proof_digest == order_conformance.bound_digest
    )


def test_every_other_step_admit_record_carries_no_bound_values() -> None:
    """([KW3-EV]) Every step besides 9/11 carries ``None`` for both — the fixture's stand-in
    stages only ever populate the two designed bindings (module docstring's own citation of
    ``provisional_stage_map``).
    """
    core, sink = build_core(transmit=RecordingTransmit())
    result = core.handle(decision_tick(sequence=1))
    assert result.flow is not None and result.flow.handed_off is True

    for record in sink.records:
        if record.kind is not EvidenceKind.FLOW_STEP_ADMITTED:
            continue
        if record.step in (
            CommitmentStep.ATOMIC_COMMIT,
            CommitmentStep.ORDER_CONFORMANCE_PROOF,
        ):
            continue
        assert record.bound_identity is None
        assert record.bound_digest is None


def test_a_deny_at_step_9_carries_none_for_both_bound_values() -> None:
    """([KW3-EV]) A DENY never reaches ``FLOW_STEP_ADMITTED`` at all — the halt at step 9 is
    recorded as ``FLOW_HALTED``, which carries no ``bound_identity`` / ``bound_digest`` fields
    (they are ``FLOW_STEP_ADMITTED``-only, populated from an ADMIT verdict that never happened).
    """
    stages = admitting_stages(
        denied_steps={CommitmentStep.ATOMIC_COMMIT: "denied for the test"}
    )
    core, sink = build_core(stages=stages, transmit=RecordingTransmit())
    result = core.handle(decision_tick(sequence=1))

    assert result.flow is not None and result.flow.handed_off is False
    assert result.flow.halt_step is CommitmentStep.ATOMIC_COMMIT
    (halt,) = [r for r in sink.records if r.kind is EvidenceKind.FLOW_HALTED]
    assert halt.bound_identity is None
    assert halt.bound_digest is None
    # and no ATOMIC_COMMIT FLOW_STEP_ADMITTED record was ever produced to carry one either:
    admitted_steps = {
        r.step for r in sink.records if r.kind is EvidenceKind.FLOW_STEP_ADMITTED
    }
    assert CommitmentStep.ATOMIC_COMMIT not in admitted_steps
