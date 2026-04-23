"""RiskFilterLayer — sequential orchestrator for Phase 3 risk filters.

The layer runs each :class:`~shared.risk.filters.base.RiskFilter` in order:

* If any filter returns ``passed=False`` the chain short-circuits immediately.
  The :class:`LayerResult` carries that filter's ``skip_reason`` and a
  ``size_multiplier`` of ``1.0`` (size reduction is irrelevant on rejection).
* Filters that pass may return a ``size_multiplier < 1.0`` to request a
  proportional reduction in position size (e.g. ``ConsecutiveLossFilter``).
  Multipliers are compounded multiplicatively across all passing filters.
* When the filter list is empty the layer passes every signal unchanged.

Design notes
------------
``LayerResult`` mirrors :class:`~shared.risk.filters.base.FilterResult` in
being a **frozen** dataclass, making it safe to cache, log, or pass across
thread boundaries without defensive copying.

The ``evaluate`` method is **synchronous** — all current filters perform only
in-memory arithmetic.  An async wrapper (``aevaluate``) can be added once a
filter requires I/O, without changing the public sync API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from shared.risk.filters.base import FilterResult, RiskFilter

if TYPE_CHECKING:
    from shared.decision.signal import Signal
    from shared.risk.state import RiskStateSnapshot


@dataclass(frozen=True)
class LayerResult:
    """Immutable result returned by :class:`RiskFilterLayer`.

    Attributes:
        passed: ``True`` when all filters approved the signal.
        skip_reason: The first rejection tag encountered, or ``None`` when
            *passed* is ``True``.
        size_multiplier: Product of every passing filter's ``size_multiplier``.
            Always ``1.0`` when *passed* is ``False`` (size reduction is
            meaningless for a rejected signal).
        filter_outcomes: Ordered list of :class:`FilterResult` objects for
            every filter that was actually called.  Filters after a rejector
            are absent (short-circuit semantics).
    """

    passed: bool
    skip_reason: str | None
    size_multiplier: float
    filter_outcomes: list[FilterResult] = field(default_factory=list)


class RiskFilterLayer:
    """Sequential orchestrator that runs a list of :class:`RiskFilter` in order.

    Args:
        filters: Ordered sequence of risk filters.  The order determines both
            evaluation priority and short-circuit behaviour.

    Example::

        layer = RiskFilterLayer(filters=[
            TradingHoursFilter(config),
            DailyMDDFilter(config),
            ConsecutiveLossFilter(config),
        ])
        result = layer.evaluate(signal, state_snapshot)
        if not result.passed:
            logger.info("Signal rejected: %s", result.skip_reason)
        else:
            size = base_size * result.size_multiplier
    """

    def __init__(self, filters: list[RiskFilter]) -> None:
        self._filters: list[RiskFilter] = list(filters)

    def evaluate(
        self,
        signal: Signal,
        state_snapshot: RiskStateSnapshot,
    ) -> LayerResult:
        """Run all filters sequentially and return an aggregated :class:`LayerResult`.

        Args:
            signal: The candidate trading signal to evaluate.
            state_snapshot: Current intraday risk metrics loaded from Redis.

        Returns:
            A :class:`LayerResult` with the aggregated pass/fail decision,
            compounded size multiplier, and per-filter observability data.
        """
        outcomes: list[FilterResult] = []
        size_multiplier: float = 1.0

        for risk_filter in self._filters:
            result = risk_filter.check(signal, state_snapshot)
            outcomes.append(result)

            if not result.passed:
                # Short-circuit: reject immediately, reset multiplier to 1.0.
                return LayerResult(
                    passed=False,
                    skip_reason=result.skip_reason,
                    size_multiplier=1.0,
                    filter_outcomes=outcomes,
                )

            size_multiplier *= result.size_multiplier

        return LayerResult(
            passed=True,
            skip_reason=None,
            size_multiplier=size_multiplier,
            filter_outcomes=outcomes,
        )
