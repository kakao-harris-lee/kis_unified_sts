"""``ActionFlowGovernor`` decision + permit issuance tests (design #40 §5 order
5 item 2)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.afg import ActionAmplificationEnvelope, ActionFlowResult
from tos.rcl import AppendReceipt, AppendRefusal, AppendRefusalReason
from tos_runtime.risk.flow import (
    ActionFlowConfigError,
    ActionFlowGovernor,
    permit_reservation_binding,
)

from .conftest import FakeEvidenceAppendPort, grant_shaped_afg_inputs

# ============================================================================
# construction — fail-closed on an undeclared amplification axis
# ============================================================================


def test_governor_refuses_to_start_with_an_undeclared_axis(
    log, evidence_port: FakeEvidenceAppendPort, writer_epoch: int
) -> None:
    incomplete_envelope = ActionAmplificationEnvelope(
        max_fan_out=10,
        max_depth=None,  # undeclared axis
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
    with pytest.raises(ActionFlowConfigError):
        ActionFlowGovernor(
            log, evidence_port, incomplete_envelope, writer_epoch=writer_epoch
        )


def test_governor_starts_with_every_axis_declared(
    afg_governor: ActionFlowGovernor,
) -> None:
    assert afg_governor.envelope.declares_every_bound()


# ============================================================================
# decide() — action_flow_decision composition
# ============================================================================


def test_decide_grants_on_a_fully_proven_bundle(
    afg_governor: ActionFlowGovernor,
) -> None:
    decision = afg_governor.decide(grant_shaped_afg_inputs())
    assert decision.result is ActionFlowResult.GRANT
    assert decision.decision_id is not None
    assert decision.decision_id != decision.canonical_digest


def test_decide_is_unknown_when_lineage_is_incomplete(
    afg_governor: ActionFlowGovernor,
) -> None:
    inputs = grant_shaped_afg_inputs()
    broken_cause = inputs.cause.model_copy(update={"cyclic": True})
    inputs = type(inputs)(**{**inputs.__dict__, "cause": broken_cause})
    decision = afg_governor.decide(inputs)
    assert decision.result is ActionFlowResult.UNKNOWN


def test_decide_appends_decision_evidence(
    afg_governor: ActionFlowGovernor, evidence_port: FakeEvidenceAppendPort
) -> None:
    decision = afg_governor.decide(grant_shaped_afg_inputs())
    decision_calls = [
        payload for payload, kind, _rc in evidence_port.calls if kind == "AFG_DECISION"
    ]
    assert len(decision_calls) == 1
    assert decision_calls[0]["decision_id"] == decision.decision_id
    assert decision_calls[0]["decision_digest"] == decision.canonical_digest


# ============================================================================
# build_permit() — content-addressed claim_nonce (no uuid4/timestamp)
# ============================================================================


def test_build_permit_is_deterministic_content_addressed(
    afg_governor: ActionFlowGovernor,
) -> None:
    decision = afg_governor.decide(grant_shaped_afg_inputs())
    first = afg_governor.build_permit(
        decision, permit_generation=1, command_identity="cmd-1"
    )
    second = afg_governor.build_permit(
        decision, permit_generation=1, command_identity="cmd-1"
    )
    assert first.claim_nonce == second.claim_nonce
    assert first.permit_id == second.permit_id
    assert first.canonical_digest == second.canonical_digest


def test_build_permit_nonce_differs_for_a_different_command(
    afg_governor: ActionFlowGovernor,
) -> None:
    decision = afg_governor.decide(grant_shaped_afg_inputs())
    first = afg_governor.build_permit(
        decision, permit_generation=1, command_identity="cmd-1"
    )
    second = afg_governor.build_permit(
        decision, permit_generation=1, command_identity="cmd-2"
    )
    assert first.claim_nonce != second.claim_nonce


# ============================================================================
# permit_reservation_binding — fail-closed on an unbound permit
# ============================================================================


def test_permit_reservation_binding_is_none_for_an_unbound_permit(
    afg_governor: ActionFlowGovernor,
) -> None:
    decision = afg_governor.decide(grant_shaped_afg_inputs())
    permit = afg_governor.build_permit(
        decision, permit_generation=1, command_identity="cmd-1"
    )
    unbound = permit.model_copy(update={"claim_nonce": None})
    assert permit_reservation_binding(unbound) is None
    assert permit_reservation_binding(permit) == (
        permit.claim_nonce,
        permit.canonical_digest,
    )


# ============================================================================
# issue_permit() — STANDALONE single-use RCL commitment (append_cas)
# ============================================================================


def test_issue_permit_commits_once_and_returns_the_entrys_seq(
    afg_governor: ActionFlowGovernor, log
) -> None:
    decision = afg_governor.decide(grant_shaped_afg_inputs())
    permit = afg_governor.build_permit(
        decision, permit_generation=1, command_identity="cmd-1"
    )
    result = afg_governor.issue_permit(permit, expected_seq=-1)
    assert isinstance(result.log_result, AppendReceipt)
    assert result.rcl_commitment_ref == result.log_result.seq


def test_issue_permit_refuses_a_second_claim_of_the_same_nonce(
    afg_governor: ActionFlowGovernor, log
) -> None:
    decision = afg_governor.decide(grant_shaped_afg_inputs())
    permit = afg_governor.build_permit(
        decision, permit_generation=1, command_identity="cmd-1"
    )
    first = afg_governor.issue_permit(permit, expected_seq=-1)
    assert isinstance(first.log_result, AppendReceipt)
    second = afg_governor.issue_permit(permit, expected_seq=first.log_result.seq)
    assert isinstance(second.log_result, AppendRefusal)
    assert second.log_result.reason is AppendRefusalReason.DUPLICATE_COMMAND_ID
    assert second.rcl_commitment_ref is None


def test_issue_permit_refuses_the_same_claim_even_after_a_simulated_restart(
    afg_governor: ActionFlowGovernor,
    log,
    log_path,
    evidence_port: FakeEvidenceAppendPort,
    envelope: ActionAmplificationEnvelope,
    writer_epoch: int,
) -> None:
    """Single-use enforcement is log-enforced, not memory-enforced: a fresh
    governor over the SAME log file refuses a second claim of a nonce a prior
    (now-closed) governor instance already committed."""
    from tos_runtime.rcl.log import SqliteCommitLog

    decision = afg_governor.decide(grant_shaped_afg_inputs())
    permit = afg_governor.build_permit(
        decision, permit_generation=1, command_identity="cmd-1"
    )
    first = afg_governor.issue_permit(permit, expected_seq=-1)
    assert isinstance(first.log_result, AppendReceipt)
    log.close()

    reopened_log = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        reopened_governor = ActionFlowGovernor(
            reopened_log, evidence_port, envelope, writer_epoch=writer_epoch
        )
        second = reopened_governor.issue_permit(
            permit, expected_seq=first.log_result.seq
        )
        assert isinstance(second.log_result, AppendRefusal)
        assert second.log_result.reason is AppendRefusalReason.DUPLICATE_COMMAND_ID
    finally:
        reopened_log.close()
