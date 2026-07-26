"""§2.2 vocabulary — exhaustive count cross-checks + per-member value binding (design #24).

Series discipline 2 (count cross-checks are exhaustive, the #16 M4 truncated-transcription
lesson): **every** enumerated list in the contract carries its ADR item count, and every one
of those counts is re-asserted here — 12 lifecycle states, 10 finality dimensions, 8 leg
directions, 6 cash kinds, 8 margin / collateral states, 3 statement classes, 9 event
obligation legs, 6 commit outcomes, 5 dispositions (9 enums), plus the 18 PTF-INV rows, the
12 §25 rejected alternatives, the 15 prohibited verbs, the 6 FQP "does not prove" items, the
8 §9 obligation-record field groups, the 5 §10 orthogonal axes, and the 19 injected sibling
tokens.

Each enum additionally gets a **per-member value binding** assertion (design #24 §9.1-4(a)):
a member renamed or re-valued in a later edit breaks here rather than silently changing what
a persisted digest or an injected token means.
"""

from __future__ import annotations

import pytest
from tos.posttrade import (
    EVENT_OBLIGATION_LEG_MINIMUM_SET,
    EVENT_STATE_TOKENS_THAT_PROVE_NO_FINALITY,
    FQP_DOES_NOT_PROVE,
    INJECTED_SIBLING_TOKENS,
    OBLIGATION_LIFECYCLE_BRANCH,
    OBLIGATION_LIFECYCLE_LINEAR,
    OBLIGATION_RECORD_FIELD_GROUPS,
    OPPOSITE_DIRECTION_PAIRS,
    ORTHOGONAL_POST_TRADE_AXES,
    PROHIBITED_VERBS,
    PTF_INVARIANT_REALIZATION,
    REJECTED_ALTERNATIVE_REALIZATION,
    CashKind,
    EventObligationLegKind,
    FinalityDimensionKind,
    MarginCollateralState,
    ObligationCommitOutcome,
    ObligationLegDirection,
    PostTradeDisposition,
    PostTradeObligationLifecycleState,
    StatementClass,
)

# --- the 9 enums with their ADR item counts (design #24 §2.2) ----------------
_ENUM_COUNTS = (
    (PostTradeObligationLifecycleState, 12),
    (FinalityDimensionKind, 10),
    (ObligationLegDirection, 8),
    (CashKind, 6),
    (MarginCollateralState, 8),
    (StatementClass, 3),
    (EventObligationLegKind, 9),
    (ObligationCommitOutcome, 6),
    (PostTradeDisposition, 5),
)


@pytest.mark.parametrize(("enum_type", "expected"), _ENUM_COUNTS)
def test_enum_member_counts_match_the_adr(enum_type: type, expected: int) -> None:
    """(§2.2) Every enum has exactly the ADR item count — no truncation, no invention."""
    assert (
        len(list(enum_type)) == expected
    ), f"{enum_type.__name__} has {len(list(enum_type))} members, ADR says {expected}"


def test_the_package_declares_exactly_nine_vocabulary_enums() -> None:
    """(§2.2/§9.1) Nine enums, counted individually — the design's own enumeration."""
    assert len(_ENUM_COUNTS) == 9


def test_lifecycle_member_values() -> None:
    """(§2.2-1) The 8 linear + 4 branch lifecycle states bind to their exact values."""
    assert PostTradeObligationLifecycleState.POTENTIAL.value == "POTENTIAL"
    assert PostTradeObligationLifecycleState.RECOGNIZED.value == "RECOGNIZED"
    assert PostTradeObligationLifecycleState.DUE.value == "DUE"
    assert PostTradeObligationLifecycleState.IN_FLIGHT.value == "IN_FLIGHT"
    assert PostTradeObligationLifecycleState.PARTIALLY_SATISFIED.value == (
        "PARTIALLY_SATISFIED"
    )
    assert PostTradeObligationLifecycleState.SATISFIED_PENDING_FINALITY.value == (
        "SATISFIED_PENDING_FINALITY"
    )
    assert PostTradeObligationLifecycleState.FINALITY_PROVEN.value == "FINALITY_PROVEN"
    assert PostTradeObligationLifecycleState.CLOSED.value == "CLOSED"
    assert PostTradeObligationLifecycleState.BREAK_OPEN.value == "BREAK_OPEN"
    assert PostTradeObligationLifecycleState.CORRECTION_PENDING.value == (
        "CORRECTION_PENDING"
    )
    assert PostTradeObligationLifecycleState.FAILED_OR_TRAPPED.value == (
        "FAILED_OR_TRAPPED"
    )
    assert PostTradeObligationLifecycleState.SUPERSEDED.value == "SUPERSEDED"


def test_lifecycle_linear_and_branch_partition_the_enum() -> None:
    """(§2.2-1) 8 linear + 4 branch, disjoint, and together the whole enum."""
    assert len(OBLIGATION_LIFECYCLE_LINEAR) == 8
    assert len(OBLIGATION_LIFECYCLE_BRANCH) == 4
    linear = set(OBLIGATION_LIFECYCLE_LINEAR)
    branch = set(OBLIGATION_LIFECYCLE_BRANCH)
    assert linear.isdisjoint(branch)
    assert linear | branch == set(PostTradeObligationLifecycleState)


def test_finality_dimension_member_values() -> None:
    """(§2.2-2) The 10 PTF-INV-002 dimensions bind to their exact values."""
    assert FinalityDimensionKind.ORDER_FQP.value == "ORDER_FQP"
    assert FinalityDimensionKind.TRADE_CAPTURE.value == "TRADE_CAPTURE"
    assert FinalityDimensionKind.INSTRUCTION_ACCEPTANCE.value == (
        "INSTRUCTION_ACCEPTANCE"
    )
    assert FinalityDimensionKind.SETTLEMENT.value == "SETTLEMENT"
    assert FinalityDimensionKind.CASH_AVAILABILITY.value == "CASH_AVAILABILITY"
    assert FinalityDimensionKind.COLLATERAL_ELIGIBILITY.value == (
        "COLLATERAL_ELIGIBILITY"
    )
    assert FinalityDimensionKind.CUSTODY_TITLE.value == "CUSTODY_TITLE"
    assert FinalityDimensionKind.FEE_FINALITY.value == "FEE_FINALITY"
    assert FinalityDimensionKind.BORROW_DISCHARGE.value == "BORROW_DISCHARGE"
    assert FinalityDimensionKind.CORPORATE_ACTION_FINALITY.value == (
        "CORPORATE_ACTION_FINALITY"
    )


def test_leg_direction_member_values() -> None:
    """(§2.2-3) The 8 §5.3 line 116 leg directions bind to their exact values."""
    assert ObligationLegDirection.DEBIT.value == "DEBIT"
    assert ObligationLegDirection.CREDIT.value == "CREDIT"
    assert ObligationLegDirection.DELIVERY.value == "DELIVERY"
    assert ObligationLegDirection.RECEIPT.value == "RECEIPT"
    assert ObligationLegDirection.ENCUMBRANCE.value == "ENCUMBRANCE"
    assert ObligationLegDirection.RELEASE.value == "RELEASE"
    assert ObligationLegDirection.RETURN.value == "RETURN"
    assert ObligationLegDirection.CONTINGENT.value == "CONTINGENT"


def test_opposite_direction_pairs_are_three_symmetric_pairs() -> None:
    """(§4.5-A) DEBIT/CREDIT, DELIVERY/RECEIPT, ENCUMBRANCE/RELEASE — both orders each."""
    assert len(OPPOSITE_DIRECTION_PAIRS) == 6
    for first, second in OPPOSITE_DIRECTION_PAIRS:
        assert (second, first) in OPPOSITE_DIRECTION_PAIRS
        assert first is not second
    # RETURN and CONTINGENT have no opposite: they are not balancing directions.
    partnered = {member for pair in OPPOSITE_DIRECTION_PAIRS for member in pair}
    assert ObligationLegDirection.RETURN not in partnered
    assert ObligationLegDirection.CONTINGENT not in partnered


def test_cash_kind_member_values() -> None:
    """(§2.2-4) The 6 PTF-INV-010 cash kinds bind to their exact values."""
    assert CashKind.LEDGER_CASH.value == "LEDGER_CASH"
    assert CashKind.PENDING_CASH.value == "PENDING_CASH"
    assert CashKind.SETTLED_CASH.value == "SETTLED_CASH"
    assert CashKind.WITHDRAWABLE_CASH.value == "WITHDRAWABLE_CASH"
    assert CashKind.BUYING_POWER.value == "BUYING_POWER"
    assert CashKind.COLLATERAL_ELIGIBLE_CASH.value == "COLLATERAL_ELIGIBLE_CASH"


def test_margin_collateral_state_member_values() -> None:
    """(§2.2-5) The 8 §15 line 385 margin / collateral states bind to their exact values."""
    assert MarginCollateralState.MARGIN_OBSERVATION.value == "MARGIN_OBSERVATION"
    assert MarginCollateralState.MARGIN_CALL.value == "MARGIN_CALL"
    assert MarginCollateralState.COLLATERAL_REQUEST.value == "COLLATERAL_REQUEST"
    assert MarginCollateralState.INSTRUCTION_ACKNOWLEDGEMENT.value == (
        "INSTRUCTION_ACKNOWLEDGEMENT"
    )
    assert MarginCollateralState.PLEDGED_COLLATERAL.value == "PLEDGED_COLLATERAL"
    assert MarginCollateralState.ACCEPTED_COLLATERAL.value == "ACCEPTED_COLLATERAL"
    assert MarginCollateralState.AVAILABLE_EXCESS.value == "AVAILABLE_EXCESS"
    assert MarginCollateralState.CONFIRMED_RELEASE.value == "CONFIRMED_RELEASE"


def test_statement_class_member_values() -> None:
    """(§2.2-5) The 3 §19 line 442 statement classes bind to their exact values."""
    assert StatementClass.PRELIMINARY.value == "PRELIMINARY"
    assert StatementClass.FINAL.value == "FINAL"
    assert StatementClass.REVISED.value == "REVISED"


def test_event_obligation_leg_member_values() -> None:
    """(§2.2-5b m6) The 9 §17 line 416 event obligation leg kinds bind to exact values."""
    assert EventObligationLegKind.ASSET.value == "ASSET"
    assert EventObligationLegKind.CASH.value == "CASH"
    assert EventObligationLegKind.FEE.value == "FEE"
    assert EventObligationLegKind.TAX.value == "TAX"
    assert EventObligationLegKind.FINANCING.value == "FINANCING"
    assert EventObligationLegKind.MARGIN.value == "MARGIN"
    assert EventObligationLegKind.BORROW.value == "BORROW"
    assert EventObligationLegKind.CUSTODY.value == "CUSTODY"
    assert EventObligationLegKind.DELIVERY.value == "DELIVERY"
    assert frozenset(EventObligationLegKind) == EVENT_OBLIGATION_LEG_MINIMUM_SET


def test_commit_outcome_member_values() -> None:
    """(§2.2-6) The 6 commit outcomes bind to their exact values."""
    assert ObligationCommitOutcome.COMMITTED_ONCE.value == "COMMITTED_ONCE"
    assert ObligationCommitOutcome.IDEMPOTENT_REPLAY.value == "IDEMPOTENT_REPLAY"
    assert ObligationCommitOutcome.REJECTED_CONFLICT.value == "REJECTED_CONFLICT"
    assert ObligationCommitOutcome.REJECTED_NO_LINEAGE.value == "REJECTED_NO_LINEAGE"
    assert ObligationCommitOutcome.REJECTED_OVERWRITE.value == "REJECTED_OVERWRITE"
    assert ObligationCommitOutcome.REJECTED_UNKNOWN.value == "REJECTED_UNKNOWN"


def test_disposition_member_values() -> None:
    """(§2.2-8) The 5 dispositions bind to their exact values."""
    assert PostTradeDisposition.POST_TRADE_ADMISSIBLE.value == "POST_TRADE_ADMISSIBLE"
    assert PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value == (
        "POST_TRADE_BLOCK_NEW_RISK"
    )
    assert PostTradeDisposition.POST_TRADE_QUARANTINED_UNKNOWN.value == (
        "POST_TRADE_QUARANTINED_UNKNOWN"
    )
    assert PostTradeDisposition.POST_TRADE_TRAPPED.value == "POST_TRADE_TRAPPED"
    assert PostTradeDisposition.POST_TRADE_CONFLICTED.value == "POST_TRADE_CONFLICTED"


# --- transcription tables ----------------------------------------------------


def test_ptf_invariant_table_covers_all_eighteen() -> None:
    """(§4.0) 18 PTF-INV rows, ids PTF-INV-001..018, no unowned invariant."""
    assert len(PTF_INVARIANT_REALIZATION) == 18
    ids = [row[0] for row in PTF_INVARIANT_REALIZATION]
    assert ids == [f"PTF-INV-{index:03d}" for index in range(1, 19)]
    for invariant_id, proposition, realization in PTF_INVARIANT_REALIZATION:
        assert proposition, f"{invariant_id} has no proposition"
        assert realization, f"{invariant_id} has no realization (unowned invariant)"


def test_rejected_alternative_table_covers_all_twelve() -> None:
    """(§4.9) 12 §25 rejected alternatives, each with a structural realization."""
    assert len(REJECTED_ALTERNATIVE_REALIZATION) == 12
    sections = [row[0] for row in REJECTED_ALTERNATIVE_REALIZATION]
    assert sections == [f"25.{index}" for index in range(1, 13)]
    for section, claim, realization in REJECTED_ALTERNATIVE_REALIZATION:
        assert claim, f"{section} has no claim"
        assert realization, f"{section} has no structural realization"


def test_prohibited_verb_count_is_fifteen() -> None:
    """(§4.8) 15 prohibited verbs, individually counted, no duplicates."""
    assert len(PROHIBITED_VERBS) == 15
    assert len(set(PROHIBITED_VERBS)) == 15


def test_fqp_does_not_prove_covers_six_items_on_six_distinct_dimensions() -> None:
    """(§2.2-7) The 6 §12 line 340-345 items map to 6 distinct finality dimensions."""
    assert len(FQP_DOES_NOT_PROVE) == 6
    dimensions = [row[2] for row in FQP_DOES_NOT_PROVE]
    assert len(set(dimensions)) == 6
    assert FinalityDimensionKind.ORDER_FQP not in dimensions


def test_obligation_record_field_groups_cover_eight_adr_groups() -> None:
    """(§2.2-7) The 8 §9 line 268-275 content groups are transcribed with field names."""
    assert len(OBLIGATION_RECORD_FIELD_GROUPS) == 8
    for anchor, field_names in OBLIGATION_RECORD_FIELD_GROUPS:
        assert isinstance(
            anchor, str
        ), "an ADR line anchor must be a string, not a number"
        assert field_names, f"group {anchor} names no realizing field"


def test_orthogonal_axes_are_five_distinct_names() -> None:
    """(§10 line 303-310) Five orthostate-owned axes, none of them ``lifecycle_state``."""
    assert len(ORTHOGONAL_POST_TRADE_AXES) == 5
    assert len(set(ORTHOGONAL_POST_TRADE_AXES)) == 5
    assert "lifecycle_state" not in ORTHOGONAL_POST_TRADE_AXES


def test_injected_sibling_tokens_are_nineteen_individually_counted() -> None:
    """(§3.4) 19 injected coordinates — the #21 MINOR-1 "13 listed, 1 missing" lesson."""
    assert len(INJECTED_SIBLING_TOKENS) == 19
    owners = [owner for owner, _ in INJECTED_SIBLING_TOKENS]
    assert owners.count("rcl") == 3
    assert owners.count("are") == 4
    assert owners.count("recon") == 3
    assert owners.count("brokercap") == 2
    assert owners.count("nontrade") == 2
    assert owners.count("egress") == 2
    assert owners.count("time") == 1
    assert owners.count("cur") == 2
    for owner, token in INJECTED_SIBLING_TOKENS:
        assert token, f"{owner} token is empty — an empty token locks nothing"


def test_event_state_tokens_named_by_the_adr_are_the_two_of_section_17() -> None:
    """(§17 line 418) ``APPLIED_LOCAL`` and ``RECONCILED`` — the two the ADR names."""
    assert EVENT_STATE_TOKENS_THAT_PROVE_NO_FINALITY == ("APPLIED_LOCAL", "RECONCILED")
