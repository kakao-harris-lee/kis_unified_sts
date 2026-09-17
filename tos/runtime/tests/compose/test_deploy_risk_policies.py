"""Compose e2e tests for the REAL deployed risk-state files
(``config/tos_runtime/paper/{risk,aggregate_risk_policy,action_flow_policy}.yaml``
-- TOS risk state service plan §6 ②, adopted by the operator 2026-09-16;
placement per DR-0002 §2.1 / DR-0003 §2.1).

Pins, in the same spirit as ``test_deploy_policies.py``:

1. Operator-fill gate: as committed, ``account_scope``/``instrument_scope``
   are ``"TBD"`` and both policy loaders REFUSE the files as-is.
2. With those coordinates filled, the files carry exactly the adopted values.
3. ``risk.yaml`` loads through the SAME loaders the compose root uses and
   carries exactly the proposal-table values.
4. The real calendar + the four real policies + the real ``risk.yaml`` boot
   the compose root WITHOUT explicit risk providers: all four
   ``*_POLICY_BOUND`` rows land, and the attempt still stops fail-closed at
   step 2 (the venue policy's null ``max_quantity`` -- pinned by
   ``test_deploy_policies.py``), so no ``RISK_STATE_OBSERVED`` row is ever
   produced. That is the adopted deploy state.

The fixture Hard Safety Envelope / Runtime Safety Profile gain the policy's
governed dimension for this test only -- no paper HSE instance is committed
yet (``safety_envelope.yaml`` is still an ``.example.yaml``), which the real
policy file's header records.

Hermetic (D1.4): every write lands under ``tmp_path``.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.risk.aggregate import (
    load_adverse_scenario_set,
    load_required_scenario_kinds,
)
from tos_runtime.riskstate import (
    load_action_flow_policy,
    load_aggregate_risk_policy,
)
from tos_runtime.venue import VenuePolicyConfigError

from . import _fixtures as fx
from .conftest import (
    _VENUE_POLICY_ACCOUNT,
    _VENUE_POLICY_INSTRUMENT,
    _governed_dimension_entry,
    _write_yaml,
)
from .test_compose_root import _reach_trusted
from .test_deploy_config import _install_real_calendar, _kst_unix_ms
from .test_deploy_policies import _install_real_policies
from .test_venue_wiring import _kind_count, _rewrite_activation

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEPLOY_DIR = _REPO_ROOT / "config" / "tos_runtime" / "paper"
_REAL_RISK = _DEPLOY_DIR / "risk.yaml"
_REAL_ARE = _DEPLOY_DIR / "aggregate_risk_policy.yaml"
_REAL_AFG = _DEPLOY_DIR / "action_flow_policy.yaml"

#: The adopted values (plan §6 ②; proposal table
#: ``2026-09-12-tos-operator-value-proposals.md`` §3) -- pinned so a silent
#: edit of a deploy file cannot pass as "still the approved value".
_ADOPTED_DIMENSION_ID = "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"
_ADOPTED_ARE_LIMIT = Decimal("1")
_ADOPTED_FLOW_DIMENSION_ID = "afg.ORDER"
_ADOPTED_SCENARIO_KIND = "ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ"
_ADOPTED_ENVELOPE = {
    "max_fan_out": 4,
    "max_depth": 3,
    "max_attempts": 2,
    "max_mutations": 3,
    "max_queries": 8,
    "max_queue_depth": 8,
    "max_in_flight": 1,
    "max_elapsed_monotonic": 30000,
    "max_duplicate_redelivery_expansion": 1,
    "max_failover_reconnect_replay_expansion": 1,
    "max_amplification_per_cause": 3,
}


def _filled_risk_policy(path: Path, *, account: str, instrument: str | None) -> dict:
    """The real document with ONLY the operator-fill coordinates filled."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["account_scope"] == ["TBD"]
    raw["account_scope"] = [account]
    if instrument is not None:
        assert raw["instrument_scope"] == ["TBD"]
        raw["instrument_scope"] = [instrument]
    return raw


def _install_real_risk_files(config_dir: Path) -> tuple[str, str]:
    """Install the real ``risk.yaml`` verbatim and the two filled real policies
    over the fixture ones, give the fixture HSE/profile the policy's governed
    dimension, and append both member refs to the activation ``members:``.
    Returns both policy digests."""
    (config_dir / "risk.yaml").write_text(
        _REAL_RISK.read_text(encoding="utf-8"), encoding="utf-8"
    )
    are_raw = _filled_risk_policy(
        _REAL_ARE, account=_VENUE_POLICY_ACCOUNT, instrument=_VENUE_POLICY_INSTRUMENT
    )
    afg_raw = _filled_risk_policy(
        _REAL_AFG, account=_VENUE_POLICY_ACCOUNT, instrument=None
    )
    for name, raw in (
        ("aggregate_risk_policy.yaml", are_raw),
        ("action_flow_policy.yaml", afg_raw),
    ):
        (config_dir / name).write_text(
            yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    # The fixture HSE/profile must govern the policy's dimension (no paper HSE
    # instance exists yet -- the real policy file's own header says so).
    for file_name, top_key, magnitude_key in (
        ("safety_envelope.yaml", "envelope", "envelope_max"),
        ("safety_profile.yaml", "profile", "profile_value"),
    ):
        path = config_dir / file_name
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        entry = _governed_dimension_entry(magnitude_key=magnitude_key, value="1")
        entry["dimension"] = _ADOPTED_DIMENSION_ID
        raw[top_key]["governed_dimensions"].append(entry)
        _write_yaml(path, raw)

    are = load_aggregate_risk_policy(
        config_dir / "aggregate_risk_policy.yaml", scheme=_SCHEME
    )
    afg = load_action_flow_policy(
        config_dir / "action_flow_policy.yaml", scheme=_SCHEME
    )
    assert are.policy.canonical_digest is not None
    assert afg.policy.canonical_digest is not None
    activation = yaml.safe_load(
        (config_dir / "safety_activation.yaml").read_text(encoding="utf-8")
    )
    members = [dict(m) for m in activation["members"]]
    members.extend(
        [
            {
                "kind": "AGGREGATE_RISK_POLICY",
                "member_id": are.policy.policy_id,
                "generation": are.policy.policy_generation,
                "digest": are.policy.canonical_digest,
                "resolved": True,
                "immutable": True,
            },
            {
                "kind": "ACTION_FLOW_POLICY",
                "member_id": afg.policy.policy_id,
                "generation": afg.policy.policy_generation,
                "digest": afg.policy.canonical_digest,
                "resolved": True,
                "immutable": True,
            },
        ]
    )
    _rewrite_activation(config_dir, members)
    return are.policy.canonical_digest, afg.policy.canonical_digest


def test_real_risk_files_carry_their_approval_provenance() -> None:
    for path in (_REAL_RISK, _REAL_ARE, _REAL_AFG):
        text = path.read_text(encoding="utf-8")
        assert "§6 ②" in text
        assert "2026-09-16" in text
    assert "DR-0003" in _REAL_ARE.read_text(encoding="utf-8")
    assert "DR-0003" in _REAL_AFG.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path, loader",
    [
        (_REAL_ARE, load_aggregate_risk_policy),
        (_REAL_AFG, load_action_flow_policy),
    ],
)
def test_real_risk_policies_refuse_to_load_until_the_operator_fills_the_scope(
    path: Path, loader
) -> None:
    with pytest.raises(VenuePolicyConfigError):
        loader(path, scheme=_SCHEME)


def test_filled_real_risk_policies_carry_exactly_the_adopted_values(
    tmp_path: Path,
) -> None:
    are_raw = _filled_risk_policy(_REAL_ARE, account="acct-x", instrument="inst-x")
    are_path = tmp_path / "aggregate_risk_policy.yaml"
    are_path.write_text(yaml.safe_dump(are_raw, sort_keys=False, allow_unicode=True))
    are = load_aggregate_risk_policy(are_path, scheme=_SCHEME)
    assert are.policy.policy_version == "1.0.0"
    assert are.policy.policy_generation == 1
    assert set(are.dimension_ids.values()) == {_ADOPTED_DIMENSION_ID}
    limit = {c.dimension_id: c.magnitude for c in are.effective_limits.components}
    assert limit == {_ADOPTED_DIMENSION_ID: _ADOPTED_ARE_LIMIT}
    assert {k.value for k in are.required_scenario_kinds} == {_ADOPTED_SCENARIO_KIND}
    assert are.unit == "CONTRACTS"

    afg_raw = _filled_risk_policy(_REAL_AFG, account="acct-x", instrument=None)
    afg_path = tmp_path / "action_flow_policy.yaml"
    afg_path.write_text(yaml.safe_dump(afg_raw, sort_keys=False, allow_unicode=True))
    afg = load_action_flow_policy(afg_path, scheme=_SCHEME)
    assert afg.policy.policy_version == "1.0.0"
    assert afg.flow_dimension_id == _ADOPTED_FLOW_DIMENSION_ID
    assert set(afg.limits) == {
        "hard_limit",
        "runtime_limit",
        "envelope_max",
        "decision_effective_limit",
    }
    for vector in afg.limits.values():
        assert [(c.dimension_id, c.magnitude) for c in vector.components] == [
            (_ADOPTED_FLOW_DIMENSION_ID, Decimal("1"))
        ]
    facts = afg.deployment_facts
    assert facts.concurrent_consumers_share_one_envelope is True
    assert facts.envelope_reset_on_duplicate is False
    assert facts.duplicate_event_created_new_allowance is False
    assert afg.side_tokens == ("BUY", "SELL")
    assert {k.value: v.value for k, v in afg.action_class_map.items()} == {
        "NEW_LONG": "NORMAL_NEW_RISK",
        "NEW_SHORT": "NORMAL_NEW_RISK",
        "DECREASE": "ORDINARY_REDUCE_OR_EXIT",
        "CLOSE": "ORDINARY_REDUCE_OR_EXIT",
        "REDUCE_ONLY": "ORDINARY_REDUCE_OR_EXIT",
    }


def test_real_risk_yaml_loads_with_exactly_the_adopted_values() -> None:
    scenario_set = load_adverse_scenario_set(_REAL_RISK)
    assert scenario_set.scenario_set_id == "paper-adverse-set-1"
    assert scenario_set.scenario_set_generation == 1
    assert {k.value for k in scenario_set.covered_scenario_kinds} == {
        _ADOPTED_SCENARIO_KIND
    }
    required = load_required_scenario_kinds(_REAL_RISK)
    assert {k.value for k in required} == {_ADOPTED_SCENARIO_KIND}
    raw = yaml.safe_load(_REAL_RISK.read_text(encoding="utf-8"))
    for key, value in _ADOPTED_ENVELOPE.items():
        assert raw[key] == value, key


def test_real_risk_files_boot_the_compose_root_and_the_attempt_still_denies_at_step2(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _install_real_calendar(config_dir)
    _install_real_policies(config_dir)
    are_digest, afg_digest = _install_real_risk_files(config_dir)

    fx.write_band_strategy_file(config_dir)
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=None,
        action_flow_inputs_provider=None,
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 9, 7, 10, 0)),
    )
    _reach_trusted(runtime)

    assert runtime.risk_state is not None
    for kind in (
        "VENUE_POLICY_BOUND",
        "ORDER_CONSTRUCTION_POLICY_BOUND",
        "AGGREGATE_RISK_POLICY_BOUND",
        "ACTION_FLOW_POLICY_BOUND",
    ):
        assert _kind_count(runtime, kind) == 1, kind

    results = runtime.run_once((fx.crossing_event(),))
    assert results[0].flow is not None
    verdicts = {v.step: v for v in results[0].flow.verdicts}
    step2 = verdicts[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION]
    assert step2.outcome is StageOutcome.DENY
    assert CommitmentStep.AGGREGATE_RISK_DECISION not in verdicts
    assert _kind_count(runtime, "RISK_STATE_OBSERVED") == 0

    runtime.rcl_log.close()
    runtime.evidence_store.close()
