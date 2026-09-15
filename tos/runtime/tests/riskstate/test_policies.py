"""Loader happy-path + negative tests for
:mod:`tos_runtime.riskstate.policies` (TOS risk state service wave, lane a)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from tos.afg import ActionClassKind, ActionFlowScopeKind
from tos.are import AdverseScenarioKind, RiskDimensionKind, RiskScopeKind
from tos_runtime.riskstate.policies import (
    VenuePolicyConfigError,
    load_action_flow_policy,
    load_aggregate_risk_policy,
)

from ._documents import (
    SCHEME,
    action_flow_policy_yaml,
    aggregate_risk_policy_yaml,
)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ===========================================================================
# Aggregate Risk Policy — happy path
# ===========================================================================


def test_load_aggregate_risk_policy_happy_path(tmp_path: Path) -> None:
    path = _write(tmp_path, "are.yaml", aggregate_risk_policy_yaml())
    loaded = load_aggregate_risk_policy(path, scheme=SCHEME)

    assert loaded.policy.policy_id == "are-fixture-1"
    assert loaded.policy.policy_generation == 1
    assert loaded.policy.governed_dimensions == (
        RiskDimensionKind.LONG_SHORT_DELTA_DIRECTIONAL,
    )
    assert loaded.policy.governed_scopes == (RiskScopeKind.INSTRUMENT,)
    key = (RiskScopeKind.INSTRUMENT, RiskDimensionKind.LONG_SHORT_DELTA_DIRECTIONAL)
    assert loaded.dimension_ids == {key: "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"}
    assert loaded.effective_limits.magnitude(
        "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"
    ) == Decimal(1)
    assert loaded.required_scenario_kinds == frozenset(
        {AdverseScenarioKind.ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ}
    )
    assert loaded.required_scopes == frozenset({RiskScopeKind.INSTRUMENT})
    assert loaded.applicable_risk_scopes == ("INSTRUMENT",)
    assert loaded.unit == "CONTRACTS"


def test_load_aggregate_risk_policy_digest_recomputed_on_reload(tmp_path: Path) -> None:
    """A real, non-``TBD`` digest that matches a fresh recompute is accepted."""
    path = _write(tmp_path, "are.yaml", aggregate_risk_policy_yaml())
    first = load_aggregate_risk_policy(path, scheme=SCHEME)
    real_digest = first.policy.canonical_digest
    assert real_digest is not None and real_digest != "TBD"

    path2 = _write(
        tmp_path, "are2.yaml", aggregate_risk_policy_yaml(canonical_digest=real_digest)
    )
    second = load_aggregate_risk_policy(path2, scheme=SCHEME)
    assert second.policy.canonical_digest == real_digest


# ===========================================================================
# Aggregate Risk Policy — negatives
# ===========================================================================


def test_are_named_tbd_policy_id_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "are.yaml", aggregate_risk_policy_yaml(policy_id="TBD"))
    with pytest.raises(VenuePolicyConfigError, match="policy_id"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_draft_status_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "are.yaml", aggregate_risk_policy_yaml(status="DRAFT"))
    with pytest.raises(VenuePolicyConfigError, match="status"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_digest_mismatch_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "are.yaml", aggregate_risk_policy_yaml(canonical_digest="deadbeef")
    )
    with pytest.raises(VenuePolicyConfigError, match="canonical_digest"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_unknown_dimension_token_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "are.yaml",
        aggregate_risk_policy_yaml(governed_dimensions='["NOT_A_REAL_DIMENSION"]'),
    )
    with pytest.raises(VenuePolicyConfigError, match="RiskDimensionKind"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_unknown_scope_token_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "are.yaml",
        aggregate_risk_policy_yaml(governed_scopes='["NOT_A_SCOPE"]'),
    )
    with pytest.raises(VenuePolicyConfigError, match="RiskScopeKind"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_unknown_scenario_kind_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "are.yaml",
        aggregate_risk_policy_yaml(required_scenario_kinds='["NOT_A_SCENARIO"]'),
    )
    with pytest.raises(VenuePolicyConfigError, match="AdverseScenarioKind"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_effective_limit_key_not_in_dimension_ids_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "are.yaml",
        aggregate_risk_policy_yaml(effective_limit_key="GHOST::DIMENSION"),
    )
    with pytest.raises(VenuePolicyConfigError, match="effective_limits"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_dimension_id_scope_outside_governed_scopes_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "are.yaml",
        aggregate_risk_policy_yaml(
            governed_scopes='["ACCOUNT"]',  # dimension_ids still declares scope INSTRUMENT
        ),
    )
    with pytest.raises(VenuePolicyConfigError, match="governed_scopes"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_dimension_id_key_convention_violated_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "are.yaml",
        aggregate_risk_policy_yaml(dimension_id="WRONG::CONVENTION"),
    )
    with pytest.raises(VenuePolicyConfigError, match="convention"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_negative_effective_limit_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "are.yaml", aggregate_risk_policy_yaml(effective_limit_value="-1")
    )
    with pytest.raises(VenuePolicyConfigError, match="non-negative"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_instrument_scope_not_singleton_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "are.yaml", aggregate_risk_policy_yaml(instrument_scope='["A", "B"]')
    )
    with pytest.raises(VenuePolicyConfigError, match="EXACTLY one"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_model_view_generation_mismatch_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "are.yaml", aggregate_risk_policy_yaml(model_view_generation=99)
    )
    with pytest.raises(VenuePolicyConfigError, match="policy_generation"):
        load_aggregate_risk_policy(path, scheme=SCHEME)


def test_are_missing_file_refused(tmp_path: Path) -> None:
    with pytest.raises(VenuePolicyConfigError, match="not found"):
        load_aggregate_risk_policy(tmp_path / "missing.yaml", scheme=SCHEME)


# ===========================================================================
# Action Flow Policy — happy path
# ===========================================================================


def test_load_action_flow_policy_happy_path(tmp_path: Path) -> None:
    path = _write(tmp_path, "afg.yaml", action_flow_policy_yaml())
    loaded = load_action_flow_policy(path, scheme=SCHEME)

    assert loaded.policy.policy_id == "afg-fixture-1"
    assert loaded.flow_dimension_id == "afg.ORDER"
    assert loaded.limits["hard_limit"].magnitude("afg.ORDER") == Decimal(1)
    assert loaded.limits["runtime_limit"].magnitude("afg.ORDER") == Decimal(1)
    assert loaded.limits["envelope_max"].magnitude("afg.ORDER") == Decimal(1)
    assert loaded.limits["decision_effective_limit"].magnitude("afg.ORDER") == Decimal(
        1
    )
    assert loaded.scope_independence.scope is ActionFlowScopeKind.ACCOUNT
    assert loaded.scope_independence.is_independent() is True
    assert loaded.covered_scopes == (ActionFlowScopeKind.ACCOUNT,)
    assert loaded.required_scopes == frozenset({ActionFlowScopeKind.ACCOUNT})
    assert loaded.applicable_action_flow_scopes == ("ACCOUNT",)
    assert loaded.deployment_facts.concurrent_consumers_share_one_envelope is False
    assert loaded.deployment_facts.envelope_reset_on_duplicate is False
    assert loaded.deployment_facts.duplicate_event_created_new_allowance is False
    from tos.venue import ActionClass

    assert (
        loaded.action_class_map[ActionClass.NEW_LONG] is ActionClassKind.NORMAL_NEW_RISK
    )
    assert (
        loaded.action_class_map[ActionClass.DECREASE]
        is ActionClassKind.ORDINARY_REDUCE_OR_EXIT
    )


# ===========================================================================
# Action Flow Policy — negatives
# ===========================================================================


def test_afg_named_tbd_policy_id_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "afg.yaml", action_flow_policy_yaml(policy_id="TBD"))
    with pytest.raises(VenuePolicyConfigError, match="policy_id"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_draft_status_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "afg.yaml", action_flow_policy_yaml(status="DRAFT"))
    with pytest.raises(VenuePolicyConfigError, match="status"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_digest_mismatch_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "afg.yaml", action_flow_policy_yaml(canonical_digest="deadbeef")
    )
    with pytest.raises(VenuePolicyConfigError, match="canonical_digest"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_unknown_dimension_token_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "afg.yaml",
        action_flow_policy_yaml(governed_dimensions='["afg.GHOST"]'),
    )
    with pytest.raises(VenuePolicyConfigError, match="ActionFlowDimensionKind"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_unknown_scope_token_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "afg.yaml", action_flow_policy_yaml(governed_scopes='["NOT_A_SCOPE"]')
    )
    with pytest.raises(VenuePolicyConfigError, match="ActionFlowScopeKind"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_unknown_action_class_kind_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "afg.yaml",
        action_flow_policy_yaml(governed_action_classes='["NOT_A_CLASS"]'),
    )
    with pytest.raises(VenuePolicyConfigError, match="ActionClassKind"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_flow_dimension_id_outside_governed_dimensions_refused(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        "afg.yaml",
        action_flow_policy_yaml(
            governed_dimensions='["afg.QUERY"]', flow_dimension_id="afg.ORDER"
        ),
    )
    with pytest.raises(VenuePolicyConfigError, match="governed_dimensions"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_deployment_facts_null_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "afg.yaml",
        action_flow_policy_yaml(concurrent_consumers_share_one_envelope="null"),
    )
    with pytest.raises(VenuePolicyConfigError, match="deployment_facts"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_scope_independence_axis_null_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "afg.yaml", action_flow_policy_yaml(allocation_separated="null")
    )
    with pytest.raises(VenuePolicyConfigError, match="scope_independence"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_deployment_facts_block_missing_refused(tmp_path: Path) -> None:
    """Review HIGH (team-lead 2026-09-16): the reviewer's own mutation — "default to
    (False, False, True) when ``_runtime.deployment_facts`` is absent entirely" — must be
    refused by ``require_mapping_key``'s absent-key check, distinct from
    :func:`test_afg_deployment_facts_null_refused`'s "present but one axis null" shape.
    """
    path = _write(
        tmp_path,
        "afg.yaml",
        action_flow_policy_yaml(include_deployment_facts=False),
    )
    with pytest.raises(VenuePolicyConfigError, match="deployment_facts"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_scope_independence_block_missing_refused(tmp_path: Path) -> None:
    """Same shape as :func:`test_afg_deployment_facts_block_missing_refused`, for
    ``_runtime.scope_independence`` — an absent block, not merely one null axis."""
    path = _write(
        tmp_path,
        "afg.yaml",
        action_flow_policy_yaml(include_scope_independence=False),
    )
    with pytest.raises(VenuePolicyConfigError, match="scope_independence"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_action_class_map_unknown_venue_action_class_refused(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        "afg.yaml",
        action_flow_policy_yaml(
            action_class_map='{"NOT_A_VENUE_CLASS": "NORMAL_NEW_RISK"}'
        ),
    )
    with pytest.raises(VenuePolicyConfigError, match="ActionClass"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_action_class_map_unknown_action_class_kind_value_refused(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        "afg.yaml",
        action_flow_policy_yaml(action_class_map='{"NEW_LONG": "NOT_A_KIND"}'),
    )
    with pytest.raises(VenuePolicyConfigError, match="ActionClassKind"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_action_class_map_value_outside_governed_action_classes_refused(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        "afg.yaml",
        action_flow_policy_yaml(
            governed_action_classes='["NORMAL_NEW_RISK"]',
            action_class_map='{"NEW_LONG": "SAFETY_PROTECTIVE"}',
        ),
    )
    with pytest.raises(VenuePolicyConfigError, match="governed_action_classes"):
        load_action_flow_policy(path, scheme=SCHEME)


def test_afg_account_scope_not_explicit_list_refused(tmp_path: Path) -> None:
    """A missing-but-required explicit-list scope array (never null) is refused — the venue
    primitives' own ``require_list`` discipline ("a missing key or null is a named-TBD gap").
    """
    text = action_flow_policy_yaml().replace(
        'account_scope: ["acct-1"]', "account_scope: null"
    )
    path = _write(tmp_path, "afg.yaml", text)
    with pytest.raises(VenuePolicyConfigError, match="account_scope"):
        load_action_flow_policy(path, scheme=SCHEME)
