"""ConsecutiveLossFilter — Phase 3 RiskFilterLayer, Filter #4.

Reduces position size after a soft threshold of consecutive losses and
rejects entry signals entirely after a hard threshold.  This guards against
tilt-trading (pressing during a losing streak) without permanently shutting
down the session.

Phase 3C (design spec §4.2, ticket C2) adds *persistence* to the soft
reduction: when the streak reaches the soft threshold, the state writer
(:class:`~shared.risk.runtime_state.RuntimeRiskState`) records a
``size_reduce_until_kst`` timestamp (now + ``soft_reduce_persist_days``).
This filter keeps returning ``size_multiplier=0.5`` until that timestamp
passes — even after wins reset the raw streak counter, and across process
restarts.  The hard threshold behaviour is unchanged.

Configuration example (YAML — ``config/risk.yaml``):

.. code-block:: yaml

   risk:
     consecutive_loss_soft_threshold: 4   # halve size after 4 consecutive losses
     consecutive_loss_hard_threshold: 6   # reject after 6 consecutive losses
     soft_reduce_persist_days: 14         # keep the x0.5 window for 14 KST days
     reduce_blocks_at_floor: false        # operator policy for base-quantity-1
"""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.primitives.breakers import consecutive_exceeds
from shared.risk.state import RiskStateSnapshot

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")


class ConsecutiveLossFilter(RiskFilter):
    """Reduce size or reject signals during a losing streak.

    Two thresholds govern the response:

    * **Hard threshold** — if ``state.consecutive_losses >= hard_threshold``
      the filter rejects the signal with ``skip_reason="consecutive_losses_cooldown"``.
    * **Soft threshold** — if ``state.consecutive_losses >= soft_threshold``
      (but below the hard threshold), **or** the persisted soft-reduce window
      (``state.size_reduce_until_kst``) is still open, the signal passes with
      ``size_multiplier=0.5``, halving the intended position size.
    * Otherwise the signal passes with the default ``size_multiplier=1.0``.

    Floor-at-1 policy (``reduce_blocks_at_floor``): with a base quantity of
    one contract the order router floors ``0.5 -> 1``, making the reduction
    a no-op.  When this flag is ``True`` the filter rejects entries outright
    while the reduction is active (``skip_reason="consecutive_losses_floor_block"``)
    — the conservative reading of spec §4.2 for one-contract operation.
    The default ``False`` preserves current behaviour; the ineffective
    reduction is still observable via an INFO log line.

    Args:
        soft_threshold: Number of consecutive losses at which position size
            is halved.  Must be >= 1.
        hard_threshold: Number of consecutive losses at which the signal is
            rejected outright.  Must be > soft_threshold.
        reduce_blocks_at_floor: Operator policy flag (see above). Default
            ``False``.

    Example::

        f = ConsecutiveLossFilter(soft_threshold=4, hard_threshold=6)
    """

    name = "consecutive_loss"

    def __init__(
        self,
        soft_threshold: int,
        hard_threshold: int,
        *,
        reduce_blocks_at_floor: bool = False,
    ) -> None:
        if soft_threshold < 1:
            raise ValueError(f"soft_threshold must be >= 1, got {soft_threshold!r}")
        if hard_threshold <= soft_threshold:
            raise ValueError(
                f"hard_threshold ({hard_threshold!r}) must be > "
                f"soft_threshold ({soft_threshold!r})"
            )
        self.soft_threshold: int = soft_threshold
        self.hard_threshold: int = hard_threshold
        self.reduce_blocks_at_floor: bool = reduce_blocks_at_floor

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,
        state_snapshot: RiskStateSnapshot,
    ) -> FilterResult:
        """Evaluate the signal against the current consecutive-loss streak.

        Args:
            signal: The candidate trading signal.  ``generated_at`` (when
                present) supplies "now" for the soft-reduce window check.
            state_snapshot: Intraday risk metrics.  ``consecutive_losses``
                drives the soft/hard thresholds; ``size_reduce_until_kst``
                drives the persisted reduction window.

        Returns:
            :class:`FilterResult` with:

            * ``passed=False, skip_reason="consecutive_losses_cooldown"``
              when losses >= hard threshold.
            * ``passed=False, skip_reason="consecutive_losses_floor_block"``
              when the reduction is active and ``reduce_blocks_at_floor``.
            * ``passed=True, size_multiplier=0.5`` when losses >= soft
              threshold or the persisted reduce window is open.
            * ``passed=True, size_multiplier=1.0`` otherwise.
        """
        losses = state_snapshot.consecutive_losses

        # Shared raw-count predicate (P4-d). Only the ``>=`` threshold math is
        # shared; the size-reduction multiplier, KST persist window, and floor
        # policy below stay filter-owned. Hard and soft stay distinct tiers.
        if consecutive_exceeds(losses, self.hard_threshold):
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason="consecutive_losses_cooldown",
            )

        window_until = self._reduce_window_until(state_snapshot)
        reduce_active = consecutive_exceeds(losses, self.soft_threshold)
        if not reduce_active and window_until is not None:
            reduce_active = self._signal_time_kst(signal) < window_until

        if reduce_active:
            if self.reduce_blocks_at_floor:
                logger.warning(
                    "consecutive-loss reduction active and "
                    "reduce_blocks_at_floor=true: rejecting entry "
                    "(losses=%d, window_until=%s)",
                    losses,
                    window_until,
                )
                return FilterResult(
                    passed=False,
                    filter_name=self.name,
                    skip_reason="consecutive_losses_floor_block",
                )
            # Floor-at-1 observability: with base_quantity=1 the order
            # router floors the halved size back to 1 contract, so this
            # reduction is a no-op in practice. Operators can switch to
            # blocking via risk.yaml reduce_blocks_at_floor: true.
            logger.info(
                "consecutive-loss soft reduction: size_multiplier=0.5 "
                "(losses=%d, window_until=%s); note: base_quantity=1 floors "
                "the scaled size back to 1 contract (reduce_blocks_at_floor=false)",
                losses,
                window_until,
            )
            return FilterResult(
                passed=True,
                filter_name=self.name,
                size_multiplier=0.5,
            )

        return FilterResult(passed=True, filter_name=self.name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _reduce_window_until(state_snapshot: RiskStateSnapshot) -> datetime | None:
        """Parse the persisted soft-reduce window end, if any."""
        raw = getattr(state_snapshot, "size_reduce_until_kst", "") or ""
        if not raw:
            return None
        try:
            until = datetime.fromisoformat(raw)
        except ValueError:
            logger.warning("unparseable size_reduce_until_kst=%r; ignoring", raw)
            return None
        return until if until.tzinfo else until.replace(tzinfo=_KST)

    @staticmethod
    def _signal_time_kst(signal: Signal) -> datetime:
        """Signal time in KST; falls back to wall-clock now when absent."""
        generated_at = getattr(signal, "generated_at", None)
        if generated_at is None:
            return datetime.now(_KST)
        if generated_at.tzinfo is None:
            return generated_at.replace(tzinfo=_KST)
        return generated_at.astimezone(_KST)
