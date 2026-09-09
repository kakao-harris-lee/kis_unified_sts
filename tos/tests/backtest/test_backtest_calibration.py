"""Phase 3 wave 3 §3.1 작업 6 — the calibration deviation-budget + expectancy claim gate.

Three verdict branches (WITHIN / EXCEEDED / INSUFFICIENT_OBSERVATIONS), the two fail-closed
INSUFFICIENT triggers (zero observations even with ``min_observations == 0``; an unobservable
``None`` dimension), the precedence between them, and the expectancy claim gate that hides the value
whenever the verdict is not WITHIN.

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError
from tos.backtest._base import BacktestIntegrityError
from tos.backtest.calibration import (
    CalibrationVerdict,
    DeviationBudget,
    ExpectancyClaim,
    FillDeviation,
    calibration_within_budget,
    claim_expectancy,
    expectancy_claim_permitted,
)

#: The house convention (``_backtest_fixtures.INTEGRITY_ERRORS``) — a ``model_validator`` raise
#: surfaces through pydantic as ``ValidationError``, not the bare ``BacktestIntegrityError``.
_INTEGRITY_ERRORS = (BacktestIntegrityError, ValidationError)


def _budget(min_observations: int = 1) -> DeviationBudget:
    return DeviationBudget(
        max_price_bps=Decimal(10),
        max_fill_ratio_shortfall=Decimal("0.05"),
        max_latency_bars=2,
        min_observations=min_observations,
    )


def _clean_observation() -> FillDeviation:
    return FillDeviation(
        price_bps=Decimal(1), fill_ratio=Decimal("0.01"), latency_bars=0
    )


# ---------------------------------------------------------------------------
# the three verdict branches
# ---------------------------------------------------------------------------


def test_within_budget_when_every_observation_is_inside_every_bound() -> None:
    verdict = calibration_within_budget((_clean_observation(),), _budget())
    assert verdict is CalibrationVerdict.WITHIN


def test_exceeded_when_price_deviation_breaches_its_bound() -> None:
    observation = FillDeviation(
        price_bps=Decimal(999), fill_ratio=Decimal(0), latency_bars=0
    )
    verdict = calibration_within_budget((observation,), _budget())
    assert verdict is CalibrationVerdict.EXCEEDED


def test_exceeded_when_fill_ratio_shortfall_breaches_its_bound() -> None:
    observation = FillDeviation(
        price_bps=Decimal(0), fill_ratio=Decimal("0.99"), latency_bars=0
    )
    verdict = calibration_within_budget((observation,), _budget())
    assert verdict is CalibrationVerdict.EXCEEDED


def test_exceeded_when_latency_breaches_its_bound() -> None:
    observation = FillDeviation(
        price_bps=Decimal(0), fill_ratio=Decimal(0), latency_bars=99
    )
    verdict = calibration_within_budget((observation,), _budget())
    assert verdict is CalibrationVerdict.EXCEEDED


def test_insufficient_when_fewer_observations_than_the_minimum() -> None:
    verdict = calibration_within_budget(
        (_clean_observation(),), _budget(min_observations=5)
    )
    assert verdict is CalibrationVerdict.INSUFFICIENT_OBSERVATIONS


# ---------------------------------------------------------------------------
# the two fail-closed INSUFFICIENT triggers
# ---------------------------------------------------------------------------


def test_zero_observations_is_insufficient_even_with_zero_minimum() -> None:
    """An empty observation set proves nothing about a budget never measured against — fail-closed."""
    verdict = calibration_within_budget((), _budget(min_observations=0))
    assert verdict is CalibrationVerdict.INSUFFICIENT_OBSERVATIONS


def test_unobservable_dimension_is_insufficient_not_within() -> None:
    """A None dimension must never be silently treated as zero deviation (module docstring)."""
    observation = FillDeviation(price_bps=None, fill_ratio=Decimal(0), latency_bars=0)
    verdict = calibration_within_budget((observation,), _budget(min_observations=0))
    assert verdict is CalibrationVerdict.INSUFFICIENT_OBSERVATIONS


@pytest.mark.parametrize(
    "kwargs",
    [
        {"price_bps": None, "fill_ratio": Decimal(0), "latency_bars": 0},
        {"price_bps": Decimal(0), "fill_ratio": None, "latency_bars": 0},
        {"price_bps": Decimal(0), "fill_ratio": Decimal(0), "latency_bars": None},
    ],
)
def test_any_unobservable_dimension_alone_is_sufficient_to_withhold(
    kwargs: dict,
) -> None:
    observation = FillDeviation(**kwargs)
    verdict = calibration_within_budget((observation,), _budget(min_observations=0))
    assert verdict is CalibrationVerdict.INSUFFICIENT_OBSERVATIONS


# ---------------------------------------------------------------------------
# precedence: INSUFFICIENT beats EXCEEDED beats WITHIN
# ---------------------------------------------------------------------------


def test_insufficient_precedence_beats_an_exceedance_elsewhere_in_the_set() -> None:
    """A too-small sample beats an exceedance found in the (too few) observations it did get."""
    breaching = FillDeviation(
        price_bps=Decimal(999), fill_ratio=Decimal(0), latency_bars=0
    )
    verdict = calibration_within_budget((breaching,), _budget(min_observations=5))
    assert verdict is CalibrationVerdict.INSUFFICIENT_OBSERVATIONS


def test_insufficient_precedence_beats_a_none_dimension_plus_exceedance() -> None:
    """One clean-but-unobservable observation among an exceeding one still yields INSUFFICIENT."""
    breaching = FillDeviation(
        price_bps=Decimal(999), fill_ratio=Decimal(0), latency_bars=0
    )
    unobservable = FillDeviation(price_bps=None, fill_ratio=Decimal(0), latency_bars=0)
    verdict = calibration_within_budget(
        (breaching, unobservable), _budget(min_observations=0)
    )
    assert verdict is CalibrationVerdict.INSUFFICIENT_OBSERVATIONS


def test_exceeded_precedence_beats_within_when_mixed() -> None:
    clean = _clean_observation()
    breaching = FillDeviation(
        price_bps=Decimal(999), fill_ratio=Decimal(0), latency_bars=0
    )
    verdict = calibration_within_budget((clean, breaching), _budget())
    assert verdict is CalibrationVerdict.EXCEEDED


# ---------------------------------------------------------------------------
# the truthy-sentinel seal
# ---------------------------------------------------------------------------


def test_exceeded_verdict_refuses_truthiness_testing() -> None:
    """EXCEEDED is a non-empty string; `if verdict:` must not silently read it as pass."""
    with pytest.raises(TypeError):
        bool(CalibrationVerdict.EXCEEDED)


# ---------------------------------------------------------------------------
# the expectancy claim gate
# ---------------------------------------------------------------------------


def test_expectancy_claim_permitted_only_for_within() -> None:
    assert expectancy_claim_permitted(CalibrationVerdict.WITHIN) is True
    assert expectancy_claim_permitted(CalibrationVerdict.EXCEEDED) is False
    assert (
        expectancy_claim_permitted(CalibrationVerdict.INSUFFICIENT_OBSERVATIONS)
        is False
    )


def test_claim_expectancy_carries_the_value_when_within() -> None:
    claim = claim_expectancy(Decimal("1.5"), CalibrationVerdict.WITHIN)
    assert claim.value == Decimal("1.5")
    assert claim.withheld_reason is None


def test_claim_expectancy_hides_the_value_when_exceeded() -> None:
    claim = claim_expectancy(Decimal("1.5"), CalibrationVerdict.EXCEEDED)
    assert claim.value is None
    assert claim.withheld_reason is not None
    assert "EXCEEDED" in claim.withheld_reason


def test_claim_expectancy_hides_the_value_when_insufficient() -> None:
    claim = claim_expectancy(
        Decimal("1.5"), CalibrationVerdict.INSUFFICIENT_OBSERVATIONS
    )
    assert claim.value is None
    assert claim.withheld_reason is not None
    assert "INSUFFICIENT_OBSERVATIONS" in claim.withheld_reason


def test_expectancy_claim_rejects_both_value_and_reason_present() -> None:
    with pytest.raises(_INTEGRITY_ERRORS):
        ExpectancyClaim(value=Decimal(1), withheld_reason="both present")


def test_expectancy_claim_rejects_neither_value_nor_reason_present() -> None:
    with pytest.raises(_INTEGRITY_ERRORS):
        ExpectancyClaim(value=None, withheld_reason=None)


def test_expectancy_claim_rejects_blank_withheld_reason_as_absent() -> None:
    """A blank/whitespace reason is not a reason — it collapses to "neither present"."""
    with pytest.raises(_INTEGRITY_ERRORS):
        ExpectancyClaim(value=None, withheld_reason="   ")


# ---------------------------------------------------------------------------
# construction-time guards on the two input types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"price_bps": Decimal(-1), "fill_ratio": Decimal(0), "latency_bars": 0},
        {"price_bps": Decimal(0), "fill_ratio": Decimal(-1), "latency_bars": 0},
        {"price_bps": Decimal(0), "fill_ratio": Decimal(0), "latency_bars": -1},
    ],
)
def test_fill_deviation_rejects_negative_magnitudes(kwargs: dict) -> None:
    with pytest.raises(_INTEGRITY_ERRORS):
        FillDeviation(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "max_price_bps": Decimal(-1),
            "max_fill_ratio_shortfall": Decimal(0),
            "max_latency_bars": 0,
            "min_observations": 0,
        },
        {
            "max_price_bps": Decimal(0),
            "max_fill_ratio_shortfall": Decimal(-1),
            "max_latency_bars": 0,
            "min_observations": 0,
        },
        {
            "max_price_bps": Decimal(0),
            "max_fill_ratio_shortfall": Decimal(0),
            "max_latency_bars": -1,
            "min_observations": 0,
        },
        {
            "max_price_bps": Decimal(0),
            "max_fill_ratio_shortfall": Decimal(0),
            "max_latency_bars": 0,
            "min_observations": -1,
        },
    ],
)
def test_deviation_budget_rejects_negative_bounds(kwargs: dict) -> None:
    with pytest.raises(_INTEGRITY_ERRORS):
        DeviationBudget(**kwargs)


# ---------------------------------------------------------------------------
# the seal — these new types carry no performance-surface field of their own
# ---------------------------------------------------------------------------


def test_none_of_the_new_types_carry_a_performance_surface_field() -> None:
    from tos.backtest._base import performance_surface_offenders

    for model in (FillDeviation, DeviationBudget, ExpectancyClaim):
        offenders = performance_surface_offenders(model.model_fields)
        assert offenders == (), f"{model.__name__} carries {offenders}"


# ---------------------------------------------------------------------------
# the claim gate is external — pinned, not incidental (team-lead decision, Phase 3 wave 3 §3.1)
# ---------------------------------------------------------------------------


def test_calibration_names_are_not_reexported_from_the_package_namespace() -> None:
    """The submodule is imported by path (``tos.backtest.calibration``), never through the package.

    A future re-export is a deliberate act that must update
    ``test_backtest_result_surface.py``'s ``_SEALED_MODELS`` / ``_RUN_RESULTS`` drift canaries in
    the same change — this pin catches a silent widening that forgot to.
    """
    import tos.backtest as package

    exported_names = set(package.__all__)
    package_vars = vars(package)
    for name in (
        "CalibrationVerdict",
        "DeviationBudget",
        "ExpectancyClaim",
        "FillDeviation",
        "calibration_within_budget",
        "claim_expectancy",
        "expectancy_claim_permitted",
    ):
        assert name not in exported_names, (
            f"tos.backtest.__all__ carries {name!r} — the calibration claim gate is external by "
            "decision (module docstring); re-exporting it requires updating the sealed-model "
            "drift canaries in test_backtest_result_surface.py in the same change"
        )
        assert name not in package_vars, (
            f"tos.backtest exposes {name!r} in its namespace even though __all__ does not list it "
            "— the anti-phantom convention in this suite sweeps vars(), not just __all__"
        )


def test_run_results_carry_no_expectancy_or_calibration_field() -> None:
    """(§1.2 B1, reaffirmed) The sealed run types gained no field from this module's addition.

    Belt-and-suspenders alongside the existing ``seal_performance_surface`` construction-time
    check: this module's own suite independently pins that ``BacktestRun`` /
    ``MultiSymbolBacktestRun`` carry no ``expectancy`` field (the literal name the plan originally
    asked for) and no ``calibration`` field either (a plausible alternate name this module's
    docstring explicitly rejects as an evasion of the seal, not a satisfaction of it).
    """
    import dataclasses

    from tos.backtest.results import BacktestRun, MultiSymbolBacktestRun

    for run_type in (BacktestRun, MultiSymbolBacktestRun):
        names = {field.name for field in dataclasses.fields(run_type)}
        for forbidden_token in ("expectancy", "calibration"):
            assert not any(forbidden_token in name for name in names), (
                f"{run_type.__name__} declares a field containing {forbidden_token!r}: {names} — "
                "the calibration claim gate must stay external (module docstring)"
            )


# ---------------------------------------------------------------------------
# mutation-matrix documentation (run manually, see test file docstring / PR report):
#
# Mutation 1 — change "0 observations => INSUFFICIENT" to "0 observations => WITHIN":
#   caught by test_zero_observations_is_insufficient_even_with_zero_minimum
#
# Mutation 2 — change "None dimension => INSUFFICIENT" to "skip the None dimension and judge the
# rest":
#   caught by test_unobservable_dimension_is_insufficient_not_within and
#   test_any_unobservable_dimension_alone_is_sufficient_to_withhold
# ---------------------------------------------------------------------------
