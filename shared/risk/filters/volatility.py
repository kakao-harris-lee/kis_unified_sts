"""VolatilityFilter — Phase 3 RiskFilterLayer, Filter #6.

Rejects entry signals when the current ATR-14 exceeds the historical 90th
percentile stored in ``RiskStateSnapshot.atr_90th_percentile``.  Elevated
volatility inflates slippage and makes intraday position sizing unreliable.

Design note — current ATR provider
-----------------------------------
The Phase 3 filter interface accepts only ``(signal, state_snapshot)``.
However the *current* ATR-14 is a live computed value, not a persistent
risk-state field.  To avoid polluting ``RiskStateSnapshot`` with a live
indicator (out of scope for Task 11), this filter accepts a
``current_atr_provider`` callable at construction time.

The callable receives no arguments and returns a ``float``.  In production
(Task 13's ``RiskFilterLayer``) this will be wired to
``IndicatorEngine.get_atr14()``.  In tests a simple ``lambda: value``
suffices.

.. note::

    Phase 4 will wire ``current_atr_provider`` to a live real-time ATR
    source (e.g. ``IndicatorEngine``).  For now the caller is responsible
    for supplying a callable that returns the most recent 14-period ATR.

Configuration example (YAML):

.. code-block:: yaml

   volatility_filter: {}  # no static config — all inputs are dynamic
"""

from __future__ import annotations

from collections.abc import Callable

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot


class VolatilityFilter(RiskFilter):
    """Reject signals when the current ATR-14 exceeds the 90th-percentile ATR.

    The rejection condition is **strict** (``>``):

    .. code-block:: text

        current_atr_provider() > state_snapshot.atr_90th_percentile

    A current ATR exactly equal to the 90th-percentile threshold does *not*
    trigger a rejection.

    Args:
        current_atr_provider: A zero-argument callable that returns the
            current ATR-14 value as a ``float``.  Must be supplied at
            construction time.  In production this should be wired to a
            live indicator engine; in tests a ``lambda: value`` is
            sufficient.

    Example::

        f = VolatilityFilter(current_atr_provider=lambda: indicator_engine.atr_14)
    """

    name = "volatility"

    def __init__(self, current_atr_provider: Callable[[], float]) -> None:
        self._current_atr_provider: Callable[[], float] = current_atr_provider

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,  # noqa: ARG002
        state_snapshot: RiskStateSnapshot,
    ) -> FilterResult:
        """Evaluate whether current volatility is within acceptable bounds.

        Args:
            signal: The candidate trading signal (not directly inspected).
            state_snapshot: Intraday risk metrics.  ``atr_90th_percentile``
                is used as the upper bound.

        Returns:
            :class:`FilterResult` with ``passed=False`` and
            ``skip_reason="volatility_too_high"`` when the current ATR
            exceeds the 90th-percentile threshold, otherwise ``passed=True``.
        """
        current_atr = self._current_atr_provider()

        if current_atr > state_snapshot.atr_90th_percentile:
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason="volatility_too_high",
            )

        return FilterResult(passed=True, filter_name=self.name)
