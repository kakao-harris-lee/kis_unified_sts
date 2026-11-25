"""Phase 3 wave 3 KW3-EV — per-step evidence carries ``event_id`` + step-9/11 bound values."""

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
    """([KW3-EV]) A full ADMIT run through the slice-1 e2e fixture: every"""
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
    assert {r.kind for r in per_step_records} == per_step_kinds
    for record in per_step_records:
        assert record.event_id == expected_event_id, (
            f"{record.kind} record carries event_id={record.event_id!r}, "
            f"expected {expected_event_id!r}"
        )


def test_a_halted_flow_records_the_handled_events_event_id_too() -> None:
    """([KW3-EV]) ``FLOW_HALTED`` carries the same ``event_id`` as a successful run's records —"""
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
    """([KW3-EV]) The ``FLOW_STEP_ADMITTED`` records for ``ATOMIC_COMMIT`` (step 9) and"""
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

    assert (
        result.flow.attempt.action_flow_permit_identity == atomic_commit.bound_identity
    )
    assert (
        result.flow.attempt.conformance_proof_digest == order_conformance.bound_digest
    )


def test_every_other_step_admit_record_carries_no_bound_values() -> None:
    """([KW3-EV]) Every step besides 9/11 carries ``None`` for both — the fixture's stand-in"""
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
    """([KW3-EV]) A DENY never reaches ``FLOW_STEP_ADMITTED`` at all — the halt at step 9 is"""
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
    admitted_steps = {
        r.step for r in sink.records if r.kind is EvidenceKind.FLOW_STEP_ADMITTED
    }
    assert CommitmentStep.ATOMIC_COMMIT not in admitted_steps
