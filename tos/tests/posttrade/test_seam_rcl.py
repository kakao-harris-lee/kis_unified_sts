"""Seam: ``tos.posttrade`` <-> ``tos.rcl`` — the strongest ownership boundary in the package.

**Proposition identity (design #24 §3.5 verdict 4) — the seam this test exists to fix.**
rcl's ``TransitionCause.FINAL_QUANTITY_PROOF`` is the **proof-gated release of order
capacity**; this package's ``FinalityDimensionKind.ORDER_FQP`` is **one of ten post-trade
finality dimensions and implies none of the other nine**. ADR-002-030 §1 line 23 verbatim:
"Final Quantity Proof establishes only final cumulative filled quantity and zero remaining
executable quantity ... **It does not prove any post-trade obligation final.**" The two are
different propositions on different axes and the token overlap is intentional.

**Capacity is rcl's alone.** §1 line 21 verbatim: "The Risk Capacity Ledger remains the sole
capacity mutation and serialization authority ... an obligation compiler, Reconciliation
Service, PTOL, position or cash projection, statement processor, evidence service, recovery
workflow, operator, or finality proof SHALL NOT create, change, quarantine, transfer, remap,
or release capacity" (PTF-INV-008). §21 line 492: an obligation closure "may transfer
consumption rather than release it" — and only the RCL performs that transition. This package
is therefore **capacity-non-mutating by structural absence**, not by a rule.

Locks **3** of the 19 injected tokens: ``FINAL_QUANTITY_PROOF``, ``TRAPPED_CONSUMED``,
``QUARANTINED_UNKNOWN``. Test-only sibling imports are not runtime package edges.
"""

from __future__ import annotations

import pytest
import tos.posttrade.predicates as posttrade_predicates
import tos.posttrade.records as posttrade_records
from tos.posttrade import (
    CAPACITY_STATE_QUARANTINED_UNKNOWN,
    CAPACITY_STATE_TRAPPED_CONSUMED,
    TRANSITION_CAUSE_FINAL_QUANTITY_PROOF,
    FinalityDimensionKind,
    PostTradeDisposition,
    finality_dimensions_orthogonal,
)

from ._posttrade_strategies import proof_map_only


def test_final_quantity_proof_token_drift_lock() -> None:
    """(token 1 of 19) The rcl ``TransitionCause.FINAL_QUANTITY_PROOF`` member value."""
    from tos.rcl import TransitionCause

    assert (
        TransitionCause.FINAL_QUANTITY_PROOF.value
        == TRANSITION_CAUSE_FINAL_QUANTITY_PROOF
    )


def test_capacity_state_token_drift_locks() -> None:
    """(tokens 2-3 of 19) The two rcl ``CapacityState`` members this package coordinates on."""
    from tos.rcl import CapacityState

    assert CapacityState.TRAPPED_CONSUMED.value == CAPACITY_STATE_TRAPPED_CONSUMED
    assert CapacityState.QUARANTINED_UNKNOWN.value == CAPACITY_STATE_QUARANTINED_UNKNOWN


def test_rcl_final_quantity_proof_is_not_post_trade_finality() -> None:
    """(§3.5 verdict 4 / §1 line 23) Same words, different propositions, different types.

    rcl's cause releases **order capacity**; our dimension is one of ten post-trade axes.
    Proving ours proves nothing about the other nine — least of all about capacity.
    """
    from tos.rcl import TransitionCause

    fqp_only = proof_map_only(FinalityDimensionKind.ORDER_FQP)
    assert (
        finality_dimensions_orthogonal(FinalityDimensionKind.ORDER_FQP, fqp_only)
        is True
    )
    for other in FinalityDimensionKind:
        if other is FinalityDimensionKind.ORDER_FQP:
            continue
        assert finality_dimensions_orthogonal(other, fqp_only) is False

    # the token overlaps in wording; the types never do
    assert TransitionCause.FINAL_QUANTITY_PROOF.value == "FINAL_QUANTITY_PROOF"
    assert FinalityDimensionKind.ORDER_FQP.value == "ORDER_FQP"
    assert type(TransitionCause.FINAL_QUANTITY_PROOF) is not FinalityDimensionKind


def test_the_capacity_states_are_a_different_axis_from_our_dispositions() -> None:
    """(§2.2-6 coordinate non-collapse) ``TRAPPED_CONSUMED`` is capacity, not disposition."""
    from tos.rcl import CapacityState

    assert (
        CapacityState.TRAPPED_CONSUMED.value
        != PostTradeDisposition.POST_TRADE_TRAPPED.value
    )
    assert type(CapacityState.TRAPPED_CONSUMED) is not PostTradeDisposition


def test_the_empty_input_proposition_matches_rcls() -> None:
    """(§5.1 ∅ guard) rcl raises on an empty union; this package returns ``False``.

    Two expressions of one fail-closed proposition: an empty credible set is not "no risk",
    it is "nothing was proven". rcl is the sole capacity authority and may raise; a pure
    decision kernel returns the restrictive verdict instead.
    """
    from tos.rcl import credible_union_capacity

    with pytest.raises(ValueError):
        credible_union_capacity([])
    assert finality_dimensions_orthogonal(FinalityDimensionKind.SETTLEMENT, {}) is False


def test_this_package_cannot_mutate_capacity() -> None:
    """(§1 line 21 / PTF-INV-008) Structural absence — there is nothing to call.

    Not "a predicate that refuses to release capacity", but **no predicate, no field, and no
    method that could**. The one boolean that names the act is forced ``False`` at
    construction, and even that is a defence-in-depth re-check rather than the enforcement.
    """
    for forbidden in (
        "release_capacity",
        "reserve_capacity",
        "commit_capacity",
        "transfer_capacity",
        "quarantine_capacity",
        "remap_capacity",
        "credible_union_capacity",
    ):
        assert not hasattr(posttrade_predicates, forbidden)
        assert not hasattr(posttrade_records, forbidden)


def test_a_finality_proven_obligation_still_releases_nothing() -> None:
    """(§21 line 492 / PTF-INV-009) Closure **transfers** consumption; it never releases.

    And the transfer is rcl's transition, not ours.
    """
    from tos.posttrade import (
        PostTradeObligationLifecycleState,
        post_trade_consequence_all_false,
    )

    from ._posttrade_strategies import clean_obligation_record

    proven = clean_obligation_record(
        lifecycle_state=PostTradeObligationLifecycleState.FINALITY_PROVEN
    )
    assert post_trade_consequence_all_false(proven.consequence) is True
    assert proven.consequence.releases_capacity is False
