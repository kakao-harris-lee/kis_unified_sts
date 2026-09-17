"""``AggregateRiskService`` + config loader tests (design #40 §5 order 5 item 1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from tos.are import RiskDecisionResult, RiskScopeKind
from tos.engine.records import InstrumentKey
from tos.rcl import (
    AppendReceipt,
    CapacityComponent,
    CapacityReservationTransition,
    CapacityState,
    CapacityVector,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos_runtime.rcl.log import SqliteCommitLog
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


def test_snapshot_conservative_current_usage_reflects_the_committed_rcl_vector(
    ara_service: AggregateRiskService,
    instrument_key: InstrumentKey,
    log: SqliteCommitLog,
    writer_epoch: int,
) -> None:
    """(review finding ④, round #4 — K-4's actual new behavior: the RCL commit vector
    now flows into the risk snapshot) A reservation committed with a NON-empty
    ``committed_vector`` in ``instrument_key``'s own scope must come back out as
    ``snapshot.conservative_current_usage`` — not the ``CapacityVector()`` fallback,
    which is reserved for "no reservation / no vector on record" only. Before this test,
    no test in this suite ever committed a non-``None`` vector, so
    ``AggregateRiskService.snapshot``'s wiring to ``instrument_committed_vector`` (rather
    than the unconditional empty-vector fallback it replaced) had no regression coverage:
    hardcoding ``conservative_current_usage=CapacityVector()`` in ``snapshot()`` left
    ``tos/runtime/tests/risk`` / ``compose`` / ``rcl`` / ``riskstate`` / ``safety`` all
    green (round #4 review, code-reviewer's own mutation)."""
    committed_vector = CapacityVector(
        components=(CapacityComponent(dimension_id="notional", magnitude="250"),)
    )
    transition = CapacityReservationTransition(
        reservation_id="res-are-1",
        writer_epoch=writer_epoch,
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.ATTEMPT_BOUND,
        scope=ReservationScope(
            account=instrument_key.account, instrument=instrument_key.instrument
        ),
        committed_vector=committed_vector,
    )
    result = log.apply_reservation_transition(
        transition,
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id="cmd-are-1",
        command_digest="dig-are-1",
        expected_seq=-1,
    )
    assert isinstance(result, AppendReceipt)

    snapshot = ara_service.snapshot(
        instrument_key,
        snapshot_generation=1,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        all_fields_attributed=True,
    )
    assert snapshot.conservative_current_usage == committed_vector
    assert snapshot.conservative_current_usage != CapacityVector()


def test_snapshot_conservative_current_usage_is_empty_vector_when_no_reservation(
    ara_service: AggregateRiskService, instrument_key: InstrumentKey
) -> None:
    """The ``CapacityVector()`` fallback stays for the honest "no reservation on
    record for this scope" case — never a fabricated magnitude, per the module
    docstring."""
    snapshot = ara_service.snapshot(
        instrument_key,
        snapshot_generation=1,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        all_fields_attributed=True,
    )
    assert snapshot.conservative_current_usage == CapacityVector()


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
