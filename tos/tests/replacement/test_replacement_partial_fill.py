"""Core §5.2 partial-fill properties — 6-target completeness, no-hiding-clamp, egress.

PR-EV-005 **substrate** (ADR §12; PR-AC-005). **Discipline tag**: the ``EV-L1`` slice
only — the ``/3`` integration-fault and adversarial-interleaving overlay plus independent
review remain open, so **no PR-EV is closed here** (design #18 §1).

The two negative-polarity flags on this path (``hides_uncovered_or_reversing``,
``became_risk_increasing``) are the v1.1 C1 lesson in miniature: their safe value is
``False``, so the gate must be ``is False`` and never ``is not True`` — a ``None``
passing an ``is not True`` gate is precisely the fail-open that was removed at the source.
Every property below drives all three tri-bool values, not just ``True`` / ``False``.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.replacement import (
    ReevaluationTargetKind,
    ReplacementOutcome,
    no_hiding_clamp,
    partial_fill_egress_disposition,
    partial_fill_reevaluation_complete,
)

from ._replacement_strategies import (
    ALL_TARGETS,
    NON_FALSE_VALUES,
    TARGET_SETS,
    TRIBOOL,
    TRUTHY_NON_BOOL,
)

# ===========================================================================
# 6-target atomic re-evaluation completeness (§12 line 291-298)
# ===========================================================================


@given(reevaluated=TARGET_SETS, recognized=TRIBOOL)
def test_completeness_is_recognition_and_full_target_coverage(
    reevaluated: frozenset[ReevaluationTargetKind], recognized: bool | None
) -> None:
    """(§12 line 291) ⇔ ``fill_recognized is True`` ∧ ``required <= reevaluated``."""
    result = partial_fill_reevaluation_complete(
        reevaluated, ALL_TARGETS, fill_recognized=recognized
    )
    assert result is (recognized is True and reevaluated >= ALL_TARGETS)


@given(missing=st.sampled_from(list(ReevaluationTargetKind)))
def test_dropping_any_single_target_leaves_a_stale_calculation(
    missing: ReevaluationTargetKind,
) -> None:
    """(guard fires, all 6) Each of the six targets is individually load-bearing.

    §12 line 291 says the re-evaluation is **atomic** — six of six, or the calculation
    that was not redone is stale.
    """
    assert (
        partial_fill_reevaluation_complete(
            ALL_TARGETS - {missing}, ALL_TARGETS, fill_recognized=True
        )
        is False
    )


def test_full_reevaluation_of_a_recognized_fill_passes() -> None:
    """(passing side, PR-AC-005) Six of six on a recognized fill is complete."""
    assert (
        partial_fill_reevaluation_complete(
            ALL_TARGETS, ALL_TARGETS, fill_recognized=True
        )
        is True
    )


def test_empty_target_universe_is_restrictive_not_vacuously_complete() -> None:
    """(§4.7 row 2) An empty required universe would certify completeness vacuously."""
    assert (
        partial_fill_reevaluation_complete(
            frozenset(), frozenset(), fill_recognized=True
        )
        is False
    )
    assert (
        partial_fill_reevaluation_complete(
            ALL_TARGETS, frozenset(), fill_recognized=True
        )
        is False
    )


@given(forged=st.sampled_from(TRUTHY_NON_BOOL))
def test_a_truthy_non_bool_recognition_never_completes(forged: object) -> None:
    """(polarity) ``fill_recognized`` is positive polarity — only the singleton ``True``."""
    assert (
        partial_fill_reevaluation_complete(
            ALL_TARGETS,
            ALL_TARGETS,
            fill_recognized=forged,  # type: ignore[arg-type]
        )
        is False
    )


# ===========================================================================
# no-hiding-clamp (§12 line 302) — negative polarity
# ===========================================================================


@given(clamp=TRIBOOL, hides=TRIBOOL)
def test_no_hiding_clamp_is_negative_polarity_is_false_only(
    clamp: bool | None, hides: bool | None
) -> None:
    """(§12 line 302 / §0.1(j)) ``True`` **only** when hiding is positively excluded."""
    assert no_hiding_clamp(clamp_applied=clamp, hides_uncovered_or_reversing=hides) is (
        hides is False
    )


@given(non_false=st.sampled_from(NON_FALSE_VALUES))
def test_an_is_not_true_gate_would_have_passed_these_but_is_false_does_not(
    non_false: object,
) -> None:
    """(C1 regression) ``None`` / falsy-but-not-``False`` values must **not** clear the gate.

    An ``is not True`` gate — the v1.0 shape — would have cleared every one of these.
    """
    assert (
        no_hiding_clamp(
            clamp_applied=True,
            hides_uncovered_or_reversing=non_false,  # type: ignore[arg-type]
        )
        is False
    )


@given(clamp=TRIBOOL)
def test_the_clamp_applied_coordinate_never_changes_the_verdict(
    clamp: bool | None,
) -> None:
    """(contract lock) §12 line 302 forbids *hiding*, not *clamping*.

    ``clamp_applied`` is the retained §12 coordinate; the rule is about whether uncovered
    or reversing quantity is hidden. This property pins that reading so it cannot silently
    drift into an extra (or a missing) gate: a clamp that hides nothing passes, and no
    value of ``clamp_applied`` can rescue a hiding clamp.
    """
    assert (
        no_hiding_clamp(clamp_applied=clamp, hides_uncovered_or_reversing=False) is True
    )
    assert (
        no_hiding_clamp(clamp_applied=clamp, hides_uncovered_or_reversing=True) is False
    )
    assert (
        no_hiding_clamp(clamp_applied=clamp, hides_uncovered_or_reversing=None) is False
    )


# ===========================================================================
# risk-increasing egress disposition (§12 line 300) — negative polarity
# ===========================================================================


@given(risk_increasing=TRIBOOL, transmitted=TRIBOOL)
def test_egress_disposition_truth_table(
    risk_increasing: bool | None, transmitted: bool | None
) -> None:
    """(§12 line 300 / C1) ADMISSIBLE only from ``became_risk_increasing is False``.

    ``None`` is treated **as risk-increasing** (never waved through), and an unknown
    transmission state takes the heavier containment branch rather than a bare denial.
    """
    outcome = partial_fill_egress_disposition(
        became_risk_increasing=risk_increasing, already_transmitted=transmitted
    )
    if risk_increasing is False:
        assert outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    elif transmitted is False:
        assert outcome is ReplacementOutcome.REPLACEMENT_DENIED
    else:
        assert outcome is ReplacementOutcome.REPLACEMENT_CONTAINED


def test_named_canary_risk_increasing_change_is_denied_or_contained_both_ways() -> None:
    """(named canary: became-risk-increasing) Guard fires, and the clean case proceeds."""
    # (a) guard fires — not yet transmitted ⇒ deny the egress
    assert (
        partial_fill_egress_disposition(
            became_risk_increasing=True, already_transmitted=False
        )
        is ReplacementOutcome.REPLACEMENT_DENIED
    )
    # (a) guard fires — already transmitted ⇒ §17 containment, denial is insufficient
    assert (
        partial_fill_egress_disposition(
            became_risk_increasing=True, already_transmitted=True
        )
        is ReplacementOutcome.REPLACEMENT_CONTAINED
    )
    # (a) guard fires — unknown risk direction is conservatively risk-increasing
    assert (
        partial_fill_egress_disposition(
            became_risk_increasing=None, already_transmitted=False
        )
        is ReplacementOutcome.REPLACEMENT_DENIED
    )
    # (b) passing side — a proven non-risk-increasing change proceeds
    assert (
        partial_fill_egress_disposition(
            became_risk_increasing=False, already_transmitted=False
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


@given(forged=st.sampled_from(NON_FALSE_VALUES))
def test_a_non_false_risk_flag_never_reaches_admissible(forged: object) -> None:
    """(C1 regression) Only the singleton ``False`` reaches the permissive identity."""
    outcome = partial_fill_egress_disposition(
        became_risk_increasing=forged,  # type: ignore[arg-type]
        already_transmitted=False,
    )
    assert outcome is not ReplacementOutcome.REPLACEMENT_ADMISSIBLE
