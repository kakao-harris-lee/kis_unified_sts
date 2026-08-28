"""§2.2 vocabulary transcription: counts, value bindings, truthy seals, tables.

The **count cross-check is exhaustive** (design #21 series discipline 2 / §10.2): every
enumerated list the contract transcribes from ADR-002-010 is re-counted here, so a
truncated transcription fails loudly rather than silently narrowing an invariant (the #16
M4 lesson). Each member is additionally locked to its **value** — an enum whose member is
silently renamed or whose value drifts would break the injected-token seams and the
``model_dump`` round trip without breaking a name-only assertion (design #21 §9.1(4a)
value-drift lock).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.nontrade import (
    CREDIBLE_TRANSITION_LEG_MINIMUM_SET,
    EVENT_IDENTITY_FIELD_GROUPS,
    ORTHOGONAL_EVENT_AXES,
    PROHIBITED_VERBS,
    RECIPROCAL_DIRECTION_PAIRS,
    SPLIT_KIND_DIRECTIONS,
    TRANSFORMATION_DISTINCTION_OWNERSHIP,
    WORKFLOW_BRANCH_STATES,
    WORKFLOW_LINEAR_LIFECYCLE,
    CorrectionReversalOutcome,
    CredibleTransitionLegKind,
    NonTradeDisposition,
    NonTradeEventClass,
    NonTradeEventRecord,
    NonTradeEventWorkflowState,
    SplitTransformationKind,
    TransformationDirection,
)

# ---------------------------------------------------------------------------
# §2.2 counts (exhaustive transcription cross-check)
# ---------------------------------------------------------------------------


def test_event_class_count_is_five() -> None:
    """(§2.2-1) ADR §4.1-§4.5 is a closed 5-way partition."""
    assert len(NonTradeEventClass) == 5


def test_workflow_state_count_is_eight_linear_plus_three_branch() -> None:
    """(§2.2-2) ADR §6 line 127-140 = 8 linear + 3 branch = 11."""
    assert len(WORKFLOW_LINEAR_LIFECYCLE) == 8
    assert len(WORKFLOW_BRANCH_STATES) == 3
    assert len(NonTradeEventWorkflowState) == 11
    # the two tuples partition the enum exactly — no state is orphaned or double-listed
    assert set(WORKFLOW_LINEAR_LIFECYCLE).isdisjoint(set(WORKFLOW_BRANCH_STATES))
    assert set(WORKFLOW_LINEAR_LIFECYCLE) | set(WORKFLOW_BRANCH_STATES) == set(
        NonTradeEventWorkflowState
    )


def test_credible_transition_leg_count_is_ten() -> None:
    """(§2.2-3) ADR §9 line 185-194 = 10 legs."""
    assert len(CredibleTransitionLegKind) == 10
    assert len(CREDIBLE_TRANSITION_LEG_MINIMUM_SET) == 10


def test_split_kind_and_direction_counts() -> None:
    """(§2.2-4) 2 declared split kinds; 3 derived directions."""
    assert len(SplitTransformationKind) == 2
    assert len(TransformationDirection) == 3


def test_correction_outcome_count_is_six() -> None:
    """(§2.2-5) 6 correction / reversal outcomes."""
    assert len(CorrectionReversalOutcome) == 6


def test_disposition_count_is_five() -> None:
    """(§2.2-6) 5 dispositions."""
    assert len(NonTradeDisposition) == 5


def test_orthogonal_axis_count_is_five() -> None:
    """(§6 line 123) order, exposure, capacity, authority, evidence-confidence."""
    assert len(ORTHOGONAL_EVENT_AXES) == 5
    assert len(set(ORTHOGONAL_EVENT_AXES)) == 5
    assert "workflow_state" not in ORTHOGONAL_EVENT_AXES


def test_event_identity_field_group_count_is_thirteen() -> None:
    """(§2.2-8) ADR §5 line 103-115 = 13 identity items, each realized by real fields."""
    assert len(EVENT_IDENTITY_FIELD_GROUPS) == 13
    lines = [line for line, _ in EVENT_IDENTITY_FIELD_GROUPS]
    assert lines == [str(line) for line in range(103, 116)], (
        "one row per ADR §5 line 103-115; the anchor is a string, never a number, so the "
        "§8.0 numeric-literal scan on the source stays absolute"
    )
    record_fields = set(NonTradeEventRecord.model_fields)
    for line, names in EVENT_IDENTITY_FIELD_GROUPS:
        assert names, f"§5 line {line} has no realizing field"
        for name in names:
            assert (
                name in record_fields
            ), f"§5 line {line} names a missing field {name!r}"


def test_the_seven_effective_times_stay_seven_separate_fields() -> None:
    """(§8 line 171) The times SHALL NOT collapse into one 'corporate action date'."""
    times = dict(EVENT_IDENTITY_FIELD_GROUPS)["106"]
    assert len(times) == 7
    assert len(set(times)) == 7


def test_transformation_distinction_count_is_six_and_none_is_unowned() -> None:
    """(§2.2-7) ADR §11 line 231-236 = 6 distinctions, every one attributed."""
    assert len(TRANSFORMATION_DISTINCTION_OWNERSHIP) == 6
    lines = [line for line, _, _ in TRANSFORMATION_DISTINCTION_OWNERSHIP]
    assert lines == [str(line) for line in range(231, 237)]
    owners = {owner for _, _, owner in TRANSFORMATION_DISTINCTION_OWNERSHIP}
    assert owners <= {"nontrade", "nontrade-partial", "venue"}
    assert all(
        owner for _, _, owner in TRANSFORMATION_DISTINCTION_OWNERSHIP
    ), "an unowned distinction is exactly the authority gap §3.5 forbids"


def test_prohibited_verb_count_is_nineteen() -> None:
    """(§4.7) The ADR §1-§22 prohibited-verb sweep = 19, individually counted."""
    assert len(PROHIBITED_VERBS) == 19
    assert len(set(PROHIBITED_VERBS)) == 19


# ---------------------------------------------------------------------------
# Per-member value bindings (drift lock)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "enum_cls",
    [
        NonTradeEventClass,
        NonTradeEventWorkflowState,
        CredibleTransitionLegKind,
        SplitTransformationKind,
        TransformationDirection,
        CorrectionReversalOutcome,
        NonTradeDisposition,
    ],
)
def test_every_member_value_equals_its_name(enum_cls: type) -> None:
    """(§9.1(4a) drift lock) ``Member.value == "MEMBER"`` for every member of every enum.

    A silent value drift would break the injected-token seams (which compare tokens) and
    every persisted ``model_dump`` without breaking a name-only assertion.
    """
    for member in enum_cls:
        assert member.value == member.name


def test_the_event_class_members_are_exactly_the_five_adr_subsections() -> None:
    """(§2.2-1 verbatim) The 5 names are pinned, not merely counted."""
    assert {member.value for member in NonTradeEventClass} == {
        "CORPORATE_ACTION",
        "LIFECYCLE",
        "ADMINISTRATIVE_BROKER",
        "INSTRUMENT_TRADABILITY",
        "UNRECOGNIZED_EXTERNAL",
    }


def test_the_workflow_lifecycle_order_is_the_adr_declaration_order() -> None:
    """(§2.2-2 verbatim) The 8-state linear order is pinned from the start."""
    assert [state.value for state in WORKFLOW_LINEAR_LIFECYCLE] == [
        "OBSERVED",
        "CORROBORATING",
        "VALIDATED",
        "TRANSITION_PREPARED",
        "EFFECT_PENDING",
        "APPLIED_LOCAL",
        "RECONCILING",
        "RECONCILED",
    ]
    assert [state.value for state in WORKFLOW_BRANCH_STATES] == [
        "CONFLICTED",
        "QUARANTINED_UNKNOWN",
        "CORRECTION_PENDING",
    ]


def test_the_correction_outcome_members_are_pinned() -> None:
    """(§2.2-5 verbatim) The 6 outcome names are pinned, not merely counted."""
    assert {member.value for member in CorrectionReversalOutcome} == {
        "APPLIED_ONCE",
        "IDEMPOTENT_REPLAY",
        "REJECTED_CONFLICT",
        "REJECTED_NO_LINEAGE",
        "REJECTED_OVERWRITE",
        "REJECTED_UNKNOWN",
    }


def test_the_disposition_members_are_pinned() -> None:
    """(§2.2-6 verbatim) The 5 disposition names are pinned."""
    assert {member.value for member in NonTradeDisposition} == {
        "NONTRADE_ADMISSIBLE",
        "NONTRADE_BLOCK_NEW_RISK",
        "NONTRADE_QUARANTINED_UNKNOWN",
        "NONTRADE_TRAPPED",
        "NONTRADE_CONFLICTED",
    }


# ---------------------------------------------------------------------------
# §4.5 truth tables A and B
# ---------------------------------------------------------------------------


def test_truth_table_a_has_exactly_three_coherent_cells_of_nine() -> None:
    """(§4.5 table A) 3 reciprocal cells + 6 rejected = the whole 3x3."""
    all_cells = {
        (quantity, basis)
        for quantity in TransformationDirection
        for basis in TransformationDirection
    }
    assert len(all_cells) == 9
    assert len(RECIPROCAL_DIRECTION_PAIRS) == 3
    assert all_cells >= RECIPROCAL_DIRECTION_PAIRS
    assert len(all_cells - RECIPROCAL_DIRECTION_PAIRS) == 6


def test_truth_table_a_rejects_both_amplify_and_both_attenuate() -> None:
    """(§4.5) A same-direction pair is a sign error in **both** directions.

    Both-attenuate under-estimates notional (loses risk); both-amplify over-estimates
    (conservative, but the direction is unproven). A mis-specification is blocked either
    way.
    """
    assert (
        TransformationDirection.AMPLIFY,
        TransformationDirection.AMPLIFY,
    ) not in RECIPROCAL_DIRECTION_PAIRS
    assert (
        TransformationDirection.ATTENUATE,
        TransformationDirection.ATTENUATE,
    ) not in RECIPROCAL_DIRECTION_PAIRS


def test_truth_table_b_pins_forward_and_reverse_to_opposite_directions() -> None:
    """(§4.5 table B) FORWARD and REVERSE are opposite-direction rules — the #16 C1 lesson."""
    assert SPLIT_KIND_DIRECTIONS[SplitTransformationKind.FORWARD_SPLIT] == (
        TransformationDirection.AMPLIFY,
        TransformationDirection.ATTENUATE,
    )
    assert SPLIT_KIND_DIRECTIONS[SplitTransformationKind.REVERSE_SPLIT] == (
        TransformationDirection.ATTENUATE,
        TransformationDirection.AMPLIFY,
    )
    # ...and they are genuinely each other's mirror, not two copies of one rule.
    forward = SPLIT_KIND_DIRECTIONS[SplitTransformationKind.FORWARD_SPLIT]
    reverse = SPLIT_KIND_DIRECTIONS[SplitTransformationKind.REVERSE_SPLIT]
    assert forward == tuple(reversed(reverse))
    assert set(SPLIT_KIND_DIRECTIONS) == set(SplitTransformationKind)
    # every declared row is itself a reciprocal cell of table A
    for pair in SPLIT_KIND_DIRECTIONS.values():
        assert pair in RECIPROCAL_DIRECTION_PAIRS


# ---------------------------------------------------------------------------
# Truthy-sentinel seals (§2.2-6 / §4)
# ---------------------------------------------------------------------------


@given(st.sampled_from(list(NonTradeDisposition)))
def test_disposition_is_not_truthy_testable(member: NonTradeDisposition) -> None:
    """(§2.2-6) ``bool(disposition)`` raises — a bare ``if`` would admit a block."""
    with pytest.raises(TypeError):
        bool(member)


@given(st.sampled_from(list(CorrectionReversalOutcome)))
def test_correction_outcome_is_not_truthy_testable(
    member: CorrectionReversalOutcome,
) -> None:
    """(§2.2-5/§4) ``bool(outcome)`` raises — a bare ``if`` would admit a rejection."""
    with pytest.raises(TypeError):
        bool(member)


def test_the_non_truthy_seal_leaves_identity_value_and_hashing_intact() -> None:
    """The seal blocks only ``__bool__`` — ``is`` / ``.value`` / hashing still work."""
    admissible = NonTradeDisposition.NONTRADE_ADMISSIBLE
    assert admissible is NonTradeDisposition.NONTRADE_ADMISSIBLE
    assert admissible.value == "NONTRADE_ADMISSIBLE"
    assert admissible == "NONTRADE_ADMISSIBLE"
    assert admissible in {NonTradeDisposition.NONTRADE_ADMISSIBLE}
    assert len({admissible, NonTradeDisposition.NONTRADE_ADMISSIBLE}) == 1


def test_the_plain_vocabulary_enums_stay_ordinary_str_enums() -> None:
    """Only the two **result** enums are sealed; the axis enums remain plain StrEnums.

    Sealing an axis enum would break ``model_dump`` round trips and the leg-set algebra for
    no safety gain — the seal exists where a bare ``if`` would read a denial as permission.
    """
    for member in (
        NonTradeEventClass.UNRECOGNIZED_EXTERNAL,
        NonTradeEventWorkflowState.QUARANTINED_UNKNOWN,
        CredibleTransitionLegKind.PROTECTIVE_ORDER_GAP_OVERLAP,
        SplitTransformationKind.REVERSE_SPLIT,
        TransformationDirection.ATTENUATE,
    ):
        assert bool(member) is True


# ---------------------------------------------------------------------------
# Coordinate non-collapse **within** the package (§2.2-5)
# ---------------------------------------------------------------------------


def test_the_nontrade_axes_are_mutually_distinct_types() -> None:
    """(§2.2-5) Token overlap across our own axes never collapses the types."""
    assert (
        NonTradeEventWorkflowState.QUARANTINED_UNKNOWN
        is not NonTradeDisposition.NONTRADE_QUARANTINED_UNKNOWN
    )
    assert (
        NonTradeEventWorkflowState.CONFLICTED
        is not NonTradeDisposition.NONTRADE_CONFLICTED
    )
    # the disposition members are deliberately prefixed so even the *strings* differ
    assert set(NonTradeDisposition).isdisjoint(set(NonTradeEventWorkflowState))
    assert set(CorrectionReversalOutcome).isdisjoint(set(NonTradeDisposition))
    assert set(CredibleTransitionLegKind).isdisjoint(set(NonTradeEventClass))
