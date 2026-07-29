"""Shared builders for the ``tos.egressgw`` / ``tos.brokeradapter`` suites (design #34 §12).

Every builder is deterministic and clock-free: no ``time`` / ``datetime`` / ``random`` / ``uuid``
appears here either, because the §12.1-8 canary scans the shipped sources and the tests must not
model something the packages forbid.

The default context (:func:`happy_context`) is the **only** fully-admitting configuration in the
suite; every scenario derives from it by making exactly one fact restrictive, so a test that
passes proves the *single* fact under examination was load-bearing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tos.brokeradapter import SyntheticFillPolicy, SyntheticPaperTransport
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.cur import (
    CurrentnessRevision,
    EgressCurrentnessProof,
    EgressProofCoordinateSet,
    ProofResult,
)
from tos.egress import (
    CredentialRouteInventoryEntry,
    EgressCoordinateSet,
    EgressRequestRecord,
    QuorumCommitCertificate,
    RestrictiveLatchState,
)
from tos.egressgw import (
    AdmittedPriceObservation,
    BrokerEgressGateway,
    CandidateConstruction,
    EffectBasis,
    EffectDimensionSpec,
    LotRoundingPolicy,
    ProposedConstructionEnvelope,
    RecordingGatewayEvidenceSink,
    SendBoundaryContext,
    SizingBound,
    TransportNature,
    VenueQuantityConstraint,
    build_order_conformance_proof,
    construct_candidate_command,
    derive_order_size,
)
from tos.engine import (
    CAPSULE_CONTEXT_SOURCE,
    AttemptRequest,
    InstrumentKey,
    build_attempt_request,
)
from tos.ioc import AxisBinding, ConformanceAxis, QuantityUnitKind
from tos.ordering import OrderingEvent
from tos.rcl import TransmissionCapability
from tos.venue import (
    ActionClass,
    ActionPhaseAdmission,
    OrderAdmissibilityDecision,
    OrderAdmissibilityResult,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "acct-1"
INSTRUMENT = "ES"
SIDE = "BUY"
SESSION_PHASE = "CONTINUOUS"

#: ⚠ Every numeric below is **provisional**: the register carries no approved sizing bound
#: (P0-1) and no approved Broker Capability Profile INSTANCE (P0-2), so these are injected test
#: values, never authorized ones (design #34 §9).
NON_LIVE_TEST_ENVIRONMENT = "non-live-test"
RISK_BUDGET = Decimal("1000")
PER_UNIT_RISK = Decimal("50")
LOT_SIZE = Decimal("2")
MIN_QUANTITY = Decimal("2")
MAX_QUANTITY = Decimal("100")
PRICE = Decimal("4200")
CAPABILITY_NONCE = "cap-nonce-1"
PERMIT_NONCE = "permit-nonce-1"
PERMIT_IDENTITY = "permit-1"
PRINCIPAL = "egressgw-1"
TRANSPORT_PRINCIPAL = "synthetic-paper-1"
REQUEST_DIGEST = "req-digest-1"
CAPSULE_EGRESS_REQUEST_DIGEST = "req-bytes-digest-1"


def instrument_key() -> InstrumentKey:
    """The dispatch key used across the suite."""
    return InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)


def ordering(sequence: int = 1) -> OrderingEvent:
    """A totally-ordered event coordinate (an opaque injected bar index)."""
    return OrderingEvent(event_id=f"ev-{sequence}", quorum_commit_index=sequence)


# ---------------------------------------------------------------------------
# Order Construction inputs
# ---------------------------------------------------------------------------


def sizing_bound(**overrides: Any) -> SizingBound:
    """The governance-supplied sizing bound the proposed envelope encloses (⚠ provisional)."""
    base: dict[str, Any] = {
        "risk_budget": RISK_BUDGET,
        "per_unit_risk": PER_UNIT_RISK,
        "lot_size": LOT_SIZE,
        "lot_rounding": LotRoundingPolicy.FLOOR_TO_LOT,
        "min_quantity": MIN_QUANTITY,
        "max_quantity": MAX_QUANTITY,
        "quantity_unit": QuantityUnitKind.CONTRACTS,
        "admitted_quantity_bases": frozenset({"RISK"}),
    }
    base.update(overrides)
    return SizingBound(**base)


def non_derived_axes() -> tuple[AxisBinding, ...]:
    """The authorized axes the derivation does **not** own."""
    return (
        AxisBinding(axis=ConformanceAxis.ACCOUNT, value=ACCOUNT),
        AxisBinding(axis=ConformanceAxis.INSTRUMENT, value=INSTRUMENT),
        AxisBinding(axis=ConformanceAxis.DIRECTION, value="LONG"),
        AxisBinding(axis=ConformanceAxis.SIDE, value=SIDE),
        AxisBinding(axis=ConformanceAxis.ORDER_TYPE, value="LIMIT"),
        AxisBinding(axis=ConformanceAxis.TIF, value="DAY"),
        AxisBinding(axis=ConformanceAxis.ENVIRONMENT, value=NON_LIVE_TEST_ENVIRONMENT),
    )


def proposed_envelope(**overrides: Any) -> ProposedConstructionEnvelope:
    """The proposed Authorized Construction Envelope (ADR-002-002 §11.1:583)."""
    base: dict[str, Any] = {
        "envelope_generation": 1,
        "policy_binding_id": "ocp-1",
        "authorized_axis_bindings": non_derived_axes(),
        "sizing_bound": sizing_bound(),
        "effect_dimensions": (
            EffectDimensionSpec(
                dimension_id="notional",
                basis=EffectBasis.NOTIONAL,
                unit="KRW",
                scale="1",
            ),
            EffectDimensionSpec(
                dimension_id="units",
                basis=EffectBasis.QUANTITY,
                unit="contract",
                scale="1",
            ),
        ),
    }
    base.update(overrides)
    return ProposedConstructionEnvelope(**base)


def admitted_price(**overrides: Any) -> AdmittedPriceObservation:
    """An admitted Critical Input price observation (capsule-sourced — ⚠ D-E2 provisional)."""
    base: dict[str, Any] = {
        "source": CAPSULE_CONTEXT_SOURCE,
        "value": PRICE,
        "snapshot_digest": "cis-digest-1",
    }
    base.update(overrides)
    return AdmittedPriceObservation(**base)


def venue_quantity_constraint(**overrides: Any) -> VenueQuantityConstraint:
    """The injected venue / brokercap quantity constraint."""
    base: dict[str, Any] = {
        "lot_size": LOT_SIZE,
        "min_quantity": MIN_QUANTITY,
        "max_quantity": MAX_QUANTITY,
        "quantity_unit": QuantityUnitKind.CONTRACTS,
    }
    base.update(overrides)
    return VenueQuantityConstraint(**base)


def construction(**overrides: Any) -> CandidateConstruction:
    """A complete, CONFORMANT candidate construction (steps 2 / 5 / 11 inputs)."""
    envelope = overrides.pop("envelope", proposed_envelope())
    price = overrides.pop("price", admitted_price())
    constraint = overrides.pop("venue_constraint", venue_quantity_constraint())
    basis = overrides.pop("quantity_basis", "RISK")
    derivation = derive_order_size(
        quantity_basis=basis,
        envelope=envelope,
        price=price,
        venue_constraint=constraint,
    )
    base: dict[str, Any] = {
        "proposal_id": "prop-1",
        "proposal_digest": "prop-digest-1",
        "derivation": derivation,
        "envelope": envelope,
        "scheme": SCHEME,
        "intent_id": "intent-1",
        "intent_version": "intent-v1",
        "envelope_id": "env-1",
        "policy_id": "ocp-1",
        "policy_version": "ocp-v1",
        "policy_generation": 1,
        "command_id": "cmd-1",
        "generation": 1,
    }
    base.update(overrides)
    return construct_candidate_command(**base)


# ---------------------------------------------------------------------------
# Send-boundary facts
# ---------------------------------------------------------------------------


def attempt_request(
    *, proof_digest: str, permit_identity: str = PERMIT_IDENTITY, sequence: int = 1
) -> AttemptRequest:
    """The Coordinator's content-addressed step-12 attempt request."""
    return build_attempt_request(
        conformance_proof_digest=proof_digest,
        action_flow_permit_identity=permit_identity,
        reference=ordering(sequence),
        scheme=SCHEME,
    )


def transmission_capability(**overrides: Any) -> TransmissionCapability:
    """⚠ A provisional single-use Transmission Capability (issuance is RCL's, deferred)."""
    base: dict[str, Any] = {
        "capability_id": "txcap-1",
        "nonce": CAPABILITY_NONCE,
        "single_use": True,
        "reservation_identity": "resv-1",
        "attempt_identity": "attempt-1",
        "account_scope": ACCOUNT,
        "instrument_scope": INSTRUMENT,
        "side_action_scope": SIDE,
        "ledger_epoch": 1,
    }
    base.update(overrides)
    issued = TransmissionCapability.issue(scheme=SCHEME, **base)
    assert isinstance(issued, TransmissionCapability)
    return issued


def venue_policy(**overrides: Any) -> VenueConstraintPolicy:
    """A venue policy admitting the suite's action class in the suite's session phase."""
    base: dict[str, Any] = {
        "policy_id": "vpol-1",
        "policy_generation": 1,
        "scope": "scope-1",
        "admitting_phase_rules": (
            ActionPhaseAdmission(
                action=ActionClass.NEW_LONG, admitting_phases=frozenset({SESSION_PHASE})
            ),
        ),
    }
    base.update(overrides)
    issued = VenueConstraintPolicy.issue(scheme=SCHEME, **base)
    assert isinstance(issued, VenueConstraintPolicy)
    return issued


def venue_snapshot(**overrides: Any) -> VenueConstraintSnapshot:
    """A venue constraint snapshot bound to the suite's policy."""
    base: dict[str, Any] = {
        "snapshot_id": "vsnap-1",
        "constraint_generation": 1,
        "policy_id": "vpol-1",
        "policy_generation": 1,
        "observed_session_phase": SESSION_PHASE,
    }
    base.update(overrides)
    issued = VenueConstraintSnapshot.issue(scheme=SCHEME, **base)
    assert isinstance(issued, VenueConstraintSnapshot)
    return issued


def venue_shape(**overrides: Any) -> OrderShapeFields:
    """An order shape that is positively **not** silently rounded."""
    base: dict[str, Any] = {
        "price": 4200,
        "quantity": 20,
        "order_type": "LIMIT",
        "tif": "DAY",
        "side": SIDE,
        "position_effect": "OPEN",
        "silently_rounded": False,
    }
    base.update(overrides)
    return OrderShapeFields(**base)


def venue_shape_constraints(**overrides: Any) -> VenueShapeConstraints:
    """Injected venue shape constraints admitting the suite's shape."""
    base: dict[str, Any] = {
        "price_min": 1000,
        "price_max": 9000,
        "tick_size": 25,
        "lot_size": 2,
        "min_quantity": 2,
        "max_quantity": 100,
        "allowed_order_types": frozenset({"LIMIT"}),
        "allowed_tifs": frozenset({"DAY"}),
        "allowed_sides": frozenset({SIDE}),
        "allowed_position_effects": frozenset({"OPEN"}),
    }
    base.update(overrides)
    return VenueShapeConstraints(**base)


def venue_decision(
    result: OrderAdmissibilityResult = OrderAdmissibilityResult.ADMISSIBLE, **overrides: Any
) -> OrderAdmissibilityDecision:
    """An issued Order Admissibility Decision carrying ``result``."""
    base: dict[str, Any] = {
        "decision_id": "vdec-1",
        "decision_generation": 1,
        "result": result,
    }
    base.update(overrides)
    issued = OrderAdmissibilityDecision.issue(scheme=SCHEME, **base)
    assert isinstance(issued, OrderAdmissibilityDecision)
    return issued


def currentness_proof(**overrides: Any) -> EgressCurrentnessProof:
    """A structurally complete, admissible, CURRENT Egress Currentness Proof.

    ⚠ Structure and coordinates only: the owner submissions inside the Safety Currentness
    Vector are provisional / D-E2-dependent (design #34 §4.3).
    """
    revision = CurrentnessRevision(revision_id="rev-1", commit_index=1)
    base: dict[str, Any] = {
        "proof_id": "ecp-1",
        "nonce": "ecp-nonce-1",
        "vector_id": "scv-1",
        "vector_digest": "scv-digest-1",
        "committed_revision": revision,
        "bound_generations": (1,),
        "restrictive_floors": (1,),
        "capability_claim_command": "ClaimCapabilityAndMarkSendStarted",
        "claim_committed_result": "COMMITTED",
        "send_started_revision": revision,
        "result": ProofResult.CURRENT,
    }
    lifecycle: dict[str, Any] = {
        "single_use_consumed": False,
        "is_expired": False,
        "egress_coordinates": EgressProofCoordinateSet(
            principal=PRINCIPAL, local_latch_clear=True
        ),
    }
    lifecycle.update({k: overrides.pop(k) for k in list(overrides) if k in lifecycle})
    base.update(overrides)
    issued = EgressCurrentnessProof.issue(scheme=SCHEME, **base, **lifecycle)
    assert isinstance(issued, EgressCurrentnessProof)
    return issued


def authorized_coordinates(**overrides: Any) -> EgressCoordinateSet:
    """The authorized egress coordinate set item 17 compares against."""
    base: dict[str, Any] = {
        "endpoint": "synthetic://paper/order",
        "account": ACCOUNT,
        "environment": NON_LIVE_TEST_ENVIRONMENT,
        "action": "NEW_ORDER",
        "method": "SUBMIT",
        "route_identity": "synthetic-route",
        "credential_generation": 0,
        "broker_session_generation": 0,
        "egress_generation": 1,
        "active_principal": PRINCIPAL,
    }
    base.update(overrides)
    return EgressCoordinateSet(**base)


def egress_request(command_digest: str | None, **overrides: Any) -> EgressRequestRecord:
    """The exact outbound egress request record, coordinate-equal to the authorized set."""
    coordinates = authorized_coordinates()
    base: dict[str, Any] = {
        "request_id": "ereq-1",
        "request_bytes_digest": CAPSULE_EGRESS_REQUEST_DIGEST,
        "canonical_command_digest": command_digest,
        "endpoint": coordinates.endpoint,
        "account": coordinates.account,
        "environment": coordinates.environment,
        "action": coordinates.action,
        "method": coordinates.method,
        "side": SIDE,
        "route_identity": coordinates.route_identity,
        "credential_generation": coordinates.credential_generation,
        "broker_session_generation": coordinates.broker_session_generation,
        "egress_generation": coordinates.egress_generation,
        "active_principal": coordinates.active_principal,
    }
    base.update(overrides)
    issued = EgressRequestRecord.issue(scheme=SCHEME, **base)
    assert isinstance(issued, EgressRequestRecord)
    return issued


def quorum_certificate(command_digest: str | None, **overrides: Any) -> QuorumCommitCertificate:
    """⚠ A provisional QCC: only its command-digest axis is consumed (quorum runtime deferred)."""
    base: dict[str, Any] = {
        "qcc_id": "qcc-1",
        "cluster_identity": "cluster-1",
        "capacity_domain": "domain-1",
        "membership_generation": 1,
        "restore_generation": 1,
        "writer_epoch": 1,
        "committed_revision": 1,
        "canonical_command_digest": command_digest,
        "resulting_state_digest": "state-digest-1",
        "egress_generation": 1,
        "active_egress_principal": PRINCIPAL,
    }
    base.update(overrides)
    issued = QuorumCommitCertificate.issue(scheme=SCHEME, **base)
    assert isinstance(issued, QuorumCommitCertificate)
    return issued


def synthetic_nature(**overrides: Any) -> TransportNature:
    """The synthetic transport's declared nature — every flag an explicit ``False``."""
    base: dict[str, Any] = {
        "principal": TRANSPORT_PRINCIPAL,
        "reaches_broker": False,
        "credential_bearing": False,
        "route_bearing": False,
        "risk_relevant_live": False,
    }
    base.update(overrides)
    return TransportNature(**base)


def disjoint_inventory() -> tuple[CredentialRouteInventoryEntry, ...]:
    """A credential-route inventory corroborating the synthetic transport structurally."""
    return (
        CredentialRouteInventoryEntry(
            principal=TRANSPORT_PRINCIPAL,
            usable_credential=False,
            broker_route=False,
            inside_boundary=True,
        ),
        CredentialRouteInventoryEntry(
            principal=PRINCIPAL,
            usable_credential=False,
            broker_route=False,
            inside_boundary=True,
        ),
    )


def happy_context(**overrides: Any) -> tuple[AttemptRequest, SendBoundaryContext]:
    """A fully-admitting attempt + send-boundary context (the suite's single baseline).

    Every scenario derives from this by making exactly one fact restrictive, so a passing test
    proves that one fact was load-bearing rather than that some other fact happened to hold.
    """
    built = construction()
    assert built.command is not None
    proof = build_order_conformance_proof(
        construction=built,
        scheme=SCHEME,
        proof_id="ocp-proof-1",
        proof_generation=1,
        required_authority_scope=("scope-1",),
    )
    assert proof is not None
    attempt = attempt_request(proof_digest=proof.canonical_digest or "")
    assert built.intent is not None
    base: dict[str, Any] = {
        "instrument_key": instrument_key(),
        "transport_nature": synthetic_nature(),
        "non_live_test_environment_token": NON_LIVE_TEST_ENVIRONMENT,
        "scope_environment": NON_LIVE_TEST_ENVIRONMENT,
        "evidence_environment": NON_LIVE_TEST_ENVIRONMENT,
        "environment_inherited": False,
        "credential_route_inventory": disjoint_inventory(),
        "transmission_capability": transmission_capability(),
        "capability_nonce": CAPABILITY_NONCE,
        "action_flow_permit_nonce": PERMIT_NONCE,
        "prior_claims": (),
        "principal": PRINCIPAL,
        "request_digest": REQUEST_DIGEST,
        "reservation_attempt_id": attempt.attempt_id,
        "reservation_conformance_proof_digest": attempt.conformance_proof_digest,
        "reservation_action_flow_permit_identity": attempt.action_flow_permit_identity,
        "commitment_epoch_current": True,
        "account_instrument_action_allowed": True,
        "max_quantity_within_allowance": True,
        "venue_session_account_facts_current": True,
        "broker_constraint_generation_current": True,
        "venue_snapshot": venue_snapshot(),
        "venue_policy": venue_policy(),
        "venue_decision": venue_decision(),
        "observed_session_phase": SESSION_PHASE,
        "action_class": ActionClass.NEW_LONG,
        "order_shape": venue_shape(),
        "venue_shape_constraints": venue_shape_constraints(),
        "construction": built,
        "conformance_proof": proof,
        "approval_consumed_for_this_intent": True,
        "approval_intent_binding_digest": built.intent.canonical_digest,
        "action_flow_permit_identity": PERMIT_IDENTITY,
        "action_flow_commitment_current": True,
        "egress_currentness_proof": currentness_proof(),
        "egress_currentness_result": ProofResult.CURRENT,
        "restrictive_latch_state": RestrictiveLatchState.CLEAR,
        "worst_credible_capacity": 1,
        "egress_request": egress_request(built.command.canonical_digest),
        "quorum_commit_certificate": quorum_certificate(built.command.canonical_digest),
        "authorized_coordinates": authorized_coordinates(),
        "capsule_egress_request_digest": CAPSULE_EGRESS_REQUEST_DIGEST,
        "outbound_quantity": built.derivation.quantity,
        "outbound_price": built.derivation.price,
        "outbound_side": SIDE,
        "reference": ordering(1),
    }
    base.update(overrides)
    return attempt, SendBoundaryContext(**base)


def full_fill_transport() -> SyntheticPaperTransport:
    """A synthetic transport whose deterministic band fills the whole authorized quantity."""
    return SyntheticPaperTransport(
        SyntheticFillPolicy(fill_numerator=1, fill_denominator=1, lot_size=LOT_SIZE)
    )


def build_gateway(
    *,
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    transport: Any = None,
) -> tuple[BrokerEgressGateway, RecordingGatewayEvidenceSink]:
    """Wire a gateway over one attempt's context and return it with its recording sink."""
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context},
        transport=transport if transport is not None else full_fill_transport(),
        sink=sink,
    )
    return gateway, sink
