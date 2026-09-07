"""``IntentRegistry`` + ``load_operator_approval_file`` tests (design #40 §5
order 4 item 3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.iap import ApprovalResult, ConsumptionOutcome, ConsumptionStatus
from tos_runtime.authority.iap import (
    IntentRegistry,
    OperatorApprovalFileError,
    load_operator_approval_file,
)
from tos_runtime.rcl.log import SqliteCommitLog

from .conftest import FakeEvidenceAppendPort, write_approval_file

# ============================================================================
# load_operator_approval_file — zero auto-approval; verbatim result pass-through
# ============================================================================


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
    """Mirrors custody's own LOW-1 discipline: a mode/owner refusal happens
    before any YAML parsing is attempted."""
    path = write_approval_file(approvals_dir / "p1.yaml", mode=0o644)
    path.write_bytes(b"not even valid yaml: [[[")
    with pytest.raises(OperatorApprovalFileError):
        load_operator_approval_file(
            path,
            expected_owner_uid=expected_owner_uid,
            environment_label="non-live-test",
        )


# ============================================================================
# consume() — single-use, log-enforced (IAP-INV-006)
# ============================================================================


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
    """decision_current=False (or an envelope mismatch) is REJECTED_INELIGIBLE
    and commits nothing — a later legitimate consume must still succeed."""
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

    # Nothing was committed — a legitimate consume afterward still succeeds.
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
    """A brand-new IntentRegistry over the SAME log (simulated restart — no
    in-memory state carried over) still refuses a second consumption of the
    same decision (IAP-INV-006; module docstring)."""
    first_registry = IntentRegistry(log, evidence_port, writer_epoch=writer_epoch)
    decision = _decision(first_registry, approvals_dir, expected_owner_uid)
    first = first_registry.consume(
        decision,
        command_identity="cmd-1",
        command_digest="digest-1",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    assert first.outcome is ConsumptionOutcome.CONSUMED_NEW

    # "Restart": open a fresh SqliteCommitLog handle at the same path and a
    # fresh IntentRegistry over it — no Python object shared with `first_registry`.
    second_log = SqliteCommitLog(log_path, evidence_port=FakeEvidenceAppendPort())
    try:
        second_registry = IntentRegistry(
            second_log, FakeEvidenceAppendPort(), writer_epoch=writer_epoch
        )
        second = second_registry.consume(
            decision,
            command_identity="cmd-2",
            command_digest="digest-DIFFERENT",
            decision_current=True,
            approved_intent_envelope_equivalent=True,
        )
        assert second.outcome is ConsumptionOutcome.REJECTED_CONFLICT

        # Even a byte-identical retry of the ORIGINAL command is only ever an
        # idempotent replay of the existing record — never a second, distinct
        # consumption.
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
