"""§6 predicate-only substrate — cancel-first gate + authorization currentness.

PR-EV-002 (ADR §6.3) and PR-EV-008 (ADR §7) **substrate only**. Both rows carry a minimum
register level of ``EV-L2/3``, so **neither is closed here**: what Phase 1 authors is the
L1-decidable decision rule, and the component-fault / integration evidence remains open
(design #18 §1/§6).

The two paths hunt opposite fail-open shapes:

* the cancel-first gate must never admit **vacuously** — an absent or all-unknown
  condition set proves ∅, and §6.3 line 176 says an unknown condition **denies**;
* the authorization path must never let an expiry **release an economic effect** — §7 line
  203 "Authorization expiry blocks further transmission. It does not expire the economic
  effect of an already transmitted old or new order."
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.replacement import (
    CANCEL_FIRST_ADMISSION_CONDITIONS,
    CancelFirstConditions,
    ReplacementOutcome,
    cancel_first_admission_gate,
    cancel_first_admission_outcome,
    expiry_releases_no_economic_effect,
    replacement_authorization_current,
)

from ._replacement_strategies import (
    NON_FALSE_VALUES,
    TRIBOOL,
    TRUTHY_NON_BOOL,
    clean_conditions,
)

# ===========================================================================
# §6.1 cancel-first admission gate (ADR §6.3 line 166-176; PR-EV-002)
# ===========================================================================


def test_all_eight_conditions_plus_an_admissible_leg_pass() -> None:
    """(passing side, PR-AC-002) The genuinely clean 8-of-8 case is admitted."""
    assert (
        cancel_first_admission_gate(clean_conditions(), leg_admissibility=True) is True
    )
    assert (
        cancel_first_admission_outcome(clean_conditions(), leg_admissibility=True)
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


@given(
    condition=st.sampled_from(list(CANCEL_FIRST_ADMISSION_CONDITIONS)),
    broken=st.sampled_from([False, None]),
)
def test_any_single_unknown_or_false_condition_denies(
    condition: str, broken: bool | None
) -> None:
    """(§6.3 line 176) "If any condition is unknown, cancel-first replacement is denied."

    Causal isolation: the baseline is fully proven and exactly one condition is flipped,
    so the denial can only be attributed to that condition. All eight are exercised.
    """
    conditions = clean_conditions(**{condition: broken})
    assert cancel_first_admission_gate(conditions, leg_admissibility=True) is False
    assert (
        cancel_first_admission_outcome(conditions, leg_admissibility=True)
        is ReplacementOutcome.REPLACEMENT_DENIED
    )


def test_an_all_unknown_condition_set_is_the_empty_proven_set_and_denies() -> None:
    """(§4.7 row 3) ∅ proven ≠ the 8-name universe — no vacuous admission."""
    empty = CancelFirstConditions()
    assert empty.positively_proven() == frozenset()
    assert cancel_first_admission_gate(empty, leg_admissibility=True) is False
    assert (
        cancel_first_admission_outcome(empty, leg_admissibility=True)
        is ReplacementOutcome.REPLACEMENT_DENIED
    )


def test_an_absent_condition_set_denies() -> None:
    """(§4.7 row 3) No condition object at all is the ∅ case, not a pass."""
    assert cancel_first_admission_gate(None, leg_admissibility=True) is False
    assert (
        cancel_first_admission_outcome(None, leg_admissibility=True)
        is ReplacementOutcome.REPLACEMENT_DENIED
    )


@given(
    condition=st.sampled_from(list(CANCEL_FIRST_ADMISSION_CONDITIONS)),
    forged=st.sampled_from(TRUTHY_NON_BOOL),
)
def test_a_truthy_non_bool_condition_is_not_proof(
    condition: str, forged: object
) -> None:
    """(polarity) ``positively_proven`` counts only the singleton ``True``.

    ``model_construct`` bypasses pydantic validation — which a forged payload or a caller
    bug can — so the predicate layer must hold on its own: the proven-set derivation is
    ``is True``, never truthiness. Otherwise an ACK payload, a ``1``, or a non-empty list
    dropped into any one of the eight slots would license a Protection Gap.
    """
    forged_conditions = CancelFirstConditions.model_construct(
        **(dict.fromkeys(CANCEL_FIRST_ADMISSION_CONDITIONS, True) | {condition: forged})
    )
    assert condition not in forged_conditions.positively_proven()
    assert (
        cancel_first_admission_gate(forged_conditions, leg_admissibility=True) is False
    )
    # Causal isolation: the same construct with a genuine ``True`` in that slot passes.
    assert (
        cancel_first_admission_gate(
            CancelFirstConditions.model_construct(
                **dict.fromkeys(CANCEL_FIRST_ADMISSION_CONDITIONS, True)
            ),
            leg_admissibility=True,
        )
        is True
    )


@given(leg=st.sampled_from([False, None]))
def test_the_ninth_conjunct_leg_admissibility_traps(leg: bool | None) -> None:
    """(v1.1 M1-② / §5 line 139 (B)) A cancellation-involving leg needs current -019.

    "a cancellation-involving replacement leg outside that scope ... SHALL NOT proceed" —
    even with all eight conditions proven.
    """
    assert (
        cancel_first_admission_gate(clean_conditions(), leg_admissibility=leg) is False
    )
    assert (
        cancel_first_admission_outcome(clean_conditions(), leg_admissibility=leg)
        is ReplacementOutcome.REPLACEMENT_TRAPPED
    )


def test_trapped_precedes_denied_when_both_would_apply() -> None:
    """(ordering) An inadmissible leg cannot proceed regardless of the other conditions."""
    assert (
        cancel_first_admission_outcome(None, leg_admissibility=None)
        is ReplacementOutcome.REPLACEMENT_TRAPPED
    )


@given(proven=st.frozensets(st.sampled_from(list(CANCEL_FIRST_ADMISSION_CONDITIONS))))
def test_gate_holds_iff_the_proven_set_equals_the_full_eight_name_universe(
    proven: frozenset[str],
) -> None:
    """(§6.3, set-level) Any proper subset denies; only the full universe admits."""
    conditions = CancelFirstConditions(**dict.fromkeys(proven, True))
    result = cancel_first_admission_gate(conditions, leg_admissibility=True)
    assert result is (proven == frozenset(CANCEL_FIRST_ADMISSION_CONDITIONS))


# ===========================================================================
# §6.2 replacement-authorization currentness / expiry (ADR §7; PR-EV-008)
# ===========================================================================


@given(material=TRIBOOL, expired=TRIBOOL, persists=TRIBOOL)
def test_authorization_currentness_truth_table(
    material: bool | None, expired: bool | None, persists: bool | None
) -> None:
    """(§7 line 201-203 / Q2) Two negative-polarity conjuncts + one positive.

    ``material_change`` and ``expired`` are negative polarity (``is False`` only, so an
    unknown materiality is *material* and an unknown expiry is *expired*);
    ``economic_effect_persists`` is positive polarity (``is True`` only, design #18 Q2).
    """
    result = replacement_authorization_current(
        material_change=material,
        expired=expired,
        economic_effect_persists=persists,
    )
    assert result is (material is False and expired is False and persists is True)


@given(non_false=st.sampled_from(NON_FALSE_VALUES))
def test_unknown_materiality_invalidates_the_authorization(non_false: object) -> None:
    """(C1 polarity) ``is not True`` would clear ``None`` here — ``is False`` does not."""
    assert (
        replacement_authorization_current(
            material_change=non_false,  # type: ignore[arg-type]
            expired=False,
            economic_effect_persists=True,
        )
        is False
    )


def test_material_change_canary_both_ways() -> None:
    """(named canary: §7 line 201 "Any material change invalidates the authorization")."""
    assert (
        replacement_authorization_current(
            material_change=True, expired=False, economic_effect_persists=True
        )
        is False
    )
    assert (
        replacement_authorization_current(
            material_change=False, expired=False, economic_effect_persists=True
        )
        is True
    )


@given(expired=TRIBOOL, persists=TRIBOOL, claimed=TRIBOOL)
def test_expiry_never_releases_an_economic_effect(
    expired: bool | None, persists: bool | None, claimed: bool | None
) -> None:
    """(§7 line 203 / §9 line 245) A release rests on FQP, never on expiry."""
    result = expiry_releases_no_economic_effect(
        expired=expired,
        economic_effect_persists=persists,
        economic_effect_release_claimed=claimed,
    )
    assert result is (claimed is False or persists is False)


def test_expire_economic_effect_canary_both_ways() -> None:
    """(named canary: expire-economic-effect-on-authorization-expiry)."""
    # (a) guard fires — expiry is claimed as the basis for a release while the effect
    #     still persists.
    assert (
        expiry_releases_no_economic_effect(
            expired=True,
            economic_effect_persists=True,
            economic_effect_release_claimed=True,
        )
        is False
    )
    # (a) guard fires — an *unknown* persistence is conservatively "still persists".
    assert (
        expiry_releases_no_economic_effect(
            expired=True,
            economic_effect_persists=None,
            economic_effect_release_claimed=True,
        )
        is False
    )
    # (b) passing side 1 — no release is being claimed at all.
    assert (
        expiry_releases_no_economic_effect(
            expired=True,
            economic_effect_persists=True,
            economic_effect_release_claimed=False,
        )
        is True
    )
    # (b) passing side 2 — the effect is positively proven gone (a Final Quantity Proof
    #     is present), which is the only legitimate basis for a release.
    assert (
        expiry_releases_no_economic_effect(
            expired=True,
            economic_effect_persists=False,
            economic_effect_release_claimed=True,
        )
        is True
    )


@given(expired=TRIBOOL)
def test_no_value_of_expired_can_legitimize_a_release(expired: bool | None) -> None:
    """(contract lock, §7 line 203) ``expired`` is a coordinate, never a justification."""
    assert (
        expiry_releases_no_economic_effect(
            expired=expired,
            economic_effect_persists=True,
            economic_effect_release_claimed=True,
        )
        is False
    )
