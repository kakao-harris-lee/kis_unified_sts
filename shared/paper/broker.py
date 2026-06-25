"""Virtual broker for paper trading."""
import logging
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from shared.execution.slippage_control import OrderBookSnapshot
    from shared.execution.slippage_model import SlippageModel
    from shared.paper.config import PaperTradingConfig

from .models import (
    InsufficientBalanceError,
    OrderSide,
    OrderType,
    PositionSide,
    TradeRecord,
    VirtualOrder,
    VirtualPosition,
)

logger = logging.getLogger(__name__)


class VirtualBroker:
    """Simulated broker for paper trading.

    Features:
    - Instant market order fills
    - Position tracking
    - P&L calculation
    - Commission simulation
    - Price freshness guards (when config supplied with max_price_staleness_seconds > 0)
    """

    def __init__(
        self,
        initial_balance: float = 10000000,
        commission_rate: float = 0.00015,  # 0.015%
        slippage_rate: float = 0.0001,     # 0.01%
        slippage_model: Optional["SlippageModel"] = None,
        config: Optional["PaperTradingConfig"] = None,
    ):
        # If a config is provided, its values take precedence
        if config is not None:
            from shared.paper.config import PaperTradingConfig as _PTC
            assert isinstance(config, _PTC), "VirtualBroker config must be a PaperTradingConfig"
            initial_balance = config.initial_balance
            commission_rate = config.commission_rate
            slippage_rate = config.slippage_rate

        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.slippage_model = slippage_model
        self.config = config  # May be None for legacy callers

        self.positions: Dict[str, VirtualPosition] = {}
        self.orders: List[VirtualOrder] = []
        self.trades: List[TradeRecord] = []

        # Callbacks
        self.on_fill: Optional[Callable] = None
        self.on_trade_close: Optional[Callable] = None

        # Price observation history for deviation guard (maxlen caps memory usage)
        self._price_history: dict[str, deque[tuple[datetime, float]]] = defaultdict(
            lambda: deque(maxlen=256)
        )

    def record_price_observation(
        self, symbol: str, price: float, ts: datetime
    ) -> None:
        """Record observed market price for use as deviation-guard reference.

        Called by the orchestrator from its tick handler per symbol.
        Only the last ``reference_price_lookback_minutes`` window of observations
        is considered at guard time.
        """
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        self._price_history[symbol].append((ts, price))

    def _check_price_deviation(
        self, symbol: str, proposed_price: float, now: datetime
    ) -> bool:
        """Return True if proposed_price is within deviation threshold, else False.

        - Returns True when deviation check is disabled (pct<=0 or lookback<=0)
        - Returns True when there is no reference data in the lookback window
        """
        if self.config is None:
            return True
        if (
            self.config.max_price_deviation_pct <= 0
            or self.config.reference_price_lookback_minutes <= 0
        ):
            return True
        history = self._price_history.get(symbol)
        if not history:
            return True
        cutoff = now - timedelta(
            minutes=self.config.reference_price_lookback_minutes
        )
        recent_prices = [p for ts, p in history if ts >= cutoff]
        if not recent_prices:
            return True
        ref = median(recent_prices)
        if ref <= 0:
            return True
        deviation = abs(proposed_price - ref) / ref
        return deviation <= self.config.max_price_deviation_pct

    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float = 0.0,
        order_type: OrderType = OrderType.MARKET,
        market_price: float | None = None,
        orderbook: Optional["OrderBookSnapshot"] = None,
        price_source_time: Optional[datetime] = None,
    ) -> VirtualOrder:
        """Submit and execute order.

        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            quantity: Order quantity
            price: Order price (used as market price for MARKET orders, limit price for LIMIT orders)
            order_type: Order type (MARKET/LIMIT)
            market_price: Current market price (used for LIMIT order execution check)
            orderbook: Order book snapshot for realistic slippage calculation
            price_source_time: When the market price was sampled. Required (and must be
                fresh) when ``config.max_price_staleness_seconds > 0``; otherwise the
                order is rejected with an appropriate rejection_reason.

        Returns:
            VirtualOrder — filled or rejected (check ``order.filled`` and
            ``order.rejection_reason``).
        """
        # ── Price freshness guard ──────────────────────────────────────────────
        if self.config is not None and self.config.max_price_staleness_seconds > 0:
            effective_price = price if price else (market_price or 0.0)
            if price_source_time is None:
                order = VirtualOrder(
                    order_id=f"VO-{uuid.uuid4().hex[:8].upper()}",
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=effective_price,
                    timestamp=datetime.now(),
                )
                order.filled = False
                order.rejection_reason = "missing_price_source_time"
                logger.warning(
                    "Paper order rejected (no price_source_time): %s %s",
                    symbol, side.value,
                )
                self.orders.append(order)
                return order

            now = datetime.now(UTC)
            pst = price_source_time
            if pst.tzinfo is None:
                # Treat naive timestamps as local time and convert to UTC.
                # Using .replace(tzinfo=...) would silently mislabel e.g. KST as UTC
                # and make the age computation wrong by the UTC offset.
                pst = pst.astimezone(UTC)
            age_seconds = (now - pst).total_seconds()
            if age_seconds > self.config.max_price_staleness_seconds:
                order = VirtualOrder(
                    order_id=f"VO-{uuid.uuid4().hex[:8].upper()}",
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=effective_price,
                    timestamp=datetime.now(),
                )
                order.filled = False
                order.rejection_reason = "stale_price"
                logger.warning(
                    "Paper order rejected (stale price, age=%.1fs): %s @ %s",
                    age_seconds, symbol, market_price,
                )
                self.orders.append(order)
                return order
        # ── End freshness guard ────────────────────────────────────────────────

        # ── Price deviation guard ─────────────────────────────────────────────
        if self.config is not None and market_price is not None:
            now_dev = datetime.now(UTC)
            if not self._check_price_deviation(symbol, market_price, now_dev):
                effective_price = price if price else (market_price or 0.0)
                order = VirtualOrder(
                    order_id=f"VO-{uuid.uuid4().hex[:8].upper()}",
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=effective_price,
                    timestamp=datetime.now(),
                )
                order.filled = False
                order.rejection_reason = "price_deviation"
                logger.warning(
                    "Paper order rejected (price deviation): %s proposed=%.2f",
                    symbol, market_price,
                )
                self.orders.append(order)
                return order
        # ── End deviation guard ───────────────────────────────────────────────

        # Normalise: callers may pass market_price without setting price (e.g.
        # when price_source_time is also supplied). For MARKET orders, use
        # market_price as the execution price when price is absent/zero.
        if order_type == OrderType.MARKET and not price and market_price:
            price = market_price

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
            await self._execute_market_order(order, price, orderbook)
        elif order_type == OrderType.LIMIT:
            await self._execute_limit_order(order, market_price)

        self.orders.append(order)
        return order

    async def _execute_market_order(
        self,
        order: VirtualOrder,
        market_price: float,
        orderbook: Optional["OrderBookSnapshot"] = None,
    ) -> None:
        """Execute market order with slippage.

        Args:
            order: Virtual order to execute
            market_price: Current market price
            orderbook: Order book snapshot for realistic slippage calculation
        """
        # Calculate slippage - use slippage model if available, otherwise fall back to simple rate
        if self.slippage_model and self.slippage_model.config.enabled:
            # Use slippage model for realistic fill price calculation
            order_size = float(order.quantity)

            # Extract orderbook data if available, otherwise use defaults
            if orderbook is not None:
                current_spread = orderbook.spread
                is_buy = (order.side == OrderSide.BUY)
                available_depth = orderbook.available_qty(is_buy)
            else:
                # Fall back to configured default values when orderbook is not provided
                current_spread = self.slippage_model.config.default_spread
                available_depth = self.slippage_model.config.default_depth

            slippage_bps = self.slippage_model.calculate_slippage(
                order_size=order_size,
                current_spread=current_spread,
                available_depth=available_depth,
                timestamp=order.timestamp,
            )

            # Convert bps to rate (1 bps = 0.01% = 0.0001)
            slippage_rate = slippage_bps / 10000.0
        else:
            # Fall back to simple slippage rate
            slippage_rate = self.slippage_rate

        # Apply slippage based on order side
        if order.side == OrderSide.BUY:
            fill_price = market_price * (1 + slippage_rate)
            # Check sufficient balance for BUY orders
            estimated_commission = fill_price * order.quantity * self.commission_rate
            required_balance = fill_price * order.quantity + estimated_commission
            if self.balance < required_balance:
                raise InsufficientBalanceError(
                    f"Insufficient balance: need {required_balance:.2f}, have {self.balance:.2f}"
                )
        else:
            fill_price = market_price * (1 - slippage_rate)

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


# Backwards-compat alias — code that imported PaperBroker still works.
PaperBroker = VirtualBroker
