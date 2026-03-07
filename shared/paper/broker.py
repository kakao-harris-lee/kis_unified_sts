"""Virtual broker for paper trading."""
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from shared.execution.slippage_model import SlippageModel

from .models import (
    VirtualOrder,
    VirtualPosition,
    TradeRecord,
    OrderSide,
    OrderType,
    PositionSide,
    InsufficientBalanceError,
)

logger = logging.getLogger(__name__)


class VirtualBroker:
    """Simulated broker for paper trading.

    Features:
    - Instant market order fills
    - Position tracking
    - P&L calculation
    - Commission simulation
    """

    def __init__(
        self,
        initial_balance: float = 10000000,
        commission_rate: float = 0.00015,  # 0.015%
        slippage_rate: float = 0.0001,     # 0.01%
        slippage_model: Optional["SlippageModel"] = None,
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.slippage_model = slippage_model

        self.positions: Dict[str, VirtualPosition] = {}
        self.orders: List[VirtualOrder] = []
        self.trades: List[TradeRecord] = []

        # Callbacks
        self.on_fill: Optional[Callable] = None
        self.on_trade_close: Optional[Callable] = None

    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float,
        order_type: OrderType = OrderType.MARKET,
        market_price: float | None = None,
    ) -> VirtualOrder:
        """Submit and execute order."""
        order_id = f"VO-{uuid.uuid4().hex[:8].upper()}"

        if order_type == OrderType.LIMIT and price <= 0:
            raise ValueError("Limit order requires positive price")

        order = VirtualOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price if order_type == OrderType.LIMIT else None,
            timestamp=datetime.now(),
        )

        # Simulate execution for market orders
        if order_type == OrderType.MARKET:
            await self._execute_market_order(order, price)
        elif order_type == OrderType.LIMIT:
            await self._execute_limit_order(order, market_price)

        self.orders.append(order)
        return order

    async def _execute_market_order(self, order: VirtualOrder, market_price: float) -> None:
        """Execute market order with slippage."""
        # Apply slippage
        if order.side == OrderSide.BUY:
            fill_price = market_price * (1 + self.slippage_rate)
            # Check sufficient balance for BUY orders
            estimated_commission = fill_price * order.quantity * self.commission_rate
            required_balance = fill_price * order.quantity + estimated_commission
            if self.balance < required_balance:
                raise InsufficientBalanceError(
                    f"Insufficient balance: need {required_balance:.2f}, have {self.balance:.2f}"
                )
        else:
            fill_price = market_price * (1 - self.slippage_rate)

        order.filled = True
        order.fill_price = fill_price
        order.fill_time = datetime.now()

        # Calculate commission
        commission = fill_price * order.quantity * self.commission_rate

        # Update balance
        if order.side == OrderSide.BUY:
            self.balance -= (fill_price * order.quantity + commission)
        else:
            self.balance += (fill_price * order.quantity - commission)

        # Update position
        await self._update_position(order, fill_price, commission)

        logger.info(
            f"Order filled: {order.side.value} {order.symbol} "
            f"x{order.quantity} @ {fill_price:.2f}"
        )

        if self.on_fill:
            await self.on_fill(order)

    async def _execute_limit_order(
        self,
        order: VirtualOrder,
        market_price: float | None,
    ) -> None:
        """Execute marketable limit orders.

        If current market_price does not cross the limit price, the order
        stays open (filled=False).
        """
        if order.price is None:
            return
        if market_price is None or market_price <= 0:
            return

        is_marketable = (
            (order.side == OrderSide.BUY and market_price <= order.price)
            or (order.side == OrderSide.SELL and market_price >= order.price)
        )
        if not is_marketable:
            return

        if order.side == OrderSide.BUY:
            fill_price = min(order.price, market_price)
            estimated_commission = fill_price * order.quantity * self.commission_rate
            required_balance = fill_price * order.quantity + estimated_commission
            if self.balance < required_balance:
                raise InsufficientBalanceError(
                    f"Insufficient balance: need {required_balance:.2f}, have {self.balance:.2f}"
                )
        else:
            fill_price = max(order.price, market_price)

        order.filled = True
        order.fill_price = fill_price
        order.fill_time = datetime.now()

        commission = fill_price * order.quantity * self.commission_rate
        if order.side == OrderSide.BUY:
            self.balance -= (fill_price * order.quantity + commission)
        else:
            self.balance += (fill_price * order.quantity - commission)

        await self._update_position(order, fill_price, commission)

        logger.info(
            f"Limit order filled: {order.side.value} {order.symbol} "
            f"x{order.quantity} @ {fill_price:.2f}"
        )

        if self.on_fill:
            await self.on_fill(order)

    async def _update_position(
        self,
        order: VirtualOrder,
        fill_price: float,
        commission: float
    ) -> None:
        """Update position after fill."""
        symbol = order.symbol
        position = self.positions.get(symbol)

        if order.side == OrderSide.BUY:
            if position is None:
                # New long position
                self.positions[symbol] = VirtualPosition(
                    symbol=symbol,
                    side=PositionSide.LONG,
                    quantity=order.quantity,
                    entry_price=fill_price,
                    entry_time=datetime.now(),
                    current_price=fill_price,
                    highest_price=fill_price,
                )
            else:
                # Add to existing or close short
                if position.side == PositionSide.LONG:
                    # Average up
                    total_qty = position.quantity + order.quantity
                    position.entry_price = (
                        position.entry_price * position.quantity +
                        fill_price * order.quantity
                    ) / total_qty
                    position.quantity = total_qty
                else:
                    # Cover short (partial or full)
                    if order.quantity >= position.quantity:
                        await self._close_position(symbol, fill_price, commission)
                    else:
                        position.quantity -= order.quantity

        else:  # SELL
            if position is None:
                # New short position
                self.positions[symbol] = VirtualPosition(
                    symbol=symbol,
                    side=PositionSide.SHORT,
                    quantity=order.quantity,
                    entry_price=fill_price,
                    entry_time=datetime.now(),
                    current_price=fill_price,
                    highest_price=fill_price,
                )
            elif position.side == PositionSide.LONG:
                if order.quantity >= position.quantity:
                    # Full close
                    await self._close_position(symbol, fill_price, commission)
                else:
                    # Partial close
                    position.quantity -= order.quantity
            else:
                # Add to existing short
                total_qty = position.quantity + order.quantity
                position.entry_price = (
                    position.entry_price * position.quantity +
                    fill_price * order.quantity
                ) / total_qty
                position.quantity = total_qty

    async def _close_position(
        self,
        symbol: str,
        exit_price: float,
        commission: float
    ) -> None:
        """Close position and record trade."""
        position = self.positions.pop(symbol, None)
        if not position:
            return

        trade = TradeRecord(
            trade_id=f"TR-{uuid.uuid4().hex[:8].upper()}",
            symbol=symbol,
            side=OrderSide.BUY if position.side == PositionSide.LONG else OrderSide.SELL,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            entry_time=position.entry_time,
            exit_time=datetime.now(),
            commission=commission,
        )

        self.trades.append(trade)

        logger.info(f"Trade closed: {symbol} PnL={trade.pnl:.2f} ({trade.pnl_pct:.2f}%)")

        if self.on_trade_close:
            await self.on_trade_close(trade)

    def get_position(self, symbol: str) -> Optional[VirtualPosition]:
        """Get current position for symbol."""
        return self.positions.get(symbol)

    def get_equity(self) -> float:
        """Calculate total equity (balance + position market value).

        For long positions, market value is added (we own the asset).
        For short positions, market value is subtracted (liability to return shares).
        """
        position_value = 0.0
        for p in self.positions.values():
            market_value = p.current_price * p.quantity
            if p.side == PositionSide.LONG:
                position_value += market_value
            elif p.side == PositionSide.SHORT:
                position_value -= market_value
        return self.balance + position_value

    def get_summary(self) -> dict:
        """Get account summary."""
        total_pnl = sum(t.pnl for t in self.trades)
        win_trades = [t for t in self.trades if t.pnl > 0]

        return {
            'initial_balance': self.initial_balance,
            'balance': self.balance,
            'equity': self.get_equity(),
            'total_trades': len(self.trades),
            'winning_trades': len(win_trades),
            'win_rate': len(win_trades) / len(self.trades) if self.trades else 0,
            'total_pnl': total_pnl,
            'open_positions': len(self.positions),
        }
