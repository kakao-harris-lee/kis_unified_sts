"""§4.8 ∅-void canaries — all 22 rows, **both** directions, end to end.

Every row of the design #24 §4.8 table is exercised twice:

* the **forbidden** direction — the empty / absent / unproven input really reaches the
  predicate, the predicate really fails closed, and the resulting verdict really folds
  through :func:`post_trade_disposition` to the member the table declares;
* the **permitted** direction — the positively proven input passes the same predicate and
  the same fold reaches ``POST_TRADE_ADMISSIBLE``.

Both halves matter: a vacuous-admissible is a defect, and so is a vacuous-block (a guard that
never lets a legitimate case through is not conservative, it is broken). The rows are driven
through the **real predicates** rather than through hand-set disposition inputs, so a
predicate whose ∅ branch silently changed would fail here even if the disposition ladder were
untouched.

Row 15 is the exception with no input at all: a capacity release or an external economic send
is **structurally unrepresentable** (PTF-INV-008 / PTF-INV-016), so it is asserted as the
absence of any field, predicate, or parameter that could express it.
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest
import tos.posttrade.predicates as posttrade_predicates
import tos.posttrade.records as posttrade_records
from tos.canonical import ArtifactStatus
from tos.posttrade import (
    EVENT_OBLIGATION_LEG_MINIMUM_SET,
    VOID_TABLE_ROWS,
    CashKind,
    EconomicObligationRecord,
    EventObligationLegKind,
    FinalityDimensionKind,
    MarginCollateralState,
    ObligationCommitOutcome,
    ObligationLegDirection,
    ObligationLegScope,
    PostTradeDisposition,
    absence_is_negative_evidence_only,
    cash_kind_matches_requirement,
    collateral_no_double_use,
    event_state_not_obligation_finality,
    finality_dimensions_orthogonal,
    finality_proof_class_specific,
    finality_proof_current,
    finality_proof_non_transferable,
    margin_collateral_states_distinct,
    missing_counterleg_is_adverse,
    monetary_leg_conservative,
    netting_requires_positive_proof,
    obligation_commit_idempotent,
    obligation_leg_set_complete,
    obligation_legs_from_event_complete,
    post_trade_disposition,
    statement_coverage_complete,
    statement_sources_independent,
)

from ._posttrade_strategies import (
    clean_allocation,
    clean_disposition_kwargs,
    clean_finality_proof,
    clean_leg,
    clean_monetary_leg,
    clean_obligation_record,
    clean_scope,
    clean_statement_manifest,
    proof_map_only,
)

_ADMISSIBLE = PostTradeDisposition.POST_TRADE_ADMISSIBLE

#: The §4.8 table, indexed by row number. Every row canary below asserts against **this**
#: rather than against a locally re-typed member (design #24 review MINOR-3): the published
#: :data:`~tos.posttrade.VOID_TABLE_ROWS` is the tracing data a consuming runtime and a
#: reviewer read, so a drift between it and the behaviour it documents must fail here. A
#: hand-written expectation would have let the table say one thing while the ladder did
#: another.
_DECLARED_ROW_VERDICT: dict[str, str] = {
    number: expected for number, _input_name, expected in VOID_TABLE_ROWS
}


def _row_verdict(row_number: str) -> PostTradeDisposition:
    """The disposition the published §4.8 table declares for ``row_number``.

    Args:
        row_number: The §4.8 row label (``"1"`` .. ``"22"``).

    Returns:
        The declared :class:`~tos.posttrade.PostTradeDisposition` member.

    Raises:
        KeyError: if the row is absent from the published table.
        ValueError: if the row declares the row-15 ``"INVARIANT"`` sentinel, which is not a
            disposition member and must not be asserted as one.
    """
    return PostTradeDisposition(_DECLARED_ROW_VERDICT[row_number])


_ALL_LEGS = frozenset(ObligationLegDirection)
_ALL_MAGNITUDES = {member: Decimal("1.00") for member in ObligationLegDirection}


def _fold(**overrides: object) -> PostTradeDisposition:
    """Fold a single changed verdict through the sole disposition producer."""
    return post_trade_disposition(**clean_disposition_kwargs(**overrides))


def test_the_permitted_direction_of_every_row_reaches_admissible() -> None:
    """(both-ways baseline) With every row's positive side proven, the fold is admissible."""
    assert _fold() is _ADMISSIBLE


# --- row 1: empty required leg set -------------------------------------------


def test_row_1_empty_required_leg_set() -> None:
    """(§9 / PTF-INV-001) An empty requirement is "we do not know what must be proven"."""
    forbidden = obligation_leg_set_complete(frozenset(), _ALL_LEGS, _ALL_MAGNITUDES)
    assert forbidden is False
    assert _fold(leg_set_complete=forbidden) is _row_verdict("1")

    permitted = obligation_leg_set_complete(
        frozenset({ObligationLegDirection.DEBIT}), _ALL_LEGS, _ALL_MAGNITUDES
    )
    assert permitted is True
    assert _fold(leg_set_complete=permitted) is _ADMISSIBLE


# --- row 2: no finality dimension proof --------------------------------------


def test_row_2_absent_dimension_proof() -> None:
    """(§12 / PTF-INV-002/004) A dimension never promotes itself without its own proof."""
    forbidden = finality_dimensions_orthogonal(FinalityDimensionKind.SETTLEMENT, {})
    assert forbidden is False
    assert _fold(finality_orthogonal=forbidden) is _row_verdict("2")

    permitted = finality_dimensions_orthogonal(
        FinalityDimensionKind.SETTLEMENT,
        proof_map_only(FinalityDimensionKind.SETTLEMENT),
    )
    assert permitted is True
    assert _fold(finality_orthogonal=permitted) is _ADMISSIBLE


# --- row 3: absent monetary amount -------------------------------------------


def test_row_3_absent_monetary_amount() -> None:
    """(§13 line 355) "A missing line item or zero estimate is not proof of zero"."""
    forbidden = monetary_leg_conservative(clean_monetary_leg(amount=None))
    assert forbidden is False
    assert _fold(monetary_conservative=forbidden) is _row_verdict("3")

    permitted = monetary_leg_conservative(
        clean_monetary_leg(
            amount=Decimal("0"), booked_zero=True, source_confidence="CORROBORATED"
        )
    )
    assert permitted is True
    assert _fold(monetary_conservative=permitted) is _ADMISSIBLE


# --- row 4: absent netting proof ---------------------------------------------


def test_row_4_absent_netting_proof() -> None:
    """(PTF-INV-007 / §25.5) Both legs stay gross without an enforceable-netting proof."""
    receivable = clean_leg(ObligationLegDirection.CREDIT)
    payable = clean_leg(ObligationLegDirection.DEBIT)
    forbidden = netting_requires_positive_proof(receivable, payable, True, None)
    assert forbidden is False
    assert _fold(netting_proof_ok=forbidden) is _row_verdict("4")

    permitted = netting_requires_positive_proof(receivable, payable, True, True)
    assert permitted is True
    assert _fold(netting_proof_ok=permitted) is _ADMISSIBLE


# --- row 5: missing counterleg -----------------------------------------------


def test_row_5_missing_counterleg() -> None:
    """(§9 line 279) A missing counterleg is greatest-credible adverse, never balanced."""
    declared = clean_leg(ObligationLegDirection.DEBIT)
    adverse = missing_counterleg_is_adverse(declared, None, True)
    assert adverse is True
    assert _fold(counterleg_established=not adverse) is _row_verdict("5")

    established = missing_counterleg_is_adverse(
        declared, clean_leg(ObligationLegDirection.CREDIT), True
    )
    assert established is False
    assert _fold(counterleg_established=not established) is _ADMISSIBLE


# --- row 6: collateral double use --------------------------------------------


def test_row_6_collateral_double_use() -> None:
    """(§15 line 386 / PTF-INV-011) A double-used unit is an active contradiction."""
    forbidden = collateral_no_double_use(
        [clean_allocation("UNIT-1", encumbered=True, free_magnitude=Decimal("5.00"))]
    )
    assert forbidden is False
    assert _fold(collateral_conserved=forbidden) is _row_verdict("6")

    permitted = collateral_no_double_use([clean_allocation("UNIT-1", encumbered=True)])
    assert permitted is True
    assert _fold(collateral_conserved=permitted) is _ADMISSIBLE


def test_row_6_empty_allocation_sequence_is_also_conflicted() -> None:
    """(∅ guard) "No collateral examined" is not "no double use"."""
    assert collateral_no_double_use([]) is False
    assert _fold(collateral_conserved=False) is _row_verdict("6")


# --- row 7: an event state claiming finality ---------------------------------


def test_row_7_event_state_cannot_supply_finality() -> None:
    """(§17 line 418) ``APPLIED_LOCAL`` / ``RECONCILED`` prove no obligation final."""
    all_unknown: dict[FinalityDimensionKind, bool | None] = dict.fromkeys(
        FinalityDimensionKind
    )
    forbidden = event_state_not_obligation_finality("APPLIED_LOCAL", all_unknown)
    assert forbidden is False
    assert _fold(event_state_not_final_ok=forbidden) is _row_verdict("7")

    permitted = event_state_not_obligation_finality(
        "APPLIED_LOCAL", proof_map_only(FinalityDimensionKind.CORPORATE_ACTION_FINALITY)
    )
    assert permitted is True
    assert _fold(event_state_not_final_ok=permitted) is _ADMISSIBLE


# --- row 8: incomplete statement coverage ------------------------------------


def test_row_8_incomplete_statement_coverage() -> None:
    """(§19 line 443 / PTF-INV-014) An expected page not received is incomplete coverage."""
    forbidden = statement_coverage_complete(
        clean_statement_manifest(received_pages=frozenset({"p1"}))
    )
    assert forbidden is False
    assert _fold(statement_coverage_ok=forbidden) is _row_verdict("8")

    permitted = statement_coverage_complete(clean_statement_manifest())
    assert permitted is True
    assert _fold(statement_coverage_ok=permitted) is _ADMISSIBLE


# --- row 9: common-mode statement sources ------------------------------------


def test_row_9_common_mode_sources() -> None:
    """(§19 line 445 / PTF-INV-014) A shared book is common mode — a contradiction."""
    forbidden = statement_sources_independent(
        frozenset({"book-a"}), frozenset({"book-a", "parser-b"})
    )
    assert forbidden is False
    assert _fold(sources_independent=forbidden) is _row_verdict("9")

    permitted = statement_sources_independent(
        frozenset({"book-a"}), frozenset({"book-b"})
    )
    assert permitted is True
    assert _fold(sources_independent=permitted) is _ADMISSIBLE


# --- row 10: cross-leg proof reuse -------------------------------------------


def test_row_10_cross_leg_proof_reuse() -> None:
    """(§11 line 328) "non-transferable and non-unionable"."""
    proof = clean_finality_proof()
    forbidden = finality_proof_non_transferable(
        proof, clean_scope(leg=ObligationLegDirection.CREDIT)
    )
    assert forbidden is False
    assert _fold(proof_non_transferable=forbidden) is _row_verdict("10")

    permitted = finality_proof_non_transferable(proof, clean_scope())
    assert permitted is True
    assert _fold(proof_non_transferable=permitted) is _ADMISSIBLE


def test_row_10_cross_obligation_proof_reuse() -> None:
    """(§11 line 320; design #24 v1.2 erratum) The **cross-obligation** variant of row 10.

    The scope tuple names a leg within an account / currency / value date / source revision /
    finality class — it does **not** name the obligation. Two distinct obligations can
    therefore legitimately share one scope, and a scope-only comparison would accept
    ``OBL-1``'s settlement proof as covering ``OBL-2``'s identical leg: rank 1 would not fire
    and ``POST_TRADE_ADMISSIBLE`` was reachable. §11 line 320 requires the proof to bind the
    "exact obligation identity", so a supplied target identity is compared too.
    """
    proof = clean_finality_proof(obligation_ref="OBL-1", obligation_version="V1")
    shared_scope = clean_scope()

    # the defect: identical six-component scope, different obligation
    forbidden = finality_proof_non_transferable(
        proof, shared_scope, target_obligation_ref="OBL-2"
    )
    assert forbidden is False
    assert _fold(proof_non_transferable=forbidden) is _row_verdict("10")

    # a later version of the *same* obligation is a different binding too (§11 line 320)
    assert (
        finality_proof_non_transferable(
            proof,
            shared_scope,
            target_obligation_ref="OBL-1",
            target_obligation_version="V2",
        )
        is False
    )

    # the permitted direction: same scope, same obligation, same version
    permitted = finality_proof_non_transferable(
        proof,
        shared_scope,
        target_obligation_ref="OBL-1",
        target_obligation_version="V1",
    )
    assert permitted is True
    assert _fold(proof_non_transferable=permitted) is _ADMISSIBLE


# --- rows 11-13: the record-pair outcomes ------------------------------------


def test_row_11_same_primary_id_different_bytes() -> None:
    """(``record_pair.py:96``) Obligation forgery ⇒ contained conflict."""
    genuine = clean_obligation_record()
    forged = clean_obligation_record(obligation_type="TAX_LEG")
    outcome = obligation_commit_idempotent(forged, genuine, True)
    assert outcome is ObligationCommitOutcome.REJECTED_CONFLICT
    assert _fold(commit_outcome=outcome) is _row_verdict("11")

    accepted = obligation_commit_idempotent(genuine, genuine, True)
    assert accepted is ObligationCommitOutcome.IDEMPOTENT_REPLAY
    assert _fold(commit_outcome=accepted) is _ADMISSIBLE


def test_row_12_same_idempotency_key_different_bytes() -> None:
    """(``record_pair.py:103``) Two different fills claiming one commit key."""
    genuine = clean_obligation_record(obligation_id="OBL-A")
    forged = clean_obligation_record(obligation_id="OBL-B", obligation_type="TAX_LEG")
    outcome = obligation_commit_idempotent(forged, genuine, True)
    assert outcome is ObligationCommitOutcome.REJECTED_CONFLICT
    assert _fold(commit_outcome=outcome) is _row_verdict("12")

    accepted = obligation_commit_idempotent(clean_obligation_record(), None, True)
    assert accepted is ObligationCommitOutcome.COMMITTED_ONCE
    assert _fold(commit_outcome=accepted) is _ADMISSIBLE


def test_row_13_undecidable_record_pair() -> None:
    """(``record_pair.py:87/105``) ``DISTINCT`` / ``NOT_COMPARABLE`` ⇒ quarantine."""
    incoming = clean_obligation_record()
    draft = EconomicObligationRecord(
        obligation_id="OBL-1", status=ArtifactStatus.DRAFT, idempotency_key="IDEM-1"
    )
    outcome = obligation_commit_idempotent(incoming, draft, True)
    assert outcome is ObligationCommitOutcome.REJECTED_UNKNOWN
    assert _fold(commit_outcome=outcome) is _row_verdict("13")


# --- row 14: injected field confidence ---------------------------------------


def test_row_14_unknown_and_conflicted_field_confidence() -> None:
    """(recon seam / PTF-INV-005) UNKNOWN quarantines; CONFLICTED contradicts.

    The only row whose forbidden direction has **two** landings, so the published table
    records the ``UNKNOWN`` one and the ``CONFLICTED`` one is asserted alongside it. The
    ``UNKNOWN`` landing is still read from :data:`~tos.posttrade.VOID_TABLE_ROWS` so the
    drift seal holds where the table speaks.
    """
    assert _fold(field_confidence="UNKNOWN") is _row_verdict("14")
    assert _fold(field_confidence="CONFLICTED") is (
        PostTradeDisposition.POST_TRADE_CONFLICTED
    )
    assert _fold(field_confidence="CORROBORATED") is _ADMISSIBLE


# --- row 15: structural absence ----------------------------------------------


def test_row_15_capacity_release_and_transmission_are_unrepresentable() -> None:
    """(PTF-INV-008 / PTF-INV-016) Row 15 has no input because the act has no expression.

    §1 line 21: only the RCL may create, change, quarantine, transfer, remap, or release
    capacity. §1 line 31: the PTOL "SHALL NOT hold a usable external-economic credential and
    route". Neither is rejected by a branch — neither can be written down.
    """
    forbidden_names = (
        "release_capacity",
        "releases_capacity_flag",
        "transfer_capacity",
        "quarantine_capacity",
        "transmit",
        "send",
        "credential",
        "route",
    )
    for name in forbidden_names:
        assert not hasattr(
            posttrade_predicates, name
        ), f"a {name!r} predicate would make the §4.8 row 15 prohibition expressible"
        assert not hasattr(posttrade_records, name)
    disposition_inputs = set(inspect.signature(post_trade_disposition).parameters)
    for name in forbidden_names:
        assert not any(name in parameter for parameter in disposition_inputs)


def test_row_15_no_input_can_raise_the_disposition_above_its_rank() -> None:
    """(§4.8 row 15) Nothing moves the disposition upward — there is nothing to move it.

    Row 15 is the one row whose published verdict is the ``"INVARIANT"`` sentinel rather than
    a disposition member, so it cannot be read through :func:`_row_verdict` — asserted here
    explicitly, and the sentinel itself is asserted in
    :func:`test_row_15_declares_the_invariant_sentinel_not_a_member`.
    """
    blocked = _fold(leg_set_complete=False)
    assert blocked is PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK
    # every remaining input already at its most favourable value; still blocked
    assert (
        _fold(leg_set_complete=False, availability_proven=True)
        is PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK
    )


def test_row_15_declares_the_invariant_sentinel_not_a_member() -> None:
    """(MINOR-3 both-ways) The lookup helper refuses row 15 rather than inventing a member."""
    assert _DECLARED_ROW_VERDICT["15"] == "INVARIANT"
    with pytest.raises(ValueError):
        _row_verdict("15")


# --- row 16: unproven availability -------------------------------------------


def test_row_16_unproven_availability_is_trapped() -> None:
    """(§14 / §16 / §18; PTF-EV-003/005/007 ``EV-L2/3``) Unproven is trapped, not zero-risk."""
    assert _fold(availability_proven=None) is _row_verdict("16")
    assert _fold(availability_proven=False) is _row_verdict("16")
    assert _fold(availability_proven=True) is _ADMISSIBLE


# --- row 17: margin-state implication ----------------------------------------


def test_row_17_margin_state_implication() -> None:
    """(§15 line 385) "No one state implies another"."""
    forbidden = margin_collateral_states_distinct(
        MarginCollateralState.MARGIN_OBSERVATION,
        MarginCollateralState.CONFIRMED_RELEASE,
    )
    assert forbidden is False
    assert _fold(margin_states_distinct=forbidden) is _row_verdict("17")

    permitted = margin_collateral_states_distinct(
        MarginCollateralState.CONFIRMED_RELEASE, MarginCollateralState.CONFIRMED_RELEASE
    )
    assert permitted is True
    assert _fold(margin_states_distinct=permitted) is _ADMISSIBLE


# --- row 18: cash-kind substitution ------------------------------------------


def test_row_18_cash_kind_substitution() -> None:
    """(PTF-INV-010 / §25.4) Buying power does not satisfy a withdrawable-cash requirement."""
    forbidden = cash_kind_matches_requirement(
        CashKind.WITHDRAWABLE_CASH, CashKind.BUYING_POWER
    )
    assert forbidden is False
    assert _fold(cash_kind_ok=forbidden) is _row_verdict("18")

    permitted = cash_kind_matches_requirement(
        CashKind.WITHDRAWABLE_CASH, CashKind.WITHDRAWABLE_CASH
    )
    assert permitted is True
    assert _fold(cash_kind_ok=permitted) is _ADMISSIBLE


# --- row 19: missing event obligation leg ------------------------------------


def test_row_19_missing_event_obligation_leg() -> None:
    """(§17 line 416) A required leg kind absent from the model is incomplete."""
    forbidden = obligation_legs_from_event_complete(
        EVENT_OBLIGATION_LEG_MINIMUM_SET,
        EVENT_OBLIGATION_LEG_MINIMUM_SET - {EventObligationLegKind.TAX},
    )
    assert forbidden is False
    assert _fold(event_legs_complete=forbidden) is _row_verdict("19")

    permitted = obligation_legs_from_event_complete(
        EVENT_OBLIGATION_LEG_MINIMUM_SET, EVENT_OBLIGATION_LEG_MINIMUM_SET
    )
    assert permitted is True
    assert _fold(event_legs_complete=permitted) is _ADMISSIBLE


# --- row 20: absence read as negative evidence without support ---------------


def test_row_20_absence_without_positive_support() -> None:
    """(§19 line 448 / PTF-INV-004) Absence is negative evidence only with full support."""
    forbidden = absence_is_negative_evidence_only(True, False, True, True)
    assert forbidden is False
    assert _fold(absence_gate_ok=forbidden) is _row_verdict("20")

    permitted = absence_is_negative_evidence_only(True, True, True, True)
    assert permitted is True
    assert _fold(absence_gate_ok=permitted) is _ADMISSIBLE


# --- row 21: a global flag replacing per-field proof -------------------------


def test_row_21_global_flag_substitution() -> None:
    """(PTF-INV-005) A global claim cannot replace exact per-field proof."""
    global_claim = clean_finality_proof(
        finality_class=None, leg_scope=None, does_not_prove=()
    )
    forbidden = finality_proof_class_specific(global_claim)
    assert forbidden is False
    assert _fold(proof_class_specific=forbidden) is _row_verdict("21")

    permitted = finality_proof_class_specific(clean_finality_proof())
    assert permitted is True
    assert _fold(proof_class_specific=permitted) is _ADMISSIBLE


def test_row_21_an_under_specified_scope_is_also_a_global_claim() -> None:
    """(§11 line 328) A scope with an absent component covers a *set* of legs."""
    assert (
        finality_proof_class_specific(
            clean_finality_proof(leg_scope=ObligationLegScope())
        )
        is False
    )


# --- row 22: a stale-generation proof ----------------------------------------


def test_row_22_stale_generation_proof_reopens_finality() -> None:
    """(§11 line 330 / PTF-INV-013) A correction advances the generation ⇒ reopen."""
    proof = clean_finality_proof(bound_generation=1)
    forbidden = finality_proof_current(proof, 2)
    assert forbidden is False
    assert _fold(proof_current=forbidden) is _row_verdict("22")

    permitted = finality_proof_current(proof, 1)
    assert permitted is True
    assert _fold(proof_current=permitted) is _ADMISSIBLE


# --- the table itself ---------------------------------------------------------


@pytest.mark.parametrize(("row_number", "input_name", "expected"), VOID_TABLE_ROWS)
def test_every_declared_row_verdict_is_a_real_member_or_the_sentinel(
    row_number: str, input_name: str, expected: str
) -> None:
    """(§4.8) Each row's declared verdict is an actual disposition — or row 15's sentinel."""
    del row_number, input_name
    assert expected == "INVARIANT" or expected in {
        member.value for member in PostTradeDisposition
    }


def test_this_module_covers_every_row_number() -> None:
    """(count cross-check) 22 rows declared, 22 rows exercised in this module."""
    exercised = {
        name.split("_")[2]
        for name in globals()
        if name.startswith("test_row_") and name.split("_")[2].isdigit()
    }
    declared = {row[0] for row in VOID_TABLE_ROWS}
    assert (
        exercised == declared
    ), f"rows not exercised here: {sorted(declared - exercised)}"
