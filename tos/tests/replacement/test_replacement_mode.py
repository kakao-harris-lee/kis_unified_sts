"""§5.3 mode admissibility + §4.5 direction polarity + §8 HALT precedence (design #18 §7).

Three defect classes are hunted here:

1. **direction inversion (#16 C1)** — ``OVERLAP_FIRST`` is *new -> old* (no gap, overlap
   risk) and ``CANCEL_FIRST`` is *old -> new* (gap risk, no overlap). They are opposite
   rules over the same ADR, so a mode must never be satisfied by the *other* mode's
   premise. The §4.5 truth table is asserted directly.
2. **fall-through promotion (#16 CRITICAL)** — ``REPLACEMENT_ADMISSIBLE`` must never be
   the residual branch. Forged modes (raw member strings, ``None``, ``1``, ``[1]``) are
   driven through the dispatch.
3. **∅-void leg composition (v1.1 M1)** — an empty ``leg_admissibilities`` set is *not*
   "all legs admissible": ``all(())`` is vacuously ``True``, which is exactly the shape
   design #18 §4.7 forbids.

Plus the §15 line 351 bound-exceed containment canary (three ``SHALL NOT``s) and the §8
line 225 HALT blind-cancel canary (Gap-7), both ways.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.replacement import (
    ReplacementMode,
    ReplacementOutcome,
    halt_precedence_disposition,
    replacement_mode_admissible,
)

from ._replacement_strategies import (
    LEG_ADMISSIBILITY_SETS,
    MODE_OR_FORGERY,
    NON_FALSE_VALUES,
    TRIBOOL,
    TRUTHY_NON_BOOL,
    clean_mode_inputs,
)

# ===========================================================================
# §4.5 direction polarity — each mode has its OWN premise
# ===========================================================================


@given(mode=st.sampled_from(list(ReplacementMode)))
def test_each_mode_requires_only_its_own_direction_specific_premise(
    mode: ReplacementMode,
) -> None:
    """(§4.5 truth table) Satisfying the *other* mode's premise never admits this one."""
    # Every premise unproven except the one belonging to ``mode``.
    per_mode_premise = {
        ReplacementMode.BROKER_PROVEN_ATOMIC: "atomic_proven",
        ReplacementMode.OVERLAP_FIRST: "overlap_reservation_complete",
        ReplacementMode.CANCEL_FIRST: "cancel_first_gate_passed",
    }
    unproven = clean_mode_inputs(
        atomic_proven=None,
        overlap_reservation_complete=None,
        overlap_sequencing_valid=None,
        cancel_first_gate_passed=None,
    )
    outcome = replacement_mode_admissible(mode, **unproven)
    if mode is ReplacementMode.NO_SAFE_MODE:
        assert outcome is ReplacementOutcome.REPLACEMENT_CONTAINED
    else:
        assert outcome is ReplacementOutcome.REPLACEMENT_DENIED

    if mode in per_mode_premise:
        # Prove *only* this mode's premise(s) and nothing else.
        overrides: dict[str, object] = {
            "atomic_proven": None,
            "overlap_reservation_complete": None,
            "overlap_sequencing_valid": None,
            "cancel_first_gate_passed": None,
        }
        overrides[per_mode_premise[mode]] = True
        if mode is ReplacementMode.OVERLAP_FIRST:
            overrides["overlap_sequencing_valid"] = True
        inputs = clean_mode_inputs(**overrides)
        assert (
            replacement_mode_admissible(mode, **inputs)
            is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
        )


def test_overlap_first_needs_both_completeness_and_sequencing() -> None:
    """(§6.2, direction check) Completeness alone does not license cancelling the old order."""
    only_complete = clean_mode_inputs(overlap_sequencing_valid=None)
    only_sequenced = clean_mode_inputs(overlap_reservation_complete=None)
    assert (
        replacement_mode_admissible(ReplacementMode.OVERLAP_FIRST, **only_complete)
        is ReplacementOutcome.REPLACEMENT_DENIED
    )
    assert (
        replacement_mode_admissible(ReplacementMode.OVERLAP_FIRST, **only_sequenced)
        is ReplacementOutcome.REPLACEMENT_DENIED
    )
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST, **clean_mode_inputs()
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


def test_cancel_first_is_not_satisfied_by_overlap_first_evidence() -> None:
    """(#16 C1 direction inversion) The *old -> new* mode needs the §6.3 gate, nothing else."""
    overlap_only = clean_mode_inputs(cancel_first_gate_passed=None)
    assert (
        replacement_mode_admissible(ReplacementMode.CANCEL_FIRST, **overlap_only)
        is ReplacementOutcome.REPLACEMENT_DENIED
    )


def test_atomic_mode_is_not_satisfied_by_a_method_name_style_assumption() -> None:
    """(§6.1 line 149) Only executed-evidence proof admits ``BROKER_PROVEN_ATOMIC``."""
    for unproven in (False, None):
        assert (
            replacement_mode_admissible(
                ReplacementMode.BROKER_PROVEN_ATOMIC,
                **clean_mode_inputs(atomic_proven=unproven),
            )
            is ReplacementOutcome.REPLACEMENT_DENIED
        )


def test_no_safe_mode_always_contains() -> None:
    """(§6.4 line 180) All three unsafe ⇒ retain the safest protection and contain."""
    assert (
        replacement_mode_admissible(ReplacementMode.NO_SAFE_MODE, **clean_mode_inputs())
        is ReplacementOutcome.REPLACEMENT_CONTAINED
    )


# ===========================================================================
# Fall-through / forgery (the #16 CRITICAL lesson)
# ===========================================================================


@given(mode=MODE_OR_FORGERY)
def test_admissible_is_never_reached_by_a_forged_mode(mode: object) -> None:
    """(#16 CRITICAL) Only a real member can be admissible; a forgery is UNKNOWN.

    A ``StrEnum`` compares equal to its own value, so a gate written with ``==`` would let
    the raw string ``"OVERLAP_FIRST"`` through. The dispatch is identity-based and its
    residual branch is the restrictive ``REPLACEMENT_UNKNOWN``.
    """
    outcome = replacement_mode_admissible(
        mode,  # type: ignore[arg-type]
        **clean_mode_inputs(),
    )
    if isinstance(mode, ReplacementMode):
        assert outcome in {
            ReplacementOutcome.REPLACEMENT_ADMISSIBLE,
            ReplacementOutcome.REPLACEMENT_CONTAINED,
        }
    else:
        assert outcome is ReplacementOutcome.REPLACEMENT_UNKNOWN


@given(forged=st.sampled_from(TRUTHY_NON_BOOL))
def test_a_truthy_non_bool_premise_never_admits_a_mode(forged: object) -> None:
    """(polarity) Every per-mode premise is ``is True``-gated, not truthiness-gated."""
    for mode, premise in (
        (ReplacementMode.BROKER_PROVEN_ATOMIC, "atomic_proven"),
        (ReplacementMode.OVERLAP_FIRST, "overlap_reservation_complete"),
        (ReplacementMode.OVERLAP_FIRST, "overlap_sequencing_valid"),
        (ReplacementMode.CANCEL_FIRST, "cancel_first_gate_passed"),
    ):
        outcome = replacement_mode_admissible(
            mode, **clean_mode_inputs(**{premise: forged})
        )
        assert outcome is not ReplacementOutcome.REPLACEMENT_ADMISSIBLE


# ===========================================================================
# Leg-admissibility composition point (v1.1 M1) — ∅ must NOT be vacuously true
# ===========================================================================


@given(legs=LEG_ADMISSIBILITY_SETS)
def test_leg_composition_traps_on_empty_or_any_non_true_member(
    legs: frozenset[bool | None],
) -> None:
    """(§5.3 M1 / §4.7 row 9) Non-empty **and** every member ``is True``, or TRAPPED."""
    outcome = replacement_mode_admissible(
        ReplacementMode.OVERLAP_FIRST,
        **clean_mode_inputs(leg_admissibilities=legs),
    )
    all_admissible = len(legs) > 0 and all(leg is True for leg in legs)
    if all_admissible:
        assert outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    else:
        assert outcome is ReplacementOutcome.REPLACEMENT_TRAPPED


def test_empty_leg_set_is_trapped_not_vacuously_admissible() -> None:
    """(∅-void, named canary: proceed-leg-without-current-admissibility).

    ``all(())`` is vacuously ``True`` in Python — the exact fail-open shape §4.7 forbids.
    No leg proven admissible is not "every leg admissible".
    """
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST,
            **clean_mode_inputs(leg_admissibilities=frozenset()),
        )
        is ReplacementOutcome.REPLACEMENT_TRAPPED
    )
    # (b) passing side: one genuinely admissible leg proceeds.
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST,
            **clean_mode_inputs(leg_admissibilities=frozenset({True})),
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


def test_one_inadmissible_leg_traps_the_whole_mode() -> None:
    """(§5 line 139 (B)) A single non-admissible leg traps the replacement."""
    for bad in (False, None):
        assert (
            replacement_mode_admissible(
                ReplacementMode.OVERLAP_FIRST,
                **clean_mode_inputs(leg_admissibilities=frozenset({True, bad})),
            )
            is ReplacementOutcome.REPLACEMENT_TRAPPED
        )


# ===========================================================================
# §15 line 351 bound-exceed containment (v1.1 M5) — negative polarity
# ===========================================================================


@given(bound_exceeded=TRIBOOL, mode=st.sampled_from(list(ReplacementMode)))
def test_bound_exceeded_forces_containment_before_anything_else(
    bound_exceeded: bool | None, mode: ReplacementMode
) -> None:
    """(§15 line 351, three ``SHALL NOT``s) Only a proven ``False`` proceeds.

    An exceeded **or unknown** bound must not extend authority, widen capacity, or let the
    replacement be declared complete — so containment precedes the mode dispatch.
    """
    outcome = replacement_mode_admissible(
        mode, **clean_mode_inputs(bound_exceeded=bound_exceeded)
    )
    if bound_exceeded is not False:
        assert outcome is ReplacementOutcome.REPLACEMENT_CONTAINED


@given(non_false=st.sampled_from(NON_FALSE_VALUES))
def test_bound_exceed_gate_is_is_false_not_is_not_true(non_false: object) -> None:
    """(C1 polarity) ``bound_exceeded`` is negative polarity — ``None`` must contain."""
    outcome = replacement_mode_admissible(
        ReplacementMode.OVERLAP_FIRST,
        **clean_mode_inputs(bound_exceeded=non_false),
    )
    assert outcome is ReplacementOutcome.REPLACEMENT_CONTAINED


def test_bound_exceed_canary_both_ways() -> None:
    """(named canary: extend-authority / widen-capacity / declare-complete on bound-exceed)."""
    # (a) guard fires
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST, **clean_mode_inputs(bound_exceeded=True)
        )
        is ReplacementOutcome.REPLACEMENT_CONTAINED
    )
    # (b) within bound ⇒ the ordinary decision is not blocked
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST, **clean_mode_inputs(bound_exceeded=False)
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


# ===========================================================================
# §8 line 225 HALT precedence + blind-cancel canary (v1.1 Gap-7)
# ===========================================================================


@given(
    halt=TRIBOOL,
    compatible=TRIBOOL,
    necessary=TRIBOOL,
    arbiter=TRIBOOL,
)
def test_halt_disposition_never_emits_a_blind_cancel(
    halt: bool | None,
    compatible: bool | None,
    necessary: bool | None,
    arbiter: bool | None,
) -> None:
    """(§8 line 225) Under HALT, a necessary protection is never blindly cancelled.

    "A protective order already necessary to contain existing exposure SHALL not be
    blindly cancelled." Whenever HALT is active (or unknown) and the protection may still
    be necessary while the Cancellation Arbiter has not positively admitted removal, the
    disposition must be ``REPLACEMENT_TRAPPED`` — the protection is retained, not cancelled.
    """
    outcome = halt_precedence_disposition(
        halt_active=halt,
        halt_compatible_protective_or_containment=compatible,
        protection_necessary_for_existing_exposure=necessary,
        cancellation_admissible=arbiter,
    )
    if halt is False:
        assert outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    elif necessary is not False and arbiter is not True:
        assert outcome is ReplacementOutcome.REPLACEMENT_TRAPPED
    elif compatible is True:
        assert outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    else:
        assert outcome is ReplacementOutcome.REPLACEMENT_CONTAINED


def test_halt_blind_cancel_canary_both_ways() -> None:
    """(named canary: HALT-blind-cancel, Gap-7) Guard fires, and the lawful path passes."""
    # (a) HALT + a protection still necessary + no arbiter approval ⇒ retained, not cancelled
    assert (
        halt_precedence_disposition(
            halt_active=True,
            halt_compatible_protective_or_containment=True,
            protection_necessary_for_existing_exposure=True,
            cancellation_admissible=None,
        )
        is ReplacementOutcome.REPLACEMENT_TRAPPED
    )
    # (b) HALT + a positively HALT-compatible containment workflow whose removal the
    #     arbiter has admitted ⇒ it MAY proceed (§8 line 225 second sentence)
    assert (
        halt_precedence_disposition(
            halt_active=True,
            halt_compatible_protective_or_containment=True,
            protection_necessary_for_existing_exposure=False,
            cancellation_admissible=True,
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )
    # ...and an ordinary (non-HALT-compatible) replacement initiation is blocked.
    assert (
        halt_precedence_disposition(
            halt_active=True,
            halt_compatible_protective_or_containment=False,
            protection_necessary_for_existing_exposure=False,
            cancellation_admissible=True,
        )
        is ReplacementOutcome.REPLACEMENT_CONTAINED
    )


def test_unknown_halt_state_is_not_cleared() -> None:
    """(polarity) Only a positively ``False`` HALT state clears the precedence check."""
    assert (
        halt_precedence_disposition(
            halt_active=None,
            halt_compatible_protective_or_containment=False,
            protection_necessary_for_existing_exposure=False,
            cancellation_admissible=True,
        )
        is ReplacementOutcome.REPLACEMENT_CONTAINED
    )


# ===========================================================================
# HALT composition order (design #18 §5.3 G5/G7 — the documented caller contract)
# ===========================================================================


def _composed(halt_active: bool | None, **mode_overrides: object) -> ReplacementOutcome:
    """The documented composition: HALT precedence **first**, mode gate **second**.

    ``replacement_mode_admissible``'s signature is frozen by design #18 §5.3 (G5) and
    carries no HALT input, so §8 line 225 precedence is applied by the caller *before* it,
    and the **more restrictive** of the two governs. This helper is the executable
    statement of that contract.
    """
    halt_outcome = halt_precedence_disposition(
        halt_active=halt_active,
        halt_compatible_protective_or_containment=False,
        protection_necessary_for_existing_exposure=False,
        cancellation_admissible=True,
    )
    if halt_outcome is not ReplacementOutcome.REPLACEMENT_ADMISSIBLE:
        return halt_outcome
    return replacement_mode_admissible(
        ReplacementMode.OVERLAP_FIRST,
        **clean_mode_inputs(**mode_overrides),  # type: ignore[arg-type]
    )


def test_the_halt_step_is_strictly_more_restrictive_than_the_mode_gate_alone() -> None:
    """(§5.3 G7 / §8 line 225) With HALT active the composed path diverges from the gate.

    This is the load-bearing regression for the G5-vs-G7 tension: the mode gate cannot see
    HALT, so if a caller skipped the HALT step an ordinary replacement would be admitted
    during a HALT. Driven with premises that make the **mode gate alone** return
    ``REPLACEMENT_ADMISSIBLE``, the composed path must still refuse.
    """
    gate_alone = replacement_mode_admissible(
        ReplacementMode.OVERLAP_FIRST, **clean_mode_inputs()
    )
    assert gate_alone is ReplacementOutcome.REPLACEMENT_ADMISSIBLE

    composed = _composed(halt_active=True)
    assert composed is ReplacementOutcome.REPLACEMENT_CONTAINED
    assert composed is not gate_alone, (
        "the composed path collapsed onto the mode gate — an ordinary replacement would "
        "be initiated during a HALT (§8 line 225 'HALT dominates ordinary replacement "
        "initiation')"
    )


def test_an_unknown_halt_state_also_diverges_from_the_mode_gate() -> None:
    """(polarity) Only a positively ``False`` HALT state lets the mode gate decide."""
    assert _composed(halt_active=None) is ReplacementOutcome.REPLACEMENT_CONTAINED


def test_without_halt_the_composition_defers_to_the_mode_gate_verdict() -> None:
    """(both ways) HALT inactive ⇒ the composition is transparent — no vacuous block.

    Both the admitting and the refusing mode verdicts must pass through unchanged, so the
    HALT step cannot mask a mode-level defect in either direction.
    """
    assert _composed(halt_active=False) is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    assert (
        _composed(halt_active=False, overlap_sequencing_valid=None)
        is ReplacementOutcome.REPLACEMENT_DENIED
    )
    assert (
        _composed(halt_active=False, leg_admissibilities=frozenset())
        is ReplacementOutcome.REPLACEMENT_TRAPPED
    )
    assert (
        _composed(halt_active=False, bound_exceeded=True)
        is ReplacementOutcome.REPLACEMENT_CONTAINED
    )


def test_containment_precedes_the_leg_trap_when_both_would_apply() -> None:
    """(§15 line 351 gate order) An exceeded bound demands containment, not a trap.

    ``REPLACEMENT_TRAPPED`` says "covered, untransmittable, no further action"; the three
    §15 line 351 ``SHALL NOT``s demand an **active** containment response instead. With
    both conditions present the heavier one must win, so the bound check is ordered ahead
    of the leg-composition check. Swapping the two would surface exactly here.
    """
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST,
            **clean_mode_inputs(bound_exceeded=True, leg_admissibilities=frozenset()),
        )
        is ReplacementOutcome.REPLACEMENT_CONTAINED
    )
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST,
            **clean_mode_inputs(
                bound_exceeded=True, leg_admissibilities=frozenset({None})
            ),
        )
        is ReplacementOutcome.REPLACEMENT_CONTAINED
    )
    # Causal isolation: with the bound proven within, the leg trap is what remains.
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST,
            **clean_mode_inputs(bound_exceeded=False, leg_admissibilities=frozenset()),
        )
        is ReplacementOutcome.REPLACEMENT_TRAPPED
    )
