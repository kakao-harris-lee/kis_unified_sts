"""MANDATED test-only seam cross-check: replacement <-> protective (design #18 §3.4(d)).

``tos.replacement`` does **not** import ``tos.protective`` at runtime — the §7.1 allowlist
closure test asserts its absence, and sibling edge 0 is the ratified boundary decision
(design #18 §0.4b). This file imports **both** as a **test** to lock the three injected
protective seams and, above all, their **polarity**:

* ``cancellation_admissible`` (``predicates.py:523``) returns a ``bool``; the replacement
  sequencing conjunct is ``is True``, so an unproven arbiter verdict never licenses the
  cancellation of the old order. The predicate already encodes §11.4 line 506's
  "no optimistic protection credit for a submitted / transmitted / acknowledged
  replacement" — replacement consumes that, it does not re-author it;
* ``partition_lease_admissible`` (``predicates.py:460``) returns the **3-token**
  ``Admissibility`` StrEnum (``vocabulary.py:118/137``). Every member is truthy, so the
  replacement gate admits only ``ADMISSIBLE``; this file drives all three members **plus**
  ``None``;
* ``protective_classification_present`` (``predicates.py:309``) is the **aggregate-risk**
  axis. The v1.1 C2 correction turns on the fact that its proposition ("PROTECTIVE_PROVEN
  via conservative aggregate-risk analysis") is **not** the §10 per-field Protection
  Sufficiency Proof — so it fills its own sequencing conjunct and cannot source the other.

It also locks the ``Admissibility`` / ``ProtectiveActionKind`` token drift: replacement
carries local coordinate constants (it cannot import the enums), so the seam asserts the
constants still equal the real members.

Causal isolation: each polarity assertion fixes a valid baseline and flips **one** input.

A test-only cross-import is **not** a runtime package edge (design #18 §3.4(d)/§7.1).
"""

from __future__ import annotations

from decimal import Decimal

from tos.protective import (
    Admissibility,
    AggregateRiskComparison,
    IntermediateStateWitness,
    ProtectiveActionKind,
    ProtectiveOwnership,
    cancellation_admissible,
    partition_lease_admissible,
    protective_classification_present,
)
from tos.replacement import (
    ADMISSIBILITY_ADMISSIBLE,
    PROTECTIVE_ACTION_KIND_CANCEL_FIRST_OR_REMOVAL,
    PROTECTIVE_ACTION_KIND_OVERLAP_FIRST_ADD_ONLY,
    ReplacementMode,
    ReplacementOutcome,
    halt_precedence_disposition,
    overlap_first_sequencing_valid,
    partition_replacement_admissible,
    protective_action_kind_token,
)

from ._replacement_strategies import clean_sequencing_inputs

# ---------------------------------------------------------------------------
# Token drift locks
# ---------------------------------------------------------------------------


def test_admissibility_token_equals_the_real_protective_member() -> None:
    """(drift lock) replacement's local ``ADMISSIBILITY_ADMISSIBLE`` is the real value."""
    assert Admissibility.ADMISSIBLE.value == ADMISSIBILITY_ADMISSIBLE
    assert {level.value for level in Admissibility} == {
        "ADMISSIBLE",
        "TRAPPED",
        "PROHIBITED",
    }


def test_protective_action_kind_tokens_equal_the_real_members() -> None:
    """(drift lock, §3.4) The mode -> action-kind mapping targets real enum members."""
    assert (
        ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY.value
        == PROTECTIVE_ACTION_KIND_OVERLAP_FIRST_ADD_ONLY
    )
    assert (
        ProtectiveActionKind.CANCEL_FIRST_OR_REMOVAL.value
        == PROTECTIVE_ACTION_KIND_CANCEL_FIRST_OR_REMOVAL
    )
    assert (
        protective_action_kind_token(ReplacementMode.OVERLAP_FIRST)
        == ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY.value
    )
    assert (
        protective_action_kind_token(ReplacementMode.CANCEL_FIRST)
        == ProtectiveActionKind.CANCEL_FIRST_OR_REMOVAL.value
    )


# ---------------------------------------------------------------------------
# cancellation_admissible -> overlap_first_sequencing_valid (bool seam)
# ---------------------------------------------------------------------------


def _arbiter(equivalent_replacement_live: bool | None) -> bool:
    """The protective arbiter verdict for a SAFETY_OWNED order, one input varying."""
    return cancellation_admissible(
        ProtectiveOwnership.SAFETY_OWNED,
        protection_no_longer_required=False,
        within_hard_envelope=True,
        equivalent_replacement_live=equivalent_replacement_live,
        continued_existence_worsens_aggregate=False,
        controller_authorizes_removal=False,
        cancellation_worsens_aggregate=False,
    )


def test_no_optimistic_credit_for_an_unconfirmed_replacement_flows_through() -> None:
    """(§11.4 line 506 seam) A submitted / ACKed replacement gets no protection credit.

    protective returns ``False`` for an unconfirmed replacement; the replacement
    sequencing conjunct then refuses to cancel the old order. This is exactly the
    ownership split design #18 §3.5 fixes: protective decides admissibility, replacement
    consumes it.
    """
    for unconfirmed in (None, False):
        produced = _arbiter(unconfirmed)
        assert produced is False
        assert (
            overlap_first_sequencing_valid(
                **clean_sequencing_inputs(cancellation_admissible=produced)
            )
            is False
        )
    # Causal isolation: only the confirmation changes and both sides flip together.
    confirmed = _arbiter(True)
    assert confirmed is True
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(cancellation_admissible=confirmed)
        )
        is True
    )


def test_a_none_arbiter_verdict_never_licenses_the_old_cancel() -> None:
    """(polarity) The conjunct is ``is True``; ``None`` / ``False`` both block."""
    for verdict in (None, False):
        assert (
            overlap_first_sequencing_valid(
                **clean_sequencing_inputs(cancellation_admissible=verdict)
            )
            is False
        )


# ---------------------------------------------------------------------------
# partition_lease_admissible -> partition_replacement_admissible (3-token StrEnum)
# ---------------------------------------------------------------------------


def test_partition_lease_admissible_returns_the_admissibility_strenum_not_a_bool() -> (
    None
):
    """(seam shape) The protective predicate returns ``Admissibility``, not ``bool | None``."""
    verdict = partition_lease_admissible(
        ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY,
        None,
        within_pre_proven_scope=None,
        staleness_ok=None,
        lease_valid_for_new_transmission=None,
        partition_new_commitment_denied=None,
    )
    assert isinstance(verdict, Admissibility)
    assert not isinstance(verdict, bool)


def test_all_three_admissibility_tokens_plus_none_have_the_right_polarity() -> None:
    """(exhaustive polarity, §4.7 row 11) Only ADMISSIBLE passes the replacement gate."""
    assert (
        partition_replacement_admissible(
            Admissibility.ADMISSIBLE, mode=ReplacementMode.OVERLAP_FIRST
        )
        is True
    )
    for token in (Admissibility.TRAPPED, Admissibility.PROHIBITED, None):
        assert (
            partition_replacement_admissible(token, mode=ReplacementMode.OVERLAP_FIRST)
            is False
        )
    # ...and every non-admissible member is nonetheless *truthy*, which is exactly why a
    # bare truthiness gate would be a fail-open defect.
    assert bool(Admissibility.TRAPPED) is True
    assert bool(Admissibility.PROHIBITED) is True


def test_a_prohibited_verdict_from_the_real_predicate_denies_the_replacement_gate() -> (
    None
):
    """(end-to-end polarity) No valid lease ⇒ PROHIBITED ⇒ the replacement leg is denied."""
    verdict = partition_lease_admissible(
        ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY,
        None,
        within_pre_proven_scope=True,
        staleness_ok=True,
        lease_valid_for_new_transmission=False,  # no valid lease => PROHIBITED
        partition_new_commitment_denied=True,
    )
    assert verdict is Admissibility.PROHIBITED
    assert (
        partition_replacement_admissible(verdict, mode=ReplacementMode.OVERLAP_FIRST)
        is False
    )


def test_a_cancel_first_leg_is_trapped_by_protective_and_refused_by_replacement() -> (
    None
):
    """(§5 line 139 (C)) The removal direction is trapped on both sides of the seam."""
    verdict = partition_lease_admissible(
        ProtectiveActionKind.CANCEL_FIRST_OR_REMOVAL,
        None,
        within_pre_proven_scope=True,
        staleness_ok=True,
        lease_valid_for_new_transmission=True,
        partition_new_commitment_denied=True,
    )
    assert verdict is Admissibility.TRAPPED
    assert (
        partition_replacement_admissible(verdict, mode=ReplacementMode.CANCEL_FIRST)
        is False
    )


# ---------------------------------------------------------------------------
# protective_classification_present — the AGGREGATE-RISK axis (v1.1 C2)
# ---------------------------------------------------------------------------


def _classification(final_risk: Decimal) -> bool:
    """The protective aggregate-risk classification, one magnitude varying."""
    return protective_classification_present(
        AggregateRiskComparison(
            final_conservative_risk=final_risk,
            current_conservative_risk=Decimal("10"),
            no_action_risk=Decimal("10"),
            already_exceeded_regime=False,
        ),
        IntermediateStateWitness(
            worst_intermediate_risk=Decimal("9"),
            credible_space_bounded=True,
            no_credible_intermediate_increases_exceedance=True,
        ),
        envelope_within_hard=True,
    )


def test_the_classification_seam_is_the_aggregate_risk_axis_not_field_sufficiency() -> (
    None
):
    """(v1.1 C2, the category-error regression) Two different propositions, two conjuncts.

    protective's docstring proposition is "``True`` only when ``PROTECTIVE_PROVEN`` via
    conservative aggregate-risk analysis". ADR §10's Protection Sufficiency Proof is a
    **per-field** establishment (identity, quantity, side, price/trigger semantics,
    remaining quantity, venue state, broker capability, relation to current exposure). If
    they were interchangeable, proving the classification alone would license the old
    cancel — this asserts it does not.
    """
    proven = _classification(Decimal("5"))
    assert proven is True
    # The genuinely-proven aggregate-risk classification, with the §10 per-field proof
    # still unestablished, must NOT license the old cancel.
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(
                protective_classification_present=proven,
                new_protection_sufficiency_current=None,
            )
        )
        is False
    )
    # ...and symmetrically, a per-field proof does not substitute for the classification.
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(protective_classification_present=None)
        )
        is False
    )


def test_a_risk_increasing_classification_blocks_the_sequencing() -> None:
    """(seam polarity) protective denies, and the replacement conjunct refuses."""
    denied = _classification(Decimal("50"))  # final above current => RISK_INCREASING
    assert denied is False
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(protective_classification_present=denied)
        )
        is False
    )


# ---------------------------------------------------------------------------
# §8 line 225 HALT blind-cancel — the arbiter owns the prohibition (Gap-7)
# ---------------------------------------------------------------------------


def test_halt_blind_cancel_defers_to_the_protective_arbiter_both_ways() -> None:
    """(§8 line 225 / Gap-7) The blind-cancel prohibition is protective's, consumed here.

    "A protective order already necessary to contain existing exposure SHALL not be
    blindly cancelled." replacement never *emits* such a cancel: with the arbiter
    unproven it reports ``REPLACEMENT_TRAPPED`` (protection retained), and only a real
    arbiter approval plus a HALT-compatible workflow proceeds.
    """
    # (a) guard fires — the arbiter refuses (no confirmed equivalent replacement).
    refused = _arbiter(None)
    assert refused is False
    assert (
        halt_precedence_disposition(
            halt_active=True,
            halt_compatible_protective_or_containment=True,
            protection_necessary_for_existing_exposure=True,
            cancellation_admissible=refused,
        )
        is ReplacementOutcome.REPLACEMENT_TRAPPED
    )
    # (b) passing side — the arbiter positively admits the removal and the workflow is
    #     HALT-compatible, so it MAY proceed (§8 line 225 second sentence).
    admitted = _arbiter(True)
    assert admitted is True
    assert (
        halt_precedence_disposition(
            halt_active=True,
            halt_compatible_protective_or_containment=True,
            protection_necessary_for_existing_exposure=True,
            cancellation_admissible=admitted,
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )
