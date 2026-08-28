"""Verbatim-transcription + coordinate-non-collapse properties (design #18 §2.2/§2.2-5).

The #16 M4 lesson is that a **truncated** transcription is a silent safety hole: an
omitted credible intermediate outcome is an unbounded outcome, and an omitted
re-evaluation target is a stale quantity calculation. So every ADR enumeration this
package transcribes is asserted by **item count and exact token set** against the ADR line
range recorded in the vocabulary docstrings:

* ADR §6 replacement modes — 4;
* ADR §5 line 124-135 workflow states — 7 linear + 2 non-linear = 9;
* ADR §9 line 234-243 credible intermediate outcomes — **9**;
* ADR §12 line 292-298 re-evaluation targets — **6**;
* ADR §6.3 line 166-174 cancel-first preconditions — **8**;
* ADR §5 line 107 orthogonal axes — **5**;
* the local ``ReplacementOutcome`` — **5** (including ``REPLACEMENT_TRAPPED``, v1.1 M1).

Coordinate non-collapse (§2.2-5) is asserted **structurally** — distinct types, and the
sibling axes are not importable from this package — rather than by token disjointness,
because the ADR deliberately reuses words like "overlap-first" and "trapped" on several
axes.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.replacement import (
    CANCEL_FIRST_ADMISSION_CONDITIONS,
    NO_NETTING_MAGNITUDE_KINDS,
    ORTHOGONAL_WORKFLOW_AXES,
    REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES,
    REQUIRED_REEVALUATION_TARGETS,
    WORKFLOW_LIFECYCLE_ORDER,
    WORKFLOW_NON_LINEAR_STATES,
    CancelFirstConditions,
    CredibleIntermediateOutcomeKind,
    ReevaluationTargetKind,
    ReplacementMode,
    ReplacementOutcome,
    ReplacementWorkflowRecord,
    ReplacementWorkflowState,
    protective_action_kind_token,
)

# ---------------------------------------------------------------------------
# Item-count transcription (the #16 M4 truncation lesson)
# ---------------------------------------------------------------------------


def test_replacement_mode_has_exactly_the_four_adr_modes() -> None:
    """(ADR §6 line 143-181, count = 4) The four modes, verbatim tokens."""
    assert {mode.value for mode in ReplacementMode} == {
        "BROKER_PROVEN_ATOMIC",
        "OVERLAP_FIRST",
        "CANCEL_FIRST",
        "NO_SAFE_MODE",
    }
    assert len(ReplacementMode) == 4
    # Per-member NAME -> VALUE binding. The set assertion above is invariant under a
    # *swap* of two members' values (the set stays equal), which would silently invert
    # the §4.5 direction polarity — overlap-first evaluated as cancel-first. Binding each
    # member individually is what closes that mutation class.
    assert ReplacementMode.BROKER_PROVEN_ATOMIC.value == "BROKER_PROVEN_ATOMIC"
    assert ReplacementMode.OVERLAP_FIRST.value == "OVERLAP_FIRST"
    assert ReplacementMode.CANCEL_FIRST.value == "CANCEL_FIRST"
    assert ReplacementMode.NO_SAFE_MODE.value == "NO_SAFE_MODE"


def test_workflow_state_has_exactly_seven_plus_two_states() -> None:
    """(ADR §5 line 124-135, count = 7 + 2) The linear lifecycle plus the two exits."""
    assert len(ReplacementWorkflowState) == 9
    assert len(WORKFLOW_LIFECYCLE_ORDER) == 7
    assert len(WORKFLOW_NON_LINEAR_STATES) == 2
    assert tuple(w.value for w in WORKFLOW_LIFECYCLE_ORDER) == (
        "PLANNED",
        "CAPACITY_COMMITTED",
        "FIRST_LEG_SENT",
        "INTERMEDIATE_STATE",
        "NEW_PROTECTION_PROVEN",
        "OLD_FINALITY_PENDING",
        "COMPLETED",
    )
    assert {w.value for w in WORKFLOW_NON_LINEAR_STATES} == {
        "FAILED_CONTAINED",
        "RECOVERY_REQUIRED",
    }
    # The two partitions are disjoint and together cover the whole enum.
    assert set(WORKFLOW_LIFECYCLE_ORDER).isdisjoint(set(WORKFLOW_NON_LINEAR_STATES))
    assert set(WORKFLOW_LIFECYCLE_ORDER) | set(WORKFLOW_NON_LINEAR_STATES) == set(
        ReplacementWorkflowState
    )


def test_credible_intermediate_outcomes_are_exactly_the_nine() -> None:
    """(ADR §9 line 234-243, count = **9**) An omitted outcome is an unbounded outcome."""
    assert len(CredibleIntermediateOutcomeKind) == 9
    assert {kind.value for kind in CredibleIntermediateOutcomeKind} == {
        "CURRENT_EXPOSURE_UNPROTECTED",
        "OLD_ORDER_REMAINING_EXECUTABLE",
        "NEW_ORDER_REMAINING_EXECUTABLE",
        "SIMULTANEOUS_OLD_AND_NEW_FILLS",
        "PARTIAL_FILLS_EVERY_ORDERING",
        "OVER_CLOSE_AND_REVERSAL",
        "TEMPORARY_LOSS_OF_PROTECTION",
        "COMMISSION_MARGIN_MARKET_BOUNDS",
        "BROKER_SCARCITY_PREVENTS_PROTECTION",
    }
    # §9 line 233 "SHALL include **at least**" — the required universe is the whole enum,
    # mode-independent (design #18 §4.5 M2), never a per-mode subset.
    assert (
        frozenset(CredibleIntermediateOutcomeKind)
        == REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES
    )
    assert len(REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES) == 9
    # Per-member NAME -> VALUE binding (see the mode test): a swap keeps the set equal but
    # would mis-key the no-netting magnitude lookup, since
    # ``NO_NETTING_MAGNITUDE_KINDS`` addresses the three slots by member.
    assert (
        CredibleIntermediateOutcomeKind.CURRENT_EXPOSURE_UNPROTECTED.value
        == "CURRENT_EXPOSURE_UNPROTECTED"
    )
    assert (
        CredibleIntermediateOutcomeKind.OLD_ORDER_REMAINING_EXECUTABLE.value
        == "OLD_ORDER_REMAINING_EXECUTABLE"
    )
    assert (
        CredibleIntermediateOutcomeKind.NEW_ORDER_REMAINING_EXECUTABLE.value
        == "NEW_ORDER_REMAINING_EXECUTABLE"
    )
    assert (
        CredibleIntermediateOutcomeKind.SIMULTANEOUS_OLD_AND_NEW_FILLS.value
        == "SIMULTANEOUS_OLD_AND_NEW_FILLS"
    )
    assert (
        CredibleIntermediateOutcomeKind.PARTIAL_FILLS_EVERY_ORDERING.value
        == "PARTIAL_FILLS_EVERY_ORDERING"
    )
    assert (
        CredibleIntermediateOutcomeKind.OVER_CLOSE_AND_REVERSAL.value
        == "OVER_CLOSE_AND_REVERSAL"
    )
    assert (
        CredibleIntermediateOutcomeKind.TEMPORARY_LOSS_OF_PROTECTION.value
        == "TEMPORARY_LOSS_OF_PROTECTION"
    )
    assert (
        CredibleIntermediateOutcomeKind.COMMISSION_MARGIN_MARKET_BOUNDS.value
        == "COMMISSION_MARGIN_MARKET_BOUNDS"
    )
    assert (
        CredibleIntermediateOutcomeKind.BROKER_SCARCITY_PREVENTS_PROTECTION.value
        == "BROKER_SCARCITY_PREVENTS_PROTECTION"
    )


def test_reevaluation_targets_are_exactly_the_six() -> None:
    """(ADR §12 line 292-298, count = **6**) An omitted target is a stale calculation."""
    assert len(ReevaluationTargetKind) == 6
    assert {kind.value for kind in ReevaluationTargetKind} == {
        "REMAINING_PROTECTIVE_OBLIGATION",
        "OLD_AND_NEW_EXECUTABLE_QUANTITIES",
        "OVERLAP_AND_GAP_RISK",
        "CAPACITY_COMMITMENTS",
        "CANCELLATION_AUTHORIZATION",
        "PENDING_TRANSMISSION_CONFORMANCE",
    }
    assert frozenset(ReevaluationTargetKind) == REQUIRED_REEVALUATION_TARGETS
    assert len(REQUIRED_REEVALUATION_TARGETS) == 6
    # Per-member NAME -> VALUE binding (see the mode test).
    assert (
        ReevaluationTargetKind.REMAINING_PROTECTIVE_OBLIGATION.value
        == "REMAINING_PROTECTIVE_OBLIGATION"
    )
    assert (
        ReevaluationTargetKind.OLD_AND_NEW_EXECUTABLE_QUANTITIES.value
        == "OLD_AND_NEW_EXECUTABLE_QUANTITIES"
    )
    assert ReevaluationTargetKind.OVERLAP_AND_GAP_RISK.value == "OVERLAP_AND_GAP_RISK"
    assert ReevaluationTargetKind.CAPACITY_COMMITMENTS.value == "CAPACITY_COMMITMENTS"
    assert (
        ReevaluationTargetKind.CANCELLATION_AUTHORIZATION.value
        == "CANCELLATION_AUTHORIZATION"
    )
    assert (
        ReevaluationTargetKind.PENDING_TRANSMISSION_CONFORMANCE.value
        == "PENDING_TRANSMISSION_CONFORMANCE"
    )


def test_replacement_outcome_has_five_members_including_trapped() -> None:
    """(design #18 §2.2-5, count = 5) ``REPLACEMENT_TRAPPED`` is the v1.1 M1 fifth value."""
    assert len(ReplacementOutcome) == 5
    assert {outcome.value for outcome in ReplacementOutcome} == {
        "REPLACEMENT_ADMISSIBLE",
        "REPLACEMENT_DENIED",
        "REPLACEMENT_CONTAINED",
        "REPLACEMENT_TRAPPED",
        "REPLACEMENT_UNKNOWN",
    }
    # Per-member NAME -> VALUE binding (see the mode test). A swap here is the worst of
    # the four: ``REPLACEMENT_ADMISSIBLE`` carrying the ``"REPLACEMENT_DENIED"`` value
    # (or vice versa) would invert every consumer gate written against the token.
    assert ReplacementOutcome.REPLACEMENT_ADMISSIBLE.value == "REPLACEMENT_ADMISSIBLE"
    assert ReplacementOutcome.REPLACEMENT_DENIED.value == "REPLACEMENT_DENIED"
    assert ReplacementOutcome.REPLACEMENT_CONTAINED.value == "REPLACEMENT_CONTAINED"
    assert ReplacementOutcome.REPLACEMENT_TRAPPED.value == "REPLACEMENT_TRAPPED"
    assert ReplacementOutcome.REPLACEMENT_UNKNOWN.value == "REPLACEMENT_UNKNOWN"


def test_cancel_first_conditions_are_exactly_the_eight() -> None:
    """(ADR §6.3 line 166-174, count = **8**) Names ↔ model fields, one-to-one."""
    assert len(CANCEL_FIRST_ADMISSION_CONDITIONS) == 8
    assert len(set(CANCEL_FIRST_ADMISSION_CONDITIONS)) == 8
    model_fields = set(CancelFirstConditions.model_fields)
    assert set(CANCEL_FIRST_ADMISSION_CONDITIONS) == model_fields, (
        "the 8-name universe and the model fields drifted apart — a missing field would "
        "make the gate assert against a name that can never be proven"
    )


def test_no_netting_magnitude_kinds_are_the_three_structural_slots() -> None:
    """(design #18 §0.4d/M6, count = 3) old + new + simultaneous, all real enum members."""
    assert len(NO_NETTING_MAGNITUDE_KINDS) == 3
    assert set(NO_NETTING_MAGNITUDE_KINDS) == {
        CredibleIntermediateOutcomeKind.OLD_ORDER_REMAINING_EXECUTABLE,
        CredibleIntermediateOutcomeKind.NEW_ORDER_REMAINING_EXECUTABLE,
        CredibleIntermediateOutcomeKind.SIMULTANEOUS_OLD_AND_NEW_FILLS,
    }
    # They are a strict subset of the 9 required outcomes: no-netting is a *structural
    # property of three of the reserved slots*, not a separate universe.
    assert set(NO_NETTING_MAGNITUDE_KINDS) < REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES


def test_orthogonal_axes_are_five_separate_record_fields() -> None:
    """(ADR §5 line 107, count = **5**) The no-collapse axes exist as separate fields."""
    assert len(ORTHOGONAL_WORKFLOW_AXES) == 5
    fields = set(ReplacementWorkflowRecord.model_fields)
    for axis in ORTHOGONAL_WORKFLOW_AXES:
        assert axis in fields, f"§5 line 107 axis {axis} is not a separate record field"
    # The replacement-owned lifecycle label is a *sixth*, distinct coordinate — it must
    # not be one of the five injected axes (that would be the collapse §5:107 forbids).
    assert "workflow_state" in fields
    assert "workflow_state" not in ORTHOGONAL_WORKFLOW_AXES


# ---------------------------------------------------------------------------
# Truthiness trap + coordinate non-collapse (§2.2 / §2.2-5)
# ---------------------------------------------------------------------------


@given(
    member=st.one_of(
        st.sampled_from(list(ReplacementOutcome)),
        st.sampled_from(list(ReplacementMode)),
        st.sampled_from(list(ReplacementWorkflowState)),
        st.sampled_from(list(CredibleIntermediateOutcomeKind)),
        st.sampled_from(list(ReevaluationTargetKind)),
    )
)
def test_every_strenum_member_is_truthy(member: object) -> None:
    """(the trap itself) Every member of every replacement enum is truthy.

    A bare ``if outcome:`` would let ``REPLACEMENT_DENIED`` / ``REPLACEMENT_UNKNOWN``
    through, which is why identity gating is mandatory across this package (§2.2).
    """
    assert bool(member) is True


def test_strenum_members_are_not_their_raw_strings_under_identity() -> None:
    """(the trap itself) A ``StrEnum`` member equals its value but is not it under ``is``."""
    for member in ReplacementOutcome:
        assert member == member.value
        assert member is not member.value
    for member in ReplacementMode:
        assert member == member.value
        assert member is not member.value


def test_replacement_axes_are_distinct_types_from_each_other() -> None:
    """(§2.2-5) No member of one replacement axis is a member of another."""
    axes = (
        set(ReplacementMode),
        set(ReplacementWorkflowState),
        set(CredibleIntermediateOutcomeKind),
        set(ReevaluationTargetKind),
        set(ReplacementOutcome),
    )
    for index, axis in enumerate(axes):
        for other in axes[index + 1 :]:
            assert axis.isdisjoint(other)
    # Type-level: an outcome is never a mode even when the *strings* would compare.
    assert ReplacementOutcome.REPLACEMENT_TRAPPED not in set(ReplacementMode)


def test_replacement_trapped_is_a_distinct_type_from_the_sibling_trapped_tokens() -> (
    None
):
    """(§2.2-5) ``REPLACEMENT_TRAPPED`` is neither protective ``TRAPPED`` nor rcl's.

    The sibling enums are imported **in this test only** (a test-only cross-import is not
    a runtime package edge, design #18 §3.4(d)); the runtime package holds sibling edge 0,
    which is what makes coercion impossible.
    """
    from tos.protective import Admissibility
    from tos.rcl import CapacityState

    assert ReplacementOutcome.REPLACEMENT_TRAPPED is not Admissibility.TRAPPED
    assert ReplacementOutcome.REPLACEMENT_TRAPPED is not CapacityState.TRAPPED_CONSUMED
    assert ReplacementOutcome.REPLACEMENT_TRAPPED != Admissibility.TRAPPED
    assert ReplacementOutcome.REPLACEMENT_TRAPPED != CapacityState.TRAPPED_CONSUMED
    # ...and the *concepts* really are three: an admissibility verdict, a capacity state,
    # and a replacement outcome. All three are truthy, hence the identity discipline.
    assert bool(Admissibility.TRAPPED) is True
    assert bool(CapacityState.TRAPPED_CONSUMED) is True


def test_replacement_mode_is_a_distinct_type_from_protective_action_kind() -> None:
    """(§2.2-5) ``OVERLAP_FIRST`` (workflow mode) is not ``OVERLAP_FIRST_ADD_ONLY``."""
    from tos.protective import ProtectiveActionKind

    assert set(ReplacementMode).isdisjoint(set(ProtectiveActionKind))
    assert (
        ReplacementMode.OVERLAP_FIRST is not ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY
    )
    assert ReplacementMode.OVERLAP_FIRST != ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY


# ---------------------------------------------------------------------------
# Mode -> protective action-kind token mapping (§3.4 seam)
# ---------------------------------------------------------------------------


@given(mode=st.sampled_from(list(ReplacementMode)))
def test_only_the_two_directional_modes_map_to_a_lease_action_kind(
    mode: ReplacementMode,
) -> None:
    """(§3.4/§5 line 139 (C)) Only overlap-first / cancel-first have a lease counterpart."""
    token = protective_action_kind_token(mode)
    if mode is ReplacementMode.OVERLAP_FIRST:
        assert token == "OVERLAP_FIRST_ADD_ONLY"
    elif mode is ReplacementMode.CANCEL_FIRST:
        assert token == "CANCEL_FIRST_OR_REMOVAL"
    else:
        # ``None`` is restrictive at the caller (there is no lease action to admit),
        # never a wildcard.
        assert token is None
