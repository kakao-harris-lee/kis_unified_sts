"""TradingHoursFilter — Phase 3 RiskFilterLayer, Filter #1.

Rejects signals whose ``generated_at`` timestamp falls outside all configured
KST trading windows.  Windows are supplied as ``"HH:MM-HH:MM"`` strings in
Korea Standard Time (UTC+9) and are treated as **half-open** intervals
``[start, end)``: the start minute is included, the end minute is excluded.

Configuration example (YAML):

.. code-block:: yaml

   trading_hours_filter:
     trading_windows:
       - "09:00-10:30"
       - "14:30-15:20"
"""

from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot

_KST = ZoneInfo("Asia/Seoul")


class TradingHoursFilter(RiskFilter):
    """Reject signals generated outside the configured KST trading windows.

    Args:
        trading_windows: List of ``"HH:MM-HH:MM"`` strings defining valid
            trading windows in Korea Standard Time.  An empty list means no
            time is ever valid (all signals rejected).

    Example::

        f = TradingHoursFilter(trading_windows=["09:00-10:30", "14:30-15:20"])
    """

    name = "trading_hours"

    def __init__(self, trading_windows: list[str]) -> None:
        self.trading_windows: list[str] = trading_windows
        # Pre-parse windows into (start_time, end_time) tuples for O(1) checks.
        self._parsed: list[tuple[time, time]] = [
            self._parse_window(w) for w in trading_windows
        ]

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,
        state_snapshot: RiskStateSnapshot,  # noqa: ARG002
    ) -> FilterResult:
        """Return ``passed=True`` if ``signal.generated_at`` is inside any window.

        Args:
            signal: The candidate trading signal.  ``generated_at`` must be a
                timezone-aware :class:`datetime.datetime`.
            state_snapshot: Intraday risk metrics (unused by this filter).

        Returns:
            :class:`FilterResult` with ``passed=True`` when the signal time
            falls inside at least one configured window, otherwise
            ``passed=False`` with ``skip_reason="outside_trading_hours"``.
        """
        if signal.generated_at is None:
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason="outside_trading_hours",
            )

        kst_dt = signal.generated_at.astimezone(_KST)
        signal_time = kst_dt.time().replace(tzinfo=None)

        for start, end in self._parsed:
            if start <= signal_time < end:
                return FilterResult(passed=True, filter_name=self.name)

        return FilterResult(
            passed=False,
            filter_name=self.name,
            skip_reason="outside_trading_hours",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_window(window: str) -> tuple[time, time]:
        """Parse ``"HH:MM-HH:MM"`` into a ``(start, end)`` :class:`time` tuple.

        Args:
            window: A string of the form ``"09:00-10:30"``.

        Returns:
            A two-element tuple ``(start_time, end_time)``.

        Raises:
            ValueError: If the string cannot be parsed.
        """
        try:
            start_str, end_str = window.split("-", 1)
            start_h, start_m = (int(x) for x in start_str.strip().split(":"))
            end_h, end_m = (int(x) for x in end_str.strip().split(":"))
            return time(start_h, start_m), time(end_h, end_m)
        except Exception as exc:
            raise ValueError(
                f"Invalid trading window format {window!r}. Expected 'HH:MM-HH:MM'."
            ) from exc
