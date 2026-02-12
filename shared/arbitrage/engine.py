"""Arbitrage Engine for Mode A Sniper Basis Trading."""
import logging
import time
from typing import Optional, Tuple

from .config import ArbitrageConfig
from .models import ArbitrageSignal, BasisData
from .basis_calculator import BasisCalculator

logger = logging.getLogger(__name__)


class ArbitrageEngine:
    """Mode A Sniper Arbitrage Engine.

    Entry Filters:
    1. Time Filter - Trading hours only
    2. Dividend Blackout - No trading near expiry
    3. Spread Filter - Tight spreads only
    4. Depth Filter - Sufficient liquidity
    5. Basis Signal - Z-score threshold
    """

    def __init__(self, config: ArbitrageConfig):
        self.config = config
        self.basis_calculator = BasisCalculator(config)

        # Statistics
        self._stats = {
            'total_checks': 0,
            'passed': 0,
            'rejected_spread': 0,
            'rejected_depth': 0,
            'rejected_no_signal': 0,
        }

    def update_basis(
        self,
        spot_index: float,
        futures_price: float,
        days_to_expiry: int,
        timestamp: Optional[float] = None
    ) -> BasisData:
        """Update basis calculation."""
        return self.basis_calculator.update(
            spot_index=spot_index,
            futures_price=futures_price,
            days_to_expiry=days_to_expiry,
            timestamp=timestamp
        )

    def check_spread(
        self,
        best_bid: float,
        best_ask: float
    ) -> Tuple[bool, Optional[ArbitrageSignal], str]:
        """Check spread filter."""
        spread = best_ask - best_bid
        spread_ticks = int(spread / self.config.tick_size + 0.5)

        if spread_ticks > self.config.max_spread_ticks:
            return False, None, f"Spread too wide: {spread_ticks} ticks"

        return True, None, "OK"

    def check_depth(self, bid_qty: float, ask_qty: float) -> bool:
        """Check if depth is sufficient."""
        min_depth = self.config.order_size * self.config.depth_multiplier
        return min(bid_qty, ask_qty) >= min_depth

    def check_entry(
        self,
        spot_index: float,
        futures_price: float,  # noqa: ARG002
        days_to_expiry: int,
        best_bid: float,
        best_ask: float,
        bid_qty: float,
        ask_qty: float,
        timestamp: Optional[float] = None
    ) -> Tuple[bool, Optional[ArbitrageSignal], str]:
        """Check if entry conditions are met.

        Returns:
            (can_enter, signal, reason)
        """
        self._stats['total_checks'] += 1
        timestamp = timestamp or time.time()

        # 1. Spread Filter
        spread_ok, _, reason = self.check_spread(best_bid, best_ask)
        if not spread_ok:
            self._stats['rejected_spread'] += 1
            return False, None, reason

        # 2. Depth Filter
        if not self.check_depth(bid_qty, ask_qty):
            self._stats['rejected_depth'] += 1
            min_depth = self.config.order_size * self.config.depth_multiplier
            return False, None, f"Insufficient depth: need {min_depth}"

        # 3. Update basis and check signal
        mid_price = (best_bid + best_ask) / 2
        basis_data = self.update_basis(spot_index, mid_price, days_to_expiry, timestamp)

        if not self.basis_calculator.is_ready():
            samples = len(self.basis_calculator.basis_history)
            return False, None, f"Warming up: {samples}/{self.config.min_samples}"

        has_signal, direction = self.basis_calculator.is_signal()
        if not has_signal:
            self._stats['rejected_no_signal'] += 1
            z = basis_data.basis_zscore
            return False, None, f"No signal: z={z:.2f}"

        # All filters passed
        self._stats['passed'] += 1

        entry_price = best_bid if direction == "BUY" else best_ask

        signal = ArbitrageSignal(
            timestamp=timestamp,
            direction=direction,
            basis_zscore=basis_data.basis_zscore,
            entry_price=entry_price,
            order_size=self.config.order_size,
            basis_data=basis_data,
        )

        logger.info(f"Arbitrage signal: {direction} @ {entry_price}, z={basis_data.basis_zscore:.2f}")

        return True, signal, f"Signal: {direction}"

    def get_stats(self) -> dict:
        """Return engine statistics."""
        return self._stats.copy()
