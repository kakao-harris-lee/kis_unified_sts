"""MANDATED test-only seam cross-check: nontrade <-> are / ADR-002-021 (§3.4(d)/§0.4c).

``tos.nontrade`` does **not** import ``tos.are`` at runtime, and design #21 §0.4c records
why: the are ``ProjectedCell`` REUSE was considered and **rejected**. The Phase-1 nontrade
decision is leg-set completeness, structural no-netting, polarity, and idempotency — none
of which needs a cell type — and are already owns the concurrent non-trade trapped scenario
as a **first-class** ``AdverseScenarioKind`` member, so re-projecting risk here would
duplicate authority and collide coordinates.

The division this file locks (design #21 §0.4d): **nontrade owns leg enumeration and the
structural no-netting; are owns the aggregate-risk projection over the credible state
space.** The verdicts cross the seam as injected magnitudes / bools.

**The M4 proposition re-designation is pinned here.** are's ``envelope_bound_not_enlarged``
proposition is ARE-INV-007 line 178 — "Neither runtime policy, strategy, human approval,
broker result, nor model output may **enlarge** the Hard Safety Envelope or single-action
bound". Its proposition-identical ADR-002-010 clause is **§9 line 196** ("Risk capacity
SHALL cover the maximum aggregate risk across the envelope. Favorable effects SHALL NOT be
netted against uncertain adverse effects") — the *limit-enlargement* axis. The v1.0 contract
hung it on §10 line 221's **release** clause, which is the rcl-owned *release* axis and a
different proposition; the re-designation is asserted below as a comment-anchored fact.

**Honest disclosure (M5 / §10.4 G6).** Whether the nontrade leg set covers the
``ProjectedCell`` set handed to are is **not** verified in Phase 1 and is **not** claimed.
The binding predicate was deliberately not authored: it would need the are coordinate (the
rejected edge-1) or a weak opaque-id proxy that would prove nothing while looking like
proof. This file asserts the *absence* of that claim as explicitly as it asserts the seam.

A test-only cross-import is **not** a runtime package edge (design #21 §3.4(d)/§7.1).
"""

from __future__ import annotations

from decimal import Decimal

from tos.are import (
    AdverseScenarioKind,
    ProjectedCell,
    RiskDimensionKind,
    credible_space_bounded,
    worst_intermediate_risk,
)
from tos.nontrade import (
    ADVERSE_SCENARIO_EXTERNAL_TRAPPED_NONTRADE_CONCURRENT,
    CredibleTransitionLegKind,
    NonTradeDisposition,
    nontrade_disposition,
)

from ._nontrade_strategies import clean_disposition_inputs


def _cell(risk: Decimal | None, bounded: bool | None) -> ProjectedCell:
    """One are projected cell on the concurrent non-trade trapped scenario."""
    return ProjectedCell(
        dimension=RiskDimensionKind.OPTION_GREEKS_EXERCISE_ASSIGNMENT,
        scenario=AdverseScenarioKind.EXTERNAL_TRAPPED_NONTRADE_CONCURRENT,
        worst_intermediate_risk=risk,
        credible_space_bounded=bounded,
    )


# ---------------------------------------------------------------------------
# are already owns the non-trade scenario axis (§0.4c reason ii)
# ---------------------------------------------------------------------------


def test_are_owns_the_concurrent_non_trade_trapped_scenario() -> None:
    """(§0.4c) The decisive ownership evidence for rejecting the ProjectedCell REUSE."""
    assert (
        AdverseScenarioKind.EXTERNAL_TRAPPED_NONTRADE_CONCURRENT.value
        == ADVERSE_SCENARIO_EXTERNAL_TRAPPED_NONTRADE_CONCURRENT
    )
    # the option-lifecycle and settlement dimensions are likewise are's, which is why
    # NT-EV-004 / NT-EV-005 are not-Phase-1 here
    assert RiskDimensionKind.OPTION_GREEKS_EXERCISE_ASSIGNMENT is not None
    assert RiskDimensionKind.SETTLEMENT_CASH_CURRENCY is not None


def test_the_two_axes_are_different_coordinate_systems() -> None:
    """(§2.2-5) A transition leg is not a risk dimension and not a scenario."""
    assert set(CredibleTransitionLegKind).isdisjoint(set(RiskDimensionKind))
    assert set(CredibleTransitionLegKind).isdisjoint(set(AdverseScenarioKind))


# ---------------------------------------------------------------------------
# The injected-verdict seam (§0.4d)
# ---------------------------------------------------------------------------


def test_a_bounded_projection_feeds_an_admissible_disposition() -> None:
    """(availability side) A finite risk over a bounded space is a usable verdict."""
    cells = [_cell(Decimal("12"), True), _cell(Decimal("7"), True)]
    risk = worst_intermediate_risk(cells)
    bounded = credible_space_bounded(cells)
    assert risk == Decimal("12"), "are takes the max — nontrade never sums or maximizes"
    assert bounded is True
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                injected_worst_intermediate_risk=risk,
                injected_credible_space_bounded=bounded,
            )
        )
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


def test_an_unknown_projection_propagates_on_both_sides_of_the_seam() -> None:
    """(seam polarity) are returns ``None``; nontrade blocks. Causal isolation: one cell."""
    cells = [_cell(Decimal("12"), True), _cell(None, True)]
    risk = worst_intermediate_risk(cells)
    assert risk is None, "a None component propagates UNKNOWN, never assume-zero"
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(injected_worst_intermediate_risk=risk)
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )
    # ...and with the magnitude restored both sides are decidable again
    restored = worst_intermediate_risk([_cell(Decimal("12"), True)])
    assert restored == Decimal("12")
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(injected_worst_intermediate_risk=restored)
        )
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


def test_an_unbounded_credible_space_blocks() -> None:
    """(§19 line 470 / §4.7 row 11) Unbounded is trapped exposure, not permission."""
    for bounded_flag in (None, False):
        cells = [_cell(Decimal("12"), True), _cell(Decimal("7"), bounded_flag)]
        bounded = credible_space_bounded(cells)
        assert bounded is not True
        assert (
            nontrade_disposition(
                **clean_disposition_inputs(injected_credible_space_bounded=bounded)
            )
            is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
        )


def test_an_empty_cell_set_is_unknown_on_the_are_side_too() -> None:
    """(∅ discipline) Both packages read "no cells" / "no legs" as unknown, not as zero."""
    assert worst_intermediate_risk([]) is None
    assert credible_space_bounded([]) is None
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(
                injected_worst_intermediate_risk=worst_intermediate_risk([]),
                injected_credible_space_bounded=credible_space_bounded([]),
            )
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


# ---------------------------------------------------------------------------
# Ownership boundaries + the M5 non-claim
# ---------------------------------------------------------------------------


def test_nontrade_projects_no_risk_and_exposes_no_cell_type() -> None:
    """(§0.2/§0.4c) The rejected REUSE leaves no trace on the nontrade surface."""
    from tos import nontrade as nontrade_pkg

    for forbidden in (
        "ProjectedCell",
        "CapacityVector",
        "RiskDimensionKind",
        "AdverseScenarioKind",
        "worst_intermediate_risk",
        "credible_space_bounded",
        "envelope_bound_not_enlarged",
        "no_credible_intermediate_increases_exceedance",
    ):
        assert not hasattr(nontrade_pkg, forbidden), (
            f"{forbidden} is are-owned — §0.4c rejected the REUSE and §0.2 forbids "
            "re-projecting aggregate risk here"
        )


def test_the_leg_to_cell_coverage_binding_is_deliberately_not_claimed() -> None:
    """(M5 / §10.4 G6 honest disclosure) The unimplemented binding is **not** faked.

    A caller can complete all ten legs and still hand are a partial cell set; neither side
    detects that, because each is fail-closed only within its own set. Phase 1 claims
    "nontrade enforces completeness **within its own leg set**" and nothing more. Any
    predicate purporting to bind the two would either resurrect the rejected are coordinate
    edge or rest on an opaque-id proxy — proof-shaped, but not proof.
    """
    from tos import nontrade as nontrade_pkg

    for never_authored in (
        "envelope_legs_covered",
        "legs_cover_projected_cells",
        "envelope_matches_projection",
    ):
        assert not hasattr(nontrade_pkg, never_authored), (
            f"{never_authored} exists — design #21 M5 deliberately did NOT author it; "
            "adding it silently would convert an honest gap into a false assurance"
        )
    # the two sets are genuinely independent today: ten legs, and an are projection that
    # knows nothing about them
    assert len(CredibleTransitionLegKind) == 10
    single_cell_projection = worst_intermediate_risk([_cell(Decimal("1"), True)])
    assert single_cell_projection == Decimal("1"), (
        "one cell yields a verdict regardless of how many legs nontrade enumerated — "
        "which is exactly the unbound seam G6 exposes"
    )
