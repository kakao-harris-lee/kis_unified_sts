"""DailyMDDFilter — Phase 3 RiskFilterLayer, Filter #2.

Rejects entry signals when the session's realised + unrealised P&L has fallen
below a configurable percentage of account equity.  The guard is applied
**strictly** (``<``) so that a loss exactly equal to the threshold still
passes — the filter only fires when the loss *exceeds* the limit.

Configuration example (YAML):

.. code-block:: yaml

   daily_mdd_filter:
     account_equity_krw: 5_000_000
     daily_mdd_limit_pct: 0.03   # 3 % of account equity
"""

from __future__ import annotations

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot


class DailyMDDFilter(RiskFilter):
    """Reject signals when daily P&L has breached the configured MDD limit.

    The rejection condition is:

    .. code-block:: text

        state_snapshot.daily_pnl_krw / account_equity_krw < -daily_mdd_limit_pct

    Because the comparison is **strict** (``<``), a loss exactly equal to
    ``daily_mdd_limit_pct`` does *not* trigger a rejection.

    Args:
        account_equity_krw: Total account equity in KRW used to compute the
            loss percentage.  Must be supplied at construction time; load from
            YAML to avoid hardcoding.
        daily_mdd_limit_pct: Maximum tolerated daily loss as a fraction of
            equity (e.g. ``0.03`` for 3 %).

    Example::

        f = DailyMDDFilter(account_equity_krw=5_000_000.0, daily_mdd_limit_pct=0.03)
    """

    name = "daily_mdd"

    def __init__(
        self,
        account_equity_krw: float,
        daily_mdd_limit_pct: float,
    ) -> None:
        self.account_equity_krw: float = account_equity_krw
        self.daily_mdd_limit_pct: float = daily_mdd_limit_pct

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,  # noqa: ARG002
        state_snapshot: RiskStateSnapshot,
    ) -> FilterResult:
        """Evaluate whether today's P&L remains within the MDD limit.

        Args:
            signal: The candidate trading signal (not directly inspected by
                this filter; presence allows uniform filter-chain API).
            state_snapshot: Intraday risk metrics.  ``daily_pnl_krw`` is read
                to compute the current loss fraction.

        Returns:
            :class:`FilterResult` with ``passed=True`` when the loss is within
            the limit, otherwise ``passed=False`` with
            ``skip_reason="daily_mdd_exceeded"``.
        """
        loss_fraction = state_snapshot.daily_pnl_krw / self.account_equity_krw

        if loss_fraction < -self.daily_mdd_limit_pct:
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason="daily_mdd_exceeded",
            )

        return FilterResult(passed=True, filter_name=self.name)
