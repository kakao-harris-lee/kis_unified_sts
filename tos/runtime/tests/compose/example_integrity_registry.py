"""The registry :mod:`tests.compose.test_shipped_example_integrity` sweeps over —"""

from __future__ import annotations

from collections.abc import Callable

from tos_runtime.authority.epoch import load_authority_config
from tos_runtime.backtest.config import load_backtest_calibration_config
from tos_runtime.brokercap.scopes import load_broker_scopes
from tos_runtime.calendar.config import load_calendar_config
from tos_runtime.compose._construction_config import load_construction_config
from tos_runtime.compose._egress_coordinates import load_egress_coordinates
from tos_runtime.compose._engine_config import load_engine_config
from tos_runtime.compose._engine_wiring import load_engine_driver_config
from tos_runtime.compose._marketfeed_wiring import load_marketfeed_config
from tos_runtime.compose._preconditions import load_coordinator_preconditions_config
from tos_runtime.compose._risk_attestations import load_risk_attestations
from tos_runtime.currentness.config import load_currentness_config
from tos_runtime.custody.file_custody import CustodyManifest
from tos_runtime.evidence.retention import RetentionPolicy
from tos_runtime.marketfeed.policy import load_critical_input_policy
from tos_runtime.operations.cold_backup import load_cold_backup_config
from tos_runtime.posttrade.config import load_finality_config
from tos_runtime.recon.witness_kis_config import load_kis_witness_config
from tos_runtime.release.config import load_release_config
from tos_runtime.safety.monitoring import _load_coverage
from tos_runtime.strategy.bindings import load_strategy_bindings
from tos_runtime.time.config import load_time_config
from tos_runtime.transport.kis_mock.config import load_kis_mock_transport_config
from tos_runtime.transport.kis_quote.config import load_kis_quote_transport_config

from .example_integrity import (
    KeyPath,
    LoaderSpec,
    assert_risk_refuses_on_both_readers,
)

EXAMPLE_REQUIRED_PATHS: dict[str, list[KeyPath]] = {
    "authority": [
        ("containment_bound_ms",),
        ("trading_approval_policy_generation",),
    ],
    "backtest_calibration": [
        ("max_price_bps",),
        ("max_fill_ratio_shortfall",),
        ("max_latency_bars",),
        ("min_observations",),
    ],
    "broker_scopes": [
        ("instance_path",),
        ("active_scope",),
        ("environment_binding",),
        ("environment_binding", "SYNTHETIC"),
        ("environment_binding", "BROKER_SIMULATION"),
        ("environment_binding", "BROKER_PRODUCTION"),
        ("asset_binding",),
        ("asset_binding", "STOCK"),
        ("asset_binding", "FUTURES"),
        ("scopes",),
    ],
    "calendar": [
        ("calendar_version",),
        ("tz_id",),
        ("holidays",),
        ("sessions",),
        ("closed_phase",),
        ("futures_expiry",),
    ],
    "construction": [
        ("account",),
        ("instrument",),
        ("action_class",),
        ("instrument_class",),
        ("outbound_side",),
        ("price_field_key",),
        ("shape_price_field_key",),
    ],
    "coordinator_preconditions": [
        ("live_authorization_state",),
        ("nonlive_broker_consuming",),
        ("nonlive_broker_consuming", "admitted"),
    ],
    "critical_input_policy": [
        ("policy_id",),
        ("policy_version",),
        ("policy_generation",),
        ("issuer_principal_id",),
        ("environment",),
        ("decision_class",),
        ("intended_use",),
        ("fields",),
    ],
    "currentness": [
        ("B_capability_claim_to_send",),
        ("required_dimensions",),
    ],
    "custody.manifest": [
        ("environment_label",),
        ("scopes",),
        ("scopes", "read.principal"),
        ("scopes", "evidence.key"),
        ("scopes", "replay.params"),
        ("scopes", "kis_mock.app_key"),
        ("scopes", "kis_mock.app_secret"),
    ],
    "egress_coordinates": [
        (field, "value")
        for field in (
            "endpoint",
            "action",
            "method",
            "route_identity",
            "credential_generation",
            "broker_session_generation",
            "egress_generation",
            "active_principal",
            "capsule_terminus_fields",
        )
    ],
    "engine": [
        ("dsl_evaluation_budget_steps",),
        ("max_unresolved_send_per_scope",),
    ],
    "engine_driver": [
        ("replay_window_events",),
    ],
    "evidence_cold_backup": [
        ("backup_root",),
        ("archive_dir",),
        ("verify_root",),
        ("minimum_free_bytes",),
    ],
    "evidence_retention": [
        ("minimum_days_by_class",),
        ("minimum_days_by_class", "TOMBSTONE"),
        ("minimum_days_by_class", "RESTORE_COMPARISON"),
        ("minimum_days_by_class", "KEY_ROTATION"),
    ],
    "finality": [
        ("currency",),
        ("value_date",),
        ("source_revision",),
        ("proof_recipe_id",),
        ("release_proof_wait_ms",),
    ],
    "kis_mock_transport": [
        ("mode",),
        ("endpoint_rest_base",),
        ("order_path",),
        ("token_path",),
        ("tr_id_buy",),
        ("tr_id_sell",),
        ("field_map",),
        ("field_map", "account"),
        ("field_map", "instrument"),
        ("field_map", "quantity"),
        ("field_map", "price"),
        ("static_body_fields",),
        ("static_body_fields", "ACNT_PRDT_CD"),
        ("static_body_fields", "ORD_DVSN"),
        ("static_body_fields", "EXCG_ID_DVSN_CD"),
        ("static_body_fields", "SLL_TYPE"),
        ("static_body_fields", "CNDT_PRIC"),
        ("price_scale",),
        ("min_send_interval_ms",),
        ("app_key_request_wait_budget_ms",),
        ("token_reissue_min_interval_s",),
        ("request_timeout_s",),
        ("allow_plaintext_for_tests",),
    ],
    "kis_quote": [
        ("endpoint_rest_base",),
        ("allow_plaintext_for_tests",),
        ("quote_path",),
        ("tr_id",),
        ("market_div_code",),
        ("instrument",),
        ("token_path",),
        ("token_reissue_min_interval_s",),
        ("field_mapping",),
        ("source_id",),
        ("request_timeout_s",),
        ("app_key_min_request_interval_ms",),
        ("app_key_request_wait_budget_ms",),
    ],
    "kis_witness": [
        ("endpoint_rest_base",),
        ("balance_path",),
        ("balance_tr_id",),
        ("order_inquiry_path",),
        ("order_inquiry_tr_id",),
        ("request_timeout_s",),
        ("max_pages",),
        ("allow_plaintext_for_tests",),
    ],
    "marketfeed": [
        ("instruments",),
        ("instrument_class",),
        ("account",),
        ("direction",),
        ("quantity_basis",),
        ("unit",),
        ("intake_kind",),
        ("journal_path",),
        ("poll_interval_ms",),
        ("journal_pass_allowance_ms",),
        ("time_evaluate_closed_interval_ms",),
        ("snapshot_age_bound",),
        ("interval_width",),
    ],
    "monitor_coverage": [
        ("coverage",),
        ("coverage", "coverage_generation"),
        ("coverage", "bounds"),
        ("coverage", "bounds", "max_evidence_tip_stall_ms"),
        ("coverage", "bounds", "max_inbox_unconsumed"),
    ],
    "release": [
        ("expected_code_digest",),
        ("expected_dependency_set_digest",),
        ("admission_result",),
        ("restriction_state_resolved",),
        ("restriction_present",),
        ("restriction",),
        ("restriction", "restriction_id"),
        ("restriction", "restriction_generation"),
        ("restriction", "trigger_class"),
    ],
    "risk": [
        ("scenario_set_id",),
        ("scenario_set_generation",),
        ("policy_binding_id",),
        ("covered_scenario_kinds",),
        ("required_scenario_kinds",),
        ("evidence_package_ref",),
        ("max_fan_out",),
        ("max_depth",),
        ("max_attempts",),
        ("max_mutations",),
        ("max_queries",),
        ("max_queue_depth",),
        ("max_in_flight",),
        ("max_elapsed_monotonic",),
        ("max_duplicate_redelivery_expansion",),
        ("max_failover_reconnect_replay_expansion",),
        ("max_amplification_per_cause",),
    ],
    "risk_attestations": [
        (field, "attested")
        for field in (
            "numerically_safe",
            "valuation_ok",
            "all_fields_attributed",
            "limit_source_is_injected_envelope",
            "economic_commitment_exclusive",
            "flow_commitment_exclusive",
        )
    ],
    "strategy_bindings": [
        ("strategies",),
    ],
    "time": [
        ("MAX_time_source_precision_ms",),
        ("MAX_time_transport_and_queue_uncertainty_ms",),
        ("MAX_time_conservative_freshness_age_ms",),
        ("MAX_future_timestamp_tolerance_ms",),
        ("MAX_process_suspension_ms",),
        ("MAX_time_source_disagreement_ms",),
        ("MIN_time_independent_reference_count",),
        ("MAX_clock_domain_conversion_uncertainty_ms",),
        ("MAX_send_result_wait_ms",),
        ("MAX_critical_input_consumer_receipt_age_ms",),
        ("MAX_time_source_sequence_gap_ms",),
        ("time_health_snapshot_heartbeat_ms",),
        ("tz_db_version",),
        ("trading_calendar_version",),
        ("verification_profile_version",),
        ("safety_profile_version",),
    ],
}


EXAMPLE_TOUCHPOINTS: dict[str, frozenset[str]] = {
    "authority": frozenset(
        {
            "tos_runtime/compose/_types.py",
            "tos_runtime/compose/_wiring.py",
            "tos_runtime/compose/root.py",
        }
    ),
    "backtest_calibration": frozenset({"tos_runtime/backtest/config.py"}),
    "broker_scopes": frozenset(
        {"tos_runtime/compose/_boot_integrity.py", "tos_runtime/compose/_wiring.py"}
    ),
    "calendar": frozenset({"tos_runtime/compose/_session_wiring.py"}),
    "construction": frozenset({"tos_runtime/compose/_construction_config.py"}),
    "coordinator_preconditions": frozenset({"tos_runtime/compose/_preconditions.py"}),
    "critical_input_policy": frozenset({"tos_runtime/marketfeed/policy.py"}),
    "currentness": frozenset(
        {
            "tos_runtime/compose/_currentness_wiring.py",
            "tos_runtime/compose/_types.py",
            "tos_runtime/compose/_wiring.py",
            "tos_runtime/compose/root.py",
        }
    ),
    "custody.manifest": frozenset({"tos_runtime/custody/file_custody.py"}),
    "egress_coordinates": frozenset(
        {"tos_runtime/compose/_boot_integrity.py", "tos_runtime/compose/_wiring.py"}
    ),
    "engine": frozenset({"tos_runtime/compose/_finalize_wiring.py"}),
    "engine_driver": frozenset({"tos_runtime/compose/_engine_wiring.py"}),
    "evidence_cold_backup": frozenset({"tos_runtime/operations/cold_backup.py"}),
    "evidence_retention": frozenset(),
    "finality": frozenset(
        {
            "tos_runtime/compose/_finalize_wiring.py",
            "tos_runtime/compose/_release_wiring.py",
            "tos_runtime/compose/_venue_ledger_wiring.py",
        }
    ),
    "kis_mock_transport": frozenset({"tos_runtime/compose/_transport_wiring.py"}),
    "kis_quote": frozenset({"tos_runtime/compose/_marketfeed_wiring.py"}),
    "kis_witness": frozenset(),
    "marketfeed": frozenset({"tos_runtime/compose/_marketfeed_wiring.py"}),
    "monitor_coverage": frozenset({"tos_runtime/compose/_monitor_wiring.py"}),
    "release": frozenset(
        {
            "tos_runtime/compose/_types.py",
            "tos_runtime/compose/_wiring.py",
            "tos_runtime/compose/root.py",
        }
    ),
    "risk": frozenset(
        {
            "tos_runtime/compose/_currentness_wiring.py",
            "tos_runtime/compose/_types.py",
            "tos_runtime/compose/_wiring.py",
            "tos_runtime/compose/root.py",
        }
    ),
    "risk_attestations": frozenset(
        {
            "tos_runtime/compose/_boot_integrity.py",
            "tos_runtime/compose/_currentness_wiring.py",
        }
    ),
    "strategy_bindings": frozenset({"tos_runtime/strategy/bindings.py"}),
    "time": frozenset(
        {
            "tos_runtime/compose/_types.py",
            "tos_runtime/compose/_wiring.py",
            "tos_runtime/compose/cli.py",
            "tos_runtime/compose/root.py",
        }
    ),
}

EXAMPLE_LOADERS: dict[str, LoaderSpec] = {
    "authority": (load_authority_config, {}),
    "backtest_calibration": (load_backtest_calibration_config, {}),
    "broker_scopes": (load_broker_scopes, {"environment_label": "BROKER_SIMULATION"}),
    "calendar": (load_calendar_config, {}),
    "construction": (load_construction_config, {}),
    "coordinator_preconditions": (load_coordinator_preconditions_config, {}),
    "critical_input_policy": (
        load_critical_input_policy,
        {"scheme": None},
    ),
    "currentness": (load_currentness_config, {}),
    "egress_coordinates": (
        load_egress_coordinates,
        {"environment_label": "BROKER_SIMULATION"},
    ),
    "engine": (load_engine_config, {}),
    "engine_driver": (load_engine_driver_config, {}),
    "evidence_cold_backup": (load_cold_backup_config, {}),
    "finality": (load_finality_config, {}),
    "kis_mock_transport": (
        load_kis_mock_transport_config,
        {
            "instance_mock_rest_base": "https://mock.example",
            "instance_real_rest_base": "https://real.example",
        },
    ),
    "kis_quote": (
        load_kis_quote_transport_config,
        {
            "instance_mock_rest_base": "https://mock.example",
            "instance_real_rest_base": "https://real.example",
        },
    ),
    "kis_witness": (
        load_kis_witness_config,
        {
            "instance_mock_rest_base": "https://mock.example",
            "instance_real_rest_base": "https://real.example",
        },
    ),
    "marketfeed": (load_marketfeed_config, {}),
    "monitor_coverage": (_load_coverage, {}),
    "release": (load_release_config, {}),
    "risk_attestations": (load_risk_attestations, {}),
    "strategy_bindings": (load_strategy_bindings, {}),
    "time": (load_time_config, {}),
}

CUSTODY_MANIFEST_LOADER: LoaderSpec = (CustodyManifest.load, {})
EVIDENCE_RETENTION_LOADER: LoaderSpec = (RetentionPolicy.load, {})

LOADS_SUCCESSFULLY_LOADERS: dict[str, LoaderSpec] = {
    "custody.manifest": CUSTODY_MANIFEST_LOADER,
    "evidence_retention": EVIDENCE_RETENTION_LOADER,
}

EXAMPLE_TEMPLATE_ONLY: frozenset[str] = frozenset()

MULTI_READER_CHECKS: dict[str, Callable[[], None]] = {
    "risk": assert_risk_refuses_on_both_readers,
}
