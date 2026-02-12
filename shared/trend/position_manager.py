"""Trend position manager with ATR-based trailing stops."""
import logging
import time
from dataclasses import dataclass
from typing import Optional, List
import uuid

from .config import TrendConfig

logger = logging.getLogger(__name__)


@dataclass
class TrendPosition:
    """A position managed by TrendPositionManager."""
    id: str
    direction: str          # "LONG" or "SHORT"
    entry_price: float
    stop_loss: float
    take_profit: float
    size: float
    entry_time: float

    # Mutable state
    is_open: bool = True
    exit_price: Optional[float] = None
    exit_time: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None

    # Tracking
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None


class TrendPositionManager:
    """Manage trend following positions with ATR-based stops.

    Features:
    - ATR-based initial stop loss
    - ATR-based take profit target
    - Trailing stop that follows price
    - Position tracking and P&L calculation
    """

    def __init__(self, config: TrendConfig):
        self.config = config
        self._positions: List[TrendPosition] = []

    def open_position(
        self,
        direction: str,
        entry_price: float,
        atr: float,
        size: float,
        timestamp: Optional[float] = None
    ) -> TrendPosition:
        """Open a new position with ATR-based stops.

        Args:
            direction: "LONG" or "SHORT"
            entry_price: Entry price
            atr: Current ATR value
            size: Position size
            timestamp: Optional timestamp

        Returns:
            TrendPosition object
        """
        timestamp = timestamp or time.time()

        if direction == "LONG":
            stop_loss = entry_price - (atr * self.config.atr_stop_multiplier)
            take_profit = entry_price + (atr * self.config.atr_target_multiplier)
        else:
            stop_loss = entry_price + (atr * self.config.atr_stop_multiplier)
            take_profit = entry_price - (atr * self.config.atr_target_multiplier)

        position = TrendPosition(
            id=str(uuid.uuid4())[:8],
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            size=size,
            entry_time=timestamp,
            highest_price=entry_price,
            lowest_price=entry_price,
        )

        self._positions.append(position)

        logger.info(
            f"Opened {direction} position @ {entry_price}, "
            f"SL={stop_loss:.2f}, TP={take_profit:.2f}"
        )

        return position

    def update_trailing_stop(
        self,
        position: TrendPosition,
        current_price: float,
        atr: float
    ) -> None:
        """Update trailing stop based on current price.

        The stop trails the price but never moves against the position.

        Args:
            position: Position to update
            current_price: Current market price
            atr: Current ATR value
        """
        if not position.is_open:
            return

        if position.direction == "LONG":
            # Track highest price
            if position.highest_price is None or current_price > position.highest_price:
                position.highest_price = current_price

            # Calculate new stop
            new_stop = current_price - (atr * self.config.atr_stop_multiplier)

            # Only move stop up, never down
            if new_stop > position.stop_loss:
                position.stop_loss = new_stop
                logger.debug(f"Trailing stop updated to {new_stop:.2f}")

        else:  # SHORT
            # Track lowest price
            if position.lowest_price is None or current_price < position.lowest_price:
                position.lowest_price = current_price

            # Calculate new stop
            new_stop = current_price + (atr * self.config.atr_stop_multiplier)

            # Only move stop down, never up
            if new_stop < position.stop_loss:
                position.stop_loss = new_stop
                logger.debug(f"Trailing stop updated to {new_stop:.2f}")

    def is_stop_hit(self, position: TrendPosition, current_price: float) -> bool:
        """Check if stop loss is hit.

        Args:
            position: Position to check
            current_price: Current market price

        Returns:
            True if stop is hit
        """
        if position.direction == "LONG":
            return current_price <= position.stop_loss
        else:
            return current_price >= position.stop_loss

    def is_target_hit(self, position: TrendPosition, current_price: float) -> bool:
        """Check if take profit target is hit.

        Args:
            position: Position to check
            current_price: Current market price

        Returns:
            True if target is hit
        """
        if position.direction == "LONG":
            return current_price >= position.take_profit
        else:
            return current_price <= position.take_profit

    def close_position(
        self,
        position: TrendPosition,
        exit_price: float,
        reason: str,
        timestamp: Optional[float] = None
    ) -> None:
        """Close a position and calculate P&L.

        Args:
            position: Position to close
            exit_price: Exit price
            reason: Exit reason (e.g., "STOP_HIT", "TARGET_HIT", "MANUAL")
            timestamp: Optional timestamp
        """
        if not position.is_open:
            return

        timestamp = timestamp or time.time()

        position.is_open = False
        position.exit_price = exit_price
        position.exit_time = timestamp
        position.exit_reason = reason

        # Calculate P&L
        if position.direction == "LONG":
            position.pnl = (exit_price - position.entry_price) * position.size
        else:
            position.pnl = (position.entry_price - exit_price) * position.size

        logger.info(
            f"Closed {position.direction} position @ {exit_price}, "
            f"reason={reason}, PnL={position.pnl:.2f}"
        )

    def get_open_positions(self) -> List[TrendPosition]:
        """Get all open positions."""
        return [p for p in self._positions if p.is_open]

    def get_all_positions(self) -> List[TrendPosition]:
        """Get all positions (open and closed)."""
        return self._positions.copy()

    def clear_closed(self) -> None:
        """Remove closed positions from memory."""
        self._positions = [p for p in self._positions if p.is_open]
