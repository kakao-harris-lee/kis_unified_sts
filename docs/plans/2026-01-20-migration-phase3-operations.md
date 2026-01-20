# Phase 3: Operations Infrastructure Migration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate Paper Trading, Regime Detection, and Monitoring infrastructure.

**Architecture:** Event-driven with async/await, Redis Streams for messaging, Prometheus for metrics.

**Tech Stack:** Python 3.11+, asyncio, redis, prometheus_client, aiohttp

---

## Overview

| # | Component | Source | Lines | Description |
|---|-----------|--------|-------|-------------|
| 1 | VirtualBroker | kospi_mini_sts | ~300 | Simulated order execution |
| 2 | PaperTradingEngine | kospi_mini_sts | ~400 | Paper trading orchestration |
| 3 | StockRegimeDetector | quant_moment_sts | ~250 | Market regime classification |
| 4 | StrategyRouter | quant_moment_sts | ~200 | Dynamic strategy selection |
| 5 | AlertService | kospi_mini_sts | ~200 | Telegram/email alerts |
| 6 | AnomalyDetector | kospi_mini_sts | ~300 | Data quality monitoring |
| 7 | HealthChecker | kospi_mini_sts | ~200 | System health checks |

**Estimated Tasks:** 18 bite-sized tasks

---

## Task 1: VirtualBroker - Models

**Files:**
- Create: `shared/paper/models.py`
- Test: `tests/unit/paper/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/paper/test_models.py
"""Test paper trading models."""
import pytest
from datetime import datetime


def test_virtual_order_creation():
    """Test VirtualOrder model."""
    from shared.paper.models import VirtualOrder, OrderSide, OrderType

    order = VirtualOrder(
        order_id="ORD-001",
        symbol="005930",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        price=None,
        timestamp=datetime.now(),
    )

    assert order.symbol == "005930"
    assert order.side == OrderSide.BUY
    assert order.is_market_order


def test_trade_record_pnl():
    """Test TradeRecord P&L calculation."""
    from shared.paper.models import TradeRecord, OrderSide

    record = TradeRecord(
        trade_id="TRD-001",
        symbol="005930",
        side=OrderSide.BUY,
        entry_price=58000,
        exit_price=59000,
        quantity=10,
        entry_time=datetime.now(),
        exit_time=datetime.now(),
    )

    assert record.pnl == 10000  # (59000 - 58000) * 10
    assert record.pnl_pct == pytest.approx(1.72, rel=0.01)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/paper/test_models.py -v`
Expected: FAIL with "No module named 'shared.paper'"

**Step 3: Write minimal implementation**

```python
# shared/paper/__init__.py
"""Paper trading module."""

# shared/paper/models.py
"""Paper trading models."""
from dataclasses import dataclass, field
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/paper/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/paper/ tests/unit/paper/
git commit -m "feat(paper): add paper trading models"
```

---

## Task 2: VirtualBroker - Core Implementation

**Files:**
- Create: `shared/paper/broker.py`
- Test: `tests/unit/paper/test_broker.py`

**Step 1: Write the failing test**

```python
# tests/unit/paper/test_broker.py
"""Test VirtualBroker."""
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_broker_buy_order():
    """Test market buy order execution."""
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide

    broker = VirtualBroker(initial_balance=1000000)

    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        price=58000  # Simulated market price
    )

    assert order.filled is True
    assert broker.get_position("005930") is not None
    assert broker.balance < 1000000  # Reduced by purchase


@pytest.mark.asyncio
async def test_broker_position_tracking():
    """Test position tracking."""
    from shared.paper.broker import VirtualBroker
    from shared.paper.models import OrderSide

    broker = VirtualBroker(initial_balance=1000000)

    # Buy
    await broker.submit_order("005930", OrderSide.BUY, 10, 58000)

    position = broker.get_position("005930")
    assert position.quantity == 10

    # Sell half
    await broker.submit_order("005930", OrderSide.SELL, 5, 59000)

    position = broker.get_position("005930")
    assert position.quantity == 5
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/paper/test_broker.py -v`
Expected: FAIL with "cannot import name 'VirtualBroker'"

**Step 3: Write minimal implementation**

```python
# shared/paper/broker.py
"""Virtual broker for paper trading."""
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable

from .models import (
    VirtualOrder,
    VirtualPosition,
    TradeRecord,
    OrderSide,
    OrderType,
    PositionSide,
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
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate

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
    ) -> VirtualOrder:
        """Submit and execute order."""
        order_id = f"VO-{uuid.uuid4().hex[:8].upper()}"

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

        self.orders.append(order)
        return order

    async def _execute_market_order(self, order: VirtualOrder, market_price: float) -> None:
        """Execute market order with slippage."""
        # Apply slippage
        if order.side == OrderSide.BUY:
            fill_price = market_price * (1 + self.slippage_rate)
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
                    # Close short
                    await self._close_position(symbol, fill_price, commission)

        else:  # SELL
            if position and position.side == PositionSide.LONG:
                if order.quantity >= position.quantity:
                    # Full close
                    await self._close_position(symbol, fill_price, commission)
                else:
                    # Partial close
                    position.quantity -= order.quantity

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
        """Calculate total equity (balance + unrealized P&L)."""
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        return self.balance + unrealized

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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/paper/test_broker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/paper/broker.py tests/unit/paper/test_broker.py
git commit -m "feat(paper): add VirtualBroker with position tracking"
```

---

## Task 3-6: PaperTradingEngine

- Task 3: PaperTradingConfig
- Task 4: Redis Streams integration
- Task 5: Strategy execution loop
- Task 6: Equity curve tracking

---

## Task 7-10: Regime Detection

- Task 7: RegimeState enum and models
- Task 8: StockRegimeDetector (BULL, BEAR, SIDEWAYS)
- Task 9: RegimeCache (Redis-backed)
- Task 10: StrategyRouter (regime → strategy mapping)

---

## Task 11-14: Monitoring

- Task 11: AlertConfig and models
- Task 12: TelegramAlertService
- Task 13: AnomalyDetector (data gaps, outliers)
- Task 14: HealthChecker (component status)

---

## Task 15-18: Integration

- Task 15: CLI commands for paper trading
- Task 16: Prometheus metrics exporter
- Task 17: Grafana dashboard templates
- Task 18: Integration tests

---

## Dependencies

```
# Add to pyproject.toml
prometheus_client>=0.19.0
```

---

**Created:** 2026-01-20
