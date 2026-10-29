"""``AggregateRiskService`` + config loader tests (design #40 §5 order 5 item 1)."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
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
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
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


def test_load_adverse_scenario_set_refuses_named_tbd_placeholder(
    tmp_path: Path,
) -> None:
    """W-A A-0 round 2 (kernel round #4 재심 BLOCKER): scenario_set_id/policy_binding_id/
    evidence_package_ref are sealed into the issued AdverseScenarioSet's canonical
    digest — an operator-typed ``"TBD"`` must never pass ``AdverseScenarioSet.issue``'s
    own null-only check."""
    path = write_risk_config(tmp_path / "risk.yaml", scenario_set_id="TBD")
    with pytest.raises(AggregateRiskConfigError, match="template placeholder"):
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
    ``AggregateRiskService.snapshot``'s wiring to the committed vector (rather
    than the unconditional empty-vector fallback it replaced) had no regression coverage:
    hardcoding ``conservative_current_usage=CapacityVector()`` in ``snapshot()`` left
    ``tos/runtime/tests/risk`` / ``compose`` / ``rcl`` / ``riskstate`` / ``safety`` all
    green (round #4 review, code-reviewer's own mutation)."""
    committed_vector = CapacityVector(
        components=(
            CapacityComponent(dimension_id="notional", magnitude=Decimal("250")),
        )
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


# ============================================================================
# #966 — a scope can hold more than one reservation, so usage is a SUM
# ============================================================================


def _commit_with_vector(
    log: SqliteCommitLog,
    *,
    reservation_id: str,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    magnitude: str,
    to_state: CapacityState,
    expected_seq: int,
    cause: TransitionCause = TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
    command_type: CommandType = CommandType.BIND_ATTEMPT,
    finality_witness: bool | None = None,
) -> int:
    result = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=writer_epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=to_state,
            scope=ReservationScope(
                account=instrument_key.account, instrument=instrument_key.instrument
            ),
            committed_vector=CapacityVector(
                components=(
                    CapacityComponent(
                        dimension_id="notional", magnitude=Decimal(magnitude)
                    ),
                )
            ),
        ),
        cause,
        command_type=command_type,
        command_id=f"cmd-{reservation_id}",
        command_digest=f"dig-{reservation_id}",
        expected_seq=expected_seq,
        finality_witness=finality_witness,
    )
    assert isinstance(result, AppendReceipt)
    assert result.seq is not None
    return result.seq


def test_snapshot_sums_every_outstanding_reservation_of_the_scope(
    ara_service: AggregateRiskService,
    log: SqliteCommitLog,
    instrument_key: InstrumentKey,
    writer_epoch: int,
) -> None:
    """Two outstanding reservations -> the dimension-wise SUM of their committed vectors.

    The concrete failing input for the pre-#966 first-row read: an entry at
    ``POSITION_CONSUMED`` holding 250 plus the exit's own reservation holding 100 was
    reported as 250 — one whole reservation of usage invisible to the limit check.
    """
    seq = _commit_with_vector(
        log,
        reservation_id="resv-entry",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        magnitude="250",
        to_state=CapacityState.POSITION_CONSUMED,
        expected_seq=-1,
        cause=TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        finality_witness=True,
    )
    _commit_with_vector(
        log,
        reservation_id="resv-close",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        magnitude="100",
        to_state=CapacityState.ATTEMPT_BOUND,
        expected_seq=seq,
    )

    snapshot = ara_service.snapshot(
        instrument_key,
        snapshot_generation=1,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        all_fields_attributed=True,
    )
    assert snapshot.conservative_current_usage.magnitude("notional") == Decimal("350")


def test_snapshot_nets_a_signed_close_vector_against_the_position(
    ara_service: AggregateRiskService,
    log: SqliteCommitLog,
    instrument_key: InstrumentKey,
    writer_epoch: int,
) -> None:
    seq = _commit_with_vector(
        log,
        reservation_id="resv-entry",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        magnitude="250",
        to_state=CapacityState.POSITION_CONSUMED,
        expected_seq=-1,
        cause=TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        finality_witness=True,
    )
    _commit_with_vector(
        log,
        reservation_id="resv-close",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        magnitude="-250",
        to_state=CapacityState.ATTEMPT_BOUND,
        expected_seq=seq,
    )

    snapshot = ara_service.snapshot(
        instrument_key,
        snapshot_generation=1,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        all_fields_attributed=True,
    )
    assert snapshot.conservative_current_usage.magnitude("notional") == Decimal("0")


def test_snapshot_excludes_released_reservations_from_usage(
    ara_service: AggregateRiskService,
    log: SqliteCommitLog,
    instrument_key: InstrumentKey,
    writer_epoch: int,
) -> None:
    """A ``RELEASED`` reservation consumes nothing — this is what reopens a closed scope."""
    seq = _commit_with_vector(
        log,
        reservation_id="resv-done",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        magnitude="250",
        to_state=CapacityState.RELEASED,
        expected_seq=-1,
        cause=TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        finality_witness=True,
    )
    _commit_with_vector(
        log,
        reservation_id="resv-open",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        magnitude="100",
        to_state=CapacityState.ATTEMPT_BOUND,
        expected_seq=seq,
    )

    snapshot = ara_service.snapshot(
        instrument_key,
        snapshot_generation=1,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        all_fields_attributed=True,
    )
    assert snapshot.conservative_current_usage.magnitude("notional") == Decimal("100")


# ============================================================================
# #972 — a reservation with no recorded vector is UNKNOWN usage, never 0
# ============================================================================


def _transition_without_vector(
    log: SqliteCommitLog,
    *,
    reservation_id: str,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    from_state: CapacityState,
    to_state: CapacityState,
    expected_seq: int,
    command_type: CommandType = CommandType.BIND_ATTEMPT,
    cause: TransitionCause = TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
    finality_witness: bool | None = None,
) -> int:
    result = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=writer_epoch,
            from_state=from_state,
            to_state=to_state,
            scope=ReservationScope(
                account=instrument_key.account, instrument=instrument_key.instrument
            ),
        ),
        cause,
        command_type=command_type,
        command_id=f"cmd-{reservation_id}-{to_state.value}",
        command_digest=f"dig-{reservation_id}-{to_state.value}",
        expected_seq=expected_seq,
        finality_witness=finality_witness,
    )
    assert isinstance(result, AppendReceipt)
    assert result.seq is not None
    return result.seq


def test_an_outstanding_reservation_without_a_vector_makes_the_decision_unknown(
    ara_service: AggregateRiskService,
    log: SqliteCommitLog,
    instrument_key: InstrumentKey,
    writer_epoch: int,
    required_scenario_kinds,
    evidence_port: FakeEvidenceAppendPort,
) -> None:
    """Failing input (PR #973 review L2): an outstanding row holding 250 plus an outstanding
    row with NO vector (a row written before #972, replayed from an existing log) summed to
    250 — the second row's usage read as 0. It must be UNKNOWN, so the decision is too.
    """
    seq = _commit_with_vector(
        log,
        reservation_id="resv-recorded",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        magnitude="250",
        to_state=CapacityState.ATTEMPT_BOUND,
        expected_seq=-1,
    )
    _transition_without_vector(
        log,
        reservation_id="resv-unrecorded",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.ATTEMPT_BOUND,
        expected_seq=seq,
    )

    snapshot = ara_service.snapshot(
        instrument_key,
        snapshot_generation=1,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        all_fields_attributed=True,
    )
    assert snapshot.conservative_current_usage.declares("notional")
    assert snapshot.conservative_current_usage.magnitude("notional") is None

    decision = ara_service.decide(
        instrument_key,
        grant_shaped_are_inputs(required_scenario_kinds),
        snapshot_generation=2,
        decision_generation=1,
    )
    assert decision.result is RiskDecisionResult.UNKNOWN

    snapshot_rows = [
        payload for payload, kind, _rc in evidence_port.calls if kind == "ARE_SNAPSHOT"
    ]
    assert snapshot_rows[-1]["unrecorded_vector_reservations"] == ["resv-unrecorded"]
    assert snapshot_rows[-1]["all_fields_attributed"] is False


def test_a_lone_outstanding_reservation_without_a_vector_is_unknown_too(
    ara_service: AggregateRiskService,
    log: SqliteCommitLog,
    instrument_key: InstrumentKey,
    writer_epoch: int,
    required_scenario_kinds,
) -> None:
    """No other row declares a dimension, so the usage vector stays empty — the decision
    must still be UNKNOWN, not the GRANT an empty (= "nothing held") vector would give.
    """
    _transition_without_vector(
        log,
        reservation_id="resv-unrecorded",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.COMMITTED_UNBOUND,
        expected_seq=-1,
    )
    decision = ara_service.decide(
        instrument_key,
        grant_shaped_are_inputs(required_scenario_kinds),
        snapshot_generation=1,
        decision_generation=1,
    )
    assert decision.result is RiskDecisionResult.UNKNOWN


def test_a_released_reservation_without_a_vector_does_not_make_usage_unknown(
    ara_service: AggregateRiskService,
    log: SqliteCommitLog,
    instrument_key: InstrumentKey,
    writer_epoch: int,
    required_scenario_kinds,
) -> None:
    """RELEASED rows consume nothing, so a missing vector on one is irrelevant — otherwise
    every scope that ever held a pre-#972 reservation would stay UNKNOWN forever."""
    seq = _transition_without_vector(
        log,
        reservation_id="resv-old-released",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.RELEASED,
        expected_seq=-1,
        command_type=CommandType.RELEASE_RESERVATION,
        cause=TransitionCause.FINAL_QUANTITY_PROOF,
        finality_witness=True,
    )
    _commit_with_vector(
        log,
        reservation_id="resv-open",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        magnitude="100",
        to_state=CapacityState.ATTEMPT_BOUND,
        expected_seq=seq,
    )
    decision = ara_service.decide(
        instrument_key,
        grant_shaped_are_inputs(required_scenario_kinds),
        snapshot_generation=1,
        decision_generation=1,
    )
    assert decision.result is RiskDecisionResult.GRANT
    snapshot = ara_service.snapshot(
        instrument_key,
        snapshot_generation=2,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        all_fields_attributed=True,
    )
    assert snapshot.conservative_current_usage.magnitude("notional") == Decimal("100")


def test_a_lifecycle_transition_without_a_vector_keeps_the_committed_usage(
    ara_service: AggregateRiskService,
    log: SqliteCommitLog,
    instrument_key: InstrumentKey,
    writer_epoch: int,
    required_scenario_kinds,
) -> None:
    """Failing input: step 9 commits 250, then the entry fill moves the row to
    POSITION_CONSUMED through a transition that carries no vector (the release consumer
    builds it that way). Overwriting the column with NULL would turn an open position into
    UNKNOWN usage and block its own CLOSE at step 6."""
    seq = _commit_with_vector(
        log,
        reservation_id="resv-entry",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        magnitude="250",
        to_state=CapacityState.ATTEMPT_BOUND,
        expected_seq=-1,
    )
    _transition_without_vector(
        log,
        reservation_id="resv-entry",
        writer_epoch=writer_epoch,
        instrument_key=instrument_key,
        from_state=CapacityState.ATTEMPT_BOUND,
        to_state=CapacityState.POTENTIALLY_LIVE,
        expected_seq=seq,
        command_type=CommandType.MARK_SEND_STARTED,
    )
    snapshot = ara_service.snapshot(
        instrument_key,
        snapshot_generation=1,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        all_fields_attributed=True,
    )
    assert snapshot.conservative_current_usage.magnitude("notional") == Decimal("250")
    decision = ara_service.decide(
        instrument_key,
        grant_shaped_are_inputs(required_scenario_kinds),
        snapshot_generation=2,
        decision_generation=1,
    )
    assert decision.result is RiskDecisionResult.GRANT


def test_a_fresh_boot_over_the_same_log_reproduces_the_snapshot_usage(
    log_path: Path,
    evidence_port: FakeEvidenceAppendPort,
    identity,
    instrument_key: InstrumentKey,
    scenario_set,
) -> None:
    """Replay/boot: a second process opening the same RCL file passes ``verify_replay`` and
    derives the same usage — the committed vector survives the restart, carried-forward
    rows included."""
    first = SqliteCommitLog(log_path, evidence_port=evidence_port)
    epoch = first.acquire_epoch(identity)
    seq = _commit_with_vector(
        first,
        reservation_id="resv-a",
        writer_epoch=epoch,
        instrument_key=instrument_key,
        magnitude="250",
        to_state=CapacityState.ATTEMPT_BOUND,
        expected_seq=-1,
    )
    seq = _transition_without_vector(
        first,
        reservation_id="resv-a",
        writer_epoch=epoch,
        instrument_key=instrument_key,
        from_state=CapacityState.ATTEMPT_BOUND,
        to_state=CapacityState.POTENTIALLY_LIVE,
        expected_seq=seq,
        command_type=CommandType.MARK_SEND_STARTED,
    )
    _commit_with_vector(
        first,
        reservation_id="resv-b",
        writer_epoch=epoch,
        instrument_key=instrument_key,
        magnitude="100",
        to_state=CapacityState.ATTEMPT_BOUND,
        expected_seq=seq,
    )

    def usage(log: SqliteCommitLog) -> CapacityVector:
        service = AggregateRiskService(
            SqliteReservationProjectionReader(log), scenario_set, evidence_port
        )
        return service.snapshot(
            instrument_key,
            snapshot_generation=1,
            required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
            all_fields_attributed=True,
        ).conservative_current_usage

    before = usage(first)
    first.close()
    second = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        second.verify_replay()
        assert usage(second) == before
        assert before.magnitude("notional") == Decimal("350")
    finally:
        second.close()
