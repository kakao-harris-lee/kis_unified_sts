"""tos/runtime/tests/compose — hermetic fixtures (D1.4: tmp_path only, no"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.cur import MANDATED_DIMENSION_FLOOR
from tos_runtime.operations.dependency_admission import (
    observe_dependency_set_digest,
    observe_source_tree_digest,
)

from ..riskstate._documents import action_flow_policy_yaml, aggregate_risk_policy_yaml
from ..venue._documents import ocp_yaml, venue_policy_yaml

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_VENUE_POLICY_ENVIRONMENT = "non-live-test"
_VENUE_POLICY_ACCOUNT = "88888888-01"
_VENUE_POLICY_INSTRUMENT = "ES"
_VENUE_POLICY_INSTRUMENT_CLASS = "krx-index-futures"
_VENUE_POLICY_ADMITTING_PHASE = "CONTINUOUS"

_BROKER_SCOPES_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "broker_scopes.example.yaml"
)

EXPECTED_CODE_DIGEST = observe_source_tree_digest()

EXPECTED_DEPENDENCY_SET_DIGEST = observe_dependency_set_digest()


def _write_yaml(path: Path, content: dict) -> None:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


def _chmod_600(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def call_wrapped_fixture(fixture_func: object, *args: object) -> Path:
    """Call the plain function a ``@pytest.fixture``-decorated callable wraps, bypassing"""
    result = fixture_func.__wrapped__(*args)  # type: ignore[attr-defined]
    assert isinstance(result, Path)
    return result


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "data"
    directory.mkdir()
    return directory


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "config"
    directory.mkdir()
    _write_yaml(
        directory / "time.yaml",
        {
            "MAX_time_source_precision_ms": 5,
            "MAX_time_transport_and_queue_uncertainty_ms": 50,
            "MAX_time_conservative_freshness_age_ms": 60_000,
            "MAX_future_timestamp_tolerance_ms": 1000,
            "MAX_process_suspension_ms": 5000,
            "MAX_time_source_disagreement_ms": 50,
            "MIN_time_independent_reference_count": 1,
            "MAX_clock_domain_conversion_uncertainty_ms": 50,
            "MAX_send_result_wait_ms": 5000,
            "MAX_critical_input_consumer_receipt_age_ms": 1000,
            "MAX_time_source_sequence_gap_ms": 50,
            "tz_db_version": "tzdb-compose-0",
            "trading_calendar_version": "cal-compose-0",
            "verification_profile_version": "ver-compose-0",
            "safety_profile_version": "safety-compose-0",
            "time_health_snapshot_heartbeat_ms": 60_000,
        },
    )
    _write_yaml(
        directory / "authority.yaml",
        {
            "containment_bound_ms": 60_000,
            "trading_approval_policy_generation": 1,
        },
    )
    _write_yaml(
        directory / "risk.yaml",
        {
            "scenario_set_id": "compose-scenario-set",
            "scenario_set_generation": 1,
            "policy_binding_id": "compose-risk-policy",
            "covered_scenario_kinds": ["ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ"],
            "required_scenario_kinds": ["ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ"],
            "evidence_package_ref": None,
            "max_fan_out": 10,
            "max_depth": 5,
            "max_attempts": 3,
            "max_mutations": 5,
            "max_queries": 10,
            "max_queue_depth": 10,
            "max_in_flight": 5,
            "max_elapsed_monotonic": 60_000,
            "max_duplicate_redelivery_expansion": 2,
            "max_failover_reconnect_replay_expansion": 2,
            "max_amplification_per_cause": 10,
        },
    )
    _write_yaml(
        directory / "currentness.yaml",
        {
            "B_capability_claim_to_send": 500,
            "required_dimensions": sorted(
                key.value for key in MANDATED_DIMENSION_FLOOR
            ),
        },
    )
    _write_yaml(
        directory / "calendar.yaml",
        {
            "calendar_version": "cal-compose-0",
            "tz_id": "Asia/Seoul",
            "holidays": [],
            "sessions": {
                "krx-index-futures": [
                    {
                        "phase": "CONTINUOUS",
                        "start": "00:00",
                        "end": "23:59:59.999999",
                        "days": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
                        "crosses_midnight": False,
                    }
                ]
            },
            "closed_phase": "CLOSED",
            "futures_expiry": {},
        },
    )
    (directory / "venue_constraint_policy.yaml").write_text(
        venue_policy_yaml(
            environment=_VENUE_POLICY_ENVIRONMENT,
            account=_VENUE_POLICY_ACCOUNT,
            instrument=_VENUE_POLICY_INSTRUMENT,
            instrument_class=_VENUE_POLICY_INSTRUMENT_CLASS,
            quantity_unit="CONTRACTS",
            currency="KRW",
            price_min="1000",
            price_max="9000000",
            tick_size="500",
            lot_size="2",
            min_quantity="2",
            max_quantity="100",
            admitting_phases=f'["{_VENUE_POLICY_ADMITTING_PHASE}"]',
            admitting_phases_short=f'["{_VENUE_POLICY_ADMITTING_PHASE}"]',
            action_classes='["NEW_LONG", "NEW_SHORT", "CLOSE"]',
            admitting_phases_close=f'["{_VENUE_POLICY_ADMITTING_PHASE}"]',
        ),
        encoding="utf-8",
    )
    (directory / "order_construction_policy.yaml").write_text(
        ocp_yaml(
            environment=_VENUE_POLICY_ENVIRONMENT,
            account=_VENUE_POLICY_ACCOUNT,
            instrument=_VENUE_POLICY_INSTRUMENT,
            wire_codec="null",
        ),
        encoding="utf-8",
    )
    _write_yaml(
        directory / "monitor_coverage.yaml",
        {
            "coverage": {
                "coverage_generation": 1,
                "bounds": {
                    "max_evidence_tip_stall_ms": 60_000,
                    "max_inbox_unconsumed": 100,
                },
            }
        },
    )
    _write_yaml(
        directory / "egress_coordinates.yaml",
        {
            "endpoint": {"value": "synthetic://paper/order"},
            "action": {"value": "NEW_ORDER"},
            "method": {"value": "SUBMIT"},
            "route_identity": {"value": "synthetic-route"},
            "credential_generation": {"value": 0},
            "broker_session_generation": {"value": 0},
            "egress_generation": {"value": 1},
            "active_principal": {"value": "egressgw-{environment_label}"},
            "capsule_terminus_fields": {"value": ["account", "instrument"]},
        },
    )
    broker_scopes_raw = yaml.safe_load(
        _BROKER_SCOPES_EXAMPLE_PATH.read_text(encoding="utf-8")
    )
    broker_scopes_raw["active_scope"] = "SYNTHETIC_FUTURES_ORDER"
    _write_yaml(directory / "broker_scopes.yaml", broker_scopes_raw)
    _write_yaml(
        directory / "risk_attestations.yaml",
        {
            "numerically_safe": {"attested": True},
            "valuation_ok": {"attested": True},
            "all_fields_attributed": {"attested": True},
            "limit_source_is_injected_envelope": {"attested": True},
            "economic_commitment_exclusive": {"attested": True},
            "flow_commitment_exclusive": {"attested": True},
        },
    )
    _write_yaml(
        directory / "engine.yaml",
        {
            "dsl_evaluation_budget_steps": 64,
            "max_unresolved_send_per_scope": 1,
        },
    )
    _write_yaml(
        directory / "engine_driver.yaml",
        {
            "replay_window_events": 1000,
        },
    )
    _write_yaml(
        directory / "coordinator_preconditions.yaml",
        {
            "live_authorization_state": "NOT_AUTHORIZED",
            "nonlive_broker_consuming": {"admitted": False},
        },
    )
    _write_yaml(
        directory / "finality.yaml",
        {
            "currency": "KRW",
            "value_date": "2026-09-09",
            "source_revision": "compose-e2e-rev-1",
            "proof_recipe_id": "compose-e2e-recipe-1",
            "release_proof_wait_ms": 3_600_000,
        },
    )
    _write_yaml(
        directory / "release.yaml",
        {
            "expected_code_digest": EXPECTED_CODE_DIGEST,
            "expected_dependency_set_digest": EXPECTED_DEPENDENCY_SET_DIGEST,
            "admission_result": "ADMIT",
            "restriction_state_resolved": True,
            "restriction_present": False,
            "restriction": {
                "restriction_id": None,
                "restriction_generation": None,
                "trigger_class": None,
            },
        },
    )
    return directory


@pytest.fixture()
def mismatched_release_config_dir(config_dir: Path) -> Path:
    """A copy of ``config_dir`` whose ``release.yaml`` carries a code digest"""
    _write_yaml(
        config_dir / "release.yaml",
        {
            "expected_code_digest": "deliberately-mismatched-digest",
            "expected_dependency_set_digest": EXPECTED_DEPENDENCY_SET_DIGEST,
            "admission_result": "ADMIT",
            "restriction_state_resolved": True,
            "restriction_present": False,
            "restriction": {
                "restriction_id": None,
                "restriction_generation": None,
                "trigger_class": None,
            },
        },
    )
    return config_dir


_RISK_STATE_DIMENSION_ID = "ACCOUNT::GROSS_NOTIONAL"
_RISK_STATE_ENVELOPE_MAX = "100000"


@pytest.fixture()
def config_dir_with_risk_state(config_dir: Path) -> Path:
    """``config_dir`` PLUS the two TOS risk state service wave governed policy instances"""
    are_path = config_dir / "aggregate_risk_policy.yaml"
    are_path.write_text(
        aggregate_risk_policy_yaml(
            instrument_scope=f'["{_VENUE_POLICY_INSTRUMENT}"]',
            account_scope=f'["{_VENUE_POLICY_ACCOUNT}"]',
            governed_dimensions='["GROSS_NOTIONAL"]',
            governed_scopes='["ACCOUNT"]',
            dimension_id=_RISK_STATE_DIMENSION_ID,
            dimension_scope="ACCOUNT",
            dimension_dimension="GROSS_NOTIONAL",
            unit="CONTRACTS",
            effective_limit_value=_RISK_STATE_ENVELOPE_MAX,
            required_scopes='["ACCOUNT"]',
            applicable_risk_scopes='["ACCOUNT"]',
        ),
        encoding="utf-8",
    )
    afg_path = config_dir / "action_flow_policy.yaml"
    afg_path.write_text(
        action_flow_policy_yaml(
            account_scope=f'["{_VENUE_POLICY_ACCOUNT}"]',
            hard_limit="100",
            runtime_limit="100",
            envelope_max="100",
            decision_effective_limit="100",
            concurrent_consumers_share_one_envelope="true",
        ),
        encoding="utf-8",
    )
    return config_dir


@pytest.fixture()
def custody_root(tmp_path: Path) -> Path:
    directory = tmp_path / "custody"
    directory.mkdir()
    uid = os.getuid()
    del uid

    _write_yaml(
        directory / "custody.manifest.yaml",
        {
            "environment_label": "non-live-test",
            "scopes": {
                "read.principal": {
                    "file": "read.principal",
                    "principal": "read-principal-compose",
                    "expected_sha256": None,
                },
                "evidence.key": {
                    "file": "evidence.key",
                    "principal": "evidence-key-compose",
                    "expected_sha256": None,
                },
                "replay.params": {
                    "file": "replay.params",
                    "principal": "replay-params-compose",
                    "expected_sha256": None,
                },
            },
        },
    )
    for name, content in (
        ("read.principal", b"compose-read-principal-secret"),
        ("evidence.key", b"compose-evidence-key-scope-secret"),
        ("replay.params", b"compose-replay-params-secret"),
    ):
        scope_path = directory / name
        scope_path.write_bytes(content)
        _chmod_600(scope_path)

    key_path = directory / "evidence.key.1"
    key_path.write_bytes(b"compose-hmac-signing-key-generation-1")
    _chmod_600(key_path)

    (directory / "approvals").mkdir()
    return directory


def write_approval_file(
    custody_root: Path,
    *,
    proposal_digest: str,
    environment_label: str,
    approved_intent_envelope_digest: str,
) -> Path:
    """Write one operator-authored IAP decision file"""
    path = custody_root / "approvals" / f"{proposal_digest}.yaml"
    _write_yaml(
        path,
        {
            "decision_id": f"decision-{proposal_digest[:16]}",
            "decision_generation": 1,
            "request_id": f"request-{proposal_digest[:16]}",
            "request_digest": proposal_digest,
            "trading_approval_policy_id": "compose-approval-policy",
            "trading_approval_policy_generation": 1,
            "trading_approval_policy_digest": "compose-approval-policy-digest",
            "result": "APPROVE",
            "reason_codes": ["compose-e2e"],
            "approved_intent_envelope_id": "compose-intent-envelope",
            "approved_intent_envelope_digest": approved_intent_envelope_digest,
            "max_decision_age_ms": None,
            "invalidation_generation": None,
            "supersedes_decision_id": None,
            "environment_label": environment_label,
        },
    )
    _chmod_600(path)
    return path
