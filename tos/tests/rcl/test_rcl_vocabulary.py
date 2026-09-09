"""§1.1 커널 라운드 #1 — ``CommandType`` 4멤버 신설 계약 테스트 (rcl/vocabulary.py).

ADR-002-012 §10 은 16종을 "at minimum ... semantics equivalent to" 로 열어두고, 같은 절이
Safety Authority / Independent Approval / Action Flow Governor / Currentness Sequencer 의
**비-capacity 명령 제출**을 명시한다(design #40 Phase 2 · slice #3 §7 reported gaps). 넷 다
capacity 를 만들지 않는다 — rcl 반영자(:func:`~tos.rcl.predicates.apply_committed`)의
``CommitReservation`` 분기(predicates.py:331)에 불포함임을 여기서 고정한다.

Regime tag: authoring evidence only; closes no RCLP-EV item (design #40 §1.1).
"""

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

#: The four new §1.1 members (kernel round #1 — runtime-realized authority/currentness commands).
_NEW_MEMBERS = (
    CommandType.ADVANCE_AUTHORITY_EPOCH,
    CommandType.CONSUME_APPROVAL_DECISION,
    CommandType.ISSUE_ACTION_FLOW_PERMIT,
    CommandType.ISSUE_EGRESS_CURRENTNESS_PROOF,
)

#: Pre-existing member count (16 ADR-012 §10 + 11 ADR-002-002 §27) — kernel round #1 adds 4.
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
    """(rcl/predicates.py:331) Only ``CommitReservation`` mutates capacity in the reducer.

    A committed command of any of the four new types must advance the ledger revision through
    the generic (non-capacity-mutating) path — no ``CommittedReservation`` entry is appended.
    """
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
