"""Position monitor for real-time position tracking."""
import asyncio
import logging
from typing import Dict, Optional, Callable, List

from shared.models.position import Position

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Monitors positions and triggers exit conditions.

    Features:
        - Real-time price updates
        - State machine transitions (SURVIVAL -> BREAKEVEN -> MAXIMIZE)
        - Exit condition callbacks
        - Async monitoring loop
    """

    def __init__(
        self,
        check_interval: float = 1.0,
        on_exit_triggered: Optional[Callable[[Position, str], None]] = None,
    ):
        """Initialize position monitor.

        Args:
            check_interval: Seconds between exit condition checks
            on_exit_triggered: Callback when exit condition is met
        """
        self.check_interval = check_interval
        self.on_exit_triggered = on_exit_triggered

        self.positions: Dict[str, Position] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def add_position(self, position: Position) -> None:
        """Add position to monitor.

        Args:
            position: Position to monitor
        """
        self.positions[position.id] = position
        logger.info(f"Added position to monitor: {position.id} ({position.code})")

    def remove_position(self, position_id: str) -> Optional[Position]:
        """Remove position from monitor.

        Args:
            position_id: Position ID to remove

        Returns:
            Removed position or None
        """
        position = self.positions.pop(position_id, None)
        if position:
            logger.info(f"Removed position from monitor: {position_id}")
        return position

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID."""
        return self.positions.get(position_id)

    def get_positions_by_code(self, code: str) -> List[Position]:
        """Get all positions for a stock code."""
        return [p for p in self.positions.values() if p.code == code]

    def update_price(self, code: str, price: float) -> None:
        """Update price for all positions with given code.

        Args:
            code: Stock code
            price: Current price
        """
        for position in self.positions.values():
            if position.code == code:
                position.update_price(price)

    def update_prices(self, prices: Dict[str, float]) -> None:
        """Batch update prices.

        Args:
            prices: Dict of code -> price
        """
        for code, price in prices.items():
            self.update_price(code, price)

    async def start(self) -> None:
        """Start monitoring loop."""
        if self._running:
            logger.warning("Monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Position monitor started")

    async def stop(self) -> None:
        """Stop monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Position monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_all_positions()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(self.check_interval)

    async def _check_all_positions(self) -> None:
        """Check exit conditions for all positions."""
        for position in list(self.positions.values()):
            if position.exit_triggered:
                continue

            should_exit, reason = self._check_exit_condition(position)
            if should_exit:
                position.exit_triggered = True
                position.exit_reason = reason
                logger.info(f"Exit triggered for {position.id}: {reason}")

                if self.on_exit_triggered:
                    self.on_exit_triggered(position, reason)

    def _check_exit_condition(self, _position: Position) -> tuple[bool, str]:
        """Check if position should exit.

        This is a placeholder - actual logic delegated to ExitChecker.

        Args:
            position: Position to check

        Returns:
            (should_exit, reason) tuple
        """
        # Default implementation - no exit
        # Real exit logic is in ExitChecker class (Task 12)
        return False, ""

    def get_summary(self) -> Dict:
        """Get monitor summary."""
        total_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        return {
            "position_count": len(self.positions),
            "total_unrealized_pnl": total_pnl,
            "running": self._running,
            "positions": [
                {
                    "id": p.id,
                    "code": p.code,
                    "side": p.side.value,
                    "profit_pct": p.profit_pct,
                    "state": p.state.value,
                }
                for p in self.positions.values()
            ],
        }
