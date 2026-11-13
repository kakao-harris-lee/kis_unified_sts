"""posttrade value models + injected inputs + the four digest-bound artifacts (§2)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from tos.canonical import CanonicalDecimal
from tos.posttrade._base import (
    AllFalsePostTradeConsequence,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.posttrade.vocabulary import (
    EventObligationLegKind,
    FinalityDimensionKind,
    ObligationLegDirection,
    PostTradeObligationLifecycleState,
)

__all__ = [
    "AllFalsePostTradeConsequence",
    "EconomicObligationRecord",
    "ObligationLeg",
    "ObligationLegScope",
    "PostTradeFinalityProof",
]


class ObligationLegScope(FrozenModel):
    """The exact scope tuple a finality proof binds (ADR §11 line 328; design #24 §2.1 M8)."""

    leg: ObligationLegDirection | None = None
    account: str | None = None
    currency: str | None = None
    value_date: str | None = None
    source_revision: str | None = None
    finality_class: FinalityDimensionKind | None = None


class ObligationLeg(FrozenModel):
    """One exact economic leg of an obligation (ADR §5.3 line 116 / §9 line 273)."""

    direction: ObligationLegDirection | None = None
    magnitude: CanonicalDecimal | None = None
    scope: ObligationLegScope | None = None
    leg_kind: EventObligationLegKind | None = None


class EconomicObligationRecord(IndependentIdArtifact):
    """An append-only, versioned Economic Obligation Record (ADR §9 line 266-275; §10)."""

    _ID_FIELD: ClassVar[str] = "obligation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "obligation_type",
        "obligation_generation",
        "idempotency_key",
        "lifecycle_state",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "obligation_type",
            "obligation_version",
            "obligation_generation",
            "source_event_ids",
            "source_event_digests",
            "account_scope",
            "subaccount_scope",
            "legal_entity_scope",
            "beneficial_owner_scope",
            "broker_scope",
            "clearing_member_scope",
            "custodian_scope",
            "bank_scope",
            "venue_scope",
            "settlement_location_scope",
            "instrument_identity",
            "asset_identity",
            "currency",
            "quantity",
            "amount",
            "unit_spec",
            "sign_convention",
            "multiplier",
            "price_basis",
            "fx_basis",
            "rounding_rule",
            "tolerance",
            "trade_date",
            "record_date",
            "ex_date",
            "due_date",
            "value_date",
            "settlement_date",
            "recall_date",
            "delivery_date",
            "payable_date",
            "observation_date",
            "legs",
            "leg_magnitudes",
            "source_continuity_id",
            "statement_bindings",
            "correction_bindings",
            "per_field_confidence",
            "conservative_bound",
            "lifecycle_state",
            "finality_proof_refs",
            "break_refs",
            "supersedes_ref",
            "invalidation_refs",
            "capacity_bindings",
            "evidence_bindings",
            "idempotency_key",
            "order_state",
            "knowledge_state",
            "capacity_state",
            "authority_state",
            "evidence_confidence_state",
        }
    )

    obligation_id: str | None = None

    obligation_type: str | None = None
    obligation_version: str | None = None
    obligation_generation: int | None = None
    source_event_ids: tuple[str, ...] = ()
    source_event_digests: tuple[str, ...] = ()
    account_scope: str | None = None
    subaccount_scope: str | None = None
    legal_entity_scope: str | None = None
    beneficial_owner_scope: str | None = None
    broker_scope: str | None = None
    clearing_member_scope: str | None = None
    custodian_scope: str | None = None
    bank_scope: str | None = None
    venue_scope: str | None = None
    settlement_location_scope: str | None = None
    instrument_identity: str | None = None
    asset_identity: str | None = None
    currency: str | None = None
    quantity: CanonicalDecimal | None = None
    amount: CanonicalDecimal | None = None
    unit_spec: str | None = None
    sign_convention: str | None = None
    multiplier: CanonicalDecimal | None = None
    price_basis: str | None = None
    fx_basis: str | None = None
    rounding_rule: str | None = None
    tolerance: CanonicalDecimal | None = None
    trade_date: str | None = None
    record_date: str | None = None
    ex_date: str | None = None
    due_date: str | None = None
    value_date: str | None = None
    settlement_date: str | None = None
    recall_date: str | None = None
    delivery_date: str | None = None
    payable_date: str | None = None
    observation_date: str | None = None
    legs: tuple[ObligationLeg, ...] = ()
    leg_magnitudes: Mapping[ObligationLegDirection, CanonicalDecimal | None] = {}
    source_continuity_id: str | None = None
    statement_bindings: tuple[str, ...] = ()
    correction_bindings: tuple[str, ...] = ()
    per_field_confidence: Mapping[str, str] = {}
    conservative_bound: str | None = None
    lifecycle_state: PostTradeObligationLifecycleState | None = None
    finality_proof_refs: tuple[str, ...] = ()
    break_refs: tuple[str, ...] = ()
    supersedes_ref: str | None = None
    invalidation_refs: tuple[str, ...] = ()
    capacity_bindings: tuple[str, ...] = ()
    evidence_bindings: tuple[str, ...] = ()

    idempotency_key: str | None = None

    order_state: str | None = None
    knowledge_state: str | None = None
    capacity_state: str | None = None
    authority_state: str | None = None
    evidence_confidence_state: str | None = None

    consequence: AllFalsePostTradeConsequence = AllFalsePostTradeConsequence()

    obligation_order: int | None = None

    def leg_direction_set(self) -> frozenset[ObligationLegDirection]:
        """Return the declared leg directions as a set for the ``required <= present`` algebra."""
        return frozenset(
            leg.direction for leg in self.legs if leg.direction is not None
        )


class PostTradeFinalityProof(IndependentIdArtifact):
    """A field-specific post-trade finality proof (ADR §11 line 318-330)."""

    _ID_FIELD: ClassVar[str] = "proof_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "bound_generation",
        "idempotency_key",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "obligation_ref",
            "obligation_version",
            "leg_scope",
            "amount",
            "finality_class",
            "bound_generation",
            "does_not_prove",
            "proof_recipe_id",
            "source_revision",
            "idempotency_key",
            "supersedes_ref",
        }
    )

    proof_id: str | None = None

    obligation_ref: str | None = None
    obligation_version: str | None = None
    leg_scope: ObligationLegScope | None = None
    amount: CanonicalDecimal | None = None
    finality_class: FinalityDimensionKind | None = None
    bound_generation: int | None = None
    does_not_prove: tuple[str, ...] = ()
    proof_recipe_id: str | None = None
    source_revision: str | None = None
    idempotency_key: str | None = None
    supersedes_ref: str | None = None

    consequence: AllFalsePostTradeConsequence = AllFalsePostTradeConsequence()

    proof_order: int | None = None
