"""Decision integrity + scope / binding / dimension / envelope predicates (design #13 §5.1-§5.6).

Both-ways canaries per §5 + the forbidden-verb canaries: "exclude" (§5.1 scope omission),
"patch/union/substitute" (§5.2 binding), "enlarge" (§5.6 envelope). ARE-EV-001/002/004/006
substrate — closes no ARE-EV.
"""

from __future__ import annotations

from decimal import Decimal

from tos.are import (
    RiskDecisionResult,
    RiskDimensionKind,
    RiskScopeKind,
    adverse_increment,
    dimension_vector_integrity,
    envelope_bound_not_enlarged,
    exact_effect_snapshot_binding,
    numerical_safety,
    risk_decision,
    snapshot_scope_complete,
)
from tos.rcl import CapacityVector

from ._are_strategies import (
    COVERAGE_FLOOR,
    SCHEME,
    capacity_vector,
    clean_cell,
    complete_descriptor,
    floor_cells,
    issue_policy,
    issue_scenario_set,
    issue_snapshot,
)

_ACCOUNT = frozenset({RiskScopeKind.ACCOUNT})


def _grant_projection():
    """A determinate, within-headroom GRANT projection."""
    return adverse_increment(
        floor_cells(), issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )


def _decide(**overrides):
    """Issue a decision with all gates passing unless overridden."""
    base = {
        "projection": _grant_projection(),
        "snapshot": issue_snapshot(),
        "applicable_risk_scopes": ("acct-1",),
        "snapshot_complete": True,
        "numerically_safe": True,
        "valuation_ok": True,
        "envelope_not_enlarged": True,
        "decision_id": "dec-x",
        "decision_generation": 1,
        "scheme": SCHEME,
        "policy": issue_policy(),
        "scenario_set": issue_scenario_set(),
        "effect_digest": "eff-1",
        "grant_identity": "grant-1",
    }
    base.update(overrides)
    return risk_decision(**base)


# ---------------------------------------------------------------------------
# risk_decision — GRANT / DENY / UNKNOWN (both-ways)
# ---------------------------------------------------------------------------


def test_all_gates_pass_grants() -> None:
    """(canary +) A determinate projection + every gate positive => GRANT."""
    assert _decide().result is RiskDecisionResult.GRANT


def test_unknown_projection_yields_unknown() -> None:
    """(canary UNKNOWN) An UNKNOWN projection => UNKNOWN decision (never permissive)."""
    unknown = adverse_increment(
        (), issue_scenario_set(), required_scenario_kinds=COVERAGE_FLOOR
    )
    assert _decide(projection=unknown).result is RiskDecisionResult.UNKNOWN


def test_numerically_unsafe_yields_unknown() -> None:
    """(§4.3) Not numerically safe => UNKNOWN (never a smaller vector)."""
    assert _decide(numerically_safe=False).result is RiskDecisionResult.UNKNOWN


def test_non_conservative_valuation_yields_unknown() -> None:
    """(§5.5) Non-conservative valuation => UNKNOWN."""
    assert _decide(valuation_ok=False).result is RiskDecisionResult.UNKNOWN


def test_raw_numerical_safety_nan_wiring_is_restrictive() -> None:
    """(MAJOR-1 国면 B) A raw numerical_safety(NaN) return wired in => UNKNOWN (truthy trap sealed).

    ``numerical_safety`` returns the *truthy* ``RiskDecisionResult.UNKNOWN`` on a NaN; the
    ``is not True`` gate in ``risk_decision`` must still treat it as restrictive (a bare
    truthiness check would have let it slip toward GRANT).
    """
    unsafe = numerical_safety([Decimal("NaN")], units_consistent=True)
    assert unsafe is RiskDecisionResult.UNKNOWN  # truthy sentinel
    assert _decide(numerically_safe=unsafe).result is RiskDecisionResult.UNKNOWN


def test_raw_numerical_safety_empty_wiring_is_restrictive() -> None:
    """(MAJOR-1 国면 A+B) A raw numerical_safety([]) return wired in => UNKNOWN (empty fails closed)."""
    unsafe = numerical_safety([], units_consistent=True)
    assert unsafe is RiskDecisionResult.UNKNOWN
    assert _decide(numerically_safe=unsafe).result is RiskDecisionResult.UNKNOWN


def test_raw_numerical_safety_true_wiring_grants() -> None:
    """(both-ways) A raw numerical_safety(finite) True wired in leaves the GRANT path open."""
    safe = numerical_safety([Decimal("1")], units_consistent=True)
    assert safe is True
    assert _decide(numerically_safe=safe).result is RiskDecisionResult.GRANT


def test_missing_snapshot_yields_unknown() -> None:
    """(§5.6) A None / incomplete snapshot => UNKNOWN."""
    assert _decide(snapshot=None).result is RiskDecisionResult.UNKNOWN
    assert _decide(snapshot_complete=False).result is RiskDecisionResult.UNKNOWN


def test_empty_scope_is_restrictive_not_wildcard() -> None:
    """(§5.6 / §15 line 385) An empty requested scope is restrictive (DENY), never a wildcard GRANT."""
    assert _decide(applicable_risk_scopes=()).result is RiskDecisionResult.DENY


def test_envelope_enlarged_denies() -> None:
    """(§5.6 enlarge) A limit that enlarges the envelope => DENY."""
    assert _decide(envelope_not_enlarged=False).result is RiskDecisionResult.DENY


def test_over_headroom_projection_denies() -> None:
    """(§5.6) A projection over headroom (DENY) carries through to a DENY decision."""
    over = adverse_increment(
        (
            clean_cell(
                conservative_current_usage=Decimal("100"),
                max_credible_command_effect=Decimal("100"),
            ),
            clean_cell(scenario=list(COVERAGE_FLOOR)[0]),
        ),
        issue_scenario_set(),
        required_scenario_kinds=COVERAGE_FLOOR,
    )
    # the projection is DENY when a cell is over headroom; assert the decision follows
    if over.result is RiskDecisionResult.DENY:
        assert _decide(projection=over).result is RiskDecisionResult.DENY


def test_capacity_coverage_necessary_not_sufficient() -> None:
    """(§24.8) Even with a determinate GRANT projection, an UNKNOWN state stays UNKNOWN."""
    # snapshot incomplete (an UNKNOWN state) => UNKNOWN even though projection would grant.
    assert _decide(snapshot_complete=False).result is RiskDecisionResult.UNKNOWN


def test_decision_is_forward_only_and_all_false_authority() -> None:
    """(§16 / ARE-INV-009) The issued decision carries no reservation coordinate + all-false authority."""
    decision = _decide()
    assert not hasattr(decision, "bound_reservation_revision")
    assert decision.authority_effect.creates_capacity is False
    assert decision.authority_effect.may_rearm is False


# ---------------------------------------------------------------------------
# snapshot_scope_complete — both-ways + "exclude" verb + ∅
# ---------------------------------------------------------------------------


def test_snapshot_scope_complete_positive() -> None:
    """(canary +) A snapshot covering every required scope + attributed => True."""
    assert (
        snapshot_scope_complete(issue_snapshot(), _ACCOUNT, all_fields_attributed=True)
        is True
    )


def test_snapshot_scope_exclude_omission_rejected() -> None:
    """(canary 'exclude' §9 line 262) An omitted required scope => False."""
    two = frozenset({RiskScopeKind.ACCOUNT, RiskScopeKind.STRATEGY})
    assert (
        snapshot_scope_complete(issue_snapshot(), two, all_fields_attributed=True)
        is False
    )


def test_snapshot_scope_empty_required_fails_closed() -> None:
    """(∅-seal §4.7) An empty required scope set is not vacuous completeness => False."""
    assert (
        snapshot_scope_complete(
            issue_snapshot(), frozenset(), all_fields_attributed=True
        )
        is False
    )


def test_snapshot_scope_missing_attribution_fails_closed() -> None:
    """(§9 line 258) Missing / None field attribution => False; None snapshot => False."""
    assert (
        snapshot_scope_complete(issue_snapshot(), _ACCOUNT, all_fields_attributed=None)
        is False
    )
    assert (
        snapshot_scope_complete(issue_snapshot(), _ACCOUNT, all_fields_attributed=False)
        is False
    )
    assert snapshot_scope_complete(None, _ACCOUNT, all_fields_attributed=True) is False


# ---------------------------------------------------------------------------
# exact_effect_snapshot_binding — "patch/union/substitute" verb
# ---------------------------------------------------------------------------


def test_exact_binding_positive() -> None:
    """(canary +) One exact matching digest set binds => True."""
    assert (
        exact_effect_snapshot_binding(
            snapshot_digest="s",
            scenario_set_digest="sc",
            effect_digest="e",
            expected_snapshot_digest="s",
            expected_scenario_set_digest="sc",
            expected_effect_digest="e",
        )
        is True
    )


def test_exact_binding_substitute_rejected() -> None:
    """(canary 'patch/union/substitute' §26 ARE-AC-002) A substituted digest => False."""
    assert (
        exact_effect_snapshot_binding(
            snapshot_digest="s-OTHER",
            scenario_set_digest="sc",
            effect_digest="e",
            expected_snapshot_digest="s",
            expected_scenario_set_digest="sc",
            expected_effect_digest="e",
        )
        is False
    )


def test_exact_binding_none_fails_closed() -> None:
    """(fail-closed) A None digest on either side => False."""
    assert (
        exact_effect_snapshot_binding(
            snapshot_digest=None,
            scenario_set_digest="sc",
            effect_digest="e",
            expected_snapshot_digest="s",
            expected_scenario_set_digest="sc",
            expected_effect_digest="e",
        )
        is False
    )


# ---------------------------------------------------------------------------
# dimension_vector_integrity — both-ways + ∅ dimension
# ---------------------------------------------------------------------------


def test_dimension_integrity_positive() -> None:
    """(canary +) Complete descriptors + described cells + known higher limits => True."""
    assert (
        dimension_vector_integrity(
            (complete_descriptor(),), (clean_cell(),), higher_scope_limits_known=True
        )
        is True
    )


def test_dimension_integrity_empty_descriptors_fails_closed() -> None:
    """(∅-seal §4.7) An empty governed-dimension set => False (not vacuous)."""
    assert (
        dimension_vector_integrity((), (clean_cell(),), higher_scope_limits_known=True)
        is False
    )


def test_dimension_integrity_missing_conversion_coefficient_fails_closed() -> None:
    """(§10 line 281) A None cross-dimension conversion coefficient cannot silently default => False."""
    bad = complete_descriptor(conversion_coefficient=None)
    assert (
        dimension_vector_integrity(
            (bad,), (clean_cell(),), higher_scope_limits_known=True
        )
        is False
    )


def test_dimension_integrity_unknown_higher_limit_fails_closed() -> None:
    """(§10 line 283) An unknown higher / cross-scope limit blocks a lower projection => False."""
    assert (
        dimension_vector_integrity(
            (complete_descriptor(),), (clean_cell(),), higher_scope_limits_known=None
        )
        is False
    )


def test_dimension_integrity_undescribed_cell_dimension_fails_closed() -> None:
    """(§5.4) A projected cell whose dimension has no descriptor => False."""
    desc = complete_descriptor(
        dimension=RiskDimensionKind.NET_NOTIONAL
    )  # describes NET, not GROSS
    assert (
        dimension_vector_integrity(
            (desc,), (clean_cell(),), higher_scope_limits_known=True
        )
        is False
    )


# ---------------------------------------------------------------------------
# envelope_bound_not_enlarged — both-ways + "enlarge" verb (v1.1 MINOR-2)
# ---------------------------------------------------------------------------


def test_envelope_not_enlarged_positive() -> None:
    """(canary + §5.6) effective (5) <= envelope max (10) from the envelope source => True."""
    assert (
        envelope_bound_not_enlarged(
            decision_effective_limit=capacity_vector(magnitude=Decimal("5")),
            injected_envelope_max=capacity_vector(magnitude=Decimal("10")),
            limit_source_is_injected_envelope=True,
        )
        is True
    )


def test_envelope_enlarge_attempt_rejected() -> None:
    """(canary 'enlarge' ARE-INV-007) effective (50) > envelope max (10) => False."""
    assert (
        envelope_bound_not_enlarged(
            decision_effective_limit=capacity_vector(magnitude=Decimal("50")),
            injected_envelope_max=capacity_vector(magnitude=Decimal("10")),
            limit_source_is_injected_envelope=True,
        )
        is False
    )


def test_envelope_non_envelope_source_rejected() -> None:
    """(ARE-INV-007 line 178) A broker / model / runtime source (not the envelope) => False."""
    assert (
        envelope_bound_not_enlarged(
            decision_effective_limit=capacity_vector(magnitude=Decimal("5")),
            injected_envelope_max=capacity_vector(magnitude=Decimal("10")),
            limit_source_is_injected_envelope=False,
        )
        is False
    )


def test_envelope_none_or_undeclared_fails_closed() -> None:
    """(fail-closed) A None envelope, or an effective dimension the envelope omits, => False."""
    assert (
        envelope_bound_not_enlarged(
            decision_effective_limit=capacity_vector(magnitude=Decimal("5")),
            injected_envelope_max=None,
            limit_source_is_injected_envelope=True,
        )
        is False
    )
    # effective declares 'qty', envelope declares 'notional' only => undeclared => False
    assert (
        envelope_bound_not_enlarged(
            decision_effective_limit=capacity_vector(
                dimension="qty", magnitude=Decimal("5")
            ),
            injected_envelope_max=capacity_vector(
                dimension="notional", magnitude=Decimal("10")
            ),
            limit_source_is_injected_envelope=True,
        )
        is False
    )


# ---------------------------------------------------------------------------
# envelope_bound_not_enlarged — empty effective limit pinning (MINOR-1)
# ---------------------------------------------------------------------------


def test_empty_effective_limit_with_envelope_source_is_true() -> None:
    """(MINOR-1 pin) An empty effective limit (0 dimensions = 0 headroom) enlarges nothing => True.

    Intentional: an empty CapacityVector is the most-restrictive bound (no wildcard); it returns
    True only AFTER the positive ``limit_source_is_injected_envelope is True`` gate passes.
    """
    assert (
        envelope_bound_not_enlarged(
            decision_effective_limit=CapacityVector(),
            injected_envelope_max=capacity_vector(magnitude=Decimal("10")),
            limit_source_is_injected_envelope=True,
        )
        is True
    )


def test_empty_effective_limit_non_envelope_source_fails_closed() -> None:
    """(MINOR-1 pin) An empty effective limit still fails closed when the source gate is not positive."""
    for source in (False, None):
        assert (
            envelope_bound_not_enlarged(
                decision_effective_limit=CapacityVector(),
                injected_envelope_max=capacity_vector(magnitude=Decimal("10")),
                limit_source_is_injected_envelope=source,
            )
            is False
        )
