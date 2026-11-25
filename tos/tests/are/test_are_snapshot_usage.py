"""The snapshot's own committed usage as a GRANT/DENY input (design #13 §5.6 / §9; #984 ①)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tos.are import (
    AdverseIncrementResult,
    AggregateRiskDecision,
    RiskDecisionResult,
    adverse_increment,
    risk_decision,
    snapshot_usage_within_limit,
)
from tos.rcl import CapacityComponent, CapacityVector

from ._are_strategies import (
    COVERAGE_FLOOR,
    SCHEME,
    clean_cell,
    floor_cells,
    issue_policy,
    issue_scenario_set,
    issue_snapshot,
)

_DIMENSION = "ACCOUNT::GROSS_NOTIONAL"
_LIMIT = Decimal("100")


def _vector(magnitude: Decimal | None, dimension: str = _DIMENSION) -> CapacityVector:
    """A one-dimension capacity vector (the shape a single-instrument tenant commits)."""
    return CapacityVector(
        components=(CapacityComponent(dimension_id=dimension, magnitude=magnitude),)
    )


def _grant_projection() -> AdverseIncrementResult:
    """A determinate, within-headroom GRANT projection."""
    return adverse_increment(
        floor_cells(), issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )


def _close_projection() -> AdverseIncrementResult:
    """A CLOSE-shaped projection: the position sits at the limit, the command reduces it."""
    return adverse_increment(
        tuple(
            clean_cell(
                scenario=scenario,
                conservative_current_usage=_LIMIT,
                conservative_current_usage_already_committed=_LIMIT,
                max_credible_command_effect=-_LIMIT,
                required_concurrent_overlap_effect=Decimal("0"),
                effective_limit=_LIMIT,
            )
            for scenario in COVERAGE_FLOOR
        ),
        issue_scenario_set(),
        required_scenario_kinds=COVERAGE_FLOOR,
    )


def _decide(**overrides: Any) -> AggregateRiskDecision:
    """A decision with every other gate positive; vary only the snapshot usage / limit."""
    base: dict[str, Any] = {
        "projection": _grant_projection(),
        "snapshot": issue_snapshot(),
        "applicable_risk_scopes": ("acct-1",),
        "snapshot_complete": True,
        "numerically_safe": True,
        "valuation_ok": True,
        "envelope_not_enlarged": True,
        "decision_id": "dec-usage",
        "decision_generation": 1,
        "scheme": SCHEME,
        "policy": issue_policy(),
        "scenario_set": issue_scenario_set(),
        "effective_limit": _vector(_LIMIT),
        "effect_digest": "eff-1",
        "grant_identity": "grant-1",
    }
    base.update(overrides)
    return risk_decision(**base)


def test_an_empty_snapshot_usage_still_grants() -> None:
    """(unchanged) Nothing committed yet — the first entry of a flat scope — still GRANTs."""
    assert issue_snapshot().conservative_current_usage == CapacityVector()
    assert _decide().result is RiskDecisionResult.GRANT


def test_snapshot_usage_at_the_effective_limit_still_grants() -> None:
    """(unchanged) Committed usage exactly AT the limit is not over it — the bound is strict."""
    snapshot = issue_snapshot(conservative_current_usage=_vector(_LIMIT))
    assert _decide(snapshot=snapshot).result is RiskDecisionResult.GRANT


def test_snapshot_usage_over_the_effective_limit_denies() -> None:
    """(#984 ①) Failing input: committed usage 150 against a limit of 100 may not GRANT."""
    snapshot = issue_snapshot(conservative_current_usage=_vector(Decimal("150")))
    assert _decide(snapshot=snapshot).result is RiskDecisionResult.DENY


def test_a_close_over_an_at_limit_position_still_grants() -> None:
    """(#984 ② x ①) A CLOSE at a position ON the limit: netted usage GRANTs, doubled DENYs."""
    projection = _close_projection()
    assert projection.result is RiskDecisionResult.GRANT
    snapshot = issue_snapshot(conservative_current_usage=_vector(_LIMIT))
    assert (
        _decide(projection=projection, snapshot=snapshot).result
        is RiskDecisionResult.GRANT
    )
    doubled = issue_snapshot(conservative_current_usage=_vector(_LIMIT * 2))
    assert (
        _decide(projection=projection, snapshot=doubled).result
        is RiskDecisionResult.DENY
    )


def test_a_usage_dimension_the_limit_does_not_declare_is_not_judged_here() -> None:
    """(boundary) A usage dimension outside the decision's own limit vector is not judged here."""
    snapshot = issue_snapshot(
        conservative_current_usage=_vector(Decimal("1"), dimension="ungoverned")
    )
    assert (
        snapshot_usage_within_limit(snapshot, effective_limit=_vector(_LIMIT)) is True
    )
    assert _decide(snapshot=snapshot).result is RiskDecisionResult.GRANT


def test_an_unknown_snapshot_usage_magnitude_is_unknown() -> None:
    """(fail-closed) A declared-but-UNKNOWN magnitude is never read as zero usage."""
    snapshot = issue_snapshot(conservative_current_usage=_vector(None))
    assert _decide(snapshot=snapshot).result is RiskDecisionResult.UNKNOWN


def test_an_unknown_usage_does_not_soften_an_earned_deny() -> None:
    """(order) An empty scope already DENYs; an unreadable usage may not turn that to UNKNOWN."""
    snapshot = issue_snapshot(conservative_current_usage=_vector(None))
    assert _decide(snapshot=snapshot).result is RiskDecisionResult.UNKNOWN
    assert (
        _decide(snapshot=snapshot, applicable_risk_scopes=()).result
        is RiskDecisionResult.DENY
    )
    assert (
        _decide(snapshot=snapshot, envelope_not_enlarged=False).result
        is RiskDecisionResult.DENY
    )


def test_an_unknown_limit_magnitude_is_unknown() -> None:
    """(fail-closed) A declared-but-UNKNOWN limit is not an absent limit — never GRANT on it."""
    snapshot = issue_snapshot(conservative_current_usage=_vector(Decimal("1")))
    assert (
        _decide(snapshot=snapshot, effective_limit=_vector(None)).result
        is RiskDecisionResult.UNKNOWN
    )


def test_predicate_is_vacuously_true_on_an_empty_usage() -> None:
    """The predicate itself: no committed dimension means nothing to exceed."""
    assert (
        snapshot_usage_within_limit(issue_snapshot(), effective_limit=_vector(_LIMIT))
        is True
    )


def test_predicate_has_no_opinion_without_a_snapshot_or_a_limit() -> None:
    """The predicate itself: a missing snapshot / limit is ``None`` (no opinion), never True."""
    assert snapshot_usage_within_limit(None, effective_limit=_vector(_LIMIT)) is None
    assert snapshot_usage_within_limit(issue_snapshot(), effective_limit=None) is None
