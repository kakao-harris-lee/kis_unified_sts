"""DailyTradeCountFilter — Phase 3 RiskFilterLayer, Filter #5.

Rejects entry signals once the session has reached a configured maximum number
of round-trip trades.  This prevents over-trading during adverse or choppy
sessions and caps commission exposure.

Configuration example (YAML):

.. code-block:: yaml

   daily_trade_count_filter:
     max_daily_trades: 10
"""

from __future__ import annotations

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot


class DailyTradeCountFilter(RiskFilter):
    """Reject signals when the daily trade count has reached its limit.

    The rejection condition is:

    .. code-block:: text

        state_snapshot.daily_trade_count >= max_daily_trades

    Args:
        max_daily_trades: Maximum number of trades allowed per session.
            Must be >= 1.

    Example::

        f = DailyTradeCountFilter(max_daily_trades=10)
    """

    name = "daily_trade_count"

    def __init__(self, max_daily_trades: int) -> None:
        if max_daily_trades < 1:
            raise ValueError(f"max_daily_trades must be >= 1, got {max_daily_trades!r}")
        self.max_daily_trades: int = max_daily_trades

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,  # noqa: ARG002
        state_snapshot: RiskStateSnapshot,
    ) -> FilterResult:
        """Evaluate whether the session trade count is within the limit.

        Args:
            signal: The candidate trading signal (not directly inspected).
            state_snapshot: Intraday risk metrics.  ``daily_trade_count``
                is compared against ``max_daily_trades``.

        Returns:
            :class:`FilterResult` with ``passed=False`` and
            ``skip_reason="max_daily_trades"`` when the limit has been
            reached or exceeded, otherwise ``passed=True``.
        """
        if state_snapshot.daily_trade_count >= self.max_daily_trades:
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason="max_daily_trades",
            )

        return FilterResult(passed=True, filter_name=self.name)
