"""Gap-1 — afg dimension-id namespace disjointness from the economic axes (§2.2-5 / §7)."""

from __future__ import annotations

from tos.afg import (
    ACTION_FLOW_DIMENSION_IDS,
    AFG_DIMENSION_ID_PREFIX,
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


def test_every_afg_dimension_id_carries_the_afg_prefix() -> None:
    """(Phase-0 Variant A) Every afg-owned dimension id is namespaced ``afg.``."""
    assert ACTION_FLOW_DIMENSION_IDS, "non-empty, or every assertion below is vacuous"
    for kind in ActionFlowDimensionKind:
        assert kind.value.startswith(AFG_DIMENSION_ID_PREFIX), (
            f"afg dimension id {kind.value!r} must carry the "
            f"{AFG_DIMENSION_ID_PREFIX!r} namespace prefix (Phase-0 Variant A)"
        )
        bare = kind.value[len(AFG_DIMENSION_ID_PREFIX) :]
        assert bare, f"{kind.value!r} must name a resource after the prefix"
        assert kind.name == bare, (
            f"member name {kind.name!r} must be the unprefixed resource word of "
            f"{kind.value!r} — the ADR §5.6:133 wording is preserved in the name"
        )
        assert is_action_flow_dimension_id(bare) is False


def test_afg_dimension_ids_are_disjoint_from_the_aggregate_risk_axis() -> None:
    """(Gap-1) afg action-flow ids ∩ are aggregate-risk (economic-view) ids = ∅."""
    risk_ids = _are_risk_dimension_ids()
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
    """(§2.2-5) are's ``BROKER_ACTION_RATE_PROTECTIVE_RESERVE`` is the *economic view*."""
    risk_ids = _are_risk_dimension_ids()
    assert "BROKER_ACTION_RATE_PROTECTIVE_RESERVE" in risk_ids
    assert is_action_flow_dimension_id("BROKER_ACTION_RATE_PROTECTIVE_RESERVE") is False


def test_ioc_economic_effect_envelope_shares_the_container_not_the_namespace() -> None:
    """(Gap-1, four consumers) ioc's ``EconomicEffectEnvelope`` IS the same container type."""
    from tos.afg import ActionFlowVector
    from tos.ioc import EconomicEffectEnvelope
    from tos.rcl import CapacityVector

    assert EconomicEffectEnvelope is CapacityVector
    assert ActionFlowVector is CapacityVector


def test_unenumerated_dimension_is_not_an_afg_dimension() -> None:
    """(§2.2-4) The enum is a named minimum set — a free string is not an afg dimension."""
    for token in (
        None,
        "",
        "GROSS_NOTIONAL",
        "broker_request",
        "SOMETHING_ELSE",
        "afg.",
        "rcl.BROKER_REQUEST",
        "are.BROKER_REQUEST",
        "ioc.BROKER_REQUEST",
        "AFG.BROKER_REQUEST",
        "xafg.BROKER_REQUEST",
    ):
        assert is_action_flow_dimension_id(token) is False


def test_planted_collision_would_be_detected() -> None:
    """(canary) The disjointness assertion is not vacuous — a planted overlap is caught."""
    planted = ACTION_FLOW_DIMENSION_IDS | {"GROSS_NOTIONAL"}
    assert planted & _are_risk_dimension_ids() != frozenset()
