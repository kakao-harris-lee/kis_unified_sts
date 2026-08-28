"""§7.2-1 — the sequencer stops fail-closed at **every** step (design #31 §4.2).

This is the design's own target: *"임의의 stage가 deny/None/UNKNOWN/예외 반환 시 시퀀스가 그 지점에서
중단·send 미발생·중단 사유 기록"*, with the positive-admit gate mutation
(``is ADMIT`` → ``is not DENY``) killed.

The suite is exhaustive rather than illustrative: **every** injected step (2-11, 13, 14) × **every**
failure mode (explicit deny, restrictive UNKNOWN, a missing stage, an absent verdict, a verdict
answering someone else's step, and a raising stage) is asserted to stop the flow *at that step*,
leave the send boundary untouched, and record the halt with a named reason.

It also covers §7.2-6 (the Coordinator holds no authority) at the structural level: step 1 and
step 12 are not injectable, and steps 15-19 are not hostable at all.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

import pytest
from tos.canonical import ArtifactIntegrityError
from tos.engine import (
    COMMITMENT_FLOW_ORDER,
    INJECTED_STAGE_STEPS,
    SEND_BOUNDARY_STEPS,
    SEQUENCED_STEPS,
    CommitmentStep,
    EvidenceKind,
    HaltReason,
    ProvisionalReservationLedger,
    ProvisionalStandIn,
    RecordingEvidenceSink,
    StageAuthorityClass,
    StageOutcome,
    StageRequest,
    StageVerdict,
    build_attempt_request,
    run_commitment_flow,
    step_number,
    validate_stage_map,
)

from ._engine_fixtures import (
    PERMIT_IDENTITY,
    PROOF_DIGEST,
    PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE,
    SCHEME,
    RecordingTransmit,
    admitting_stages,
    build_core,
    decision_tick,
    instrument_key,
    ordering,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _emit_proposal():
    """Run one clean decision tick and return the Proposal the pipeline emitted."""
    core, _ = build_core(transmit=RecordingTransmit())
    result = core.handle(decision_tick(sequence=1))
    assert result.pipeline is not None
    assert result.pipeline.proposal is not None
    return result.pipeline.proposal


class _AbsentVerdictStage:
    """A stage that returns nothing at all — absence must not be read as admission."""

    def __call__(self, _request: StageRequest) -> None:
        """Return nothing at all."""
        return None


class _WrongStepStage:
    """A stage that answers a *different* step than the one it was asked about."""

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Answer a different step than the one asked about."""
        other = (
            CommitmentStep.ORDER_CONFORMANCE_PROOF
            if request.step is not CommitmentStep.ORDER_CONFORMANCE_PROOF
            else CommitmentStep.VENUE_ADMISSIBILITY_DECISION
        )
        return StageVerdict(
            step=other,
            outcome=StageOutcome.ADMIT,
            authority_class=StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
        )


class _RaisingStage:
    """A stage that raises — an exception is a restrictive stop, never a skip."""

    def __call__(self, _request: StageRequest) -> StageVerdict:
        """Raise instead of judging."""
        raise RuntimeError("stage exploded")


#: Sentinel distinguishing "use the default transmit" from the deliberate ``transmit=None`` case.
_DEFAULT = object()


def _run_flow(stages, *, transmit=_DEFAULT, ledger=None, sink=None):
    """Run one commitment flow over ``stages`` with the suite's fixtures."""
    proposal = _emit_proposal()
    return (
        run_commitment_flow(
            proposal_id=proposal.proposal_id,
            proposal=proposal,
            instrument_key=instrument_key(),
            reference=ordering(1),
            stages=stages,
            transmit=RecordingTransmit() if transmit is _DEFAULT else transmit,
            ledger=ledger
            or ProvisionalReservationLedger(
                max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
            ),
            sink=sink or RecordingEvidenceSink(),
            scheme=SCHEME,
        ),
        proposal,
    )


# ---------------------------------------------------------------------------
# §7.2-1 — exhaustive fail-closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("failing_step", list(INJECTED_STAGE_STEPS))
def test_explicit_deny_stops_at_that_step_and_sends_nothing(failing_step) -> None:
    """(§7.2-1) An explicit DENY at any step stops the flow there; no send occurs."""
    transmit = RecordingTransmit()
    sink = RecordingEvidenceSink()
    stages = admitting_stages(denied_steps={failing_step: "refused for the test"})
    flow, _ = _run_flow(stages, transmit=transmit, sink=sink)

    assert flow.handed_off is False
    assert flow.attempt is None or failing_step in (
        CommitmentStep.ATTEMPT_BIND_VERIFICATION,
        CommitmentStep.TRANSMISSION_CAPABILITY,
    )
    assert flow.halt_step is failing_step
    assert flow.halt_reason is HaltReason.STAGE_DENIED
    assert transmit.attempts == []
    halts = [r for r in sink.records if r.kind is EvidenceKind.FLOW_HALTED]
    assert len(halts) == 1
    assert halts[0].step is failing_step
    assert halts[0].halt_reason is HaltReason.STAGE_DENIED


@pytest.mark.parametrize("failing_step", list(INJECTED_STAGE_STEPS))
def test_unknown_stops_at_that_step_and_sends_nothing(failing_step) -> None:
    """(§7.2-1) A restrictive UNKNOWN stops the flow there under its own reason."""
    transmit = RecordingTransmit()
    stages = admitting_stages(unknown_steps=frozenset({failing_step}))
    flow, _ = _run_flow(stages, transmit=transmit)

    assert flow.handed_off is False
    assert flow.halt_step is failing_step
    assert flow.halt_reason is HaltReason.STAGE_UNKNOWN, (
        "UNKNOWN must be recorded distinctly from DENY — it is neither a rejection nor "
        "safe-to-retry (RFC-005 §11:325-327)"
    )
    assert transmit.attempts == []


@pytest.mark.parametrize("missing_step", list(INJECTED_STAGE_STEPS))
def test_a_missing_stage_stops_the_flow(missing_step) -> None:
    """(§7.2-1) A step with **no** injected stage stops the flow — a gap is never a skip."""
    transmit = RecordingTransmit()
    stages = admitting_stages()
    del stages[missing_step]
    flow, _ = _run_flow(stages, transmit=transmit)

    assert flow.handed_off is False
    assert flow.halt_step is missing_step
    assert flow.halt_reason is HaltReason.STAGE_MISSING
    assert transmit.attempts == []


@pytest.mark.parametrize("failing_step", list(INJECTED_STAGE_STEPS))
def test_an_absent_verdict_stops_the_flow(failing_step) -> None:
    """(§7.2-1) A stage that returns nothing stops the flow — absence is not admission."""
    transmit = RecordingTransmit()
    stages = admitting_stages()
    stages[failing_step] = _AbsentVerdictStage()
    flow, _ = _run_flow(stages, transmit=transmit)

    assert flow.handed_off is False
    assert flow.halt_step is failing_step
    assert flow.halt_reason is HaltReason.STAGE_VERDICT_ABSENT
    assert transmit.attempts == []


@pytest.mark.parametrize("failing_step", list(INJECTED_STAGE_STEPS))
def test_a_verdict_for_another_step_stops_the_flow(failing_step) -> None:
    """(§7.2-1) A verdict answering a different step stops the flow — verdicts are not fungible."""
    transmit = RecordingTransmit()
    stages = admitting_stages()
    stages[failing_step] = _WrongStepStage()
    flow, _ = _run_flow(stages, transmit=transmit)

    assert flow.handed_off is False
    assert flow.halt_step is failing_step
    assert flow.halt_reason is HaltReason.STAGE_VERDICT_STEP_MISMATCH
    assert transmit.attempts == []


@pytest.mark.parametrize("failing_step", list(INJECTED_STAGE_STEPS))
def test_a_raising_stage_stops_the_flow(failing_step) -> None:
    """(§7.2-1) A raising stage stops the flow with a recorded reason, never a propagated crash."""
    transmit = RecordingTransmit()
    stages = admitting_stages()
    stages[failing_step] = _RaisingStage()
    flow, _ = _run_flow(stages, transmit=transmit)

    assert flow.handed_off is False
    assert flow.halt_step is failing_step
    assert flow.halt_reason is HaltReason.STAGE_RAISED
    assert flow.detail is not None and "RuntimeError" in flow.detail
    assert transmit.attempts == []


def test_the_positive_admit_gate_is_identity_not_negation() -> None:
    """(§7.2-1 mutation target) A verdict that is merely "not DENY" does **not** advance.

    This is the ``is ADMIT`` → ``is not DENY`` mutation, expressed as behaviour: a stage returning
    UNKNOWN would pass a negated gate and must not pass this one.
    """
    transmit = RecordingTransmit()
    first_injected = INJECTED_STAGE_STEPS[0]
    stages = admitting_stages(unknown_steps=frozenset({first_injected}))
    flow, _ = _run_flow(stages, transmit=transmit)
    assert flow.halt_step is first_injected
    assert transmit.attempts == []


def test_no_transmit_injected_is_a_stop_not_a_skip() -> None:
    """(§4.5) An absent send boundary halts after step 14 — it never means "send anyway"."""
    flow, _ = _run_flow(admitting_stages(), transmit=None)
    assert flow.handed_off is False
    assert flow.halt_reason is HaltReason.TRANSMIT_UNAVAILABLE


def test_a_raising_transmit_keeps_the_reservation_potentially_live() -> None:
    """(§4.2 rule 3; INV-005:168) A failed hand-off is never read as "not sent"."""
    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    flow, _ = _run_flow(
        admitting_stages(), transmit=RecordingTransmit(raises=True), ledger=ledger
    )
    assert flow.handed_off is False
    assert flow.halt_reason is HaltReason.TRANSMIT_RAISED
    reservation = ledger.outstanding(instrument_key())
    assert reservation is not None
    assert reservation.capacity_state.value == "POTENTIALLY_LIVE"


def test_a_clean_flow_admits_every_step_in_the_normative_order() -> None:
    """The happy path really walks ADR-002-002 §11 steps 1-14 in order and then hands off."""
    transmit = RecordingTransmit()
    flow, proposal = _run_flow(admitting_stages(), transmit=transmit)
    assert flow.handed_off is True
    assert tuple(v.step for v in flow.verdicts) == SEQUENCED_STEPS
    assert all(v.outcome is StageOutcome.ADMIT for v in flow.verdicts)
    assert len(transmit.attempts) == 1
    assert flow.attempt is not None
    assert flow.attempt.conformance_proof_digest == PROOF_DIGEST
    assert flow.attempt.action_flow_permit_identity == PERMIT_IDENTITY
    assert flow.verdicts[0].bound_identity == proposal.proposal_id


# ---------------------------------------------------------------------------
# §7.2-6 — the Coordinator holds no authority (structural seals)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sealed_step",
    [CommitmentStep.DECISION_PROPOSAL, CommitmentStep.ATTEMPT_REQUEST],
)
def test_coordinator_realized_steps_are_not_injectable(sealed_step) -> None:
    """(§4.3) Steps 1 and 12 are realized by the Coordinator itself and refuse a stage."""
    stages = admitting_stages()
    stages[sealed_step] = ProvisionalStandIn(sealed_step, admit=True)
    with pytest.raises(ArtifactIntegrityError, match="not injectable"):
        validate_stage_map(stages)


@pytest.mark.parametrize("send_step", sorted(SEND_BOUNDARY_STEPS, key=step_number))
def test_send_boundary_steps_are_not_hostable(send_step) -> None:
    """(§4.5 item-7) Steps 15-19 are constitutionally D-E4's; the sequencer refuses to host them."""
    stages = admitting_stages()
    stages[send_step] = ProvisionalStandIn(send_step, admit=True)
    with pytest.raises(ArtifactIntegrityError, match="Send Boundary"):
        validate_stage_map(stages)


def test_the_sequenced_range_is_steps_one_to_fourteen() -> None:
    """(§4.5 item-7) The guarantee scope is honestly steps 1-14 and the flow order is 19 long."""
    assert len(COMMITMENT_FLOW_ORDER) == 14 + 5
    assert [step_number(s) for s in SEQUENCED_STEPS] == list(range(1, 15))
    assert sorted(step_number(s) for s in SEND_BOUNDARY_STEPS) == [15, 16, 17, 18, 19]


# ---------------------------------------------------------------------------
# step 12 — content-addressed attempt identity (§4.3, MAJOR-3)
# ---------------------------------------------------------------------------


def test_attempt_identity_is_content_addressed_and_reproducible() -> None:
    """(§4.3) The same (proof, permit, reference) always yields the same attempt id."""
    first = build_attempt_request(
        conformance_proof_digest=PROOF_DIGEST,
        action_flow_permit_identity=PERMIT_IDENTITY,
        reference=ordering(7),
        scheme=SCHEME,
    )
    second = build_attempt_request(
        conformance_proof_digest=PROOF_DIGEST,
        action_flow_permit_identity=PERMIT_IDENTITY,
        reference=ordering(7),
        scheme=SCHEME,
    )
    assert first.attempt_id == second.attempt_id
    assert first == second


@pytest.mark.parametrize(
    ("proof", "permit", "sequence"),
    [
        ("other-proof", PERMIT_IDENTITY, 7),
        (PROOF_DIGEST, "other-permit", 7),
        (PROOF_DIGEST, PERMIT_IDENTITY, 8),
    ],
)
def test_attempt_identity_changes_with_every_binding(proof, permit, sequence) -> None:
    """(§4.3) Each of the three bindings is really part of the identity preimage."""
    baseline = build_attempt_request(
        conformance_proof_digest=PROOF_DIGEST,
        action_flow_permit_identity=PERMIT_IDENTITY,
        reference=ordering(7),
        scheme=SCHEME,
    )
    variant = build_attempt_request(
        conformance_proof_digest=proof,
        action_flow_permit_identity=permit,
        reference=ordering(sequence),
        scheme=SCHEME,
    )
    assert variant.attempt_id != baseline.attempt_id


@pytest.mark.parametrize(
    ("proof", "permit"),
    [(None, PERMIT_IDENTITY), (PROOF_DIGEST, None), ("", PERMIT_IDENTITY), (PROOF_DIGEST, "")],
)
def test_an_unbound_attempt_is_unconstructable(proof, permit) -> None:
    """(§4.3) A missing proof digest or permit identity makes the attempt unconstructable."""
    with pytest.raises(ArtifactIntegrityError):
        build_attempt_request(
            conformance_proof_digest=proof,
            action_flow_permit_identity=permit,
            reference=ordering(1),
            scheme=SCHEME,
        )


def test_a_missing_step_eleven_binding_halts_step_twelve() -> None:
    """(§4.3) Without the step-11 proof digest the Coordinator cannot create an attempt."""
    stages = admitting_stages()
    stages[CommitmentStep.ORDER_CONFORMANCE_PROOF] = ProvisionalStandIn(
        CommitmentStep.ORDER_CONFORMANCE_PROOF, admit=True, bound_digest=None
    )
    transmit = RecordingTransmit()
    flow, _ = _run_flow(stages, transmit=transmit)
    assert flow.halt_step is CommitmentStep.ATTEMPT_REQUEST
    assert flow.halt_reason is HaltReason.ATTEMPT_BINDING_INCOMPLETE
    assert transmit.attempts == []
