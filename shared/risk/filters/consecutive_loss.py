"""ConsecutiveLossFilter — Phase 3 RiskFilterLayer, Filter #4.

Reduces position size after a soft threshold of consecutive losses and
rejects entry signals entirely after a hard threshold.  This guards against
tilt-trading (pressing during a losing streak) without permanently shutting
down the session.

Configuration example (YAML):

.. code-block:: yaml

   consecutive_loss_filter:
     soft_threshold: 4   # halve size after 4 consecutive losses
     hard_threshold: 6   # reject after 6 consecutive losses
"""

from __future__ import annotations

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot


class ConsecutiveLossFilter(RiskFilter):
    """Reduce size or reject signals during a losing streak.

    Two thresholds govern the response:

    * **Hard threshold** — if ``state.consecutive_losses >= hard_threshold``
      the filter rejects the signal with ``skip_reason="consecutive_losses_cooldown"``.
    * **Soft threshold** — if ``state.consecutive_losses >= soft_threshold``
      (but below the hard threshold) the signal passes with
      ``size_multiplier=0.5``, halving the intended position size.
    * Otherwise the signal passes with the default ``size_multiplier=1.0``.

    Args:
        soft_threshold: Number of consecutive losses at which position size
            is halved.  Must be >= 1.
        hard_threshold: Number of consecutive losses at which the signal is
            rejected outright.  Must be > soft_threshold.

    Example::

        f = ConsecutiveLossFilter(soft_threshold=4, hard_threshold=6)
    """

    name = "consecutive_loss"

    def __init__(self, soft_threshold: int, hard_threshold: int) -> None:
        if soft_threshold < 1:
            raise ValueError(f"soft_threshold must be >= 1, got {soft_threshold!r}")
        if hard_threshold <= soft_threshold:
            raise ValueError(
                f"hard_threshold ({hard_threshold!r}) must be > "
                f"soft_threshold ({soft_threshold!r})"
            )
        self.soft_threshold: int = soft_threshold
        self.hard_threshold: int = hard_threshold

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,  # noqa: ARG002
        state_snapshot: RiskStateSnapshot,
    ) -> FilterResult:
        """Evaluate the signal against the current consecutive-loss streak.

        Args:
            signal: The candidate trading signal (not directly inspected).
            state_snapshot: Intraday risk metrics.  ``consecutive_losses``
                is read to apply the soft/hard thresholds.

        Returns:
            :class:`FilterResult` with:

            * ``passed=False, skip_reason="consecutive_losses_cooldown"``
              when losses >= hard threshold.
            * ``passed=True, size_multiplier=0.5`` when losses >= soft
              threshold (but below hard threshold).
            * ``passed=True, size_multiplier=1.0`` otherwise.
        """
        losses = state_snapshot.consecutive_losses

        if losses >= self.hard_threshold:
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason="consecutive_losses_cooldown",
            )

        if losses >= self.soft_threshold:
            return FilterResult(
                passed=True,
                filter_name=self.name,
                size_multiplier=0.5,
            )

        return FilterResult(passed=True, filter_name=self.name)
