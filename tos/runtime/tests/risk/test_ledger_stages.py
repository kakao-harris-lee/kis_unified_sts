"""Engine ``Stage`` realizations for steps 6-10 — tests (design #40 §5 order 5
item 3; slice plan §2 item 3 fault contracts)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from tos.afg import ActionAmplificationEnvelope
from tos.dsl import Proposal
from tos.engine.records import InstrumentKey, StageRequest
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass, StageOutcome
from tos.rcl import CapacityState
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.log import InjectedCrash, SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.risk.aggregate import AggregateRiskService
from tos_runtime.risk.flow import ActionFlowGovernor
from tos_runtime.risk.ledger_stages import (
    ActionFlowDecisionStage,
    AggregateRiskDecisionStage,
    AtomicCommitStage,
    CommitmentUnavailabilityStage,
    LedgerVerificationStage,
    item15_fields,
)

from .conftest import (
    CountingCommitLog,
    FakeEvidenceAppendPort,
    grant_shaped_afg_inputs,
    grant_shaped_are_inputs,
)


def _request(
    step: CommitmentStep,
    key: InstrumentKey,
    prior_verdicts: tuple = (),
) -> StageRequest:
    return StageRequest(
        step=step,
        instrument_key=key,
        proposal=Proposal(),
        prior_verdicts=prior_verdicts,
    )


def _committed_permit(afg_governor: ActionFlowGovernor):
    decision = afg_governor.decide(grant_shaped_afg_inputs())
    return afg_governor.build_permit(
        decision, permit_generation=1, command_identity="cmd-1"
    )


# ============================================================================
# step 6 — AggregateRiskDecisionStage
# ============================================================================


def test_step6_admits_on_a_granted_decision(
    ara_service: AggregateRiskService,
    instrument_key: InstrumentKey,
    required_scenario_kinds,
) -> None:
    stage = AggregateRiskDecisionStage(
        ara_service,
        inputs_provider=lambda _r: grant_shaped_are_inputs(required_scenario_kinds),
        snapshot_generation_provider=lambda _r: 1,
        decision_generation_provider=lambda _r: 1,
        time_permits_new_risk=lambda: True,
    )
    verdict = stage(_request(CommitmentStep.AGGREGATE_RISK_DECISION, instrument_key))
    assert verdict.outcome is StageOutcome.ADMIT
    assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE


def test_step6_is_unknown_when_no_inputs_are_available(
    ara_service: AggregateRiskService, instrument_key: InstrumentKey
) -> None:
    stage = AggregateRiskDecisionStage(
        ara_service,
        inputs_provider=lambda _r: None,
        snapshot_generation_provider=lambda _r: 1,
        decision_generation_provider=lambda _r: 1,
        time_permits_new_risk=lambda: True,
    )
    verdict = stage(_request(CommitmentStep.AGGREGATE_RISK_DECISION, instrument_key))
    assert verdict.outcome is StageOutcome.UNKNOWN
    assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE


def test_step6_is_unknown_when_time_does_not_permit_new_risk(
    ara_service: AggregateRiskService,
    instrument_key: InstrumentKey,
    required_scenario_kinds,
) -> None:
    stage = AggregateRiskDecisionStage(
        ara_service,
        inputs_provider=lambda _r: grant_shaped_are_inputs(required_scenario_kinds),
        snapshot_generation_provider=lambda _r: 1,
        decision_generation_provider=lambda _r: 1,
        time_permits_new_risk=lambda: False,
    )
    verdict = stage(_request(CommitmentStep.AGGREGATE_RISK_DECISION, instrument_key))
    assert verdict.outcome is StageOutcome.UNKNOWN


def test_step6_is_unknown_when_the_rcl_projection_is_unreachable(
    ara_service: AggregateRiskService,
    instrument_key: InstrumentKey,
    required_scenario_kinds,
    log: SqliteCommitLog,
) -> None:
    log.close()
    stage = AggregateRiskDecisionStage(
        ara_service,
        inputs_provider=lambda _r: grant_shaped_are_inputs(required_scenario_kinds),
        snapshot_generation_provider=lambda _r: 1,
        decision_generation_provider=lambda _r: 1,
        time_permits_new_risk=lambda: True,
    )
    verdict = stage(_request(CommitmentStep.AGGREGATE_RISK_DECISION, instrument_key))
    assert verdict.outcome is StageOutcome.UNKNOWN


def test_step6_never_admits_when_evidence_append_fails(
    ara_service: AggregateRiskService,
    instrument_key: InstrumentKey,
    required_scenario_kinds,
    evidence_port: FakeEvidenceAppendPort,
) -> None:
    """Evidence is appended (inside ``decide()``) before ``risk_decision``'s
    result is ever returned to the caller — an append failure means the
    stage NEVER reaches ADMIT for this attempt."""
    evidence_port.fail_next_append(RuntimeError("evidence store down"))
    stage = AggregateRiskDecisionStage(
        ara_service,
        inputs_provider=lambda _r: grant_shaped_are_inputs(required_scenario_kinds),
        snapshot_generation_provider=lambda _r: 1,
        decision_generation_provider=lambda _r: 1,
        time_permits_new_risk=lambda: True,
    )
    verdict = stage(_request(CommitmentStep.AGGREGATE_RISK_DECISION, instrument_key))
    assert verdict.outcome is StageOutcome.UNKNOWN


# ============================================================================
# step 7 — ActionFlowDecisionStage
# ============================================================================


def test_step7_admits_on_a_granted_decision(
    afg_governor: ActionFlowGovernor, instrument_key: InstrumentKey
) -> None:
    stage = ActionFlowDecisionStage(
        afg_governor,
        inputs_provider=lambda _r: grant_shaped_afg_inputs(),
        time_permits_new_risk=lambda: True,
    )
    verdict = stage(_request(CommitmentStep.ACTION_FLOW_DECISION, instrument_key))
    assert verdict.outcome is StageOutcome.ADMIT
    assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE


def test_step7_is_unknown_when_time_does_not_permit_new_risk(
    afg_governor: ActionFlowGovernor, instrument_key: InstrumentKey
) -> None:
    stage = ActionFlowDecisionStage(
        afg_governor,
        inputs_provider=lambda _r: grant_shaped_afg_inputs(),
        time_permits_new_risk=lambda: False,
    )
    verdict = stage(_request(CommitmentStep.ACTION_FLOW_DECISION, instrument_key))
    assert verdict.outcome is StageOutcome.UNKNOWN


# ============================================================================
# step 8 — LedgerVerificationStage
# ============================================================================


def test_step8_admits_a_fresh_scope(
    log: SqliteCommitLog,
    projection_reader: SqliteReservationProjectionReader,
    writer_epoch: int,
    instrument_key: InstrumentKey,
) -> None:
    stage = LedgerVerificationStage(log, projection_reader, writer_epoch=writer_epoch)
    verdict = stage(_request(CommitmentStep.LEDGER_VERIFICATION, instrument_key))
    assert verdict.outcome is StageOutcome.ADMIT
    assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE


def test_step8_denies_an_already_occupied_scope(
    log: SqliteCommitLog,
    projection_reader: SqliteReservationProjectionReader,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    permit = _committed_permit(afg_governor)
    commit_stage = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    commit_verdict = commit_stage(
        _request(CommitmentStep.ATOMIC_COMMIT, instrument_key)
    )
    assert commit_verdict.outcome is StageOutcome.ADMIT

    stage = LedgerVerificationStage(log, projection_reader, writer_epoch=writer_epoch)
    verdict = stage(_request(CommitmentStep.LEDGER_VERIFICATION, instrument_key))
    assert verdict.outcome is StageOutcome.DENY
    assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE


def test_step8_is_unknown_when_the_log_file_is_inaccessible(
    log: SqliteCommitLog,
    projection_reader: SqliteReservationProjectionReader,
    writer_epoch: int,
    instrument_key: InstrumentKey,
) -> None:
    log.close()
    stage = LedgerVerificationStage(log, projection_reader, writer_epoch=writer_epoch)
    verdict = stage(_request(CommitmentStep.LEDGER_VERIFICATION, instrument_key))
    assert verdict.outcome is StageOutcome.UNKNOWN


def test_step8_is_unknown_on_a_stale_writer_epoch(
    log_path: Path,
    evidence_port: FakeEvidenceAppendPort,
    identity: RuntimeIdentity,
    instrument_key: InstrumentKey,
) -> None:
    first = SqliteCommitLog(log_path, evidence_port=evidence_port)
    second = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        stale_epoch = first.acquire_epoch(identity)
        second.acquire_epoch(identity)  # fences `first`'s epoch as stale
        reader = SqliteReservationProjectionReader(first)
        stage = LedgerVerificationStage(first, reader, writer_epoch=stale_epoch)
        verdict = stage(_request(CommitmentStep.LEDGER_VERIFICATION, instrument_key))
        assert verdict.outcome is StageOutcome.UNKNOWN
    finally:
        first.close()
        second.close()


# ============================================================================
# step 9 — AtomicCommitStage
# ============================================================================


def test_step9_commits_reservation_and_permit_in_one_transaction(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
    projection_reader: SqliteReservationProjectionReader,
) -> None:
    permit = _committed_permit(afg_governor)
    stage = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    verdict = stage(_request(CommitmentStep.ATOMIC_COMMIT, instrument_key))
    assert verdict.outcome is StageOutcome.ADMIT
    assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE
    assert verdict.bound_digest == permit.canonical_digest
    assert verdict.bound_identity == permit.permit_id
    assert (
        projection_reader.instrument_state(instrument_key)
        is CapacityState.COMMITTED_UNBOUND
    )


def test_step9_commits_via_exactly_one_commit_entry_call(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    """Pins the module docstring's "ONE apply_reservation_transition call,
    never split into two transactions" invariant: a mutation splitting the
    step-9 commit into two separate calls (reservation first, nonce/digest
    binding second) must fail this test, even though every *outcome*-level
    assertion elsewhere in this file would still pass (independent review
    MEDIUM, 2026-09-08)."""
    permit = _committed_permit(afg_governor)
    counting_log = CountingCommitLog(log)
    stage = AtomicCommitStage(
        counting_log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    verdict = stage(_request(CommitmentStep.ATOMIC_COMMIT, instrument_key))
    assert verdict.outcome is StageOutcome.ADMIT
    assert counting_log.total_commit_calls == 1
    assert counting_log.apply_reservation_transition_calls == 1
    assert counting_log.append_cas_calls == 0


def test_step9_single_entry_carries_both_the_reservation_and_the_permit_binding(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    """Independent content check (not the call-count wrapper above): exactly
    ONE row exists in ``entries`` for this attempt, and that ONE row's
    ``command_id``/``command_digest`` (the permit's single-use claim) sit on
    the SAME entry as the reservation transition's own
    ``is_reservation_transition=1``/scope/state — a two-call split would
    either leave two ``entries`` rows (caught by the ``COUNT(*)`` check) or a
    reservation row whose commit fields never proved they came from ONE
    transaction (independent review MEDIUM, 2026-09-08)."""
    permit = _committed_permit(afg_governor)
    stage = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    verdict = stage(_request(CommitmentStep.ATOMIC_COMMIT, instrument_key))
    assert verdict.outcome is StageOutcome.ADMIT

    (entry_count,) = log._conn.execute("SELECT COUNT(*) FROM entries").fetchone()
    assert entry_count == 1

    row = log._conn.execute(
        "SELECT e.command_id, e.command_digest, e.is_reservation_transition, "
        "r.reservation_id, r.state, r.scope_account, r.scope_instrument "
        "FROM entries e JOIN reservations r ON r.last_seq = e.seq "
        "WHERE r.reservation_id = ?",
        ("reservation-1",),
    ).fetchone()
    assert row is not None
    (
        command_id,
        command_digest,
        is_reservation_transition,
        reservation_id,
        state,
        scope_account,
        scope_instrument,
    ) = row
    assert command_id == permit.claim_nonce
    assert command_digest == permit.canonical_digest
    assert is_reservation_transition == 1
    assert reservation_id == "reservation-1"
    assert state == CapacityState.COMMITTED_UNBOUND.value
    assert scope_account == instrument_key.account
    assert scope_instrument == instrument_key.instrument


def test_step9_is_unknown_when_no_permit_is_available(
    log: SqliteCommitLog, writer_epoch: int, instrument_key: InstrumentKey
) -> None:
    stage = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: None,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    verdict = stage(_request(CommitmentStep.ATOMIC_COMMIT, instrument_key))
    assert verdict.outcome is StageOutcome.UNKNOWN


def test_step9_is_unknown_when_time_does_not_permit_new_risk(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    permit = _committed_permit(afg_governor)
    stage = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: False,
    )
    verdict = stage(_request(CommitmentStep.ATOMIC_COMMIT, instrument_key))
    assert verdict.outcome is StageOutcome.UNKNOWN


def test_step9_denies_a_permit_claimed_twice(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    permit = _committed_permit(afg_governor)
    stage_a = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    first = stage_a(_request(CommitmentStep.ATOMIC_COMMIT, instrument_key))
    assert first.outcome is StageOutcome.ADMIT

    other_key = InstrumentKey(account="acct-2", instrument="202S07")
    stage_b = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,  # SAME permit, different scope
        reservation_id_provider=lambda _r: "reservation-2",
        time_permits_new_risk=lambda: True,
    )
    second = stage_b(_request(CommitmentStep.ATOMIC_COMMIT, other_key))
    assert second.outcome is StageOutcome.DENY


def test_step9_denies_a_permit_claimed_twice_even_after_a_simulated_restart(
    log: SqliteCommitLog,
    log_path: Path,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    permit = _committed_permit(afg_governor)
    stage_a = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    first = stage_a(_request(CommitmentStep.ATOMIC_COMMIT, instrument_key))
    assert first.outcome is StageOutcome.ADMIT
    log.close()

    reopened = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        other_key = InstrumentKey(account="acct-2", instrument="202S07")
        stage_b = AtomicCommitStage(
            reopened,
            writer_epoch=writer_epoch,
            permit_provider=lambda _r: permit,
            reservation_id_provider=lambda _r: "reservation-2",
            time_permits_new_risk=lambda: True,
        )
        second = stage_b(_request(CommitmentStep.ATOMIC_COMMIT, other_key))
        assert second.outcome is StageOutcome.DENY
    finally:
        reopened.close()


def test_step9_is_unknown_when_the_log_file_is_inaccessible(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    permit = _committed_permit(afg_governor)
    log.close()
    stage = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    verdict = stage(_request(CommitmentStep.ATOMIC_COMMIT, instrument_key))
    assert verdict.outcome is StageOutcome.UNKNOWN


def test_step9_atomic_commit_leaves_neither_reservation_nor_permit_on_a_crash_before_commit(
    log_path: Path,
    evidence_port: FakeEvidenceAppendPort,
    identity: RuntimeIdentity,
    instrument_key: InstrumentKey,
) -> None:
    """Crash injection immediately before COMMIT: the whole attempt leaves
    NEITHER the reservation NOR the permit's commitment coordinate durable —
    never a partial state (all-or-nothing)."""

    def crash_before_commit(point: str) -> None:
        if point == "before_commit":
            raise InjectedCrash("simulated crash before commit")

    crashing_log = SqliteCommitLog(
        log_path, evidence_port=evidence_port, crash_hook=crash_before_commit
    )
    epoch = crashing_log.acquire_epoch(identity)
    envelope_evidence = FakeEvidenceAppendPort()
    envelope = ActionAmplificationEnvelope(
        max_fan_out=10,
        max_depth=10,
        max_attempts=5,
        max_mutations=5,
        max_queries=5,
        max_queue_depth=100,
        max_in_flight=10,
        max_elapsed_monotonic=Decimal("1000"),
        max_duplicate_redelivery_expansion=3,
        max_failover_reconnect_replay_expansion=3,
        max_amplification_per_cause=Decimal("100"),
    )
    governor = ActionFlowGovernor(
        crashing_log, envelope_evidence, envelope, writer_epoch=epoch
    )
    permit = _committed_permit(governor)

    stage = AtomicCommitStage(
        crashing_log,
        writer_epoch=epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    with pytest.raises(InjectedCrash):
        stage(_request(CommitmentStep.ATOMIC_COMMIT, instrument_key))
    crashing_log.close()

    reopened = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        assert list(reopened.replay()) == []
        reader = SqliteReservationProjectionReader(reopened)
        assert reader.instrument_state(instrument_key) is None
        assert dict(reader.all_reservations()) == {}

        # Nothing leaked: the SAME permit's nonce was never durably claimed by
        # the crashed attempt, so a fresh stage call over the reopened log can
        # still claim it (proving the crash consumed no single-use state).
        retry_stage = AtomicCommitStage(
            reopened,
            writer_epoch=epoch,
            permit_provider=lambda _r: permit,
            reservation_id_provider=lambda _r: "reservation-1",
            time_permits_new_risk=lambda: True,
        )
        retry_verdict = retry_stage(
            _request(CommitmentStep.ATOMIC_COMMIT, instrument_key)
        )
        assert retry_verdict.outcome is StageOutcome.ADMIT
    finally:
        reopened.close()


# ============================================================================
# step 10 — CommitmentUnavailabilityStage
# ============================================================================


def test_step10_confirms_a_durable_commit(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
    projection_reader: SqliteReservationProjectionReader,
) -> None:
    permit = _committed_permit(afg_governor)
    commit_stage = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    commit_verdict = commit_stage(
        _request(CommitmentStep.ATOMIC_COMMIT, instrument_key)
    )
    assert commit_verdict.outcome is StageOutcome.ADMIT

    stage = CommitmentUnavailabilityStage(projection_reader)
    verdict = stage(
        _request(
            CommitmentStep.COMMITMENT_UNAVAILABILITY,
            instrument_key,
            prior_verdicts=(commit_verdict,),
        )
    )
    assert verdict.outcome is StageOutcome.ADMIT
    assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE


def test_step10_is_unknown_without_an_admitted_step9_verdict(
    projection_reader: SqliteReservationProjectionReader, instrument_key: InstrumentKey
) -> None:
    stage = CommitmentUnavailabilityStage(projection_reader)
    verdict = stage(_request(CommitmentStep.COMMITMENT_UNAVAILABILITY, instrument_key))
    assert verdict.outcome is StageOutcome.UNKNOWN


def test_step10_is_unknown_when_the_projection_is_unreachable(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
    projection_reader: SqliteReservationProjectionReader,
) -> None:
    permit = _committed_permit(afg_governor)
    commit_stage = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    commit_verdict = commit_stage(
        _request(CommitmentStep.ATOMIC_COMMIT, instrument_key)
    )
    log.close()

    stage = CommitmentUnavailabilityStage(projection_reader)
    verdict = stage(
        _request(
            CommitmentStep.COMMITMENT_UNAVAILABILITY,
            instrument_key,
            prior_verdicts=(commit_verdict,),
        )
    )
    assert verdict.outcome is StageOutcome.UNKNOWN


# ============================================================================
# item15_fields
# ============================================================================


def test_item15_fields_carries_permit_identity_and_commitment_current(
    afg_governor: ActionFlowGovernor,
) -> None:
    permit = _committed_permit(afg_governor)
    fields = item15_fields(permit, commitment_current=True)
    assert fields == {
        "action_flow_permit_identity": permit.permit_id,
        "action_flow_commitment_current": True,
    }


def test_item15_fields_is_none_shaped_without_a_permit() -> None:
    fields = item15_fields(None, commitment_current=None)
    assert fields == {
        "action_flow_permit_identity": None,
        "action_flow_commitment_current": None,
    }


# ============================================================================
# cross-cutting — authority_class is never NON_AUTHORITATIVE_PROVISIONAL
# ============================================================================


def test_no_stage_here_ever_emits_non_authoritative_provisional(
    ara_service: AggregateRiskService,
    afg_governor: ActionFlowGovernor,
    log: SqliteCommitLog,
    projection_reader: SqliteReservationProjectionReader,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    required_scenario_kinds,
) -> None:
    are_stage = AggregateRiskDecisionStage(
        ara_service,
        inputs_provider=lambda _r: grant_shaped_are_inputs(required_scenario_kinds),
        snapshot_generation_provider=lambda _r: 1,
        decision_generation_provider=lambda _r: 1,
        time_permits_new_risk=lambda: True,
    )
    afg_stage = ActionFlowDecisionStage(
        afg_governor,
        inputs_provider=lambda _r: grant_shaped_afg_inputs(),
        time_permits_new_risk=lambda: True,
    )
    ledger_stage = LedgerVerificationStage(
        log, projection_reader, writer_epoch=writer_epoch
    )
    permit = _committed_permit(afg_governor)
    commit_stage = AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _r: permit,
        reservation_id_provider=lambda _r: "reservation-1",
        time_permits_new_risk=lambda: True,
    )
    unavailability_stage = CommitmentUnavailabilityStage(projection_reader)

    v6 = are_stage(_request(CommitmentStep.AGGREGATE_RISK_DECISION, instrument_key))
    v7 = afg_stage(_request(CommitmentStep.ACTION_FLOW_DECISION, instrument_key))
    v8 = ledger_stage(_request(CommitmentStep.LEDGER_VERIFICATION, instrument_key))
    v9 = commit_stage(_request(CommitmentStep.ATOMIC_COMMIT, instrument_key))
    v10 = unavailability_stage(
        _request(
            CommitmentStep.COMMITMENT_UNAVAILABILITY,
            instrument_key,
            prior_verdicts=(v9,),
        )
    )
    for verdict in (v6, v7, v8, v9, v10):
        assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE
        assert (
            verdict.authority_class
            is not StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL
        )
