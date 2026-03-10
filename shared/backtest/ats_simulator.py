"""ATS execution simulator for backtesting.

Simulates Korean ATS (넥스트레이드) execution characteristics including:
- Venue selection (KRX vs ATS)
- Fill rate modeling (ATS typically has lower fill rate than KRX)
- Price improvement simulation (ATS may provide better execution prices)
- Latency effects

Usage:
    from shared.backtest.ats_simulator import ATSSimulator

    # Create simulator from config
    simulator = ATSSimulator(
        ats_fill_rate=0.65,
        price_improvement_mean_bps=3.0,
        price_improvement_std_bps=2.0,
        latency_penalty_ms=15.0
    )

    # Simulate venue selection
    venue = simulator.simulate_venue_selection(
        order_size=100,
        market_data={"krx_best_ask": 70000, "ats_best_ask": 69980}
    )

    # Simulate fill
    filled, fill_price = simulator.simulate_fill(
        venue="ATS",
        order_side="BUY",
        order_price=70000,
        order_size=100
    )
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from shared.execution.config import ATSSimulationConfig

logger = logging.getLogger(__name__)


@dataclass
class VenueSelection:
    """Result of venue selection simulation.

    Attributes:
        venue: Selected venue (KRX or ATS)
        reason: Reason for selection
        expected_price_improvement_bps: Expected price improvement if ATS
        estimated_fill_rate: Estimated fill probability
    """

    venue: Literal["KRX", "ATS"]
    reason: str
    expected_price_improvement_bps: float = 0.0
    estimated_fill_rate: float = 1.0


@dataclass
class FillResult:
    """Result of fill simulation.

    Attributes:
        filled: Whether order was filled
        fill_price: Actual fill price (None if not filled)
        fill_quantity: Filled quantity
        price_improvement_bps: Actual price improvement achieved (can be negative)
        latency_ms: Execution latency
    """

    filled: bool
    fill_price: float | None
    fill_quantity: int
    price_improvement_bps: float = 0.0
    latency_ms: float = 0.0


class ATSSimulator:
    """ATS execution simulator for backtesting.

    Simulates realistic ATS execution characteristics:
    - Lower fill rates than KRX (configurable, typically 60-70%)
    - Price improvement opportunities (mean +3 bps, stochastic)
    - Additional latency penalty (~15ms)

    KRX baseline:
    - Fill rate: ~100% for liquid stocks
    - Price improvement: minimal
    - Latency: baseline
    """

    def __init__(
        self,
        ats_fill_rate: float = 0.65,
        price_improvement_mean_bps: float = 3.0,
        price_improvement_std_bps: float = 2.0,
        latency_penalty_ms: float = 15.0,
        random_seed: int | None = None,
    ):
        """Initialize ATS simulator.

        Args:
            ats_fill_rate: Average fill rate for ATS (0.0-1.0)
            price_improvement_mean_bps: Mean price improvement in bps
            price_improvement_std_bps: Standard deviation of price improvement
            latency_penalty_ms: Additional latency for ATS execution
            random_seed: Random seed for reproducibility (backtest use)
        """
        self.ats_fill_rate = ats_fill_rate
        self.price_improvement_mean_bps = price_improvement_mean_bps
        self.price_improvement_std_bps = price_improvement_std_bps
        self.latency_penalty_ms = latency_penalty_ms

        # Instance-level RNG to avoid mutating global random state
        self._rng = random.Random(random_seed)
        self._np_rng = np.random.default_rng(random_seed)

        logger.info(
            f"ATSSimulator initialized: fill_rate={ats_fill_rate:.1%}, "
            f"price_improvement={price_improvement_mean_bps:.2f}±{price_improvement_std_bps:.2f} bps, "
            f"latency_penalty={latency_penalty_ms:.1f}ms"
        )

    @classmethod
    def from_config(cls, config: ATSSimulationConfig, random_seed: int | None = None) -> ATSSimulator:
        """Create simulator from config object.

        Args:
            config: ATS simulation configuration
            random_seed: Random seed for reproducibility

        Returns:
            ATSSimulator instance
        """
        return cls(
            ats_fill_rate=config.ats_fill_rate,
            price_improvement_mean_bps=config.price_improvement_mean_bps,
            price_improvement_std_bps=config.price_improvement_std_bps,
            latency_penalty_ms=config.latency_penalty_ms,
            random_seed=random_seed,
        )

    def simulate_venue_selection(
        self,
        order_size: int,
        market_data: dict[str, Any] | None = None,
        routing_score: float | None = None,
    ) -> VenueSelection:
        """Simulate venue selection for an order.

        In real execution, VenueRouter makes this decision based on market data.
        In backtests, we simulate a simplified routing decision.

        Args:
            order_size: Order size in shares
            market_data: Optional market data dict with KRX/ATS quotes
            routing_score: Optional pre-computed routing score (0-1, higher = prefer ATS)

        Returns:
            VenueSelection with chosen venue and reasoning
        """
        # If routing_score provided, use it directly
        if routing_score is not None:
            if routing_score >= 0.5:
                return VenueSelection(
                    venue="ATS",
                    reason=f"routing_score={routing_score:.2f} (threshold 0.5)",
                    expected_price_improvement_bps=self.price_improvement_mean_bps,
                    estimated_fill_rate=self.ats_fill_rate,
                )
            else:
                return VenueSelection(
                    venue="KRX",
                    reason=f"routing_score={routing_score:.2f} (below 0.5 threshold)",
                    expected_price_improvement_bps=0.0,
                    estimated_fill_rate=1.0,
                )

        # Simple heuristic: ATS preferred if expected value is positive
        # Expected value = price_improvement * fill_rate - opportunity_cost * (1 - fill_rate)
        # Assume opportunity cost ~= 2 bps (market impact of delayed fill)
        opportunity_cost_bps = 2.0
        ats_expected_value = (
            self.price_improvement_mean_bps * self.ats_fill_rate
            - opportunity_cost_bps * (1.0 - self.ats_fill_rate)
        )

        if ats_expected_value > 0:
            return VenueSelection(
                venue="ATS",
                reason=f"positive expected value ({ats_expected_value:.2f} bps)",
                expected_price_improvement_bps=self.price_improvement_mean_bps,
                estimated_fill_rate=self.ats_fill_rate,
            )
        else:
            return VenueSelection(
                venue="KRX",
                reason=f"negative ATS expected value ({ats_expected_value:.2f} bps)",
                expected_price_improvement_bps=0.0,
                estimated_fill_rate=1.0,
            )

    def simulate_fill(
        self,
        venue: Literal["KRX", "ATS"],
        order_side: Literal["BUY", "SELL"],
        order_price: float,
        order_size: int,
        market_price: float | None = None,
    ) -> FillResult:
        """Simulate order fill on specified venue.

        Args:
            venue: Execution venue (KRX or ATS)
            order_side: Order side (BUY or SELL)
            order_price: Limit order price
            order_size: Order size in shares
            market_price: Current market price (for price improvement calc)

        Returns:
            FillResult with fill status and execution details
        """
        if venue == "KRX":
            return self._simulate_krx_fill(order_side, order_price, order_size, market_price)
        else:
            return self._simulate_ats_fill(order_side, order_price, order_size, market_price)

    def _simulate_krx_fill(
        self,
        order_side: Literal["BUY", "SELL"],
        order_price: float,
        order_size: int,
        market_price: float | None = None,
    ) -> FillResult:
        """Simulate KRX fill (typically 100% fill rate for liquid stocks).

        Args:
            order_side: Order side
            order_price: Limit price
            order_size: Order size
            market_price: Current market price

        Returns:
            FillResult
        """
        # KRX: assume 100% fill for backtest simplicity
        # Real execution may have partial fills, but this is baseline
        filled = True
        fill_price = order_price
        latency_ms = 5.0  # Baseline latency

        # Calculate price improvement vs market price
        price_improvement_bps = 0.0
        if market_price is not None and market_price > 0:
            if order_side == "BUY":
                # Positive if filled below market
                price_improvement_bps = (market_price - fill_price) / market_price * 10000
            else:  # SELL
                # Positive if filled above market
                price_improvement_bps = (fill_price - market_price) / market_price * 10000

        return FillResult(
            filled=filled,
            fill_price=fill_price,
            fill_quantity=order_size,
            price_improvement_bps=price_improvement_bps,
            latency_ms=latency_ms,
        )

    def _simulate_ats_fill(
        self,
        order_side: Literal["BUY", "SELL"],
        order_price: float,
        order_size: int,
        market_price: float | None = None,
    ) -> FillResult:
        """Simulate ATS fill with stochastic fill rate and price improvement.

        Args:
            order_side: Order side
            order_price: Limit price
            order_size: Order size
            market_price: Current market price

        Returns:
            FillResult
        """
        # Simulate fill probability
        fill_random = self._rng.random()
        filled = fill_random < self.ats_fill_rate

        if not filled:
            return FillResult(
                filled=False,
                fill_price=None,
                fill_quantity=0,
                price_improvement_bps=0.0,
                latency_ms=self.latency_penalty_ms,
            )

        # Sample price improvement from normal distribution
        price_improvement_sample_bps = self._np_rng.normal(
            self.price_improvement_mean_bps,
            self.price_improvement_std_bps,
        )

        # Apply price improvement to fill price
        # Positive improvement = better price for trader
        if order_side == "BUY":
            # Buy: improvement = lower price
            fill_price = order_price * (1 - price_improvement_sample_bps / 10000)
        else:  # SELL
            # Sell: improvement = higher price
            fill_price = order_price * (1 + price_improvement_sample_bps / 10000)

        # Calculate actual improvement vs market price (if available)
        actual_improvement_bps = price_improvement_sample_bps
        if market_price is not None and market_price > 0:
            if order_side == "BUY":
                actual_improvement_bps = (market_price - fill_price) / market_price * 10000
            else:
                actual_improvement_bps = (fill_price - market_price) / market_price * 10000

        return FillResult(
            filled=True,
            fill_price=fill_price,
            fill_quantity=order_size,
            price_improvement_bps=actual_improvement_bps,
            latency_ms=self.latency_penalty_ms,
        )

    def apply_ats_slippage(
        self,
        order_side: Literal["BUY", "SELL"],
        base_price: float,
        venue: Literal["KRX", "ATS"],
    ) -> float:
        """Apply venue-specific slippage to execution price.

        Simplified slippage model for backtest integration.

        Args:
            order_side: Order side
            base_price: Base execution price
            venue: Execution venue

        Returns:
            Adjusted price with slippage applied
        """
        if venue == "KRX":
            # KRX: minimal slippage (handled separately by slippage_model.py if enabled)
            return base_price

        # ATS: apply sampled price improvement
        price_improvement_bps = self._np_rng.normal(
            self.price_improvement_mean_bps,
            self.price_improvement_std_bps,
        )

        if order_side == "BUY":
            # Positive improvement = lower price
            return base_price * (1 - price_improvement_bps / 10000)
        else:
            # Positive improvement = higher price
            return base_price * (1 + price_improvement_bps / 10000)
