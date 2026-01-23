"""Position manager for managing multiple positions."""
import uuid
import logging
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Deque

from shared.models.position import Position, PositionState, PositionSide
from .exit_checker import ExitChecker, ExitConfig
from .monitor import PositionMonitor

logger = logging.getLogger(__name__)


class PositionManager:
    """Manages multiple positions with exit condition monitoring.

    Features:
        - Position lifecycle management (open, update, close)
        - Integrated exit condition checking
        - Position history tracking
        - Callbacks for position events
        - Optional order executor integration
    """

    DEFAULT_MAX_CLOSED_HISTORY = 10000

    def __init__(
        self,
        exit_config: ExitConfig,
        on_position_opened: Optional[Callable[[Position], None]] = None,
        on_position_closed: Optional[Callable[[Position], None]] = None,
        on_exit_triggered: Optional[Callable[[Position, str], None]] = None,
        order_executor: Optional[Any] = None,
        max_closed_history: int = DEFAULT_MAX_CLOSED_HISTORY,
    ):
        """Initialize position manager.

        Args:
            exit_config: Exit condition configuration
            on_position_opened: Callback when position is opened
            on_position_closed: Callback when position is closed
            on_exit_triggered: Callback when exit condition triggers
            order_executor: Optional order executor for trade execution
            max_closed_history: Maximum number of closed positions to keep in memory
        """
        self.exit_config = exit_config
        self.exit_checker = ExitChecker(exit_config)
        self.order_executor = order_executor
        self.max_closed_history = max_closed_history

        # Callbacks
        self.on_position_opened = on_position_opened
        self.on_position_closed = on_position_closed
        self.on_exit_triggered = on_exit_triggered

        # Position storage
        self.positions: Dict[str, Position] = {}
        self._closed_positions: Deque[Position] = deque(maxlen=max_closed_history)

        # Monitor
        self.monitor = PositionMonitor(
            on_exit_triggered=self._handle_exit_triggered
        )

    @property
    def closed_positions(self) -> List[Position]:
        """Get closed positions (backward compatible list).

        Returns:
            List of closed positions (most recent first)
        """
        return list(self._closed_positions)

    async def open_position(
        self,
        code: str,
        name: str,
        side: PositionSide,
        entry_price: float,
        quantity: int,
        strategy: str,
        position_id: Optional[str] = None,
    ) -> Position:
        """Open a new position.

        Args:
            code: Stock code
            name: Stock name
            side: Position side (LONG/SHORT)
            entry_price: Entry price
            quantity: Quantity
            strategy: Strategy name
            position_id: Optional custom ID

        Returns:
            Created position
        """
        pos_id = position_id or f"POS-{uuid.uuid4().hex[:8].upper()}"

        position = Position(
            id=pos_id,
            code=code,
            name=name,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=datetime.now(),
            strategy=strategy,
            state=PositionState.SURVIVAL,
        )

        self.positions[pos_id] = position
        self.monitor.add_position(position)

        logger.info(
            f"Position opened: {pos_id} {side.value} {code} "
            f"x{quantity} @ {entry_price}"
        )

        if self.on_position_opened:
            self.on_position_opened(position)

        return position

    async def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str,
    ) -> Optional[Position]:
        """Close a position.

        Args:
            position_id: Position ID to close
            exit_price: Exit price
            reason: Exit reason

        Returns:
            Closed position or None if not found
        """
        position = self.positions.pop(position_id, None)
        if not position:
            logger.warning(f"Position not found: {position_id}")
            return None

        # Update position with exit info
        position.exit_price = exit_price
        position.exit_time = datetime.now()
        position.exit_reason = reason
        position.exit_triggered = True
        position.current_price = exit_price

        # Remove from monitor
        self.monitor.remove_position(position_id)

        # Add to history (deque automatically handles maxlen)
        self._closed_positions.append(position)

        # Calculate P&L
        pnl = position.unrealized_pnl
        pnl_pct = position.profit_pct

        logger.info(
            f"Position closed: {position_id} @ {exit_price} "
            f"PnL: {pnl:,.0f} ({pnl_pct:+.2f}%) reason: {reason}"
        )

        if self.on_position_closed:
            self.on_position_closed(position)

        return position

    def _handle_exit_triggered(self, position: Position, reason: str) -> None:
        """Handle exit condition triggered.

        Args:
            position: Position with triggered exit
            reason: Exit reason
        """
        logger.info(f"Exit triggered for {position.id}: {reason}")

        if self.on_exit_triggered:
            self.on_exit_triggered(position, reason)

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID."""
        return self.positions.get(position_id)

    def get_positions_by_code(self, code: str) -> List[Position]:
        """Get all positions for a stock code."""
        return [p for p in self.positions.values() if p.code == code]

    def get_positions_by_strategy(self, strategy: str) -> List[Position]:
        """Get all positions for a strategy."""
        return [p for p in self.positions.values() if p.strategy == strategy]

    def update_price(self, code: str, price: float) -> None:
        """Update price for all positions with given code.

        Also checks exit conditions.

        Args:
            code: Stock code
            price: Current price
        """
        self.monitor.update_price(code, price)

        # Check exit conditions
        for position in self.get_positions_by_code(code):
            should_exit, reason = self.exit_checker.check(position)
            if should_exit and not position.exit_triggered:
                position.exit_triggered = True
                position.exit_reason = reason
                self._handle_exit_triggered(position, reason)

    def update_prices(self, prices: Dict[str, float]) -> None:
        """Batch update prices."""
        for code, price in prices.items():
            self.update_price(code, price)

    async def start_monitoring(self) -> None:
        """Start position monitoring."""
        await self.monitor.start()

    async def stop_monitoring(self) -> None:
        """Stop position monitoring."""
        await self.monitor.stop()

    def get_summary(self) -> Dict:
        """Get manager summary."""
        total_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        closed_pnl = sum(
            (p.exit_price - p.entry_price) * p.quantity
            if p.side == PositionSide.LONG
            else (p.entry_price - p.exit_price) * p.quantity
            for p in self.closed_positions
            if p.exit_price
        )

        return {
            "open_positions": len(self.positions),
            "closed_positions": len(self.closed_positions),
            "total_unrealized_pnl": total_pnl,
            "total_realized_pnl": closed_pnl,
            "positions": [
                {
                    "id": p.id,
                    "code": p.code,
                    "side": p.side.value,
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "profit_pct": p.profit_pct,
                    "state": p.state.value,
                }
                for p in self.positions.values()
            ],
        }

    async def restore_positions(self, positions: List[Position]) -> None:
        """Restore positions from a list.

        Used for recovering positions after restart.

        Args:
            positions: List of positions to restore
        """
        for position in positions:
            self.positions[position.id] = position
            self.monitor.add_position(position)
            logger.info(f"Position restored: {position.id}")

    async def close_all_positions(
        self,
        prices: Dict[str, float],
        reason: str,
    ) -> List[Position]:
        """Close all open positions.

        Args:
            prices: Dict mapping code to current price
            reason: Exit reason for all positions

        Returns:
            List of closed positions
        """
        closed = []
        position_ids = list(self.positions.keys())

        for pos_id in position_ids:
            position = self.positions.get(pos_id)
            if position and position.code in prices:
                exit_price = prices[position.code]
                closed_pos = await self.close_position(pos_id, exit_price, reason)
                if closed_pos:
                    closed.append(closed_pos)

        return closed
