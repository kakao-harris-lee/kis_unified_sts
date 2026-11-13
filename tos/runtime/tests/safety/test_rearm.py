"""``tos_runtime.safety.rearm`` — the new-risk-halt clear door.

Replaces the ``tos.hag`` two-person quorum test module (plan S2-a). What is asserted here
is every property the door still holds: the latch's own identity first, the custody gate,
cross-environment isolation, exactly one positively-APPROVE principal, and a durable
evidence row on both outcomes.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tos_runtime.engine.inbox import NewRiskHaltClearOutcome
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.safety.rearm import (
    ReArmStatus,
    ReArmWorkflow,
    prepare_new_risk_halt_clear,
)

from .conftest import FakeNewRiskHaltInbox, write_rearm_approval_file

_SEQ = 42
_LABEL = "non-live-test"


def _workflow(
    approvals_dir: Path,
    evidence_store: SqliteEvidenceStore,
    *,
    environment_label: str = _LABEL,
    expected_owner_uid: int | None = None,
) -> ReArmWorkflow:
    return ReArmWorkflow(
        approvals_dir,
        evidence_store,
        FakeNewRiskHaltInbox(None),
        environment_label=environment_label,
        expected_owner_uid=(
            os.getuid() if expected_owner_uid is None else expected_owner_uid
        ),
    )


def _kinds(evidence_store: SqliteEvidenceStore) -> list[str]:
    return [row.kind for row in evidence_store.iter_entry_meta()]


# ---------------------------------------------------------------------------
# the happy path
# ---------------------------------------------------------------------------


def test_one_named_approver_clears(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(tmp_path, latched_evidence_seq=_SEQ)
    outcome = _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ)

    assert outcome.status is ReArmStatus.APPROVED
    assert outcome.reasons == ()
    assert outcome.attestation_text == "operator-rearm-approved:alice"
    assert "REARM_APPROVED" in _kinds(evidence_store)


# ---------------------------------------------------------------------------
# the approval file itself
# ---------------------------------------------------------------------------


def test_no_approval_file_is_refused_and_evidenced(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    outcome = _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ)

    assert outcome.status is ReArmStatus.REFUSED
    assert outcome.attestation_text is None
    assert "REARM_REFUSED" in _kinds(evidence_store)


@pytest.mark.parametrize("decision", ["DENY", "ABSTAIN"])
def test_a_non_approve_decision_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, decision: str
) -> None:
    write_rearm_approval_file(
        tmp_path,
        latched_evidence_seq=_SEQ,
        approvals=[{"principal_id": "alice", "decision": decision}],
    )
    outcome = _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ)

    assert outcome.status is ReArmStatus.REFUSED
    assert "REARM_REFUSED" in _kinds(evidence_store)


def test_an_unknown_decision_token_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(
        tmp_path,
        latched_evidence_seq=_SEQ,
        approvals=[{"principal_id": "alice", "decision": "YES"}],
    )
    assert (
        _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ).status
        is ReArmStatus.REFUSED
    )


def test_two_entries_are_refused_rather_than_reduced_to_one(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """An approval file is a record of who decided; an ambiguous one is not a decision."""
    write_rearm_approval_file(
        tmp_path,
        latched_evidence_seq=_SEQ,
        approvals=[
            {"principal_id": "alice", "decision": "APPROVE"},
            {"principal_id": "bob", "decision": "APPROVE"},
        ],
    )
    outcome = _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ)

    assert outcome.status is ReArmStatus.REFUSED


def test_an_empty_approvals_list_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(tmp_path, latched_evidence_seq=_SEQ, approvals=[])
    assert (
        _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ).status
        is ReArmStatus.REFUSED
    )


@pytest.mark.parametrize("principal_id", ["TBD", "", "   "])
def test_a_blank_or_named_tbd_principal_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, principal_id: str
) -> None:
    write_rearm_approval_file(
        tmp_path,
        latched_evidence_seq=_SEQ,
        approvals=[{"principal_id": principal_id, "decision": "APPROVE"}],
    )
    assert (
        _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ).status
        is ReArmStatus.REFUSED
    )


def test_a_file_for_the_wrong_seq_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """A stale approval can never clear a newer halt."""
    write_rearm_approval_file(tmp_path, latched_evidence_seq=_SEQ + 1)
    assert (
        _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ).status
        is ReArmStatus.REFUSED
    )


def test_a_mismatched_environment_label_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(
        tmp_path, latched_evidence_seq=_SEQ, environment_label="some-other-cell"
    )
    assert (
        _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ).status
        is ReArmStatus.REFUSED
    )


def test_a_wrong_mode_file_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """The 0600 custody gate every other operator file in this runtime obeys."""
    write_rearm_approval_file(tmp_path, latched_evidence_seq=_SEQ, mode=0o644)
    assert (
        _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ).status
        is ReArmStatus.REFUSED
    )


def test_a_wrong_owner_uid_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(tmp_path, latched_evidence_seq=_SEQ)
    outcome = _workflow(
        tmp_path, evidence_store, expected_owner_uid=os.getuid() + 1
    ).approve_and_clear(_SEQ)
    assert outcome.status is ReArmStatus.REFUSED


def test_a_malformed_yaml_file_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    path = tmp_path / "rearm" / f"{_SEQ}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("approvals: [ unclosed", encoding="utf-8")
    os.chmod(path, 0o600)
    assert (
        _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ).status
        is ReArmStatus.REFUSED
    )


# ---------------------------------------------------------------------------
# prepare_new_risk_halt_clear — the latch's own identity first
# ---------------------------------------------------------------------------


def test_no_latch_is_refused_before_the_approval_file_is_read(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """``NO_LATCH`` is decided without ever reading the approval file — so no approval
    file is written here, and the refusal is still the latch's, not the file's."""
    decision = prepare_new_risk_halt_clear(
        current=None,
        latched_evidence_seq=_SEQ,
        approvals_dir=tmp_path,
        evidence_store=evidence_store,
        inbox=FakeNewRiskHaltInbox(None),
        environment_label=_LABEL,
        expected_owner_uid=os.getuid(),
        refused_kind="NEW_RISK_HALT_CLEAR_REFUSED",
    )
    assert decision.refusal is NewRiskHaltClearOutcome.NO_LATCH
    assert decision.attestation_text is None
    assert "NEW_RISK_HALT_CLEAR_REFUSED" in _kinds(evidence_store)


def test_a_different_currently_latched_seq_is_a_seq_mismatch(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(tmp_path, latched_evidence_seq=_SEQ)
    decision = prepare_new_risk_halt_clear(
        current={"evidence_seq": _SEQ + 5},
        latched_evidence_seq=_SEQ,
        approvals_dir=tmp_path,
        evidence_store=evidence_store,
        inbox=FakeNewRiskHaltInbox(None),
        environment_label=_LABEL,
        expected_owner_uid=os.getuid(),
        refused_kind="NEW_RISK_HALT_CLEAR_REFUSED",
    )
    assert decision.refusal is NewRiskHaltClearOutcome.SEQ_MISMATCH


def test_a_refused_approval_surfaces_as_quorum_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(
        tmp_path,
        latched_evidence_seq=_SEQ,
        approvals=[{"principal_id": "alice", "decision": "DENY"}],
    )
    decision = prepare_new_risk_halt_clear(
        current={"evidence_seq": _SEQ},
        latched_evidence_seq=_SEQ,
        approvals_dir=tmp_path,
        evidence_store=evidence_store,
        inbox=FakeNewRiskHaltInbox(None),
        environment_label=_LABEL,
        expected_owner_uid=os.getuid(),
        refused_kind="NEW_RISK_HALT_CLEAR_REFUSED",
    )
    assert decision.refusal is NewRiskHaltClearOutcome.QUORUM_REFUSED


def test_an_approved_file_hands_back_the_attestation_and_no_refusal(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(tmp_path, latched_evidence_seq=_SEQ)
    decision = prepare_new_risk_halt_clear(
        current={"evidence_seq": _SEQ},
        latched_evidence_seq=_SEQ,
        approvals_dir=tmp_path,
        evidence_store=evidence_store,
        inbox=FakeNewRiskHaltInbox(None),
        environment_label=_LABEL,
        expected_owner_uid=os.getuid(),
        refused_kind="NEW_RISK_HALT_CLEAR_REFUSED",
    )
    assert decision.refusal is None
    assert decision.attestation_text == "operator-rearm-approved:alice"


# ---------------------------------------------------------------------------
# secret hygiene
# ---------------------------------------------------------------------------


def test_no_evidence_row_carries_a_credential_shaped_kind(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(tmp_path, latched_evidence_seq=_SEQ)
    _workflow(tmp_path, evidence_store).approve_and_clear(_SEQ)
    for kind in _kinds(evidence_store):
        for term in ("secret", "password", "credential", "token", "private_key"):
            assert term not in kind.lower()
