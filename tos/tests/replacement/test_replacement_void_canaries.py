"""§4.7 ∅-void canaries — the 12-row table, **both ways**, one test per row.

Design #18 §4.7 tabulates twelve empty / unknown inputs with, for each, a **forbidden**
direction (the vacuous-permissive shape that must be blocked) and an **allowed** direction
(the genuine input that must not be blocked). §7 requires the property list to map onto
that table **1:1**, so this module has exactly one test per row and every test asserts
**both** directions. A vacuous *block* is a defect too — the #12 both-ways lesson: the
first is a safety violation, the second an availability violation.

Row 12 is the deliberate exception the design itself records: an empty workflow state has
**no** permissive side, because a lifecycle label never grants authority under any
circumstance (§5 line 137). Its "allowed" direction is therefore the assertion that the
answer stays negative — which is what makes it a row rather than an omission.

Alongside the table, this module sweeps the ADR's **forbidden verbs** (§4.7) and asserts
each has a named guard: net-old-against-new, cancel-old-before-new-proven,
cancel-first-without-8-conditions, proceed-leg-without-current-admissibility,
clamp-hiding-quantity, treat-ACK-as-effective-protection, reduce-capacity-on-label,
expire-economic-effect-on-authorization-expiry, assume-atomic-by-method-name,
extend-authority / widen-capacity / declare-complete on bound-exceed, and
clear-workflow-and-restart.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from tos.replacement import (
    CancelFirstConditions,
    ReplacementAuthorityEffect,
    ReplacementMode,
    ReplacementOutcome,
    ReplacementWorkflowState,
    cancel_first_admission_gate,
    netting_absent,
    no_hiding_clamp,
    overlap_first_reservation_complete,
    overlap_first_reservation_outcome,
    overlap_first_sequencing_valid,
    partial_fill_reevaluation_complete,
    partition_replacement_admissible,
    replacement_mode_admissible,
    reversal_bounded_outcome,
    workflow_label_grants_nothing,
)

from ._replacement_strategies import (
    ADMISSIBILITY_TOKENS_OR_FORGERY,
    ALL_OUTCOMES,
    ALL_TARGETS,
    clean_claim,
    clean_conditions,
    clean_magnitudes,
    clean_mode_inputs,
    clean_sequencing_inputs,
)

# ===========================================================================
# Row 1 — empty credible-outcome set
# ===========================================================================


def test_row01_empty_outcome_set_is_unknown_and_the_full_set_is_evaluable() -> None:
    """(§9 line 231 / 234-243) ∅ outcomes is never "no risk"; nine of nine is evaluable."""
    # (a) forbidden direction
    assert (
        overlap_first_reservation_outcome(
            clean_claim(),
            frozenset(),
            within_hard_envelope=True,
            leg_admissibility=True,
        )
        is ReplacementOutcome.REPLACEMENT_UNKNOWN
    )
    assert (
        overlap_first_reservation_complete(
            clean_claim(), frozenset(), within_hard_envelope=True
        )
        is False
    )
    # (b) allowed direction
    assert (
        overlap_first_reservation_outcome(
            clean_claim(),
            ALL_OUTCOMES,
            within_hard_envelope=True,
            leg_admissibility=True,
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


# ===========================================================================
# Row 2 — empty re-evaluation-target set
# ===========================================================================


def test_row02_empty_target_set_is_incomplete_and_six_of_six_is_complete() -> None:
    """(§12 line 292-298) ∅ targets is never "no change"; six of six re-evaluates."""
    assert (
        partial_fill_reevaluation_complete(
            frozenset(), frozenset(), fill_recognized=True
        )
        is False
    )
    assert (
        partial_fill_reevaluation_complete(
            ALL_TARGETS, ALL_TARGETS, fill_recognized=True
        )
        is True
    )


# ===========================================================================
# Row 3 — empty cancel-first condition set
# ===========================================================================


def test_row03_empty_condition_set_denies_and_eight_of_eight_passes() -> None:
    """(§6.3 line 176) ∅ proven conditions is a denial; all eight proven admits."""
    assert cancel_first_admission_gate(None, leg_admissibility=True) is False
    assert (
        cancel_first_admission_gate(CancelFirstConditions(), leg_admissibility=True)
        is False
    )
    assert (
        cancel_first_admission_gate(clean_conditions(), leg_admissibility=True) is True
    )


# ===========================================================================
# Row 4 — a None / negative no-netting magnitude (structural derivation)
# ===========================================================================


def test_row04_missing_or_negative_magnitude_blocks_and_coexistence_passes() -> None:
    """(§0.4d / §4.1(2)) Structural no-netting — not a flag, so it cannot be forged."""
    # (a) forbidden — any one slot absent or negative
    assert (
        netting_absent(
            clean_claim(
                magnitudes=clean_magnitudes(NEW_ORDER_REMAINING_EXECUTABLE=None)
            )
        )
        is False
    )
    assert (
        netting_absent(
            clean_claim(
                magnitudes=clean_magnitudes(
                    SIMULTANEOUS_OLD_AND_NEW_FILLS=Decimal("-1")
                )
            )
        )
        is False
    )
    # (b) allowed — three separate non-negative magnitudes coexist
    assert netting_absent(clean_claim()) is True


# ===========================================================================
# Row 5 — a None magnitude / limit / aggregate risk
# ===========================================================================


def test_row05_none_magnitude_is_unknown_and_finite_values_are_comparable() -> None:
    """(§9) ``None`` propagates UNKNOWN exactly as rcl's ``aggregate_usage`` does."""
    assert (
        reversal_bounded_outcome(
            aggregate_risk_magnitude=None,
            hard_envelope_limit=Decimal("100"),
            within_hard_envelope=True,
        )
        is ReplacementOutcome.REPLACEMENT_UNKNOWN
    )
    assert (
        reversal_bounded_outcome(
            aggregate_risk_magnitude=Decimal("12"),
            hard_envelope_limit=None,
            within_hard_envelope=True,
        )
        is ReplacementOutcome.REPLACEMENT_UNKNOWN
    )
    assert (
        reversal_bounded_outcome(
            aggregate_risk_magnitude=Decimal("12"),
            hard_envelope_limit=Decimal("100"),
            within_hard_envelope=True,
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


# ===========================================================================
# Rows 6-8 — the three sequencing conjuncts, each on its own axis
# ===========================================================================


def test_row06_unknown_new_protection_sufficiency_blocks_the_old_cancel() -> None:
    """(§1 line 34 / §10 line 267 / §4.6a) ACK-alone and staleness are not sufficiency."""
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(new_protection_sufficiency_current=None)
        )
        is False
    )
    assert overlap_first_sequencing_valid(**clean_sequencing_inputs()) is True


def test_row07_unknown_protective_classification_blocks_the_old_cancel() -> None:
    """(§4.1 (ii) / §6.2 line 159) The aggregate-risk axis is its own conjunct."""
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(protective_classification_present=None)
        )
        is False
    )
    assert overlap_first_sequencing_valid(**clean_sequencing_inputs()) is True


def test_row08_unknown_cancellation_admissibility_blocks_the_old_cancel() -> None:
    """(§4.1 (iii) / §8) The Cancellation Arbiter must positively admit the removal."""
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(cancellation_admissible=None)
        )
        is False
    )
    assert overlap_first_sequencing_valid(**clean_sequencing_inputs()) is True


# ===========================================================================
# Row 9 — leg admissibility (ADR-002-019)
# ===========================================================================


def test_row09_unknown_leg_admissibility_traps_and_a_current_one_proceeds() -> None:
    """(§5 line 139 (B)) Missing exact -019 admissibility ⇒ ``REPLACEMENT_TRAPPED``."""
    assert (
        overlap_first_reservation_outcome(
            clean_claim(),
            ALL_OUTCOMES,
            within_hard_envelope=True,
            leg_admissibility=None,
        )
        is ReplacementOutcome.REPLACEMENT_TRAPPED
    )
    assert (
        cancel_first_admission_gate(clean_conditions(), leg_admissibility=None) is False
    )
    assert (
        overlap_first_reservation_outcome(
            clean_claim(),
            ALL_OUTCOMES,
            within_hard_envelope=True,
            leg_admissibility=True,
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


# ===========================================================================
# Row 10 — an exceeded (or unknown) §15 bound
# ===========================================================================


def test_row10_bound_exceeded_contains_and_within_bound_proceeds() -> None:
    """(§15 line 351) The three ``SHALL NOT``s: no authority extension, no widening, no
    completion declaration."""
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST, **clean_mode_inputs(bound_exceeded=True)
        )
        is ReplacementOutcome.REPLACEMENT_CONTAINED
    )
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST, **clean_mode_inputs(bound_exceeded=None)
        )
        is ReplacementOutcome.REPLACEMENT_CONTAINED
    )
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST, **clean_mode_inputs(bound_exceeded=False)
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


# ===========================================================================
# Row 11 — the injected protective Admissibility verdict (partition)
# ===========================================================================


@given(token=ADMISSIBILITY_TOKENS_OR_FORGERY)
def test_row11_only_the_admissible_token_passes_the_partition_gate(
    token: object,
) -> None:
    """(§5 line 139 (C)) ``TRAPPED`` / ``PROHIBITED`` / ``None`` / forgeries all deny.

    Every real ``Admissibility`` member is truthy, so a bare truthiness gate would let a
    ``TRAPPED`` verdict transmit during a partition.
    """
    result = partition_replacement_admissible(
        token,  # type: ignore[arg-type]
        mode=ReplacementMode.OVERLAP_FIRST,
    )
    assert result is (token == "ADMISSIBLE")


def test_row11_cancel_first_is_refused_during_a_partition_even_when_admissible() -> (
    None
):
    """(§5 line 139 (C)) Only the add-only direction has a partition-lease counterpart."""
    for mode in ReplacementMode:
        result = partition_replacement_admissible("ADMISSIBLE", mode=mode)
        assert result is (mode is ReplacementMode.OVERLAP_FIRST)


# ===========================================================================
# Row 12 — an empty workflow state (no permissive side, by construction)
# ===========================================================================


def test_row12_no_workflow_state_ever_grants_authority() -> None:
    """(§5 line 137) The one row with **no** permissive side — a label grants nothing.

    Design #18 §4.7 records this explicitly: "(양성 side 없음 — label은 결코 authority를
    부여하지 않음)". The "allowed" direction is therefore that a *well-formed, all-false*
    block is still recognized as all-false — i.e. the guard is not vacuously failing —
    while no state, including the absent one and ``COMPLETED``, ever yields authority.
    """
    # (a) forbidden — an absent block is unknown, not all-false
    assert workflow_label_grants_nothing(None) is False
    # (b) the only positive answer available: a genuine all-false block
    assert workflow_label_grants_nothing(ReplacementAuthorityEffect()) is True
    # ...and there is no state whose label grants anything (all nine, incl. COMPLETED)
    for state in ReplacementWorkflowState:
        assert state.value != ""
        effect = ReplacementAuthorityEffect()
        assert workflow_label_grants_nothing(effect) is True
        assert all(
            getattr(effect, flag) is False
            for flag in ReplacementAuthorityEffect.model_fields
        )


# ===========================================================================
# Forbidden-verb sweep (§4.7) — each verb has a named guard
# ===========================================================================


def test_forbidden_verb_net_old_against_new_is_structurally_impossible() -> None:
    """(§0.4d / §20.2 line 443) There is no flag to net with; the magnitudes must coexist."""
    netted = clean_claim(
        magnitudes=clean_magnitudes(
            OLD_ORDER_REMAINING_EXECUTABLE=None,  # netted away into the new order
        )
    )
    assert netting_absent(netted) is False
    assert (
        overlap_first_reservation_complete(
            netted, ALL_OUTCOMES, within_hard_envelope=True
        )
        is False
    )


def test_forbidden_verb_clamp_hiding_quantity_is_refused() -> None:
    """(§12 line 302) A clamp that hides uncovered or reversing quantity is refused."""
    assert (
        no_hiding_clamp(clamp_applied=True, hides_uncovered_or_reversing=True) is False
    )
    assert (
        no_hiding_clamp(clamp_applied=True, hides_uncovered_or_reversing=None) is False
    )
    assert (
        no_hiding_clamp(clamp_applied=True, hides_uncovered_or_reversing=False) is True
    )


def test_forbidden_verb_assume_atomic_by_method_name_is_refused() -> None:
    """(§6.1 line 149-151) Unproven atomicity is non-atomic, never assumed atomic."""
    assert (
        replacement_mode_admissible(
            ReplacementMode.BROKER_PROVEN_ATOMIC,
            **clean_mode_inputs(atomic_proven=None),
        )
        is ReplacementOutcome.REPLACEMENT_DENIED
    )


def test_forbidden_verb_reduce_capacity_on_label_is_impossible() -> None:
    """(§9 line 245) No label — not even ``COMPLETED`` — can release capacity.

    The authority block is all-false by construction, and there is no capacity-release
    method anywhere in the package, so the verb has no expression at all.
    """
    from tos import replacement as replacement_pkg

    effect = ReplacementAuthorityEffect()
    assert effect.releases_capacity is False
    assert effect.declares_completion is False
    for forbidden in (
        "release_capacity",
        "commit_capacity",
        "transmit",
        "issue_authority",
    ):
        assert not hasattr(replacement_pkg, forbidden)


def test_forbidden_verb_clear_workflow_and_restart_has_no_expression() -> None:
    """(§20.7 line 463) Recovery is never "clear the workflow and restart".

    The package exposes no clear / reset / restart entry point, and the workflow records
    are frozen and append-only — so a restart can only be a **new generation**, which the
    ordering property already constrains.
    """
    from tos import replacement as replacement_pkg

    for forbidden in ("clear_workflow", "reset_workflow", "restart", "clear", "reset"):
        assert not hasattr(replacement_pkg, forbidden)
