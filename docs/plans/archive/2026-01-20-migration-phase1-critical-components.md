# Phase 1: Critical Components Migration Plan

**Status**: Implemented (2026-01-20)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate critical components needed for live trading from kospi_mini_sts and quant_moment_sts to the unified architecture.

**Architecture:** Configuration-driven approach with abstract interfaces. All components use Pydantic models for configuration, async/await patterns for I/O, and registry-based factory pattern for instantiation.

**Tech Stack:** Python 3.11+, asyncio, aiohttp, clickhouse-driver, redis, pydantic

---

## Overview

This plan migrates the following components in priority order:

| # | Component | Source | Lines | Priority |
|---|-----------|--------|-------|----------|
| 1 | ClickHouse Client | quant_moment_sts | 744 | Critical |
| 2 | Data Collector | kospi_mini_sts | 253 | Critical |
| 3 | Order Executor | quant_moment_sts | ~300 | Critical |
| 4 | Position Manager | quant_moment_sts | ~600 | Critical |
| 5 | Trading Orchestrator | quant_moment_sts | ~1500 | Critical |

**Estimated Tasks:** 25 bite-sized tasks

---

## Task 1: ClickHouse Client - Data Models

**Files:**
- Create: `shared/db/models.py`
- Test: `tests/unit/db/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/db/test_models.py
"""Test ClickHouse data models."""
import pytest
from datetime import date, datetime


def test_daily_candle_creation():
    """Test DailyCandle dataclass creation."""
    from shared.db.models import DailyCandle

    candle = DailyCandle(
        code="005930",
        date=date(2025, 1, 15),
        open=58000.0,
        high=59000.0,
        low=57500.0,
        close=58500.0,
        volume=1000000,
        value=58500000000,
        change_rate=0.86
    )

    assert candle.code == "005930"
    assert candle.close == 58500.0
    assert candle.change_rate == 0.86


def test_minute_candle_creation():
    """Test MinuteCandle dataclass creation."""
    from shared.db.models import MinuteCandle

    candle = MinuteCandle(
        code="005930",
        datetime=datetime(2025, 1, 15, 9, 30),
        open=58000.0,
        high=58100.0,
        low=57900.0,
        close=58050.0,
        volume=5000,
        value=290250000
    )

    assert candle.code == "005930"
    assert candle.datetime.hour == 9
    assert candle.datetime.minute == 30


def test_tick_data_creation():
    """Test TickData dataclass creation."""
    from shared.db.models import TickData

    tick = TickData(
        code="005930",
        datetime=datetime(2025, 1, 15, 9, 30, 15, 123000),
        price=58000.0,
        volume=100,
        bid_price=57990.0,
        ask_price=58010.0,
        cumulative_volume=50000
    )

    assert tick.price == 58000.0
    assert tick.bid_price == 57990.0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/db/test_models.py -v`
Expected: FAIL with "No module named 'shared.db'"

**Step 3: Write minimal implementation**

```python
# shared/db/__init__.py
"""Database module for ClickHouse integration."""

# shared/db/models.py
"""ClickHouse data models."""
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class DailyCandle:
    """일봉 데이터"""
    code: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    value: int  # 거래대금
    change_rate: float  # 등락률


@dataclass
class MinuteCandle:
    """분봉 데이터"""
    code: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    value: int


@dataclass
class TickData:
    """틱 데이터"""
    code: str
    datetime: datetime
    price: float
    volume: int
    bid_price: float
    ask_price: float
    cumulative_volume: int
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/db/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/db/ tests/unit/db/
git commit -m "feat(db): add ClickHouse data models

- Add DailyCandle, MinuteCandle, TickData dataclasses
- Mirror schema from quant_moment_sts/core/clickhouse_client.py"
```

---

## Task 2: ClickHouse Client - Configuration

**Files:**
- Create: `shared/db/config.py`
- Create: `config/clickhouse.yaml`
- Test: `tests/unit/db/test_config.py`

**Step 1: Write the failing test**

```python
# tests/unit/db/test_config.py
"""Test ClickHouse configuration."""
import pytest


def test_clickhouse_config_from_dict():
    """Test ClickHouseConfig creation from dictionary."""
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig(
        host="localhost",
        port=9000,
        user="default",
        password="",
        database="market"
    )

    assert config.host == "localhost"
    assert config.port == 9000
    assert config.database == "market"


def test_clickhouse_config_defaults():
    """Test ClickHouseConfig default values."""
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig()

    assert config.host == "localhost"
    assert config.port == 9000
    assert config.database == "market"


def test_clickhouse_config_connection_string():
    """Test connection string generation."""
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig(
        host="db.example.com",
        port=9000,
        user="trader",
        database="trading"
    )

    assert "db.example.com" in str(config)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/db/test_config.py -v`
Expected: FAIL with "cannot import name 'ClickHouseConfig'"

**Step 3: Write minimal implementation**

```python
# shared/db/config.py
"""ClickHouse configuration."""
from pydantic import BaseModel, Field


class ClickHouseConfig(BaseModel):
    """ClickHouse connection configuration."""

    host: str = Field(default="localhost", description="ClickHouse host")
    port: int = Field(default=9000, description="ClickHouse native port")
    user: str = Field(default="default", description="Username")
    password: str = Field(default="", description="Password")
    database: str = Field(default="market", description="Database name")

    # Connection pool settings
    pool_size: int = Field(default=5, description="Connection pool size")
    connect_timeout: int = Field(default=10, description="Connection timeout seconds")

    def __str__(self) -> str:
        return f"ClickHouse({self.user}@{self.host}:{self.port}/{self.database})"

    class Config:
        frozen = True
```

```yaml
# config/clickhouse.yaml
clickhouse:
  host: ${CLICKHOUSE_HOST:localhost}
  port: ${CLICKHOUSE_PORT:9000}
  user: ${CLICKHOUSE_USER:default}
  password: ${CLICKHOUSE_PASSWORD:}
  database: ${CLICKHOUSE_DATABASE:market}
  pool_size: 5
  connect_timeout: 10
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/db/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/db/config.py config/clickhouse.yaml tests/unit/db/test_config.py
git commit -m "feat(db): add ClickHouse configuration

- Add ClickHouseConfig pydantic model
- Add config/clickhouse.yaml with env var support"
```

---

## Task 3: ClickHouse Client - Core Client

**Files:**
- Create: `shared/db/client.py`
- Test: `tests/unit/db/test_client.py`

**Step 1: Write the failing test**

```python
# tests/unit/db/test_client.py
"""Test ClickHouse client."""
import pytest
from unittest.mock import Mock, patch


def test_client_singleton():
    """Test ClickHouseClient is singleton."""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig()

    # Reset singleton for test
    ClickHouseClient._instance = None

    client1 = ClickHouseClient(config)
    client2 = ClickHouseClient(config)

    assert client1 is client2


def test_client_ping_mock():
    """Test ping with mocked connection."""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig()
    ClickHouseClient._instance = None

    client = ClickHouseClient(config)

    with patch.object(client, '_sync_client') as mock_sync:
        mock_sync.execute.return_value = [(1,)]

        result = client.ping()

        assert result is True


def test_get_clickhouse_client_factory():
    """Test factory function."""
    from shared.db.client import get_clickhouse_client

    # Should not raise
    client = get_clickhouse_client()
    assert client is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/db/test_client.py -v`
Expected: FAIL with "cannot import name 'ClickHouseClient'"

**Step 3: Write minimal implementation**

```python
# shared/db/client.py
"""ClickHouse client with singleton pattern."""
import logging
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta

from clickhouse_driver import Client as SyncClient

from .config import ClickHouseConfig
from .models import DailyCandle, MinuteCandle, TickData

logger = logging.getLogger(__name__)


class ClickHouseClient:
    """ClickHouse client (Singleton).

    Features:
        - Singleton pattern for connection reuse
        - Sync query support (async via run_in_executor)
        - Auto table creation
        - Batch insert optimization
    """

    _instance: Optional['ClickHouseClient'] = None

    # Table schemas
    SCHEMAS = {
        "daily_candles": """
            CREATE TABLE IF NOT EXISTS {database}.daily_candles (
                code String,
                date Date,
                open Float64,
                high Float64,
                low Float64,
                close Float64,
                volume UInt64,
                value UInt64,
                change_rate Float64,
                created_at DateTime DEFAULT now()
            ) ENGINE = ReplacingMergeTree(created_at)
            PARTITION BY toYear(date)
            ORDER BY (code, date)
            TTL date + INTERVAL 3 YEAR
        """,
        "minute_candles": """
            CREATE TABLE IF NOT EXISTS {database}.minute_candles (
                code String,
                datetime DateTime,
                open Float64,
                high Float64,
                low Float64,
                close Float64,
                volume UInt64,
                value UInt64,
                created_at DateTime DEFAULT now()
            ) ENGINE = ReplacingMergeTree(created_at)
            PARTITION BY toYYYYMM(datetime)
            ORDER BY (code, datetime)
            TTL datetime + INTERVAL 90 DAY
        """,
        "tick_data": """
            CREATE TABLE IF NOT EXISTS {database}.tick_data (
                code String,
                datetime DateTime64(3),
                price Float64,
                volume UInt32,
                bid_price Float64,
                ask_price Float64,
                cumulative_volume UInt64,
                created_at DateTime DEFAULT now()
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMMDD(datetime)
            ORDER BY (code, datetime)
            TTL datetime + INTERVAL 30 DAY
        """,
    }

    def __new__(cls, config: ClickHouseConfig = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: ClickHouseConfig = None):
        if self._initialized:
            return

        self.config = config or ClickHouseConfig()
        self._sync_client: Optional[SyncClient] = None
        self._initialized = True

        logger.info(f"ClickHouseClient initialized: {self.config}")

    def get_sync_client(self) -> SyncClient:
        """Get or create sync client."""
        if self._sync_client is None:
            self._sync_client = SyncClient(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                connect_timeout=self.config.connect_timeout,
            )
            logger.info(f"Connected to ClickHouse: {self.config.host}:{self.config.port}")
        return self._sync_client

    def disconnect(self):
        """Close connection."""
        if self._sync_client:
            self._sync_client.disconnect()
            self._sync_client = None
            logger.info("ClickHouse disconnected")

    def ping(self) -> bool:
        """Test connection."""
        try:
            client = self.get_sync_client()
            result = client.execute("SELECT 1")
            return result == [(1,)]
        except Exception as e:
            logger.error(f"ClickHouse ping failed: {e}")
            return False

    def init_schema(self) -> bool:
        """Initialize database and tables."""
        try:
            # Create database first (connect without database)
            temp_client = SyncClient(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
            )
            temp_client.execute(f"CREATE DATABASE IF NOT EXISTS {self.config.database}")
            temp_client.disconnect()

            # Create tables
            client = self.get_sync_client()
            for table_name, schema in self.SCHEMAS.items():
                client.execute(schema.format(database=self.config.database))
                logger.info(f"Table '{table_name}' ready")

            return True
        except Exception as e:
            logger.error(f"Failed to init schema: {e}")
            return False

    # CRUD Operations
    def insert_daily_candles(self, candles: List[DailyCandle]) -> int:
        """Batch insert daily candles."""
        if not candles:
            return 0

        try:
            client = self.get_sync_client()
            data = [
                (c.code, c.date, c.open, c.high, c.low, c.close,
                 c.volume, c.value, c.change_rate)
                for c in candles
            ]
            client.execute(
                f"INSERT INTO {self.config.database}.daily_candles "
                "(code, date, open, high, low, close, volume, value, change_rate) VALUES",
                data
            )
            return len(candles)
        except Exception as e:
            logger.error(f"Failed to insert daily candles: {e}")
            return 0

    def get_daily_candles(
        self,
        code: str,
        start_date: date,
        end_date: date
    ) -> List[DailyCandle]:
        """Query daily candles."""
        try:
            client = self.get_sync_client()
            result = client.execute(
                f"""
                SELECT code, date, open, high, low, close, volume, value, change_rate
                FROM {self.config.database}.daily_candles
                WHERE code = %(code)s AND date >= %(start)s AND date <= %(end)s
                ORDER BY date ASC
                """,
                {"code": code, "start": start_date, "end": end_date}
            )
            return [
                DailyCandle(
                    code=r[0], date=r[1], open=r[2], high=r[3],
                    low=r[4], close=r[5], volume=r[6], value=r[7], change_rate=r[8]
                )
                for r in result
            ]
        except Exception as e:
            logger.error(f"Failed to get daily candles: {e}")
            return []

    def insert_minute_candles(self, candles: List[MinuteCandle]) -> int:
        """Batch insert minute candles."""
        if not candles:
            return 0

        try:
            client = self.get_sync_client()
            data = [
                (c.code, c.datetime, c.open, c.high, c.low, c.close, c.volume, c.value)
                for c in candles
            ]
            client.execute(
                f"INSERT INTO {self.config.database}.minute_candles "
                "(code, datetime, open, high, low, close, volume, value) VALUES",
                data
            )
            return len(candles)
        except Exception as e:
            logger.error(f"Failed to insert minute candles: {e}")
            return 0

    def get_minute_candles(
        self,
        code: str,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> List[MinuteCandle]:
        """Query minute candles."""
        try:
            client = self.get_sync_client()
            result = client.execute(
                f"""
                SELECT code, datetime, open, high, low, close, volume, value
                FROM {self.config.database}.minute_candles
                WHERE code = %(code)s AND datetime >= %(start)s AND datetime <= %(end)s
                ORDER BY datetime ASC
                """,
                {"code": code, "start": start_datetime, "end": end_datetime}
            )
            return [
                MinuteCandle(
                    code=r[0], datetime=r[1], open=r[2], high=r[3],
                    low=r[4], close=r[5], volume=r[6], value=r[7]
                )
                for r in result
            ]
        except Exception as e:
            logger.error(f"Failed to get minute candles: {e}")
            return []


# Factory function
_client_instance: Optional[ClickHouseClient] = None


def get_clickhouse_client(config: ClickHouseConfig = None) -> ClickHouseClient:
    """Get ClickHouse client singleton."""
    global _client_instance
    if _client_instance is None:
        _client_instance = ClickHouseClient(config)
    return _client_instance
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/db/test_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/db/client.py tests/unit/db/test_client.py
git commit -m "feat(db): add ClickHouse client with CRUD operations

- Singleton pattern for connection reuse
- Auto schema initialization
- Batch insert for daily/minute candles
- Query methods with date range filtering"
```

---

## Task 4: Data Collector - TickData Model

**Files:**
- Create: `shared/collector/models.py`
- Test: `tests/unit/collector/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/collector/test_models.py
"""Test data collector models."""
import pytest
from datetime import datetime


def test_tick_data_creation():
    """Test TickData with L5 orderbook."""
    from shared.collector.models import TickData

    tick = TickData(
        symbol="101S06",
        timestamp=1705300800.123,
        bid_price_1=330.50,
        bid_qty_1=100,
        ask_price_1=330.55,
        ask_qty_1=150,
    )

    assert tick.symbol == "101S06"
    assert tick.bid_price_1 == 330.50
    assert tick.ask_price_1 == 330.55


def test_tick_data_to_dict():
    """Test TickData serialization excludes None values."""
    from shared.collector.models import TickData

    tick = TickData(
        symbol="101S06",
        timestamp=1705300800.0,
        bid_price_1=330.50,
        bid_qty_1=100,
        ask_price_1=330.55,
        ask_qty_1=150,
        current_price=330.52,
    )

    data = tick.to_dict()

    assert "bid_price_2" not in data  # None values excluded
    assert data["current_price"] == 330.52


def test_tick_data_spread():
    """Test spread calculation."""
    from shared.collector.models import TickData

    tick = TickData(
        symbol="101S06",
        timestamp=1705300800.0,
        bid_price_1=330.50,
        bid_qty_1=100,
        ask_price_1=330.55,
        ask_qty_1=150,
    )

    assert tick.spread == 0.05
    assert tick.mid_price == 330.525
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/collector/test_models.py -v`
Expected: FAIL with "No module named 'shared.collector'"

**Step 3: Write minimal implementation**

```python
# shared/collector/__init__.py
"""Data collector module for real-time market data ingestion."""

# shared/collector/models.py
"""Data collector models."""
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional


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
    bid_price_2: Optional[float] = None
    bid_qty_2: Optional[float] = None
    bid_price_3: Optional[float] = None
    bid_qty_3: Optional[float] = None
    bid_price_4: Optional[float] = None
    bid_qty_4: Optional[float] = None
    bid_price_5: Optional[float] = None
    bid_qty_5: Optional[float] = None

    ask_price_2: Optional[float] = None
    ask_qty_2: Optional[float] = None
    ask_price_3: Optional[float] = None
    ask_qty_3: Optional[float] = None
    ask_price_4: Optional[float] = None
    ask_qty_4: Optional[float] = None
    ask_price_5: Optional[float] = None
    ask_qty_5: Optional[float] = None

    # Trade data
    current_price: Optional[float] = None
    tick_volume: Optional[float] = None
    cumulative_volume: Optional[float] = None

    # OHLC (for day)
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None

    # Futures specific
    open_interest: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/collector/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/collector/ tests/unit/collector/
git commit -m "feat(collector): add TickData model with L5 orderbook

- Support for 5-level orderbook depth
- Spread and mid_price calculated properties
- Serialization excludes None values"
```

---

## Task 5: Data Collector - Base API Adapter

**Files:**
- Modify: `shared/collector/models.py` (add BaseAPIAdapter)
- Test: `tests/unit/collector/test_adapter.py`

**Step 1: Write the failing test**

```python
# tests/unit/collector/test_adapter.py
"""Test API adapter interface."""
import pytest
from abc import ABC


def test_base_adapter_is_abstract():
    """Test BaseAPIAdapter is abstract class."""
    from shared.collector.adapter import BaseAPIAdapter

    with pytest.raises(TypeError):
        BaseAPIAdapter()


def test_mock_adapter_implements_interface():
    """Test MockAPIAdapter implements interface."""
    from shared.collector.adapter import MockAPIAdapter

    adapter = MockAPIAdapter(tick_interval=0.1)

    assert hasattr(adapter, 'connect')
    assert hasattr(adapter, 'subscribe')
    assert hasattr(adapter, 'disconnect')
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/collector/test_adapter.py -v`
Expected: FAIL with "No module named 'shared.collector.adapter'"

**Step 3: Write minimal implementation**

```python
# shared/collector/adapter.py
"""API adapter interfaces for data collection."""
import time
import random
import logging
from abc import ABC, abstractmethod
from typing import Callable, List

from .models import TickData

logger = logging.getLogger(__name__)


class BaseAPIAdapter(ABC):
    """Base class for API adapters.

    Implement this for each data source (KIS, Upbit, etc.)
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to data source."""
        pass

    @abstractmethod
    def subscribe(self, symbols: List[str], callback: Callable[[TickData], None]) -> None:
        """Subscribe to symbols and register tick callback.

        Args:
            symbols: List of symbols to subscribe
            callback: Function called on each tick
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection."""
        pass


class MockAPIAdapter(BaseAPIAdapter):
    """Mock adapter for testing.

    Generates fake tick data at configurable interval.
    """

    def __init__(self, tick_interval: float = 0.1):
        self.tick_interval = tick_interval
        self._running = False
        self._callback: Callable[[TickData], None] = None

    def connect(self) -> None:
        logger.info("Mock API connected")

    def subscribe(self, symbols: List[str], callback: Callable[[TickData], None]) -> None:
        self._callback = callback
        self._running = True

        # Generate base prices for each symbol
        base_prices = {s: 330.0 + random.random() * 10 for s in symbols}

        while self._running:
            for symbol in symbols:
                base = base_prices[symbol]
                # Random walk
                base_prices[symbol] += (random.random() - 0.5) * 0.1

                tick = TickData(
                    symbol=symbol,
                    timestamp=time.time(),
                    bid_price_1=base - 0.025,
                    bid_qty_1=random.randint(10, 100),
                    ask_price_1=base + 0.025,
                    ask_qty_1=random.randint(10, 100),
                    current_price=base,
                    tick_volume=random.randint(1, 20),
                )
                self._callback(tick)

            time.sleep(self.tick_interval)

    def disconnect(self) -> None:
        self._running = False
        logger.info("Mock API disconnected")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/collector/test_adapter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/collector/adapter.py tests/unit/collector/test_adapter.py
git commit -m "feat(collector): add BaseAPIAdapter abstract class

- Abstract interface for data source adapters
- MockAPIAdapter for testing with random walk prices"
```

---

## Task 6: Data Collector - Main Collector Class

**Files:**
- Create: `shared/collector/collector.py`
- Test: `tests/unit/collector/test_collector.py`

**Step 1: Write the failing test**

```python
# tests/unit/collector/test_collector.py
"""Test DataCollector class."""
import pytest
from unittest.mock import Mock, MagicMock


def test_collector_creation():
    """Test DataCollector instantiation."""
    from shared.collector.collector import DataCollector
    from shared.collector.adapter import MockAPIAdapter

    adapter = MockAPIAdapter()
    collector = DataCollector(adapter)

    assert collector.adapter is adapter
    assert collector._message_count == 0


def test_collector_tick_callback():
    """Test tick callback publishes to stream."""
    from shared.collector.collector import DataCollector
    from shared.collector.adapter import MockAPIAdapter
    from shared.collector.models import TickData

    adapter = MockAPIAdapter()
    collector = DataCollector(adapter)

    # Mock the publisher
    collector.publisher = Mock()
    collector.publisher.publish = Mock()

    tick = TickData(
        symbol="TEST",
        timestamp=1705300800.0,
        bid_price_1=100.0,
        bid_qty_1=10,
        ask_price_1=100.1,
        ask_qty_1=10,
    )

    collector._on_tick(tick)

    assert collector._message_count == 1
    collector.publisher.publish.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/collector/test_collector.py -v`
Expected: FAIL with "cannot import name 'DataCollector'"

**Step 3: Write minimal implementation**

```python
# shared/collector/collector.py
"""Main data collector class."""
import time
import logging
from typing import List, Optional

from .adapter import BaseAPIAdapter
from .models import TickData
from shared.streaming.publisher import StreamPublisher

logger = logging.getLogger(__name__)


class DataCollector:
    """Data Collector - ingests data from API adapter to Redis Stream.

    This is the main entry point for real-time data collection.
    """

    def __init__(
        self,
        api_adapter: BaseAPIAdapter,
        stream_name: str = "raw_data",
        stream_maxlen: int = 100000,
    ):
        """Initialize collector.

        Args:
            api_adapter: API adapter instance
            stream_name: Redis stream name for output
            stream_maxlen: Maximum stream length (older entries trimmed)
        """
        self.adapter = api_adapter
        self.stream_name = stream_name
        self.stream_maxlen = stream_maxlen

        # Publisher created lazily on start
        self.publisher: Optional[StreamPublisher] = None

        self._running = False
        self._message_count = 0

    def _on_tick(self, tick: TickData) -> None:
        """Callback for tick data from adapter.

        Publishes tick to Redis Stream.
        """
        try:
            data = tick.to_dict()
            if self.publisher:
                self.publisher.publish(data)

            self._message_count += 1

            if self._message_count % 1000 == 0:
                logger.info(f"Published {self._message_count} messages")

        except Exception as e:
            logger.error(f"Error publishing tick: {e}")

    def start(self, symbols: List[str]) -> None:
        """Start data collection.

        Args:
            symbols: List of symbols to collect
        """
        logger.info(f"Starting Data Collector for {len(symbols)} symbols")
        self._running = True

        try:
            # Initialize publisher
            self.publisher = StreamPublisher(
                stream_name=self.stream_name,
                maxlen=self.stream_maxlen
            )

            # Connect and subscribe
            self.adapter.connect()
            self.adapter.subscribe(symbols, self._on_tick)

            # Main loop (adapter's subscribe is blocking)
            while self._running:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop data collection."""
        self._running = False
        self.adapter.disconnect()
        logger.info(f"Data Collector stopped. Total messages: {self._message_count}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/collector/test_collector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/collector/collector.py tests/unit/collector/test_collector.py
git commit -m "feat(collector): add DataCollector class

- Orchestrates data collection from API adapter
- Publishes ticks to Redis Stream
- Graceful shutdown support"
```

---

## Task 7: Order Executor - Configuration

**Files:**
- Create: `shared/execution/config.py`
- Test: `tests/unit/execution/test_config.py`

**Step 1: Write the failing test**

```python
# tests/unit/execution/test_config.py
"""Test order execution configuration."""
import pytest


def test_execution_config_creation():
    """Test ExecutionConfig creation."""
    from shared.execution.config import ExecutionConfig

    config = ExecutionConfig(
        trading_mode="MOCK",
        max_retries=3,
        retry_delay=1.0,
    )

    assert config.trading_mode == "MOCK"
    assert config.max_retries == 3


def test_execution_config_modes():
    """Test valid trading modes."""
    from shared.execution.config import ExecutionConfig, TradingMode

    assert TradingMode.PAPER.value == "PAPER"
    assert TradingMode.MOCK.value == "MOCK"
    assert TradingMode.REAL.value == "REAL"


def test_execution_config_defaults():
    """Test default configuration."""
    from shared.execution.config import ExecutionConfig

    config = ExecutionConfig()

    assert config.trading_mode == "PAPER"
    assert config.max_retries == 3
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/execution/test_config.py -v`
Expected: FAIL with "No module named 'shared.execution'"

**Step 3: Write minimal implementation**

```python
# shared/execution/__init__.py
"""Order execution module."""

# shared/execution/config.py
"""Order execution configuration."""
from enum import Enum
from pydantic import BaseModel, Field


class TradingMode(str, Enum):
    """Trading mode enumeration."""
    PAPER = "PAPER"   # Local simulation (no API calls)
    MOCK = "MOCK"     # KIS 모의투자 API
    REAL = "REAL"     # KIS 실전투자 API


class ExecutionConfig(BaseModel):
    """Order execution configuration."""

    trading_mode: str = Field(
        default="PAPER",
        description="Trading mode: PAPER, MOCK, or REAL"
    )

    # Retry settings
    max_retries: int = Field(default=3, description="Max retry attempts")
    retry_delay: float = Field(default=1.0, description="Delay between retries (seconds)")

    # Rate limiting
    orders_per_second: float = Field(default=5.0, description="Max orders per second")

    # Account info (loaded from environment)
    account_no: str = Field(default="", description="Account number")

    class Config:
        use_enum_values = True
```

```yaml
# config/execution.yaml
execution:
  trading_mode: ${TRADING_MODE:PAPER}
  max_retries: 3
  retry_delay: 1.0
  orders_per_second: 5.0
  account_no: ${KIS_ACCOUNT_NO:}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/execution/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/execution/ config/execution.yaml tests/unit/execution/
git commit -m "feat(execution): add order execution configuration

- TradingMode enum (PAPER, MOCK, REAL)
- ExecutionConfig with retry and rate limit settings
- YAML config with environment variable support"
```

---

## Task 8: Order Executor - Request/Response Models

**Files:**
- Create: `shared/execution/models.py`
- Test: `tests/unit/execution/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/execution/test_models.py
"""Test order execution models."""
import pytest


def test_order_request_creation():
    """Test OrderRequest model."""
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    order = OrderRequest(
        code="005930",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
    )

    assert order.code == "005930"
    assert order.side == OrderSide.BUY
    assert order.quantity == 10


def test_order_response_success():
    """Test successful OrderResponse."""
    from shared.execution.models import OrderResponse

    response = OrderResponse(
        success=True,
        order_no="0001234567",
        message="Order accepted"
    )

    assert response.success is True
    assert response.order_no == "0001234567"


def test_order_response_failure():
    """Test failed OrderResponse."""
    from shared.execution.models import OrderResponse

    response = OrderResponse(
        success=False,
        message="Insufficient balance"
    )

    assert response.success is False
    assert response.order_no is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/execution/test_models.py -v`
Expected: FAIL with "cannot import name 'OrderRequest'"

**Step 3: Write minimal implementation**

```python
# shared/execution/models.py
"""Order execution models."""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enumeration.

    KIS API order type codes:
    - 00: 지정가
    - 01: 시장가
    - 02: 조건부지정가
    """
    LIMIT = "00"      # 지정가
    MARKET = "01"     # 시장가
    CONDITIONAL = "02"  # 조건부지정가


class OrderRequest(BaseModel):
    """Order request model."""

    code: str = Field(..., description="Stock/futures code")
    side: OrderSide = Field(..., description="BUY or SELL")
    order_type: OrderType = Field(default=OrderType.MARKET, description="Order type")
    quantity: int = Field(..., gt=0, description="Order quantity")
    price: Optional[float] = Field(default=None, description="Limit price (required for LIMIT orders)")

    class Config:
        use_enum_values = True


class OrderResponse(BaseModel):
    """Order response model."""

    success: bool = Field(..., description="Whether order was successful")
    order_no: Optional[str] = Field(default=None, description="Order number if successful")
    message: str = Field(default="", description="Response message")
    filled_qty: int = Field(default=0, description="Filled quantity")
    filled_price: float = Field(default=0.0, description="Average fill price")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/execution/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/execution/models.py tests/unit/execution/test_models.py
git commit -m "feat(execution): add OrderRequest and OrderResponse models

- OrderSide, OrderType enums matching KIS API
- OrderRequest with validation
- OrderResponse with fill information"
```

---

## Task 9: Order Executor - Core Executor

**Files:**
- Create: `shared/execution/executor.py`
- Test: `tests/unit/execution/test_executor.py`

**Step 1: Write the failing test**

```python
# tests/unit/execution/test_executor.py
"""Test order executor."""
import pytest
from unittest.mock import Mock, AsyncMock, patch


@pytest.mark.asyncio
async def test_executor_paper_mode():
    """Test paper trading mode simulates orders."""
    from shared.execution.executor import OrderExecutor
    from shared.execution.config import ExecutionConfig
    from shared.execution.models import OrderRequest, OrderSide, OrderType

    config = ExecutionConfig(trading_mode="PAPER")
    executor = OrderExecutor(config)

    order = OrderRequest(
        code="005930",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
    )

    response = await executor.execute_order(order)

    assert response.success is True
    assert response.order_no is not None


@pytest.mark.asyncio
async def test_executor_initialize_cleanup():
    """Test session lifecycle."""
    from shared.execution.executor import OrderExecutor
    from shared.execution.config import ExecutionConfig

    config = ExecutionConfig(trading_mode="PAPER")
    executor = OrderExecutor(config)

    await executor.initialize()
    assert executor._initialized is True

    await executor.cleanup()
    assert executor.session is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/execution/test_executor.py -v`
Expected: FAIL with "cannot import name 'OrderExecutor'"

**Step 3: Write minimal implementation**

```python
# shared/execution/executor.py
"""Order execution engine."""
import asyncio
import logging
import uuid
from typing import Optional
from datetime import datetime

import aiohttp

from .config import ExecutionConfig, TradingMode
from .models import OrderRequest, OrderResponse, OrderSide

logger = logging.getLogger(__name__)


class OrderExecutor:
    """Order execution engine.

    Handles order routing to KIS API with:
    - Multiple trading modes (PAPER, MOCK, REAL)
    - Automatic retry on failure
    - Rate limiting
    """

    def __init__(
        self,
        config: ExecutionConfig,
        auth_manager=None,
        notifier=None,
    ):
        self.config = config
        self.auth_manager = auth_manager
        self.notifier = notifier

        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self._initialized = False

        # Account parsing
        self.account_prefix = ""
        self.account_suffix = ""
        if config.account_no and len(config.account_no) >= 10:
            self.account_prefix = config.account_no[:8]
            self.account_suffix = config.account_no[8:10]

    async def initialize(self) -> None:
        """Initialize HTTP session."""
        if not self._initialized:
            self.session = aiohttp.ClientSession()
            self._initialized = True
            logger.debug("OrderExecutor initialized")

    async def cleanup(self) -> None:
        """Cleanup HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
        self._initialized = False
        logger.debug("OrderExecutor cleaned up")

    async def execute_order(self, order: OrderRequest) -> OrderResponse:
        """Execute order with retry logic.

        Args:
            order: Order request

        Returns:
            OrderResponse with result
        """
        for attempt in range(self.config.max_retries):
            try:
                response = await self._send_order(order)
                if response.success:
                    await self._log_success(order, response)
                    return response

                logger.warning(f"Order attempt {attempt + 1} failed: {response.message}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)

            except Exception as e:
                logger.error(f"Order attempt {attempt + 1} exception: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    return OrderResponse(success=False, message=str(e))

        return OrderResponse(
            success=False,
            message=f"Failed after {self.config.max_retries} retries"
        )

    async def _send_order(self, order: OrderRequest) -> OrderResponse:
        """Send order based on trading mode."""
        mode = self.config.trading_mode

        if mode == TradingMode.PAPER.value:
            return await self._simulate_order(order)
        elif mode == TradingMode.MOCK.value:
            return await self._send_kis_order(order, is_mock=True)
        elif mode == TradingMode.REAL.value:
            return await self._send_kis_order(order, is_mock=False)
        else:
            return OrderResponse(success=False, message=f"Unknown mode: {mode}")

    async def _simulate_order(self, order: OrderRequest) -> OrderResponse:
        """Simulate order for paper trading."""
        # Generate fake order number
        order_no = f"PAPER-{uuid.uuid4().hex[:8].upper()}"

        logger.info(
            f"[PAPER] Order simulated: {order.side.value} {order.code} "
            f"x{order.quantity} @ {order.price or 'MARKET'}"
        )

        return OrderResponse(
            success=True,
            order_no=order_no,
            message="Paper order simulated",
            filled_qty=order.quantity,
        )

    async def _send_kis_order(self, order: OrderRequest, is_mock: bool) -> OrderResponse:
        """Send order to KIS API."""
        if not self.auth_manager:
            return OrderResponse(success=False, message="Auth manager not configured")

        if not self.session:
            await self.initialize()

        # Get auth headers
        headers = await self.auth_manager.get_auth_headers()

        # Determine TR code
        if order.side == OrderSide.BUY:
            tr_id = "VTTC0802U" if is_mock else "TTTC0802U"
        else:
            tr_id = "VTTC0801U" if is_mock else "TTTC0801U"

        headers["tr_id"] = tr_id

        # Build request body
        body = {
            "CANO": self.account_prefix,
            "ACNT_PRDT_CD": self.account_suffix,
            "PDNO": order.code,
            "ORD_DVSN": order.order_type.value,
            "ORD_QTY": str(order.quantity),
            "ORD_UNPR": str(int(order.price)) if order.price else "0",
        }

        # Send request
        base_url = "https://openapivts.koreainvestment.com:29443" if is_mock else "https://openapi.koreainvestment.com:9443"
        url = f"{base_url}/uapi/domestic-stock/v1/trading/order-cash"

        try:
            async with self.session.post(url, headers=headers, json=body) as response:
                data = await response.json()

                if response.status == 200 and data.get("rt_cd") == "0":
                    return OrderResponse(
                        success=True,
                        order_no=data.get("output", {}).get("ODNO"),
                        message=data.get("msg1", "Success"),
                    )
                else:
                    return OrderResponse(
                        success=False,
                        message=f"[{data.get('rt_cd')}] {data.get('msg1', 'Unknown error')}",
                    )
        except Exception as e:
            logger.error(f"KIS order error: {e}")
            raise

    async def _log_success(self, order: OrderRequest, response: OrderResponse) -> None:
        """Log successful order."""
        logger.info(
            f"Order executed: {order.side.value} {order.code} x{order.quantity} "
            f"-> {response.order_no}"
        )

        if self.notifier:
            await self.notifier.send_message(
                f"Order Executed: {order.side.value} {order.code} x{order.quantity}"
            )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/execution/test_executor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/execution/executor.py tests/unit/execution/test_executor.py
git commit -m "feat(execution): add OrderExecutor with multi-mode support

- PAPER mode for local simulation
- MOCK mode for KIS 모의투자
- REAL mode for KIS 실전투자
- Retry logic with configurable attempts"
```

---

## Task 10: Position Manager - Position Model Enhancement

**Files:**
- Modify: `shared/models/position.py`
- Test: `tests/unit/models/test_position_enhanced.py`

**Step 1: Write the failing test**

```python
# tests/unit/models/test_position_enhanced.py
"""Test enhanced Position model."""
import pytest
from datetime import datetime


def test_position_state_transitions():
    """Test position state transitions."""
    from shared.models.position import Position, PositionState

    pos = Position(
        id="pos-001",
        code="005930",
        name="Samsung",
        side="BUY",
        entry_price=58000.0,
        quantity=10,
        entry_time=datetime.now(),
        strategy="bb_reversion",
    )

    assert pos.state == PositionState.SURVIVAL

    # Simulate price increase to trigger breakeven
    pos.update_price(59200.0)  # +2.07%

    # State should transition
    assert pos.profit_rate > 0.02


def test_position_profit_calculation():
    """Test P&L calculations."""
    from shared.models.position import Position

    pos = Position(
        id="pos-001",
        code="005930",
        name="Samsung",
        side="BUY",
        entry_price=58000.0,
        quantity=10,
        entry_time=datetime.now(),
        strategy="test",
    )

    pos.update_price(59000.0)

    assert pos.current_price == 59000.0
    assert pos.profit_rate == pytest.approx(0.01724, rel=0.01)
    assert pos.unrealized_pnl == pytest.approx(10000.0, rel=0.01)


def test_position_highest_price_tracking():
    """Test highest price tracking for trailing stop."""
    from shared.models.position import Position

    pos = Position(
        id="pos-001",
        code="005930",
        name="Samsung",
        side="BUY",
        entry_price=58000.0,
        quantity=10,
        entry_time=datetime.now(),
        strategy="test",
    )

    pos.update_price(59000.0)
    pos.update_price(60000.0)
    pos.update_price(59500.0)  # Drops but highest should stay

    assert pos.highest_price == 60000.0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/models/test_position_enhanced.py -v`
Expected: FAIL (missing state machine and price tracking)

**Step 3: Read current position.py and enhance it**

First, let me check the existing position model:

```python
# This step requires reading the file first, then editing
```

**Step 4: Commit after implementation**

```bash
git add shared/models/position.py tests/unit/models/test_position_enhanced.py
git commit -m "feat(models): enhance Position with state machine and price tracking

- Add PositionState enum (SURVIVAL, BREAKEVEN, MAXIMIZE)
- Add highest_price tracking for trailing stops
- Add profit_rate and unrealized_pnl calculations"
```

---

## Remaining Tasks (Summary)

The following tasks follow the same TDD pattern:

### Task 11-15: Position Manager Module
- **Task 11**: PositionMonitor class (async monitoring loop)
- **Task 12**: Exit condition checking (3-Stage state machine)
- **Task 13**: PositionManager class (manages multiple positions)
- **Task 14**: Position restoration from database
- **Task 15**: Integration with OrderExecutor

### Task 16-20: Trading Orchestrator
- **Task 16**: OrchestratorConfig and state enum
- **Task 17**: Component initialization
- **Task 18**: Trading loop (market hours detection)
- **Task 19**: Position tracking and signal processing
- **Task 20**: Graceful shutdown and crash recovery

### Task 21-25: Integration & CLI
- **Task 21**: CLI commands for data collection
- **Task 22**: CLI commands for trading control
- **Task 23**: Health check endpoints
- **Task 24**: Integration tests
- **Task 25**: Documentation update

---

## Dependencies

```
# Add to pyproject.toml
clickhouse-driver>=0.2.6
aiohttp>=3.9.0
redis>=5.0.0
```

---

## Testing Commands

```bash
# Run all Phase 1 tests
pytest tests/unit/db/ tests/unit/collector/ tests/unit/execution/ -v

# Run with coverage
pytest tests/unit/ --cov=shared --cov-report=html

# Integration tests (requires running services)
pytest tests/integration/ -v --tb=short
```

---

## Notes

1. **No hardcoding**: All configuration values come from YAML files or environment variables
2. **TDD approach**: Write failing test → implement → verify → commit
3. **Async by default**: All I/O operations use async/await
4. **Registry pattern**: Components are registered for dependency injection
5. **Graceful degradation**: Components handle failures without crashing

---

**Created:** 2026-01-20
**Author:** Migration Plan Generator
