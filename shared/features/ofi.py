"""Order Flow Imbalance (OFI) Calculator."""
import logging
from collections import deque
from typing import Deque, Optional, Tuple

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class OFIConfig(BaseModel):
    """Configuration for OFI calculator."""

    model_config = ConfigDict(frozen=True)

    lookback: int = Field(default=20, description="Lookback period for OFI calculation")
    threshold: float = Field(default=2.0, description="Z-score threshold for signals")
    min_samples: int = Field(default=10, description="Minimum samples before signals")


class OFICalculator:
    """Calculate Order Flow Imbalance from order book data.

    OFI measures the net buying/selling pressure by tracking changes
    in bid and ask quantities at the best prices.

    Formula:
        OFI = sum of (bid_qty_change - ask_qty_change) when price unchanged
              + bid_qty when bid price increases
              - ask_qty when ask price decreases

    A positive OFI indicates buying pressure (more aggressive buyers).
    A negative OFI indicates selling pressure (more aggressive sellers).
    """

    def __init__(self, config: OFIConfig):
        self.config = config

        # Order book state
        self._prev_bid: Optional[float] = None
        self._prev_bid_qty: Optional[float] = None
        self._prev_ask: Optional[float] = None
        self._prev_ask_qty: Optional[float] = None

        # OFI history
        self._ofi_history: Deque[float] = deque(maxlen=config.lookback)
        self._cumulative_ofi: float = 0.0

    def update(
        self,
        best_bid: float,
        bid_qty: float,
        best_ask: float,
        ask_qty: float
    ) -> float:
        """Update OFI with new order book snapshot.

        Args:
            best_bid: Best bid price
            bid_qty: Quantity at best bid
            best_ask: Best ask price
            ask_qty: Quantity at best ask

        Returns:
            Current tick OFI
        """
        tick_ofi = 0.0

        if self._prev_bid is not None:
            # Calculate OFI based on Lee-Ready style logic
            if best_bid > self._prev_bid:
                # Bid price increased - buying pressure
                tick_ofi += bid_qty
            elif best_bid == self._prev_bid:
                # Same bid price - use quantity change
                tick_ofi += (bid_qty - self._prev_bid_qty)

            if best_ask < self._prev_ask:
                # Ask price decreased - selling pressure
                tick_ofi -= ask_qty
            elif best_ask == self._prev_ask:
                # Same ask price - use quantity change
                tick_ofi -= (ask_qty - self._prev_ask_qty)

        # Update state
        self._prev_bid = best_bid
        self._prev_bid_qty = bid_qty
        self._prev_ask = best_ask
        self._prev_ask_qty = ask_qty

        # Track history
        self._ofi_history.append(tick_ofi)
        self._cumulative_ofi += tick_ofi

        return tick_ofi

    def get_ofi(self) -> float:
        """Get cumulative OFI over lookback period."""
        if not self._ofi_history:
            return 0.0
        return sum(self._ofi_history)

    def get_ofi_zscore(self) -> Optional[float]:
        """Get z-score of current OFI.

        Returns:
            Z-score or None if not enough samples
        """
        if len(self._ofi_history) < self.config.min_samples:
            return None

        arr = np.array(self._ofi_history)
        mean = np.mean(arr)
        std = np.std(arr, ddof=1)

        if std == 0:
            return 0.0

        current_ofi = self.get_ofi()
        # Z-score of cumulative OFI
        return (current_ofi - mean * len(self._ofi_history)) / (std * np.sqrt(len(self._ofi_history)))

    def is_signal(self) -> Tuple[bool, Optional[str]]:
        """Check if OFI indicates a trading signal.

        Returns:
            (has_signal, direction): direction is "BUY" or "SELL" or None
        """
        zscore = self.get_ofi_zscore()
        if zscore is None:
            return False, None

        if zscore > self.config.threshold:
            return True, "BUY"
        elif zscore < -self.config.threshold:
            return True, "SELL"

        return False, None

    def get_liquidity_score(
        self,
        spread: float,
        bid_depth: float,
        ask_depth: float,
        avg_spread: float,
        avg_depth: float
    ) -> float:
        """Calculate liquidity score based on current market conditions.

        Args:
            spread: Current bid-ask spread
            bid_depth: Current bid depth
            ask_depth: Current ask depth
            avg_spread: Average spread
            avg_depth: Average depth

        Returns:
            Liquidity score (0.0 to 1.0)
        """
        # Spread component (tighter is better)
        if avg_spread > 0:
            spread_score = min(1.0, avg_spread / spread) if spread > 0 else 1.0
        else:
            spread_score = 0.5

        # Depth component (deeper is better)
        total_depth = bid_depth + ask_depth
        if avg_depth > 0:
            depth_score = min(1.0, total_depth / (2 * avg_depth))
        else:
            depth_score = 0.5

        # Imbalance penalty (balanced is better)
        if total_depth > 0:
            imbalance = abs(bid_depth - ask_depth) / total_depth
            balance_score = 1.0 - imbalance
        else:
            balance_score = 0.5

        # Weighted average
        score = 0.4 * spread_score + 0.4 * depth_score + 0.2 * balance_score

        return score

    def reset(self) -> None:
        """Reset calculator state."""
        self._prev_bid = None
        self._prev_bid_qty = None
        self._prev_ask = None
        self._prev_ask_qty = None
        self._ofi_history.clear()
        self._cumulative_ofi = 0.0
