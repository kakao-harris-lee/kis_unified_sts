"""Shared valid-artifact builders + strategies for the are property tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #13 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 REJECT lesson):

* a "clean" projection cell declares concrete, finite, within-headroom magnitudes so a GRANT
  fixture is genuinely admissible, never a permissive shortcut;
* an **over-headroom** cell carries a real requested increment strictly greater than headroom;
* an **UNKNOWN** cell drops one magnitude to ``None`` (a genuine missing input);
* a **full** benefit proof has all seven premises positively ``True``; a partial one flips one;
* a **conservative** valuation input tuple has every flag ``True``;
* a min-coverage scenario set genuinely covers the injected floor.

The reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.are import (
    AdverseScenarioKind,
    AdverseScenarioSet,
    AggregateRiskDecision,
    AggregateRiskPolicy,
    AggregateRiskStateSnapshot,
    BenefitKind,
    BenefitProof,
    CancellationRiskInputs,
    ProjectedCell,
    RiskDecisionResult,
    RiskDimensionDescriptor,
    RiskDimensionKind,
    RiskScopeKind,
    ValuationInputs,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.rcl import CapacityComponent, CapacityVector

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")
#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False``).
TRIBOOL = st.sampled_from([True, False, None])
#: A finite decimal magnitude (never NaN / infinity — those are unconstructable, §14).
FINITE_MAGNITUDE = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

#: The injected min-coverage floor used across the projection tests (two credible kinds).
COVERAGE_FLOOR: frozenset[AdverseScenarioKind] = frozenset(
    {
        AdverseScenarioKind.FILL_PREFIX_ORDERING,
        AdverseScenarioKind.OVERLAP_RETRY,
    }
)


# ---------------------------------------------------------------------------
# Digest-bound artifact builders
# ---------------------------------------------------------------------------


def issue_policy(**overrides: Any) -> AggregateRiskPolicy:
    """Issue a valid :class:`AggregateRiskPolicy` (all required covered fields concrete)."""
    base: dict[str, Any] = {
        "policy_id": "pol-1",
        "policy_generation": 1,
        "policy_version": "v1",
        "governed_dimensions": (RiskDimensionKind.GROSS_NOTIONAL,),
        "governed_scopes": (RiskScopeKind.ACCOUNT,),
    }
    base.update(overrides)
    return AggregateRiskPolicy.issue(scheme=SCHEME, **base)


def issue_snapshot(**overrides: Any) -> AggregateRiskStateSnapshot:
    """Issue a valid :class:`AggregateRiskStateSnapshot` covering the ACCOUNT scope."""
    base: dict[str, Any] = {
        "snapshot_id": "snap-1",
        "snapshot_generation": 1,
        "consistency_cut_identity": "cut-1",
        "covered_scopes": (RiskScopeKind.ACCOUNT,),
    }
    base.update(overrides)
    return AggregateRiskStateSnapshot.issue(scheme=SCHEME, **base)


def issue_scenario_set(**overrides: Any) -> AdverseScenarioSet:
    """Issue a scenario set covering the full :data:`COVERAGE_FLOOR` (clean fixture)."""
    base: dict[str, Any] = {
        "scenario_set_id": "ss-1",
        "scenario_set_generation": 1,
        "policy_binding_id": "pol-1",
        "covered_scenario_kinds": tuple(sorted(COVERAGE_FLOOR)),
    }
    base.update(overrides)
    return AdverseScenarioSet.issue(scheme=SCHEME, **base)


def issue_decision(**overrides: Any) -> AggregateRiskDecision:
    """Issue a valid :class:`AggregateRiskDecision` (concrete id + generation + result)."""
    base: dict[str, Any] = {
        "decision_id": "dec-1",
        "decision_generation": 1,
        "result": RiskDecisionResult.GRANT,
    }
    base.update(overrides)
    return AggregateRiskDecision.issue(scheme=SCHEME, **base)


# ---------------------------------------------------------------------------
# Value-model builders
# ---------------------------------------------------------------------------


def clean_cell(
    scenario: AdverseScenarioKind = AdverseScenarioKind.FILL_PREFIX_ORDERING,
    **overrides: Any,
) -> ProjectedCell:
    """A within-headroom, fully-finite projection cell (projected 17 <= limit 100)."""
    base: dict[str, Any] = {
        "scope": RiskScopeKind.ACCOUNT,
        "dimension": RiskDimensionKind.GROSS_NOTIONAL,
        "scenario": scenario,
        "conservative_current_usage": Decimal("10"),
        "max_credible_command_effect": Decimal("5"),
        "required_concurrent_overlap_effect": Decimal("2"),
        "conservative_current_usage_already_committed": Decimal("8"),
        "effective_limit": Decimal("100"),
        "current_conservative_risk": Decimal("15"),
        "final_conservative_risk": Decimal("10"),
        "no_action_risk": Decimal("12"),
        "worst_intermediate_risk": Decimal("9"),
        "credible_space_bounded": True,
        "no_credible_intermediate_increases_exceedance": True,
        "already_exceeded_regime": False,
    }
    base.update(overrides)
    return ProjectedCell(**base)


def floor_cells(**overrides: Any) -> tuple[ProjectedCell, ...]:
    """One clean cell per :data:`COVERAGE_FLOOR` kind (a determinate, within-headroom set)."""
    return tuple(
        clean_cell(scenario=kind, **overrides) for kind in sorted(COVERAGE_FLOOR)
    )


def over_headroom_cell(**overrides: Any) -> ProjectedCell:
    """A cell whose requested increment (projected 200 - committed 8 = 192) exceeds headroom (92)."""
    base: dict[str, Any] = {
        "conservative_current_usage": Decimal("100"),
        "max_credible_command_effect": Decimal("100"),
        "required_concurrent_overlap_effect": Decimal("0"),
    }
    base.update(overrides)
    return clean_cell(**base)


def full_benefit_proof(**overrides: Any) -> BenefitProof:
    """A benefit proof with all seven §13 premises positively True (admissible)."""
    base: dict[str, Any] = {
        "kind": BenefitKind.NETTING,
        "exact_identity_and_eligibility": True,
        "current_enforceable_state_and_fqp": True,
        "simultaneous_availability": True,
        "approved_basis_correlation_liquidity_stress": True,
        "margin_recognition": True,
        "no_undeclared_common_mode": True,
        "complete_adverse_leg_failure_scenario": True,
    }
    base.update(overrides)
    return BenefitProof(**base)


def conservative_valuation(**overrides: Any) -> ValuationInputs:
    """Valuation inputs with every classification flag positively True (conservative)."""
    base: dict[str, Any] = {
        "price_classes_distinguished": True,
        "stale_or_unknown_flagged": True,
        "no_zero_negative_future_crossed_as_conservative": True,
        "broker_figure_treated_as_ceiling_only": True,
        "local_or_broker_more_restrictive_dominates": True,
    }
    base.update(overrides)
    return ValuationInputs(**base)


def complete_descriptor(**overrides: Any) -> RiskDimensionDescriptor:
    """A dimension descriptor with concrete unit / sign / scope / limit / conversion."""
    base: dict[str, Any] = {
        "dimension": RiskDimensionKind.GROSS_NOTIONAL,
        "scope": RiskScopeKind.ACCOUNT,
        "unit": "krw",
        "sign_convention": "signed",
        "limit_source": "hard_safety_envelope",
        "conversion_coefficient": Decimal("1"),
    }
    base.update(overrides)
    return RiskDimensionDescriptor(**base)


def cancellation_inputs(**overrides: Any) -> CancellationRiskInputs:
    """Cancellation-risk magnitudes (defaults: continued 20 > baseline 10 > post 5)."""
    base: dict[str, Any] = {
        "continued_existence_risk": Decimal("20"),
        "post_cancellation_risk": Decimal("5"),
        "baseline_no_action_risk": Decimal("10"),
    }
    base.update(overrides)
    return CancellationRiskInputs(**base)


def capacity_vector(
    dimension: str = "qty", magnitude: Decimal | None = Decimal("5")
) -> CapacityVector:
    """A one-dimension rcl :class:`~tos.rcl.CapacityVector` (for envelope / increment checks)."""
    return CapacityVector(
        components=(CapacityComponent(dimension_id=dimension, magnitude=magnitude),)
    )
