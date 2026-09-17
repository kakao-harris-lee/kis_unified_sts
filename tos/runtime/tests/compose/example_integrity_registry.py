"""The registry :mod:`tests.compose.test_shipped_example_integrity` sweeps over —
every ``tos/runtime/config/*.example.yaml`` this repo ships, the key paths its real reader(s)
require to be EXPLICITLY present (value ``null`` is fine — key absence is not), and the set of
``tos_runtime`` source files independently confirmed to reference its deployed filename literal.

**How this was built (2026-09-18, A-0b, docs/plans/2026-09-18-tos-config-adoption-and-carryover-
plan.md §0.1.4 / §4 W-A row A-0b):** every config listed here was checked by actually calling its
real reader function(s) against the shipped example (not by reading the example's OWN keys and
calling that "the schema" — that would be circular, since the one confirmed defect
(``safety_activation``) is precisely an example that is missing a key its own text never hints
at). ``EXAMPLE_TOUCHPOINTS`` was built by grepping ``tos_runtime`` for each config's exact
deployed-filename literal and manually classifying every hit as either (a) a wiring call site
that resolves the path and forwards to an already-covered canonical loader, or (b) a genuinely
independent schema reader — every (b) is reflected in ``EXAMPLE_REQUIRED_PATHS``.

Two configs turned out to have MORE THAN ONE independent reader (the shape of bug this whole
module exists to catch):

* ``safety_activation`` — ``tos_runtime.safety.profile._load_documents`` (``activation:`` block +
  ``not_expired:``) AND ``tos_runtime.venue.activation.load_activation_members`` (``members:``,
  a SEPARATE top-level key that document does not otherwise use). The shipped example satisfied
  only the first before this wave — the confirmed A-0b defect.
* ``risk`` — ``tos_runtime.risk.aggregate.load_adverse_scenario_set``/
  ``load_required_scenario_kinds`` (the ``AdverseScenarioSet`` fields) AND
  ``tos_runtime.compose._currentness_wiring._load_action_flow_envelope`` (the
  ``ActionAmplificationEnvelope`` ``max_*`` axes — that function's own docstring: "``risk.yaml``
  block ... constructed directly by the composition root"). Both were already satisfied.

Every other config in this registry was confirmed to have exactly ONE real structural reader.

Two loaders that exist and were checked (``tos_runtime.evidence.retention.RetentionPolicy.load``,
``tos_runtime.recon.witness_kis_config.load_kis_witness_config``) are NOT yet reachable from any
``tos_runtime.compose`` wiring path at all (grep confirms zero call sites in
``tos_runtime/compose``) — neither loader's own module even spells its deployed filename as a
literal (each takes an arbitrary ``Path`` from its caller; no wiring module has picked a fixed
name for either yet), so their ``EXAMPLE_TOUCHPOINTS`` entry is the empty set, not a stand-in for
"one known reader". There is no cross-schema risk to guard against until a second reader appears,
at which point ``touchpoint_files`` (a plain grep) starts finding BOTH readers as soon as some
future wiring module gives the file a fixed literal name — the same instant this drift guard
would go red and demand an ``EXAMPLE_REQUIRED_PATHS`` entry.
"""

from __future__ import annotations

from tos_runtime.authority.epoch import load_authority_config
from tos_runtime.backtest.config import load_backtest_calibration_config
from tos_runtime.brokercap.scopes import load_broker_scopes
from tos_runtime.calendar.config import load_calendar_config
from tos_runtime.compose._construction_config import load_construction_config
from tos_runtime.compose._egress_coordinates import load_egress_coordinates
from tos_runtime.compose._engine_config import load_engine_config
from tos_runtime.compose._engine_wiring import load_engine_driver_config
from tos_runtime.compose._marketfeed_wiring import load_marketfeed_config
from tos_runtime.compose._pending_dimensions import (
    load_pending_currentness_dimensions,
)
from tos_runtime.compose._preconditions import load_coordinator_preconditions_config
from tos_runtime.compose._risk_attestations import load_risk_attestations
from tos_runtime.currentness.config import load_currentness_config
from tos_runtime.custody.file_custody import CustodyManifest
from tos_runtime.marketfeed.policy import load_critical_input_policy
from tos_runtime.nontrade.config import load_required_legs_config
from tos_runtime.posttrade.config import load_finality_config
from tos_runtime.recon.witness_kis_config import load_kis_witness_config
from tos_runtime.release.config import load_release_config
from tos_runtime.safety.deviation import _load_deviations
from tos_runtime.safety.incident import _load_incidents
from tos_runtime.safety.monitoring import _load_coverage
from tos_runtime.time.config import load_time_config
from tos_runtime.transport.kis_mock.config import load_kis_mock_transport_config
from tos_runtime.transport.kis_quote.config import load_kis_quote_transport_config

from .example_integrity import KeyPath, LoaderSpec

# ---------------------------------------------------------------------------
# Required key paths — a copy of the shipped example missing any of these
# would refuse to boot for a STRUCTURAL reason, not a named-TBD value.
# ---------------------------------------------------------------------------

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
    "currentness_dimensions": [
        (dim, field)
        for dim in ("CONTEXT", "CRITICAL_INPUT", "EGRESS_IDENTITY")
        for field in (
            "bound_generation",
            "bound_digest",
            "restrictive_floor",
            "positively_established",
        )
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
        ("min_send_interval_ms",),
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
        ("snapshot_age_bound",),
        ("interval_width",),
    ],
    "monitor_coverage": [
        ("coverage",),
        ("coverage", "manifest"),
        ("coverage", "manifest", "coverage_manifest_id"),
        ("coverage", "manifest", "coverage_generation"),
        ("coverage", "manifest", "coverage_manifest_digest"),
        ("coverage", "manifest", "policy_digest"),
        ("coverage", "manifest", "is_complete"),
        ("coverage", "items"),
        *[
            ("coverage", "items", item, field)
            for item in (
                "evidence-tip-currency",
                "time-service-health",
                "inbox-backlog",
            )
            for field in (
                "restrictive_response_present",
                "alert_path_present",
                "evidence_path_present",
                "currentness_rule_present",
                "closure_1_to_12_complete",
                "criticality",
            )
        ],
        ("coverage", "bounds"),
        ("coverage", "bounds", "max_evidence_tip_stall_ms"),
        ("coverage", "bounds", "healthy_time_states"),
        ("coverage", "bounds", "max_inbox_unconsumed"),
    ],
    "nontrade": [
        ("required_legs_by_class",),
        ("required_legs_by_class", "CORPORATE_ACTION"),
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
        # tos_runtime.risk.aggregate.load_adverse_scenario_set /
        # load_required_scenario_kinds (AdverseScenarioSet).
        ("scenario_set_id",),
        ("scenario_set_generation",),
        ("policy_binding_id",),
        ("covered_scenario_kinds",),
        ("required_scenario_kinds",),
        ("evidence_package_ref",),
        # tos_runtime.compose._currentness_wiring._load_action_flow_envelope
        # (ActionAmplificationEnvelope) — the SECOND independent reader of
        # this same file (module docstring: "tos_runtime.risk has no
        # dedicated loader for this").
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
    "safety_activation": [
        # tos_runtime.safety.profile._load_documents.
        ("activation",),
        ("activation", "activation_id"),
        ("activation", "profile_generation"),
        ("activation", "envelope_digest"),
        ("activation", "profile_digest"),
        ("activation", "bundle_digest"),
        ("activation", "scope"),
        ("activation", "approval_ids"),
        ("activation", "compatibility_attestation_refs"),
        ("activation", "predecessor_generation"),
        ("activation", "restrictive_generation_effects"),
        ("not_expired",),
        # tos_runtime.venue.activation.load_activation_members — the SECOND
        # independent reader of this same file (the A-0b defect: this key
        # was entirely missing from the shipped example).
        ("members",),
    ],
    "safety_deviations": [
        ("deviations",),
        ("deviations", "active_set"),
        ("deviations", "active_set", "active_set_id"),
        ("deviations", "active_set", "active_set_generation"),
        ("deviations", "active_set", "deviation_generation"),
        ("deviations", "active_set", "is_complete"),
        ("deviations", "active_set", "combined_within_envelope"),
        ("deviations", "applicable_decision_ids"),
        ("deviations", "members"),
    ],
    "safety_envelope": [
        ("envelope",),
        ("envelope", "envelope_id"),
        ("envelope", "envelope_generation"),
        ("envelope", "envelope_version"),
        ("envelope", "governed_dimensions"),
        ("envelope", "permitted_scope"),
        ("envelope", "prohibited_fallbacks"),
        ("envelope", "residual_risk_ceiling"),
        ("envelope", "evidence_package_ref"),
    ],
    "safety_incidents": [
        ("incidents",),
        ("incidents", "active_set"),
        ("incidents", "active_set", "active_set_id"),
        ("incidents", "active_set", "active_set_generation"),
        ("incidents", "active_set", "incident_generation"),
        ("incidents", "active_set", "safety_cell"),
        ("incidents", "active_set", "shared_dependencies"),
        ("incidents", "active_set", "is_complete"),
        ("incidents", "active_set", "is_current"),
        ("incidents", "applicable_incident_ids"),
        ("incidents", "members"),
    ],
    "safety_profile": [
        ("profile",),
        ("profile", "profile_id"),
        ("profile", "profile_generation"),
        ("profile", "profile_version"),
        ("profile", "target_envelope_id"),
        ("profile", "target_envelope_generation"),
        ("profile", "governed_dimensions"),
        ("profile", "scope"),
        ("profile", "permitted_behaviors"),
        ("profile", "fallback_rules"),
        ("profile", "evidence_package_ref"),
    ],
    "strategy_bindings": [
        # `strategies` keys are strategy-file stems (operator-defined, not a
        # fixed set) — only the container key itself is a fixed structural
        # requirement; `tos_runtime.strategy.resolve`'s own five refusal
        # rules (this file's own module docstring) govern per-entry shape.
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
        ("tz_db_version",),
        ("trading_calendar_version",),
        ("verification_profile_version",),
        ("safety_profile_version",),
    ],
}

# ---------------------------------------------------------------------------
# Touch-point drift guard — the LIVE set of tos_runtime source files that
# reference each config's exact deployed-filename literal (f'"{stem}.yaml"'),
# as last confirmed by hand (2026-09-18, A-0b). A file appearing or
# disappearing from this set fails test_touchpoints_have_not_drifted loudly
# rather than silently — see example_integrity.assert_touchpoints_match.
# ---------------------------------------------------------------------------

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
    "currentness_dimensions": frozenset(
        {
            "tos_runtime/compose/_currentness_wiring.py",
            "tos_runtime/compose/_wiring.py",
        }
    ),
    "custody.manifest": frozenset({"tos_runtime/custody/file_custody.py"}),
    "egress_coordinates": frozenset(
        {"tos_runtime/compose/_boot_integrity.py", "tos_runtime/compose/_wiring.py"}
    ),
    "engine": frozenset({"tos_runtime/compose/_finalize_wiring.py"}),
    "engine_driver": frozenset({"tos_runtime/compose/_engine_wiring.py"}),
    # Not yet reachable from any tos_runtime.compose wiring path, and the
    # defining module (tos_runtime/evidence/retention.py) itself never spells
    # the literal "evidence_retention.yaml" either — RetentionPolicy.load
    # takes an arbitrary Path from its caller, no fixed filename picked yet
    # (module docstring above) — so the live grep is genuinely empty today.
    "evidence_retention": frozenset(),
    "finality": frozenset(
        {
            "tos_runtime/compose/_finalize_wiring.py",
            "tos_runtime/compose/_release_wiring.py",
        }
    ),
    "kis_mock_transport": frozenset({"tos_runtime/compose/_transport_wiring.py"}),
    "kis_quote": frozenset({"tos_runtime/compose/_marketfeed_wiring.py"}),
    # See the "evidence_retention" comment above — same situation:
    # load_kis_witness_config takes an arbitrary Path, no wiring module has
    # picked a fixed "kis_witness.yaml" filename yet, live grep is empty.
    "kis_witness": frozenset(),
    "marketfeed": frozenset({"tos_runtime/compose/_marketfeed_wiring.py"}),
    "monitor_coverage": frozenset({"tos_runtime/compose/_safety_wiring.py"}),
    "nontrade": frozenset({"tos_runtime/nontrade/config.py"}),
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
    "safety_activation": frozenset(
        {
            "tos_runtime/compose/_riskstate_wiring.py",
            "tos_runtime/compose/_safety_wiring.py",
            "tos_runtime/compose/_venue_wiring.py",
        }
    ),
    "safety_deviations": frozenset({"tos_runtime/compose/_safety_wiring.py"}),
    "safety_envelope": frozenset({"tos_runtime/compose/_safety_wiring.py"}),
    "safety_incidents": frozenset({"tos_runtime/compose/_safety_wiring.py"}),
    "safety_profile": frozenset({"tos_runtime/compose/_safety_wiring.py"}),
    "strategy_bindings": frozenset(
        {
            "tos_runtime/strategy/bindings.py",
            "tos_runtime/strategy/resolve.py",
        }
    ),
    "time": frozenset(
        {
            "tos_runtime/compose/_types.py",
            "tos_runtime/compose/_wiring.py",
            "tos_runtime/compose/cli.py",
            "tos_runtime/compose/root.py",
        }
    ),
}

# ---------------------------------------------------------------------------
# Single-argument loader call sites — absorbs (and generalizes across every
# config with exactly one straightforward ``load_x(path)`` reader) the intent
# of the three narrow ``test_shipped_example_file_is_all_null_and_therefore_
# refuses`` tests this wave supersedes (``compose/test_construction_config.py``,
# ``compose/test_marketfeed_intake_kind_wiring.py``,
# ``transport/kis_quote/test_config.py``): every shipped example here is
# confirmed to STILL refuse to load, on top of (never instead of) the
# structural ``EXAMPLE_REQUIRED_PATHS`` check above — a template that started
# passing outright would mean a real, filled-in value leaked into a file that
# is supposed to ship all-``null``, a different bug this same sweep also
# wants to catch.
#
# Readers needing extra construction context beyond ``path`` (an
# ``environment_label``, a sibling INSTANCE document's REST bases, a
# ``CanonicalizationScheme``) are given plausible dummy values here — those
# extra args are never sourced from the example file itself, and every one of
# these loaders is confirmed (by reading its source) to validate the
# example's own null leaves BEFORE it ever touches them. Configs with a
# multi-reader schema (``safety_activation``, ``risk``), a multi-path
# constructor (``safety_envelope``/``safety_profile``/``safety_activation``
# via ``tos_runtime.safety.profile._load_documents``), or a strictly-optional
# file (``strategy_bindings``) get their own targeted test instead — see
# ``test_shipped_example_integrity.py``.
EXAMPLE_LOADERS: dict[str, LoaderSpec] = {
    "authority": (load_authority_config, {}),
    "backtest_calibration": (load_backtest_calibration_config, {}),
    "broker_scopes": (load_broker_scopes, {"environment_label": "BROKER_SIMULATION"}),
    "calendar": (load_calendar_config, {}),
    "construction": (load_construction_config, {}),
    "coordinator_preconditions": (load_coordinator_preconditions_config, {}),
    "critical_input_policy": (
        load_critical_input_policy,
        # scheme.compute_digest is only reached AFTER every raw leaf is
        # validated (tos_runtime.marketfeed.policy.load_critical_input_policy
        # source) — None never gets called on this all-null example.
        {"scheme": None},
    ),
    "currentness": (load_currentness_config, {}),
    "currentness_dimensions": (load_pending_currentness_dimensions, {}),
    "egress_coordinates": (
        load_egress_coordinates,
        {"environment_label": "BROKER_SIMULATION"},
    ),
    "engine": (load_engine_config, {}),
    "engine_driver": (load_engine_driver_config, {}),
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
    "nontrade": (load_required_legs_config, {}),
    "release": (load_release_config, {}),
    "risk_attestations": (load_risk_attestations, {}),
    "safety_deviations": (_load_deviations, {}),
    "safety_incidents": (_load_incidents, {}),
    "time": (load_time_config, {}),
}

#: ``custody.manifest.example.yaml`` is the one shipped example confirmed to
#: LOAD SUCCESSFULLY as-is (``tos_runtime.custody.file_custody.CustodyManifest
#: .load`` — every leaf ``load`` actually requires already carries a concrete
#: illustrative value; only the optional ``expected_sha256`` pins are
#: ``null``) — deliberately excluded from ``EXAMPLE_LOADERS`` (which asserts
#: "still refuses"); its own dedicated test asserts the opposite.
CUSTODY_MANIFEST_LOADER: LoaderSpec = (CustodyManifest.load, {})
