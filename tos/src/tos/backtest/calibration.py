"""tos.backtest.calibration — the paper/backtest deviation observation + expectancy claim gate."""

from __future__ import annotations

from pydantic import model_validator

from tos.backtest._base import (
    BacktestIntegrityError,
    CanonicalDecimal,
    FrozenModel,
    seal_performance_surface,
)
from tos.backtest.vocabulary import _NonTruthyStrEnum

__all__ = [
    "CalibrationVerdict",
    "DeviationBudget",
    "ExpectancyClaim",
    "FillDeviation",
    "calibration_within_budget",
    "claim_expectancy",
    "expectancy_claim_permitted",
]


class CalibrationVerdict(_NonTruthyStrEnum):
    """A calibration verdict — verdict-shaped, so it inherits the truthy-sentinel seal."""

    WITHIN = "WITHIN"
    EXCEEDED = "EXCEEDED"
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"


class FillDeviation(FrozenModel):
    """One paper-vs-backtest fill-deviation observation, along three independent dimensions."""

    price_bps: CanonicalDecimal | None = None
    fill_ratio: CanonicalDecimal | None = None
    latency_bars: int | None = None

    @model_validator(mode="after")
    def _fill_deviation_is_well_formed(self) -> FillDeviation:
        """Seal the performance surface and require every present dimension to be non-negative."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        if self.price_bps is not None and self.price_bps < 0:
            raise BacktestIntegrityError(
                f"FillDeviation.price_bps must be non-negative (got {self.price_bps}) — it is a "
                "deviation magnitude, not a signed price move"
            )
        if self.fill_ratio is not None and self.fill_ratio < 0:
            raise BacktestIntegrityError(
                f"FillDeviation.fill_ratio must be non-negative (got {self.fill_ratio}) — it is a "
                "shortfall magnitude, not a signed ratio"
            )
        if self.latency_bars is not None and self.latency_bars < 0:
            raise BacktestIntegrityError(
                f"FillDeviation.latency_bars must be non-negative (got {self.latency_bars}) — a "
                "settlement cannot deviate by a negative bar count"
            )
        return self


class DeviationBudget(FrozenModel):
    """The injected tolerance a set of :class:`FillDeviation` observations is measured against."""

    max_price_bps: CanonicalDecimal
    max_fill_ratio_shortfall: CanonicalDecimal
    max_latency_bars: int
    min_observations: int

    @model_validator(mode="after")
    def _deviation_budget_is_well_formed(self) -> DeviationBudget:
        """Seal the performance surface and require every bound to be non-negative."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        if self.max_price_bps < 0:
            raise BacktestIntegrityError(
                f"DeviationBudget.max_price_bps must be non-negative (got {self.max_price_bps})"
            )
        if self.max_fill_ratio_shortfall < 0:
            raise BacktestIntegrityError(
                "DeviationBudget.max_fill_ratio_shortfall must be non-negative "
                f"(got {self.max_fill_ratio_shortfall})"
            )
        if self.max_latency_bars < 0:
            raise BacktestIntegrityError(
                f"DeviationBudget.max_latency_bars must be non-negative (got {self.max_latency_bars})"
            )
        if self.min_observations < 0:
            raise BacktestIntegrityError(
                f"DeviationBudget.min_observations must be non-negative (got {self.min_observations})"
            )
        return self


def calibration_within_budget(
    observed: tuple[FillDeviation, ...], budget: DeviationBudget
) -> CalibrationVerdict:
    """Decide whether a set of observations is within, exceeds, or cannot yet judge, a budget."""
    if not observed:
        return CalibrationVerdict.INSUFFICIENT_OBSERVATIONS
    if len(observed) < budget.min_observations:
        return CalibrationVerdict.INSUFFICIENT_OBSERVATIONS
    for deviation in observed:
        if (
            deviation.price_bps is None
            or deviation.fill_ratio is None
            or deviation.latency_bars is None
        ):
            return CalibrationVerdict.INSUFFICIENT_OBSERVATIONS
    for deviation in observed:
        assert deviation.price_bps is not None
        assert deviation.fill_ratio is not None
        assert deviation.latency_bars is not None
        if deviation.price_bps > budget.max_price_bps:
            return CalibrationVerdict.EXCEEDED
        if deviation.fill_ratio > budget.max_fill_ratio_shortfall:
            return CalibrationVerdict.EXCEEDED
        if deviation.latency_bars > budget.max_latency_bars:
            return CalibrationVerdict.EXCEEDED
    return CalibrationVerdict.WITHIN


def expectancy_claim_permitted(verdict: CalibrationVerdict) -> bool:
    """Whether a calibration verdict permits repeating an externally-computed value."""
    return verdict is CalibrationVerdict.WITHIN


class ExpectancyClaim(FrozenModel):
    """A gated pass-through of an externally-computed value — never a computation of its own."""

    value: CanonicalDecimal | None = None
    withheld_reason: str | None = None

    @model_validator(mode="after")
    def _expectancy_claim_is_well_formed(self) -> ExpectancyClaim:
        """Seal the performance surface and require exactly one of value/withheld_reason."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        has_value = self.value is not None
        has_reason = (
            self.withheld_reason is not None and self.withheld_reason.strip() != ""
        )
        if has_value == has_reason:
            raise BacktestIntegrityError(
                "ExpectancyClaim must carry exactly one of value/withheld_reason — a claim that is "
                "both permitted and withheld (or neither) is not a decision"
            )
        return self


def claim_expectancy(
    observed_value: CanonicalDecimal, verdict: CalibrationVerdict
) -> ExpectancyClaim:
    """Gate an externally-computed value behind a calibration verdict."""
    if expectancy_claim_permitted(verdict):
        return ExpectancyClaim(value=observed_value, withheld_reason=None)
    return ExpectancyClaim(
        value=None,
        withheld_reason=f"withheld: calibration verdict is {verdict.value}",
    )
