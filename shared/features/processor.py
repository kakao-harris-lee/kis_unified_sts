"""Feature Processor for real-time market data processing."""
import logging
import time
from collections import deque
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .ofi import OFICalculator, OFIConfig

logger = logging.getLogger(__name__)


class ProcessorConfig(BaseModel):
    """Configuration for feature processor."""

    model_config = ConfigDict(frozen=True)

    # Trade processing
    vwap_window: int = Field(default=100, description="Number of trades for VWAP")
    imbalance_window: int = Field(default=50, description="Window for trade imbalance")

    # OFI config
    ofi_lookback: int = Field(default=20, description="OFI lookback period")
    ofi_threshold: float = Field(default=2.0, description="OFI signal threshold")

    # Spread tracking
    spread_window: int = Field(default=20, description="Window for spread average")

    # Liquidity scoring
    depth_baseline: float = Field(default=100.0, description="Baseline depth for liquidity scoring")
    default_liquidity_score: float = Field(default=0.5, description="Default liquidity score when data unavailable")


class FeatureProcessor:
    """Process real-time market data into features.

    Handles:
    - Trade data processing (VWAP, volume, imbalance)
    - Orderbook data processing (spread, OFI, liquidity)
    - Feature aggregation for model input

    Thread-safe for concurrent trade and orderbook updates.
    """

    def __init__(self, config: ProcessorConfig):
        self.config = config

        # OFI calculator
        ofi_config = OFIConfig(
            lookback=config.ofi_lookback,
            threshold=config.ofi_threshold,
        )
        self.ofi_calculator = OFICalculator(ofi_config)

        # Trade tracking
        self._trades: deque[dict[str, Any]] = deque(maxlen=config.vwap_window)
        self._trade_count = 0
        self._buy_volume = 0.0
        self._sell_volume = 0.0

        # Orderbook tracking
        self._spreads: deque[float] = deque(maxlen=config.spread_window)
        self._last_mid: float | None = None
        self._last_spread: float | None = None
        self._last_bid_depth: float | None = None
        self._last_ask_depth: float | None = None

    def process_trade(
        self,
        price: float,
        size: float,
        side: str,
        timestamp: float | None = None
    ) -> dict[str, Any]:
        """Process a trade event.

        Args:
            price: Trade price
            size: Trade size
            side: "BUY" or "SELL"
            timestamp: Optional timestamp

        Returns:
            Dict with trade features
        """
        timestamp = timestamp or time.time()

        trade = {
            "price": price,
            "size": size,
            "side": side,
            "timestamp": timestamp,
        }

        self._trades.append(trade)
        self._trade_count += 1

        if side == "BUY":
            self._buy_volume += size
        else:
            self._sell_volume += size

        # Calculate VWAP
        vwap = self._calculate_vwap()

        return {
            "price": price,
            "size": size,
            "side": side,
            "vwap": vwap,
            "trade_count": self._trade_count,
        }

    def _calculate_vwap(self) -> float:
        """Calculate Volume Weighted Average Price."""
        if not self._trades:
            return 0.0

        total_value = sum(t["price"] * t["size"] for t in self._trades)
        total_volume = sum(t["size"] for t in self._trades)

        if total_volume == 0:
            return 0.0

        return total_value / total_volume

    def process_orderbook(
        self,
        best_bid: float,
        bid_qty: float,
        best_ask: float,
        ask_qty: float,
        timestamp: float | None = None
    ) -> dict[str, Any]:
        """Process an orderbook update.

        Args:
            best_bid: Best bid price
            bid_qty: Quantity at best bid
            best_ask: Best ask price
            ask_qty: Quantity at best ask
            timestamp: Optional timestamp

        Returns:
            Dict with orderbook features
        """
        timestamp = timestamp or time.time()

        # Calculate spread and mid
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2

        self._spreads.append(spread)
        self._last_mid = mid_price
        self._last_spread = spread
        self._last_bid_depth = bid_qty
        self._last_ask_depth = ask_qty

        # Update OFI
        self.ofi_calculator.update(best_bid, bid_qty, best_ask, ask_qty)
        ofi = self.ofi_calculator.get_ofi()

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "mid_price": mid_price,
            "ofi": ofi,
            "bid_depth": bid_qty,
            "ask_depth": ask_qty,
        }

    def get_features(self) -> dict[str, Any]:
        """Get current feature snapshot.

        Returns:
            Dict with all calculated features
        """
        vwap = self._calculate_vwap()
        avg_spread = sum(self._spreads) / len(self._spreads) if self._spreads else 0.0

        # Liquidity score
        liquidity_score = self.config.default_liquidity_score
        if self._last_spread is not None and self._last_bid_depth is not None:
            liquidity_score = self.ofi_calculator.get_liquidity_score(
                spread=self._last_spread,
                bid_depth=self._last_bid_depth,
                ask_depth=self._last_ask_depth or 0,
                avg_spread=avg_spread or self._last_spread,
                avg_depth=self.config.depth_baseline,
            )

        return {
            "vwap": vwap,
            "trade_count": self._trade_count,
            "buy_volume": self._buy_volume,
            "sell_volume": self._sell_volume,
            "trade_imbalance": self.get_trade_imbalance(),
            "ofi": self.ofi_calculator.get_ofi(),
            "spread": self._last_spread or 0.0,
            "avg_spread": avg_spread,
            "mid_price": self._last_mid or 0.0,
            "liquidity_score": liquidity_score,
        }

    def get_trade_imbalance(self) -> float:
        """Get buy/sell trade imbalance.

        Returns:
            Imbalance ratio: positive = more buys, negative = more sells
            Range: -1.0 to 1.0
        """
        total = self._buy_volume + self._sell_volume
        if total == 0:
            return 0.0

        return (self._buy_volume - self._sell_volume) / total

    def reset(self) -> None:
        """Reset processor state."""
        self._trades.clear()
        self._trade_count = 0
        self._buy_volume = 0.0
        self._sell_volume = 0.0
        self._spreads.clear()
        self._last_mid = None
        self._last_spread = None
        self._last_bid_depth = None
        self._last_ask_depth = None
        self.ofi_calculator.reset()
