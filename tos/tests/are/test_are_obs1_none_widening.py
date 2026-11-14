"""§1.4 커널 라운드 #1 — OBS-1 ``| None`` 균일화 (are/predicates.py)."""

from __future__ import annotations

from typing import TypedDict, Unpack

from tos.are import (
    AdverseIncrementResult,
    AdverseScenarioSet,
    AggregateRiskDecision,
    AggregateRiskPolicy,
    AggregateRiskStateSnapshot,
    RiskDecisionResult,
    adverse_increment,
    risk_decision,
)
from tos.canonical import CanonicalizationScheme
from tos.rcl import CapacityVector

from ._are_strategies import (
    COVERAGE_FLOOR,
    SCHEME,
    floor_cells,
    issue_policy,
    issue_scenario_set,
    issue_snapshot,
)


class _DecisionKwargs(TypedDict):
    """1:1 with :func:`risk_decision`'s signature (plan §1.1 A-fn) — a"""

    projection: AdverseIncrementResult
    snapshot: AggregateRiskStateSnapshot | None
    applicable_risk_scopes: tuple[str, ...]
    snapshot_complete: bool
    numerically_safe: RiskDecisionResult | bool | None
    valuation_ok: bool | None
    envelope_not_enlarged: bool
    decision_id: str
    decision_generation: int
    scheme: CanonicalizationScheme
    policy: AggregateRiskPolicy | None
    scenario_set: AdverseScenarioSet | None
    effective_limit: CapacityVector | None
    effect_digest: str | None
    grant_identity: str | None


class _DecisionKwargsPartial(TypedDict, total=False):
    """Same fields as :class:`_DecisionKwargs`, all optional — the override-kwargs shape"""

    projection: AdverseIncrementResult
    snapshot: AggregateRiskStateSnapshot | None
    applicable_risk_scopes: tuple[str, ...]
    snapshot_complete: bool
    numerically_safe: RiskDecisionResult | bool | None
    valuation_ok: bool | None
    envelope_not_enlarged: bool
    decision_id: str
    decision_generation: int
    scheme: CanonicalizationScheme
    policy: AggregateRiskPolicy | None
    scenario_set: AdverseScenarioSet | None
    effective_limit: CapacityVector | None
    effect_digest: str | None
    grant_identity: str | None


def _decide(**overrides: Unpack[_DecisionKwargsPartial]) -> AggregateRiskDecision:
    """Issue a decision with all gates passing unless overridden (mirrors test_are_decision._decide)."""
    projection = adverse_increment(
        floor_cells(), issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    base: _DecisionKwargs = {
        "projection": projection,
        "snapshot": issue_snapshot(),
        "applicable_risk_scopes": ("acct-1",),
        "snapshot_complete": True,
        "numerically_safe": True,
        "valuation_ok": True,
        "envelope_not_enlarged": True,
        "decision_id": "dec-obs1",
        "decision_generation": 1,
        "scheme": SCHEME,
        "policy": issue_policy(),
        "scenario_set": issue_scenario_set(),
        "effective_limit": None,
        "effect_digest": "eff-1",
        "grant_identity": "grant-1",
    }
    base.update(overrides)
    return risk_decision(**base)


def test_numerically_safe_none_yields_unknown() -> None:
    """``numerically_safe=None`` (no opinion) is accepted by the type and yields UNKNOWN."""
    assert _decide(numerically_safe=None).result is RiskDecisionResult.UNKNOWN


def test_valuation_ok_none_yields_unknown() -> None:
    """``valuation_ok=None`` (no opinion) is accepted by the type and yields UNKNOWN."""
    assert _decide(valuation_ok=None).result is RiskDecisionResult.UNKNOWN


def test_both_none_yields_unknown() -> None:
    """Both fields ``None`` simultaneously still yields UNKNOWN (never permissive)."""
    assert (
        _decide(numerically_safe=None, valuation_ok=None).result
        is RiskDecisionResult.UNKNOWN
    )
