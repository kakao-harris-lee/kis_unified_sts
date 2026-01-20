"""Paper trading engine."""
import logging
from datetime import datetime
from typing import Optional, Dict, List, Callable, Any

from .broker import VirtualBroker
from .config import PaperTradingConfig
from .models import VirtualOrder, OrderSide, TradeRecord

logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """Paper trading orchestration engine.

    Features:
    - Simulated order execution via VirtualBroker
    - Signal processing
    - Equity curve tracking
    - Performance metrics
    """

    def __init__(
        self,
        config: PaperTradingConfig,
        on_trade: Optional[Callable[[TradeRecord], Any]] = None,
    ):
        self.config = config
        self.broker = VirtualBroker(
            initial_balance=config.initial_balance,
            commission_rate=config.commission_rate,
            slippage_rate=config.slippage_rate,
        )
        self.on_trade = on_trade

        self.is_running = False
        self.equity_curve: List[Dict] = []
        self.start_time: Optional[datetime] = None

        # Wire up broker callbacks
        self.broker.on_trade_close = self._on_trade_closed

    async def start(self) -> None:
        """Start the paper trading engine."""
        self.is_running = True
        self.start_time = datetime.now()
        self._record_equity()
        logger.info("Paper trading engine started")

    async def stop(self) -> None:
        """Stop the paper trading engine."""
        self.is_running = False
        self._record_equity()
        logger.info("Paper trading engine stopped")

    async def process_signal(
        self,
        symbol: str,
        side: OrderSide,
        price: float,
        quantity: int,
    ) -> Optional[VirtualOrder]:
        """Process trading signal."""
        # Check position limits
        if not self._can_open_position(symbol, side, price, quantity):
            logger.warning(f"Position limit reached, rejecting signal for {symbol}")
            return None

        order = await self.broker.submit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
        )

        self._record_equity()
        return order

    def _can_open_position(
        self,
        symbol: str,
        side: OrderSide,
        price: float,
        quantity: int,
    ) -> bool:
        """Check if position can be opened within limits."""
        # Check max positions
        if len(self.broker.positions) >= self.config.max_positions:
            if symbol not in self.broker.positions:
                return False

        # Check position size limit
        position_value = price * quantity
        max_position_value = self.broker.get_equity() * self.config.max_position_pct
        if position_value > max_position_value:
            return False

        return True

    async def _on_trade_closed(self, trade: TradeRecord) -> None:
        """Handle trade closure."""
        self._record_equity()
        if self.on_trade:
            result = self.on_trade(trade)
            if hasattr(result, '__await__'):
                await result

    def _record_equity(self) -> None:
        """Record equity point."""
        self.equity_curve.append({
            "timestamp": datetime.now(),
            "equity": self.broker.get_equity(),
            "balance": self.broker.balance,
            "positions": len(self.broker.positions),
        })

    def get_performance(self) -> Dict:
        """Get performance metrics."""
        summary = self.broker.get_summary()

        # Calculate returns
        if self.equity_curve:
            start_equity = self.equity_curve[0]["equity"]
            end_equity = self.equity_curve[-1]["equity"]
            total_return = (end_equity - start_equity) / start_equity * 100
        else:
            total_return = 0.0

        return {
            **summary,
            "total_return_pct": total_return,
            "equity_points": len(self.equity_curve),
        }
