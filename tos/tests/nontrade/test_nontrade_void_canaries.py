"""§4.7 ∅-void regression — the 15 rows, **1:1**, each in **both** directions.

Design #21 §4.7 tabulates fifteen empty / unproven inputs, and §7 lists the same fifteen as
the mandated void cases. This module is the 1:1 realization: one test per row, numbered to
match, each asserting

* the **prohibited direction** — the guard actually fires (no vacuous admit), and
* the **permitted direction** — the legitimate input still passes (no vacuous block).

A vacuous *block* is as much a defect as a vacuous admit: the former violates safety, the
latter availability (design #21 §4.7 "양방향 규율"). Every row also asserts the resulting
:class:`~tos.nontrade.NonTradeDisposition`, because §4.7's last column is the disposition
each row folds into — the C1 requirement that no row is left to an ownerless downstream.
"""

from __future__ import annotations

from decimal import Decimal

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
    NonTradeEventWorkflowState,
    TransitionEnvelope,
    correction_reversal_idempotent,
    favorable_netting_absent,
    material_change_trigger_nonempty,
    nontrade_authority_effect_all_false,
    nontrade_disposition,
    split_polarity_coherent,
    transformation_residual_conservative,
    transformation_units_and_rounding_explicit,
    transition_envelope_complete,
)

from ._nontrade_strategies import (
    ALL_LEGS,
    clean_disposition_inputs,
    clean_envelope,
    clean_spec,
    issue_correction,
    issue_event,
)

#: The §4.7 table has fifteen rows; §7 lists fifteen void cases. A drift in either would
#: break the 1:1 mapping this module realizes.
VOID_ROW_COUNT = 15


def test_the_void_row_count_is_fifteen() -> None:
    """(§4.7 ↔ §7) The table and the harness list stay the same length."""
    realized = [
        name
        for name in globals()
        if name.startswith("test_row_") and callable(globals()[name])
    ]
    assert len(realized) == VOID_ROW_COUNT, sorted(realized)


# ---------------------------------------------------------------------------
# Row 1 — empty required-leg set
# ---------------------------------------------------------------------------


def test_row_01_empty_required_leg_set() -> None:
    """(§4.7 row 1) ∅ required legs ⇒ ``False`` **inside** the predicate ⇒ block."""
    # prohibited direction
    assert transition_envelope_complete(clean_envelope(), frozenset()) is False
    assert (
        nontrade_disposition(**clean_disposition_inputs(envelope_complete=False))
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )
    # permitted direction
    assert transition_envelope_complete(clean_envelope(), ALL_LEGS) is True
    assert (
        nontrade_disposition(**clean_disposition_inputs())
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


# ---------------------------------------------------------------------------
# Row 2 — pre/post exposure None or negative (structural no-netting)
# ---------------------------------------------------------------------------


def test_row_02_missing_or_negative_exposure() -> None:
    """(§4.7 row 2) Netting unproven ⇒ ``False`` ⇒ block; coexisting magnitudes ⇒ pass."""
    assert favorable_netting_absent(clean_envelope(pre_event_exposure=None)) is False
    assert (
        favorable_netting_absent(
            clean_envelope(post_event_credible_exposure=Decimal("-1"))
        )
        is False
    )
    assert (
        nontrade_disposition(**clean_disposition_inputs(netting_absent=False))
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )
    assert favorable_netting_absent(clean_envelope()) is True


# ---------------------------------------------------------------------------
# Row 3 — a missing polarity magnitude
# ---------------------------------------------------------------------------


def test_row_03_missing_polarity_magnitude() -> None:
    """(§4.7 row 3) Any of the four magnitudes ``None`` ⇒ no derivation ⇒ block."""
    for field in ("pre_quantity", "post_quantity", "pre_basis", "post_basis"):
        assert split_polarity_coherent(clean_spec(**{field: None})) is False
    assert (
        nontrade_disposition(**clean_disposition_inputs(polarity_coherent=False))
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )
    assert split_polarity_coherent(clean_spec()) is True


# ---------------------------------------------------------------------------
# Row 4 — missing unit spec / rounding rule
# ---------------------------------------------------------------------------


def test_row_04_missing_units_or_rounding() -> None:
    """(§4.7 row 4 / §11 line 227) Either token missing ⇒ block; both declared ⇒ pass."""
    for field in ("unit_spec", "rounding_rule"):
        assert (
            transformation_units_and_rounding_explicit(clean_spec(**{field: None}))
            is False
        )
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(units_and_rounding_explicit=False)
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )
    assert transformation_units_and_rounding_explicit(clean_spec()) is True


# ---------------------------------------------------------------------------
# Row 5 — absent residual
# ---------------------------------------------------------------------------


def test_row_05_absent_residual() -> None:
    """(§4.7 row 5 / §11 line 240) A hidden residual ⇒ block; an explicit one ⇒ pass."""
    for field in ("fractional_residual", "cash_in_lieu"):
        assert (
            transformation_residual_conservative(clean_spec(**{field: None})) is False
        )
    assert (
        nontrade_disposition(**clean_disposition_inputs(residual_conservative=False))
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )
    assert transformation_residual_conservative(clean_spec()) is True


# ---------------------------------------------------------------------------
# Row 6 — empty change-trigger set (M3, both materiality directions)
# ---------------------------------------------------------------------------


def test_row_06_empty_change_trigger_set() -> None:
    """(§4.7 row 6) Material **or unknown** materiality + ∅ triggers ⇒ block.

    The unknown case is asserted separately because reading ``None`` as an exemption is the
    exact fail-open the design caught in its own self-verification pass.
    """
    assert material_change_trigger_nonempty(True, frozenset()) is False
    assert material_change_trigger_nonempty(None, frozenset()) is False
    for materiality in (True, None):
        assert (
            nontrade_disposition(
                **clean_disposition_inputs(
                    event_is_material=materiality,
                    material_change_triggers_present=False,
                )
            )
            is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
        )
    # permitted direction: positively proven non-materiality exempts, and a material event
    # that names its triggers passes
    assert material_change_trigger_nonempty(False, frozenset()) is True
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                event_is_material=False, material_change_triggers_present=False
            )
        )
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )
    assert material_change_trigger_nonempty(True, frozenset({"venue-snapshot-1"})) is (
        True
    )


# ---------------------------------------------------------------------------
# Row 7 — missing supersedes reference
# ---------------------------------------------------------------------------


def test_row_07_missing_supersedes_ref() -> None:
    """(§4.7 row 7 / §16 line 311) No lineage ⇒ ``REJECTED_NO_LINEAGE`` ⇒ block."""
    lineage_less = issue_correction(supersedes_ref=None)
    assert (
        correction_reversal_idempotent(lineage_less, None, True)
        is CorrectionReversalOutcome.REJECTED_NO_LINEAGE
    )
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                correction_outcome=CorrectionReversalOutcome.REJECTED_NO_LINEAGE
            )
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )
    # permitted direction
    assert (
        correction_reversal_idempotent(issue_correction(), None, True)
        is CorrectionReversalOutcome.APPLIED_ONCE
    )


# ---------------------------------------------------------------------------
# Row 8 — CRITICAL_CONFLICT (same primary id, different bytes)
# ---------------------------------------------------------------------------


def test_row_08_critical_conflict() -> None:
    """(§4.7 row 8) Record forgery ⇒ ``REJECTED_CONFLICT`` ⇒ ``NONTRADE_CONFLICTED``."""
    incoming = issue_correction()
    forged = issue_correction(correction_kind="REVERSAL")
    assert (
        correction_reversal_idempotent(incoming, forged, True)
        is CorrectionReversalOutcome.REJECTED_CONFLICT
    )
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                correction_outcome=CorrectionReversalOutcome.REJECTED_CONFLICT
            )
        )
        is NonTradeDisposition.NONTRADE_CONFLICTED
    )
    # permitted direction: same id, SAME bytes is a harmless replay
    assert (
        correction_reversal_idempotent(incoming, issue_correction(), True)
        is CorrectionReversalOutcome.IDEMPOTENT_REPLAY
    )


# ---------------------------------------------------------------------------
# Row 9 — DIVERGENT_EMISSION (same idempotency key, different bytes)
# ---------------------------------------------------------------------------


def test_row_09_divergent_emission() -> None:
    """(§4.7 row 9) Two corrections claiming one key ⇒ ``REJECTED_CONFLICT`` ⇒ conflicted."""
    first = issue_correction(correction_id="nt-corr-a")
    second = issue_correction(correction_id="nt-corr-b", correction_kind="REVERSAL")
    assert first.idempotency_key == second.idempotency_key
    assert (
        correction_reversal_idempotent(first, second, True)
        is CorrectionReversalOutcome.REJECTED_CONFLICT
    )
    # permitted direction: same key, SAME bytes is a replay, not a divergence
    same_bytes = issue_correction(correction_id="nt-corr-a")
    assert (
        correction_reversal_idempotent(first, same_bytes, True)
        is CorrectionReversalOutcome.IDEMPOTENT_REPLAY
    )


# ---------------------------------------------------------------------------
# Row 10 — DISTINCT / NOT_COMPARABLE
# ---------------------------------------------------------------------------


def test_row_10_distinct_or_not_comparable() -> None:
    """(§4.7 row 10) Undecidable ⇒ ``REJECTED_UNKNOWN`` ⇒ ``NONTRADE_QUARANTINED_UNKNOWN``."""
    incoming = issue_correction(correction_id="nt-corr-a", idempotency_key="idem-a")
    unrelated = issue_correction(correction_id="nt-corr-b", idempotency_key="idem-b")
    assert (
        correction_reversal_idempotent(incoming, unrelated, True)
        is CorrectionReversalOutcome.REJECTED_UNKNOWN
    )
    draft = issue_correction().model_copy(update={"canonical_digest": None})
    assert (
        correction_reversal_idempotent(incoming, draft, True)
        is CorrectionReversalOutcome.REJECTED_UNKNOWN
    )
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                correction_outcome=CorrectionReversalOutcome.REJECTED_UNKNOWN
            )
        )
        is NonTradeDisposition.NONTRADE_QUARANTINED_UNKNOWN
    )
    # permitted direction: a legitimate FIRST correction never reaches the classifier
    assert (
        correction_reversal_idempotent(incoming, None, True)
        is CorrectionReversalOutcome.APPLIED_ONCE
    )


# ---------------------------------------------------------------------------
# Row 11 — None aggregate risk / capacity (are + rcl injections)
# ---------------------------------------------------------------------------


def test_row_11_unknown_risk_or_capacity() -> None:
    """(§4.7 row 11) An unbounded credible space or unknown capacity ⇒ block."""
    for override in (
        {"injected_worst_intermediate_risk": None},
        {"injected_credible_space_bounded": None},
        {"injected_credible_space_bounded": False},
        {"injected_union_capacity_known": None},
        {"injected_union_capacity_known": False},
    ):
        assert (
            nontrade_disposition(**clean_disposition_inputs(**override))
            is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
        )
    # permitted direction
    assert (
        nontrade_disposition(**clean_disposition_inputs())
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


# ---------------------------------------------------------------------------
# Row 12 — RESTRICTED_PROTECTIVE_ONLY
# ---------------------------------------------------------------------------


def test_row_12_restricted_protective_only() -> None:
    """(§4.7 row 12 / M6) Ordinary new risk blocked; the exposure is **not** trapped.

    Trapping it (the v1.0 blanket fold) would have been an availability violation against
    §18 line 348, which permits a newly authorized recovery or protective action.
    """
    restricted = clean_disposition_inputs(
        admissibility=ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY
    )
    assert (
        nontrade_disposition(**restricted)
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )
    assert (
        nontrade_disposition(**{**restricted, "protective_action_may_proceed": True})
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    ), "the protective coordinate travels with the decision but never upgrades it"
    # permitted direction
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(admissibility=ORDER_ADMISSIBILITY_ADMISSIBLE)
        )
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


# ---------------------------------------------------------------------------
# Row 13 — INADMISSIBLE / UNKNOWN / None admissibility
# ---------------------------------------------------------------------------


def test_row_13_no_fresh_exact_decision() -> None:
    """(§4.7 row 13 / §12 line 252) Trapped exposure, **unconditionally** — never zero risk."""
    for token in (
        ORDER_ADMISSIBILITY_INADMISSIBLE,
        ORDER_ADMISSIBILITY_UNKNOWN,
        None,
    ):
        assert (
            nontrade_disposition(**clean_disposition_inputs(admissibility=token))
            is NonTradeDisposition.NONTRADE_TRAPPED
        )
        # the inconsistent injection must not relax the trap
        assert (
            nontrade_disposition(
                **clean_disposition_inputs(
                    admissibility=token, protective_action_may_proceed=True
                )
            )
            is NonTradeDisposition.NONTRADE_TRAPPED
        )
    # permitted direction
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(admissibility=ORDER_ADMISSIBILITY_ADMISSIBLE)
        )
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


# ---------------------------------------------------------------------------
# Row 14 — UNKNOWN / CONFLICTED field confidence (recon injection)
# ---------------------------------------------------------------------------


def test_row_14_unknown_or_conflicted_field_confidence() -> None:
    """(§4.7 row 14) UNKNOWN ⇒ quarantine, CONFLICTED ⇒ conflicted, ∅ ⇒ block."""
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                field_confidences=frozenset({FIELD_CONFIDENCE_UNKNOWN})
            )
        )
        is NonTradeDisposition.NONTRADE_QUARANTINED_UNKNOWN
    )
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                field_confidences=frozenset({FIELD_CONFIDENCE_CONFLICTED})
            )
        )
        is NonTradeDisposition.NONTRADE_CONFLICTED
    )
    assert (
        nontrade_disposition(**clean_disposition_inputs(field_confidences=frozenset()))
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )
    # permitted direction
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                field_confidences=frozenset({FIELD_CONFIDENCE_CORROBORATED})
            )
        )
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


# ---------------------------------------------------------------------------
# Row 15 — any workflow label grants nothing
# ---------------------------------------------------------------------------


def test_row_15_no_workflow_label_changes_the_disposition() -> None:
    """(§4.7 row 15 / §6 line 144) A label grants nothing and moves nothing.

    There is deliberately **no** availability side here: a label never authorizes anything,
    so the only assertion is that no state — not even ``RECONCILED`` — is a permission, and
    that the disposition is invariant across all eleven states.
    """
    baseline = nontrade_disposition(**clean_disposition_inputs())
    for state in NonTradeEventWorkflowState:
        event = issue_event(workflow_state=state)
        assert nontrade_authority_effect_all_false(event.authority_effect) is True
        # the disposition takes no workflow state at all — the label cannot reach it
        assert nontrade_disposition(**clean_disposition_inputs()) is baseline
    # an empty envelope with no state at all likewise grants nothing
    assert transition_envelope_complete(TransitionEnvelope(), ALL_LEGS) is False
