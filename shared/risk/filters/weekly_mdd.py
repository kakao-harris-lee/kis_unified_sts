"""WeeklyMDDFilter — Phase 3 RiskFilterLayer, Filter #3.

Rejects entry signals when the rolling weekly P&L has fallen below a
configurable percentage of account equity.  Mirrors the logic of
:class:`~shared.risk.filters.daily_mdd.DailyMDDFilter` but operates on
``state_snapshot.weekly_pnl_krw`` and uses ``skip_reason="weekly_mdd_exceeded"``.

The comparison is **strict** (``<``) so a loss exactly equal to the limit
still passes — rejection fires only when the loss *exceeds* the threshold.

Configuration example (YAML):

.. code-block:: yaml

   weekly_mdd_filter:
     account_equity_krw: 5_000_000
     weekly_mdd_limit_pct: 0.06   # 6 % of account equity
"""

from __future__ import annotations

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.primitives.breakers import loss_fraction_exceeds
from shared.risk.state import RiskStateSnapshot


class WeeklyMDDFilter(RiskFilter):
    """Reject signals when rolling weekly P&L has breached the MDD limit.

    The rejection condition is:

    .. code-block:: text

        state_snapshot.weekly_pnl_krw / account_equity_krw < -weekly_mdd_limit_pct

    Because the comparison is **strict** (``<``), a loss exactly equal to
    ``weekly_mdd_limit_pct`` does *not* trigger a rejection.

    Args:
        account_equity_krw: Total account equity in KRW.  Load from YAML to
            avoid hardcoding.
        weekly_mdd_limit_pct: Maximum tolerated rolling weekly loss as a
            fraction of equity (e.g. ``0.06`` for 6 %).

    Example::

        f = WeeklyMDDFilter(account_equity_krw=5_000_000.0, weekly_mdd_limit_pct=0.06)
    """

    name = "weekly_mdd"

    def __init__(
        self,
        account_equity_krw: float,
        weekly_mdd_limit_pct: float,
    ) -> None:
        self.account_equity_krw: float = account_equity_krw
        self.weekly_mdd_limit_pct: float = weekly_mdd_limit_pct

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,  # noqa: ARG002
        state_snapshot: RiskStateSnapshot,
    ) -> FilterResult:
        """Evaluate whether the rolling weekly P&L remains within the MDD limit.

        Args:
            signal: The candidate trading signal (not directly inspected by
                this filter).
            state_snapshot: Intraday risk metrics.  ``weekly_pnl_krw`` is read
                to compute the current weekly loss fraction.

        Returns:
            :class:`FilterResult` with ``passed=True`` when the loss is within
            the limit, otherwise ``passed=False`` with
            ``skip_reason="weekly_mdd_exceeded"``.
        """
        # Shared loss-fraction predicate (P4-d). Strict boundary
        # (``inclusive=False``) and guardless division
        # (``equity_nonpositive="raise"``) reproduce this filter's exact prior
        # behavior: ``weekly_pnl_krw / account_equity_krw < -weekly_mdd_limit_pct``.
        if loss_fraction_exceeds(
            state_snapshot.weekly_pnl_krw,
            self.account_equity_krw,
            self.weekly_mdd_limit_pct,
            inclusive=False,
            equity_nonpositive="raise",
        ):
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason="weekly_mdd_exceeded",
            )

        return FilterResult(passed=True, filter_name=self.name)
