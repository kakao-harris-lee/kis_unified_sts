"""MANDATED test-only seam cross-check: nontrade <-> venue / ADR-002-019 (§3.4(d)).

``tos.nontrade`` does **not** import ``tos.venue`` at runtime (sibling edge 0); the §7.1
closure test asserts that absence and this file asserts the **consequence** — that the
seam behaves the way the contract claims with the real producer on the other side.

Three judgments are locked here:

1. **the ∅-closure direction (M3)** — venue's ``material_change_closure`` legitimately
   returns the empty set for an empty trigger input ("no change, nothing invalidated — the
   availability side"). That is correct *on venue's side*, and it is exactly why the
   non-emptiness obligation lives on **this** side: a material event handed over with an
   empty trigger set would invalidate nothing and leave every stale snapshot alive. Both
   directions are driven through the **real** venue predicate;
2. **the three-way admissibility fold (M6)** — the real producer is a **four**-token,
   truthy-untestable ``StrEnum``. ``ADMISSIBLE`` is the ordinary pass;
   ``RESTRICTED_PROTECTIVE_ONLY`` blocks ordinary new risk but is **not** trapped (a
   separately authorized protective action may proceed through the venue-owned
   ``protective_label_no_bypass``, which this package consumes and never re-decides);
   ``INADMISSIBLE`` / ``UNKNOWN`` / ``None`` are trapped;
3. **token drift** — the local constants are locked against the live members, so a rename
   on venue's side breaks here rather than silently degrading a comparison to ``False``.

A test-only cross-import is **not** a runtime package edge (design #21 §3.4(d)/§7.1).
"""

from __future__ import annotations

import pytest
from tos.nontrade import (
    ORDER_ADMISSIBILITY_ADMISSIBLE,
    ORDER_ADMISSIBILITY_INADMISSIBLE,
    ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY,
    ORDER_ADMISSIBILITY_UNKNOWN,
    ORDINARY_NEW_RISK_ADMISSIBILITY_TOKENS,
    NonTradeDisposition,
    instrument_lineage_preserved,
    material_change_trigger_nonempty,
    nontrade_disposition,
)
from tos.venue import (
    OrderAdmissibilityResult,
    material_change_closure,
    protective_label_no_bypass,
)

from ._nontrade_strategies import clean_disposition_inputs, clean_lineage_inputs

#: A small constraint dependency graph: a venue snapshot feeds an admissibility decision,
#: which feeds a final egress permission.
_DEP_GRAPH = {
    "venue-snapshot-1": frozenset({"admissibility-decision-1"}),
    "admissibility-decision-1": frozenset({"egress-permission-1"}),
}


# ---------------------------------------------------------------------------
# 1. The ∅-closure direction (M3)
# ---------------------------------------------------------------------------


def test_venue_really_returns_the_empty_closure_for_an_empty_trigger_set() -> None:
    """(M3 premise) The fail-open this package guards against is **measured**, not assumed.

    venue's docstring says an empty ``change_triggers`` yields the empty set. This drives
    the real predicate to prove it, so the nontrade guard is protecting against a real
    behaviour rather than a remembered one.
    """
    assert material_change_closure(_DEP_GRAPH, frozenset()) == frozenset()


def test_a_material_event_with_no_triggers_is_blocked_on_the_nontrade_side() -> None:
    """(M3 prohibited direction) Nothing is invalidated, so nothing may proceed.

    Causal isolation: the same venue call, the same graph — only the nontrade guard
    distinguishes the material case from the non-material one.
    """
    closure = material_change_closure(_DEP_GRAPH, frozenset())
    assert closure == frozenset(), "no snapshot or decision was invalidated"
    assert material_change_trigger_nonempty(True, frozenset()) is False
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                event_is_material=True, material_change_triggers_present=False
            )
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


def test_unknown_materiality_is_material_across_the_seam() -> None:
    """(M3 / venue §5.8) ``None`` materiality gets the same treatment as ``True``.

    Reading ``None`` as an exemption would skip the invalidation wholesale — the fail-open
    the design caught in its own self-verification pass.
    """
    assert material_change_closure(_DEP_GRAPH, frozenset()) == frozenset()
    assert material_change_trigger_nonempty(None, frozenset()) is False


def test_a_material_event_with_triggers_invalidates_the_whole_downstream_reach() -> (
    None
):
    """(M3 permitted direction) A named trigger reaches the decision and the egress."""
    triggers = frozenset({"venue-snapshot-1"})
    assert material_change_trigger_nonempty(True, triggers) is True
    closure = material_change_closure(_DEP_GRAPH, triggers)
    assert closure == frozenset(
        {"venue-snapshot-1", "admissibility-decision-1", "egress-permission-1"}
    ), "venue owns the reach; nontrade only proves the trigger set is non-empty"


def test_a_non_material_event_may_legitimately_invalidate_nothing() -> None:
    """(M3 availability direction) A valid decision is not spuriously invalidated.

    This is venue's stated availability side, and the nontrade guard exempts exactly here —
    on the **positive** proof of non-materiality, never on a ``None``.
    """
    assert material_change_trigger_nonempty(False, frozenset()) is True
    assert material_change_closure(_DEP_GRAPH, frozenset()) == frozenset()


def test_venue_expands_an_unproven_edge_and_nontrade_does_not_second_guess_it() -> None:
    """(§3.5) The unproven-edge expansion is venue's conservatism, consumed as-is."""
    unproven = {"venue-snapshot-1": frozenset({"unknown-dependent-1"})}
    closure = material_change_closure(
        _DEP_GRAPH, frozenset({"venue-snapshot-1"}), unproven=unproven
    )
    assert "unknown-dependent-1" in closure
    from tos import nontrade as nontrade_pkg

    assert not hasattr(nontrade_pkg, "material_change_closure")


# ---------------------------------------------------------------------------
# 2. The three-way admissibility fold (M6)
# ---------------------------------------------------------------------------


def test_the_producer_is_truthy_untestable_on_every_token() -> None:
    """(§4) ``bool(result)`` raises — including on ``RESTRICTED_PROTECTIVE_ONLY``.

    Reading protective-only as full permission is the catastrophic misuse the seal exists
    for, so the seal is confirmed against the **real** producer, not our local copy.
    """
    for member in OrderAdmissibilityResult:
        with pytest.raises(TypeError):
            bool(member)


@pytest.mark.parametrize(
    "result", [*OrderAdmissibilityResult, None], ids=lambda value: str(value)
)
def test_the_four_tokens_plus_none_fold_three_ways(
    result: OrderAdmissibilityResult | None,
) -> None:
    """(M6) ADMISSIBLE ⇒ ordinary; RESTRICTED ⇒ block; the rest ⇒ trapped.

    The token crosses the seam as the **real member** here (a ``StrEnum`` equals its
    value), proving the ``==``-against-a-local-constant comparison genuinely recognizes the
    live producer's output.
    """
    lineage = instrument_lineage_preserved(**clean_lineage_inputs(admissibility=result))
    disposition = nontrade_disposition(
        **clean_disposition_inputs(admissibility=result, lineage_preserved=lineage)
    )
    if result is OrderAdmissibilityResult.ADMISSIBLE:
        assert lineage is True
        assert disposition is NonTradeDisposition.NONTRADE_ADMISSIBLE
    elif result is OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY:
        assert lineage is False
        assert disposition is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    else:
        assert lineage is False
        assert disposition is NonTradeDisposition.NONTRADE_TRAPPED


def test_the_protective_path_is_venue_owned_and_only_consumed_here() -> None:
    """(M6 / §3.5) The four-condition carve-out is venue's; nontrade takes the bool.

    The real ``protective_label_no_bypass`` is driven for both a passing and a failing
    condition set, and the produced bool is what travels — nontrade re-decides none of it.
    """
    may_proceed = protective_label_no_bypass(
        True,
        OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY,
        True,
        True,
    )
    assert may_proceed is True
    # ...and any missing condition fails closed on venue's side
    for degraded in (
        (None, OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY, True, True),
        (True, OrderAdmissibilityResult.INADMISSIBLE, True, True),
        (True, OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY, None, True),
        (True, OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY, True, None),
    ):
        assert protective_label_no_bypass(*degraded) is False

    # nontrade consumes the produced bool and never upgrades the disposition with it
    restricted = clean_disposition_inputs(
        admissibility=OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY,
        lineage_preserved=False,
        protective_action_may_proceed=may_proceed,
    )
    assert (
        nontrade_disposition(**restricted)
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )
    from tos import nontrade as nontrade_pkg

    assert not hasattr(nontrade_pkg, "protective_label_no_bypass")


def test_venue_never_emits_the_inconsistent_pair_that_nontrade_still_absorbs() -> None:
    """(§5.5 rank-3 rationale) The pair cannot arise through venue — and is absorbed anyway.

    ``protective_label_no_bypass`` returns ``True`` only for ``ADMISSIBLE`` /
    ``RESTRICTED_PROTECTIVE_ONLY``, so ``INADMISSIBLE`` + ``True`` is impossible via venue.
    nontrade imports no sibling and therefore trusts no injected pair: the trap holds.
    """
    assert (
        protective_label_no_bypass(
            True, OrderAdmissibilityResult.INADMISSIBLE, True, True
        )
        is False
    )
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                admissibility=OrderAdmissibilityResult.INADMISSIBLE,
                protective_action_may_proceed=True,
            )
        )
        is NonTradeDisposition.NONTRADE_TRAPPED
    )


# ---------------------------------------------------------------------------
# 3. Token drift locks
# ---------------------------------------------------------------------------


def test_the_local_admissibility_tokens_match_the_live_members() -> None:
    """(§3.4 drift lock) A venue rename must break here, not degrade a comparison."""
    assert OrderAdmissibilityResult.ADMISSIBLE.value == ORDER_ADMISSIBILITY_ADMISSIBLE
    assert (
        OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY.value
        == ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY
    )
    assert (
        OrderAdmissibilityResult.INADMISSIBLE.value == ORDER_ADMISSIBILITY_INADMISSIBLE
    )
    assert OrderAdmissibilityResult.UNKNOWN.value == ORDER_ADMISSIBILITY_UNKNOWN
    assert (
        len(OrderAdmissibilityResult) == 4
    ), "the fold covers the whole producer domain"


def test_the_ordinary_token_tuple_is_exactly_the_two_non_trapped_members() -> None:
    """(§5.5 rank 3) Everything else — including an unrecognized token — traps."""
    assert set(ORDINARY_NEW_RISK_ADMISSIBILITY_TOKENS) == {
        OrderAdmissibilityResult.ADMISSIBLE.value,
        OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY.value,
    }
    assert OrderAdmissibilityResult.INADMISSIBLE not in (
        ORDINARY_NEW_RISK_ADMISSIBILITY_TOKENS
    )
    assert OrderAdmissibilityResult.UNKNOWN not in (
        ORDINARY_NEW_RISK_ADMISSIBILITY_TOKENS
    )
