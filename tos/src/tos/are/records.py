"""are value models + injected inputs + the four digest-bound artifacts (design #13 §2)."""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from tos.are._base import (
    AllFalseAggregateAuthority,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.are.vocabulary import (
    AdverseScenarioKind,
    BenefitKind,
    RiskDecisionResult,
    RiskDimensionKind,
    RiskScopeKind,
)
from tos.canonical import CanonicalDecimal
from tos.rcl import CapacityVector

__all__ = [
    "AggregateRiskAuthorityEffect",
    "RiskDimensionDescriptor",
    "ProjectedCell",
    "BenefitProof",
    "CancellationRiskInputs",
    "ValuationInputs",
    "AdverseIncrementResult",
    "AggregateRiskPolicy",
    "AggregateRiskStateSnapshot",
    "AdverseScenarioSet",
    "AggregateRiskDecision",
]


class AggregateRiskAuthorityEffect(AllFalseAggregateAuthority):
    """Authority effect of a GRANT / decision / snapshot — every flag false (ARE-INV-009)."""

    creates_capacity: bool = False
    permits_transmission: bool = False
    issues_live_authorization: bool = False
    grants_broker_permission: bool = False
    may_rearm: bool = False


class RiskDimensionDescriptor(FrozenModel):
    """One governed dimension's explicit vector semantics (ADR-002-021 §10 line 270-281)."""

    dimension: RiskDimensionKind | None = None
    scope: RiskScopeKind | None = None
    unit: str | None = None
    sign_convention: str | None = None
    limit_source: str | None = None
    valuation_rule: str | None = None
    aggregation_rule: str | None = None
    uncertainty_treatment: str | None = None
    correlation_treatment: str | None = None
    scenario_semantics: str | None = None
    freshness_requirement: str | None = None
    conversion_coefficient: CanonicalDecimal | None = None


class ProjectedCell(FrozenModel):
    """One per-(scope, dimension, scenario) projection record (ADR-002-021 §12 line 311-328)."""

    scope: RiskScopeKind | None = None
    dimension: RiskDimensionKind | None = None
    scenario: AdverseScenarioKind | None = None
    conservative_current_usage: CanonicalDecimal | None = None
    max_credible_command_effect: CanonicalDecimal | None = None
    required_concurrent_overlap_effect: CanonicalDecimal | None = None
    conservative_current_usage_already_committed: CanonicalDecimal | None = None
    effective_limit: CanonicalDecimal | None = None
    current_conservative_risk: CanonicalDecimal | None = None
    final_conservative_risk: CanonicalDecimal | None = None
    no_action_risk: CanonicalDecimal | None = None
    worst_intermediate_risk: CanonicalDecimal | None = None
    credible_space_bounded: bool | None = None
    no_credible_intermediate_increases_exceedance: bool | None = None
    already_exceeded_regime: bool | None = None

    def projected_usage(self) -> Decimal | None:
        """Return ``ConservativeCurrentUsage + MaxCredibleCommandEffect + OverlapEffect`` (§12)."""
        parts = (
            self.conservative_current_usage,
            self.max_credible_command_effect,
            self.required_concurrent_overlap_effect,
        )
        total = Decimal(0)
        for part in parts:
            if part is None:
                return None
            total = total + part
        return total

    def requested_increment(self) -> Decimal | None:
        """Return ``ProjectedUsage - ConservativeCurrentUsageAlreadyCommitted`` (§12 line 321)."""
        projected = self.projected_usage()
        committed = self.conservative_current_usage_already_committed
        if projected is None or committed is None:
            return None
        return projected - committed

    def headroom(self) -> Decimal | None:
        """Return ``EffectiveLimit - ConservativeCurrentUsageAlreadyCommitted`` (§5.6)."""
        limit = self.effective_limit
        committed = self.conservative_current_usage_already_committed
        if limit is None or committed is None:
            return None
        return limit - committed


class BenefitProof(FrozenModel):
    """A netting / hedge / diversification / correlation benefit proof (ADR-002-021 §13)."""

    kind: BenefitKind | None = None
    exact_identity_and_eligibility: bool = False
    current_enforceable_state_and_fqp: bool = False
    simultaneous_availability: bool = False
    approved_basis_correlation_liquidity_stress: bool = False
    margin_recognition: bool = False
    no_undeclared_common_mode: bool = False
    complete_adverse_leg_failure_scenario: bool = False
    proof_reference: str | None = None


class CancellationRiskInputs(FrozenModel):
    """Injected magnitudes for the protective cancellation-arbiter flags (design #13 §3.4)."""

    continued_existence_risk: CanonicalDecimal | None = None
    post_cancellation_risk: CanonicalDecimal | None = None
    baseline_no_action_risk: CanonicalDecimal | None = None


class ValuationInputs(FrozenModel):
    """Injected valuation classification inputs (ADR-002-021 §14 line 350-354)."""

    price_classes_distinguished: bool | None = None
    stale_or_unknown_flagged: bool | None = None
    no_zero_negative_future_crossed_as_conservative: bool | None = None
    broker_figure_treated_as_ceiling_only: bool | None = None
    local_or_broker_more_restrictive_dominates: bool | None = None


class AdverseIncrementResult(FrozenModel):
    """The result of :func:`~tos.are.predicates.adverse_increment` (design #13 §5.3)."""

    result: RiskDecisionResult = RiskDecisionResult.UNKNOWN
    increment: CapacityVector = CapacityVector()
    final_conservative_risk: CanonicalDecimal | None = None
    current_conservative_risk: CanonicalDecimal | None = None
    no_action_risk: CanonicalDecimal | None = None
    worst_intermediate_risk: CanonicalDecimal | None = None
    credible_space_bounded: bool | None = None
    no_credible_intermediate_increases_exceedance: bool | None = None
    already_exceeded_regime: bool | None = None


class AggregateRiskPolicy(IndependentIdArtifact):
    """An append-only, generation-immutable Aggregate Risk Policy (ADR-002-021 §5.1 / §8)."""

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_generation",
        "policy_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "policy_version",
            "governed_dimensions",
            "governed_scopes",
            "signer_identity",
            "approval_identity",
            "evidence_package_ref",
        }
    )

    policy_id: str | None = None

    policy_generation: int | None = None
    policy_version: str | None = None
    governed_dimensions: tuple[RiskDimensionKind, ...] = ()
    governed_scopes: tuple[RiskScopeKind, ...] = ()
    signer_identity: str | None = None
    approval_identity: str | None = None
    evidence_package_ref: str | None = None

    policy_order: int | None = None


class AggregateRiskStateSnapshot(IndependentIdArtifact):
    """An append-only Aggregate Risk State Snapshot (ADR-002-021 §5.3 / §9)."""

    _ID_FIELD: ClassVar[str] = "snapshot_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "snapshot_generation",
        "consistency_cut_identity",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "snapshot_generation",
            "consistency_cut_identity",
            "covered_scopes",
            "conservative_current_usage",
            "lineage_ref",
            "authority_effect",
        }
    )

    snapshot_id: str | None = None

    snapshot_generation: int | None = None
    consistency_cut_identity: str | None = None
    covered_scopes: tuple[RiskScopeKind, ...] = ()
    conservative_current_usage: CapacityVector = CapacityVector()
    lineage_ref: str | None = None
    authority_effect: AggregateRiskAuthorityEffect = AggregateRiskAuthorityEffect()

    snapshot_order: int | None = None

    def covers(self, scope: RiskScopeKind) -> bool:
        """Whether ``scope`` is among the snapshot's covered scopes (pure lookup)."""
        return scope in self.covered_scopes


class AdverseScenarioSet(IndependentIdArtifact):
    """An append-only, policy-bound Adverse Scenario Set (ADR-002-021 §5.4 / §11)."""

    _ID_FIELD: ClassVar[str] = "scenario_set_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("scenario_set_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "scenario_set_generation",
            "policy_binding_id",
            "covered_scenario_kinds",
            "evidence_package_ref",
        }
    )

    scenario_set_id: str | None = None

    scenario_set_generation: int | None = None
    policy_binding_id: str | None = None
    covered_scenario_kinds: tuple[AdverseScenarioKind, ...] = ()
    evidence_package_ref: str | None = None

    scenario_set_order: int | None = None

    def covered_kinds(self) -> frozenset[AdverseScenarioKind]:
        """The set of adverse-scenario kinds this set covers (pure)."""
        return frozenset(self.covered_scenario_kinds)


class AggregateRiskDecision(IndependentIdArtifact):
    """An append-only, forward-only Aggregate Risk Decision (ADR-002-021 §5.5 / §15 / §16)."""

    _ID_FIELD: ClassVar[str] = "decision_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "decision_generation",
        "result",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "decision_generation",
            "result",
            "policy_digest",
            "snapshot_digest",
            "scenario_set_digest",
            "effect_digest",
            "applicable_risk_scopes",
            "grant_identity",
            "adverse_increment",
            "effective_limit",
            "authority_effect",
        }
    )

    decision_id: str | None = None

    decision_generation: int | None = None
    result: RiskDecisionResult | None = None
    policy_digest: str | None = None
    snapshot_digest: str | None = None
    scenario_set_digest: str | None = None
    effect_digest: str | None = None
    applicable_risk_scopes: tuple[str, ...] = ()
    grant_identity: str | None = None
    adverse_increment: CapacityVector = CapacityVector()
    effective_limit: CapacityVector = CapacityVector()
    authority_effect: AggregateRiskAuthorityEffect = AggregateRiskAuthorityEffect()

    decision_order: int | None = None
