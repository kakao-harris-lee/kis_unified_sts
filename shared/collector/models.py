"""Data collector models."""
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class TickData:
    """Tick data with L5 orderbook support.

    Attributes:
        symbol: Trading symbol (e.g., "101S06" for KOSPI200 Mini)
        timestamp: Unix timestamp with milliseconds
        bid_price_1..5: Best bid prices (level 1-5)
        bid_qty_1..5: Best bid quantities
        ask_price_1..5: Best ask prices (level 1-5)
        ask_qty_1..5: Best ask quantities
        current_price: Last traded price
        tick_volume: Volume of last trade
        cumulative_volume: Day's cumulative volume
    """
    symbol: str
    timestamp: float
    bid_price_1: float
    bid_qty_1: float
    ask_price_1: float
    ask_qty_1: float

    # L5 orderbook (optional)
    bid_price_2: float | None = None
    bid_qty_2: float | None = None
    bid_price_3: float | None = None
    bid_qty_3: float | None = None
    bid_price_4: float | None = None
    bid_qty_4: float | None = None
    bid_price_5: float | None = None
    bid_qty_5: float | None = None

    ask_price_2: float | None = None
    ask_qty_2: float | None = None
    ask_price_3: float | None = None
    ask_qty_3: float | None = None
    ask_price_4: float | None = None
    ask_qty_4: float | None = None
    ask_price_5: float | None = None
    ask_qty_5: float | None = None

    # Trade data
    current_price: float | None = None
    tick_volume: float | None = None
    cumulative_volume: float | None = None

    # OHLC (for day)
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None

    # Futures specific
    open_interest: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        return self.ask_price_1 - self.bid_price_1

    @property
    def mid_price(self) -> float:
        """Calculate mid price."""
        return (self.bid_price_1 + self.ask_price_1) / 2
