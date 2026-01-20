"""ClickHouse client with singleton pattern."""
import logging
from typing import Optional, List
from datetime import date, datetime

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
