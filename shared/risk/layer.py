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

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from shared.risk.filters.base import FilterResult, RiskFilter

if TYPE_CHECKING:
    from shared.decision.signal import Signal
    from shared.risk.config import FuturesRiskConfig
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

    @classmethod
    def from_config(
        cls,
        config: FuturesRiskConfig,
        trading_windows: list[str],
        *,
        current_atr_provider: Callable[[], float] | None = None,
        current_spread_provider: Callable[[], float] | None = None,
        has_open_position_provider: Callable[[str], bool] | None = None,
    ) -> RiskFilterLayer:
        """Build a fully-wired RiskFilterLayer from a FuturesRiskConfig + providers.

        All 8 Phase 3 filters are assembled in the spec §6.1 order:

        1. :class:`TradingHoursFilter` — KST trading-window whitelist.
        2. :class:`DailyMDDFilter`.
        3. :class:`WeeklyMDDFilter`.
        4. :class:`ConsecutiveLossFilter` (may return size_multiplier=0.5).
        5. :class:`DailyTradeCountFilter`.
        6. :class:`VolatilityFilter` — uses ``current_atr_provider`` if given,
           else a stub that returns 0.0 (never rejects on volatility).
        7. :class:`SpreadFilter` — uses ``current_spread_provider`` if given,
           else a stub that returns 0.0 (never rejects on spread).
        8. :class:`OpenPositionFilter` — uses ``has_open_position_provider``
           if given, else a stub that always returns False (never rejects
           for duplicate positions).

        The stubs let the backtest run the layer in a reproducible way
        without wiring real position / ATR / LOB sources; Phase 4 overrides
        them with live providers.
        """
        from shared.risk.filters.consecutive_loss import ConsecutiveLossFilter
        from shared.risk.filters.daily_mdd import DailyMDDFilter
        from shared.risk.filters.daily_trade_count import DailyTradeCountFilter
        from shared.risk.filters.open_position import OpenPositionFilter
        from shared.risk.filters.spread import SpreadFilter
        from shared.risk.filters.trading_hours import TradingHoursFilter
        from shared.risk.filters.volatility import VolatilityFilter
        from shared.risk.filters.weekly_mdd import WeeklyMDDFilter

        if current_atr_provider is None:

            def current_atr_provider() -> float:
                return 0.0

        if current_spread_provider is None:

            def current_spread_provider() -> float:
                return 0.0

        if has_open_position_provider is None:

            def has_open_position_provider(_symbol: str) -> bool:
                return False

        filters: list[RiskFilter] = [
            TradingHoursFilter(trading_windows=trading_windows),
            DailyMDDFilter(
                account_equity_krw=config.account_equity_krw,
                daily_mdd_limit_pct=config.daily_mdd_limit_pct,
            ),
            WeeklyMDDFilter(
                account_equity_krw=config.account_equity_krw,
                weekly_mdd_limit_pct=config.weekly_mdd_limit_pct,
            ),
            ConsecutiveLossFilter(
                soft_threshold=config.consecutive_loss_soft_threshold,
                hard_threshold=config.consecutive_loss_hard_threshold,
            ),
            DailyTradeCountFilter(max_daily_trades=config.max_daily_trades),
            VolatilityFilter(current_atr_provider=current_atr_provider),
            SpreadFilter(
                max_spread_ticks=config.max_spread_ticks,
                current_spread_provider=current_spread_provider,
            ),
            OpenPositionFilter(has_open_position_provider=has_open_position_provider),
        ]
        return cls(filters=filters)

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
