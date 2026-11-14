"""Order Construction (design #34 §3) — the G5 quantity / price derivation + the ioc wrapping."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from tos.canonical import CanonicalizationScheme
from tos.dsl import FLAT_QUANTITY_BASIS, ContextValue, ContextValueView
from tos.egressgw._base import ArtifactIntegrityError
from tos.egressgw.records import (
    AdmittedPriceObservation,
    CandidateConstruction,
    EffectDimensionSpec,
    ProposedConstructionEnvelope,
    QuantityDerivation,
    SizingBound,
    VenueQuantityConstraint,
    positive_decimal,
)
from tos.egressgw.vocabulary import (
    DerivationOutcome,
    EffectBasis,
    LotRoundingPolicy,
)
from tos.engine import (
    CAPSULE_CONTEXT_SOURCE,
    CommitmentStep,
    StageAuthorityClass,
    StageOutcome,
    StageRequest,
    StageVerdict,
    conformance_proof_verdict,
    economic_effect_envelope_verdict,
    venue_admissibility_verdict,
)
from tos.ioc import (
    ApprovedIntentContract,
    AuthorizedConstructionEnvelope,
    AxisBinding,
    ConformanceAxis,
    ConformanceResult,
    EconomicEffectEnvelope,
    OrderConformanceProof,
    OrderConstructionPolicy,
    command_conforms,
    compile_command,
    mutation_fence_holds,
    no_silent_widening,
    numerical_safety,
)
from tos.rcl import CapacityComponent
from tos.venue import (
    ActionClass,
    OrderAdmissibilityDecision,
    OrderAdmissibilityResult,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
    order_shape_admissible,
    session_phase_admits,
)

__all__ = [
    "ConformanceProofStage",
    "EconomicEffectStage",
    "OrderConstructionStage",
    "VenueConstraintStage",
    "admitted_price_from_view",
    "admitted_shape_price_from_view",
    "build_order_conformance_proof",
    "candidate_command_verdict",
    "construct_candidate_command",
    "derive_economic_effect_envelope",
    "derive_order_size",
    "fold_venue_admissibility",
]


DERIVATION_RULE = "risk_budget / per_unit_risk under the authored lot policy"

_FLAT_DERIVATION_RULE = "observed held position under the authored lot policy"

DERIVATION_CONTEXT: Context = Context(prec=28, rounding=ROUND_HALF_EVEN)

_DECIDED_RESULTS: frozenset[ConformanceResult] = frozenset(
    {ConformanceResult.CONFORMANT, ConformanceResult.NON_CONFORMANT}
)


def _denied(reason: str) -> QuantityDerivation:
    """A denied derivation carrying no partially-repaired value (design #34 §3.1)."""
    return QuantityDerivation(outcome=DerivationOutcome.DENIED, denial_reason=reason)


def _exact_admitted_int_value(
    view: ContextValueView, *, field_key: str
) -> tuple[int | None, ContextValue | None]:
    """The single #32 §2.5 exact-integer admission predicate both projections share."""
    if not view.values:
        return (None, None)
    matched = [value for value in view.values if value.field_key == field_key]
    if len(matched) != 1:
        return (None, None)
    admitted = matched[0]
    magnitude = admitted.value
    if type(magnitude) is not int:
        return (None, None)
    return (magnitude, admitted)


def admitted_price_from_view(
    view: ContextValueView, *, field_key: str
) -> AdmittedPriceObservation:
    """Project one admitted Critical Input value onto a price observation (design #35 §4.2)."""
    if not view.values:
        return AdmittedPriceObservation()
    lineage = AdmittedPriceObservation(
        source=CAPSULE_CONTEXT_SOURCE,
        snapshot_digest=view.snapshot_canonical_digest,
    )
    magnitude, admitted = _exact_admitted_int_value(view, field_key=field_key)
    if magnitude is None or admitted is None:
        return lineage
    return AdmittedPriceObservation(
        source=CAPSULE_CONTEXT_SOURCE,
        value=Decimal(magnitude),
        snapshot_digest=view.snapshot_canonical_digest,
        value_payload_digest=admitted.payload_digest,
    )


def admitted_shape_price_from_view(
    view: ContextValueView, *, field_key: str
) -> int | None:
    """Project one admitted Critical Input value onto an integer venue-shape price (design #36 §4)."""
    magnitude, _admitted = _exact_admitted_int_value(view, field_key=field_key)
    return magnitude


def derive_order_size(
    *,
    quantity_basis: str | None,
    envelope: ProposedConstructionEnvelope | None,
    price: AdmittedPriceObservation | None,
    venue_constraint: VenueQuantityConstraint | None,
    held_position: Decimal | None = None,
) -> QuantityDerivation:
    """Derive the order size deterministically, bounded, with no repair (design #34 §3.1)."""
    if envelope is None:
        return _denied(
            "no proposed Authorized Construction Envelope — an absent envelope permits no "
            "construction (ADR-002-020 §5.3:125)"
        )
    bound: SizingBound | None = envelope.sizing_bound
    if bound is None:
        return _denied(
            "the proposed envelope encloses no sizing bound — the derivation's boundedness is "
            "governance-supplied and cannot be sourced elsewhere (design #34 §3.1)"
        )
    if quantity_basis is None or not quantity_basis.strip():
        return _denied("the proposal declares no quantity_basis — nothing to render")
    if not bound.admitted_quantity_bases:
        return _denied(
            "the sizing bound admits no quantity basis — an empty admitted set authorizes "
            "nothing (∅ fail-closed, design #34 §7)"
        )
    if quantity_basis not in bound.admitted_quantity_bases:
        return _denied(
            f"quantity_basis {quantity_basis!r} is not in the envelope's admitted set — a "
            "basis outside the authorized closed set is a silent widening (ADR-002-020 §5.3)"
        )
    if price is None:
        return _denied(
            "no admitted Critical Input price observation — an unknown price is a no-send, "
            "never a last-known default (RFC-005 §7:211; design #34 §3.1 (a))"
        )
    if price.source != CAPSULE_CONTEXT_SOURCE:
        return _denied(
            f"price source {price.source!r} is not the admitted Critical Input source "
            f"{CAPSULE_CONTEXT_SOURCE!r} — a market-derived value carried as an authored "
            "constant is the RFC-008 §10:327-331 relabelling prohibition"
        )
    if not (price.snapshot_digest or "").strip():
        return _denied("the price observation carries no snapshot lineage")
    if not positive_decimal(price.value):
        return _denied("the price observation carries no positive finite value")
    is_flat = quantity_basis == FLAT_QUANTITY_BASIS
    if is_flat:
        if held_position is None:
            return _denied(
                f"quantity_basis {FLAT_QUANTITY_BASIS!r} closes a position but no held position "
                "was observed — an unknown held position is a no-send, never an assumed size "
                "(design #35 §5.2)"
            )
        if not positive_decimal(held_position):
            return _denied(
                f"the observed held position is {held_position} — there is nothing to close, and "
                f"a zero-size {FLAT_QUANTITY_BASIS!r} order is not a smaller exit, it is no order "
                "(∅ both ways: an explicit zero is not an absent observation)"
            )
    else:
        if not positive_decimal(bound.risk_budget):
            return _denied("the sizing bound declares no positive risk budget")
        if not positive_decimal(bound.per_unit_risk):
            return _denied(
                "the sizing bound declares no positive per-unit risk — a missing per-unit risk "
                "is never assumed to be one"
            )
    if not positive_decimal(bound.lot_size):
        return _denied("the sizing bound declares no positive lot size")
    if bound.lot_rounding is None:
        return _denied(
            "the sizing bound states no lot policy — an unstated rounding policy is a denial, "
            "never a silent round (RFC-005 §7:211; design #34 §3.1)"
        )
    if bound.quantity_unit is None:
        return _denied("the sizing bound declares no quantity unit")
    if bound.min_quantity is None or bound.max_quantity is None:
        return _denied("the sizing bound declares no quantity floor / ceiling")
    if venue_constraint is None:
        return _denied(
            "no venue / broker quantity constraint — a missing constraint is not 'no "
            "constraint' (venue order_shape_admissible UNKNOWN discipline)"
        )
    if (
        not positive_decimal(venue_constraint.lot_size)
        or venue_constraint.min_quantity is None
        or venue_constraint.max_quantity is None
        or venue_constraint.quantity_unit is None
    ):
        return _denied("the venue / broker quantity constraint is incomplete")
    if venue_constraint.quantity_unit is not bound.quantity_unit:
        return _denied(
            f"quantity unit disagreement: envelope {bound.quantity_unit.value} vs venue "
            f"{venue_constraint.quantity_unit.value} — a unit mismatch is prohibited "
            "(ADR-002-020 §11:301)"
        )

    assert bound.lot_size is not None
    lot: Decimal = bound.lot_size
    assert price.value is not None
    assert venue_constraint.lot_size is not None
    venue_lot: Decimal = venue_constraint.lot_size
    with localcontext(DERIVATION_CONTEXT):
        if is_flat:
            assert held_position is not None
            raw: Decimal = held_position
        else:
            assert bound.risk_budget is not None
            assert bound.per_unit_risk is not None
            raw = bound.risk_budget / bound.per_unit_risk
        if not raw.is_finite():
            return _denied("the derived raw size is not finite")
        if bound.lot_rounding is LotRoundingPolicy.EXACT_MULTIPLE_REQUIRED:
            if raw % lot != 0:
                return _denied(
                    f"derived size {raw} is not an exact multiple of lot {lot} and the authored "
                    "policy is EXACT_MULTIPLE_REQUIRED — adjusting it would be a repair "
                    "(RFC-005 §7:211)"
                )
            quantity = raw
        else:
            quantity = (raw // lot) * lot

        if not positive_decimal(quantity):
            return _denied(
                f"the authored lot policy yields a non-positive size ({quantity}) — a zero-size "
                "order is not a smaller order, it is no order"
            )
        if quantity < bound.min_quantity or quantity > bound.max_quantity:
            return _denied(
                f"derived size {quantity} is outside the authorized envelope "
                f"[{bound.min_quantity}, {bound.max_quantity}] — denial, never a clamp "
                "(ADR-002-020 §9 'outside the authorized envelope — denial')"
            )
        if (
            quantity < venue_constraint.min_quantity
            or quantity > venue_constraint.max_quantity
            or quantity % venue_lot != 0
        ):
            return _denied(
                f"derived size {quantity} violates the venue / broker quantity constraint — "
                "denial, never a permissive adjustment (ADR-002-019 §12:309)"
            )
        notional = quantity * price.value
        if bound.max_notional is not None and notional > bound.max_notional:
            return _denied(
                f"derived notional {notional} exceeds the authorized ceiling "
                f"{bound.max_notional} — denial, never a reduction"
            )
        return QuantityDerivation(
            outcome=DerivationOutcome.DERIVED,
            quantity=quantity,
            price=price.value,
            quantity_unit=bound.quantity_unit,
            rule=_FLAT_DERIVATION_RULE if is_flat else DERIVATION_RULE,
        )


def _derived_axis_bindings(derivation: QuantityDerivation) -> tuple[AxisBinding, ...]:
    """The three derivation-owned axis bindings, rendered from the single derivation."""
    assert derivation.quantity is not None
    assert derivation.price is not None
    assert derivation.quantity_unit is not None
    return (
        AxisBinding(axis=ConformanceAxis.QUANTITY, value=str(derivation.quantity)),
        AxisBinding(axis=ConformanceAxis.PRICE, value=str(derivation.price)),
        AxisBinding(axis=ConformanceAxis.UNIT, value=derivation.quantity_unit.value),
    )


def construct_candidate_command(
    *,
    proposal_id: str | None,
    proposal_digest: str | None,
    derivation: QuantityDerivation,
    envelope: ProposedConstructionEnvelope,
    scheme: CanonicalizationScheme,
    intent_id: str,
    intent_version: str,
    envelope_id: str,
    policy_id: str,
    policy_version: str,
    policy_generation: int,
    command_id: str,
    generation: int,
    signer_identity: str | None = None,
    approval_identity: str | None = None,
    evidence_package_ref: str | None = None,
) -> CandidateConstruction:
    """Compile the candidate command from a derived size and seal it with ioc (design #34 §3.2)."""
    if derivation.outcome is not DerivationOutcome.DERIVED:
        return CandidateConstruction(
            derivation=derivation,
            denial_reason=derivation.denial_reason
            or "the quantity derivation was denied",
        )
    bindings = tuple(envelope.authorized_axis_bindings) + _derived_axis_bindings(
        derivation
    )
    intent: ApprovedIntentContract | None = None
    ioc_envelope: AuthorizedConstructionEnvelope | None = None
    policy: OrderConstructionPolicy | None = None
    try:
        issued_intent = ApprovedIntentContract.issue(
            scheme=scheme,
            intent_id=intent_id,
            intent_generation=generation,
            intent_version=intent_version,
            proposal_id=proposal_id,
            proposal_digest=proposal_digest,
            authorized_axis_bindings=bindings,
        )
        assert isinstance(issued_intent, ApprovedIntentContract)
        intent = issued_intent
        issued_envelope = AuthorizedConstructionEnvelope.issue(
            scheme=scheme,
            envelope_id=envelope_id,
            envelope_generation=envelope.envelope_generation,
            authorized_axis_bindings=bindings,
            policy_binding_id=envelope.policy_binding_id,
        )
        assert isinstance(issued_envelope, AuthorizedConstructionEnvelope)
        ioc_envelope = issued_envelope
        issued_policy = OrderConstructionPolicy.issue(
            scheme=scheme,
            policy_id=policy_id,
            policy_generation=policy_generation,
            policy_version=policy_version,
            signer_identity=signer_identity,
            approval_identity=approval_identity,
            evidence_package_ref=evidence_package_ref,
        )
        assert isinstance(issued_policy, OrderConstructionPolicy)
        policy = issued_policy
        command = compile_command(
            intent=intent,
            policy=policy,
            envelope=ioc_envelope,
            generation=generation,
            scheme=scheme,
            command_id=command_id,
        )
    except ArtifactIntegrityError as exc:
        return CandidateConstruction(
            derivation=derivation,
            intent=intent,
            envelope=ioc_envelope,
            policy=policy,
            denial_reason=(
                f"ioc construction denied the candidate: {exc} — denial is total, there is "
                "no best-effort recompile (ADR-002-020 §9:270)"
            ),
        )
    conformance = command_conforms(intent, command, policy, ioc_envelope)
    numerical = numerical_safety(
        [derivation.quantity, derivation.price],
        units_consistent=derivation.quantity_unit is not None,
    )
    widening_ok = no_silent_widening(
        exact_bounded_within_envelope=derivation.outcome is DerivationOutcome.DERIVED,
        every_dependent_gate_evaluated=(
            conformance in _DECIDED_RESULTS and numerical in _DECIDED_RESULTS
        ),
    )
    return CandidateConstruction(
        derivation=derivation,
        intent=intent,
        envelope=ioc_envelope,
        policy=policy,
        command=command,
        conformance_result=conformance,
        numerical_result=numerical,
        no_silent_widening_ok=widening_ok,
    )


def candidate_command_verdict(
    construction: CandidateConstruction | None,
    *,
    step: CommitmentStep = CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION,
) -> StageVerdict:
    """Wrap a candidate construction as a positive-admit step-2 verdict (design #34 §3.2)."""
    if construction is None:
        return StageVerdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            reason="no candidate construction was produced",
        )
    if construction.command is None or construction.conformance_result is None:
        return StageVerdict(
            step=step,
            outcome=StageOutcome.DENY,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            native_verdict_type=type(construction).__name__,
            reason=construction.denial_reason
            or "the candidate command was not constructed",
        )
    if (
        construction.conformance_result is ConformanceResult.CONFORMANT
        and construction.numerical_result is ConformanceResult.CONFORMANT
        and construction.no_silent_widening_ok is True
    ):
        outcome = StageOutcome.ADMIT
        reason = None
    elif (
        construction.conformance_result is ConformanceResult.UNKNOWN
        or construction.numerical_result is ConformanceResult.UNKNOWN
    ):
        outcome = StageOutcome.UNKNOWN
        reason = "candidate conformance or numerical safety is UNKNOWN — denial"
    else:
        outcome = StageOutcome.DENY
        reason = "the candidate command is NON_CONFORMANT or silently widened"
    return StageVerdict(
        step=step,
        outcome=outcome,
        authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
        native_verdict_type=type(construction.conformance_result).__name__,
        native_verdict_value=str(construction.conformance_result.value),
        bound_digest=construction.command.canonical_digest,
        bound_identity=construction.command.command_id,
        reason=reason,
    )


def derive_economic_effect_envelope(
    derivation: QuantityDerivation,
    specs: tuple[EffectDimensionSpec, ...] = (),
) -> EconomicEffectEnvelope:
    """Derive the conservative Economic Effect Envelope from the order size (step 5)."""
    components: list[CapacityComponent] = []
    quantity = derivation.quantity
    price = derivation.price
    derived = derivation.outcome is DerivationOutcome.DERIVED
    with localcontext(DERIVATION_CONTEXT):
        for spec in specs:
            if spec.dimension_id is None:
                continue
            magnitude: Decimal | None = None
            if derived and quantity is not None:
                if spec.basis is EffectBasis.QUANTITY:
                    magnitude = quantity
                elif spec.basis is EffectBasis.NOTIONAL and price is not None:
                    magnitude = quantity * price
            components.append(
                CapacityComponent(
                    dimension_id=spec.dimension_id,
                    magnitude=magnitude,
                    unit=spec.unit,
                    scale=spec.scale,
                )
            )
        return EconomicEffectEnvelope(components=tuple(components))


def build_order_conformance_proof(
    *,
    construction: CandidateConstruction,
    scheme: CanonicalizationScheme,
    proof_id: str,
    proof_generation: int,
    effect_digest: str | None = None,
    venue_admissibility_decision_digest: str | None = None,
    broker_capability_profile_digest: str | None = None,
    required_authority_scope: tuple[str, ...] = (),
) -> OrderConformanceProof | None:
    """Issue the step-11 Order Conformance Proof binding the exact command (design #34 §3.2)."""
    if construction.command is None or construction.envelope is None:
        return None
    proof = OrderConformanceProof.issue(
        scheme=scheme,
        proof_id=proof_id,
        proof_generation=proof_generation,
        policy_digest=(
            None
            if construction.policy is None
            else construction.policy.canonical_digest
        ),
        envelope_digest=construction.envelope.canonical_digest,
        command_digest=construction.command.canonical_digest,
        effect_digest=effect_digest,
        venue_admissibility_decision_digest=venue_admissibility_decision_digest,
        broker_capability_profile_digest=broker_capability_profile_digest,
        required_authority_scope=required_authority_scope,
        conformance_result=construction.conformance_result,
    )
    assert isinstance(proof, OrderConformanceProof)
    return proof


def fold_venue_admissibility(
    *,
    observed_session_phase: str | None,
    action_class: ActionClass | None,
    snapshot: VenueConstraintSnapshot | None,
    policy: VenueConstraintPolicy | None,
    shape: OrderShapeFields | None,
    constraints: VenueShapeConstraints | None,
) -> OrderAdmissibilityResult:
    """Fold venue's two shipped predicates into one non-authorizing result (design #34 §3.2)."""
    if action_class is None:
        return OrderAdmissibilityResult.UNKNOWN
    phase = session_phase_admits(observed_session_phase, action_class, snapshot, policy)
    shape_result = order_shape_admissible(shape, constraints)
    results = (phase, shape_result)
    for result in results:
        if result is OrderAdmissibilityResult.INADMISSIBLE:
            return OrderAdmissibilityResult.INADMISSIBLE
    for result in results:
        if result is OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY:
            return OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY
    for result in results:
        if result is not OrderAdmissibilityResult.ADMISSIBLE:
            return OrderAdmissibilityResult.UNKNOWN
    return OrderAdmissibilityResult.ADMISSIBLE


class OrderConstructionStage:
    """The step-2 ``Stage``: derive, compile, and seal the candidate command (design #34 §3.2)."""

    def __init__(
        self,
        *,
        envelope: ProposedConstructionEnvelope,
        price: AdmittedPriceObservation | None,
        venue_constraint: VenueQuantityConstraint | None,
        scheme: CanonicalizationScheme,
        intent_id: str,
        intent_version: str,
        envelope_id: str,
        policy_id: str,
        policy_version: str,
        policy_generation: int,
        command_id: str,
        generation: int,
        price_field_key: str | None = None,
    ) -> None:
        """Configure the stage with its injected construction inputs."""
        self._envelope = envelope
        self._price = price
        self._price_field_key = price_field_key
        self._venue_constraint = venue_constraint
        self._scheme = scheme
        self._intent_id = intent_id
        self._intent_version = intent_version
        self._envelope_id = envelope_id
        self._policy_id = policy_id
        self._policy_version = policy_version
        self._policy_generation = policy_generation
        self._command_id = command_id
        self._generation = generation
        self.construction: CandidateConstruction | None = None

    @property
    def effect_specs(self) -> tuple[EffectDimensionSpec, ...]:
        """The injected Economic Effect Envelope specs the proposed envelope encloses."""
        return self._envelope.effect_dimensions

    def _price_for(self, request: StageRequest) -> AdmittedPriceObservation | None:
        """The price this construction sizes against (design #35 §4.2 (3))."""
        view = request.value_view
        if self._price_field_key is None or view is None:
            return self._price
        return admitted_price_from_view(view, field_key=self._price_field_key)

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Run the derivation + compile and return the positive-admit step-2 verdict."""
        proposal = request.proposal
        derivation = derive_order_size(
            quantity_basis=getattr(proposal, "quantity_basis", None),
            envelope=self._envelope,
            price=self._price_for(request),
            venue_constraint=self._venue_constraint,
            held_position=request.held_position_magnitude,
        )
        self.construction = construct_candidate_command(
            proposal_id=getattr(proposal, "proposal_id", None),
            proposal_digest=getattr(proposal, "canonical_digest", None),
            derivation=derivation,
            envelope=self._envelope,
            scheme=self._scheme,
            intent_id=self._intent_id,
            intent_version=self._intent_version,
            envelope_id=self._envelope_id,
            policy_id=self._policy_id,
            policy_version=self._policy_version,
            policy_generation=self._policy_generation,
            command_id=self._command_id,
            generation=self._generation,
        )
        return candidate_command_verdict(self.construction, step=request.step)


class VenueConstraintStage:
    """The step-3 ``Stage``: a **non-authorizing thin adapter** over venue (design #34 §3.2)."""

    def __init__(
        self,
        *,
        observed_session_phase: str | None,
        action_class: ActionClass | None,
        snapshot: VenueConstraintSnapshot | None,
        policy: VenueConstraintPolicy | None,
        shape: OrderShapeFields | None,
        constraints: VenueShapeConstraints | None,
        decision: OrderAdmissibilityDecision | None = None,
        shape_price_field_key: str | None = None,
    ) -> None:
        """Configure the stage with its injected venue facts."""
        self._observed_session_phase = observed_session_phase
        self._action_class = action_class
        self._snapshot = snapshot
        self._policy = policy
        self._shape = shape
        self._constraints = constraints
        self._decision = decision
        self._shape_price_field_key = shape_price_field_key
        self.resolved_shape: OrderShapeFields | None = None

    @property
    def shape_constraints(self) -> VenueShapeConstraints | None:
        """The injected constraints, exposed so the item-11 context reads the same object the"""
        return self._constraints

    def _shape_for(self, request: StageRequest) -> OrderShapeFields | None:
        """The shape this step folds and the item-11 context reuses (design #36 §3.3)."""
        view = request.value_view
        if self._shape_price_field_key is None or view is None:
            return self._shape
        if self._shape is None:
            return None
        projected = admitted_shape_price_from_view(
            view, field_key=self._shape_price_field_key
        )
        return self._shape.model_copy(update={"price": projected})

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Produce the non-authorizing venue verdict for step 3."""
        resolved_shape = self._shape_for(request)
        self.resolved_shape = resolved_shape
        result = fold_venue_admissibility(
            observed_session_phase=self._observed_session_phase,
            action_class=self._action_class,
            snapshot=self._snapshot,
            policy=self._policy,
            shape=resolved_shape,
            constraints=self._constraints,
        )
        return venue_admissibility_verdict(result, self._decision, step=request.step)


class EconomicEffectStage:
    """The step-5 ``Stage``: derive the conservative Economic Effect Envelope (design #34 §3.2)."""

    def __init__(self, *, construction_stage: OrderConstructionStage) -> None:
        """Configure the stage to read the step-2 stage's completed construction."""
        self._construction_stage = construction_stage
        self.envelope: EconomicEffectEnvelope | None = None

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Derive the envelope from the step-2 derivation and wrap it."""
        self.envelope = None
        construction = self._construction_stage.construction
        if construction is None:
            return StageVerdict(
                step=request.step,
                outcome=StageOutcome.UNKNOWN,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason="step 2 produced no construction — nothing to derive an effect from",
            )
        self.envelope = derive_economic_effect_envelope(
            construction.derivation,
            self._construction_stage.effect_specs,
        )
        return economic_effect_envelope_verdict(self.envelope, step=request.step)


class ConformanceProofStage:
    """The step-11 ``Stage``: issue the Order Conformance Proof and fence it (design #34 §3.2)."""

    def __init__(
        self,
        *,
        construction_stage: OrderConstructionStage,
        scheme: CanonicalizationScheme,
        proof_id: str,
        proof_generation: int,
        required_authority_scope: tuple[str, ...],
        effect_digest: str | None = None,
        venue_admissibility_decision_digest: str | None = None,
        broker_capability_profile_digest: str | None = None,
    ) -> None:
        """Configure the stage with its injected proof identities and seam digests."""
        self._construction_stage = construction_stage
        self._effect_digest = effect_digest
        self._scheme = scheme
        self._proof_id = proof_id
        self._proof_generation = proof_generation
        self._required_authority_scope = required_authority_scope
        self._venue_digest = venue_admissibility_decision_digest
        self._profile_digest = broker_capability_profile_digest
        self.proof: OrderConformanceProof | None = None

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Issue the proof, apply the mutation fence, and wrap the ioc result."""
        construction = self._construction_stage.construction
        if construction is None or construction.command is None:
            return StageVerdict(
                step=request.step,
                outcome=StageOutcome.UNKNOWN,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason="no candidate command exists — there is no proof of an unbuilt command",
            )
        self.proof = build_order_conformance_proof(
            construction=construction,
            scheme=self._scheme,
            proof_id=self._proof_id,
            proof_generation=self._proof_generation,
            effect_digest=self._effect_digest,
            venue_admissibility_decision_digest=self._venue_digest,
            broker_capability_profile_digest=self._profile_digest,
            required_authority_scope=self._required_authority_scope,
        )
        if not mutation_fence_holds(construction.command, self.proof):
            return StageVerdict(
                step=request.step,
                outcome=StageOutcome.DENY,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                native_verdict_type=type(self.proof).__name__ if self.proof else None,
                reason=(
                    "the conformance proof does not fence the exact command digest — a "
                    "post-proof mutation is a new command identity and a new proof "
                    "(ADR-002-020 §6.2 / §16:429)"
                ),
            )
        return conformance_proof_verdict(
            construction.conformance_result, self.proof, step=request.step
        )
