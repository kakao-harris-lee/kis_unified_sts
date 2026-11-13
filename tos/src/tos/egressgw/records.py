"""egressgw frozen models — construction inputs / outputs and the send-boundary verify records."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import ClassVar

from pydantic import model_validator

from tos.brokercap import (
    BrokerCapabilityProfile,
    CapabilityTuple,
    RequiredCapabilitySet,
)
from tos.cur import EgressCurrentnessProof, ProofResult
from tos.egress import (
    ClaimObservation,
    CredentialRouteInventoryEntry,
    EgressCoordinateSet,
    EgressRequestRecord,
    QuorumCommitCertificate,
    RestrictiveLatchState,
)
from tos.egressgw._base import (
    AllFalseConstructionCoordinatorAuthority,
    AllFalseGatewayAuthority,
    ArtifactIntegrityError,
    CanonicalDecimal,
    FrozenModel,
)
from tos.egressgw.seal import SendSeal
from tos.egressgw.vocabulary import (
    DEFERRED_ITEMS,
    PROVISIONAL_ITEMS,
    REALIZED_ITEMS,
    BrokerApplicability,
    DerivationOutcome,
    EffectBasis,
    LotRoundingPolicy,
    SendHaltReason,
    SendVerifyItem,
    VerifyDisposition,
    VerifyOutcome,
)
from tos.engine import AttemptRequest, CommitmentStep, InstrumentKey
from tos.ioc import (
    ApprovedIntentContract,
    AuthorizedConstructionEnvelope,
    AxisBinding,
    CanonicalBrokerCommand,
    ConformanceAxis,
    ConformanceResult,
    OrderConformanceProof,
    OrderConstructionPolicy,
    QuantityUnitKind,
)
from tos.ordering import OrderingEvent
from tos.rcl import TransmissionCapability
from tos.venue import (
    ActionClass,
    OrderAdmissibilityDecision,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)

__all__ = [
    "DERIVED_AXES",
    "AdmittedPriceObservation",
    "CandidateConstruction",
    "EffectDimensionSpec",
    "GatewayEvidenceRecord",
    "ProposedConstructionEnvelope",
    "positive_decimal",
    "QuantityDerivation",
    "SendBoundaryContext",
    "SendBoundaryVerification",
    "SizingBound",
    "TransportNature",
    "VenueQuantityConstraint",
    "VerifyItemVerdict",
    "send_boundary_context",
]


class SizingBound(FrozenModel):
    """The sizing bound **enclosed in** the proposed Authorized Construction Envelope (§3.1)."""

    risk_budget: CanonicalDecimal | None = None
    per_unit_risk: CanonicalDecimal | None = None
    lot_size: CanonicalDecimal | None = None
    lot_rounding: LotRoundingPolicy | None = None
    min_quantity: CanonicalDecimal | None = None
    max_quantity: CanonicalDecimal | None = None
    max_notional: CanonicalDecimal | None = None
    quantity_unit: QuantityUnitKind | None = None
    admitted_quantity_bases: frozenset[str] = frozenset()


class AdmittedPriceObservation(FrozenModel):
    """One admitted Critical Input price observation (design #34 §3.1 (iii))."""

    source: str | None = None
    value: CanonicalDecimal | None = None
    snapshot_digest: str | None = None
    value_payload_digest: str | None = None


class VenueQuantityConstraint(FrozenModel):
    """The venue / brokercap quantity constraint the derivation must fall inside (§3.1 (iv))."""

    lot_size: CanonicalDecimal | None = None
    min_quantity: CanonicalDecimal | None = None
    max_quantity: CanonicalDecimal | None = None
    quantity_unit: QuantityUnitKind | None = None


class EffectDimensionSpec(FrozenModel):
    """One Economic Effect Envelope dimension's derivation spec (design #34 §3.2 step 5)."""

    dimension_id: str | None = None
    basis: EffectBasis | None = None
    unit: str | None = None
    scale: str | None = None


class ProposedConstructionEnvelope(FrozenModel):
    """The proposed Authorized Construction Envelope for step 2 (ADR-002-002 §11.1:583)."""

    envelope_generation: int | None = None
    policy_binding_id: str | None = None
    authorized_axis_bindings: tuple[AxisBinding, ...] = ()
    sizing_bound: SizingBound | None = None
    effect_dimensions: tuple[EffectDimensionSpec, ...] = ()

    @model_validator(mode="after")
    def _no_derived_axis_is_pre_declared(self) -> ProposedConstructionEnvelope:
        """Reject an envelope that pre-declares a derivation-owned axis (ambiguity is denial)."""
        for binding in self.authorized_axis_bindings:
            if binding.axis is not None and binding.axis in DERIVED_AXES:
                raise ArtifactIntegrityError(
                    f"ProposedConstructionEnvelope pre-declares the derived axis "
                    f"{binding.axis.value} — quantity / price / unit are produced by the "
                    "deterministic derivation from the enclosed sizing bound, and a second "
                    "declaration would make the authorized value ambiguous (ADR-002-020 "
                    "§10:284 ambiguity is denial; design #34 §3.1)"
                )
        return self


DERIVED_AXES: frozenset[ConformanceAxis] = frozenset(
    {ConformanceAxis.QUANTITY, ConformanceAxis.PRICE, ConformanceAxis.UNIT}
)


class QuantityDerivation(FrozenModel):
    """The result of the deterministic, bounded, no-repair G5 derivation (design #34 §3.1)."""

    outcome: DerivationOutcome
    quantity: CanonicalDecimal | None = None
    price: CanonicalDecimal | None = None
    quantity_unit: QuantityUnitKind | None = None
    rule: str | None = None
    denial_reason: str | None = None

    @model_validator(mode="after")
    def _outcome_shape_consistent(self) -> QuantityDerivation:
        """A ``DERIVED`` result carries values; a ``DENIED`` one carries none but a reason."""
        if self.outcome is DerivationOutcome.DERIVED:
            if (
                self.quantity is None
                or self.price is None
                or self.quantity_unit is None
                or self.rule is None
            ):
                raise ArtifactIntegrityError(
                    "a DERIVED QuantityDerivation must carry quantity, price, unit, and the "
                    "authored rule — an unquantified derivation is not a derivation "
                    "(design #34 §3.1)"
                )
            if self.denial_reason is not None:
                raise ArtifactIntegrityError(
                    "a DERIVED QuantityDerivation must not carry a denial reason"
                )
            return self
        if self.quantity is not None or self.price is not None:
            raise ArtifactIntegrityError(
                "a DENIED QuantityDerivation must carry no quantity or price — a partially "
                "repaired shape is exactly the RFC-005 §7:211 repair prohibition "
                "(design #34 §3.1)"
            )
        if not (self.denial_reason or "").strip():
            raise ArtifactIntegrityError(
                "a DENIED QuantityDerivation must record why — a restrictive stop without a "
                "recorded reason is a silent stop (design #34 §4.2)"
            )
        return self


class CandidateConstruction(FrozenModel):
    """The step-2 candidate construction bundle (design #34 §3.2)."""

    derivation: QuantityDerivation
    intent: ApprovedIntentContract | None = None
    envelope: AuthorizedConstructionEnvelope | None = None
    policy: OrderConstructionPolicy | None = None
    command: CanonicalBrokerCommand | None = None
    conformance_result: ConformanceResult | None = None
    numerical_result: ConformanceResult | None = None
    no_silent_widening_ok: bool | None = None
    denial_reason: str | None = None
    authority_effect: AllFalseConstructionCoordinatorAuthority = (
        AllFalseConstructionCoordinatorAuthority()
    )

    @model_validator(mode="after")
    def _shape_is_one_of_the_sanctioned_bundles(self) -> CandidateConstruction:
        """Reject any bundle that is not a denied or a fully-built shape (design #34 §3.2)."""
        if self.command is None:
            if not (self.denial_reason or "").strip():
                raise ArtifactIntegrityError(
                    "a denied CandidateConstruction (no command) must record a non-empty "
                    "denial_reason — a restrictive stop without a recorded reason is a silent "
                    "stop (design #34 §4.2)"
                )
            if (
                self.conformance_result is not None
                or self.numerical_result is not None
                or self.no_silent_widening_ok is not None
            ):
                raise ArtifactIntegrityError(
                    "a denied CandidateConstruction (no command) must carry no ioc verdict — "
                    "conformance_result / numerical_result / no_silent_widening_ok must all be "
                    "None; a verdict over a command that was never compiled is not a decision "
                    "(design #34 §3.2)"
                )
            return self
        if self.denial_reason is not None:
            raise ArtifactIntegrityError(
                "a built CandidateConstruction (command present) must not carry a "
                "denial_reason — a command and its own denial cannot coexist (design #34 §3.2)"
            )
        missing = [
            name
            for name, value in (
                ("intent", self.intent),
                ("envelope", self.envelope),
                ("policy", self.policy),
                ("conformance_result", self.conformance_result),
                ("numerical_result", self.numerical_result),
                ("no_silent_widening_ok", self.no_silent_widening_ok),
            )
            if value is None
        ]
        if missing:
            raise ArtifactIntegrityError(
                "a built CandidateConstruction (command present) must carry intent, envelope, "
                "policy, and both ioc verdicts (conformance_result, numerical_result, "
                f"no_silent_widening_ok) — missing: {', '.join(missing)} (design #34 §3.2 / "
                "IOC-INV-006 every dependent gate evaluated it)"
            )
        return self


class TransportNature(FrozenModel):
    """The **declared** nature of the injected transport (design #34 §4.2)."""

    principal: str | None = None
    reaches_broker: bool | None = None
    credential_bearing: bool | None = None
    route_bearing: bool | None = None
    risk_relevant_live: bool | None = None


class VerifyItemVerdict(FrozenModel):
    """One verify item's recorded judgement (design #34 §4.1 / §4.2)."""

    item: SendVerifyItem
    disposition: VerifyDisposition
    outcome: VerifyOutcome
    reason: str | None = None
    native_verdict_type: str | None = None
    native_verdict_value: str | None = None
    preserved_worst_credible_capacity: int | None = None
    preserved_obligation_magnitude_unknown: bool = False
    authority_effect: AllFalseGatewayAuthority = AllFalseGatewayAuthority()

    @model_validator(mode="after")
    def _not_applicable_only_for_deferred(self) -> VerifyItemVerdict:
        """Reject an N/A judgement on anything but a deferred-applicability item."""
        if (
            self.outcome is VerifyOutcome.NOT_APPLICABLE
            and self.disposition is not VerifyDisposition.DEFERRED_APPLICABILITY
        ):
            raise ArtifactIntegrityError(
                f"verify item {self.item.value} is {self.disposition.value} and cannot be "
                "recorded NOT_APPLICABLE — only the deferred safety-governance mesh may be "
                "explicitly N/A, and only under a positively established non-broker synthetic "
                "send (design #34 §4.2)"
            )
        return self

    @model_validator(mode="after")
    def _preserved_capacity_only_for_currentness(self) -> VerifyItemVerdict:
        """Reject a preserved-capacity obligation recorded on anything but item 16 (kernel round #1 §1.3)."""
        if (
            self.preserved_worst_credible_capacity is not None
            and self.item is not SendVerifyItem.CURRENTNESS
        ):
            raise ArtifactIntegrityError(
                f"verify item {self.item.value} cannot record a preserved worst-credible "
                "capacity obligation — only item 16 (CURRENTNESS) may author cur's "
                "unknown-preservation obligation (CUR-INV-011:183; kernel round #1 §1.3)"
            )
        return self

    @model_validator(mode="after")
    def _magnitude_unknown_only_for_currentness_with_no_concrete_obligation(
        self,
    ) -> VerifyItemVerdict:
        """Reject a magnitude-unknown flag on anything but item 16, or beside a concrete obligation."""
        if self.preserved_obligation_magnitude_unknown and (
            self.item is not SendVerifyItem.CURRENTNESS
            or self.preserved_worst_credible_capacity is not None
        ):
            raise ArtifactIntegrityError(
                f"verify item {self.item.value} cannot record a magnitude-unknown preserved "
                "obligation — only item 16 (CURRENTNESS) may author it, and only when no "
                "concrete worst-credible capacity is recorded (CUR-INV-011:183; kernel round #1 "
                "review #4)"
            )
        return self


def _verdict(
    item: SendVerifyItem,
    outcome: VerifyOutcome,
    *,
    reason: str | None = None,
    native: object | None = None,
    native_value: str | None = None,
    preserved_worst_credible_capacity: int | None = None,
    preserved_obligation_magnitude_unknown: bool = False,
) -> VerifyItemVerdict:
    """Assemble one item verdict, deriving its disposition from the design §4.1 partition."""
    if item in REALIZED_ITEMS:
        disposition = VerifyDisposition.REALIZED_STRUCTURAL
    elif item in PROVISIONAL_ITEMS:
        disposition = VerifyDisposition.PROVISIONAL_STAND_IN
    elif item in DEFERRED_ITEMS:
        disposition = VerifyDisposition.DEFERRED_APPLICABILITY
    else:
        raise ArtifactIntegrityError(
            f"{item!r} is not judged at the send boundary (plan S2-b fold) — no verdict for it"
        )
    return VerifyItemVerdict(
        item=item,
        disposition=disposition,
        outcome=outcome,
        reason=reason,
        native_verdict_type=None if native is None else type(native).__name__,
        native_verdict_value=native_value,
        preserved_worst_credible_capacity=preserved_worst_credible_capacity,
        preserved_obligation_magnitude_unknown=preserved_obligation_magnitude_unknown,
    )


class SendBoundaryVerification(FrozenModel):
    """The whole step-15 verify result (design #34 §4.1)."""

    attempt_id: str
    applicability: BrokerApplicability
    verdicts: tuple[VerifyItemVerdict, ...] = ()
    admitted: bool | None = None
    halt_item: SendVerifyItem | None = None
    halt_reason: SendHaltReason | None = None
    detail: str | None = None
    authority_effect: AllFalseGatewayAuthority = AllFalseGatewayAuthority()


class GatewayEvidenceRecord(FrozenModel):
    """One provisional send-boundary evidence record (design #34 §4.6 / §1.3 step 19)."""

    kind: str
    attempt_id: str | None = None
    item: SendVerifyItem | None = None
    outcome: VerifyOutcome | None = None
    applicability: BrokerApplicability | None = None
    halt_reason: SendHaltReason | None = None
    detail: str | None = None
    preserved_worst_credible_capacity: int | None = None
    preserved_obligation_magnitude_unknown: bool = False
    send_seal: SendSeal | None = None
    send_seal_digest: str | None = None
    step: CommitmentStep
    authority_effect: AllFalseGatewayAuthority = AllFalseGatewayAuthority()

    SEND_SEAL_DIGEST_KINDS: ClassVar[frozenset[str]] = frozenset(
        {"SEND_STARTED", "NETWORK_CALL_ENTERED", "EGRESS_RESULT_RECORDED"}
    )

    FIXED_KIND_STEPS: ClassVar[dict[str, CommitmentStep]] = {
        "VERIFY_ITEM": CommitmentStep.SEND_BOUNDARY_VERIFICATION,
        "SEND_SEALED": CommitmentStep.SEND_BOUNDARY_VERIFICATION,
        "SEND_STARTED": CommitmentStep.SEND_STARTED_DURABLE,
        "POTENTIALLY_LIVE_OBSERVED": CommitmentStep.POTENTIALLY_LIVE_TRANSITION,
        "NETWORK_CALL_ENTERED": CommitmentStep.NETWORK_CALL,
        "EGRESS_RESULT_RECORDED": CommitmentStep.EVIDENCE_RECORD,
        "UNCERTAIN_SEND": CommitmentStep.EVIDENCE_RECORD,
    }

    @model_validator(mode="after")
    def _seal_fields_match_their_kind(self) -> GatewayEvidenceRecord:
        """Reject ``send_seal`` / ``send_seal_digest`` on a kind that never legitimately carries it."""
        if self.send_seal is not None and self.kind != "SEND_SEALED":
            raise ArtifactIntegrityError(
                f"GatewayEvidenceRecord(kind={self.kind!r}) carries a non-None send_seal — the "
                "full seal is written exactly once, on the SEND_SEALED record only (Phase 4 작업 "
                "6 §1.2; independent review finding #9)"
            )
        if (
            self.send_seal_digest is not None
            and self.kind not in self.SEND_SEAL_DIGEST_KINDS
        ):
            raise ArtifactIntegrityError(
                f"GatewayEvidenceRecord(kind={self.kind!r}) carries a non-None "
                f"send_seal_digest — only {sorted(self.SEND_SEAL_DIGEST_KINDS)} legitimately "
                "carry it (Phase 4 작업 6 §1.2; independent review finding #9)"
            )
        return self

    @model_validator(mode="after")
    def _step_matches_fixed_kind_when_given(self) -> GatewayEvidenceRecord:
        """``step`` must be the kind's fixed one, when that kind has exactly one."""
        expected = self.FIXED_KIND_STEPS.get(self.kind)
        if expected is not None and self.step is not expected:
            raise ArtifactIntegrityError(
                f"GatewayEvidenceRecord(kind={self.kind!r}) was stamped step={self.step!r}, "
                f"but this kind is always {expected!r} (Phase 3 wave 3 KW3-GW — the mutation-"
                "matrix finding this field closes: kind alone did not carry step identity)"
            )
        return self


class SendBoundaryContext(FrozenModel):
    """Every injected fact the RFC-002 §10.8:741-759 verify list consumes (design #34 §4.1)."""

    instrument_key: InstrumentKey | None = None
    transport_nature: TransportNature | None = None
    non_live_test_environment_token: str | None = None
    scope_environment: str | None = None
    evidence_environment: str | None = None
    environment_inherited: bool | None = None
    credential_route_inventory: tuple[CredentialRouteInventoryEntry, ...] = ()

    transmission_capability: TransmissionCapability | None = None
    capability_nonce: str | None = None
    action_flow_permit_nonce: str | None = None
    prior_claims: tuple[ClaimObservation, ...] = ()
    principal: str | None = None
    request_digest: str | None = None

    reservation_attempt_id: str | None = None
    reservation_conformance_proof_digest: str | None = None
    reservation_action_flow_permit_identity: str | None = None

    commitment_epoch_current: bool | None = None

    safety_authority_epoch_current: bool | None = None
    live_scope_valid: bool | None = None

    broker_capability_profile: BrokerCapabilityProfile | None = None
    required_capability_set: RequiredCapabilitySet | None = None
    broker_profile_version_current: bool | None = None
    capability_tuples: tuple[CapabilityTuple, ...] = ()
    idempotency_proven: bool | None = None
    account_instrument_action_allowed: bool | None = None
    max_quantity_within_allowance: bool | None = None
    session_facts_current: bool | None = None
    tradability_facts_current: bool | None = None
    account_facts_current: bool | None = None
    broker_constraint_generation_current: bool | None = None

    venue_snapshot: VenueConstraintSnapshot | None = None
    venue_policy: VenueConstraintPolicy | None = None
    venue_decision: OrderAdmissibilityDecision | None = None
    observed_session_phase: str | None = None
    action_class: ActionClass | None = None
    order_shape: OrderShapeFields | None = None
    venue_shape_constraints: VenueShapeConstraints | None = None

    construction: CandidateConstruction | None = None
    conformance_proof: OrderConformanceProof | None = None

    approval_consumed_for_this_intent: bool | None = None
    approval_intent_binding_digest: str | None = None

    action_flow_permit_identity: str | None = None
    action_flow_commitment_current: bool | None = None

    egress_currentness_proof: EgressCurrentnessProof | None = None
    egress_currentness_result: ProofResult | None = None
    restrictive_latch_state: RestrictiveLatchState | None = None
    worst_credible_capacity: int | None = None

    egress_request: EgressRequestRecord | None = None
    quorum_commit_certificate: QuorumCommitCertificate | None = None
    authorized_coordinates: EgressCoordinateSet | None = None
    capsule_egress_request_digest: str | None = None

    outbound_quantity: CanonicalDecimal | None = None
    outbound_price: CanonicalDecimal | None = None
    outbound_side: str | None = None
    reference: OrderingEvent = OrderingEvent()


def positive_decimal(value: Decimal | None) -> bool:
    """Whether ``value`` is a present, finite, strictly positive magnitude (fail-closed)."""
    if value is None:
        return False
    if not value.is_finite():
        return False
    return value > 0


def send_boundary_context(
    *,
    attempt: AttemptRequest,
    construction: CandidateConstruction,
    conformance_proof: OrderConformanceProof | None,
    reference: OrderingEvent,
    egress_request_for_command: (
        Callable[[str | None], EgressRequestRecord | None] | None
    ) = None,
    quorum_certificate_for_command: (
        Callable[[str | None], QuorumCommitCertificate | None] | None
    ) = None,
    instrument_key: InstrumentKey | None = None,
    transport_nature: TransportNature | None = None,
    non_live_test_environment_token: str | None = None,
    scope_environment: str | None = None,
    evidence_environment: str | None = None,
    environment_inherited: bool | None = None,
    credential_route_inventory: tuple[CredentialRouteInventoryEntry, ...] = (),
    transmission_capability: TransmissionCapability | None = None,
    capability_nonce: str | None = None,
    action_flow_permit_nonce: str | None = None,
    prior_claims: tuple[ClaimObservation, ...] = (),
    principal: str | None = None,
    request_digest: str | None = None,
    venue_snapshot: VenueConstraintSnapshot | None = None,
    venue_policy: VenueConstraintPolicy | None = None,
    venue_decision: OrderAdmissibilityDecision | None = None,
    observed_session_phase: str | None = None,
    action_class: ActionClass | None = None,
    order_shape: OrderShapeFields | None = None,
    venue_shape_constraints: VenueShapeConstraints | None = None,
    egress_currentness_proof: EgressCurrentnessProof | None = None,
    egress_currentness_result: ProofResult | None = None,
    restrictive_latch_state: RestrictiveLatchState | None = None,
    worst_credible_capacity: int | None = None,
    authorized_coordinates: EgressCoordinateSet | None = None,
    capsule_egress_request_digest: str | None = None,
    safety_authority_epoch_current: bool | None = None,
    live_scope_valid: bool | None = None,
    commitment_epoch_current: bool | None = None,
    broker_capability_profile: BrokerCapabilityProfile | None = None,
    required_capability_set: RequiredCapabilitySet | None = None,
    broker_profile_version_current: bool | None = None,
    capability_tuples: tuple[CapabilityTuple, ...] = (),
    idempotency_proven: bool | None = None,
    account_instrument_action_allowed: bool | None = None,
    max_quantity_within_allowance: bool | None = None,
    session_facts_current: bool | None = None,
    tradability_facts_current: bool | None = None,
    account_facts_current: bool | None = None,
    broker_constraint_generation_current: bool | None = None,
    approval_consumed_for_this_intent: bool | None = None,
    action_flow_permit_identity: str | None = None,
    action_flow_commitment_current: bool | None = None,
    outbound_side: str | None = None,
) -> SendBoundaryContext:
    """Assemble the verify list's input surface from **this flow's own artifacts** (§35 §3.1)."""
    command = construction.command
    command_digest = None if command is None else command.canonical_digest
    intent = construction.intent
    egress_request: EgressRequestRecord | None = None
    quorum_commit_certificate: QuorumCommitCertificate | None = None
    if command_digest is not None:
        if egress_request_for_command is not None:
            egress_request = egress_request_for_command(command_digest)
        if quorum_certificate_for_command is not None:
            quorum_commit_certificate = quorum_certificate_for_command(command_digest)
    return SendBoundaryContext(
        instrument_key=instrument_key,
        transport_nature=transport_nature,
        non_live_test_environment_token=non_live_test_environment_token,
        scope_environment=scope_environment,
        evidence_environment=evidence_environment,
        environment_inherited=environment_inherited,
        credential_route_inventory=credential_route_inventory,
        transmission_capability=transmission_capability,
        capability_nonce=capability_nonce,
        action_flow_permit_nonce=action_flow_permit_nonce,
        prior_claims=prior_claims,
        principal=principal,
        request_digest=request_digest,
        reservation_attempt_id=attempt.attempt_id,
        reservation_conformance_proof_digest=attempt.conformance_proof_digest,
        reservation_action_flow_permit_identity=attempt.action_flow_permit_identity,
        safety_authority_epoch_current=safety_authority_epoch_current,
        live_scope_valid=live_scope_valid,
        commitment_epoch_current=commitment_epoch_current,
        broker_capability_profile=broker_capability_profile,
        required_capability_set=required_capability_set,
        broker_profile_version_current=broker_profile_version_current,
        capability_tuples=capability_tuples,
        idempotency_proven=idempotency_proven,
        account_instrument_action_allowed=account_instrument_action_allowed,
        max_quantity_within_allowance=max_quantity_within_allowance,
        session_facts_current=session_facts_current,
        tradability_facts_current=tradability_facts_current,
        account_facts_current=account_facts_current,
        broker_constraint_generation_current=broker_constraint_generation_current,
        venue_snapshot=venue_snapshot,
        venue_policy=venue_policy,
        venue_decision=venue_decision,
        observed_session_phase=observed_session_phase,
        action_class=action_class,
        order_shape=order_shape,
        venue_shape_constraints=venue_shape_constraints,
        construction=construction,
        conformance_proof=conformance_proof,
        approval_consumed_for_this_intent=approval_consumed_for_this_intent,
        approval_intent_binding_digest=(
            None if intent is None else intent.canonical_digest
        ),
        action_flow_permit_identity=action_flow_permit_identity,
        action_flow_commitment_current=action_flow_commitment_current,
        egress_currentness_proof=egress_currentness_proof,
        egress_currentness_result=egress_currentness_result,
        restrictive_latch_state=restrictive_latch_state,
        worst_credible_capacity=worst_credible_capacity,
        egress_request=egress_request,
        quorum_commit_certificate=quorum_commit_certificate,
        authorized_coordinates=authorized_coordinates,
        capsule_egress_request_digest=capsule_egress_request_digest,
        outbound_quantity=construction.derivation.quantity,
        outbound_price=construction.derivation.price,
        outbound_side=outbound_side,
        reference=reference,
    )
