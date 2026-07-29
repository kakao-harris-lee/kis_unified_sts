"""Seams — D-E1's ``Transmit`` slot and the ``tos.brokeradapter`` structural transport port.

Two seams the design (§0.1-7 / §5.1 / §7) makes load-bearing, and which no single-package test can
prove:

1. **The gateway fills D-E1's open slot.** ``engine/sequencer.py`` refuses to host steps 15-19
   and halts with ``TRANSMIT_UNAVAILABLE`` when no transmit is injected ("an absent send boundary
   is not a licence to skip it"). This file runs the real 19-step flow with the Order Construction
   stages at steps 2 / 3 / 5 / 11 and the Broker Egress Gateway in the ``Transmit`` slot, so the
   hand-off, the binding, and the ``EGRESS_RESULT`` production are exercised end to end.
2. **The two Protocol declarations have not drifted.** ``tos.egressgw`` and ``tos.brokeradapter``
   are kept out of each other's import closures (design #34 §0.3), so the transport port is
   declared twice and satisfied structurally. A silent signature drift would break the injection
   at runtime only, so it is asserted here directly.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

from __future__ import annotations

import inspect

from tos.brokeradapter import Transport
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule import DecisionContextCapsule
from tos.capsule._base import PolicyRef
from tos.capsule.capsule import CapsuleScope, SafetyCriticalFacts, SnapshotRef
from tos.dsl import DecisionContextCapsuleRef, Proposal, Proposer, TargetKind
from tos.egressgw import (
    ConformanceProofStage,
    EconomicEffectStage,
    OrderConstructionStage,
    SendTransport,
    VenueConstraintStage,
)
from tos.engine import (
    CommitmentStep,
    EgressResultKind,
    HaltReason,
    RecordingEvidenceSink,
    Stage,
    StageOutcome,
    StageRequest,
    Transmit,
    build_attempt_request,
    provisional_stage_map,
    run_commitment_flow,
)
from tos.engine.state import ProvisionalReservationLedger
from tos.rcl import CapacityState

from ._egressgw_fixtures import (
    ACCOUNT,
    INSTRUMENT,
    PERMIT_IDENTITY,
    SCHEME,
    admitted_price,
    build_gateway,
    egress_request,
    full_fill_transport,
    happy_context,
    instrument_key,
    ordering,
    proposed_envelope,
    quorum_certificate,
    venue_decision,
    venue_policy,
    venue_quantity_constraint,
    venue_shape,
    venue_shape_constraints,
    venue_snapshot,
)
from ._egressgw_fixtures import SESSION_PHASE as PHASE

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _capsule_ref() -> DecisionContextCapsuleRef:
    """A content-addressed bind to an issued Decision Context Capsule."""
    capsule = DecisionContextCapsule.issue(
        scheme=_SCHEME,
        issuer_principal_id="iss-1",
        critical_input_policy=PolicyRef(policy_id="pol-1", canonical_digest="pd-1"),
        critical_input_snapshot=SnapshotRef(snapshot_id="cis-ref", canonical_digest="sd-1"),
        scope=CapsuleScope(
            environment="non-live-test",
            account=ACCOUNT,
            instrument=INSTRUMENT,
            decision_class="entry",
        ),
        safety_critical_facts=SafetyCriticalFacts(
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
        ),
    )
    return DecisionContextCapsuleRef(
        capsule_id=capsule.capsule_id, canonical_digest=capsule.canonical_digest
    )


def _proposal() -> Proposal:
    """An issued Proposal carrying the abstract quantity **basis** — never a quantity."""
    issued = Proposal.issue(
        scheme=_SCHEME,
        proposer=Proposer(strategy_id="astrat-1", strategy_version="digest-1"),
        target_kind=TargetKind.ACTION,
        account=ACCOUNT,
        instrument=INSTRUMENT,
        direction="LONG",
        position_effect="OPEN",
        quantity_basis="RISK",
        rationale="edge present",
        decision_context_capsule=_capsule_ref(),
        dsl_version="dsl-0",
        config_version="cfg-v1",
    )
    assert isinstance(issued, Proposal)
    return issued


def _construction_stages(price=None) -> dict[CommitmentStep, Stage]:
    """The four Order Construction stages, wired over the suite's baseline inputs."""
    step2 = OrderConstructionStage(
        envelope=proposed_envelope(),
        price=price if price is not None else admitted_price(),
        venue_constraint=venue_quantity_constraint(),
        scheme=SCHEME,
        intent_id="intent-1",
        intent_version="intent-v1",
        envelope_id="env-1",
        policy_id="ocp-1",
        policy_version="ocp-v1",
        policy_generation=1,
        command_id="cmd-1",
        generation=1,
    )
    step3 = VenueConstraintStage(
        observed_session_phase=PHASE,
        action_class=None,
        snapshot=venue_snapshot(),
        policy=venue_policy(),
        shape=venue_shape(),
        constraints=venue_shape_constraints(),
        decision=venue_decision(),
    )
    step5 = EconomicEffectStage(construction_stage=step2)
    step11 = ConformanceProofStage(
        construction_stage=step2,
        scheme=SCHEME,
        proof_id="ocp-proof-1",
        proof_generation=1,
        required_authority_scope=("scope-1",),
    )
    return {
        CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION: step2,
        CommitmentStep.VENUE_ADMISSIBILITY_DECISION: step3,
        CommitmentStep.ECONOMIC_EFFECT_ENVELOPE: step5,
        CommitmentStep.ORDER_CONFORMANCE_PROOF: step11,
    }


def _stage_request(step: CommitmentStep) -> StageRequest:
    """A minimal stage request carrying the same Proposal the flow will carry."""
    return StageRequest(
        step=step,
        instrument_key=instrument_key(),
        proposal=_proposal(),
        reference=ordering(1),
    )


def _prebuilt_construction() -> tuple[OrderConstructionStage, ConformanceProofStage]:
    """Run steps 2 and 11 once with the flow's own inputs (the derivation is deterministic)."""
    stages = _construction_stages()
    step2 = stages[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION]
    step11 = stages[CommitmentStep.ORDER_CONFORMANCE_PROOF]
    assert isinstance(step2, OrderConstructionStage)
    assert isinstance(step11, ConformanceProofStage)
    step2(_stage_request(CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION))
    step11(_stage_request(CommitmentStep.ORDER_CONFORMANCE_PROOF))
    return step2, step11


def _flow_attempt_and_context():
    """The attempt the flow will build, plus a context bound to the flow's own artifacts.

    Both halves come from the *same* deterministic construction the flow re-runs, so the seam is
    exercised on identical artifacts rather than on look-alikes: the reservation identities the
    gateway matches at item 2 really are the ones step 12 binds.
    """
    step2, step11 = _prebuilt_construction()
    built = step2.construction
    proof = step11.proof
    assert built is not None and built.command is not None and built.intent is not None
    assert proof is not None and proof.canonical_digest is not None
    attempt = build_attempt_request(
        conformance_proof_digest=proof.canonical_digest,
        action_flow_permit_identity=PERMIT_IDENTITY,
        reference=ordering(1),
        scheme=SCHEME,
    )
    _, context = happy_context(
        construction=built,
        conformance_proof=proof,
        approval_intent_binding_digest=built.intent.canonical_digest,
        egress_request=egress_request(built.command.canonical_digest),
        quorum_commit_certificate=quorum_certificate(built.command.canonical_digest),
        outbound_quantity=built.derivation.quantity,
        outbound_price=built.derivation.price,
        reservation_attempt_id=attempt.attempt_id,
        reservation_conformance_proof_digest=proof.canonical_digest,
    )
    return attempt, context


def _run_flow(*, transmit, action_class=None, price=None):
    """Run the full 19-step flow with the construction stages + provisional stand-ins."""
    stages = provisional_stage_map(
        conformance_proof_digest="unused-provisional-digest",
        action_flow_permit_identity=PERMIT_IDENTITY,
    )
    construction_stages = _construction_stages(price=price)
    if action_class is not None:
        construction_stages[CommitmentStep.VENUE_ADMISSIBILITY_DECISION] = VenueConstraintStage(
            observed_session_phase=PHASE,
            action_class=action_class,
            snapshot=venue_snapshot(),
            policy=venue_policy(),
            shape=venue_shape(),
            constraints=venue_shape_constraints(),
            decision=venue_decision(),
        )
    stages.update(construction_stages)
    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=1)
    sink = RecordingEvidenceSink()
    result = run_commitment_flow(
        proposal_id="prop-1",
        proposal=_proposal(),
        instrument_key=instrument_key(),
        reference=ordering(1),
        stages=stages,
        transmit=transmit,
        ledger=ledger,
        sink=sink,
        scheme=SCHEME,
    )
    return result, ledger, sink


# ---------------------------------------------------------------------------
# seam 1 — the gateway satisfies D-E1's Transmit slot
# ---------------------------------------------------------------------------


def test_the_gateway_satisfies_the_engine_transmit_protocol() -> None:
    """(§0.1-7) ``(AttemptRequest) -> SendHandoff`` — the slot D-E1 left open."""
    attempt, context = happy_context()
    gateway, _ = build_gateway(attempt=attempt, context=context)
    assert isinstance(gateway, Transmit)


def test_the_full_nineteen_step_flow_reaches_the_gateway_and_hands_off() -> None:
    """(§1.3) Steps 1-14 in the engine, 15-19 in the gateway — one continuous flow."""
    from tos.venue import ActionClass

    attempt, context = _flow_attempt_and_context()
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    result, ledger, _engine_sink = _run_flow(
        transmit=gateway, action_class=ActionClass.NEW_LONG
    )
    assert result.halt_reason is None, result.detail
    assert result.handed_off is True
    assert result.attempt is not None
    assert result.attempt.attempt_id == attempt.attempt_id
    assert result.handoff is not None
    assert result.handoff.accepted_for_transmission is True
    assert len(transport.requests) == 1
    (egress_result,) = gateway.results
    assert egress_result.kind is EgressResultKind.FULL_FILL
    assert "EGRESS_RESULT_RECORDED" in sink.kinds
    outstanding = ledger.outstanding(instrument_key())
    assert outstanding is not None
    assert outstanding.capacity_state is CapacityState.POTENTIALLY_LIVE


def test_the_step2_stage_reads_the_basis_off_the_engines_own_proposal() -> None:
    """(§3.1 3-way split) Decision identifies the basis; construction renders the size.

    The Proposal carries ``quantity_basis`` and **no** quantity field at all (RFC-008 §7
    "evidence, never capacity"), so the concrete size can only come from the derivation over the
    envelope-enclosed governance bound.
    """
    proposal = _proposal()
    assert proposal.quantity_basis == "RISK"
    for name in type(proposal).model_fields:
        assert name != "quantity", "a Proposal carries evidence, never capacity"
    step2, _ = _prebuilt_construction()
    built = step2.construction
    assert built is not None and built.intent is not None
    assert built.derivation.outcome.value == "DERIVED"
    assert built.intent.proposal_id == proposal.proposal_id
    assert built.intent.proposal_digest == proposal.canonical_digest


def test_a_denied_construction_halts_the_flow_before_the_send_boundary() -> None:
    """(§3.1 ↔ §4) An unknown price stops the flow at step 2; nothing reaches the gateway."""
    from tos.venue import ActionClass

    attempt, context = happy_context()
    transport = full_fill_transport()
    gateway, _ = build_gateway(attempt=attempt, context=context, transport=transport)
    result, _, _ = _run_flow(
        transmit=gateway,
        action_class=ActionClass.NEW_LONG,
        price=admitted_price(value=None),
    )
    assert result.handed_off is False
    assert result.halt_step is CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION
    assert result.halt_reason is HaltReason.STAGE_DENIED
    assert transport.requests == ()


def test_an_absent_action_class_makes_the_venue_stage_unknown() -> None:
    """(fail-closed) The step-3 stage stops the flow rather than passing an unjudged venue."""
    result, _, _ = _run_flow(transmit=None)
    assert result.halt_step is CommitmentStep.VENUE_ADMISSIBILITY_DECISION
    assert result.halt_reason is HaltReason.STAGE_UNKNOWN


def test_the_engine_still_refuses_to_host_the_send_boundary_itself() -> None:
    """(design #31 §4.5 / §0.1-7) Steps 15-19 stay constitutionally D-E4's."""
    from tos.engine import SEND_BOUNDARY_STEPS, validate_stage_map
    from tos.engine._base import ArtifactIntegrityError

    attempt, context = happy_context()
    gateway, _ = build_gateway(attempt=attempt, context=context)
    for step in SEND_BOUNDARY_STEPS:
        try:
            validate_stage_map({step: gateway})
        except ArtifactIntegrityError:
            continue
        raise AssertionError(f"the engine hosted send-boundary step {step}")


def test_a_flow_without_a_transmit_halts_rather_than_skipping_the_boundary() -> None:
    """(design #31 §4.5) An absent send boundary is not a licence to skip it."""
    from tos.venue import ActionClass

    result, _, _ = _run_flow(transmit=None, action_class=ActionClass.NEW_LONG)
    assert result.halt_step is CommitmentStep.SEND_BOUNDARY_VERIFICATION
    assert result.halt_reason is HaltReason.TRANSMIT_UNAVAILABLE


def test_the_construction_stages_admit_positively_inside_the_flow() -> None:
    """(§3.2) Steps 2 / 3 / 5 / 11 each produce an explicit ADMIT, never an implied pass."""
    from tos.venue import ActionClass

    attempt, context = _flow_attempt_and_context()
    gateway, _ = build_gateway(attempt=attempt, context=context)
    result, _, _ = _run_flow(transmit=gateway, action_class=ActionClass.NEW_LONG)
    outcomes = {verdict.step: verdict.outcome for verdict in result.verdicts}
    for step in (
        CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION,
        CommitmentStep.VENUE_ADMISSIBILITY_DECISION,
        CommitmentStep.ECONOMIC_EFFECT_ENVELOPE,
        CommitmentStep.ORDER_CONFORMANCE_PROOF,
    ):
        assert outcomes[step] is StageOutcome.ADMIT


# ---------------------------------------------------------------------------
# seam 2 — the two Protocol declarations have not drifted
# ---------------------------------------------------------------------------


def test_the_two_transport_protocol_declarations_are_signature_identical() -> None:
    """(§0.3/§5.1) Declared twice by firewall necessity; satisfied structurally — so assert it."""
    gateway_side = inspect.signature(SendTransport.send_once)
    adapter_side = inspect.signature(Transport.send_once)
    assert list(gateway_side.parameters) == list(adapter_side.parameters)
    for name, gateway_param in gateway_side.parameters.items():
        adapter_param = adapter_side.parameters[name]
        assert gateway_param.kind == adapter_param.kind, name
        assert str(gateway_param.annotation) == str(adapter_param.annotation), name
    assert str(gateway_side.return_annotation) == str(adapter_side.return_annotation)


def test_the_synthetic_transport_satisfies_the_gateway_side_port() -> None:
    """(§5.1) Structural satisfaction is what the firewall-imposed split relies on."""
    assert isinstance(full_fill_transport(), SendTransport)
