"""``IntentRegistry`` + ``load_operator_approval_file`` tests (design #40 §5"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.iap import ApprovalResult, ConsumptionOutcome, ConsumptionStatus
from tos.rcl import AppendReceipt, CommandType, CommitEntry
from tos.time import HealthState
from tos.workload import RuntimeIdentity
from tos_runtime.authority.iap import (
    IntentRegistry,
    OperatorApprovalFileError,
    _consumption_command_id,
    load_operator_approval_file,
    load_operator_approval_with_receipt,
)
from tos_runtime.rcl.log import CommitLogCorruption, SqliteCommitLog
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TrustworthyTimeService

from .conftest import (
    FakeEvidenceAppendPort,
    FakeMonotonicSource,
    FakeReferenceReader,
    FakeTimeService,
    _time_config,
    expiry_snapshot,
    write_approval_file,
)


@pytest.mark.parametrize("result", ["APPROVE", "DENY", "UNKNOWN"])
def test_loader_passes_the_operators_result_verbatim(
    approvals_dir: Path, expected_owner_uid: int, result: str
) -> None:
    path = write_approval_file(
        approvals_dir / "p1.yaml", decision_id="d1", result=result
    )
    decision = load_operator_approval_file(
        path,
        expected_owner_uid=expected_owner_uid,
        environment_label="non-live-test",
    )
    assert decision.result is ApprovalResult(result)
    assert decision.decision_id == "d1"


def test_loader_refuses_named_tbd_placeholder_decision_id(
    approvals_dir: Path, expected_owner_uid: int
) -> None:
    """W-A A-0 round 2 (kernel round #4 재심 BLOCKER): decision_id/request_id/"""
    path = write_approval_file(approvals_dir / "p1.yaml", decision_id="TBD")
    with pytest.raises(OperatorApprovalFileError, match="template placeholder"):
        load_operator_approval_file(
            path,
            expected_owner_uid=expected_owner_uid,
            environment_label="non-live-test",
        )


def test_loader_refuses_mode_0644(approvals_dir: Path, expected_owner_uid: int) -> None:
    path = write_approval_file(approvals_dir / "p1.yaml", mode=0o644)
    with pytest.raises(OperatorApprovalFileError):
        load_operator_approval_file(
            path,
            expected_owner_uid=expected_owner_uid,
            environment_label="non-live-test",
        )


def test_loader_refuses_owner_mismatch(
    approvals_dir: Path, expected_owner_uid: int
) -> None:
    path = write_approval_file(approvals_dir / "p1.yaml")
    with pytest.raises(OperatorApprovalFileError):
        load_operator_approval_file(
            path,
            expected_owner_uid=expected_owner_uid + 1,
            environment_label="non-live-test",
            getuid=lambda: expected_owner_uid,
        )


def test_loader_refuses_environment_label_mismatch(
    approvals_dir: Path, expected_owner_uid: int
) -> None:
    path = write_approval_file(approvals_dir / "p1.yaml", environment_label="paper")
    with pytest.raises(OperatorApprovalFileError):
        load_operator_approval_file(
            path,
            expected_owner_uid=expected_owner_uid,
            environment_label="non-live-test",
        )


def test_loader_never_opens_the_file_before_the_custody_gate(
    approvals_dir: Path, expected_owner_uid: int
) -> None:
    """Mirrors custody's own LOW-1 discipline: a mode/owner refusal happens"""
    path = write_approval_file(approvals_dir / "p1.yaml", mode=0o644)
    path.write_bytes(b"not even valid yaml: [[[")
    with pytest.raises(OperatorApprovalFileError):
        load_operator_approval_file(
            path,
            expected_owner_uid=expected_owner_uid,
            environment_label="non-live-test",
        )


def test_loader_refuses_a_non_null_max_decision_age_ms(
    approvals_dir: Path, expected_owner_uid: int
) -> None:
    """Kernel round #1 §2.2 relaxed this to a conditional check (issued_at"""
    path = write_approval_file(
        approvals_dir / "p1.yaml", decision_id="d1", max_decision_age_ms=60_000
    )
    with pytest.raises(
        OperatorApprovalFileError, match="load_operator_approval_with_receipt"
    ):
        load_operator_approval_file(
            path,
            expected_owner_uid=expected_owner_uid,
            environment_label="non-live-test",
        )


def test_loader_accepts_a_null_max_decision_age_ms(
    approvals_dir: Path, expected_owner_uid: int
) -> None:
    path = write_approval_file(
        approvals_dir / "p1.yaml", decision_id="d1", max_decision_age_ms=None
    )
    decision = load_operator_approval_file(
        path, expected_owner_uid=expected_owner_uid, environment_label="non-live-test"
    )
    assert decision.max_decision_age_ms is None


def _decision(
    intent_registry: IntentRegistry, approvals_dir: Path, expected_owner_uid: int
):
    path = write_approval_file(
        approvals_dir / "p1.yaml", decision_id="d1", result="APPROVE"
    )
    return load_operator_approval_file(
        path, expected_owner_uid=expected_owner_uid, environment_label="non-live-test"
    )


def test_first_consumption_admits_consumed_new(
    intent_registry: IntentRegistry, approvals_dir: Path, expected_owner_uid: int
) -> None:
    decision = _decision(intent_registry, approvals_dir, expected_owner_uid)
    result = intent_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    assert result.outcome is ConsumptionOutcome.CONSUMED_NEW
    assert result.status is ConsumptionStatus.CONSUMED
    assert result.record is not None


def test_repeat_identical_command_is_idempotent_replay(
    intent_registry: IntentRegistry, approvals_dir: Path, expected_owner_uid: int
) -> None:
    decision = _decision(intent_registry, approvals_dir, expected_owner_uid)
    first = intent_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    assert first.outcome is ConsumptionOutcome.CONSUMED_NEW

    second = intent_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    assert second.outcome is ConsumptionOutcome.IDEMPOTENT_REPLAY


def test_conflicting_second_command_is_rejected(
    intent_registry: IntentRegistry, approvals_dir: Path, expected_owner_uid: int
) -> None:
    decision = _decision(intent_registry, approvals_dir, expected_owner_uid)
    first = intent_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    assert first.outcome is ConsumptionOutcome.CONSUMED_NEW

    second = intent_registry.consume(
        decision,
        command_identity="cmd-2",
        command_digest="digest-DIFFERENT",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    assert second.outcome is ConsumptionOutcome.REJECTED_CONFLICT
    assert second.record is None


def test_ineligible_decision_never_reaches_the_log(
    intent_registry: IntentRegistry, approvals_dir: Path, expected_owner_uid: int
) -> None:
    """decision_current=False (or an envelope mismatch) is REJECTED_INELIGIBLE"""
    decision = _decision(intent_registry, approvals_dir, expected_owner_uid)
    refused = intent_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=False,
        approved_intent_envelope_equivalent=True,
    )
    assert refused.outcome is ConsumptionOutcome.REJECTED_INELIGIBLE
    assert refused.record is None

    admitted = intent_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    assert admitted.outcome is ConsumptionOutcome.CONSUMED_NEW


def test_binding_mismatch_denies_via_exact_binding_holds_before_any_log_write(
    intent_registry: IntentRegistry, approvals_dir: Path, expected_owner_uid: int
) -> None:
    decision = _decision(intent_registry, approvals_dir, expected_owner_uid)
    refused = intent_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
        bound_chain={"a": "x"},
        actual_chain={"a": "y"},
    )
    assert refused.outcome is ConsumptionOutcome.REJECTED_INELIGIBLE
    assert refused.record is None

    admitted = intent_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    assert admitted.outcome is ConsumptionOutcome.CONSUMED_NEW


def test_double_consume_refused_across_a_recreated_registry(
    log_path: Path,
    log: SqliteCommitLog,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    """A brand-new IntentRegistry over the SAME log (simulated restart — no"""
    first_registry = IntentRegistry(
        log,
        evidence_port,
        writer_epoch=writer_epoch,
        trading_approval_policy_generation=1,
    )
    decision = _decision(first_registry, approvals_dir, expected_owner_uid)
    first = first_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    assert first.outcome is ConsumptionOutcome.CONSUMED_NEW

    second_log = SqliteCommitLog(log_path, evidence_port=FakeEvidenceAppendPort())
    try:
        second_registry = IntentRegistry(
            second_log,
            FakeEvidenceAppendPort(),
            writer_epoch=writer_epoch,
            trading_approval_policy_generation=1,
        )
        second = second_registry.consume(
            decision,
            command_identity="cmd-2",
            command_digest="digest-DIFFERENT",
            decision_current=True,
            approved_intent_envelope_equivalent=True,
        )
        assert second.outcome is ConsumptionOutcome.REJECTED_CONFLICT

        replay = second_registry.consume(
            decision,
            command_identity="cmd-1",
            command_digest="digest-1",
            decision_current=True,
            approved_intent_envelope_equivalent=True,
        )
        assert replay.outcome is ConsumptionOutcome.IDEMPOTENT_REPLAY
    finally:
        second_log.close()


def test_decision_current_true_when_policy_generation_matches(
    intent_registry: IntentRegistry,
    approvals_dir: Path,
    expected_owner_uid: int,
    trading_approval_policy_generation: int,
) -> None:
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        request_id="proposal-1",
        decision_generation=1,
        trading_approval_policy_generation=trading_approval_policy_generation,
    )
    decision = load_operator_approval_file(
        path, expected_owner_uid=expected_owner_uid, environment_label="non-live-test"
    )
    assert intent_registry.decision_current(decision) is True


def test_decision_current_false_when_policy_generation_mismatches(
    intent_registry: IntentRegistry,
    approvals_dir: Path,
    expected_owner_uid: int,
    trading_approval_policy_generation: int,
) -> None:
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        request_id="proposal-1",
        decision_generation=1,
        trading_approval_policy_generation=trading_approval_policy_generation + 1,
    )
    decision = load_operator_approval_file(
        path, expected_owner_uid=expected_owner_uid, environment_label="non-live-test"
    )
    assert intent_registry.decision_current(decision) is False


def test_decision_current_none_when_decision_carries_no_generation(
    intent_registry: IntentRegistry, approvals_dir: Path, expected_owner_uid: int
) -> None:
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        request_id="proposal-1",
    )
    decision = load_operator_approval_file(
        path, expected_owner_uid=expected_owner_uid, environment_label="non-live-test"
    )
    assert decision.trading_approval_policy_generation is None
    assert intent_registry.decision_current(decision) is None


def test_decision_current_none_when_decision_carries_no_request_id(
    intent_registry: IntentRegistry,
    approvals_dir: Path,
    expected_owner_uid: int,
    trading_approval_policy_generation: int,
) -> None:
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        decision_generation=1,
        trading_approval_policy_generation=trading_approval_policy_generation,
    )
    decision = load_operator_approval_file(
        path, expected_owner_uid=expected_owner_uid, environment_label="non-live-test"
    )
    assert decision.request_id is None
    assert intent_registry.decision_current(decision) is None


def test_decision_current_false_when_superseded_by_a_later_consumed_decision(
    intent_registry: IntentRegistry,
    approvals_dir: Path,
    expected_owner_uid: int,
    trading_approval_policy_generation: int,
) -> None:
    """A later-generation decision for the SAME proposal, already consumed,"""
    older_path = write_approval_file(
        approvals_dir / "older.yaml",
        decision_id="d-older",
        request_id="proposal-1",
        decision_generation=1,
        trading_approval_policy_generation=trading_approval_policy_generation,
    )
    older = load_operator_approval_file(
        older_path,
        expected_owner_uid=expected_owner_uid,
        environment_label="non-live-test",
    )
    newer_path = write_approval_file(
        approvals_dir / "newer.yaml",
        decision_id="d-newer",
        request_id="proposal-1",
        decision_generation=2,
        trading_approval_policy_generation=trading_approval_policy_generation,
        supersedes_decision_id="d-older",
    )
    newer = load_operator_approval_file(
        newer_path,
        expected_owner_uid=expected_owner_uid,
        environment_label="non-live-test",
    )

    consumed = intent_registry.consume(
        newer,
        command_identity="cmd-newer",
        command_digest="digest-newer",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    assert consumed.outcome is ConsumptionOutcome.CONSUMED_NEW

    assert intent_registry.decision_current(older) is False
    assert intent_registry.decision_current(newer) is True


def test_decision_current_true_when_not_yet_superseded_by_anything_consumed(
    intent_registry: IntentRegistry,
    approvals_dir: Path,
    expected_owner_uid: int,
    trading_approval_policy_generation: int,
) -> None:
    """An unrelated proposal's consumption never affects this one's currency."""
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        request_id="proposal-1",
        decision_generation=1,
        trading_approval_policy_generation=trading_approval_policy_generation,
    )
    decision = load_operator_approval_file(
        path, expected_owner_uid=expected_owner_uid, environment_label="non-live-test"
    )
    other_path = write_approval_file(
        approvals_dir / "other.yaml",
        decision_id="d-other",
        request_id="proposal-OTHER",
        decision_generation=99,
        trading_approval_policy_generation=trading_approval_policy_generation,
    )
    other = load_operator_approval_file(
        other_path,
        expected_owner_uid=expected_owner_uid,
        environment_label="non-live-test",
    )
    intent_registry.consume(
        other,
        command_identity="cmd-other",
        command_digest="digest-other",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    assert intent_registry.decision_current(decision) is True


def test_consume_uses_the_new_consume_approval_decision_command_type(
    intent_registry: IntentRegistry,
    log: SqliteCommitLog,
    writer_epoch: int,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    """A newly-committed consumption is written under the new, dedicated"""
    path = write_approval_file(approvals_dir / "p1.yaml", decision_id="d1")
    decision = load_operator_approval_file(
        path, expected_owner_uid=expected_owner_uid, environment_label="non-live-test"
    )
    intent_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    view = log.read_linearizable(writer_epoch=writer_epoch)
    kinds = {entry.kind for entry in view.entries if entry.command_id is not None}
    assert CommandType.CONSUME_APPROVAL_DECISION in kinds
    assert CommandType.CONSUME_TRANSMISSION_CAPABILITY not in kinds


def test_consume_raises_on_a_legacy_kind_entry_at_the_same_command_id(
    intent_registry: IntentRegistry,
    log: SqliteCommitLog,
    writer_epoch: int,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    """A pre-existing entry at this decision's own consumption command-id,"""
    path = write_approval_file(approvals_dir / "p1.yaml", decision_id="d1")
    decision = load_operator_approval_file(
        path, expected_owner_uid=expected_owner_uid, environment_label="non-live-test"
    )
    legacy_entry = CommitEntry(
        command_id=_consumption_command_id(decision),
        command_digest="legacy-digest",
        kind=CommandType.CONSUME_TRANSMISSION_CAPABILITY,
    )
    receipt = log.append_cas(legacy_entry, expected_seq=-1, writer_epoch=writer_epoch)
    assert isinstance(receipt, AppendReceipt)

    with pytest.raises(CommitLogCorruption):
        intent_registry.consume(
            decision,
            command_identity="cmd-1",
            command_digest="digest-1",
            decision_current=True,
            approved_intent_envelope_equivalent=True,
        )


def test_decision_current_raises_on_a_legacy_kind_entry_under_the_supersession_prefix(
    intent_registry: IntentRegistry,
    log: SqliteCommitLog,
    writer_epoch: int,
    approvals_dir: Path,
    expected_owner_uid: int,
    trading_approval_policy_generation: int,
) -> None:
    """A later-generation entry under this proposal's own consumption prefix,"""
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        request_id="proposal-1",
        decision_generation=1,
        trading_approval_policy_generation=trading_approval_policy_generation,
    )
    decision = load_operator_approval_file(
        path, expected_owner_uid=expected_owner_uid, environment_label="non-live-test"
    )
    legacy_entry = CommitEntry(
        command_id="iap-consumption:proposal-1:2:d-newer-legacy",
        command_digest="legacy-digest",
        kind=CommandType.CONSUME_TRANSMISSION_CAPABILITY,
    )
    receipt = log.append_cas(legacy_entry, expected_seq=-1, writer_epoch=writer_epoch)
    assert isinstance(receipt, AppendReceipt)

    with pytest.raises(CommitLogCorruption):
        intent_registry.decision_current(decision)


def test_loader_refuses_a_non_null_max_decision_age_ms_even_with_issued_at(
    approvals_dir: Path, expected_owner_uid: int
) -> None:
    """Kernel round #1 §2.2 re-review finding #7 (LOW): the receipt-less"""
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        max_decision_age_ms=60_000,
        issued_at_unix_ms=1_000_000,
    )
    with pytest.raises(
        OperatorApprovalFileError, match="load_operator_approval_with_receipt"
    ):
        load_operator_approval_file(
            path,
            expected_owner_uid=expected_owner_uid,
            environment_label="non-live-test",
        )


def test_loader_still_refuses_max_decision_age_ms_without_issued_at(
    approvals_dir: Path, expected_owner_uid: int
) -> None:
    path = write_approval_file(
        approvals_dir / "p1.yaml", decision_id="d1", max_decision_age_ms=60_000
    )
    with pytest.raises(
        OperatorApprovalFileError, match="load_operator_approval_with_receipt"
    ):
        load_operator_approval_file(
            path,
            expected_owner_uid=expected_owner_uid,
            environment_label="non-live-test",
        )


def test_load_operator_approval_with_receipt_refuses_a_future_dated_issuance(
    approvals_dir: Path,
    expected_owner_uid: int,
    expiry_time_config: TrustworthyTimeConfig,
) -> None:
    time_service = FakeTimeService(
        snapshot=expiry_snapshot(wall_clock_observation=1_000_000)
    )
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        max_decision_age_ms=60_000,
        issued_at_unix_ms=1_000_000 + 10_000,
    )
    with pytest.raises(OperatorApprovalFileError, match="future-dated"):
        load_operator_approval_with_receipt(
            path,
            time=time_service,
            time_config=expiry_time_config,
            expected_owner_uid=expected_owner_uid,
            environment_label="non-live-test",
        )


def test_real_time_service_refuses_a_future_dated_issuance(
    approvals_dir: Path, expected_owner_uid: int
) -> None:
    """G-1 end-to-end pin (runtime operations wiring plan §2 decision 1,"""
    monotonic = FakeMonotonicSource(first=1_000)
    time_service = TrustworthyTimeService(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=1_000_000)],
        config=_time_config(),
        identity=RuntimeIdentity(cell_id="test-cell", process_nonce="test-nonce-real"),
        evidence=FakeEvidenceAppendPort(),
    )
    time_service.start()
    time_service.evaluate()
    monotonic.value = 1_010
    time_service.evaluate()
    assert time_service.wall_clock_now() == 1_000_000

    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        max_decision_age_ms=60_000,
        issued_at_unix_ms=1_000_000 + 10_000,
    )
    with pytest.raises(OperatorApprovalFileError, match="future-dated"):
        load_operator_approval_with_receipt(
            path,
            time=time_service,
            time_config=_time_config(),
            expected_owner_uid=expected_owner_uid,
            environment_label="non-live-test",
        )


def test_load_operator_approval_with_receipt_captures_receipt_facts(
    approvals_dir: Path,
    expected_owner_uid: int,
    expiry_time_config: TrustworthyTimeConfig,
) -> None:
    time_service = FakeTimeService(
        snapshot=expiry_snapshot(wall_clock_observation=1_000_000)
    )
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        max_decision_age_ms=60_000,
        issued_at_unix_ms=999_900,
    )
    loaded = load_operator_approval_with_receipt(
        path,
        time=time_service,
        time_config=expiry_time_config,
        expected_owner_uid=expected_owner_uid,
        environment_label="non-live-test",
    )
    assert loaded.decision.max_decision_age_ms == 60_000
    assert loaded.issued_at_unix_ms == 999_900
    assert loaded.issuer_signed_age_ms == 100
    assert (
        loaded.issuer_age_uncertainty_ms
        == expiry_time_config.max_clock_domain_conversion_uncertainty_ms
    )
    assert loaded.receipt_continuity is not None
    assert loaded.receipt_anchor is not None


def test_load_operator_approval_with_receipt_is_none_safe_before_time_service_starts(
    approvals_dir: Path,
    expected_owner_uid: int,
    expiry_time_config: TrustworthyTimeConfig,
) -> None:
    """An un-set ``FakeTimeService`` (no snapshot yet — the real"""
    time_service = FakeTimeService(snapshot=None)
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        max_decision_age_ms=60_000,
        issued_at_unix_ms=999_900,
    )
    loaded = load_operator_approval_with_receipt(
        path,
        time=time_service,
        time_config=expiry_time_config,
        expected_owner_uid=expected_owner_uid,
        environment_label="non-live-test",
    )
    assert loaded.receipt_continuity is None
    assert loaded.receipt_anchor is None
    assert loaded.issuer_signed_age_ms is None


def _load_expiry_decision(
    approvals_dir: Path,
    expected_owner_uid: int,
    time_service: FakeTimeService,
    time_config: TrustworthyTimeConfig,
    *,
    max_decision_age_ms: int,
    issued_at_unix_ms: int,
    trading_approval_policy_generation: int = 1,
):
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        request_id="proposal-1",
        max_decision_age_ms=max_decision_age_ms,
        issued_at_unix_ms=issued_at_unix_ms,
        trading_approval_policy_generation=trading_approval_policy_generation,
    )
    return load_operator_approval_with_receipt(
        path,
        time=time_service,
        time_config=time_config,
        expected_owner_uid=expected_owner_uid,
        environment_label="non-live-test",
    )


def test_decision_current_admits_before_expiry_and_denies_after_time_advances(
    expiry_intent_registry: IntentRegistry,
    expiry_time_service: FakeTimeService,
    expiry_time_config: TrustworthyTimeConfig,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    """Kernel round #1 §2.2 RED-then-GREEN case: age bound at load is"""
    loaded = _load_expiry_decision(
        approvals_dir,
        expected_owner_uid,
        expiry_time_service,
        expiry_time_config,
        max_decision_age_ms=300,
        issued_at_unix_ms=999_900,
    )
    assert (
        expiry_intent_registry.decision_current(loaded.decision, receipt=loaded) is True
    )

    expiry_time_service.set_snapshot(
        expiry_snapshot(monotonic_anchor_value=1_150, wall_clock_observation=1_000_150)
    )
    assert (
        expiry_intent_registry.decision_current(loaded.decision, receipt=loaded)
        is False
    )


def test_decision_current_denies_when_time_is_not_trusted(
    expiry_intent_registry: IntentRegistry,
    expiry_time_service: FakeTimeService,
    expiry_time_config: TrustworthyTimeConfig,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    loaded = _load_expiry_decision(
        approvals_dir,
        expected_owner_uid,
        expiry_time_service,
        expiry_time_config,
        max_decision_age_ms=300,
        issued_at_unix_ms=999_900,
    )
    expiry_time_service.set_snapshot(
        expiry_snapshot(health_state=HealthState.UNTRUSTED)
    )
    assert (
        expiry_intent_registry.decision_current(loaded.decision, receipt=loaded)
        is False
    )


def test_decision_current_denies_after_a_continuity_change_simulating_restart(
    expiry_intent_registry: IntentRegistry,
    expiry_time_service: FakeTimeService,
    expiry_time_config: TrustworthyTimeConfig,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    """A changed monotonic continuity id (simulated process restart) makes"""
    loaded = _load_expiry_decision(
        approvals_dir,
        expected_owner_uid,
        expiry_time_service,
        expiry_time_config,
        max_decision_age_ms=300,
        issued_at_unix_ms=999_900,
    )
    expiry_time_service.set_snapshot(
        expiry_snapshot(monotonic_continuity_id="mono-RESTARTED")
    )
    assert (
        expiry_intent_registry.decision_current(loaded.decision, receipt=loaded)
        is False
    )


def test_decision_current_denies_when_receipt_is_missing_but_expiry_is_configured(
    expiry_intent_registry: IntentRegistry,
    expiry_time_service: FakeTimeService,
    expiry_time_config: TrustworthyTimeConfig,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    loaded = _load_expiry_decision(
        approvals_dir,
        expected_owner_uid,
        expiry_time_service,
        expiry_time_config,
        max_decision_age_ms=300,
        issued_at_unix_ms=999_900,
    )
    assert (
        expiry_intent_registry.decision_current(loaded.decision, receipt=None) is False
    )


def test_decision_current_is_unaffected_when_max_decision_age_ms_is_none(
    intent_registry: IntentRegistry,
    approvals_dir: Path,
    expected_owner_uid: int,
    trading_approval_policy_generation: int,
) -> None:
    """A registry with NO ``time``/``time_config`` wired (every pre-existing"""
    path = write_approval_file(
        approvals_dir / "p1.yaml",
        decision_id="d1",
        request_id="proposal-1",
        trading_approval_policy_generation=trading_approval_policy_generation,
    )
    decision = load_operator_approval_file(
        path, expected_owner_uid=expected_owner_uid, environment_label="non-live-test"
    )
    assert decision.max_decision_age_ms is None
    assert intent_registry.decision_current(decision) is True


def test_consume_records_not_configured_expiry_evidence_when_unset(
    intent_registry: IntentRegistry,
    evidence_port: FakeEvidenceAppendPort,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    decision = _decision(intent_registry, approvals_dir, expected_owner_uid)
    intent_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    consumption_calls = [
        call for call in evidence_port.calls if call[1] == "IAP_CONSUMPTION"
    ]
    assert len(consumption_calls) == 1
    payload = consumption_calls[0][0]
    assert payload["expiry_verdict"] == "NOT_CONFIGURED"
    assert payload["age_bound_ms"] is None


def test_consume_records_unexpired_expiry_evidence_when_admitted(
    expiry_intent_registry: IntentRegistry,
    expiry_time_service: FakeTimeService,
    expiry_time_config: TrustworthyTimeConfig,
    evidence_port: FakeEvidenceAppendPort,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    loaded = _load_expiry_decision(
        approvals_dir,
        expected_owner_uid,
        expiry_time_service,
        expiry_time_config,
        max_decision_age_ms=300,
        issued_at_unix_ms=999_900,
    )
    dc = expiry_intent_registry.decision_current(loaded.decision, receipt=loaded)
    result = expiry_intent_registry.consume(
        loaded.decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=dc,
        approved_intent_envelope_equivalent=True,
        receipt=loaded,
    )
    assert result.outcome is ConsumptionOutcome.CONSUMED_NEW
    consumption_calls = [
        call for call in evidence_port.calls if call[1] == "IAP_CONSUMPTION"
    ]
    payload = consumption_calls[-1][0]
    assert payload["expiry_verdict"] == "UNEXPIRED"
    assert payload["age_bound_ms"] == 210
    assert payload["receipt_anchor"] is not None


def test_decision_current_denies_when_suspension_is_unobserved(
    expiry_intent_registry: IntentRegistry,
    expiry_time_service: FakeTimeService,
    expiry_time_config: TrustworthyTimeConfig,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    """Kernel round #1 §2.2 re-review finding #2 (HIGH): production must read"""
    loaded = _load_expiry_decision(
        approvals_dir,
        expected_owner_uid,
        expiry_time_service,
        expiry_time_config,
        max_decision_age_ms=300,
        issued_at_unix_ms=999_900,
    )
    expiry_time_service.set_snapshot(expiry_snapshot(suspension_ms=None))
    assert (
        expiry_intent_registry.decision_current(loaded.decision, receipt=loaded)
        is False
    )


def test_consume_rejects_when_suspension_is_unobserved(
    expiry_intent_registry: IntentRegistry,
    expiry_time_service: FakeTimeService,
    expiry_time_config: TrustworthyTimeConfig,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    """Same unobserved-suspension case as"""
    loaded = _load_expiry_decision(
        approvals_dir,
        expected_owner_uid,
        expiry_time_service,
        expiry_time_config,
        max_decision_age_ms=300,
        issued_at_unix_ms=999_900,
    )
    expiry_time_service.set_snapshot(expiry_snapshot(suspension_ms=None))
    dc = expiry_intent_registry.decision_current(loaded.decision, receipt=loaded)
    result = expiry_intent_registry.consume(
        loaded.decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=dc,
        approved_intent_envelope_equivalent=True,
        receipt=loaded,
    )
    assert result.outcome is ConsumptionOutcome.REJECTED_INELIGIBLE


def test_decision_current_denies_when_suspension_exceeds_the_configured_bound(
    expiry_intent_registry: IntentRegistry,
    expiry_time_service: FakeTimeService,
    expiry_time_config: TrustworthyTimeConfig,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    """``max_process_suspension_ms`` is ``0`` in the test config (conftest"""
    loaded = _load_expiry_decision(
        approvals_dir,
        expected_owner_uid,
        expiry_time_service,
        expiry_time_config,
        max_decision_age_ms=300,
        issued_at_unix_ms=999_900,
    )
    expiry_time_service.set_snapshot(expiry_snapshot(suspension_ms=1))
    assert (
        expiry_intent_registry.decision_current(loaded.decision, receipt=loaded)
        is False
    )
