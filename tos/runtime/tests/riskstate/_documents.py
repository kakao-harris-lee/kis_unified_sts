"""Shared Aggregate Risk Policy / Action Flow Policy INSTANCE document builders (TOS risk
state service wave, lane a; ``docs/plans/2026-09-16-tos-risk-state-service-plan.md``).

Mirrors ``tests/venue/_documents.py`` exactly: each builder copies the FULL key set of
``tos-spec/src/part-1-foundation/verification/AGGREGATE-RISK-POLICY-template.yaml`` /
``ACTION-FLOW-POLICY-template.yaml`` (every rule-list key present as ``[]``,
``authority``/``evidence``/``hard_safety_envelope``/``runtime_safety_profile`` present as
their template-shaped mappings) plus the two sibling ``_model_view``/``_runtime`` blocks the
loader actually reads kernel-typed content from.

The YAML VALUES below are FIXTURE DATA for these test suites only — NOT the operator-signed
production policy (plan §6 ②, an open operator decision, lane c/S)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalizationScheme, get_scheme

#: The one registered kernel canonicalization scheme (mirrors
#: ``tests.venue._documents``'s own ``SCHEME`` constant).
SCHEME: CanonicalizationScheme = get_scheme(EV_L1_PROVISIONAL_VERSION)

FIXTURE_ARE_POLICY_ID = "are-fixture-1"
FIXTURE_ARE_POLICY_GENERATION = 1
FIXTURE_AFG_POLICY_ID = "afg-fixture-1"
FIXTURE_AFG_POLICY_GENERATION = 1

_NULL_ENVELOPE_REF_BLOCK = textwrap.dedent("""\
    hard_safety_envelope:
      envelope_id: TBD
      generation: null
      canonical_digest: TBD
    runtime_safety_profile:
      profile_id: TBD
      generation: null
      canonical_digest: TBD
    """)

_ARE_AUTHORITY_BLOCK = textwrap.dedent("""\
    authority:
      policy_active: false
      grants_risk_allocation: false
      creates_capacity: false
      releases_capacity: false
      creates_live_authorization: false
      creates_protective_classification: false
      creates_transmission_capability: false
      permits_broker_transmission: false
      clears_halt: false
      permits_rearm: false
      permits_automatic_rearm: false
    evidence:
      activation_record_id: TBD
      independent_review_id: TBD
      evidence_location: TBD
    """)

_ARE_TEMPLATE_TAIL = textwrap.dedent("""\
    risk_dimensions: []
    scope_aggregation_rules: []
    valuation_and_uncertainty_rules: []
    scenario_set_requirements: []
    netting_hedge_and_correlation_rules: []
    margin_collateral_and_liquidity_rules: []
    numerical_safety_rules: []
    dependency_closure_rules: []
    materiality_default: MATERIAL
    unknown_disposition: DENY_NEW_RISK
    compatibility_requirements: []
    invalidation_conditions: []
    approved_by: []
    """)

_AFG_AUTHORITY_BLOCK = textwrap.dedent("""\
    authority:
      policy_active: false
      grants_action_flow_allocation: false
      creates_or_refills_capacity: false
      releases_capacity: false
      creates_live_authorization: false
      creates_protective_classification: false
      creates_transmission_capability: false
      permits_broker_transmission: false
      clears_halt: false
      permits_rearm: false
      permits_automatic_rearm: false
    evidence:
      activation_record_id: TBD
      independent_review_id: TBD
      evidence_location: TBD
    """)

_AFG_TEMPLATE_TAIL = textwrap.dedent("""\
    action_classes: []
    resource_dimensions_and_units: []
    scope_aggregation_and_shared_limit_rules: []
    rate_burst_queue_and_in_flight_limits: []
    cause_amplification_limits: []
    retry_reconnect_replay_and_redelivery_rules: []
    protective_flow_reservations: []
    trustworthy_time_and_refill_rules: []
    atomic_risk_and_flow_commitment_rules: []
    materiality_default: MATERIAL
    unknown_disposition: DENY_NEW_NORMAL_RISK
    invalidation_and_containment_rules: []
    recovery_and_non_revival_rules: []
    compatibility_requirements: []
    approved_by: []
    """)


def aggregate_risk_policy_yaml(
    *,
    policy_id: str = FIXTURE_ARE_POLICY_ID,
    policy_generation: int = FIXTURE_ARE_POLICY_GENERATION,
    model_view_generation: int | None = None,
    status: str = "ISSUED",
    canonical_digest: str = "TBD",
    instrument_scope: str = '["K200F"]',
    account_scope: str = '["acct-1"]',
    policy_version: str = "1.0.0",
    governed_dimensions: str = '["LONG_SHORT_DELTA_DIRECTIONAL"]',
    governed_scopes: str = '["INSTRUMENT"]',
    dimension_id: str = "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL",
    dimension_scope: str = "INSTRUMENT",
    dimension_dimension: str = "LONG_SHORT_DELTA_DIRECTIONAL",
    unit: str = "CONTRACTS",
    effective_limit_key: str | None = None,
    effective_limit_value: str = "1",
    required_scenario_kinds: str = '["ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ"]',
    required_scopes: str = '["INSTRUMENT"]',
    applicable_risk_scopes: str = '["INSTRUMENT"]',
) -> str:
    """The standard fixture ``aggregate_risk_policy.yaml`` INSTANCE document."""
    mv_generation = (
        policy_generation if model_view_generation is None else model_view_generation
    )
    limit_key = dimension_id if effective_limit_key is None else effective_limit_key
    head = textwrap.dedent(f"""\
        artifact_type: AGGREGATE_RISK_POLICY
        schema_version: "1.0-DRAFT"
        policy_id: "{policy_id}"
        policy_version: TBD
        aggregate_risk_generation: {policy_generation}
        canonical_digest: {canonical_digest}
        status: {status}
        environment_scope: []
        safety_cell_scope: []
        legal_portfolio_scope: []
        account_scope: {account_scope}
        strategy_scope: []
        venue_scope: []
        instrument_scope: {instrument_scope}
        currency_scope: []
        global_scope_included: false
        """)
    model_view = textwrap.dedent(f"""\
        _model_view:
          policy_generation: {mv_generation}
          policy_version: "{policy_version}"
          governed_dimensions: {governed_dimensions}
          governed_scopes: {governed_scopes}
          signer_identity: null
          approval_identity: null
          evidence_package_ref: null
        _runtime:
          unit: "{unit}"
          dimension_ids:
            "{dimension_id}":
              scope: "{dimension_scope}"
              dimension: "{dimension_dimension}"
          effective_limits:
            "{limit_key}": {effective_limit_value}
          required_scenario_kinds: {required_scenario_kinds}
          required_scopes: {required_scopes}
          applicable_risk_scopes: {applicable_risk_scopes}
        """)
    return (
        head
        + _NULL_ENVELOPE_REF_BLOCK
        + _ARE_TEMPLATE_TAIL
        + "effective_from: null\nreview_due: null\n"
        + _ARE_AUTHORITY_BLOCK
        + model_view
    )


def action_flow_policy_yaml(
    *,
    policy_id: str = FIXTURE_AFG_POLICY_ID,
    policy_generation: int = FIXTURE_AFG_POLICY_GENERATION,
    model_view_generation: int | None = None,
    status: str = "ISSUED",
    canonical_digest: str = "TBD",
    account_scope: str = '["acct-1"]',
    policy_version: str = "1.0.0",
    governed_dimensions: str = '["afg.ORDER"]',
    governed_scopes: str = '["ACCOUNT"]',
    governed_action_classes: str = '["NORMAL_NEW_RISK", "ORDINARY_REDUCE_OR_EXIT"]',
    bundle_member_kind: str = "ACTION_FLOW_POLICY",
    flow_dimension_id: str = "afg.ORDER",
    hard_limit: str = "1",
    runtime_limit: str = "1",
    envelope_max: str = "1",
    decision_effective_limit: str = "1",
    scope_independence_scope: str = "ACCOUNT",
    allocation_separated: str = "true",
    refill_separated: str = "true",
    broker_enforcement_separated: str = "true",
    credential_session_state_separated: str = "true",
    failure_domain_separated: str = "true",
    final_route_separated: str = "true",
    basis_is_local_counter_only: str = "false",
    basis_is_scheduler_priority_only: str = "false",
    covered_scopes: str = '["ACCOUNT"]',
    required_scopes: str = '["ACCOUNT"]',
    applicable_action_flow_scopes: str = '["ACCOUNT"]',
    action_class_map: str | None = None,
    concurrent_consumers_share_one_envelope: str = "false",
    envelope_reset_on_duplicate: str = "false",
    duplicate_event_created_new_allowance: str = "false",
) -> str:
    """The standard fixture ``action_flow_policy.yaml`` INSTANCE document."""
    mv_generation = (
        policy_generation if model_view_generation is None else model_view_generation
    )
    if action_class_map is None:
        action_class_map_block = (
            "  action_class_map:\n"
            '    NEW_LONG: "NORMAL_NEW_RISK"\n'
            '    NEW_SHORT: "NORMAL_NEW_RISK"\n'
            '    DECREASE: "ORDINARY_REDUCE_OR_EXIT"\n'
            '    CLOSE: "ORDINARY_REDUCE_OR_EXIT"\n'
            '    REDUCE_ONLY: "ORDINARY_REDUCE_OR_EXIT"\n'
        )
    else:
        action_class_map_block = f"  action_class_map: {action_class_map}\n"
    head = textwrap.dedent(f"""\
        artifact_type: ACTION_FLOW_POLICY
        schema_version: "1.0-DRAFT"
        policy_id: "{policy_id}"
        policy_version: TBD
        action_flow_generation: {policy_generation}
        canonical_digest: {canonical_digest}
        status: {status}
        environment_scope: []
        safety_cell_scope: []
        broker_scope: []
        legal_portfolio_scope: []
        account_scope: {account_scope}
        credential_session_route_and_endpoint_scope: []
        venue_and_instrument_scope: []
        strategy_intent_and_cause_scope: []
        global_scope_included: false
        """)
    model_view = textwrap.dedent(f"""\
        _model_view:
          policy_generation: {mv_generation}
          policy_version: "{policy_version}"
          governed_dimensions: {governed_dimensions}
          governed_scopes: {governed_scopes}
          governed_action_classes: {governed_action_classes}
          bundle_member_kind: "{bundle_member_kind}"
          signer_identity: null
          approval_identity: null
          evidence_package_ref: null
        """)
    runtime_head = textwrap.dedent(f"""\
        _runtime:
          flow_dimension_id: "{flow_dimension_id}"
          limits:
            hard_limit: {hard_limit}
            runtime_limit: {runtime_limit}
            envelope_max: {envelope_max}
            decision_effective_limit: {decision_effective_limit}
          scope_independence:
            scope: "{scope_independence_scope}"
            allocation_separated: {allocation_separated}
            refill_separated: {refill_separated}
            broker_enforcement_separated: {broker_enforcement_separated}
            credential_session_state_separated: {credential_session_state_separated}
            failure_domain_separated: {failure_domain_separated}
            final_route_separated: {final_route_separated}
            basis_is_local_counter_only: {basis_is_local_counter_only}
            basis_is_scheduler_priority_only: {basis_is_scheduler_priority_only}
          covered_scopes: {covered_scopes}
          required_scopes: {required_scopes}
          applicable_action_flow_scopes: {applicable_action_flow_scopes}
        """)
    deployment_facts_block = (
        "  deployment_facts:\n"
        f"    concurrent_consumers_share_one_envelope: {concurrent_consumers_share_one_envelope}\n"
        f"    envelope_reset_on_duplicate: {envelope_reset_on_duplicate}\n"
        f"    duplicate_event_created_new_allowance: {duplicate_event_created_new_allowance}\n"
    )
    return (
        head
        + _NULL_ENVELOPE_REF_BLOCK
        + _AFG_TEMPLATE_TAIL
        + "effective_from: null\nreview_due: null\n"
        + _AFG_AUTHORITY_BLOCK
        + model_view
        + runtime_head
        + action_class_map_block
        + deployment_facts_block
    )


def write_fixture_aggregate_risk_policy(
    tmp_path: Path, text: str | None = None
) -> Path:
    path = tmp_path / "aggregate_risk_policy.yaml"
    path.write_text(
        aggregate_risk_policy_yaml() if text is None else text, encoding="utf-8"
    )
    return path


def write_fixture_action_flow_policy(tmp_path: Path, text: str | None = None) -> Path:
    path = tmp_path / "action_flow_policy.yaml"
    path.write_text(
        action_flow_policy_yaml() if text is None else text, encoding="utf-8"
    )
    return path
