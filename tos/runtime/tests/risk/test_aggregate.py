"""``AggregateRiskService`` + config loader tests (design #40 §5 order 5 item 1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from tos.are import RiskDecisionResult, RiskScopeKind
from tos.engine.records import InstrumentKey
from tos_runtime.risk.aggregate import (
    AggregateRiskConfigError,
    AggregateRiskService,
    load_adverse_scenario_set,
    load_required_scenario_kinds,
)

from .conftest import FakeEvidenceAppendPort, grant_shaped_are_inputs, write_risk_config

# ============================================================================
# config loading — fail-closed on null/missing values
# ============================================================================


def test_load_adverse_scenario_set_refuses_null_generation(tmp_path: Path) -> None:
    path = write_risk_config(tmp_path / "risk.yaml", scenario_set_generation=None)
    with pytest.raises(AggregateRiskConfigError):
        load_adverse_scenario_set(path)


def test_load_adverse_scenario_set_refuses_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AggregateRiskConfigError):
        load_adverse_scenario_set(tmp_path / "does-not-exist.yaml")


def test_load_adverse_scenario_set_refuses_malformed_yaml(tmp_path: Path) -> None:
    path = tmp_path / "risk.yaml"
    path.write_text("not: valid: yaml: [[[")
    with pytest.raises(AggregateRiskConfigError):
        load_adverse_scenario_set(path)


def test_load_adverse_scenario_set_refuses_unrecognized_scenario_kind(
    tmp_path: Path,
) -> None:
    path = write_risk_config(
        tmp_path / "risk.yaml", covered_scenario_kinds=["NOT_A_REAL_KIND"]
    )
    with pytest.raises(AggregateRiskConfigError):
        load_adverse_scenario_set(path)


def test_load_adverse_scenario_set_succeeds_when_fully_filled(
    risk_config_path: Path,
) -> None:
    scenario_set = load_adverse_scenario_set(risk_config_path)
    assert scenario_set.scenario_set_generation == 1
    assert scenario_set.canonical_digest is not None


def test_load_required_scenario_kinds_refuses_empty_floor(tmp_path: Path) -> None:
    path = write_risk_config(tmp_path / "risk.yaml", required_scenario_kinds=None)
    with pytest.raises(AggregateRiskConfigError):
        load_required_scenario_kinds(path)


def test_load_required_scenario_kinds_refuses_unrecognized_member(
    tmp_path: Path,
) -> None:
    path = write_risk_config(
        tmp_path / "risk.yaml", required_scenario_kinds=["NOT_A_REAL_KIND"]
    )
    with pytest.raises(AggregateRiskConfigError):
        load_required_scenario_kinds(path)


# ============================================================================
# snapshot() — structural derivation from the RCL projection
# ============================================================================


def test_snapshot_covers_required_scopes_after_a_successful_read(
    ara_service: AggregateRiskService, instrument_key: InstrumentKey
) -> None:
    snapshot = ara_service.snapshot(
        instrument_key,
        snapshot_generation=1,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        all_fields_attributed=True,
    )
    assert snapshot.covered_scopes == (RiskScopeKind.ACCOUNT,)
    assert snapshot.snapshot_id is not None
    assert snapshot.canonical_digest is not None


def test_snapshot_is_content_addressed_not_a_bare_counter(
    ara_service: AggregateRiskService, instrument_key: InstrumentKey
) -> None:
    """Two snapshots for the SAME scope at the SAME ledger state carry the
    same ``consistency_cut_identity`` shape (content-addressed, not a bare
    process-lifetime counter that could collide across a restart)."""
    first = ara_service.snapshot(
        instrument_key,
        snapshot_generation=1,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        all_fields_attributed=True,
    )
    assert first.consistency_cut_identity is not None
    assert first.consistency_cut_identity.startswith("are-cut-")


def test_snapshot_propagates_projection_read_failures(
    ara_service: AggregateRiskService, instrument_key: InstrumentKey, log
) -> None:
    """An unreachable RCL log is never silently read as 'covers nothing' —
    the exception propagates (the caller/Stage maps it to UNKNOWN)."""
    log.close()
    with pytest.raises(sqlite3.Error):
        ara_service.snapshot(
            instrument_key,
            snapshot_generation=1,
            required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
            all_fields_attributed=True,
        )


# ============================================================================
# decide() — risk_decision composition
# ============================================================================


def test_decide_grants_on_a_fully_proven_bundle(
    ara_service: AggregateRiskService,
    instrument_key: InstrumentKey,
    required_scenario_kinds,
) -> None:
    inputs = grant_shaped_are_inputs(required_scenario_kinds)
    decision = ara_service.decide(
        instrument_key, inputs, snapshot_generation=1, decision_generation=1
    )
    assert decision.result is RiskDecisionResult.GRANT
    assert decision.decision_id is not None
    assert decision.canonical_digest is not None
    # decision_id is orthogonal to the digest (are §3.1) — never the same string.
    assert decision.decision_id != decision.canonical_digest


def test_decide_is_unknown_when_all_fields_attributed_is_false(
    ara_service: AggregateRiskService,
    instrument_key: InstrumentKey,
    required_scenario_kinds,
) -> None:
    inputs = grant_shaped_are_inputs(required_scenario_kinds)
    inputs = type(inputs)(**{**inputs.__dict__, "all_fields_attributed": False})
    decision = ara_service.decide(
        instrument_key, inputs, snapshot_generation=1, decision_generation=1
    )
    assert decision.result is RiskDecisionResult.UNKNOWN


def test_decide_denies_when_the_effective_limit_enlarges_the_envelope(
    ara_service: AggregateRiskService,
    instrument_key: InstrumentKey,
    required_scenario_kinds,
) -> None:
    inputs = grant_shaped_are_inputs(required_scenario_kinds)
    inputs = type(inputs)(
        **{**inputs.__dict__, "limit_source_is_injected_envelope": False}
    )
    decision = ara_service.decide(
        instrument_key, inputs, snapshot_generation=1, decision_generation=1
    )
    assert decision.result is RiskDecisionResult.DENY


def test_decide_appends_decision_evidence(
    ara_service: AggregateRiskService,
    instrument_key: InstrumentKey,
    required_scenario_kinds,
    evidence_port: FakeEvidenceAppendPort,
) -> None:
    inputs = grant_shaped_are_inputs(required_scenario_kinds)
    decision = ara_service.decide(
        instrument_key, inputs, snapshot_generation=1, decision_generation=1
    )
    kinds = evidence_port.kinds()
    assert "ARE_SNAPSHOT" in kinds
    assert "ARE_DECISION" in kinds
    decision_calls = [
        payload for payload, kind, _rc in evidence_port.calls if kind == "ARE_DECISION"
    ]
    assert decision_calls[0]["decision_id"] == decision.decision_id
    assert decision_calls[0]["decision_digest"] == decision.canonical_digest
    # decision_id ⊥ digest — both recorded as separate fields, never conflated.
    assert decision_calls[0]["decision_id"] != decision_calls[0]["decision_digest"]
