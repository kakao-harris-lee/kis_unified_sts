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
from tos.cur import MANDATED_DIMENSION_FLOOR
from tos_runtime.compose._pending_dimensions import PENDING_DIMENSION_KEYS
from tos_runtime.operations.dependency_admission import (
    observe_dependency_set_digest,
    observe_source_tree_digest,
)
from tos_runtime.riskstate.policies import (
    load_action_flow_policy,
    load_aggregate_risk_policy,
)
from tos_runtime.venue import (
    load_order_construction_policy,
    load_venue_constraint_policy,
)

from ..riskstate._documents import action_flow_policy_yaml, aggregate_risk_policy_yaml
from ..venue._documents import ocp_yaml, venue_policy_yaml

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: This suite's single scope coordinates for the governed venue/OCP policies (TOS venue
#: constraint service wave, plan §2 decision 9) — MUST match ``_fixtures.py``'s own
#: ACCOUNT/INSTRUMENT/INSTRUMENT_CLASS constants and this fixture's own ``environment_label``
#: ("non-live-test") and ``calendar.yaml`` (below): the loader's scope cross-check requires an
#: exact match, and the admitting-phase tokens must be ones ``calendar.yaml`` actually declares
#: for that instrument class.
_VENUE_POLICY_ENVIRONMENT = "non-live-test"
_VENUE_POLICY_ACCOUNT = "acct-compose"
_VENUE_POLICY_INSTRUMENT = "ES"
_VENUE_POLICY_INSTRUMENT_CLASS = "krx-index-futures"
#: The ONE session-phase token this fixture's ``calendar.yaml`` (below) declares for
#: ``krx-index-futures`` — the ONLY token an admitting-phase rule may legally name.
_VENUE_POLICY_ADMITTING_PHASE = "CONTINUOUS"

#: The shipped example (TOS Phase 4 plan §2 decisions 1-2, G-4) — this
#: fixture only fills the one named-TBD field (``active_scope``), never
#: hand-retypes the scope table, so the compose e2e suite exercises the SAME
#: config a real deployment would start from.
_BROKER_SCOPES_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "broker_scopes.example.yaml"
)

#: The digest compose_paper_runtime computes for its own RuntimeIdentity.code_digest
#: (tos_runtime.compose._wiring._build_identity: the installed source-tree digest,
#: tos_runtime.operations.dependency_admission.observe_source_tree_digest). Reproduced
#: here (pure function, same measurement, same installed tree the test process itself
#: runs from) so release.yaml can match it exactly.
EXPECTED_CODE_DIGEST = observe_source_tree_digest()

#: The digest compose_paper_runtime computes for its STAGE A/B dependency-set
#: observation (tos_runtime.operations.dependency_admission
#: .observe_dependency_set_digest) — the installed distribution set this test process
#: itself is running under.
EXPECTED_DEPENDENCY_SET_DIGEST = observe_dependency_set_digest()


def _write_yaml(path: Path, content: dict) -> None:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


def _chmod_600(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def call_wrapped_fixture(fixture_func: object, *args: object) -> Path:
    """Call the plain function a ``@pytest.fixture``-decorated callable wraps, bypassing
    pytest's own guard against calling a fixture directly. ``config_dir``/``data_dir``/
    ``custody_root``/``config_dir_with_risk_state`` below are each parametrized only by plain
    arguments (verified by reading their signatures), so a caller building an independent root
    can drive the SAME fixture-writing logic every other e2e test in this package relies on,
    just against a fresh root. ``__wrapped__`` reaches that original function.

    The ignore below is a **choice, not a necessity** — pytest 9.0.2's
    ``FixtureFunctionDefinition._get_wrapped_function()`` returns the same function and type-checks
    clean without it. It is not used because it is a private method on a class that pytest does not
    export (``pytest.FixtureFunctionDefinition`` does not exist; the class lives in the top-level
    private ``_pytest.fixtures``), so depending on it would break on any internal refactor.
    ``__wrapped__`` rests on the ``functools.update_wrapper`` convention instead, which is a far
    more stable contract — at the cost of one ignore, kept here as this module's single place for
    the gap so call sites stay clean. **If pytest ever exports the accessor, prefer it and drop
    the ignore.**

    ``fixture_func`` is deliberately typed ``object`` rather than ``Callable[..., Path]``:
    ``FixtureFunctionDefinition.__call__`` is defined to ``fail()``, so a callable annotation would
    be a type the object does not actually honour. That looseness is also why the ``isinstance``
    below earns its keep: a caller can always pass a fixture returning something other than
    ``Path`` — Python does not enforce annotations — and with ``object`` mypy will not flag it
    either, so this check is the only thing between a wrong fixture and a confusing downstream
    failure. It does fire (verified by passing a real ``@pytest.fixture``-decorated ``str``
    fixture); that is a runtime fact, not a mypy-reachability one.
    """
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
        {
            "B_capability_claim_to_send": 500,
            # MEDIUM-3: the operator-declared CURRENTNESS_POLICY dimension set — the
            # full mandated floor, same as production would declare correctly.
            "required_dimensions": sorted(
                key.value for key in MANDATED_DIMENSION_FLOOR
            ),
        },
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
    # TOS Phase 5 W5 (plan §2 decisions 1-4): egress_attestations.yaml is retired to
    # zero -- venue_session_account_facts_current now has a real runtime owner
    # (tos_runtime.calendar.owner.SessionFactsOwner via calendar.yaml below), so this
    # file is deliberately NOT written here any more (a leftover file refuses boot --
    # RetiredConfigPresent, tests/compose/test_session_wiring.py). This fixture's
    # calendar is deliberately permissive (one full-day CONTINUOUS window, every
    # weekday, no holidays) so every OTHER compose e2e test's happy path keeps
    # reaching an ADMISSIBLE step 3 / SATISFIED item 12 (for the non-broker-reaching
    # SYNTHETIC_FUTURES_ORDER scope this suite activates below) regardless of which
    # instant the test's own wall-clock fixture injects; tests/compose/
    # test_session_wiring.py exercises the interesting negative paths (holiday,
    # after-hours, absent wall clock, calendar-version mismatch) with their OWN,
    # narrower calendar configs.
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
                        "end": "23:59",
                        "days": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
                        "crosses_midnight": False,
                    }
                ]
            },
            "closed_phase": "CLOSED",
            "futures_expiry": {},
        },
    )
    # TOS venue constraint service wave (plan §2 decisions 1/2/6/9) — the two governed policy
    # YAMLs `build_venue_service` loads. Every numeric shape bound below reproduces this
    # suite's OWN pre-wave fixture values (formerly `_fixtures.py::venue_shape_constraints`) so
    # every existing e2e test's happy path keeps folding the SAME admissible shape at step 3:
    # the crossing event's own "close" value (4_499_000, `_fixtures.CROSSING_CLOSE`) is the
    # price step 3 actually resolves (shape_price_field_key="close" projects off the tick's own
    # value view, never the injected `order_shape().price` stand-in — see
    # `tos.egressgw.construction.VenueConstraintStage._shape_for`'s own docstring), and
    # 1_000 <= 4_499_000 <= 9_000_000 with (4_499_000 - 1_000) % 500 == 0.
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
            # Both NEW_LONG and NEW_SHORT admit the SAME token — one shared config_dir
            # fixture serves both the LONG (test_compose_root.py) and SHORT
            # (test_symmetry.py) e2e suites (plan §2 decision 8 mirroring).
            admitting_phases=f'["{_VENUE_POLICY_ADMITTING_PHASE}"]',
            admitting_phases_short=f'["{_VENUE_POLICY_ADMITTING_PHASE}"]',
        ),
        encoding="utf-8",
    )
    (directory / "order_construction_policy.yaml").write_text(
        ocp_yaml(
            environment=_VENUE_POLICY_ENVIRONMENT,
            account=_VENUE_POLICY_ACCOUNT,
            instrument=_VENUE_POLICY_INSTRUMENT,
            # synthetic transport (this suite's default) requires wire_codec: null.
            wire_codec="null",
        ),
        encoding="utf-8",
    )
    loaded_venue_policy = load_venue_constraint_policy(
        directory / "venue_constraint_policy.yaml", scheme=_SCHEME
    )
    loaded_ocp_policy = load_order_construction_policy(
        directory / "order_construction_policy.yaml", scheme=_SCHEME
    )
    # Phase 5 W3 safety-mesh policy documents (tos_runtime.compose._safety_wiring) — a
    # minimal NOMINAL "everything clear" fixture (one governed dimension, no active
    # deviations/incidents, all three MONITORING obligations closed) so every compose
    # e2e test's happy path exercises a genuinely CLEAR mesh, not a fabricated one.
    _write_yaml(
        directory / "safety_envelope.yaml",
        {
            "envelope": {
                "envelope_id": "env-compose-1",
                "envelope_generation": 1,
                "envelope_version": {
                    "version": "v1",
                    "effective_date": "2026-09-01",
                    "evidence_package_version": None,
                    "approver_identity": "operator-compose",
                    "expiration_or_revalidation_date": None,
                    "superseded_version_link": None,
                    "change_classification": None,
                },
                "governed_dimensions": [
                    {
                        "dimension": "max_notional",
                        "envelope_max": "100",
                        "unit": "KRW",
                        "multiplier": "1",
                        "sign": "POSITIVE",
                        "precision": "0",
                        "rounding": "NEAREST",
                        "boundary": "INCLUSIVE",
                    }
                ],
                "permitted_scope": ["default"],
                "prohibited_fallbacks": [],
                "residual_risk_ceiling": None,
                "evidence_package_ref": None,
            }
        },
    )
    _write_yaml(
        directory / "safety_profile.yaml",
        {
            "profile": {
                "profile_id": "prof-compose-1",
                "profile_generation": 1,
                "profile_version": {
                    "version": "v1",
                    "effective_date": "2026-09-01",
                    "evidence_package_version": None,
                    "approver_identity": "operator-compose",
                    "expiration_or_revalidation_date": None,
                    "superseded_version_link": None,
                    "change_classification": None,
                },
                "target_envelope_id": "env-compose-1",
                "target_envelope_generation": 1,
                "governed_dimensions": [
                    {
                        "dimension": "max_notional",
                        "profile_value": "50",
                        "unit": "KRW",
                        "multiplier": "1",
                        "sign": "POSITIVE",
                        "precision": "0",
                        "rounding": "NEAREST",
                        "boundary": "INCLUSIVE",
                    }
                ],
                "scope": ["default"],
                "permitted_behaviors": [],
                "fallback_rules": [],
                "evidence_package_ref": None,
            }
        },
    )
    _write_yaml(
        directory / "safety_activation.yaml",
        {
            "activation": {
                "activation_id": "act-compose-1",
                "profile_generation": 1,
                "envelope_digest": None,
                "profile_digest": None,
                "bundle_digest": None,
                "scope": [],
                "approval_ids": ["appr-compose-1"],
                "compatibility_attestation_refs": ["attest-compose-1"],
                "predecessor_generation": None,
                "restrictive_generation_effects": [],
            },
            "not_expired": True,
            # TOS venue constraint service wave (plan §2 decision 7) — a SEPARATE top-level
            # key `tos_runtime.safety.profile` never reads; `tos_runtime.venue.activation`
            # exact-matches against it. Digests are the REAL, freshly kernel-computed values
            # from the two loads just above — never hardcoded (plan §5 discipline).
            "members": [
                {
                    "kind": "VENUE_CONSTRAINT_POLICY",
                    "member_id": loaded_venue_policy.policy.policy_id,
                    "generation": loaded_venue_policy.policy.policy_generation,
                    "digest": loaded_venue_policy.policy.canonical_digest,
                    "resolved": True,
                    "immutable": True,
                },
                {
                    "kind": "ORDER_CONSTRUCTION_POLICY",
                    "member_id": loaded_ocp_policy.policy.policy_id,
                    "generation": loaded_ocp_policy.policy.policy_generation,
                    "digest": loaded_ocp_policy.policy.canonical_digest,
                    "resolved": True,
                    "immutable": True,
                },
            ],
        },
    )
    _write_yaml(
        directory / "safety_deviations.yaml",
        {
            "deviations": {
                "active_set": {
                    "active_set_id": "dev-set-compose-1",
                    "active_set_generation": 1,
                    "deviation_generation": 1,
                    "is_complete": True,
                    "combined_within_envelope": True,
                },
                "applicable_decision_ids": [],
                "members": [],
            }
        },
    )
    _write_yaml(
        directory / "safety_incidents.yaml",
        {
            "incidents": {
                "active_set": {
                    "active_set_id": "inc-set-compose-1",
                    "active_set_generation": 1,
                    "incident_generation": 1,
                    "safety_cell": "compose-cell-1",
                    "shared_dependencies": [],
                    "is_complete": True,
                    "is_current": True,
                },
                "applicable_incident_ids": [],
                "members": [],
            }
        },
    )
    _write_yaml(
        directory / "monitor_coverage.yaml",
        {
            "coverage": {
                "manifest": {
                    "coverage_manifest_id": "cov-compose-1",
                    "coverage_generation": 1,
                    "coverage_manifest_digest": "cov-digest-compose-1",
                    "policy_digest": "cov-policy-digest-compose-1",
                    "is_complete": True,
                },
                "items": {
                    obligation: {
                        "restrictive_response_present": True,
                        "alert_path_present": True,
                        "evidence_path_present": True,
                        "currentness_rule_present": True,
                        "closure_1_to_12_complete": True,
                        "criticality": "CRITICAL",
                    }
                    for obligation in (
                        "evidence-tip-currency",
                        "time-service-health",
                        "inbox-backlog",
                    )
                },
                "bounds": {
                    "max_evidence_tip_stall_ms": 60_000,
                    "healthy_time_states": ["TRUSTED"],
                    "max_inbox_unconsumed": 100,
                },
            }
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
            # T2 lane B (plan §2 decision 7 / §7 operator disposition row 1)
            # — this compose e2e suite's active scope is the SYNTHETIC one
            # (reaches_broker=False), which never reaches this posture at
            # all (gate ② already admits it), so the value here is inert for
            # every existing e2e test; `false` is the honest "not
            # operator-admitted" default, never a silent grant.
            "nonlive_broker_consuming": {"admitted": False},
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
            # TOS Phase 5 W2-R (plan §10 row ④) — large enough that no compose e2e test's
            # synchronous run ever crosses it, so the obligation-expiry evidence stays absent
            # unless a test deliberately advances the injected clock past it.
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
    """A copy of ``config_dir`` whose ``release.yaml`` carries a code digest
    that does NOT match ``RuntimeIdentity.code_digest`` — for the release-
    admission-refusal test (scenario 7)."""
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


#: The TOS risk state service wave's own governed dimension id (an ADDITIVE new HSE/profile
#: dimension, alongside the existing "max_notional" pair — never replacing it, so every OTHER
#: compose e2e test reusing the base ``config_dir`` fixture's own envelope/profile is
#: untouched) — see :func:`config_dir_with_risk_state`'s own docstring for why this lives on
#: a SEPARATE, opt-in fixture rather than mutating ``config_dir`` itself.
_RISK_STATE_DIMENSION_ID = "ACCOUNT::GROSS_NOTIONAL"
_RISK_STATE_ENVELOPE_MAX = "100000"


def _governed_dimension_entry(*, magnitude_key: str, value: str) -> dict:
    return {
        "dimension": _RISK_STATE_DIMENSION_ID,
        magnitude_key: value,
        "unit": "CONTRACTS",
        "multiplier": "1",
        "sign": "POSITIVE",
        "precision": "0",
        "rounding": "NEAREST",
        "boundary": "INCLUSIVE",
    }


@pytest.fixture()
def config_dir_with_risk_state(config_dir: Path) -> Path:
    """``config_dir`` PLUS the two TOS risk state service wave governed policy instances
    (TOS risk state service wave, plan §1 "합성 paper e2e" acceptance) — an OPT-IN layered
    fixture, mirroring :func:`mismatched_release_config_dir`'s own "copy of config_dir with
    one more thing written into it" idiom, so the ~400 OTHER compose e2e tests that request
    ``config_dir`` directly are completely unaffected (each test's own ``config_dir``
    invocation is a fresh ``tmp_path``-scoped directory; this fixture only ever mutates the
    ONE instance a test that actually depends on it receives).

    Adds, on top of the base fixture:

    * A new ``ACCOUNT::GROSS_NOTIONAL`` governed dimension to BOTH ``safety_envelope.yaml``
      and ``safety_profile.yaml`` (alongside the existing ``max_notional`` pair, never
      replacing it) — ``profile_within_envelope``'s own "profile covers every envelope
      dimension" requirement stays satisfied for every OTHER test's own happy path, since
      this dimension is additive to both files together.
    * ``aggregate_risk_policy.yaml`` / ``action_flow_policy.yaml`` scoped to this suite's own
      ``fx.ACCOUNT``/``fx.INSTRUMENT``, covering both ``NEW_LONG``/``NEW_SHORT`` action
      classes (plan §5 실증 (7) NEW_SHORT mirror), with generous limits
      (``_RISK_STATE_ENVELOPE_MAX`` / ``100`` afg.ORDER) so a single crossing-event attempt's
      real derived quantity has ample headroom, and
      ``concurrent_consumers_share_one_envelope: true`` — REQUIRED (not the lane a fixture
      builder's own ``false`` default) for ``tos.afg.amplification_bounded`` to ever GRANT
      (§11 line 294's own positive-``True`` requirement).
    * Two new ``safety_activation.yaml`` ``members:`` entries (additive to the existing
      VENUE_CONSTRAINT_POLICY/ORDER_CONSTRUCTION_POLICY pair).
    """
    envelope_raw = yaml.safe_load(
        (config_dir / "safety_envelope.yaml").read_text(encoding="utf-8")
    )
    envelope_raw["envelope"]["governed_dimensions"].append(
        _governed_dimension_entry(
            magnitude_key="envelope_max", value=_RISK_STATE_ENVELOPE_MAX
        )
    )
    _write_yaml(config_dir / "safety_envelope.yaml", envelope_raw)

    profile_raw = yaml.safe_load(
        (config_dir / "safety_profile.yaml").read_text(encoding="utf-8")
    )
    profile_raw["profile"]["governed_dimensions"].append(
        _governed_dimension_entry(
            magnitude_key="profile_value", value=_RISK_STATE_ENVELOPE_MAX
        )
    )
    _write_yaml(config_dir / "safety_profile.yaml", profile_raw)

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
    are_loaded = load_aggregate_risk_policy(are_path, scheme=_SCHEME)
    afg_loaded = load_action_flow_policy(afg_path, scheme=_SCHEME)

    activation_raw = yaml.safe_load(
        (config_dir / "safety_activation.yaml").read_text(encoding="utf-8")
    )
    activation_raw["members"].extend(
        [
            {
                "kind": "AGGREGATE_RISK_POLICY",
                "member_id": are_loaded.policy.policy_id,
                "generation": are_loaded.policy.policy_generation,
                "digest": are_loaded.policy.canonical_digest,
                "resolved": True,
                "immutable": True,
            },
            {
                "kind": "ACTION_FLOW_POLICY",
                "member_id": afg_loaded.policy.policy_id,
                "generation": afg_loaded.policy.policy_generation,
                "digest": afg_loaded.policy.canonical_digest,
                "resolved": True,
                "immutable": True,
            },
        ]
    )
    _write_yaml(config_dir / "safety_activation.yaml", activation_raw)
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
