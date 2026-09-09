"""tos.backtest.calibration — the paper/backtest deviation observation + expectancy claim gate.

Phase 3 wave 3 §3.1 작업 6 (design #33 slice E): the survey line the plan opens with is explicit —
``DeterministicFillModel``/``FillParameters.price_band_fraction`` (the synthetic reject band) exist,
but "paper 관측 대비 calibration·deviation budget·expectancy 금지 게이트 부재" (calibration against a
paper observation, a deviation budget, and an expectancy-*prohibition* gate are absent). This module
is that gate — and only that gate.

**This module computes no expectancy.** No expectancy/edge/PnL computation exists anywhere in the
kernel today (design #33 §1.2 B1 — the whole ``tos.backtest`` package is sealed against exactly that
surface, see :mod:`tos.backtest._base`), and this module does not invent one. :func:`claim_expectancy`
takes an already-computed ``observed_value`` from the **caller** (the runtime calibration report,
which pairs a paper ``EGRESS_RESULT_RECORDED`` observation against a backtest fill) and decides
whether that value may be *repeated* — never whether it is correct, and never how it was derived.
The gate's product is a permission bit plus, when withheld, the named reason; it is a CLAIM GATE, not
a metric computation.

**Absence is not zero.** :class:`FillDeviation` models one paper-vs-backtest fill-deviation
observation along three independent dimensions (price, fill ratio, latency). A dimension is ``None``
when it is **not observable on the surface that produced it** — the paper synthetic transport in
:mod:`tos.backtest.fills` reports quantity only, and ``EgressResultPayload``
(:class:`~tos.engine.EgressResultPayload`) carries no price field at all
(``tos/src/tos/engine/records.py`` — quantity/reference only) — never "the deviation measured as
zero". Treating an unobserved dimension as zero deviation would silently manufacture a calibration
pass; :func:`calibration_within_budget` refuses that by treating any bounded-but-unobserved dimension
as insufficient (fail-closed), not as passing.

**Verdict precedence** (:func:`calibration_within_budget`): ``INSUFFICIENT_OBSERVATIONS`` beats
``EXCEEDED`` beats ``WITHIN``. Zero observations is insufficient *unconditionally* — even when
``budget.min_observations == 0`` — because an empty observation set proves nothing about a budget
that was never measured against; "zero observations required" is a budget-authoring statement about
tolerance, not a licence to claim compliance with no evidence at all. An observation carrying a
``None`` value on a dimension the budget bounds is likewise insufficient: the budget states a bound
on that dimension, so a claim that the (unmeasured) dimension is "within" it would be unsupported.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No clock, no RNG, no network.
"""

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
    """A calibration verdict — verdict-shaped, so it inherits the truthy-sentinel seal.

    Every member is a non-empty string, so ``if verdict:`` would read ``EXCEEDED`` as truthy — a
    silent fail-open exactly like the one :class:`~tos.backtest.vocabulary.SettlementStatus` seals
    against (``vocabulary.py:48-67``). Consumers must use the explicit positive-identity gate
    (``verdict is CalibrationVerdict.WITHIN``); everything else is denial.
    """

    WITHIN = "WITHIN"
    EXCEEDED = "EXCEEDED"
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"


class FillDeviation(FrozenModel):
    """One paper-vs-backtest fill-deviation observation, along three independent dimensions.

    A ``None`` dimension means **not observable on this surface** — never "zero deviation". The
    paper synthetic transport reports quantity only (no price), and
    :class:`~tos.engine.EgressResultPayload` carries no price field at all, so a price-deviation
    observation paired against a paper fill that never priced anything has nothing to report; the
    honest value is absence, not a fabricated zero (module docstring).

    The three dimensions, all optional independently — an observation may be able to compare
    quantities but not prices, or vice versa, depending on which surfaces produced the two sides
    being paired:

    * ``price_bps``: the absolute price deviation in basis points, when both sides carried a price.
    * ``fill_ratio``: the fill-ratio shortfall (paper's realized fraction below the backtest's, or
      vice versa), when both sides carried a fill magnitude.
    * ``latency_bars``: the settlement-bar-count deviation between the two sides, when both carried a
      settlement coordinate.
    """

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
    """The injected tolerance a set of :class:`FillDeviation` observations is measured against.

    Every bound is required, with no default — this is a runtime-injected policy value (design #33
    §10 "hardcoded numbers: 0"), never a value this module supplies on the caller's behalf.

    ``min_observations`` is a **sample-size floor**, independent of whether any individual
    observation is within its own per-dimension bound: a budget may set it to ``0`` to state "no
    minimum sample size is required", but that is a statement about tolerance, not a licence for
    :func:`calibration_within_budget` to treat zero observations as evidence of anything (see that
    function's docstring for the precedence this implies).
    """

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
    """Decide whether a set of observations is within, exceeds, or cannot yet judge, a budget.

    Precedence (module docstring): ``INSUFFICIENT_OBSERVATIONS`` beats ``EXCEEDED`` beats ``WITHIN``.

    1. Zero observations ⇒ ``INSUFFICIENT_OBSERVATIONS``, unconditionally — even when
       ``budget.min_observations == 0``. An empty set was never measured against the budget at all,
       so there is nothing for "within" to describe; "no minimum sample size" is a tolerance
       statement, not evidence.
    2. Fewer observations than ``budget.min_observations`` ⇒ ``INSUFFICIENT_OBSERVATIONS``.
    3. Any observation carrying ``None`` on a dimension this budget bounds (every dimension here is
       always bounded, since every :class:`DeviationBudget` field is required) ⇒
       ``INSUFFICIENT_OBSERVATIONS`` — an unobservable dimension cannot be claimed within budget.
    4. Any observation exceeding any bound ⇒ ``EXCEEDED``.
    5. Otherwise ⇒ ``WITHIN``.

    Args:
        observed: The fill-deviation observations, in any order.
        budget: The injected tolerance.

    Returns:
        The calibration verdict.
    """
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
    """Whether a calibration verdict permits repeating an externally-computed value.

    Only ``WITHIN`` does. ``EXCEEDED`` and ``INSUFFICIENT_OBSERVATIONS`` both withhold — the gate
    does not distinguish "known to be off" from "not yet known" when deciding whether to permit the
    claim, only when naming the reason (:func:`claim_expectancy`).

    Args:
        verdict: The calibration verdict.

    Returns:
        ``True`` only for :attr:`CalibrationVerdict.WITHIN`.
    """
    return verdict is CalibrationVerdict.WITHIN


class ExpectancyClaim(FrozenModel):
    """A gated pass-through of an externally-computed value — never a computation of its own.

    Exactly one of ``value`` / ``withheld_reason`` is non-``None`` (validated below). This is a
    **claim gate**, not a metric: the value this type may carry is supplied by the caller
    (:func:`claim_expectancy`'s ``observed_value`` parameter) and this module never computes one
    itself — no expectancy/edge/PnL computation exists anywhere in the kernel today (module
    docstring).
    """

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
    """Gate an externally-computed value behind a calibration verdict.

    This function computes nothing about ``observed_value`` — it is opaque here, supplied by the
    caller (module docstring). It only decides, from ``verdict`` alone, whether that value may be
    repeated.

    Args:
        observed_value: The already-computed value the caller wishes to claim. Ignored entirely
            unless ``verdict`` is :attr:`CalibrationVerdict.WITHIN`.
        verdict: The calibration verdict gating the claim.

    Returns:
        An :class:`ExpectancyClaim` carrying ``observed_value`` when permitted, or ``None`` plus a
        reason naming the verdict when withheld.
    """
    if expectancy_claim_permitted(verdict):
        return ExpectancyClaim(value=observed_value, withheld_reason=None)
    return ExpectancyClaim(
        value=None,
        withheld_reason=f"withheld: calibration verdict is {verdict.value}",
    )
