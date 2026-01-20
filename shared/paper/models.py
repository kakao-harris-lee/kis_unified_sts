"""Paper trading models."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass
class VirtualOrder:
    """Virtual order for paper trading."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float]
    timestamp: datetime
    filled: bool = False
    fill_price: Optional[float] = None
    fill_time: Optional[datetime] = None

    @property
    def is_market_order(self) -> bool:
        return self.order_type == OrderType.MARKET


@dataclass
class TradeRecord:
    """Completed trade record."""
    trade_id: str
    symbol: str
    side: OrderSide
    entry_price: float
    exit_price: float
    quantity: int
    entry_time: datetime
    exit_time: datetime
    strategy: str = ""
    commission: float = 0.0

    @property
    def pnl(self) -> float:
        """Calculate realized P&L."""
        if self.side == OrderSide.BUY:
            return (self.exit_price - self.entry_price) * self.quantity - self.commission
        else:
            return (self.entry_price - self.exit_price) * self.quantity - self.commission

    @property
    def pnl_pct(self) -> float:
        """Calculate P&L percentage."""
        return (self.pnl / (self.entry_price * self.quantity)) * 100


@dataclass
class VirtualPosition:
    """Current virtual position."""
    symbol: str
    side: PositionSide
    quantity: int
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0

    @property
    def unrealized_pnl(self) -> float:
        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) * self.quantity
        elif self.side == PositionSide.SHORT:
            return (self.entry_price - self.current_price) * self.quantity
        return 0.0

    def update_price(self, price: float) -> None:
        self.current_price = price
        self.highest_price = max(self.highest_price, price)
        self.lowest_price = min(self.lowest_price, price) if self.lowest_price > 0 else price
