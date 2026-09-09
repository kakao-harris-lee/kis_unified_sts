"""tos/runtime/tests/compose — hermetic fixtures (D1.4: tmp_path only, no
external network, no ambient env). Builds a fully-valued config directory, a
D4 custody directory (manifest + scope files + generation-numbered evidence
key + an approvals/ directory), and a data directory — everything
:func:`tos_runtime.compose.root.compose_paper_runtime` needs to construct
successfully.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.compose._pending_dimensions import PENDING_DIMENSION_KEYS

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: The shipped example (TOS Phase 4 plan §2 decisions 1-2, G-4) — this
#: fixture only fills the one named-TBD field (``active_scope``), never
#: hand-retypes the scope table, so the compose e2e suite exercises the SAME
#: config a real deployment would start from.
_BROKER_SCOPES_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "broker_scopes.example.yaml"
)

#: The digest compose_paper_runtime computes for its own RuntimeIdentity.code_digest
#: (tos_runtime.compose.root: ``_SCHEME.compute_digest({"component": "tos_runtime.compose"})``).
#: Reproduced here (pure function, same scheme) so release.yaml can match it exactly.
EXPECTED_CODE_DIGEST = _SCHEME.compute_digest({"component": "tos_runtime.compose"})


def _write_yaml(path: Path, content: dict) -> None:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


def _chmod_600(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


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
            "tz_db_version": "tzdb-compose-0",
            "trading_calendar_version": "cal-compose-0",
            "verification_profile_version": "ver-compose-0",
            "safety_profile_version": "safety-compose-0",
        },
    )
    _write_yaml(
        directory / "authority.yaml",
        {
            "containment_bound_ms": 60_000,
            # Matches write_approval_file's own
            # trading_approval_policy_generation=1 below, so
            # IntentRegistry.decision_current's generation-equality check
            # (tos_runtime.authority.iap, landed by lane P 2026-09-08) holds
            # for every approval file this fixture module writes.
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
        {"B_capability_claim_to_send": 500},
    )
    _write_yaml(
        directory / "currentness_dimensions.yaml",
        {
            key.value: {
                "bound_generation": 1,
                "bound_digest": f"operator-attested-{key.value.lower()}-digest",
                "restrictive_floor": 0,
                "positively_established": True,
            }
            for key in PENDING_DIMENSION_KEYS
        },
    )
    _write_yaml(
        directory / "egress_attestations.yaml",
        {
            "venue_session_account_facts_current": {"attested": True},
            "restrictive_latch_state": {"clear": True},
            "worst_credible_capacity": {"value": 1},
        },
    )
    _write_yaml(
        directory / "egress_coordinates.yaml",
        {
            # Mirrors the literals _wiring.py's _build_context_resolver used
            # to hardcode (kernel round #1 §7.2 survey) — see
            # tos_runtime.compose._egress_coordinates's own module docstring.
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
    # The example's ONE named-TBD field (module docstring) — this compose
    # e2e suite activates the same SYNTHETIC scope _wiring.py's old
    # hardcoded transport literal represented (G-4, now structurally
    # derived instead — tos_runtime.brokercap.scopes).
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
            # TOS Phase 3 Wave 1 Lane A-R — a boot-time cost bound, not a
            # safety threshold (tos_runtime.compose._engine_wiring's own
            # module docstring); large enough to cover every event this
            # suite's compose end-to-end tests ever admit in one process.
            "replay_window_events": 1000,
        },
    )
    _write_yaml(
        directory / "coordinator_preconditions.yaml",
        {
            # TOS Phase 3 Wave 2 Lane B-R (design #31 §9-10; plan §2.1) — the
            # ONLY governance posture tos_runtime.compose._preconditions has
            # wiring for today (ADR-002-025; tos-spec's own
            # AUTHORITY-STATUS.csv "restricted_live,NOT_AUTHORIZED" row).
            # This compose e2e suite's synthetic (reaches_broker=False)
            # transport is exactly the case this posture admits.
            "live_authorization_state": "NOT_AUTHORIZED",
        },
    )
    _write_yaml(
        directory / "finality.yaml",
        {
            # TOS Phase 3 Wave 2 Lane C-R follow-up (team-lead CR-4 dispatch,
            # plan §2.2) — the SYNTHETIC post-trade finality policy every
            # SyntheticFinalityProducer this compose root wires needs.
            "currency": "KRW",
            "value_date": "2026-09-09",
            "source_revision": "compose-e2e-rev-1",
            "proof_recipe_id": "compose-e2e-recipe-1",
        },
    )
    _write_yaml(
        directory / "release.yaml",
        {
            "expected_code_digest": EXPECTED_CODE_DIGEST,
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
    """A copy of ``config_dir`` whose ``release.yaml`` carries a code digest
    that does NOT match ``RuntimeIdentity.code_digest`` — for the release-
    admission-refusal test (scenario 7)."""
    _write_yaml(
        config_dir / "release.yaml",
        {
            "expected_code_digest": "deliberately-mismatched-digest",
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


@pytest.fixture()
def custody_root(tmp_path: Path) -> Path:
    directory = tmp_path / "custody"
    directory.mkdir()
    uid = os.getuid()
    del uid  # files are owned by the test process itself already

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

    # tos_runtime.custody.key_provider.FileKeyProvider scans for
    # evidence.key.<generation> files directly under custody_root — a
    # DIFFERENT convention from the manifest-driven "evidence.key" scope
    # file above (see tos_runtime/custody/key_provider.py's own docstring).
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
    """Write one operator-authored IAP decision file
    (``approvals/<proposal_digest>.yaml`` — see
    ``tos_runtime.authority.iap.load_operator_approval_file``).

    ``approved_intent_envelope_digest`` MUST be the REAL
    ``tos.ioc.ApprovedIntentContract.canonical_digest`` step 2
    (``OrderConstructionStage``) built for this exact attempt (e.g.
    ``runtime.construction_stage.construction.intent.canonical_digest``,
    read AFTER the run that produced it) — never a placeholder string.
    ``ComposeContextResolver``'s ``_envelope_equivalent_provider``
    (``tos_runtime.compose._wiring``) structurally compares this field
    against that live digest via ``tos.iap.exact_binding_holds``, so a
    placeholder here would make step 4 (``INDEPENDENT_APPROVAL``) DENY
    every time (a mismatch, not a permissive default) — matching this
    fixture's own digest to a real one is required for the honest ADMIT
    path, not for any weakened check.
    """
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
