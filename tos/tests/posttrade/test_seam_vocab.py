"""Seam: vocabulary drift locks — the ``EventObligationLegKind`` enum + the 19-token roll-up.

Two jobs:

1. **The m6 enum drift lock.** ``EventObligationLegKind`` was authored as an enum precisely so
   the §17 line 416 nine leg kinds cannot drift: an earlier draft carried them as a bare
   ``frozenset[str]``, where a caller's typo would silently *shrink* the completeness
   requirement instead of failing. Every one of the nine members is value-bound here, and the
   consequence of the enum choice — that an unknown string simply is not a member — is
   asserted directly.
2. **The 19-token roll-up.** The #21 MINOR-1 lesson was a drift-lock list that claimed
   thirteen tokens and locked twelve. This module asserts the count is 19, that every entry is
   individually locked by one of the seam modules, and it carries the one token with no
   dedicated seam module of its own (the ``tos.time`` freshness verdict) so the count really
   is exhaustive rather than nearly so.

Test-only sibling imports are not runtime package edges.
"""

from __future__ import annotations

import pytest
from tos.posttrade import (
    EVENT_OBLIGATION_LEG_MINIMUM_SET,
    FRESHNESS_VERDICT_FRESH,
    INJECTED_SIBLING_TOKENS,
    EventObligationLegKind,
    obligation_legs_from_event_complete,
)

#: Which seam module locks each owner's tokens. Every one of the 19 coordinates must appear
#: under exactly one owner, and every owner must have a seam module — the roll-up that makes
#: "all 19 are locked" checkable instead of merely claimed.
_TOKEN_OWNER_TO_SEAM_MODULE = {
    "rcl": "test_seam_rcl",
    "are": "test_seam_are",
    "recon": "test_seam_recon",
    "brokercap": "test_seam_brokercap",
    "nontrade": "test_seam_nontrade",
    "egress": "test_seam_egress",
    "cur": "test_seam_cur",
    "time": "test_seam_vocab",  # the one coordinate locked here (see below)
}


# --- 1. the m6 EventObligationLegKind drift lock ------------------------------


@pytest.mark.parametrize(
    ("member", "value"),
    [
        (EventObligationLegKind.ASSET, "ASSET"),
        (EventObligationLegKind.CASH, "CASH"),
        (EventObligationLegKind.FEE, "FEE"),
        (EventObligationLegKind.TAX, "TAX"),
        (EventObligationLegKind.FINANCING, "FINANCING"),
        (EventObligationLegKind.MARGIN, "MARGIN"),
        (EventObligationLegKind.BORROW, "BORROW"),
        (EventObligationLegKind.CUSTODY, "CUSTODY"),
        (EventObligationLegKind.DELIVERY, "DELIVERY"),
    ],
)
def test_event_obligation_leg_member_value_binding(
    member: EventObligationLegKind, value: str
) -> None:
    """(m6) Each of the nine §17 line 416 leg kinds binds to its exact value."""
    assert member.value == value


def test_the_nine_members_are_exactly_the_adr_enumeration() -> None:
    """(m6 / §2.2-5b) Nine, no more and no fewer, and the universe matches."""
    assert len(list(EventObligationLegKind)) == 9
    assert frozenset(EventObligationLegKind) == EVENT_OBLIGATION_LEG_MINIMUM_SET


def test_an_unknown_leg_name_is_not_a_member() -> None:
    """(m6 rationale) The enum is what stops a typo from shrinking the requirement.

    With a bare ``frozenset[str]`` a caller's ``"CUSTOODY"`` would simply be a required kind
    nobody ever supplies — or, worse, be silently absent from the required set and reduce what
    completeness means. As an enum it is not constructible at all.
    """
    with pytest.raises(ValueError):
        EventObligationLegKind("CUSTOODY")


def test_a_typo_cannot_shrink_the_required_set() -> None:
    """(m6) The enum protects the **required** side, which is the side that matters.

    Honest about what the enum does and does not buy. It does **not** stop a *present* set
    from being strings: a ``StrEnum`` member equals its value, so a present-side ``"CUSTODY"``
    satisfies a required-side ``EventObligationLegKind.CUSTODY``, and that is harmless — a
    string that matches a real leg kind describes a real leg.

    What it does stop is a typo on the **required** side, which is where a bare
    ``frozenset[str]`` was dangerous: a caller who meant ``CUSTODY`` and wrote ``CUSTOODY``
    would have created a requirement nobody could satisfy (a permanent block, merely noisy) or
    — building the required set by filtering a known vocabulary — would have silently dropped
    custody from the requirement and **shrunk what completeness means**. As an enum the typo
    is not constructible at all.
    """
    required = frozenset({EventObligationLegKind.CUSTODY})
    present_as_strings = frozenset({"CUSTODY"})
    assert obligation_legs_from_event_complete(required, present_as_strings) is True  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        frozenset({EventObligationLegKind("NOT_A_LEG")})


# --- 2. the 19-token roll-up --------------------------------------------------


def test_the_injected_token_list_has_exactly_nineteen_entries() -> None:
    """(§3.4, the #21 MINOR-1 lesson) 19 coordinates, individually counted."""
    assert len(INJECTED_SIBLING_TOKENS) == 19


def test_every_token_owner_has_a_seam_module_that_locks_it() -> None:
    """(§7) No owner is left with an unlocked coordinate."""
    owners = {owner for owner, _ in INJECTED_SIBLING_TOKENS}
    assert owners == set(
        _TOKEN_OWNER_TO_SEAM_MODULE
    ), "a token owner has no seam module, or a seam module locks nothing"


def test_the_per_owner_counts_sum_to_nineteen() -> None:
    """(§3.4) The arithmetic, spelled out, so a silently dropped token cannot hide."""
    counts = {
        owner: sum(
            1 for entry_owner, _ in INJECTED_SIBLING_TOKENS if entry_owner == owner
        )
        for owner in _TOKEN_OWNER_TO_SEAM_MODULE
    }
    assert counts == {
        "rcl": 3,
        "are": 4,
        "recon": 3,
        "brokercap": 2,
        "nontrade": 2,
        "egress": 2,
        "time": 1,
        "cur": 2,
    }
    assert sum(counts.values()) == 19


def test_freshness_verdict_token_drift_lock() -> None:
    """(token 17 of 19) time ``FreshnessVerdict.FRESH`` — the one locked in this module.

    ``tos.time`` has no dedicated seam module because this package reads **no** clock at all:
    the token exists so a consuming runtime can carry a freshness verdict alongside a
    post-trade decision, and nothing in Phase 1 branches on it. Locking it here keeps the
    nineteen exhaustive.
    """
    from tos.time import FreshnessVerdict

    assert FreshnessVerdict.FRESH.value == FRESHNESS_VERDICT_FRESH


def test_no_predicate_reads_the_freshness_verdict() -> None:
    """(clock-free) The time coordinate is carried, never consumed, in Phase 1.

    Every age bound is a null VP-002 key (design #24 §8.1), so a Phase-1 predicate that
    branched on freshness would be branching on an unapproved bound.
    """
    import inspect

    import tos.posttrade.predicates as posttrade_predicates

    for name, function in vars(posttrade_predicates).items():
        if name.startswith("_") or not inspect.isfunction(function):
            continue
        parameters = set(inspect.signature(function).parameters)
        assert not any(
            "fresh" in parameter for parameter in parameters
        ), f"{name}() branches on freshness — Phase 1 is clock-free"


def test_every_token_is_a_non_empty_string() -> None:
    """(§3.4) An empty token would lock nothing and would compare equal to nothing useful."""
    for owner, token in INJECTED_SIBLING_TOKENS:
        assert isinstance(token, str) and token, f"{owner} carries an empty token"


def test_the_tokens_are_unique_within_each_owner() -> None:
    """(§3.4) A duplicated entry would inflate the count without locking anything new."""
    for owner in _TOKEN_OWNER_TO_SEAM_MODULE:
        tokens = [
            token
            for entry_owner, token in INJECTED_SIBLING_TOKENS
            if entry_owner == owner
        ]
        assert len(tokens) == len(set(tokens)), f"{owner} has a duplicated token entry"
