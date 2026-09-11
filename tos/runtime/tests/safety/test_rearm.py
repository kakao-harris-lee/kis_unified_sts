"""``tos_runtime.safety.rearm`` tests (Phase 5 W3 plan §2 decision 7) — the HAG
two-person new-risk-halt re-arm workflow.
"""

from __future__ import annotations

import os
from pathlib import Path

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.safety.rearm import ReArmStatus, ReArmWorkflow

from .conftest import FakeNewRiskHaltInbox, FakeTimeService, write_rearm_approval_file

_ENV_LABEL = "non-live-test"
_SEQ = 42


def _workflow(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    *,
    inbox: FakeNewRiskHaltInbox | None = None,
    expected_owner_uid: int | None = None,
) -> ReArmWorkflow:
    if inbox is None:
        inbox = FakeNewRiskHaltInbox(
            {"reason": "NEW_RISK_HALTED_BY_COUPLING_VIOLATION", "evidence_seq": _SEQ}
        )
    return ReArmWorkflow(
        tmp_path / "approvals",
        evidence_store,
        inbox,
        FakeTimeService(),
        environment_label=_ENV_LABEL,
        expected_owner_uid=(
            os.getuid() if expected_owner_uid is None else expected_owner_uid
        ),
    )


def _rearm_evidence_kinds(evidence_store: SqliteEvidenceStore) -> list[str]:
    rows = evidence_store.connection.execute(
        "SELECT kind FROM entries ORDER BY seq"
    ).fetchall()
    return [row[0] for row in rows]


# ============================================================================
# The satisfying two-person quorum
# ============================================================================


def test_two_distinct_approvers_clears(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(tmp_path / "approvals", latched_evidence_seq=_SEQ)
    workflow = _workflow(tmp_path, evidence_store)

    outcome = workflow.approve_and_clear(_SEQ)

    assert outcome.status is ReArmStatus.APPROVED
    assert outcome.reasons == ()
    assert outcome.attestation_text is not None
    assert outcome.attestation_text.startswith("hag-rearm-quorum-satisfied:")
    assert _rearm_evidence_kinds(evidence_store) == ["REARM_APPROVED"]


def test_approved_evidence_hashes_principals_never_plaintext(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(tmp_path / "approvals", latched_evidence_seq=_SEQ)
    workflow = _workflow(tmp_path, evidence_store)

    workflow.approve_and_clear(_SEQ)

    import json

    row = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'REARM_APPROVED'"
    ).fetchone()
    payload = json.loads(row[0])["payload"]
    assert "alice" not in json.dumps(payload)
    assert "bob" not in json.dumps(payload)
    assert len(payload["principal_sha256"]) == 2
    assert all(len(h) == 64 for h in payload["principal_sha256"])


# ============================================================================
# M6 — no approval file at all
# ============================================================================


def test_mutation_m6_no_approval_file_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    workflow = _workflow(tmp_path, evidence_store)

    outcome = workflow.approve_and_clear(_SEQ)

    assert outcome.status is ReArmStatus.REFUSED
    assert outcome.attestation_text is None
    assert any("approval_file" in reason for reason in outcome.reasons)
    assert _rearm_evidence_kinds(evidence_store) == ["REARM_REFUSED"]


# ============================================================================
# M5 — two-person quorum weakened to one approver
# ============================================================================


def test_mutation_m5_a_single_approver_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(
        tmp_path / "approvals",
        latched_evidence_seq=_SEQ,
        approvals=[{"principal_id": "alice", "decision": "APPROVE"}],
    )
    workflow = _workflow(tmp_path, evidence_store)

    outcome = workflow.approve_and_clear(_SEQ)

    assert outcome.status is ReArmStatus.REFUSED
    assert "dual_control_effective_distinct" in outcome.reasons
    assert "quorum_independence_satisfied" in outcome.reasons


def test_the_same_principal_twice_is_refused_not_a_quorum() -> None:
    """§17.1.4/HAG-INV-018: an external reviewer who collapses to the operator is
    not a second principal — here, structurally, the SAME principal_id listed
    twice must not satisfy the quorum."""
    # constructed inline (no fixtures needed) to keep the property obvious
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
    from tos.hag import (
        AttestationDecision,
        ConflictRole,
        EffectivePrincipalGraph,
        EffectivePrincipalNode,
        HumanApprovalAttestation,
        HumanApprovalRequest,
        dual_control_effective_distinct,
        quorum_independence_satisfied,
    )

    scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
    request = HumanApprovalRequest.issue(
        scheme=scheme, request_id="r", creation_generation=1
    )
    attestations = tuple(
        HumanApprovalAttestation.issue(
            scheme=scheme,
            attestation_id=f"a{i}",
            request_digest=request.canonical_digest,
            principal_id="alice",
            role=ConflictRole.REARM_APPROVER,
            decision=AttestationDecision.APPROVE,
        )
        for i in range(2)
    )
    graph = EffectivePrincipalGraph.issue(
        scheme=scheme,
        graph_id="g",
        graph_generation=1,
        nodes=(EffectivePrincipalNode(principal_id="alice"),),
        edges=(),
        unresolved_control=False,
    )
    assert dual_control_effective_distinct(attestations, graph) is False
    assert (
        quorum_independence_satisfied(
            attestations, graph, quorum_n=2, required_roles=frozenset()
        )
        is False
    )


# ============================================================================
# Wrong/stale seq, wrong environment, bad file custody
# ============================================================================


def test_a_file_for_the_wrong_seq_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(tmp_path / "approvals", latched_evidence_seq=_SEQ + 1)
    workflow = _workflow(tmp_path, evidence_store)

    outcome = workflow.approve_and_clear(_SEQ)

    assert outcome.status is ReArmStatus.REFUSED


def test_a_mismatched_environment_label_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(
        tmp_path / "approvals", latched_evidence_seq=_SEQ, environment_label="paper"
    )
    workflow = _workflow(tmp_path, evidence_store)

    outcome = workflow.approve_and_clear(_SEQ)

    assert outcome.status is ReArmStatus.REFUSED


def test_a_wrong_mode_file_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(
        tmp_path / "approvals", latched_evidence_seq=_SEQ, mode=0o644
    )
    workflow = _workflow(tmp_path, evidence_store)

    outcome = workflow.approve_and_clear(_SEQ)

    assert outcome.status is ReArmStatus.REFUSED


def test_no_matching_latch_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    write_rearm_approval_file(tmp_path / "approvals", latched_evidence_seq=_SEQ)
    workflow = _workflow(tmp_path, evidence_store, inbox=FakeNewRiskHaltInbox(None))

    outcome = workflow.approve_and_clear(_SEQ)

    assert outcome.status is ReArmStatus.REFUSED
    assert outcome.reasons == ("no_matching_latch",)


# ============================================================================
# no_automatic_rearm — trivially true, but exercised
# ============================================================================


def test_no_automatic_rearm_is_unconditionally_true() -> None:
    from tos.hag import no_automatic_rearm

    assert no_automatic_rearm() is True
    assert (
        no_automatic_rearm(
            health_recovered=True,
            timeout_elapsed=True,
            reconciliation_completed=True,
            leader_elected=True,
            restart_completed=True,
        )
        is True
    )


# ============================================================================
# approval_set_single_use — the SAME seq's approval cannot clear twice
# ============================================================================


def test_a_second_attempt_against_the_same_seq_is_refused_single_use(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """The workflow never clears the latch itself (that is ``_types.py``'s job), so
    this drives ``approve_and_clear`` TWICE against the SAME still-latched seq —
    the second call must be refused by ``approval_set_single_use`` (the first
    call's ``REARM_APPROVED`` evidence already carries this exact approval-set
    digest)."""
    write_rearm_approval_file(tmp_path / "approvals", latched_evidence_seq=_SEQ)
    workflow = _workflow(tmp_path, evidence_store)

    first = workflow.approve_and_clear(_SEQ)
    second = workflow.approve_and_clear(_SEQ)

    assert first.status is ReArmStatus.APPROVED
    assert second.status is ReArmStatus.REFUSED
    assert "approval_set_single_use" in second.reasons
