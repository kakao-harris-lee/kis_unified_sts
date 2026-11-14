"""are decision-integrity predicates + the produced-seam producers (design #13 §5/§6)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from tos.are.records import (
    AdverseIncrementResult,
    AdverseScenarioSet,
    AggregateRiskAuthorityEffect,
    AggregateRiskDecision,
    AggregateRiskPolicy,
    AggregateRiskStateSnapshot,
    BenefitProof,
    CancellationRiskInputs,
    ProjectedCell,
    RiskDimensionDescriptor,
    ValuationInputs,
)
from tos.are.vocabulary import (
    AdverseScenarioKind,
    RiskDecisionResult,
    RiskDimensionKind,
    RiskScopeKind,
)
from tos.canonical import CanonicalizationScheme
from tos.rcl import CapacityComponent, CapacityVector

__all__ = [
    "snapshot_scope_complete",
    "exact_effect_snapshot_binding",
    "adverse_increment",
    "dimension_vector_integrity",
    "valuation_conservative",
    "numerical_safety",
    "risk_decision",
    "envelope_bound_not_enlarged",
    "benefit_admissible",
    "numerical_determinism",
    "protective_creates_nothing",
    "grants_no_authority",
    "final_conservative_risk",
    "current_conservative_risk",
    "no_action_risk",
    "worst_intermediate_risk",
    "credible_space_bounded",
    "no_credible_intermediate_increases_exceedance",
    "already_exceeded_regime",
    "continued_existence_worsens_aggregate",
    "cancellation_worsens_aggregate",
    "decision_content_ref",
    "grant_identity_of",
    "applicable_risk_scopes_of",
    "aggregate_effect_within",
]


def _max_or_none(values: Sequence[Decimal | None]) -> Decimal | None:
    """Return the maximum (dominance) of ``values``; ``None`` if empty or any is ``None``."""
    result: Decimal | None = None
    seen = False
    for value in values:
        if value is None:
            return None
        seen = True
        result = value if result is None else max(result, value)
    return result if seen else None


def _all_true_or_none(flags: Sequence[bool | None]) -> bool | None:
    """Conjunction with fail-closed ``None``: ``True`` only if every flag is ``True``."""
    if not flags:
        return None
    saw_none = False
    for flag in flags:
        if flag is False:
            return False
        if flag is None:
            saw_none = True
    return None if saw_none else True


def _any_true_or_none(flags: Sequence[bool | None]) -> bool | None:
    """Disjunction with fail-closed ``None``: ``True`` if any flag is ``True``."""
    if not flags:
        return None
    saw_none = False
    for flag in flags:
        if flag is True:
            return True
        if flag is None:
            saw_none = True
    return None if saw_none else False


def final_conservative_risk(cells: Sequence[ProjectedCell]) -> Decimal | None:
    """The worst-case conservative final-state risk across cells (protective seam, §5.3)."""
    return _max_or_none([cell.final_conservative_risk for cell in cells])


def current_conservative_risk(cells: Sequence[ProjectedCell]) -> Decimal | None:
    """The worst-case conservative current-state risk across cells (protective seam, §5.3)."""
    return _max_or_none([cell.current_conservative_risk for cell in cells])


def no_action_risk(cells: Sequence[ProjectedCell]) -> Decimal | None:
    """The worst-case no-action risk across cells (protective seam, §5.3)."""
    return _max_or_none([cell.no_action_risk for cell in cells])


def worst_intermediate_risk(cells: Sequence[ProjectedCell]) -> Decimal | None:
    """The worst credible intermediate-state risk across cells (§6.2 protective seam)."""
    return _max_or_none([cell.worst_intermediate_risk for cell in cells])


def credible_space_bounded(cells: Sequence[ProjectedCell]) -> bool | None:
    """Whether every cell's credible state space is bounded (§6.2 / §19 line 470)."""
    return _all_true_or_none([cell.credible_space_bounded for cell in cells])


def no_credible_intermediate_increases_exceedance(
    cells: Sequence[ProjectedCell],
) -> bool | None:
    """Whether no credible intermediate increases hard-limit exceedance (§6.2 protective seam)."""
    return _all_true_or_none(
        [cell.no_credible_intermediate_increases_exceedance for cell in cells]
    )


def already_exceeded_regime(cells: Sequence[ProjectedCell]) -> bool | None:
    """Whether any cell reports the already-exceeded regime (protective seam, §5.3)."""
    return _any_true_or_none([cell.already_exceeded_regime for cell in cells])


def snapshot_scope_complete(
    snapshot: AggregateRiskStateSnapshot | None,
    required_scopes: frozenset[RiskScopeKind],
    *,
    all_fields_attributed: bool | None,
) -> bool:
    """Whether the snapshot covers every applicable scope with full attribution (§5.1 / §9)."""
    if snapshot is None:
        return False
    if not required_scopes:
        return False
    if all_fields_attributed is not True:
        return False
    covered = frozenset(snapshot.covered_scopes)
    return required_scopes <= covered


def exact_effect_snapshot_binding(
    *,
    snapshot_digest: str | None,
    scenario_set_digest: str | None,
    effect_digest: str | None,
    expected_snapshot_digest: str | None,
    expected_scenario_set_digest: str | None,
    expected_effect_digest: str | None,
) -> bool:
    """Whether one exact snapshot / scenario-set / effect digest set is bound (§5.2 / §16)."""
    presented = (snapshot_digest, scenario_set_digest, effect_digest)
    expected = (
        expected_snapshot_digest,
        expected_scenario_set_digest,
        expected_effect_digest,
    )
    if any(value is None for value in presented + expected):
        return False
    return presented == expected


def _scenario_coverage_sufficient(
    scenario_set: AdverseScenarioSet | None,
    required_scenario_kinds: frozenset[AdverseScenarioKind],
) -> bool:
    """Whether the scenario set meets the injected min-coverage floor (§11 / §4.7)."""
    if scenario_set is None:
        return False
    if not required_scenario_kinds:
        return False
    return required_scenario_kinds <= scenario_set.covered_kinds()


def adverse_increment(
    cells: Sequence[ProjectedCell],
    scenario_set: AdverseScenarioSet | None,
    *,
    required_scenario_kinds: frozenset[AdverseScenarioKind],
) -> AdverseIncrementResult:
    """Project the conservative adverse increment over all credible scenarios (§5.3 / §12)."""
    coverage_ok = _scenario_coverage_sufficient(scenario_set, required_scenario_kinds)

    _Key = tuple[RiskScopeKind | None, RiskDimensionKind | None]
    order: list[_Key] = []
    grouped: dict[_Key, list[Decimal | None]] = {}
    determinate = coverage_ok and bool(cells)
    for cell in cells:
        key = (cell.scope, cell.dimension)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        increment = cell.requested_increment()
        grouped[key].append(increment)
        if increment is None or cell.headroom() is None:
            determinate = False

    components: list[CapacityComponent] = []
    all_within_headroom = determinate
    for key in order:
        scope, dimension = key
        magnitude = _max_or_none(grouped[key])
        scope_token = scope.value if scope is not None else "<unknown-scope>"
        dim_token = dimension.value if dimension is not None else "<unknown-dimension>"
        components.append(
            CapacityComponent(
                dimension_id=f"{scope_token}::{dim_token}", magnitude=magnitude
            )
        )
        if magnitude is None:
            determinate = False

    if determinate:
        for cell in cells:
            increment = cell.requested_increment()
            headroom = cell.headroom()
            if increment is None or headroom is None:
                all_within_headroom = False
                determinate = False
                break
            if increment > headroom:
                all_within_headroom = False

    if not determinate:
        result = RiskDecisionResult.UNKNOWN
    elif all_within_headroom:
        result = RiskDecisionResult.GRANT
    else:
        result = RiskDecisionResult.DENY

    return AdverseIncrementResult(
        result=result,
        increment=CapacityVector(components=tuple(components)),
        final_conservative_risk=final_conservative_risk(cells),
        current_conservative_risk=current_conservative_risk(cells),
        no_action_risk=no_action_risk(cells),
        worst_intermediate_risk=worst_intermediate_risk(cells),
        credible_space_bounded=credible_space_bounded(cells),
        no_credible_intermediate_increases_exceedance=(
            no_credible_intermediate_increases_exceedance(cells)
        ),
        already_exceeded_regime=already_exceeded_regime(cells),
    )


def dimension_vector_integrity(
    descriptors: Sequence[RiskDimensionDescriptor],
    cells: Sequence[ProjectedCell],
    *,
    higher_scope_limits_known: bool | None,
) -> bool:
    """Whether every governed dimension has explicit, complete vector semantics (§5.4 / §10)."""
    if not descriptors:
        return False
    if higher_scope_limits_known is not True:
        return False
    described = set()
    for descriptor in descriptors:
        if (
            descriptor.dimension is None
            or descriptor.scope is None
            or descriptor.unit is None
            or descriptor.sign_convention is None
            or descriptor.limit_source is None
            or descriptor.conversion_coefficient is None
        ):
            return False
        described.add(descriptor.dimension)
    for cell in cells:
        if cell.dimension is None or cell.dimension not in described:
            return False
    return True


def valuation_conservative(inputs: ValuationInputs) -> bool:
    """Whether valuation is conservative on every axis (§5.5 / §14 line 350-354)."""
    return (
        inputs.price_classes_distinguished is True
        and inputs.stale_or_unknown_flagged is True
        and inputs.no_zero_negative_future_crossed_as_conservative is True
        and inputs.broker_figure_treated_as_ceiling_only is True
        and inputs.local_or_broker_more_restrictive_dominates is True
    )


def numerical_safety(
    magnitudes: Sequence[Decimal | None],
    *,
    units_consistent: bool | None,
) -> RiskDecisionResult | bool:
    """Whether the magnitudes are numerically safe (§5.5 / §14 line 356-366; ARE-INV-008)."""
    if units_consistent is not True:
        return RiskDecisionResult.UNKNOWN
    if not magnitudes:
        return RiskDecisionResult.UNKNOWN
    for magnitude in magnitudes:
        if magnitude is None or not magnitude.is_finite():
            return RiskDecisionResult.UNKNOWN
    return True


def envelope_bound_not_enlarged(
    *,
    decision_effective_limit: CapacityVector,
    injected_envelope_max: CapacityVector | None,
    limit_source_is_injected_envelope: bool | None,
) -> bool:
    """Whether the decision's effective limit does not enlarge the Hard Safety Envelope (§5.6)."""
    if injected_envelope_max is None:
        return False
    if limit_source_is_injected_envelope is not True:
        return False
    for component in decision_effective_limit.components:
        dimension = component.dimension_id
        effective = component.magnitude
        if dimension is None or effective is None:
            return False
        envelope_max = injected_envelope_max.magnitude(dimension)
        if envelope_max is None:
            return False
        if effective > envelope_max:
            return False
    return True


def _decide_result(
    *,
    projection: AdverseIncrementResult,
    snapshot: AggregateRiskStateSnapshot | None,
    applicable_risk_scopes: tuple[str, ...],
    snapshot_complete: bool,
    numerically_safe: RiskDecisionResult | bool | None,
    valuation_ok: bool | None,
    envelope_not_enlarged: bool,
) -> RiskDecisionResult:
    """The pure GRANT/DENY/UNKNOWN verdict (§5.6 / ARE-INV-006); restrictive-by-default."""
    if projection.result is RiskDecisionResult.UNKNOWN:
        return RiskDecisionResult.UNKNOWN
    if snapshot is None or not snapshot_complete:
        return RiskDecisionResult.UNKNOWN
    if numerically_safe is not True or not valuation_ok:
        return RiskDecisionResult.UNKNOWN
    if not applicable_risk_scopes:
        return RiskDecisionResult.DENY
    if not envelope_not_enlarged:
        return RiskDecisionResult.DENY
    if projection.result is RiskDecisionResult.DENY:
        return RiskDecisionResult.DENY
    return RiskDecisionResult.GRANT


def risk_decision(
    *,
    projection: AdverseIncrementResult,
    snapshot: AggregateRiskStateSnapshot | None,
    applicable_risk_scopes: tuple[str, ...],
    snapshot_complete: bool,
    numerically_safe: RiskDecisionResult | bool | None,
    valuation_ok: bool | None,
    envelope_not_enlarged: bool,
    decision_id: str,
    decision_generation: int,
    scheme: CanonicalizationScheme,
    policy: AggregateRiskPolicy | None = None,
    scenario_set: AdverseScenarioSet | None = None,
    effective_limit: CapacityVector | None = None,
    grant_identity: str | None = None,
    effect_digest: str | None = None,
) -> AggregateRiskDecision:
    """Decide GRANT / DENY / UNKNOWN and issue the forward-only decision (§5.6 / §15 / §16)."""
    result = _decide_result(
        projection=projection,
        snapshot=snapshot,
        applicable_risk_scopes=applicable_risk_scopes,
        snapshot_complete=snapshot_complete,
        numerically_safe=numerically_safe,
        valuation_ok=valuation_ok,
        envelope_not_enlarged=envelope_not_enlarged,
    )
    decision = AggregateRiskDecision.issue(
        scheme=scheme,
        decision_id=decision_id,
        decision_generation=decision_generation,
        result=result,
        policy_digest=policy.canonical_digest if policy is not None else None,
        snapshot_digest=snapshot.canonical_digest if snapshot is not None else None,
        scenario_set_digest=(
            scenario_set.canonical_digest if scenario_set is not None else None
        ),
        effect_digest=effect_digest,
        applicable_risk_scopes=applicable_risk_scopes,
        grant_identity=grant_identity,
        adverse_increment=projection.increment,
        effective_limit=(
            effective_limit if effective_limit is not None else CapacityVector()
        ),
    )
    assert isinstance(decision, AggregateRiskDecision)
    return decision


def benefit_admissible(proof: BenefitProof) -> bool:
    """Whether a claimed benefit is admissible on all seven §13 premises (§6.1 / ARE-INV-005)."""
    return (
        proof.exact_identity_and_eligibility is True
        and proof.current_enforceable_state_and_fqp is True
        and proof.simultaneous_availability is True
        and proof.approved_basis_correlation_liquidity_stress is True
        and proof.margin_recognition is True
        and proof.no_undeclared_common_mode is True
        and proof.complete_adverse_leg_failure_scenario is True
    )


def numerical_determinism(
    *,
    canonical_representation: bool | None,
    deterministic_ordering: bool | None,
    parser_library_model_agreement: bool | None,
    convergence_established: bool | None,
) -> bool:
    """Whether numeric evaluation is deterministic beyond the L1 finite check (§6.2 / §14)."""
    return (
        canonical_representation is True
        and deterministic_ordering is True
        and parser_library_model_agreement is True
        and convergence_established is True
    )


def protective_creates_nothing(
    *,
    label_creates_capacity: bool | None,
    label_creates_feasibility: bool | None,
    label_creates_allocation: bool | None,
    label_creates_transmission: bool | None,
) -> bool:
    """Whether an exit / reduce-only / emergency label creates nothing (§6.5 / ARE-INV-012)."""
    return (
        label_creates_capacity is False
        and label_creates_feasibility is False
        and label_creates_allocation is False
        and label_creates_transmission is False
    )


def grants_no_authority(effect: AggregateRiskAuthorityEffect) -> bool:
    """Whether the authority effect grants nothing (§6.7 / ARE-INV-009 / §7 line 217)."""
    return not (
        effect.creates_capacity
        or effect.permits_transmission
        or effect.issues_live_authorization
        or effect.grants_broker_permission
        or effect.may_rearm
    )


def continued_existence_worsens_aggregate(
    inputs: CancellationRiskInputs,
) -> bool | None:
    """Whether continued order existence worsens conservative aggregate risk (§3.4)."""
    risk = inputs.continued_existence_risk
    baseline = inputs.baseline_no_action_risk
    if risk is None or baseline is None:
        return None
    return risk > baseline


def cancellation_worsens_aggregate(inputs: CancellationRiskInputs) -> bool | None:
    """Whether cancelling the order worsens conservative aggregate risk (§3.4)."""
    risk = inputs.post_cancellation_risk
    baseline = inputs.baseline_no_action_risk
    if risk is None or baseline is None:
        return None
    return risk > baseline


def decision_content_ref(
    decision: AggregateRiskDecision,
) -> tuple[str | None, int | None, str | None]:
    """The forward-only ``(decision_id, decision_generation, canonical_decision_digest)`` (§3.4)."""
    return (
        decision.decision_id,
        decision.decision_generation,
        decision.canonical_digest,
    )


def grant_identity_of(decision: AggregateRiskDecision) -> str | None:
    """The aggregate-risk authority grant identity (rcl ``records.py:99`` seam, §3.4)."""
    return decision.grant_identity


def applicable_risk_scopes_of(decision: AggregateRiskDecision) -> tuple[str, ...]:
    """The applicable risk scopes the decision authorizes (rcl ``records.py:98`` seam, §3.4)."""
    return decision.applicable_risk_scopes


def aggregate_effect_within(
    *,
    decision_effective_limit: CapacityVector,
    injected_envelope_max: CapacityVector | None,
    limit_source_is_injected_envelope: bool | None,
) -> bool:
    """The spg semantic-validation step-7 ``aggregate_effect_within`` bool (§3.4 / §8)."""
    return envelope_bound_not_enlarged(
        decision_effective_limit=decision_effective_limit,
        injected_envelope_max=injected_envelope_max,
        limit_source_is_injected_envelope=limit_source_is_injected_envelope,
    )
