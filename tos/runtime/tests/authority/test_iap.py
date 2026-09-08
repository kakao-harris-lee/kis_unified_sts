"""``IntentRegistry`` + ``load_operator_approval_file`` tests (design #40 §5
order 4 item 3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.iap import ApprovalResult, ConsumptionOutcome, ConsumptionStatus
from tos.rcl import AppendReceipt, CommandType, CommitEntry
from tos_runtime.authority.iap import (
    IntentRegistry,
    OperatorApprovalFileError,
    _consumption_command_id,
    load_operator_approval_file,
)
from tos_runtime.rcl.log import CommitLogCorruption, SqliteCommitLog

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
# max_decision_age_ms — 2026-09-08 re-review MEDIUM: no kernel predicate
# enforces decision expiry (tos.iap is clock-free; decision_current is an
# injected fact), so a non-null value must be REFUSED at load, never
# silently accepted-but-unenforced (ADR-002-023 §12 item 2 "unexpired").
# ============================================================================


def test_loader_refuses_a_non_null_max_decision_age_ms(
    approvals_dir: Path, expected_owner_uid: int
) -> None:
    path = write_approval_file(
        approvals_dir / "p1.yaml", decision_id="d1", max_decision_age_ms=60_000
    )
    with pytest.raises(OperatorApprovalFileError, match="expiry enforcement"):
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

    # "Restart": open a fresh SqliteCommitLog handle at the same path and a
    # fresh IntentRegistry over it — no Python object shared with `first_registry`.
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


# ============================================================================
# decision_current() — input collection: policy-generation equality + a
# log-derived proposal-scoped supersession check (no kernel predicate exists)
# ============================================================================


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
        # trading_approval_policy_generation omitted -> None
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
        # request_id omitted -> supersession undeterminable
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
    """A later-generation decision for the SAME proposal, already consumed,
    supersedes an older one (§11 line 298) — detected purely from the log's
    own command-id encoding, no payload readback (module docstring)."""
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

    # Only the newer decision is ever consumed — the older one is never
    # itself consumed, so its currency depends entirely on the supersession
    # check, not on its own consumption status.
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


# ============================================================================
# kernel round #1 §2.1 — CommandType switch + legacy-kind fail-closed refusal
# ============================================================================


def test_consume_uses_the_new_consume_approval_decision_command_type(
    intent_registry: IntentRegistry,
    log: SqliteCommitLog,
    writer_epoch: int,
    approvals_dir: Path,
    expected_owner_uid: int,
) -> None:
    """A newly-committed consumption is written under the new, dedicated
    ``CONSUME_APPROVAL_DECISION`` member (kernel round #1 §1.1/§2.1) — the
    reported-gap ``CONSUME_TRANSMISSION_CAPABILITY`` reuse is resolved."""
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
    """A pre-existing entry at this decision's own consumption command-id,
    committed under the OLD legacy ``CONSUME_TRANSMISSION_CAPABILITY`` kind,
    must never be silently treated as "not yet consumed" by
    :meth:`IntentRegistry._current_consumption` — that would let a second,
    differently-kinded consumption slip through undetected (fail-open). It
    must instead raise :class:`CommitLogCorruption` (kernel round #1 §2.1)."""
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
    """A later-generation entry under this proposal's own consumption prefix,
    committed under the OLD legacy ``CONSUME_TRANSMISSION_CAPABILITY`` kind,
    must never be silently skipped by the supersession scan in
    :meth:`IntentRegistry.decision_current` — skipping it would hide a real
    supersession (fail-open). It must instead raise
    :class:`CommitLogCorruption` (kernel round #1 §2.1)."""
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
