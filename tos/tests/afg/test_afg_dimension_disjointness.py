"""Gap-1 — afg dimension-id namespace disjointness from the economic axes (§2.2-5 / §7).

``ActionFlowVector`` **is** the rcl ``CapacityVector`` type (design #16 §0.4c), whose
``dimension_id`` is a free string and whose ``aggregate_usage`` / ``effective_limit``
arithmetic matches on **string equality**. The self-consistency condition of the REUSE
justification ("no coordinate collapse") is therefore that the afg action-flow dimension-id
set is **disjoint** from the economic / aggregate-risk dimension-id sets carried on the same
container by the other three consumers (rcl / are / ioc).

afg cannot import those siblings (§0.3 allowlist), so this **test-only** cross-import is
where the global namespace condition is asserted — the same pattern as the MANDATED seam
checks (design #16 §3.4(d); a test import is not a package edge, §7.1).

The design fixes only the afg half of the contract; the global prefix convention across all
four consumers stays a Phase-0 / follow-up decision (design #16 §2.2-5 / §10.3-6). A
planted-collision canary proves the assertion is not vacuous.
"""

from __future__ import annotations

from tos.afg import (
    ACTION_FLOW_DIMENSION_IDS,
    ActionFlowDimensionKind,
    action_flow_dimension_id,
    is_action_flow_dimension_id,
)


def _are_risk_dimension_ids() -> frozenset[str]:
    """The aggregate-risk (economic view) dimension tokens — test-only import."""
    from tos.are import RiskDimensionKind

    return frozenset(kind.value for kind in RiskDimensionKind)


def test_afg_dimension_ids_are_exactly_the_enum_values() -> None:
    """(Gap-1 convention) An afg dimension id IS an ``ActionFlowDimensionKind`` value."""
    assert (
        frozenset(kind.value for kind in ActionFlowDimensionKind)
        == ACTION_FLOW_DIMENSION_IDS
    )
    for kind in ActionFlowDimensionKind:
        assert action_flow_dimension_id(kind) == kind.value
        assert is_action_flow_dimension_id(kind.value) is True


def test_afg_dimension_ids_are_disjoint_from_the_aggregate_risk_axis() -> None:
    """(Gap-1) afg action-flow ids ∩ are aggregate-risk (economic-view) ids = ∅."""
    risk_ids = _are_risk_dimension_ids()
    # Both sides must be non-empty or the disjointness assertion is vacuously true
    # (an empty afg id set would trivially be "disjoint" from everything — MINOR-7).
    assert (
        ACTION_FLOW_DIMENSION_IDS
    ), "the afg action-flow dimension-id set must be non-empty for this to bite"
    assert risk_ids, "the are risk-dimension axis must be non-empty for this to bite"
    overlap = ACTION_FLOW_DIMENSION_IDS & risk_ids
    assert overlap == frozenset(), (
        "afg action-flow dimension ids must not collide with the economic / aggregate-"
        f"risk axis on the shared CapacityVector container (Gap-1): {sorted(overlap)}"
    )


def test_action_rate_risk_and_action_flow_resource_stay_distinct_axes() -> None:
    """(§2.2-5) are's ``BROKER_ACTION_RATE_PROTECTIVE_RESERVE`` is the *economic view*.

    It is deliberately **not** an afg resource dimension: the same real-world phenomenon
    appears on two axes, and the two token sets must not collapse onto one another.
    """
    risk_ids = _are_risk_dimension_ids()
    assert "BROKER_ACTION_RATE_PROTECTIVE_RESERVE" in risk_ids
    assert is_action_flow_dimension_id("BROKER_ACTION_RATE_PROTECTIVE_RESERVE") is False


def test_ioc_economic_effect_envelope_shares_the_container_not_the_namespace() -> None:
    """(Gap-1, four consumers) ioc's ``EconomicEffectEnvelope`` IS the same container type."""
    from tos.afg import ActionFlowVector
    from tos.ioc import EconomicEffectEnvelope
    from tos.rcl import CapacityVector

    # All four consumers share ONE container type — which is exactly why the dimension-id
    # namespaces must be disjoint (design #16 §2.2-5).
    assert EconomicEffectEnvelope is CapacityVector
    assert ActionFlowVector is CapacityVector


def test_unenumerated_dimension_is_not_an_afg_dimension() -> None:
    """(§2.2-4) The enum is a named minimum set — a free string is not an afg dimension."""
    for token in (None, "", "GROSS_NOTIONAL", "broker_request", "SOMETHING_ELSE"):
        assert is_action_flow_dimension_id(token) is False


def test_planted_collision_would_be_detected() -> None:
    """(canary) The disjointness assertion is not vacuous — a planted overlap is caught."""
    planted = ACTION_FLOW_DIMENSION_IDS | {"GROSS_NOTIONAL"}
    assert planted & _are_risk_dimension_ids() != frozenset()
