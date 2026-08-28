"""MANDATED test-only seam cross-check: nontrade <-> rcl / ADR-002-002+012 (§3.4(d)).

``tos.nontrade`` does **not** import ``tos.rcl`` at runtime, and that is the most
load-bearing absence in the package: design #21 §0.4c considered the ``CapacityVector``
REUSE and **rejected** it. ADR-002-010 §10 line 217 seals the direction — "Only the Risk
Capacity Ledger may mutate capacity. The event processor ... may propose a remap but SHALL
NOT update capacity independently" — so this package is a remap **proposer**, never a
committer.

The proposition this file pins is the **∅ fail-closed equivalence** (design #21 §5.1): rcl
``credible_union_capacity`` **raises** ``ValueError`` on an empty history set ("an empty
history set must not be read as zero capacity to cover"), and
``transition_envelope_complete`` returns ``False`` on an empty required-leg set. Different
mechanisms, **one proposition**: an empty input is the absence of a proof, never a proof of
absence. (The design records why nontrade returns ``False`` rather than raising: it is a
pure ``bool`` predicate whose caller folds the result into a disposition, and an exception
would break that fold.)

A test-only cross-import is **not** a runtime package edge (design #21 §3.4(d)/§7.1).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.nontrade import (
    CAPACITY_STATE_QUARANTINED_UNKNOWN,
    CAPACITY_STATE_TRAPPED_CONSUMED,
    TRANSITION_CAUSE_RECOGNIZED_EXTERNAL_CHANGE,
    CredibleTransitionLegKind,
    NonTradeDisposition,
    NonTradeEventWorkflowState,
    nontrade_disposition,
    transition_envelope_complete,
)
from tos.rcl import (
    CapacityComponent,
    CapacityState,
    CapacityVector,
    CredibleHistory,
    TransitionCause,
    credible_union_capacity,
)

from ._nontrade_strategies import ALL_LEGS, clean_disposition_inputs, clean_envelope

_DIMENSION = "economic-exposure-dimension-1"


def _history(magnitude: Decimal | None, *, bounded: bool) -> CredibleHistory:
    """One reconstructable history on the injected economic dimension."""
    return CredibleHistory(
        history_id=f"h-{magnitude}-{bounded}",
        capacity=CapacityVector(
            components=(
                CapacityComponent(dimension_id=_DIMENSION, magnitude=magnitude),
            )
        ),
        bounded=bounded,
    )


# ---------------------------------------------------------------------------
# The ∅ fail-closed equivalence (§5.1 C1)
# ---------------------------------------------------------------------------


def test_the_empty_input_proposition_is_identical_on_both_sides() -> None:
    """(C1) rcl raises, nontrade returns ``False`` — one proposition, two mechanisms.

    Neither side reads "no input" as "nothing to cover". The mechanisms differ only because
    nontrade is a pure ``bool`` predicate folded into a disposition.
    """
    with pytest.raises(ValueError, match="empty history set"):
        credible_union_capacity([])
    assert transition_envelope_complete(clean_envelope(), frozenset()) is False
    assert (
        nontrade_disposition(**clean_disposition_inputs(envelope_complete=False))
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


def test_a_non_empty_input_is_decidable_on_both_sides() -> None:
    """(availability side) Neither guard is a blanket block."""
    union = credible_union_capacity([_history(Decimal("7"), bounded=True)])
    assert union.components[0].magnitude == Decimal("7")
    assert transition_envelope_complete(clean_envelope(), ALL_LEGS) is True


def test_an_unbounded_history_makes_every_dimension_unknown() -> None:
    """(rcl §18 line 472) An unbounded history is capacity-consuming UNKNOWN, never dropped.

    nontrade consumes that as ``injected_union_capacity_known`` and blocks — the same
    conservative direction on both sides of the seam.
    """
    union = credible_union_capacity(
        [_history(Decimal("7"), bounded=True), _history(Decimal("5"), bounded=False)]
    )
    magnitude = union.components[0].magnitude
    assert magnitude is None
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                injected_union_capacity_known=magnitude is not None
            )
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


def test_the_union_is_a_union_not_a_chosen_branch() -> None:
    """(rcl §18 line 472) No last-write-wins — which is why nontrade never merges either."""
    union = credible_union_capacity(
        [_history(Decimal("7"), bounded=True), _history(Decimal("5"), bounded=True)]
    )
    assert union.components[0].magnitude == Decimal("7")


# ---------------------------------------------------------------------------
# Ownership: propose, never commit (§10 line 217)
# ---------------------------------------------------------------------------


def test_nontrade_proposes_a_cause_and_never_mutates_capacity() -> None:
    """(§10 line 217) The recognized external change is a **cause token**, not a mutation."""
    assert (
        TransitionCause.RECOGNIZED_EXTERNAL_CHANGE.value
        == TRANSITION_CAUSE_RECOGNIZED_EXTERNAL_CHANGE
    )
    from tos import nontrade as nontrade_pkg

    for forbidden in (
        "CapacityVector",
        "CapacityComponent",
        "CapacityState",
        "TransitionCause",
        "credible_union_capacity",
        "aggregate_usage",
        "effective_limit",
        "commit_capacity",
        "release_capacity",
        "remap_capacity",
    ):
        assert not hasattr(nontrade_pkg, forbidden), (
            f"{forbidden} is rcl-owned — §10 line 217 makes the event processor a remap "
            "proposer, never a capacity mutator"
        )


def test_the_capacity_state_tokens_are_drift_locked() -> None:
    """(§3.4 drift lock) The two rcl states nontrade recognizes still exist by these names."""
    assert CapacityState.TRAPPED_CONSUMED.value == CAPACITY_STATE_TRAPPED_CONSUMED
    assert CapacityState.QUARANTINED_UNKNOWN.value == CAPACITY_STATE_QUARANTINED_UNKNOWN


def test_the_capacity_axis_is_not_the_nontrade_event_axis() -> None:
    """(§2.2-5) ``QUARANTINED_UNKNOWN`` on two axes is two **types**, not one meaning.

    The tokens overlap because the ADR uses the same word for the event workflow and for
    the capacity state; the types never do, and nontrade cannot coerce one onto the other
    because it imports neither.
    """
    assert (
        NonTradeEventWorkflowState.QUARANTINED_UNKNOWN
        is not CapacityState.QUARANTINED_UNKNOWN
    )
    assert NonTradeDisposition.NONTRADE_TRAPPED is not CapacityState.TRAPPED_CONSUMED
    # the disposition members are prefixed, so even the strings stay disjoint
    assert set(NonTradeDisposition).isdisjoint(set(CapacityState))


def test_the_leg_axis_is_not_the_capacity_dimension_axis() -> None:
    """(§0.4c reason i) A transition leg is not a capacity dimension id."""
    union = credible_union_capacity([_history(Decimal("7"), bounded=True)])
    assert union.components[0].dimension_id == _DIMENSION
    assert _DIMENSION not in {leg.value for leg in CredibleTransitionLegKind}
