"""§1.1 커널 라운드 #1 — ``CommandType`` 4멤버 신설 계약 테스트 (rcl/vocabulary.py)."""

from __future__ import annotations

from tos.rcl import (
    ApplyReason,
    CapacityVector,
    CommandType,
    FenceCoordinates,
    LedgerState,
    apply_committed,
)

from ._rcl_strategies import issue_command

_NEW_MEMBERS = (
    CommandType.ADVANCE_AUTHORITY_EPOCH,
    CommandType.CONSUME_APPROVAL_DECISION,
    CommandType.ISSUE_ACTION_FLOW_PERMIT,
    CommandType.ISSUE_EGRESS_CURRENTNESS_PROOF,
)

_PRIOR_MEMBER_COUNT = 27


def test_four_new_members_carry_the_spec_values() -> None:
    """The four new members' string values are the ADR semantic-equivalence names."""
    assert CommandType.ADVANCE_AUTHORITY_EPOCH.value == "AdvanceAuthorityEpoch"
    assert CommandType.CONSUME_APPROVAL_DECISION.value == "ConsumeApprovalDecision"
    assert CommandType.ISSUE_ACTION_FLOW_PERMIT.value == "IssueActionFlowPermit"
    assert (
        CommandType.ISSUE_EGRESS_CURRENTNESS_PROOF.value
        == "IssueEgressCurrentnessProof"
    )


def test_member_count_pinned_at_prior_plus_four() -> None:
    """The enum closed-set size is pinned so a future silent addition/removal is caught."""
    assert len(CommandType) == _PRIOR_MEMBER_COUNT + 4


def test_none_of_the_four_is_commit_reservation() -> None:
    """None of the four is (or aliases) the one capacity-mutating member."""
    for member in _NEW_MEMBERS:
        assert member is not CommandType.COMMIT_RESERVATION


def test_none_of_the_four_takes_the_commit_reservation_branch_in_the_reducer() -> None:
    """(rcl/predicates.py:331) Only ``CommitReservation`` mutates capacity in the reducer."""
    limits = CapacityVector()
    for index, member in enumerate(_NEW_MEMBERS):
        state = LedgerState()
        command = issue_command(
            command_identity=f"cmd-new-{index}",
            command_type=member,
            fence=FenceCoordinates(expected_revision=0),
        )
        outcome = apply_committed(
            state, command, limits=limits, applicable_dimensions=()
        )
        assert outcome.admitted is True
        assert outcome.reason is ApplyReason.ADMITTED
        assert outcome.state.committed == ()
        assert outcome.state.revision == 1
