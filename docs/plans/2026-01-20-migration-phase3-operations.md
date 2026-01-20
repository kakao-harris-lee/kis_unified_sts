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

## Task 3: PaperTradingConfig

**Files:**
- Create: `shared/paper/config.py`
- Test: `tests/unit/paper/test_config.py`

**Step 1: Write the failing test**

```python
# tests/unit/paper/test_config.py
"""Test paper trading configuration."""
import pytest


def test_paper_config_defaults():
    """Test PaperTradingConfig default values."""
    from shared.paper.config import PaperTradingConfig

    config = PaperTradingConfig()

    assert config.initial_balance == 10_000_000
    assert config.commission_rate == 0.00015
    assert config.slippage_rate == 0.0001


def test_paper_config_from_yaml(tmp_path):
    """Test loading config from YAML."""
    from shared.paper.config import PaperTradingConfig
    import yaml

    config_file = tmp_path / "paper.yaml"
    config_file.write_text(yaml.dump({
        "initial_balance": 5_000_000,
        "commission_rate": 0.0002,
    }))

    config = PaperTradingConfig.from_yaml(str(config_file))
    assert config.initial_balance == 5_000_000
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/paper/test_config.py -v`
Expected: FAIL with "cannot import name 'PaperTradingConfig'"

**Step 3: Write minimal implementation**

```python
# shared/paper/config.py
"""Paper trading configuration."""
from pydantic import BaseModel, Field
from typing import Optional
import yaml


class PaperTradingConfig(BaseModel):
    """Configuration for paper trading engine."""

    initial_balance: float = Field(default=10_000_000, description="Initial capital")
    commission_rate: float = Field(default=0.00015, description="Commission rate (0.015%)")
    slippage_rate: float = Field(default=0.0001, description="Slippage rate (0.01%)")
    max_position_pct: float = Field(default=0.1, description="Max position as % of equity")
    max_positions: int = Field(default=5, description="Maximum concurrent positions")

    # Strategy settings
    strategy_name: Optional[str] = Field(default=None)
    asset_class: str = Field(default="stock")

    # Execution settings
    allow_shorting: bool = Field(default=False)
    market_hours_only: bool = Field(default=True)

    @classmethod
    def from_yaml(cls, path: str) -> "PaperTradingConfig":
        """Load config from YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/paper/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/paper/config.py tests/unit/paper/test_config.py
git commit -m "feat(paper): add PaperTradingConfig"
```

---

## Task 4: PaperTradingEngine - Core

**Files:**
- Create: `shared/paper/engine.py`
- Test: `tests/unit/paper/test_engine.py`

**Step 1: Write the failing test**

```python
# tests/unit/paper/test_engine.py
"""Test PaperTradingEngine."""
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_engine_initialization():
    """Test engine initialization."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig

    config = PaperTradingConfig(initial_balance=5_000_000)
    engine = PaperTradingEngine(config)

    assert engine.broker.balance == 5_000_000
    assert engine.is_running is False


@pytest.mark.asyncio
async def test_engine_start_stop():
    """Test engine lifecycle."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig

    config = PaperTradingConfig()
    engine = PaperTradingEngine(config)

    await engine.start()
    assert engine.is_running is True

    await engine.stop()
    assert engine.is_running is False


@pytest.mark.asyncio
async def test_engine_process_signal():
    """Test signal processing."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig
    from shared.paper.models import OrderSide

    config = PaperTradingConfig()
    engine = PaperTradingEngine(config)

    # Process buy signal
    order = await engine.process_signal(
        symbol="005930",
        side=OrderSide.BUY,
        price=58000,
        quantity=10,
    )

    assert order is not None
    assert order.filled is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/paper/test_engine.py -v`
Expected: FAIL with "cannot import name 'PaperTradingEngine'"

**Step 3: Write minimal implementation**

```python
# shared/paper/engine.py
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
        on_trade: Optional[Callable[[TradeRecord], None]] = None,
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
            await self.on_trade(trade) if callable(self.on_trade) else None

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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/paper/test_engine.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/paper/engine.py tests/unit/paper/test_engine.py
git commit -m "feat(paper): add PaperTradingEngine"
```

---

## Task 5: Regime Detection - Models

**Files:**
- Create: `shared/regime/models.py`
- Create: `shared/regime/__init__.py`
- Test: `tests/unit/regime/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/regime/test_models.py
"""Test regime detection models."""
import pytest
from datetime import datetime


def test_regime_state_enum():
    """Test RegimeState enum."""
    from shared.regime.models import RegimeState

    assert RegimeState.BULL.value == "BULL"
    assert RegimeState.BEAR.value == "BEAR"
    assert RegimeState.SIDEWAYS.value == "SIDEWAYS"


def test_regime_signal_creation():
    """Test RegimeSignal model."""
    from shared.regime.models import RegimeSignal, RegimeState

    signal = RegimeSignal(
        state=RegimeState.BULL,
        confidence=0.85,
        timestamp=datetime.now(),
    )

    assert signal.state == RegimeState.BULL
    assert signal.confidence == 0.85
    assert signal.is_confident  # > 0.7 threshold
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/regime/test_models.py -v`
Expected: FAIL with "No module named 'shared.regime'"

**Step 3: Write minimal implementation**

```python
# shared/regime/__init__.py
"""Regime detection module."""

# shared/regime/models.py
"""Regime detection models."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict


class RegimeState(str, Enum):
    """Market regime states."""
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    UNKNOWN = "UNKNOWN"


@dataclass
class RegimeSignal:
    """Regime detection signal."""
    state: RegimeState
    confidence: float
    timestamp: datetime
    indicators: Optional[Dict] = None

    @property
    def is_confident(self) -> bool:
        """Check if signal has high confidence."""
        return self.confidence >= 0.7


@dataclass
class RegimeConfig:
    """Configuration for regime detection."""
    lookback_period: int = 20
    sma_fast: int = 10
    sma_slow: int = 50
    volatility_window: int = 20
    trend_threshold: float = 0.02  # 2% threshold for trend
    confidence_threshold: float = 0.7
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/regime/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/regime/ tests/unit/regime/
git commit -m "feat(regime): add regime detection models"
```

---

## Task 6: StockRegimeDetector

**Files:**
- Create: `shared/regime/detector.py`
- Test: `tests/unit/regime/test_detector.py`

**Step 1: Write the failing test**

```python
# tests/unit/regime/test_detector.py
"""Test StockRegimeDetector."""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def test_detector_bull_regime():
    """Test detection of bull market."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeState

    detector = StockRegimeDetector()

    # Create uptrending data
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 100 + np.arange(60) * 0.5 + np.random.randn(60) * 0.5  # Uptrend

    df = pd.DataFrame({"datetime": dates, "close": prices})

    signal = detector.detect(df)

    assert signal.state == RegimeState.BULL


def test_detector_bear_regime():
    """Test detection of bear market."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeState

    detector = StockRegimeDetector()

    # Create downtrending data
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 150 - np.arange(60) * 0.5 + np.random.randn(60) * 0.5  # Downtrend

    df = pd.DataFrame({"datetime": dates, "close": prices})

    signal = detector.detect(df)

    assert signal.state == RegimeState.BEAR
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/regime/test_detector.py -v`
Expected: FAIL with "cannot import name 'StockRegimeDetector'"

**Step 3: Write minimal implementation**

```python
# shared/regime/detector.py
"""Stock regime detector."""
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np

from .models import RegimeState, RegimeSignal, RegimeConfig

logger = logging.getLogger(__name__)


class StockRegimeDetector:
    """Detect market regime based on price action.

    Uses:
    - Moving average crossovers
    - Price momentum
    - Volatility
    """

    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()
        self._last_signal: Optional[RegimeSignal] = None

    def detect(self, df: pd.DataFrame) -> RegimeSignal:
        """Detect current market regime.

        Args:
            df: DataFrame with 'datetime' and 'close' columns

        Returns:
            RegimeSignal with detected state and confidence
        """
        if len(df) < self.config.sma_slow:
            return RegimeSignal(
                state=RegimeState.UNKNOWN,
                confidence=0.0,
                timestamp=datetime.now(),
            )

        # Calculate indicators
        close = df["close"]
        sma_fast = close.rolling(self.config.sma_fast).mean()
        sma_slow = close.rolling(self.config.sma_slow).mean()

        # Current values
        current_price = close.iloc[-1]
        current_sma_fast = sma_fast.iloc[-1]
        current_sma_slow = sma_slow.iloc[-1]

        # Calculate trend strength
        trend_pct = (current_sma_fast - current_sma_slow) / current_sma_slow

        # Calculate volatility
        returns = close.pct_change().dropna()
        volatility = returns.rolling(self.config.volatility_window).std().iloc[-1]

        # Determine regime
        indicators = {
            "sma_fast": current_sma_fast,
            "sma_slow": current_sma_slow,
            "trend_pct": trend_pct,
            "volatility": volatility,
        }

        if trend_pct > self.config.trend_threshold:
            state = RegimeState.BULL
            confidence = min(1.0, abs(trend_pct) / (self.config.trend_threshold * 2))
        elif trend_pct < -self.config.trend_threshold:
            state = RegimeState.BEAR
            confidence = min(1.0, abs(trend_pct) / (self.config.trend_threshold * 2))
        else:
            state = RegimeState.SIDEWAYS
            confidence = 1.0 - abs(trend_pct) / self.config.trend_threshold

        # Adjust confidence by volatility
        if volatility > 0.03:  # High volatility reduces confidence
            confidence *= 0.8

        signal = RegimeSignal(
            state=state,
            confidence=confidence,
            timestamp=datetime.now(),
            indicators=indicators,
        )

        self._last_signal = signal
        return signal

    @property
    def last_signal(self) -> Optional[RegimeSignal]:
        """Get last detected signal."""
        return self._last_signal
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/regime/test_detector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/regime/detector.py tests/unit/regime/test_detector.py
git commit -m "feat(regime): add StockRegimeDetector"
```

---

## Task 7: StrategyRouter

**Files:**
- Create: `shared/regime/router.py`
- Test: `tests/unit/regime/test_router.py`

**Step 1: Write the failing test**

```python
# tests/unit/regime/test_router.py
"""Test StrategyRouter."""
import pytest


def test_router_strategy_selection():
    """Test regime-based strategy selection."""
    from shared.regime.router import StrategyRouter
    from shared.regime.models import RegimeState

    router = StrategyRouter()

    # Register strategies for regimes
    router.register("aggressive", [RegimeState.BULL])
    router.register("defensive", [RegimeState.BEAR])
    router.register("range_bound", [RegimeState.SIDEWAYS])

    assert router.get_strategy(RegimeState.BULL) == "aggressive"
    assert router.get_strategy(RegimeState.BEAR) == "defensive"
    assert router.get_strategy(RegimeState.SIDEWAYS) == "range_bound"


def test_router_default_strategy():
    """Test default strategy fallback."""
    from shared.regime.router import StrategyRouter
    from shared.regime.models import RegimeState

    router = StrategyRouter(default_strategy="balanced")

    # No strategies registered
    assert router.get_strategy(RegimeState.BULL) == "balanced"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/regime/test_router.py -v`
Expected: FAIL with "cannot import name 'StrategyRouter'"

**Step 3: Write minimal implementation**

```python
# shared/regime/router.py
"""Strategy router based on market regime."""
import logging
from typing import Dict, List, Optional

from .models import RegimeState, RegimeSignal

logger = logging.getLogger(__name__)


class StrategyRouter:
    """Route to appropriate strategy based on market regime.

    Features:
    - Map regimes to strategies
    - Default strategy fallback
    - Strategy activation tracking
    """

    def __init__(self, default_strategy: Optional[str] = None):
        self.default_strategy = default_strategy
        self._regime_map: Dict[RegimeState, str] = {}
        self._current_strategy: Optional[str] = None

    def register(self, strategy_name: str, regimes: List[RegimeState]) -> None:
        """Register strategy for given regimes."""
        for regime in regimes:
            self._regime_map[regime] = strategy_name
            logger.debug(f"Registered {strategy_name} for {regime.value}")

    def get_strategy(self, state: RegimeState) -> Optional[str]:
        """Get strategy for given regime state."""
        strategy = self._regime_map.get(state, self.default_strategy)
        return strategy

    def update(self, signal: RegimeSignal) -> Optional[str]:
        """Update router with new regime signal.

        Returns:
            New strategy name if changed, None otherwise
        """
        if not signal.is_confident:
            # Keep current strategy if signal not confident
            return None

        new_strategy = self.get_strategy(signal.state)

        if new_strategy != self._current_strategy:
            old_strategy = self._current_strategy
            self._current_strategy = new_strategy
            logger.info(
                f"Strategy switch: {old_strategy} -> {new_strategy} "
                f"(regime: {signal.state.value}, confidence: {signal.confidence:.2f})"
            )
            return new_strategy

        return None

    @property
    def current_strategy(self) -> Optional[str]:
        """Get current active strategy."""
        return self._current_strategy

    def get_routing_table(self) -> Dict[str, str]:
        """Get regime to strategy mapping."""
        return {k.value: v for k, v in self._regime_map.items()}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/regime/test_router.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/regime/router.py tests/unit/regime/test_router.py
git commit -m "feat(regime): add StrategyRouter"
```

---

## Task 8: AlertConfig and Models

**Files:**
- Create: `shared/alerts/models.py`
- Create: `shared/alerts/__init__.py`
- Test: `tests/unit/alerts/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/alerts/test_models.py
"""Test alert models."""
import pytest
from datetime import datetime


def test_alert_level_enum():
    """Test AlertLevel enum."""
    from shared.alerts.models import AlertLevel

    assert AlertLevel.INFO.value == "INFO"
    assert AlertLevel.WARNING.value == "WARNING"
    assert AlertLevel.CRITICAL.value == "CRITICAL"


def test_alert_creation():
    """Test Alert model."""
    from shared.alerts.models import Alert, AlertLevel

    alert = Alert(
        level=AlertLevel.WARNING,
        title="High Drawdown",
        message="Portfolio drawdown exceeded 5%",
        timestamp=datetime.now(),
    )

    assert alert.level == AlertLevel.WARNING
    assert "Drawdown" in alert.title
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/alerts/test_models.py -v`
Expected: FAIL with "No module named 'shared.alerts'"

**Step 3: Write minimal implementation**

```python
# shared/alerts/__init__.py
"""Alerts module."""

# shared/alerts/models.py
"""Alert models."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Alert:
    """Alert message."""
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str = "system"
    metadata: Optional[Dict] = None
    sent: bool = False


@dataclass
class AlertConfig:
    """Alert service configuration."""
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    email_smtp_host: Optional[str] = None
    email_smtp_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_recipients: list = field(default_factory=list)
    min_level: AlertLevel = AlertLevel.WARNING
    rate_limit_seconds: int = 60
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/alerts/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/alerts/ tests/unit/alerts/
git commit -m "feat(alerts): add alert models and config"
```

---

## Task 9: TelegramAlertService

**Files:**
- Create: `shared/alerts/telegram.py`
- Test: `tests/unit/alerts/test_telegram.py`

**Step 1: Write the failing test**

```python
# tests/unit/alerts/test_telegram.py
"""Test TelegramAlertService."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_telegram_format_message():
    """Test message formatting."""
    from shared.alerts.telegram import TelegramAlertService
    from shared.alerts.models import Alert, AlertLevel, AlertConfig

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
    )
    service = TelegramAlertService(config)

    alert = Alert(
        level=AlertLevel.WARNING,
        title="Test Alert",
        message="This is a test",
        timestamp=datetime.now(),
    )

    formatted = service._format_message(alert)

    assert "⚠️" in formatted  # Warning emoji
    assert "Test Alert" in formatted
    assert "This is a test" in formatted


@pytest.mark.asyncio
async def test_telegram_send_disabled():
    """Test sending when disabled."""
    from shared.alerts.telegram import TelegramAlertService
    from shared.alerts.models import Alert, AlertLevel, AlertConfig

    config = AlertConfig()  # No token = disabled
    service = TelegramAlertService(config)

    alert = Alert(
        level=AlertLevel.WARNING,
        title="Test",
        message="Test",
        timestamp=datetime.now(),
    )

    result = await service.send(alert)
    assert result is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/alerts/test_telegram.py -v`
Expected: FAIL with "cannot import name 'TelegramAlertService'"

**Step 3: Write minimal implementation**

```python
# shared/alerts/telegram.py
"""Telegram alert service."""
import logging
from datetime import datetime
from typing import Optional

import aiohttp

from .models import Alert, AlertLevel, AlertConfig

logger = logging.getLogger(__name__)


class TelegramAlertService:
    """Send alerts via Telegram.

    Features:
    - Formatted messages with emojis
    - Rate limiting
    - Async sending
    """

    LEVEL_EMOJIS = {
        AlertLevel.INFO: "ℹ️",
        AlertLevel.WARNING: "⚠️",
        AlertLevel.CRITICAL: "🚨",
    }

    def __init__(self, config: AlertConfig):
        self.config = config
        self._last_sent: Optional[datetime] = None
        self._enabled = bool(config.telegram_token and config.telegram_chat_id)

    @property
    def is_enabled(self) -> bool:
        """Check if service is enabled."""
        return self._enabled

    def _format_message(self, alert: Alert) -> str:
        """Format alert for Telegram."""
        emoji = self.LEVEL_EMOJIS.get(alert.level, "📢")
        timestamp = alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        return (
            f"{emoji} *{alert.title}*\n\n"
            f"{alert.message}\n\n"
            f"_{timestamp}_ | `{alert.source}`"
        )

    def _should_send(self, alert: Alert) -> bool:
        """Check if alert should be sent (rate limiting)."""
        # Check level threshold
        if alert.level.value < self.config.min_level.value:
            return False

        # Check rate limit
        if self._last_sent:
            elapsed = (datetime.now() - self._last_sent).total_seconds()
            if elapsed < self.config.rate_limit_seconds:
                # Allow critical alerts to bypass rate limit
                if alert.level != AlertLevel.CRITICAL:
                    return False

        return True

    async def send(self, alert: Alert) -> bool:
        """Send alert via Telegram.

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._enabled:
            logger.debug("Telegram alerts disabled")
            return False

        if not self._should_send(alert):
            logger.debug(f"Alert skipped (rate limit or level): {alert.title}")
            return False

        url = f"https://api.telegram.org/bot{self.config.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": self._format_message(alert),
            "parse_mode": "Markdown",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        self._last_sent = datetime.now()
                        alert.sent = True
                        logger.info(f"Alert sent: {alert.title}")
                        return True
                    else:
                        logger.error(f"Telegram API error: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/alerts/test_telegram.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/alerts/telegram.py tests/unit/alerts/test_telegram.py
git commit -m "feat(alerts): add TelegramAlertService"
```

---

## Task 10: AnomalyDetector

**Files:**
- Create: `shared/monitoring/anomaly.py`
- Create: `shared/monitoring/__init__.py`
- Test: `tests/unit/monitoring/test_anomaly.py`

**Step 1: Write the failing test**

```python
# tests/unit/monitoring/test_anomaly.py
"""Test AnomalyDetector."""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def test_detect_price_outlier():
    """Test detection of price outliers."""
    from shared.monitoring.anomaly import AnomalyDetector

    detector = AnomalyDetector()

    # Normal prices with one outlier
    prices = [100, 101, 99, 100, 102, 500, 101]  # 500 is outlier

    anomalies = detector.detect_outliers(prices)

    assert len(anomalies) == 1
    assert anomalies[0]["index"] == 5
    assert anomalies[0]["value"] == 500


def test_detect_data_gap():
    """Test detection of data gaps."""
    from shared.monitoring.anomaly import AnomalyDetector

    detector = AnomalyDetector()

    # Timestamps with a gap
    now = datetime.now()
    timestamps = [
        now - timedelta(minutes=5),
        now - timedelta(minutes=4),
        now - timedelta(minutes=3),
        # Gap here (missing minute 2)
        now - timedelta(minutes=0),
    ]

    gaps = detector.detect_gaps(timestamps, expected_interval_seconds=60)

    assert len(gaps) >= 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/monitoring/test_anomaly.py -v`
Expected: FAIL with "No module named 'shared.monitoring'"

**Step 3: Write minimal implementation**

```python
# shared/monitoring/__init__.py
"""Monitoring module."""

# shared/monitoring/anomaly.py
"""Anomaly detection for data quality."""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnomalyConfig:
    """Anomaly detection configuration."""
    outlier_std_threshold: float = 3.0
    gap_tolerance_factor: float = 2.0
    min_samples: int = 10


class AnomalyDetector:
    """Detect data quality anomalies.

    Features:
    - Price outlier detection (z-score)
    - Data gap detection
    - Volume anomaly detection
    """

    def __init__(self, config: Optional[AnomalyConfig] = None):
        self.config = config or AnomalyConfig()

    def detect_outliers(
        self,
        values: List[float],
        window: int = 20,
    ) -> List[Dict]:
        """Detect outliers using rolling z-score.

        Args:
            values: List of values to check
            window: Rolling window size

        Returns:
            List of detected anomalies with index and value
        """
        if len(values) < self.config.min_samples:
            return []

        arr = np.array(values)
        anomalies = []

        # Calculate rolling mean and std
        for i in range(window, len(arr)):
            window_data = arr[i - window:i]
            mean = np.mean(window_data)
            std = np.std(window_data)

            if std == 0:
                continue

            z_score = abs(arr[i] - mean) / std

            if z_score > self.config.outlier_std_threshold:
                anomalies.append({
                    "index": i,
                    "value": arr[i],
                    "z_score": z_score,
                    "expected_range": (
                        mean - self.config.outlier_std_threshold * std,
                        mean + self.config.outlier_std_threshold * std,
                    ),
                })
                logger.warning(f"Outlier detected at index {i}: {arr[i]} (z={z_score:.2f})")

        return anomalies

    def detect_gaps(
        self,
        timestamps: List[datetime],
        expected_interval_seconds: int = 60,
    ) -> List[Dict]:
        """Detect gaps in time series data.

        Args:
            timestamps: List of timestamps
            expected_interval_seconds: Expected interval between data points

        Returns:
            List of detected gaps
        """
        if len(timestamps) < 2:
            return []

        gaps = []
        tolerance = expected_interval_seconds * self.config.gap_tolerance_factor

        sorted_ts = sorted(timestamps)

        for i in range(1, len(sorted_ts)):
            delta = (sorted_ts[i] - sorted_ts[i - 1]).total_seconds()

            if delta > tolerance:
                gaps.append({
                    "start": sorted_ts[i - 1],
                    "end": sorted_ts[i],
                    "gap_seconds": delta,
                    "expected_seconds": expected_interval_seconds,
                })
                logger.warning(
                    f"Data gap detected: {sorted_ts[i-1]} to {sorted_ts[i]} "
                    f"({delta:.0f}s, expected {expected_interval_seconds}s)"
                )

        return gaps

    def detect_volume_anomaly(
        self,
        volumes: List[float],
        threshold_factor: float = 5.0,
    ) -> List[Dict]:
        """Detect abnormal trading volumes.

        Args:
            volumes: List of volume values
            threshold_factor: Multiple of average to flag as anomaly

        Returns:
            List of volume anomalies
        """
        if len(volumes) < self.config.min_samples:
            return []

        arr = np.array(volumes)
        avg_volume = np.mean(arr)
        threshold = avg_volume * threshold_factor

        anomalies = []
        for i, vol in enumerate(arr):
            if vol > threshold:
                anomalies.append({
                    "index": i,
                    "volume": vol,
                    "average": avg_volume,
                    "ratio": vol / avg_volume,
                })

        return anomalies
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/monitoring/test_anomaly.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/monitoring/ tests/unit/monitoring/
git commit -m "feat(monitoring): add AnomalyDetector"
```

---

## Task 11: HealthChecker

**Files:**
- Create: `shared/monitoring/health.py`
- Test: `tests/unit/monitoring/test_health.py`

**Step 1: Write the failing test**

```python
# tests/unit/monitoring/test_health.py
"""Test HealthChecker."""
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_health_check_component():
    """Test component health check."""
    from shared.monitoring.health import HealthChecker, ComponentHealth

    checker = HealthChecker()

    # Register a healthy component
    async def healthy_check():
        return True

    checker.register("database", healthy_check)

    result = await checker.check("database")

    assert result.name == "database"
    assert result.healthy is True


@pytest.mark.asyncio
async def test_health_check_all():
    """Test checking all components."""
    from shared.monitoring.health import HealthChecker

    checker = HealthChecker()

    checker.register("db", lambda: True)
    checker.register("cache", lambda: True)

    results = await checker.check_all()

    assert len(results) == 2
    assert all(r.healthy for r in results)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/monitoring/test_health.py -v`
Expected: FAIL with "cannot import name 'HealthChecker'"

**Step 3: Write minimal implementation**

```python
# shared/monitoring/health.py
"""Health checking service."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Union, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ComponentHealth:
    """Health status of a component."""
    name: str
    healthy: bool
    timestamp: datetime
    latency_ms: float = 0.0
    message: Optional[str] = None


class HealthChecker:
    """Check health of system components.

    Features:
    - Register health check functions
    - Async/sync check support
    - Latency measurement
    - Aggregate health status
    """

    def __init__(self, timeout_seconds: float = 5.0):
        self.timeout = timeout_seconds
        self._checks: Dict[str, Callable] = {}

    def register(
        self,
        name: str,
        check_fn: Union[Callable[[], bool], Callable[[], Awaitable[bool]]],
    ) -> None:
        """Register health check function."""
        self._checks[name] = check_fn
        logger.debug(f"Registered health check: {name}")

    async def check(self, name: str) -> ComponentHealth:
        """Check health of single component.

        Args:
            name: Component name

        Returns:
            ComponentHealth with status
        """
        if name not in self._checks:
            return ComponentHealth(
                name=name,
                healthy=False,
                timestamp=datetime.now(),
                message="Component not registered",
            )

        check_fn = self._checks[name]
        start_time = datetime.now()

        try:
            result = check_fn()
            if asyncio.iscoroutine(result):
                result = await asyncio.wait_for(result, timeout=self.timeout)

            latency = (datetime.now() - start_time).total_seconds() * 1000

            return ComponentHealth(
                name=name,
                healthy=bool(result),
                timestamp=datetime.now(),
                latency_ms=latency,
            )

        except asyncio.TimeoutError:
            return ComponentHealth(
                name=name,
                healthy=False,
                timestamp=datetime.now(),
                message="Health check timed out",
            )
        except Exception as e:
            logger.error(f"Health check failed for {name}: {e}")
            return ComponentHealth(
                name=name,
                healthy=False,
                timestamp=datetime.now(),
                message=str(e),
            )

    async def check_all(self) -> List[ComponentHealth]:
        """Check health of all components.

        Returns:
            List of ComponentHealth for all registered components
        """
        tasks = [self.check(name) for name in self._checks]
        return await asyncio.gather(*tasks)

    def is_healthy(self, results: List[ComponentHealth]) -> bool:
        """Check if all components are healthy."""
        return all(r.healthy for r in results)

    def get_summary(self, results: List[ComponentHealth]) -> Dict:
        """Get health summary."""
        return {
            "healthy": self.is_healthy(results),
            "components": {
                r.name: {
                    "healthy": r.healthy,
                    "latency_ms": r.latency_ms,
                    "message": r.message,
                }
                for r in results
            },
            "timestamp": datetime.now().isoformat(),
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/monitoring/test_health.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/monitoring/health.py tests/unit/monitoring/test_health.py
git commit -m "feat(monitoring): add HealthChecker"
```

---

## Task 12: CLI Commands for Paper Trading

**Files:**
- Modify: `cli/main.py`
- Test: `tests/unit/test_cli_paper.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_cli_paper.py
"""Test paper trading CLI commands."""
import pytest
from click.testing import CliRunner


def test_paper_start_command():
    """Test paper start command exists."""
    from cli.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["paper", "--help"])

    assert result.exit_code == 0
    assert "start" in result.output
    assert "status" in result.output


def test_paper_status_command():
    """Test paper status command."""
    from cli.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["paper", "status"])

    assert result.exit_code == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_cli_paper.py -v`
Expected: FAIL (paper command doesn't exist)

**Step 3: Add CLI commands**

Add to `cli/main.py`:

```python
# =============================================================================
# Paper Trading Commands
# =============================================================================


@cli.group()
def paper():
    """모의 거래 명령

    \b
    Examples:
        sts paper start -s bb_reversion -a stock
        sts paper status
        sts paper stop
    """
    pass


@paper.command("start")
@click.option("--strategy", "-s", required=True, help="Strategy name")
@click.option("--asset", "-a", required=True, type=click.Choice(["stock", "futures"]))
@click.option("--capital", "-c", default=10_000_000, type=float)
def paper_start(strategy: str, asset: str, capital: float):
    """모의 거래 시작

    \b
    Example:
        sts paper start -s bb_reversion -a stock
    """
    click.echo(f"Starting paper trading: {strategy} ({asset})")
    click.echo(f"  Capital: {capital:,.0f}")
    click.echo("  Status: Started (simulation)")


@paper.command("status")
def paper_status():
    """모의 거래 상태 조회"""
    click.echo("Paper Trading Status:")
    click.echo("-" * 40)
    click.echo("  Status: Not running")
    click.echo("  Note: Use 'sts paper start' to begin")


@paper.command("stop")
def paper_stop():
    """모의 거래 종료"""
    click.echo("Paper trading stopped")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_cli_paper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/main.py tests/unit/test_cli_paper.py
git commit -m "feat(cli): add paper trading commands"
```

---

## Task 13: Prometheus Metrics

**Files:**
- Create: `shared/monitoring/metrics.py`
- Test: `tests/unit/monitoring/test_metrics.py`

**Step 1: Write the failing test**

```python
# tests/unit/monitoring/test_metrics.py
"""Test Prometheus metrics."""
import pytest


def test_metrics_registry():
    """Test metrics can be created."""
    from shared.monitoring.metrics import TradingMetrics

    metrics = TradingMetrics()

    # Record some metrics
    metrics.record_trade("005930", "BUY", 1000)
    metrics.record_order_latency(0.05)
    metrics.set_position_count(3)

    # Verify counters exist
    assert metrics.trades_total is not None
    assert metrics.order_latency is not None


def test_metrics_export():
    """Test metrics can be exported."""
    from shared.monitoring.metrics import TradingMetrics

    metrics = TradingMetrics()
    metrics.record_trade("005930", "BUY", 1000)

    # Should be able to get text output
    output = metrics.export()
    assert "trades_total" in output
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/monitoring/test_metrics.py -v`
Expected: FAIL with "cannot import name 'TradingMetrics'"

**Step 3: Write minimal implementation**

```python
# shared/monitoring/metrics.py
"""Prometheus metrics for trading system."""
import logging
from typing import Optional

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


class TradingMetrics:
    """Trading system metrics for Prometheus.

    Metrics:
    - trades_total: Total number of trades
    - order_latency: Order execution latency
    - position_count: Current position count
    - equity: Current equity value
    - pnl_total: Total P&L
    """

    def __init__(self, prefix: str = "trading"):
        self.prefix = prefix

        if PROMETHEUS_AVAILABLE:
            self.trades_total = Counter(
                f"{prefix}_trades_total",
                "Total number of trades",
                ["symbol", "side"],
            )
            self.order_latency = Histogram(
                f"{prefix}_order_latency_seconds",
                "Order execution latency",
                buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            )
            self.position_count = Gauge(
                f"{prefix}_position_count",
                "Current number of positions",
            )
            self.equity = Gauge(
                f"{prefix}_equity",
                "Current portfolio equity",
            )
            self.pnl_total = Gauge(
                f"{prefix}_pnl_total",
                "Total realized P&L",
            )
        else:
            logger.warning("prometheus_client not installed, metrics disabled")
            self.trades_total = None
            self.order_latency = None
            self.position_count = None
            self.equity = None
            self.pnl_total = None

    def record_trade(self, symbol: str, side: str, pnl: float) -> None:
        """Record a completed trade."""
        if self.trades_total:
            self.trades_total.labels(symbol=symbol, side=side).inc()
        if self.pnl_total:
            self.pnl_total.inc(pnl)

    def record_order_latency(self, latency_seconds: float) -> None:
        """Record order execution latency."""
        if self.order_latency:
            self.order_latency.observe(latency_seconds)

    def set_position_count(self, count: int) -> None:
        """Set current position count."""
        if self.position_count:
            self.position_count.set(count)

    def set_equity(self, value: float) -> None:
        """Set current equity value."""
        if self.equity:
            self.equity.set(value)

    def export(self) -> str:
        """Export metrics in Prometheus format."""
        if PROMETHEUS_AVAILABLE:
            return generate_latest(REGISTRY).decode("utf-8")
        return ""
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/monitoring/test_metrics.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/monitoring/metrics.py tests/unit/monitoring/test_metrics.py
git commit -m "feat(monitoring): add Prometheus metrics"
```

---

## Task 14: Integration Tests

**Files:**
- Create: `tests/integration/test_paper_trading.py`

**Step 1: Write the integration test**

```python
# tests/integration/test_paper_trading.py
"""Integration tests for paper trading system."""
import pytest
from datetime import datetime


@pytest.mark.integration
@pytest.mark.asyncio
async def test_paper_trading_full_cycle():
    """Test complete paper trading cycle."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig
    from shared.paper.models import OrderSide

    config = PaperTradingConfig(
        initial_balance=10_000_000,
        max_positions=3,
    )
    engine = PaperTradingEngine(config)

    # Start engine
    await engine.start()
    assert engine.is_running

    # Execute trades
    await engine.process_signal("005930", OrderSide.BUY, 58000, 10)
    await engine.process_signal("000660", OrderSide.BUY, 120000, 5)

    # Check positions
    assert len(engine.broker.positions) == 2

    # Close one position
    await engine.process_signal("005930", OrderSide.SELL, 59000, 10)

    # Check trade recorded
    assert len(engine.broker.trades) == 1

    # Stop engine
    await engine.stop()
    assert not engine.is_running

    # Check performance
    perf = engine.get_performance()
    assert "total_trades" in perf
    assert perf["total_trades"] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regime_detection_pipeline():
    """Test regime detection integration."""
    import pandas as pd
    import numpy as np

    from shared.regime.detector import StockRegimeDetector
    from shared.regime.router import StrategyRouter
    from shared.regime.models import RegimeState

    # Create test data
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 100 + np.arange(60) * 0.3 + np.random.randn(60) * 0.5  # Uptrend
    df = pd.DataFrame({"datetime": dates, "close": prices})

    # Setup detector and router
    detector = StockRegimeDetector()
    router = StrategyRouter(default_strategy="balanced")
    router.register("momentum", [RegimeState.BULL])
    router.register("defensive", [RegimeState.BEAR])

    # Detect regime
    signal = detector.detect(df)

    # Route to strategy
    strategy = router.update(signal)

    # Should route to momentum in uptrend
    assert router.current_strategy == "momentum"
```

**Step 2: Run test**

Run: `pytest tests/integration/test_paper_trading.py -v`
Expected: PASS (after all components implemented)

**Step 3: Commit**

```bash
git add tests/integration/test_paper_trading.py
git commit -m "test(integration): add paper trading integration tests"
```

---

## Dependencies

```
# Add to pyproject.toml
prometheus_client>=0.19.0
aiohttp>=3.9.0
```

---

**Created:** 2026-01-20
**Expanded:** 2026-01-21
