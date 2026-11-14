"""Conservative projection + adverse-increment dominance (design #13 §5.3; ARE-EV-003 substrate)."""

from __future__ import annotations

from decimal import Decimal

from tos.are import (
    AdverseScenarioKind,
    RiskDecisionResult,
    RiskDimensionKind,
    RiskScopeKind,
    adverse_increment,
)
from tos.rcl import CapacityVector

from ._are_strategies import (
    COVERAGE_FLOOR,
    clean_cell,
    floor_cells,
    issue_scenario_set,
    over_headroom_cell,
)


def test_determinate_within_headroom_projection_grants() -> None:
    """(canary +) A complete, finite, within-headroom projection over the floor => GRANT."""
    result = adverse_increment(
        floor_cells(), issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    assert result.result is RiskDecisionResult.GRANT
    assert result.increment.components
    assert result.increment.magnitude("ACCOUNT::GROSS_NOTIONAL") == Decimal("9")


def test_over_headroom_projection_denies() -> None:
    """(canary -) A cell whose requested increment exceeds headroom => DENY (pass fails, §12)."""
    cells = (
        over_headroom_cell(scenario=AdverseScenarioKind.FILL_PREFIX_ORDERING),
        clean_cell(scenario=AdverseScenarioKind.OVERLAP_RETRY),
    )
    result = adverse_increment(
        cells, issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    assert result.result is RiskDecisionResult.DENY


def test_result_is_the_rcl_capacity_vector_type() -> None:
    """(MAJOR-1 type-seal) The final AdverseIncrement[s,d] is the rcl CapacityVector type."""
    result = adverse_increment(
        floor_cells(), issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    assert isinstance(result.increment, CapacityVector)


def test_empty_scenario_set_is_unknown_not_vacuous() -> None:
    """(∅-seal §4.7) A None scenario set => UNKNOWN — 'no adverse path' is not proof."""
    result = adverse_increment(
        floor_cells(), None, required_scenario_kinds=COVERAGE_FLOOR
    )
    assert result.result is RiskDecisionResult.UNKNOWN


def test_empty_coverage_floor_is_unknown() -> None:
    """(∅-seal §4.7) An empty injected min-coverage floor cannot prove coverage => UNKNOWN."""
    result = adverse_increment(
        floor_cells(), issue_scenario_set(), required_scenario_kinds=frozenset()
    )
    assert result.result is RiskDecisionResult.UNKNOWN


def test_under_covering_scenario_set_is_unknown() -> None:
    """(min-coverage floor §11 line 301) A set missing a required kind => UNKNOWN."""
    partial_set = issue_scenario_set(
        scenario_set_id="ss-partial",
        covered_scenario_kinds=(AdverseScenarioKind.FILL_PREFIX_ORDERING,),
    )
    result = adverse_increment(
        floor_cells(), partial_set, required_scenario_kinds=COVERAGE_FLOOR
    )
    assert result.result is RiskDecisionResult.UNKNOWN


def test_empty_cells_is_unknown() -> None:
    """(∅-seal §4.7) No projection cells => no credible aggregate established => UNKNOWN."""
    result = adverse_increment(
        (), issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    assert result.result is RiskDecisionResult.UNKNOWN


def test_full_floor_and_cells_is_determinate_positive_side() -> None:
    """(∅-seal positive side) A covered floor + finite cells => a determinate (non-UNKNOWN) result."""
    result = adverse_increment(
        floor_cells(), issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    assert result.result is not RiskDecisionResult.UNKNOWN


def test_none_component_forces_unknown_not_smaller_vector() -> None:
    """(fail-closed §4.3) A missing (None) component makes the projection UNKNOWN, not smaller."""
    cells = (
        clean_cell(
            scenario=AdverseScenarioKind.FILL_PREFIX_ORDERING,
            max_credible_command_effect=None,
        ),
        clean_cell(scenario=AdverseScenarioKind.OVERLAP_RETRY),
    )
    result = adverse_increment(
        cells, issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    assert result.result is RiskDecisionResult.UNKNOWN
    assert result.increment.magnitude("ACCOUNT::GROSS_NOTIONAL") is None


def test_none_limit_forces_unknown() -> None:
    """(fail-closed §5.6) A missing effective limit (None headroom) => UNKNOWN."""
    cells = floor_cells(effective_limit=None)
    result = adverse_increment(
        cells, issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    assert result.result is RiskDecisionResult.UNKNOWN


def test_favorable_final_does_not_shrink_increment_negative() -> None:
    """(canary 'shrink') Intended reduction + credible overlap keeps the increment positive (§12:328)."""
    cell = clean_cell(
        conservative_current_usage=Decimal("100"),
        max_credible_command_effect=Decimal("0"),
        required_concurrent_overlap_effect=Decimal("30"),
        conservative_current_usage_already_committed=Decimal("100"),
        effective_limit=Decimal("1000"),
    )
    increment = cell.requested_increment()
    assert increment == Decimal("30")
    assert increment is not None
    assert increment > 0


def test_dominance_takes_max_over_scenarios() -> None:
    """(dominance max_q §12 line 317) Per (scope,dimension), the worst scenario increment wins."""
    small = clean_cell(
        scenario=AdverseScenarioKind.FILL_PREFIX_ORDERING,
        max_credible_command_effect=Decimal("1"),
    )
    large = clean_cell(
        scenario=AdverseScenarioKind.OVERLAP_RETRY,
        max_credible_command_effect=Decimal("40"),
    )
    result = adverse_increment(
        (small, large), issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    assert result.increment.magnitude("ACCOUNT::GROSS_NOTIONAL") == Decimal("44")


def test_produced_magnitudes_none_propagates() -> None:
    """(fail-closed §5.3) A None protective witness => produced magnitude None (never small)."""
    cells = (
        clean_cell(
            scenario=AdverseScenarioKind.FILL_PREFIX_ORDERING,
            worst_intermediate_risk=None,
        ),
        clean_cell(scenario=AdverseScenarioKind.OVERLAP_RETRY),
    )
    result = adverse_increment(
        cells, issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    assert result.worst_intermediate_risk is None
    assert result.result is not RiskDecisionResult.UNKNOWN


def test_distinct_scope_dimension_produce_distinct_components() -> None:
    """A second (scope, dimension) key yields its own increment component (no collapse)."""
    a = clean_cell(scenario=AdverseScenarioKind.FILL_PREFIX_ORDERING)
    b = clean_cell(
        scenario=AdverseScenarioKind.OVERLAP_RETRY,
        scope=RiskScopeKind.STRATEGY,
        dimension=RiskDimensionKind.NET_NOTIONAL,
    )
    result = adverse_increment(
        (a, b), issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    dims = set(result.increment.dimension_ids())
    assert "ACCOUNT::GROSS_NOTIONAL" in dims
    assert "STRATEGY::NET_NOTIONAL" in dims
