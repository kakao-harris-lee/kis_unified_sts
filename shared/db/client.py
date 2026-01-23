"""ClickHouse client with singleton pattern."""
import logging
import asyncio
import threading
from typing import Optional, List, Any, AsyncGenerator, ClassVar, TYPE_CHECKING
from datetime import date, datetime
from dataclasses import astuple

from clickhouse_driver import Client as SyncClient
try:
    from aiochclient import ChClient
    from aiohttp import ClientSession
    HAS_ASYNC = True
except ImportError:
    HAS_ASYNC = False
    if TYPE_CHECKING:
        from aiochclient import ChClient
        from aiohttp import ClientSession

from .config import ClickHouseConfig
from .models import DailyCandle, MinuteCandle, TickData

logger = logging.getLogger(__name__)

# Schema Definitions
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


class ClickHouseClient:
    """Thread-safe singleton ClickHouse client.

    Features:
        - Thread-safe singleton pattern with double-checked locking
        - Sync query support (blocking)
        - Auto table creation

    Thread Safety:
        Uses double-checked locking pattern to prevent race conditions
        during singleton initialization in multi-threaded environments.
    """

    _instance: ClassVar[Optional['ClickHouseClient']] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls, config: ClickHouseConfig = None):
        # First check without lock (fast path)
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking pattern
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self, config: ClickHouseConfig = None):
        # Prevent re-initialization
        if self._initialized:
            return

        with self._lock:
            # Double-check inside lock
            if self._initialized:
                return

            if config is None:
                raise ValueError("Config required for first initialization")

            self.config = config
            self._sync_client: Optional[SyncClient] = None
            self._initialized = True

            logger.info(f"ClickHouseClient (Sync) initialized: {self.config}")

    @classmethod
    def reset_singleton(cls) -> None:
        """Reset singleton instance (for testing only).

        Warning:
            This method is intended for testing purposes only.
            Do not use in production code.
        """
        with cls._lock:
            if cls._instance is not None:
                # Cleanup existing instance
                try:
                    cls._instance.disconnect()
                except Exception as e:
                    logger.warning(f"Error during singleton cleanup: {e}")
            cls._instance = None

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
            logger.info(f"Connected to ClickHouse (Sync): {self.config.host}:{self.config.port}")
        return self._sync_client

    def disconnect(self):
        """Close connection."""
        if self._sync_client:
            self._sync_client.disconnect()
            self._sync_client = None
            logger.info("ClickHouse disconnected")

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
            # Safe because self.config.database is validated in Config
            temp_client.execute(f"CREATE DATABASE IF NOT EXISTS {self.config.database}")
            temp_client.disconnect()

            # Create tables
            client = self.get_sync_client()
            for table_name, schema in SCHEMAS.items():
                client.execute(schema.format(database=self.config.database))
                logger.info(f"Table '{table_name}' ready")

            return True
        except Exception as e:
            logger.error(f"Failed to init schema: {e}")
            return False

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

    def get_minute_candles(self, code: str, start: datetime, end: datetime) -> List[MinuteCandle]:
        try:
            client = self.get_sync_client()
            result = client.execute(
                f"""
                SELECT code, datetime, open, high, low, close, volume, value
                FROM {self.config.database}.minute_candles
                WHERE code = %(code)s AND datetime >= %(start)s AND datetime <= %(end)s
                ORDER BY datetime ASC
                """,
                {"code": code, "start": start, "end": end}
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


class AsyncClickHouseClient:
    """Asynchronous ClickHouse client using aiochclient."""

    def __init__(self, config: ClickHouseConfig = None):
        if not HAS_ASYNC:
            raise ImportError("aiochclient not installed. Please install 'aiochclient' and 'aiohttp'.")
        self.config = config or ClickHouseConfig()
        self._session: Optional[ClientSession] = None
        self._client: Optional[ChClient] = None

    async def connect(self):
        if self._session is None:
            self._session = ClientSession()
            self._client = ChClient(
                self._session,
                url=f"http://{self.config.host}:{self.config.http_port}",
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
            )
            logger.info(f"Connected to ClickHouse (Async): {self.config.host} (HTTP)")

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
            self._client = None

    async def get_client(self):
        """Get or create async client.

        Returns:
            ChClient: The async ClickHouse client instance
        """
        if self._client is None:
            await self.connect()
        return self._client  # type: ignore

    async def insert_daily_candles(self, candles: List[DailyCandle]) -> int:
        if not candles:
            return 0
        try:
            client = await self.get_client()
            # aiochclient uses *args for values
            data = [
                (c.code, c.date, c.open, c.high, c.low, c.close,
                 c.volume, c.value, c.change_rate)
                for c in candles
            ]
            await client.execute(
                f"INSERT INTO {self.config.database}.daily_candles "
                "(code, date, open, high, low, close, volume, value, change_rate) VALUES",
                *data
            )
            return len(candles)
        except Exception as e:
            logger.error(f"Async insert daily failed: {e}")
            return 0

    async def get_daily_candles(self, code: str, start: date, end: date) -> List[DailyCandle]:
        try:
            client = await self.get_client()
            # aiochclient params syntax is {name:Type}
            result = await client.fetch(
                f"""
                SELECT code, date, open, high, low, close, volume, value, change_rate
                FROM {self.config.database}.daily_candles
                WHERE code = {{code:String}} AND date >= {{start:Date}} AND date <= {{end:Date}}
                ORDER BY date ASC
                """,
                {"code": code, "start": start, "end": end}
            )
            return [
                DailyCandle(
                    code=r[0], date=r[1], open=r[2], high=r[3],
                    low=r[4], close=r[5], volume=r[6], value=r[7], change_rate=r[8]
                )
                for r in result
            ]
        except Exception as e:
            logger.error(f"Async get daily failed: {e}")
            return []

    async def insert_minute_candles(self, candles: List[MinuteCandle]) -> int:
        if not candles:
            return 0
        try:
            client = await self.get_client()
            data = [
                (c.code, c.datetime, c.open, c.high, c.low, c.close, c.volume, c.value)
                for c in candles
            ]
            await client.execute(
                f"INSERT INTO {self.config.database}.minute_candles "
                "(code, datetime, open, high, low, close, volume, value) VALUES",
                *data
            )
            return len(candles)
        except Exception as e:
            logger.error(f"Async insert minute failed: {e}")
            return 0

    async def get_minute_candles(self, code: str, start: datetime, end: datetime) -> List[MinuteCandle]:
        try:
            client = await self.get_client()
            result = await client.fetch(
                f"""
                SELECT code, datetime, open, high, low, close, volume, value
                FROM {self.config.database}.minute_candles
                WHERE code = {{code:String}} AND datetime >= {{start:DateTime}} AND datetime <= {{end:DateTime}}
                ORDER BY datetime ASC
                """,
                {"code": code, "start": start, "end": end}
            )
            return [
                MinuteCandle(
                    code=r[0], datetime=r[1], open=r[2], high=r[3],
                    low=r[4], close=r[5], volume=r[6], value=r[7]
                )
                for r in result
            ]
        except Exception as e:
            logger.error(f"Async get minute failed: {e}")
            return []


# Factory function for legacy sync singleton
_client_instance: Optional[ClickHouseClient] = None

def get_clickhouse_client(config: ClickHouseConfig = None) -> ClickHouseClient:
    """Get ClickHouse client singleton (Sync)."""
    global _client_instance
    if _client_instance is None:
        _client_instance = ClickHouseClient(config)
    return _client_instance

# FastAPI dependency factory
async def get_async_db(config: ClickHouseConfig = None) -> AsyncGenerator[AsyncClickHouseClient, None]:
    """Dependency for FastAPI.

    Usage:
        @router.get("/")
        async def handler(db: AsyncClickHouseClient = Depends(get_async_db)):
            ...
    """
    client = AsyncClickHouseClient(config)
    try:
        await client.connect()
        yield client
    finally:
        await client.close()
