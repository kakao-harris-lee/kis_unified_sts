"""SpreadFilter — Phase 3 RiskFilterLayer, Filter #7.

Rejects entry signals when the current bid-ask spread exceeds a configured
maximum number of ticks.  A wide spread indicates poor liquidity and inflates
round-trip transaction costs beyond acceptable bounds.

Design note — current spread provider
--------------------------------------
The Phase 3 filter interface accepts only ``(signal, state_snapshot)``.
However the *current* spread is a live order-book value, not a persistent
risk-state field.  To avoid polluting ``RiskStateSnapshot`` with a live
market-microstructure metric, this filter accepts a ``current_spread_provider``
callable at construction time.

The callable receives no arguments and returns a ``float`` (spread in ticks).
In production (Task 13's ``RiskFilterLayer``) this will be wired to the
live order-book feed.  In tests a simple ``lambda: value`` suffices.

Configuration example (YAML):

.. code-block:: yaml

   spread_filter:
     max_spread_ticks: 2.0
"""

from __future__ import annotations

from collections.abc import Callable

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot


class SpreadFilter(RiskFilter):
    """Reject signals when the current bid-ask spread exceeds *max_spread_ticks*.

    The rejection condition is **strict** (``>``):

    .. code-block:: text

        current_spread_provider() > max_spread_ticks

    A spread exactly equal to ``max_spread_ticks`` does *not* trigger rejection.

    Args:
        max_spread_ticks: Maximum allowable spread in ticks (inclusive boundary).
        current_spread_provider: A zero-argument callable that returns the
            current bid-ask spread in ticks as a ``float``.  Must be supplied
            at construction time.  In production this should be wired to a live
            order-book feed; in tests a ``lambda: value`` is sufficient.

    Example::

        f = SpreadFilter(
            max_spread_ticks=2.0,
            current_spread_provider=lambda: order_book.spread_ticks,
        )
    """

    name = "spread"

    def __init__(
        self,
        max_spread_ticks: float,
        current_spread_provider: Callable[[], float],
    ) -> None:
        self._max_spread_ticks: float = max_spread_ticks
        self._current_spread_provider: Callable[[], float] = current_spread_provider

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,  # noqa: ARG002
        state_snapshot: RiskStateSnapshot,  # noqa: ARG002
    ) -> FilterResult:
        """Evaluate whether the current spread is within acceptable bounds.

        Args:
            signal: The candidate trading signal (not directly inspected).
            state_snapshot: Intraday risk metrics (not used by this filter).

        Returns:
            :class:`FilterResult` with ``passed=False`` and
            ``skip_reason="spread_too_wide"`` when the current spread exceeds
            ``max_spread_ticks``, otherwise ``passed=True``.
        """
        current_spread = self._current_spread_provider()

        if current_spread > self._max_spread_ticks:
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason="spread_too_wide",
            )

        return FilterResult(passed=True, filter_name=self.name)
