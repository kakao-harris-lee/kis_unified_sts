"""§5.5 ``nontrade_disposition`` — the sole ``NonTradeDisposition`` producer (C1).

*Discipline tag: predicate / coordinate substrate only; NT-EV-001..012 are all
``NOT_IMPLEMENTED``. No EV-L1-complete claim. Closing NT-EV = 0.*

The v1.0 defect this file regresses against is a vocabulary with **no producer**: the five
dispositions existed and every ∅ row "folded" into one of them, but no function returned
any of them. §5.5 made this the single producer, so this module pins:

* the **total order** of the five ranks (a simultaneous conflict / trap / incompleteness
  always returns the most conservative member);
* the **fall-through ban** — ``NONTRADE_ADMISSIBLE`` is reachable only through the full
  positive conjunction plus the exact ``ADMISSIBLE`` identity; knocking any single conjunct
  down to ``None`` blocks immediately;
* the **rank-3 unconditionality** — ``protective_action_may_proceed`` cannot relax a trap,
  even when injected inconsistently.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.nontrade import (
    FIELD_CONFIDENCE_CONFLICTED,
    FIELD_CONFIDENCE_CORROBORATED,
    FIELD_CONFIDENCE_UNKNOWN,
    ORDER_ADMISSIBILITY_ADMISSIBLE,
    ORDER_ADMISSIBILITY_INADMISSIBLE,
    ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY,
    ORDER_ADMISSIBILITY_UNKNOWN,
    CorrectionReversalOutcome,
    NonTradeDisposition,
    nontrade_disposition,
)

from ._nontrade_strategies import (
    ADMISSIBILITY_FORGERIES,
    ADMISSIBILITY_OR_FORGERY,
    FIELD_CONFIDENCE_SETS,
    NON_ADMISSIBLE_TOKENS,
    TRIBOOL,
    TRUTHY_NON_BOOL,
    clean_disposition_inputs,
)

#: The conjunct arguments that must each be ``is True`` for rank 5.
_POSITIVE_CONJUNCTS = (
    "envelope_complete",
    "netting_absent",
    "polarity_coherent",
    "units_and_rounding_explicit",
    "residual_conservative",
    "lineage_preserved",
    "effective_window_blocks",
    "material_change_triggers_present",
    "injected_credible_space_bounded",
    "injected_union_capacity_known",
)


# ---------------------------------------------------------------------------
# Availability side — the clean fixture really is admissible
# ---------------------------------------------------------------------------


def test_the_clean_input_set_reaches_admissible() -> None:
    """(both-ways, availability) A vacuous *block* is as much a defect as a vacuous admit."""
    assert (
        nontrade_disposition(**clean_disposition_inputs())
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


def test_an_event_without_a_transformation_or_correction_is_still_admissible() -> None:
    """(§5.5) The two optional groups are optional — ``None`` means "not accompanied"."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                polarity_coherent=None,
                units_and_rounding_explicit=None,
                residual_conservative=None,
                correction_outcome=None,
            )
        )
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


def test_an_idempotent_replay_is_an_acceptable_correction_outcome() -> None:
    """(§5.5) A harmless re-apply does not block; only the ``REJECTED_*`` members do."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                correction_outcome=CorrectionReversalOutcome.IDEMPOTENT_REPLAY
            )
        )
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


# ---------------------------------------------------------------------------
# Fall-through ban (§5.5 / the #16 CRITICAL lesson)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("conjunct", _POSITIVE_CONJUNCTS)
@pytest.mark.parametrize("degraded", [None, False])
def test_knocking_any_single_conjunct_down_blocks_immediately(
    conjunct: str, degraded: object
) -> None:
    """(§5.5) ``NONTRADE_ADMISSIBLE`` is a positive conjunction, never a dispatch residue."""
    assert (
        nontrade_disposition(**clean_disposition_inputs(**{conjunct: degraded}))
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


@pytest.mark.parametrize("conjunct", _POSITIVE_CONJUNCTS)
@pytest.mark.parametrize("truthy", TRUTHY_NON_BOOL)
def test_a_truthy_non_bool_conjunct_does_not_satisfy_the_is_true_gate(
    conjunct: str, truthy: object
) -> None:
    """(§0.1(8)) Positive polarity is ``is True`` only — ``1`` / ``"yes"`` / ``[1]`` fail."""
    assert (
        nontrade_disposition(**clean_disposition_inputs(**{conjunct: truthy}))
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


def test_a_partially_proven_transformation_blocks() -> None:
    """(§5.2/§5.5) All three transformation verdicts are required once one is present."""
    for present, absent_pair in (
        ("polarity_coherent", ("units_and_rounding_explicit", "residual_conservative")),
        ("units_and_rounding_explicit", ("polarity_coherent", "residual_conservative")),
        ("residual_conservative", ("polarity_coherent", "units_and_rounding_explicit")),
    ):
        overrides = dict.fromkeys(absent_pair)
        overrides[present] = True
        assert (
            nontrade_disposition(**clean_disposition_inputs(**overrides))
            is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
        ), f"{present} alone must not promote an unproven transformation"


def test_a_missing_or_non_finite_risk_magnitude_blocks() -> None:
    """(§4.7 row 11) are's projection must be a present finite magnitude."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(injected_worst_intermediate_risk=None)
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(injected_worst_intermediate_risk=Decimal("NaN"))
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


# ---------------------------------------------------------------------------
# Evidence axis (recon tokens)
# ---------------------------------------------------------------------------


def test_an_empty_field_confidence_set_blocks_rather_than_passing_vacuously() -> None:
    """(∅ structural guard, isomorphic to §5.1 C1) ``∅ <= {CORROBORATED}`` is vacuously True.

    "No field carries any evidence" must never read as "every field is corroborated", so
    the non-emptiness is required alongside the subset relation.
    """
    assert (
        nontrade_disposition(**clean_disposition_inputs(field_confidences=frozenset()))
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


@pytest.mark.parametrize("weak", ["SINGLE_SOURCE", "STALE"])
def test_a_non_corroborated_grade_blocks(weak: str) -> None:
    """(§7 line 159/161) One source is not corroboration and stale is not fresh."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                field_confidences=frozenset({FIELD_CONFIDENCE_CORROBORATED, weak})
            )
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


def test_a_conflicted_field_is_rank_one() -> None:
    """(§18 line 344 / §4.7 row 14) Contradiction outranks everything else."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                field_confidences=frozenset({FIELD_CONFIDENCE_CONFLICTED})
            )
        )
        is NonTradeDisposition.NONTRADE_CONFLICTED
    )


def test_an_unknown_field_is_rank_two() -> None:
    """(§4.5 line 95 / §4.7 row 14) Unattributable evidence quarantines."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                field_confidences=frozenset({FIELD_CONFIDENCE_UNKNOWN})
            )
        )
        is NonTradeDisposition.NONTRADE_QUARANTINED_UNKNOWN
    )


# ---------------------------------------------------------------------------
# The admissibility three-way fold (M6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token", [ORDER_ADMISSIBILITY_INADMISSIBLE, ORDER_ADMISSIBILITY_UNKNOWN, None]
)
def test_no_fresh_exact_decision_is_trapped(token: str | None) -> None:
    """(§12 line 252 / §4.7 row 13) Inability to exit is trapped exposure, never zero risk."""
    assert (
        nontrade_disposition(**clean_disposition_inputs(admissibility=token))
        is NonTradeDisposition.NONTRADE_TRAPPED
    )


def test_restricted_protective_only_blocks_but_does_not_trap() -> None:
    """(M6 / §4.7 row 12) Ordinary new risk is barred; the protective path stays open.

    Folding it into the trapped bucket (the v1.0 reading) was an availability violation
    against §18 line 348 "permit **only** newly authorized recovery or protective action".
    """
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                admissibility=ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY
            )
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


@pytest.mark.parametrize("forged", ADMISSIBILITY_FORGERIES)
def test_an_unrecognized_admissibility_token_traps(forged: object) -> None:
    """(fall-through ban) A forged / drifted token is not a decision at all.

    Rank 3 is written as "not one of the two ordinary tokens", so a lowercase variant, a
    nonsense string, or a truthy non-string lands in the **most conservative** bucket
    instead of falling through to a block or, worse, an admit.
    """
    assert (
        nontrade_disposition(**clean_disposition_inputs(admissibility=forged))
        is NonTradeDisposition.NONTRADE_TRAPPED
    )


@given(ADMISSIBILITY_OR_FORGERY)
def test_only_the_exact_admissible_identity_can_reach_rank_five(
    token: object,
) -> None:
    """(§5.5) Even a fully proven conjunction needs the exact ``ADMISSIBLE`` token."""
    result = nontrade_disposition(**clean_disposition_inputs(admissibility=token))
    if token == ORDER_ADMISSIBILITY_ADMISSIBLE:
        assert result is NonTradeDisposition.NONTRADE_ADMISSIBLE
    else:
        assert result is not NonTradeDisposition.NONTRADE_ADMISSIBLE


# ---------------------------------------------------------------------------
# Rank-3 unconditionality (the inconsistent-injection fail-open)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", NON_ADMISSIBLE_TOKENS)
@pytest.mark.parametrize("protective", [True, False, None])
def test_the_protective_flag_never_changes_the_disposition(
    token: str | None, protective: bool | None
) -> None:
    """(§5.5) ``protective_action_may_proceed`` is structurally unable to relax any rank.

    The dangerous combination is an ``INADMISSIBLE`` token injected together with a ``True``
    protective flag: had rank 3 been conditional, that pair would have *relaxed* a trap into
    a block. venue never emits it, but this package imports no sibling and therefore trusts
    no injected pair.
    """
    baseline = nontrade_disposition(
        **clean_disposition_inputs(
            admissibility=token, protective_action_may_proceed=None
        )
    )
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                admissibility=token, protective_action_may_proceed=protective
            )
        )
        is baseline
    )


@given(TRIBOOL)
def test_the_protective_flag_cannot_manufacture_an_admissible_either(
    protective: bool | None,
) -> None:
    """(§4.4) The disposition itself never authorizes a protective action."""
    blocked = clean_disposition_inputs(
        envelope_complete=False, protective_action_may_proceed=protective
    )
    assert (
        nontrade_disposition(**blocked) is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


# ---------------------------------------------------------------------------
# The rank total order
# ---------------------------------------------------------------------------


def test_conflict_outranks_quarantine_trap_and_block() -> None:
    """(§5.5 total order) All four failures at once ⇒ the most conservative member."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                field_confidences=frozenset(
                    {FIELD_CONFIDENCE_CONFLICTED, FIELD_CONFIDENCE_UNKNOWN}
                ),
                correction_outcome=CorrectionReversalOutcome.REJECTED_CONFLICT,
                admissibility=ORDER_ADMISSIBILITY_INADMISSIBLE,
                envelope_complete=False,
            )
        )
        is NonTradeDisposition.NONTRADE_CONFLICTED
    )


def test_quarantine_outranks_trap_and_block() -> None:
    """(§5.5 total order) rank 2 beats ranks 3 and 4."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                field_confidences=frozenset({FIELD_CONFIDENCE_UNKNOWN}),
                admissibility=ORDER_ADMISSIBILITY_INADMISSIBLE,
                envelope_complete=False,
            )
        )
        is NonTradeDisposition.NONTRADE_QUARANTINED_UNKNOWN
    )


def test_trap_outranks_block() -> None:
    """(§5.5 total order) rank 3 beats rank 4 — an incomplete envelope does not downgrade it."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                admissibility=ORDER_ADMISSIBILITY_UNKNOWN, envelope_complete=False
            )
        )
        is NonTradeDisposition.NONTRADE_TRAPPED
    )
    # ...and with the token restored, the same incomplete envelope is only a block.
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                admissibility=ORDER_ADMISSIBILITY_ADMISSIBLE, envelope_complete=False
            )
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


def test_a_rejected_correction_outcome_maps_to_its_rank() -> None:
    """(§4.7 rows 8/9/10) ``REJECTED_CONFLICT`` ⇒ rank 1; ``REJECTED_UNKNOWN`` ⇒ rank 2."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                correction_outcome=CorrectionReversalOutcome.REJECTED_CONFLICT
            )
        )
        is NonTradeDisposition.NONTRADE_CONFLICTED
    )
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                correction_outcome=CorrectionReversalOutcome.REJECTED_UNKNOWN
            )
        )
        is NonTradeDisposition.NONTRADE_QUARANTINED_UNKNOWN
    )
    for blocked in (
        CorrectionReversalOutcome.REJECTED_NO_LINEAGE,
        CorrectionReversalOutcome.REJECTED_OVERWRITE,
    ):
        assert (
            nontrade_disposition(**clean_disposition_inputs(correction_outcome=blocked))
            is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
        )


# ---------------------------------------------------------------------------
# Materiality relaxation polarity (§6.3)
# ---------------------------------------------------------------------------


def test_only_positively_proven_non_materiality_exempts_the_trigger_conjunct() -> None:
    """(§6.3) ``None`` materiality is material — ``is not True`` must never exempt."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                event_is_material=False, material_change_triggers_present=False
            )
        )
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )
    for material in (True, None):
        assert (
            nontrade_disposition(
                **clean_disposition_inputs(
                    event_is_material=material,
                    material_change_triggers_present=False,
                )
            )
            is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
        )


# ---------------------------------------------------------------------------
# Determinism + total coverage
# ---------------------------------------------------------------------------


@given(
    FIELD_CONFIDENCE_SETS,
    ADMISSIBILITY_OR_FORGERY,
    TRIBOOL,
    TRIBOOL,
    st.sampled_from([*CorrectionReversalOutcome, None]),
)
def test_the_producer_is_total_and_deterministic(
    field_confidences: frozenset[str],
    admissibility: object,
    envelope_complete: object,
    protective: bool | None,
    correction_outcome: object,
) -> None:
    """(§5.5) Every input combination returns exactly one member, reproducibly."""
    kwargs = clean_disposition_inputs(
        field_confidences=field_confidences,
        admissibility=admissibility,
        envelope_complete=envelope_complete,
        protective_action_may_proceed=protective,
        correction_outcome=correction_outcome,
    )
    first = nontrade_disposition(**kwargs)
    assert first in set(NonTradeDisposition)
    assert nontrade_disposition(**kwargs) is first


def test_the_disposition_is_not_truthy_testable() -> None:
    """(§2.2-6) A consuming gate must use identity, never ``if disposition:``."""
    trapped = nontrade_disposition(**clean_disposition_inputs(admissibility=None))
    with pytest.raises(TypeError):
        bool(trapped)
    assert trapped is NonTradeDisposition.NONTRADE_TRAPPED
