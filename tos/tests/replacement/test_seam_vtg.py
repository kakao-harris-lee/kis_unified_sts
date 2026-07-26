"""MANDATED test-only seam cross-check: replacement <-> venue / ADR-002-019 (§3.4, v1.2).

This is the seam design #18 §7 listed but v1.1 could not write: the ADR-002-019 producer
did not exist in code yet. It landed as ``tos.venue`` (design #19, commit ``9eb13bba``
lineage / ``9b68d1be``), so the deferral is over and the seam is now **measured**, which
is what the v1.2 errata records.

**The shape mismatch this file pins.** The real producer is
:class:`~tos.venue.vocabulary.OrderAdmissibilityResult` — a **four**-token,
**truthy-untestable** StrEnum (``bool()`` raises ``TypeError``), whereas the replacement
``leg_admissibility`` slot is ``bool | None``. The ratified folding rule (design #18 v1.2
errata §3.4) is **caller-side and conservative**::

    leg_admissibility = (result is OrderAdmissibilityResult.ADMISSIBLE)

so ``RESTRICTED_PROTECTIVE_ONLY``, ``INADMISSIBLE``, ``UNKNOWN``, and ``None`` all fold to
not-``True`` and fail closed. ``RESTRICTED_PROTECTIVE_ONLY`` folding to ``False`` on the
**direct** path is deliberate, not an oversight: ADR-002-019 §1 line 29 / §19 line 426
permit **no ordinary new risk** under it.

**The one sanctioned way past it** is the **venue-owned**
:func:`~tos.venue.predicates.protective_label_no_bypass` (``predicates.py:599``): a
protective-labelled leg with a separate protective authority and capacity cover for every
credible intermediate effect yields a ``bool`` the caller then supplies to the slot.
``tos.replacement`` re-decides none of that — it consumes the produced bool (sibling edge
0, design #18 §0.2/§3.5). Re-implementing the protective-only carve-out here would be
exactly the authority duplication §3.5 forbids.

A test-only cross-import is **not** a runtime package edge (design #18 §3.4(d)/§7.1); the
§7.1 allowlist closure test still asserts ``tos.venue`` is absent from the runtime closure.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.replacement import (
    ORDER_ADMISSIBILITY_ADMISSIBLE,
    ReplacementMode,
    ReplacementOutcome,
    cancel_first_admission_gate,
    cancel_first_admission_outcome,
    overlap_first_reservation_outcome,
    overlap_first_sequencing_valid,
    replacement_mode_admissible,
)
from tos.venue import OrderAdmissibilityResult, protective_label_no_bypass

from ._replacement_strategies import (
    ALL_OUTCOMES,
    clean_claim,
    clean_conditions,
    clean_mode_inputs,
    clean_sequencing_inputs,
)

#: The four real producer tokens plus the ``None`` (no decision at all) case.
_TOKENS_OR_NONE: list[OrderAdmissibilityResult | None] = [
    *OrderAdmissibilityResult,
    None,
]


def _fold(result: OrderAdmissibilityResult | None) -> bool:
    """The ratified caller-side folding rule (design #18 v1.2 errata §3.4).

    ``True`` **only** on the positive ``ADMISSIBLE`` identity. Written with ``is`` and
    never with ``bool(result)`` / ``if result:`` — the producer's ``__bool__`` raises, and
    even if it did not, ``RESTRICTED_PROTECTIVE_ONLY`` is a non-empty (truthy) string that
    would read as full permission.
    """
    return result is OrderAdmissibilityResult.ADMISSIBLE


# ---------------------------------------------------------------------------
# Token drift lock + the truthy-untestable seal
# ---------------------------------------------------------------------------


def test_the_order_admissibility_token_matches_the_real_venue_member() -> None:
    """(drift lock) replacement's local token is the live ADR-002-019 enum value."""
    assert OrderAdmissibilityResult.ADMISSIBLE.value == ORDER_ADMISSIBILITY_ADMISSIBLE


def test_the_producer_has_exactly_the_four_adr_tokens() -> None:
    """(ADR-002-019 §5.4 line 123, count = 4) Four results, three of them denials here."""
    assert {member.value for member in OrderAdmissibilityResult} == {
        "ADMISSIBLE",
        "RESTRICTED_PROTECTIVE_ONLY",
        "INADMISSIBLE",
        "UNKNOWN",
    }
    assert len(OrderAdmissibilityResult) == 4


@given(token=st.sampled_from(list(OrderAdmissibilityResult)))
def test_every_producer_token_is_truthy_untestable(
    token: OrderAdmissibilityResult,
) -> None:
    """(design #19 seal) ``bool(token)`` raises — a bare truthiness fold is impossible.

    This is *stronger* than the protective ``Admissibility`` seam, where the denial tokens
    are merely truthy. Here the misuse is a loud ``TypeError``, so the folding rule cannot
    silently degrade into ``bool(result)``.
    """
    with pytest.raises(TypeError):
        bool(token)


def test_the_folding_helper_does_not_rely_on_truthiness() -> None:
    """(seal parity) The fold survives the ``__bool__`` trap for all four tokens."""
    for token in OrderAdmissibilityResult:
        assert isinstance(_fold(token), bool)


# ---------------------------------------------------------------------------
# Exhaustive polarity: 4 tokens + None across the three consuming predicates
# ---------------------------------------------------------------------------


@given(token=st.sampled_from(_TOKENS_OR_NONE))
def test_sequencing_admits_only_the_admissible_token(
    token: OrderAdmissibilityResult | None,
) -> None:
    """(§4.1 (iv) / §5 line 139 (B)) Only ``ADMISSIBLE`` folds to a passing leg."""
    leg = _fold(token)
    assert overlap_first_sequencing_valid(
        **clean_sequencing_inputs(leg_admissibility=leg)
    ) is (token is OrderAdmissibilityResult.ADMISSIBLE)


@given(token=st.sampled_from(_TOKENS_OR_NONE))
def test_cancel_first_gate_admits_only_the_admissible_token(
    token: OrderAdmissibilityResult | None,
) -> None:
    """(§4.3 M1-② / §5 line 139 (B)) A cancellation-involving leg needs exact -019."""
    leg = _fold(token)
    admitted = token is OrderAdmissibilityResult.ADMISSIBLE
    assert (
        cancel_first_admission_gate(clean_conditions(), leg_admissibility=leg)
        is admitted
    )
    outcome = cancel_first_admission_outcome(clean_conditions(), leg_admissibility=leg)
    if admitted:
        assert outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    else:
        assert outcome is ReplacementOutcome.REPLACEMENT_TRAPPED


@given(token=st.sampled_from(_TOKENS_OR_NONE))
def test_mode_composition_traps_on_every_non_admissible_token(
    token: OrderAdmissibilityResult | None,
) -> None:
    """(§5.3 M1) The mode composition point is "every leg positively ``ADMISSIBLE``"."""
    outcome = replacement_mode_admissible(
        ReplacementMode.OVERLAP_FIRST,
        **clean_mode_inputs(leg_admissibilities=frozenset({_fold(token)})),
    )
    if token is OrderAdmissibilityResult.ADMISSIBLE:
        assert outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    else:
        assert outcome is ReplacementOutcome.REPLACEMENT_TRAPPED


@given(token=st.sampled_from(_TOKENS_OR_NONE))
def test_overlap_first_outcome_traps_on_every_non_admissible_token(
    token: OrderAdmissibilityResult | None,
) -> None:
    """(§4.7 row 9) A non-``ADMISSIBLE`` leg is ``REPLACEMENT_TRAPPED``, never denied-only."""
    outcome = overlap_first_reservation_outcome(
        clean_claim(),
        ALL_OUTCOMES,
        within_hard_envelope=True,
        leg_admissibility=_fold(token),
    )
    if token is OrderAdmissibilityResult.ADMISSIBLE:
        assert outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    else:
        assert outcome is ReplacementOutcome.REPLACEMENT_TRAPPED


def test_restricted_protective_only_does_not_fold_true_on_the_direct_path() -> None:
    """(ADR-002-019 §1 line 29 / §19 line 426) Protective-only is **not** ordinary permission.

    The catastrophic misreading design #19 seals against is treating
    ``RESTRICTED_PROTECTIVE_ONLY`` as a pass. The direct fold refuses it, and every
    consuming replacement predicate therefore refuses too.
    """
    restricted = OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY
    assert _fold(restricted) is False
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(leg_admissibility=_fold(restricted))
        )
        is False
    )
    assert (
        cancel_first_admission_outcome(
            clean_conditions(), leg_admissibility=_fold(restricted)
        )
        is ReplacementOutcome.REPLACEMENT_TRAPPED
    )
    # Causal isolation: only the token changes and everything flips together.
    assert _fold(OrderAdmissibilityResult.ADMISSIBLE) is True


# ---------------------------------------------------------------------------
# The one sanctioned carve-out: venue-owned protective_label_no_bypass
# ---------------------------------------------------------------------------


def test_the_protective_only_carve_out_runs_through_the_venue_predicate() -> None:
    """(§3.5 ownership) venue decides the protective-only path; replacement consumes it.

    VTG-INV-007: "Protective or containment use requires exact current admissibility,
    separate protective classification and authority, and conservative capacity for every
    credible intermediate effect." All four conditions positively held ⇒ venue produces
    ``True`` ⇒ the caller supplies that bool to ``leg_admissibility`` ⇒ the protective leg
    proceeds under ``RESTRICTED_PROTECTIVE_ONLY``, which the direct fold alone refused.
    """
    produced = protective_label_no_bypass(
        True,  # label_is_protective
        OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY,
        True,  # separate_protective_authority
        True,  # intermediate_effects_capacity_covered
    )
    assert produced is True
    # The direct fold said False; the venue-produced bool says True. replacement simply
    # consumes whichever bool the caller supplies — it re-decides nothing.
    assert _fold(OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY) is False
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(leg_admissibility=produced)
        )
        is True
    )
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST,
            **clean_mode_inputs(leg_admissibilities=frozenset({produced})),
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


@given(
    missing=st.sampled_from(
        [
            "label_is_protective",
            "separate_protective_authority",
            "intermediate_effects_capacity_covered",
        ]
    ),
    broken=st.sampled_from([False, None]),
)
def test_the_carve_out_fails_closed_on_any_missing_condition(
    missing: str, broken: bool | None
) -> None:
    """(VTG-INV-007, causal isolation) Any one missing condition traps the leg."""
    kwargs: dict[str, bool | None] = {
        "label_is_protective": True,
        "separate_protective_authority": True,
        "intermediate_effects_capacity_covered": True,
    }
    kwargs[missing] = broken
    produced = protective_label_no_bypass(
        kwargs["label_is_protective"],
        OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY,
        kwargs["separate_protective_authority"],
        kwargs["intermediate_effects_capacity_covered"],
    )
    assert produced is False
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST,
            **clean_mode_inputs(leg_admissibilities=frozenset({produced})),
        )
        is ReplacementOutcome.REPLACEMENT_TRAPPED
    )


def test_the_carve_out_refuses_an_inadmissible_or_unknown_token() -> None:
    """(VTG-INV-007 (ii)) A protective label never bypasses a denial verdict."""
    for token in (
        OrderAdmissibilityResult.INADMISSIBLE,
        OrderAdmissibilityResult.UNKNOWN,
    ):
        assert protective_label_no_bypass(True, token, True, True) is False


def test_replacement_does_not_re_author_the_order_admissibility_decision() -> None:
    """(§0.2 / §3.5) No -019 verdict, tradability, or protective-bypass rule lives here."""
    from tos import replacement as replacement_pkg

    for forbidden in (
        "OrderAdmissibilityResult",
        "OrderAdmissibilityDecision",
        "TradabilityState",
        "protective_label_no_bypass",
        "order_admissible",
        "exact_admissibility",
    ):
        assert not hasattr(replacement_pkg, forbidden), (
            f"{forbidden} re-authors the ADR-002-019 producer — design #18 §3.5 assigns "
            "it to venue and consumes only the folded bool"
        )
