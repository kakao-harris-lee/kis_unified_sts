"""egressgw frozen models — construction inputs / outputs and the send-boundary verify records.

Every model is a **pydantic v2 frozen model** (``frozen=True, extra="forbid"`` via
:class:`~tos.canonical.FrozenModel`): ``extra="forbid"`` is the schema-level "omission is
restrictive", and frozen is the append-only realization — there is **no** update / mutate /
transmit / sign / re-arm method on any model here (the series' constructive-absence canary).

Two groups:

* **Order Construction (design #34 §3)** — :class:`SizingBound`,
  :class:`AdmittedPriceObservation`, :class:`VenueQuantityConstraint`,
  :class:`ProposedConstructionEnvelope`, :class:`EffectDimensionSpec`,
  :class:`QuantityDerivation`, :class:`CandidateConstruction`. The load-bearing shape is that
  **there is no quantity input field anywhere**: the only path from inputs to an order size runs
  through :func:`~tos.egressgw.construction.derive_order_size` over the sizing bound *enclosed in
  the proposed Authorized Construction Envelope* (design #34 §3.1 MINOR-3), so an author cannot
  inject an arbitrary quantity through config. Symmetrically, a market price may enter **only**
  as an admitted Critical Input observation whose ``source`` is the capsule source token — a
  ``config``-sourced price is the RFC-008 §10:327-331 relabelling prohibition and is refused
  (design #34 §3.1 provisional note (1)).

* **Send boundary (design #34 §4)** — :class:`SendBoundaryContext` (every injected verify-list
  fact), :class:`VerifyItemVerdict`, :class:`SendBoundaryVerification`,
  :class:`GatewayEvidenceRecord`. ``SendBoundaryContext`` is deliberately wide: it *is* the
  RFC-002 §10.8:741-759 verify list's input surface, and a missing fact is a stop rather than a
  skip (§10.8:761).

**⚠ provisional.** Several fields carry facts whose owning runtimes have not landed (RCL atomic
claim, independent approval, Action Flow Governor, Safety Authority). They are labelled
provisional at their definition site and close no EV (design #34 §1.1).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #34 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import model_validator

from tos.brokercap import BrokerCapabilityProfile, RequiredCapabilitySet
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
from tos.egressgw.vocabulary import (
    BrokerApplicability,
    DerivationOutcome,
    EffectBasis,
    LotRoundingPolicy,
    SendHaltReason,
    SendVerifyItem,
    VerifyDisposition,
    VerifyOutcome,
)
from tos.engine import InstrumentKey
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
]


# ===========================================================================
# §3.1 — Order Construction inputs
# ===========================================================================


class SizingBound(FrozenModel):
    """The sizing bound **enclosed in** the proposed Authorized Construction Envelope (§3.1).

    Design #34 §3.1 (MINOR-3): the boundedness of the derivation — risk budget, per-unit risk,
    lot policy — is enclosed in the *proposed Authorized Construction Envelope*, because
    RFC-002 §9.1:553 makes Order Construction Policy governance the supplier of construction
    rules. That enclosure is the structural block on the obvious bypass: an author cannot hand
    the constructor a quantity, because no quantity field exists — only the bound the governance
    artifact carries and the rule that consumes it.

    ⚠ **Every value here is P0-1-unapproved and therefore provisional** (design #34 §9): the
    register carries no approved risk-budget / per-unit / lot policy, so a slice run wires
    provisional values and its output is provisional. A ``None`` on any field is a denial at
    :func:`~tos.egressgw.construction.derive_order_size` — never a default.

    ``admitted_quantity_bases`` is the closed set of ``Proposal.quantity_basis`` tokens this
    envelope authorizes. An **empty** set authorizes nothing (∅ fail-closed, both-ways): a
    vacuous "every basis is fine" is not authorization.
    """

    #: The governance-supplied risk budget (``None`` ⇒ denial; must be > 0).
    risk_budget: CanonicalDecimal | None = None
    #: The governance-supplied per-unit risk (``None`` / ``<= 0`` ⇒ denial; never assume-1).
    per_unit_risk: CanonicalDecimal | None = None
    #: The venue/broker lot size the authored policy binds (``None`` / ``<= 0`` ⇒ denial).
    lot_size: CanonicalDecimal | None = None
    #: The **authored, explicit** lot policy (``None`` ⇒ denial — never a silent round, §3.1).
    lot_rounding: LotRoundingPolicy | None = None
    #: Inclusive envelope quantity floor / ceiling (``None`` ⇒ denial; outside ⇒ denial, not
    #: repair — ioc ``compile_command`` "outside authorized envelope — denial").
    min_quantity: CanonicalDecimal | None = None
    max_quantity: CanonicalDecimal | None = None
    #: Optional governance notional ceiling; when declared, exceeding it is a denial.
    max_notional: CanonicalDecimal | None = None
    #: The authorized quantity unit (``None`` ⇒ denial; ADR-002-020 §11:297 unit axis).
    quantity_unit: QuantityUnitKind | None = None
    #: The closed set of authorized ``quantity_basis`` tokens (∅ ⇒ authorizes nothing).
    admitted_quantity_bases: frozenset[str] = frozenset()


class AdmittedPriceObservation(FrozenModel):
    """One admitted Critical Input price observation (design #34 §3.1 (iii)).

    The market-derived value surface is **D-E2's** (design #31 §3.2): a market value flows only
    through an admitted Critical Input observation carried by the Snapshot body, and carrying it
    as an authored constant instead would be the RFC-008 §10:327-331 / RFC-003 §8:236-237
    relabelling prohibition. This model therefore carries the source token explicitly and
    :func:`~tos.egressgw.construction.derive_order_size` admits **only** the capsule source — a
    ``"config"``-sourced price is refused rather than silently consumed.

    ⚠ **provisional**: until D-E2 lands the value surface, a slice run injects the observation
    directly, so the *value* is provisional even though the *source discipline* is enforced.
    """

    #: The context source token; only the capsule source is admissible (D-E1 vocabulary).
    source: str | None = None
    #: The observed price (``None`` ⇒ derivation denial — no last-known default, §3.1 (a)).
    value: CanonicalDecimal | None = None
    #: The snapshot the observation came from (recorded for lineage; ``None`` ⇒ denial).
    snapshot_digest: str | None = None


class VenueQuantityConstraint(FrozenModel):
    """The venue / brokercap quantity constraint the derivation must fall inside (§3.1 (iv)).

    A **separate** coordinate from :class:`SizingBound`: the sizing bound is what governance
    authorizes, this is what the venue and the Broker Capability Profile permit, and the derived
    size must satisfy both. A ``None`` field is a denial — a missing constraint is not "no
    constraint" (the venue ``order_shape_admissible`` ``UNKNOWN`` discipline).
    """

    lot_size: CanonicalDecimal | None = None
    min_quantity: CanonicalDecimal | None = None
    max_quantity: CanonicalDecimal | None = None
    quantity_unit: QuantityUnitKind | None = None


class EffectDimensionSpec(FrozenModel):
    """One Economic Effect Envelope dimension's derivation spec (design #34 §3.2 step 5).

    The dimension id, unit, and scale are **injected policy content** (nothing numeric or
    broker-specific is hardcoded, design #34 §9); the magnitude is derived from the order size
    through :class:`~tos.egressgw.vocabulary.EffectBasis`, never self-reported.
    """

    dimension_id: str | None = None
    basis: EffectBasis | None = None
    unit: str | None = None
    scale: str | None = None


class ProposedConstructionEnvelope(FrozenModel):
    """The proposed Authorized Construction Envelope for step 2 (ADR-002-002 §11.1:583).

    §11.1:583: step 2 constructs a deterministic candidate Canonical Broker Command "from the
    exact proposal under a proposed Authorized Construction Envelope". This model *is* that
    proposed envelope: the non-derived authorized axis values plus the enclosed
    :class:`SizingBound`. Construction is then a pure ``(proposal, envelope)`` function
    (design #34 §3.1 MINOR-3), and ioc ``compile_command``'s declare-and-verify seals the result
    against the very same authorized set.

    ``authorized_axis_bindings`` carries the axes the derivation does **not** produce (account,
    instrument, direction, order type, TIF, …). Declaring a derived axis
    (:data:`DERIVED_AXES`) here is a construction error, not a silent override: the derivation
    owns those three axes and an envelope that also states them would make "which value wins"
    ambiguous, which §10:284 makes denial.
    """

    envelope_generation: int | None = None
    policy_binding_id: str | None = None
    authorized_axis_bindings: tuple[AxisBinding, ...] = ()
    sizing_bound: SizingBound | None = None
    #: The per-dimension Economic Effect Envelope specs (∅ ⇒ nothing derived ⇒ UNKNOWN at the
    #: step-5 adapter — "an empty vector is not no effect", D-E1 ``adapters.py:385-392``).
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


#: The three conformance axes the G5 derivation owns end-to-end (design #34 §3.1). They are
#: produced by :func:`~tos.egressgw.construction.derive_order_size` and declared onto both the
#: intent and the envelope from that single derivation, so no other path can supply them.
DERIVED_AXES: frozenset[ConformanceAxis] = frozenset(
    {ConformanceAxis.QUANTITY, ConformanceAxis.PRICE, ConformanceAxis.UNIT}
)


class QuantityDerivation(FrozenModel):
    """The result of the deterministic, bounded, no-repair G5 derivation (design #34 §3.1).

    ``outcome`` is the truthy-untestable positive gate: only
    :attr:`~tos.egressgw.vocabulary.DerivationOutcome.DERIVED` carries values, and a ``DENIED``
    derivation carries **no** quantity or price at all — there is no partially-repaired shape to
    consume by accident (the shape validator enforces that both ways).

    ``rule`` records the exact authored rule that produced the size, so the evidence names the
    computation rather than asserting it.
    """

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
    """The step-2 candidate construction bundle (design #34 §3.2).

    Carries the derivation, the three ioc artifacts the compile produced (intent / envelope /
    policy / command), the ioc verdicts (``command_conforms`` / ``numerical_safety`` /
    ``no_silent_widening``), and — on denial — the recorded reason. Its ``authority_effect`` is
    the all-false RFC-002 §9.1:553 block: constructing a candidate approves nothing, mutates no
    capacity, transmits nothing, and arms no live scope (design #34 §3.3).
    """

    derivation: QuantityDerivation
    intent: ApprovedIntentContract | None = None
    envelope: AuthorizedConstructionEnvelope | None = None
    policy: OrderConstructionPolicy | None = None
    command: CanonicalBrokerCommand | None = None
    conformance_result: ConformanceResult | None = None
    numerical_result: ConformanceResult | None = None
    #: Positive polarity — ``True`` only when the transformation is an exact bounded result
    #: inside the envelope **and** every dependent gate evaluated it (ioc ``no_silent_widening``).
    no_silent_widening_ok: bool | None = None
    denial_reason: str | None = None
    authority_effect: AllFalseConstructionCoordinatorAuthority = (
        AllFalseConstructionCoordinatorAuthority()
    )


# ===========================================================================
# §4 — send-boundary verify records
# ===========================================================================


class TransportNature(FrozenModel):
    """The **declared** nature of the injected transport (design #34 §4.2).

    Every flag is negative-polarity ``bool | None`` and the non-broker gate requires an explicit
    ``is False`` on each: ``True`` **or** ``None`` (an unestablished nature) is conservatively
    broker-consuming (design #34 §4.2 "미상/unknown transport nature는 보수적으로
    broker-consuming 취급").

    ⚠ **Declaration alone never establishes non-broker applicability.** A self-report is exactly
    the 자기신고 the series refuses, so
    :func:`~tos.egressgw.gateway.resolve_broker_applicability` requires this declaration **and**
    the structural corroboration ADR-002-013 §1 supplies: the transport principal must appear in
    the injected credential-route inventory holding *neither* a usable credential *nor* a broker
    route, and the whole inventory must satisfy egress ``credential_route_authority_disjoint``.
    A synthetic transport does not constitute the Final Egress Trust Boundary, and that absence
    is the structural fact the gate reads (design #34 §1.1-1 / §4.5).
    """

    #: The runtime principal the transport runs as (matched against the inventory; ``None`` ⇒
    #: unresolvable ⇒ conservatively broker-consuming).
    principal: str | None = None
    reaches_broker: bool | None = None
    credential_bearing: bool | None = None
    route_bearing: bool | None = None
    risk_relevant_live: bool | None = None


class VerifyItemVerdict(FrozenModel):
    """One verify item's recorded judgement (design #34 §4.1 / §4.2).

    Records the item, its design-§4.1 disposition, the outcome, and the reason. A
    ``NOT_APPLICABLE`` outcome is admissible **only** for a
    :attr:`~tos.egressgw.vocabulary.VerifyDisposition.DEFERRED_APPLICABILITY` item — the model
    validator makes an N/A on a realized or provisional item unconstructable, so the design's
    §4.2 rule ("explicit N/A only for a positively established synthetic send, and only for the
    deferred mesh") cannot be widened by a call site.
    """

    item: SendVerifyItem
    disposition: VerifyDisposition
    outcome: VerifyOutcome
    reason: str | None = None
    #: The native sibling verdict type name, derived via ``type(artifact).__name__``.
    native_verdict_type: str | None = None
    #: The native verdict's own value (for the result enums), recorded as a plain string.
    native_verdict_value: str | None = None
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


class SendBoundaryVerification(FrozenModel):
    """The whole step-15 verify result (design #34 §4.1).

    ``admitted`` is **positive polarity**: only ``True`` records an admitted verification, and it
    is set only when every one of the 17 items produced an outcome in
    :data:`~tos.egressgw.vocabulary.ADMITTING_VERIFY_OUTCOMES` *and* the item set is exactly the
    normative 17 (an unevaluated item is a stop, never a skip — RFC-002 §10.8:761).
    """

    attempt_id: str
    applicability: BrokerApplicability
    verdicts: tuple[VerifyItemVerdict, ...] = ()
    admitted: bool | None = None
    halt_item: SendVerifyItem | None = None
    halt_reason: SendHaltReason | None = None
    detail: str | None = None
    authority_effect: AllFalseGatewayAuthority = AllFalseGatewayAuthority()


class GatewayEvidenceRecord(FrozenModel):
    """One provisional send-boundary evidence record (design #34 §4.6 / §1.3 step 19).

    ⚠ **Provisional sink, not an Evidence Store.** The full Evidence Store runtime (ADR-002-016)
    is deferred (design #34 §0.2-5) and ``SEND_STARTED`` durability is *not* claimed: this is a
    gateway-local record consumed by an injected
    :class:`~tos.egressgw.gateway.GatewayEvidenceSink`. What the slice *does* establish is the
    **order** — the SEND_STARTED record is written before the transport is called (RFC-005
    §12:360 claim / ``SEND_STARTED`` / first-byte ordering, design #34 §4.6).
    """

    kind: str
    attempt_id: str | None = None
    item: SendVerifyItem | None = None
    outcome: VerifyOutcome | None = None
    applicability: BrokerApplicability | None = None
    halt_reason: SendHaltReason | None = None
    detail: str | None = None
    authority_effect: AllFalseGatewayAuthority = AllFalseGatewayAuthority()


class SendBoundaryContext(FrozenModel):
    """Every injected fact the RFC-002 §10.8:741-759 verify list consumes (design #34 §4.1).

    This model *is* the verify list's input surface, which is why it is wide. A missing fact is a
    **stop**, never a skip: §10.8:761 — "reject the request when any required fact is missing,
    stale, conflicting, or unverifiable" — so every field defaults to ``None`` and every consuming
    check gates positively.

    ⚠ Fields are labelled by the design's §4.1 disposition. The provisional ones stand in for
    runtimes that do not exist (RCL atomic claim / commitment epoch, independent approval, the
    Action Flow Governor) and close no EV (design #34 §1.1 / §4.4).
    """

    # ---- scope + transport (§4.2 broker-applicability, §4.7 environment) --------------
    instrument_key: InstrumentKey | None = None
    transport_nature: TransportNature | None = None
    #: The injected ``environment`` scope token (register §3:88 — the only fixed scope value,
    #: injected here, never hardcoded — design #34 §9).
    non_live_test_environment_token: str | None = None
    scope_environment: str | None = None
    evidence_environment: str | None = None
    #: brokercap ``environment_binding_ok`` cross-environment inheritance flag (negative
    #: polarity; only ``is False`` binds — BC-INV-009).
    environment_inherited: bool | None = None
    credential_route_inventory: tuple[CredentialRouteInventoryEntry, ...] = ()

    # ---- item 1 (Realize): single-use Transmission Capability ------------------------
    #: ⚠ the capability's *issuance* is a provisional RCL stand-in; what is verified here is its
    #: presence plus the structural single-use of its nonce (design #34 §4.1 item 1).
    transmission_capability: TransmissionCapability | None = None
    capability_nonce: str | None = None
    action_flow_permit_nonce: str | None = None
    prior_claims: tuple[ClaimObservation, ...] = ()
    principal: str | None = None
    request_digest: str | None = None

    # ---- item 2 (Realize): intent / reservation identity match ------------------------
    reservation_attempt_id: str | None = None
    reservation_conformance_proof_digest: str | None = None
    reservation_action_flow_permit_identity: str | None = None

    # ---- item 3 (Provisional): commitment epoch ---------------------------------------
    #: ⚠ provisional RCL stand-in — real epoch fencing is deferred (design #34 §4.1 item 3).
    commitment_epoch_current: bool | None = None

    # ---- items 6 / 12 (Provisional): broker + venue generation facts ------------------
    broker_capability_profile: BrokerCapabilityProfile | None = None
    required_capability_set: RequiredCapabilitySet | None = None
    #: brokercap ``capability_admissible`` version currency (§6.1); ``None`` / ``False`` ⇒
    #: PROHIBITED — a stale profile version can never be fallback'd out of.
    broker_profile_version_current: bool | None = None
    #: brokercap ``same_order_retry_allowed`` witness — positively proven deterministic
    #: idempotency for this exact request identity and retry window. ``None`` ⇒ no blind retry.
    idempotency_proven: bool | None = None
    #: ⚠ provisional — the approved Broker Capability Profile INSTANCE is P0-2-blocked, so the
    #: account / instrument / action-class / max-quantity allowance is a stand-in (§4.1 item 6).
    account_instrument_action_allowed: bool | None = None
    max_quantity_within_allowance: bool | None = None
    #: ⚠ provisional — broker-constraint generation currency (§4.1 item 12).
    venue_session_account_facts_current: bool | None = None
    broker_constraint_generation_current: bool | None = None

    # ---- item 11 (Realize): venue snapshot + admissibility decision -------------------
    venue_snapshot: VenueConstraintSnapshot | None = None
    venue_policy: VenueConstraintPolicy | None = None
    venue_decision: OrderAdmissibilityDecision | None = None
    observed_session_phase: str | None = None
    action_class: ActionClass | None = None
    order_shape: OrderShapeFields | None = None
    venue_shape_constraints: VenueShapeConstraints | None = None

    # ---- item 13 (Realize): order construction ---------------------------------------
    construction: CandidateConstruction | None = None
    conformance_proof: OrderConformanceProof | None = None

    # ---- item 14 (Provisional): trading approval --------------------------------------
    #: ⚠ provisional iap stand-in — no independent approver runtime exists (§4.1 item 14).
    approval_consumed_for_this_intent: bool | None = None
    approval_intent_binding_digest: str | None = None

    # ---- item 15 (Provisional): action flow -------------------------------------------
    #: ⚠ provisional afg stand-in — no Action Flow Governor runtime exists (§4.1 item 15).
    action_flow_permit_identity: str | None = None
    action_flow_commitment_current: bool | None = None

    # ---- item 16 (Realize): currentness ------------------------------------------------
    egress_currentness_proof: EgressCurrentnessProof | None = None
    egress_currentness_result: ProofResult | None = None
    restrictive_latch_state: RestrictiveLatchState | None = None
    #: The worst-credible capacity obligation cur ``unknown_preserves_capacity`` preserves when
    #: currentness is not positively known — recorded, never released (CUR-INV-011:183).
    worst_credible_capacity: int | None = None

    # ---- item 17 (Realize): actual-outbound coordinate equivalence ---------------------
    egress_request: EgressRequestRecord | None = None
    quorum_commit_certificate: QuorumCommitCertificate | None = None
    authorized_coordinates: EgressCoordinateSet | None = None
    capsule_egress_request_digest: str | None = None

    # ---- step 18 outbound payload ------------------------------------------------------
    outbound_quantity: CanonicalDecimal | None = None
    outbound_price: CanonicalDecimal | None = None
    outbound_side: str | None = None
    reference: OrderingEvent = OrderingEvent()


def positive_decimal(value: Decimal | None) -> bool:
    """Whether ``value`` is a present, finite, strictly positive magnitude (fail-closed).

    Args:
        value: The magnitude (``None`` / non-finite / ``<= 0`` ⇒ ``False``).

    Returns:
        ``True`` iff the magnitude is usable as a derivation input.
    """
    if value is None:
        return False
    if not value.is_finite():
        return False
    return value > 0
