"""§20 closure-contract 12-item anchor drift + polarity regression (design #28 §6.8b / appendix B).

ADR-002-027 §20 line 490-503 enumerates **twelve** requirements for administrative closure. The item
labels and their polarities are a **manually transcribed** anchor, so this file re-transcribes the ADR
list independently and asserts the code's anchor still matches — a dropped, added or re-ordered item
fails here rather than in a review six cycles later.

Item 11 is the single **negative**-polarity slot: its proposition is that an open parent / child /
overlapping incident / shared cause / common mode **invalidates** closure (§20 line 502), so closure
requires it positively ``False`` (design #28 §4.3 row ``open_parent_present`` / ``common_mode_present``).
Every other slot is positive. An unknown ``None`` denies on **both** polarities.

Regime tag: closure predicate substrate only; closes **no** SIR-EV (SIR-EV-010 is
``EV-L2/3+Security``); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.sir as s
from hypothesis import given

from ._sir_strategies import TRIBOOL, clean_closure_decision, clean_contract_items

#: The ADR §20 line 492-503 twelve requirements, **independently transcribed** in ADR order, each with
#: its polarity (``True`` = positive slot). ``過 0 · 不 0``.
_ADR_CLOSURE_CONTRACT: tuple[tuple[str, bool], ...] = (
    ("SIGNALS_SEVERITY_SCOPE_CLOSURE_COMMON_MODE_CHRONOLOGY_COMPLETE", True),  # 492
    ("RESTRICTION_AND_HARD_FENCE_CURRENT", True),  # 493
    ("BROKER_ATTEMPT_FINAL_QUANTITY_PROOF_OR_OBLIGATION", True),  # 494
    (
        "POSITIONS_ORDERS_FILLS_EXTERNAL_MARGIN_SETTLEMENT_PROTECTION_RECONCILED_OR_RETAINED",
        True,
    ),  # 495
    ("CONTAINMENT_AND_SHUTDOWN_DISPOSITION_EVIDENCE_BACKED", True),  # 496
    ("EVIDENCE_GAPS_RESOLVED_OR_BLOCK", True),  # 497
    ("ROOT_CAUSE_RECORDED_NOT_SUBSTITUTING", True),  # 498
    ("REMEDIATION_AND_ROLLBACK_FRESH_CONFIGURATION", True),  # 499
    ("RECOVERY_OBLIGATIONS_TRANSFERRED_BEHIND_RECOVERY_BARRIER", True),  # 500
    ("INDEPENDENT_EFFECTIVE_PRINCIPAL_REVIEW_OR_SINGLE_OPERATOR_VARIANT", True),  # 501
    ("OPEN_PARENT_CHILD_OVERLAP_SHARED_CAUSE_OR_COMMON_MODE_INVALIDATES", False),  # 502
    ("EXPLICIT_NO_AUTHORITY_STATEMENT", True),  # 503
)


def test_closure_contract_matches_the_adr_twelve_item_anchor() -> None:
    """(§7.2 drift) The item labels equal the ADR §20 line 492-503 list, in order."""
    assert (
        tuple(label for label, _ in _ADR_CLOSURE_CONTRACT) == s.CLOSURE_CONTRACT_ITEMS
    )
    assert s.CLOSURE_CONTRACT_ITEM_COUNT == 12
    assert len(_ADR_CLOSURE_CONTRACT) == 12


def test_closure_contract_polarity_matches_the_adr_anchor() -> None:
    """(§4.3/§6.8b) Item 11 is the only negative slot; every other slot is positive."""
    assert (
        tuple(polarity for _, polarity in _ADR_CLOSURE_CONTRACT)
        == s.CLOSURE_CONTRACT_ITEM_POLARITY
    )
    negatives = [
        index
        for index, positive in enumerate(s.CLOSURE_CONTRACT_ITEM_POLARITY, start=1)
        if not positive
    ]
    assert negatives == [11]


def test_single_operator_variant_is_an_item_ten_satisfaction_path() -> None:
    """(patch v0.2 / §20 item 10) The Governed Single-Operator Re-Arm Variant is folded into item 10."""
    assert "SINGLE_OPERATOR_VARIANT" in s.CLOSURE_CONTRACT_ITEMS[9]
    assert "INDEPENDENT_EFFECTIVE_PRINCIPAL_REVIEW" in s.CLOSURE_CONTRACT_ITEMS[9]


def test_clean_contract_is_complete() -> None:
    """(both-ways positive) Every slot at its declared polarity ⇒ the contract is satisfied."""
    assert s.closure_contract_complete(clean_contract_items()) is True
    assert s.closure_administrative_non_permissive(clean_closure_decision()) is True


def test_empty_contract_denies() -> None:
    """(∅-seal) An empty contract tuple is an under-specified contract ⇒ deny."""
    assert s.closure_contract_complete(()) is False


@pytest.mark.parametrize("index", range(12))
def test_each_slot_is_individually_load_bearing(index: int) -> None:
    """(both-ways) Flipping **any** single slot off its polarity denies the whole contract."""
    items = list(clean_contract_items())
    items[index] = not items[index]
    assert s.closure_contract_complete(tuple(items)) is False


@pytest.mark.parametrize("index", range(12))
@given(value=TRIBOOL)
def test_each_slot_polarity_is_exact(index: int, value: bool | None) -> None:
    """(§4.3) Each slot admits **only** its declared polarity value; ``None`` denies on both."""
    items = list(clean_contract_items())
    items[index] = value
    expected = value is bool(s.CLOSURE_CONTRACT_ITEM_POLARITY[index])
    assert s.closure_contract_complete(tuple(items)) is expected


@given(consumed=TRIBOOL)
def test_single_use_consumed_is_negative_polarity(consumed: bool | None) -> None:
    """(§20 line 505; §4.3 negative) Only an explicit ``False`` clears; ``None`` denies re-use."""
    decision = clean_closure_decision(single_use_consumed=consumed)
    assert s.closure_single_use_non_authorizing(decision) is (consumed is False)
    assert s.closure_administrative_non_permissive(decision) is (consumed is False)


@given(live=TRIBOOL)
def test_consumed_by_live_authority_is_negative_polarity(live: bool | None) -> None:
    """(§20 line 505; §4.3 negative) A live-authority consumption path denies; ``None`` denies too."""
    decision = clean_closure_decision(consumed_by_live_authority=live)
    assert s.closure_single_use_non_authorizing(decision) is (live is False)


def test_absent_closure_denies() -> None:
    """(∅-seal) An absent decision is undecidable ⇒ deny."""
    assert s.closure_single_use_non_authorizing(None) is False
    assert s.closure_administrative_non_permissive(None) is False
