"""§4.1 — the RFC-002 §10.8:741-759 17-item verify list and its honest disposition table.

The design's central over-claim risk is reading "the gate ran" as "the send is safe". These tests
lock the *honesty structure*: the list is exactly seventeen, the three dispositions partition it
6 / 5 / 6, every non-deferred item has a named check, and the only admitting outcomes are the two
enumerated positive ones.

Design #34 §12.1-1 target: "verify 항목 임의 하나가 deny/None/UNKNOWN 반환 시 SendHandoff
(accepted_for_transmission=None)·transmit 미발생·중단 사유 기록."

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.egressgw import (
    ADMITTING_VERIFY_OUTCOMES,
    DEFERRED_ITEMS,
    PROVISIONAL_ITEMS,
    REALIZED_ITEMS,
    SEND_VERIFY_ITEMS,
    ArtifactIntegrityError,
    BrokerApplicability,
    SendVerifyItem,
    VerifyDisposition,
    VerifyItemVerdict,
    VerifyOutcome,
    verify_item_number,
    verify_send_boundary,
)

from ._egressgw_fixtures import happy_context

#: The design §4.1 table, transcribed. A drift between this and the shipped constants is the
#: defect this file exists to catch — so it is written out item by item, not derived from them.
_DESIGN_TABLE: dict[int, VerifyDisposition] = {
    1: VerifyDisposition.REALIZED_STRUCTURAL,
    2: VerifyDisposition.REALIZED_STRUCTURAL,
    3: VerifyDisposition.PROVISIONAL_STAND_IN,
    4: VerifyDisposition.DEFERRED_APPLICABILITY,
    5: VerifyDisposition.DEFERRED_APPLICABILITY,
    6: VerifyDisposition.PROVISIONAL_STAND_IN,
    7: VerifyDisposition.DEFERRED_APPLICABILITY,
    8: VerifyDisposition.DEFERRED_APPLICABILITY,
    9: VerifyDisposition.DEFERRED_APPLICABILITY,
    10: VerifyDisposition.DEFERRED_APPLICABILITY,
    11: VerifyDisposition.REALIZED_STRUCTURAL,
    12: VerifyDisposition.PROVISIONAL_STAND_IN,
    13: VerifyDisposition.REALIZED_STRUCTURAL,
    14: VerifyDisposition.PROVISIONAL_STAND_IN,
    15: VerifyDisposition.PROVISIONAL_STAND_IN,
    16: VerifyDisposition.REALIZED_STRUCTURAL,
    17: VerifyDisposition.REALIZED_STRUCTURAL,
}


def _disposition(item: SendVerifyItem) -> VerifyDisposition:
    """The shipped disposition of ``item``."""
    if item in REALIZED_ITEMS:
        return VerifyDisposition.REALIZED_STRUCTURAL
    if item in PROVISIONAL_ITEMS:
        return VerifyDisposition.PROVISIONAL_STAND_IN
    return VerifyDisposition.DEFERRED_APPLICABILITY


def test_the_verify_list_is_exactly_seventeen_items() -> None:
    """(§10.8:741-759) Seventeen, no more and no fewer."""
    assert len(SEND_VERIFY_ITEMS) == 17
    assert len(set(SEND_VERIFY_ITEMS)) == 17
    assert set(SEND_VERIFY_ITEMS) == set(SendVerifyItem)


def test_the_dispositions_partition_the_list_six_five_six() -> None:
    """(§4.1) 6 Realize + 5 Provisional + 6 Deferred = 17, disjoint and exhaustive."""
    assert len(REALIZED_ITEMS) == 6
    assert len(PROVISIONAL_ITEMS) == 5
    assert len(DEFERRED_ITEMS) == 6
    assert set(SEND_VERIFY_ITEMS) == REALIZED_ITEMS | PROVISIONAL_ITEMS | DEFERRED_ITEMS
    assert not (REALIZED_ITEMS & PROVISIONAL_ITEMS)
    assert not (REALIZED_ITEMS & DEFERRED_ITEMS)
    assert not (PROVISIONAL_ITEMS & DEFERRED_ITEMS)


@pytest.mark.parametrize("number", sorted(_DESIGN_TABLE))
def test_each_item_carries_the_design_table_disposition(number: int) -> None:
    """(§4.1 anti-drift) The shipped disposition equals the ratified table, item by item."""
    item = SEND_VERIFY_ITEMS[number - 1]
    assert verify_item_number(item) == number
    assert _disposition(item) is _DESIGN_TABLE[number]


def test_the_six_deferred_items_are_the_live_safety_governance_mesh() -> None:
    """(§4.1) Safety Authority / Live Scope / Envelope / Deviation / Incident / Monitoring."""
    assert {
        SendVerifyItem.CURRENT_SAFETY_AUTHORITY_EPOCH,
        SendVerifyItem.VALID_LIVE_SCOPE,
        SendVerifyItem.HARD_SAFETY_ENVELOPE_VERSIONS,
        SendVerifyItem.SAFETY_DEVIATION,
        SendVerifyItem.SAFETY_INCIDENT,
        SendVerifyItem.SAFETY_MONITORING,
    } == DEFERRED_ITEMS


def test_item_numbers_are_derived_from_the_normative_order() -> None:
    """(§4.1) A number is the RFC's own position, never a re-assigned label."""
    for position, item in enumerate(SEND_VERIFY_ITEMS, start=1):
        assert verify_item_number(item) == position


def test_a_non_member_has_no_verify_item_number() -> None:
    """(fail-closed) An item outside the closed seventeen is not a verify item."""
    with pytest.raises(ArtifactIntegrityError, match="not one of the 17"):
        verify_item_number("NOT_AN_ITEM")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# admission is a positive closed set, and N/A is confined to the deferred mesh
# ---------------------------------------------------------------------------


def test_only_two_outcomes_admit_and_they_are_enumerated_positively() -> None:
    """(§4.2 / §7) The gate is positive membership, never ``is not DENIED``."""
    assert {
        VerifyOutcome.SATISFIED,
        VerifyOutcome.NOT_APPLICABLE,
    } == ADMITTING_VERIFY_OUTCOMES
    assert VerifyOutcome.UNKNOWN not in ADMITTING_VERIFY_OUTCOMES
    assert VerifyOutcome.DENIED not in ADMITTING_VERIFY_OUTCOMES


def test_verify_outcomes_are_not_truthy_testable() -> None:
    """(truthy-sentinel seal) ``if outcome:`` would read DENIED as a pass — so it raises."""
    for outcome in VerifyOutcome:
        with pytest.raises(TypeError, match="not truthy-testable"):
            bool(outcome)
    for applicability in BrokerApplicability:
        with pytest.raises(TypeError, match="not truthy-testable"):
            bool(applicability)


@pytest.mark.parametrize(
    "item",
    sorted(REALIZED_ITEMS | PROVISIONAL_ITEMS),
)
def test_not_applicable_is_unconstructable_outside_the_deferred_mesh(
    item: SendVerifyItem,
) -> None:
    """(§4.2) Only the deferred mesh may be explicitly N/A — the model forbids the rest."""
    with pytest.raises(ValidationError, match="cannot be recorded NOT_APPLICABLE"):
        VerifyItemVerdict(
            item=item,
            disposition=_disposition(item),
            outcome=VerifyOutcome.NOT_APPLICABLE,
        )


def test_a_deferred_item_may_be_not_applicable() -> None:
    """(§4.2, both ways) The recorded positive N/A judgement is constructable where it belongs."""
    verdict = VerifyItemVerdict(
        item=SendVerifyItem.VALID_LIVE_SCOPE,
        disposition=VerifyDisposition.DEFERRED_APPLICABILITY,
        outcome=VerifyOutcome.NOT_APPLICABLE,
    )
    assert verdict.outcome is VerifyOutcome.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# the list actually runs, in order, over every item
# ---------------------------------------------------------------------------


def test_the_baseline_run_judges_every_item_in_the_normative_order() -> None:
    """(§10.8:761) Seventeen judgements, in the RFC's order — an unevaluated item is a stop."""
    attempt, context = happy_context()
    verification = verify_send_boundary(attempt=attempt, context=context)
    assert verification.admitted is True
    assert tuple(v.item for v in verification.verdicts) == SEND_VERIFY_ITEMS


def test_the_baseline_run_is_six_satisfied_realize_and_six_not_applicable() -> None:
    """(§4.1 정직 귀결) The honest shape of a synthetic slice run, asserted numerically."""
    attempt, context = happy_context()
    verification = verify_send_boundary(attempt=attempt, context=context)
    by_disposition: dict[VerifyDisposition, list[VerifyOutcome]] = {}
    for verdict in verification.verdicts:
        by_disposition.setdefault(verdict.disposition, []).append(verdict.outcome)
    assert by_disposition[VerifyDisposition.REALIZED_STRUCTURAL] == [
        VerifyOutcome.SATISFIED
    ] * 6
    assert by_disposition[VerifyDisposition.PROVISIONAL_STAND_IN] == [
        VerifyOutcome.SATISFIED
    ] * 5
    assert by_disposition[VerifyDisposition.DEFERRED_APPLICABILITY] == [
        VerifyOutcome.NOT_APPLICABLE
    ] * 6


def test_every_deferred_verdict_records_the_no_broker_reached_justification() -> None:
    """(§4.7 MAJOR-2 정정) The N/A reason is "no broker reached", never "no live arming"."""
    attempt, context = happy_context()
    verification = verify_send_boundary(attempt=attempt, context=context)
    for verdict in verification.verdicts:
        if verdict.disposition is VerifyDisposition.DEFERRED_APPLICABILITY:
            reason = verdict.reason or ""
            assert "no broker route was reached" in reason
            assert "NOT 'no live scope was armed'" in reason
