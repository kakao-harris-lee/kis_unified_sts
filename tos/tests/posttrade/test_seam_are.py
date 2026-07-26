"""Seam: ``tos.posttrade`` <-> ``tos.are`` — the three-way netting split.

**Proposition identity (design #24 §3.5 verdict 3).** "Netting" names three different
propositions on three different axes and confusing them is a fail-open:

1. **nontrade** transition-envelope no-netting — old and new instrument exposures both
   counted during an event;
2. **posttrade** obligation-leg no-netting — a receivable and a payable stay **gross** unless
   an enforceable-netting proof is positively injected (PTF-INV-007);
3. **are** ``BenefitKind.NETTING`` — a netting **benefit** on the aggregate-risk axis, which
   are already owns and which itself requires proof.

are also already owns settlement / cash / currency as a first-class risk dimension and the
margin / collateral / borrow / FX / settle / assign scenario, which is precisely why this
package projects **no** risk: it owns obligation-set enumeration completeness and the
structural no-favourable-default, and are owns the projection over it (§0.4c/§0.4d).

Locks **4** of the 19 injected tokens: ``SETTLEMENT_CASH_CURRENCY``,
``MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN``, ``MISSING_ACK_RECEIPT_AMBIGUITY``,
``BenefitKind.NETTING``. Test-only sibling imports are not runtime package edges.
"""

from __future__ import annotations

from decimal import Decimal

import tos.posttrade.predicates as posttrade_predicates
from tos.posttrade import (
    ADVERSE_SCENARIO_MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN,
    ADVERSE_SCENARIO_MISSING_ACK_RECEIPT_AMBIGUITY,
    BENEFIT_KIND_NETTING,
    RISK_DIMENSION_SETTLEMENT_CASH_CURRENCY,
    ObligationLegDirection,
    netting_requires_positive_proof,
)

from ._posttrade_strategies import clean_leg


def test_risk_dimension_token_drift_lock() -> None:
    """(token 4 of 19) are ``RiskDimensionKind.SETTLEMENT_CASH_CURRENCY``."""
    from tos.are import RiskDimensionKind

    assert (
        RiskDimensionKind.SETTLEMENT_CASH_CURRENCY.value
        == RISK_DIMENSION_SETTLEMENT_CASH_CURRENCY
    )


def test_adverse_scenario_token_drift_locks() -> None:
    """(tokens 5-6 of 19) The two are ``AdverseScenarioKind`` members this package coordinates on."""
    from tos.are import AdverseScenarioKind

    assert (
        AdverseScenarioKind.MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN.value
        == ADVERSE_SCENARIO_MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN
    )
    assert (
        AdverseScenarioKind.MISSING_ACK_RECEIPT_AMBIGUITY.value
        == ADVERSE_SCENARIO_MISSING_ACK_RECEIPT_AMBIGUITY
    )


def test_benefit_kind_netting_token_drift_lock() -> None:
    """(token 7 of 19) are ``BenefitKind.NETTING`` — the aggregate-risk netting benefit."""
    from tos.are import BenefitKind

    assert BenefitKind.NETTING.value == BENEFIT_KIND_NETTING


def test_the_three_netting_propositions_are_distinct() -> None:
    """(§3.5 verdict 3) Three axes, three types, one word.

    are's is a **benefit** on the aggregate-risk axis; ours is the **absence** of an offset on
    the obligation axis; nontrade's is the coexistence of pre- and post-event exposures on the
    transition axis. None of the three implies another.
    """
    from tos.are import BenefitKind
    from tos.nontrade import favorable_netting_absent

    assert BenefitKind.NETTING.value == "NETTING"
    # ours is a predicate over two gross legs, not an enum member at all
    assert callable(netting_requires_positive_proof)
    # nontrade's is a third, separate predicate over a transition envelope
    assert callable(favorable_netting_absent)
    assert netting_requires_positive_proof is not favorable_netting_absent


def test_our_no_netting_is_structural_gross_coexistence() -> None:
    """(§0.4d) Two gross magnitudes standing side by side **are** the proof of no netting.

    An offset can only be expressed by erasing or reducing one of them, so the absence of an
    offset needs no flag — and a caller cannot forge it, because there is no flag to set.
    """
    receivable = clean_leg(ObligationLegDirection.CREDIT, Decimal("5.00"))
    payable = clean_leg(ObligationLegDirection.DEBIT, Decimal("3.00"))
    # both gross, one scope, proof present -> netting valid
    assert netting_requires_positive_proof(receivable, payable, True, True) is True
    # erase one magnitude (what an offset would do) -> not a netting, both stay gross
    erased = clean_leg(ObligationLegDirection.CREDIT, None)
    assert netting_requires_positive_proof(erased, payable, True, True) is False


def test_this_package_projects_no_aggregate_risk() -> None:
    """(§0.4c/§0.4d) are owns ``worst_intermediate_risk``; this package owns no projection.

    Structural absence: there is no risk-projection, scenario, or envelope-bound predicate
    here to disagree with are's.
    """
    for forbidden in (
        "worst_intermediate_risk",
        "credible_space_bounded",
        "envelope_bound_not_enlarged",
        "project_risk",
        "aggregate_risk",
    ):
        assert not hasattr(posttrade_predicates, forbidden)


def test_are_owns_the_post_trade_risk_coordinates_this_package_only_names() -> None:
    """(§0.4d) The coordinates exist on are's axis — this package injects, never re-derives."""
    from tos.are import AdverseScenarioKind, RiskDimensionKind

    assert hasattr(RiskDimensionKind, "SETTLEMENT_CASH_CURRENCY")
    assert hasattr(RiskDimensionKind, "LEVERAGE_MARGIN_COLLATERAL")
    assert hasattr(RiskDimensionKind, "OPTION_GREEKS_EXERCISE_ASSIGNMENT")
    assert hasattr(AdverseScenarioKind, "MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN")
    assert hasattr(AdverseScenarioKind, "MISSING_ACK_RECEIPT_AMBIGUITY")
