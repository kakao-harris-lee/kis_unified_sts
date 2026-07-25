"""No-unproven-benefit + numerical safety / determinism (design #13 §4.2/§4.3/§6.1/§6.2).

Both-ways canaries + the ∅-void hunt (an empty benefit proof proves nothing). ARE-EV-005/006/007
substrate — closes no ARE-EV.
"""

from __future__ import annotations

from decimal import Decimal

from tos.are import (
    BenefitProof,
    RiskDecisionResult,
    ValuationInputs,
    benefit_admissible,
    numerical_determinism,
    numerical_safety,
    valuation_conservative,
)

from ._are_strategies import conservative_valuation, full_benefit_proof

# ---------------------------------------------------------------------------
# benefit_admissible — both-ways + ∅ + "broker-margin-only is not proof"
# ---------------------------------------------------------------------------


def test_full_proof_is_admissible() -> None:
    """(canary +) All seven §13 premises positively True => admissible."""
    assert benefit_admissible(full_benefit_proof()) is True


def test_one_missing_premise_removes_benefit() -> None:
    """(canary - ARE-INV-005) A single unproven premise => not admissible (benefit removed)."""
    assert (
        benefit_admissible(full_benefit_proof(no_undeclared_common_mode=False)) is False
    )


def test_empty_benefit_proof_is_zero() -> None:
    """(∅-seal §4.2) A bare BenefitProof (all premises defaulting False) proves nothing => False."""
    assert benefit_admissible(BenefitProof()) is False


def test_broker_margin_number_is_not_proof() -> None:
    """(§13 line 344) A proof carrying only a scalar reference (no premise) is not admissible."""
    assert benefit_admissible(BenefitProof(proof_reference="broker-margin-42")) is False


# ---------------------------------------------------------------------------
# numerical_safety — both-ways (NaN / infinity / unit mismatch => UNKNOWN)
# ---------------------------------------------------------------------------


def test_finite_consistent_magnitudes_are_safe() -> None:
    """(canary +) Finite magnitudes + consistent units => True."""
    assert (
        numerical_safety([Decimal("1"), Decimal("2.50")], units_consistent=True) is True
    )


def test_empty_magnitudes_is_unknown_not_vacuous() -> None:
    """(∅-seal §4.7 / MAJOR-1) An empty magnitude sequence is not vacuously safe => UNKNOWN.

    Symmetric with the module's other empty-input reductions (all fail closed); the guard
    fires on ``[]`` even when the units flag is positively ``True``.
    """
    assert numerical_safety([], units_consistent=True) is RiskDecisionResult.UNKNOWN


def test_empty_magnitudes_positive_side_still_reachable() -> None:
    """(both-ways) A single finite magnitude (non-empty) with consistent units => True."""
    assert numerical_safety([Decimal("0")], units_consistent=True) is True


def test_nan_magnitude_is_unknown() -> None:
    """(canary - §4.3 / §26 ARE-AC-007) A NaN magnitude => UNKNOWN, never a smaller vector."""
    assert (
        numerical_safety([Decimal("NaN")], units_consistent=True)
        is RiskDecisionResult.UNKNOWN
    )


def test_infinity_magnitude_is_unknown() -> None:
    """(canary - §4.3) An infinite magnitude => UNKNOWN."""
    assert (
        numerical_safety([Decimal("Infinity")], units_consistent=True)
        is RiskDecisionResult.UNKNOWN
    )


def test_none_magnitude_is_unknown() -> None:
    """(fail-closed) A None magnitude => UNKNOWN."""
    assert numerical_safety([None], units_consistent=True) is RiskDecisionResult.UNKNOWN


def test_unit_mismatch_is_unknown() -> None:
    """(§4.3) Inconsistent units => UNKNOWN even for finite magnitudes."""
    assert (
        numerical_safety([Decimal("1")], units_consistent=False)
        is RiskDecisionResult.UNKNOWN
    )
    assert (
        numerical_safety([Decimal("1")], units_consistent=None)
        is RiskDecisionResult.UNKNOWN
    )


def test_scale_normalized_equal_still_safe() -> None:
    """(§4.3) 1.0 and 1.00 are numerically equal — both finite, safe."""
    assert (
        numerical_safety([Decimal("1.0"), Decimal("1.00")], units_consistent=True)
        is True
    )


# ---------------------------------------------------------------------------
# valuation_conservative — both-ways
# ---------------------------------------------------------------------------


def test_valuation_all_true_is_conservative() -> None:
    """(canary +) Every valuation flag positively True => conservative."""
    assert valuation_conservative(conservative_valuation()) is True


def test_valuation_missing_flag_fails_closed() -> None:
    """(canary - §14 line 352) A None / False valuation flag => not conservative."""
    assert (
        valuation_conservative(conservative_valuation(stale_or_unknown_flagged=None))
        is False
    )
    assert (
        valuation_conservative(
            conservative_valuation(broker_figure_treated_as_ceiling_only=False)
        )
        is False
    )


def test_empty_valuation_inputs_fails_closed() -> None:
    """(∅-seal) A bare ValuationInputs (all None) is not conservative."""
    assert valuation_conservative(ValuationInputs()) is False


# ---------------------------------------------------------------------------
# numerical_determinism — both-ways
# ---------------------------------------------------------------------------


def test_determinism_all_true() -> None:
    """(canary +) Every determinism witness True => deterministic."""
    assert (
        numerical_determinism(
            canonical_representation=True,
            deterministic_ordering=True,
            parser_library_model_agreement=True,
            convergence_established=True,
        )
        is True
    )


def test_determinism_parser_disagreement_fails_closed() -> None:
    """(canary - §14 line 360) A parser / library / model disagreement => False."""
    assert (
        numerical_determinism(
            canonical_representation=True,
            deterministic_ordering=True,
            parser_library_model_agreement=False,
            convergence_established=True,
        )
        is False
    )


def test_determinism_none_fails_closed() -> None:
    """(fail-closed) A None witness => False."""
    assert (
        numerical_determinism(
            canonical_representation=None,
            deterministic_ordering=True,
            parser_library_model_agreement=True,
            convergence_established=True,
        )
        is False
    )
