"""Cost-aware filters for signal validation.

Filters trading signals based on expected returns vs trading costs
to prevent marginal setups that erode capital through fees.
"""

import logging
from typing import Dict, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CostFilterConfig(BaseModel):
    """Configuration for cost-aware signal filtering.

    Attributes:
        min_atr_cost_ratio: Minimum ratio of ATR-based expected move to round-trip cost
        commission_rate: Commission rate as decimal (e.g., 0.003 = 0.3%)
        slippage_bps: Slippage estimate in basis points (e.g., 1.5 = 0.015%)
    """

    min_atr_cost_ratio: float = Field(
        default=1.5,
        gt=0.0,
        description="Minimum edge ratio (expected_move / round_trip_cost)",
    )
    commission_rate: float = Field(
        default=0.003,
        ge=0.0,
        le=0.1,
        description="Commission rate as decimal (0.003 = 0.3%)",
    )
    slippage_bps: float = Field(
        default=1.5,
        ge=0.0,
        le=100.0,
        description="Slippage estimate in basis points",
    )


class CostFilter:
    """Cost-aware filter rejecting signals with insufficient edge.

    Evaluates whether the expected price movement (based on ATR) exceeds
    the round-trip trading cost by a configurable minimum ratio. This prevents
    entering marginal trades that are likely to lose money after costs.

    The filter calculates:
    1. Expected move percentage: ATR / price
    2. Round-trip cost: commission_rate + (slippage_bps / 10000)
    3. Edge ratio: expected_move / round_trip_cost
    4. Rejects if edge_ratio < min_atr_cost_ratio

    Example:
        - ATR = 1000 KRW, Price = 100000 KRW → expected_move = 1%
        - Commission = 0.3%, Slippage = 0.015% → round_trip_cost = 0.315%
        - Edge ratio = 1.0% / 0.315% = 3.17
        - If min_atr_cost_ratio = 1.5 → PASS (3.17 > 1.5)
    """

    def __init__(self, config: CostFilterConfig):
        self.config = config

        # Pre-calculate round-trip cost
        self._round_trip_cost = config.commission_rate + (config.slippage_bps / 10000.0)

        # Statistics tracking
        self._stats: Dict[str, float] = {
            "total_checks": 0,
            "passed": 0,
            "rejected_insufficient_edge": 0,
            "rejected_missing_atr": 0,
            "rejected_invalid_price": 0,
            "avg_edge_ratio": 0.0,
            "edge_ratio_sum": 0.0,
        }

        logger.info(
            f"CostFilter initialized: min_ratio={config.min_atr_cost_ratio:.2f}, "
            f"round_trip_cost={self._round_trip_cost:.4%}"
        )

    def check_signal(
        self,
        signal: "Signal",  # Forward reference to avoid circular import
        indicators: Dict[str, float],
        price: float,
    ) -> Tuple[bool, Optional[str]]:
        """Check if signal has sufficient edge to justify entry.

        Args:
            signal: Entry signal to validate
            indicators: Technical indicators dict (must contain 'atr')
            price: Current price for percentage calculation

        Returns:
            (pass, reason) tuple:
                - pass: True if signal should be accepted, False otherwise
                - reason: None if passed, rejection reason string if failed

        Raises:
            None - All errors return (False, reason) instead of raising
        """
        self._stats["total_checks"] += 1

        # Validate price
        if price <= 0:
            self._stats["rejected_invalid_price"] += 1
            reason = f"Invalid price: {price}"
            logger.warning(f"Cost filter rejected {signal.code}: {reason}")
            return False, reason

        # Extract ATR from indicators
        atr = indicators.get("atr")
        if atr is None or atr <= 0:
            self._stats["rejected_missing_atr"] += 1
            reason = f"Missing or invalid ATR: {atr}"
            logger.warning(f"Cost filter rejected {signal.code}: {reason}")
            return False, reason

        # Calculate expected move as percentage
        expected_move_pct = atr / price

        # Calculate edge ratio
        edge_ratio = expected_move_pct / self._round_trip_cost

        # Update rolling average
        self._stats["edge_ratio_sum"] += edge_ratio
        self._stats["avg_edge_ratio"] = (
            self._stats["edge_ratio_sum"] / self._stats["total_checks"]
        )

        # Check against minimum threshold
        if edge_ratio < self.config.min_atr_cost_ratio:
            self._stats["rejected_insufficient_edge"] += 1
            reason = (
                f"Insufficient edge ratio {edge_ratio:.2f} < {self.config.min_atr_cost_ratio:.2f} "
                f"(ATR={atr:.0f}, move={expected_move_pct:.2%}, cost={self._round_trip_cost:.4%})"
            )
            logger.info(f"Cost filter rejected {signal.code}: {reason}")
            return False, reason

        # Signal passes
        self._stats["passed"] += 1
        logger.debug(
            f"Cost filter passed {signal.code}: edge_ratio={edge_ratio:.2f} "
            f"(ATR={atr:.0f}, move={expected_move_pct:.2%})"
        )
        return True, None

    def get_stats(self) -> Dict[str, float]:
        """Get filter statistics.

        Returns:
            Dictionary containing:
                - total_checks: Total signals checked
                - passed: Signals that passed
                - rejected_insufficient_edge: Rejected due to low edge ratio
                - rejected_missing_atr: Rejected due to missing ATR
                - rejected_invalid_price: Rejected due to invalid price
                - avg_edge_ratio: Average edge ratio across all checks
                - pass_rate: Percentage of signals that passed
        """
        stats = self._stats.copy()
        if stats["total_checks"] > 0:
            stats["pass_rate"] = stats["passed"] / stats["total_checks"]
        else:
            stats["pass_rate"] = 0.0
        return stats

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        for key in self._stats:
            self._stats[key] = 0.0
        logger.debug("Cost filter statistics reset")
