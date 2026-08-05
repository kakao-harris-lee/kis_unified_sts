"""OpenPositionFilter — Phase 3 RiskFilterLayer, Filter #8.

Rejects entry signals when an open position already exists for the signal's
symbol.  This prevents the system from doubling into an existing position
unintentionally and enforces a one-position-per-symbol policy.

Design note — has_open_position provider
-----------------------------------------
The Phase 3 filter interface accepts only ``(signal, state_snapshot)``.
However the open-position state is maintained by ``PositionTracker``, not
``RiskStateSnapshot``.  To avoid coupling this filter to a concrete
``PositionTracker`` instance, the filter accepts a ``has_open_position_provider``
callable at construction time.

The callable receives a *symbol* string and returns ``True`` if an open position
exists for that symbol.  In production both risk-filter daemons wire it to a
sync-Redis ``HEXISTS`` against their chain's open-position hash:

* futures — ``futures:monitor:positions``, field = contract symbol, written by
  ``services/futures_monitor`` (HSET on an entry fill, HDEL on an exit fill);
* stock — ``stock:daemon:positions``, field = stock code, written by
  ``services/stock_order_router`` and ``services/stock_exit``.

Both resolve a Redis error to ``True`` — fail-closed, blocking re-entry on
uncertainty.  In tests a simple ``lambda symbol: False`` suffices.

When no provider is supplied, :meth:`RiskFilterLayer.from_config` substitutes a
stub that returns ``False`` for every symbol and logs a warning.  That stub does
not merely leave a filter inert: it reports "no position held" unconditionally,
which *disables* the duplicate-entry guard.  Callers that hold positions must
pass a real provider.

Configuration example (YAML):

.. code-block:: yaml

   open_position_filter: {}  # no static config — injected via provider
"""

from __future__ import annotations

from collections.abc import Callable

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot


class OpenPositionFilter(RiskFilter):
    """Reject signals when an open position already exists for the signal's symbol.

    Delegates the position-existence check to a caller-supplied provider
    callable, keeping this filter decoupled from any specific position tracker
    implementation.

    Args:
        has_open_position_provider: A callable that accepts a *symbol* string
            and returns ``True`` if an open position exists for that symbol.
            In production this is wired to a ``HEXISTS`` against the chain's
            open-position hash (see the module docstring); in tests a
            ``lambda symbol: True/False`` is sufficient.

    Example::

        f = OpenPositionFilter(
            has_open_position_provider=lambda symbol: bool(
                redis.hexists("futures:monitor:positions", symbol)
            ),
        )
    """

    name = "open_position"

    def __init__(
        self,
        has_open_position_provider: Callable[[str], bool],
    ) -> None:
        self._has_open_position_provider: Callable[[str], bool] = (
            has_open_position_provider
        )

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,
        state_snapshot: RiskStateSnapshot,  # noqa: ARG002
    ) -> FilterResult:
        """Evaluate whether a conflicting open position exists.

        Args:
            signal: The candidate trading signal.  ``signal.symbol`` is
                passed to the provider to check for an existing position.
            state_snapshot: Intraday risk metrics (not used by this filter).

        Returns:
            :class:`FilterResult` with ``passed=False`` and
            ``skip_reason="position_already_open"`` when the provider reports
            an open position for ``signal.symbol``, otherwise ``passed=True``.
        """
        if self._has_open_position_provider(signal.symbol):
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason="position_already_open",
            )

        return FilterResult(passed=True, filter_name=self.name)
