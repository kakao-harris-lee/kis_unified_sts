"""ClickHouse client with singleton pattern."""
import logging
import asyncio
import ssl
import threading
from typing import Optional, List, AsyncGenerator, ClassVar, TYPE_CHECKING
from datetime import date, datetime

from clickhouse_driver import Client as SyncClient
try:
    from aiochclient import ChClient
    from aiohttp import ClientSession, TCPConnector
    HAS_ASYNC = True
except ImportError:
    HAS_ASYNC = False
    if TYPE_CHECKING:
        from aiochclient import ChClient
        from aiohttp import ClientSession, TCPConnector

from .config import ClickHouseConfig
from .models import DailyCandle, MinuteCandle
from shared.monitoring.drift_metrics import DriftMetrics

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
    "swing_positions": """
        CREATE TABLE IF NOT EXISTS {database}.swing_positions (
            id String,
            code String,
            name String,
            entry_date DateTime,
            entry_price Float64,
            quantity Int32,
            strategy String,
            stop_loss_price Float64,
            high_since_entry Float64,
            current_state String,
            is_open Bool,
            exit_date Nullable(DateTime),
            exit_price Nullable(Float64),
            exit_reason Nullable(String),
            pnl Nullable(Float64),
            side String DEFAULT 'long',
            fee_rate Float64 DEFAULT 0.003,
            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (code, entry_date, id)
        COMMENT 'Swing position state for multi-day strategies (volume_accumulation)'
    """,
    "rl_trades": """
        CREATE TABLE IF NOT EXISTS {database}.rl_trades (
            id String,
            asset_class LowCardinality(String),
            code String,
            name String,
            side LowCardinality(String),
            strategy LowCardinality(String),
            entry_date DateTime,
            entry_price Float64,
            exit_date DateTime,
            exit_price Float64,
            quantity Int32,
            pnl Float64,
            pnl_pct Float64,
            hold_seconds UInt32,
            exit_reason String,
            metadata_json String,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(exit_date)
        ORDER BY (asset_class, strategy, exit_date, id)
        TTL exit_date + INTERVAL 180 DAY
        COMMENT 'Closed RL trade records for performance analytics'
    """,
    "rl_drift_metrics": """
        CREATE TABLE IF NOT EXISTS {database}.rl_drift_metrics (
            timestamp DateTime,
            code String,
            strategy LowCardinality(String),
            kl_divergence Float64,
            psi_score Float64,
            confidence_mean Float64,
            confidence_std Float64,
            sharpe_5d Nullable(Float64),
            sharpe_20d Nullable(Float64),
            win_rate_5d Nullable(Float64),
            win_rate_20d Nullable(Float64),
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (strategy, timestamp)
        TTL timestamp + INTERVAL 180 DAY
        COMMENT 'RL model drift detection metrics for production monitoring'
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


def _daily_candle_to_tuple(candle: DailyCandle) -> tuple:
    return (
        candle.code,
        candle.date,
        candle.open,
        candle.high,
        candle.low,
        candle.close,
        candle.volume,
        candle.value,
        candle.change_rate,
    )


def _minute_candle_to_tuple(candle: MinuteCandle) -> tuple:
    return (
        candle.code,
        candle.datetime,
        candle.open,
        candle.high,
        candle.low,
        candle.close,
        candle.volume,
        candle.value,
    )


def _daily_candle_from_row(row: tuple) -> DailyCandle:
    return DailyCandle(
        code=row[0],
        date=row[1],
        open=row[2],
        high=row[3],
        low=row[4],
        close=row[5],
        volume=row[6],
        value=row[7],
        change_rate=row[8],
    )


def _minute_candle_from_row(row: tuple) -> MinuteCandle:
    return MinuteCandle(
        code=row[0],
        datetime=row[1],
        open=row[2],
        high=row[3],
        low=row[4],
        close=row[5],
        volume=row[6],
        value=row[7],
    )


def _drift_metrics_to_tuple(metrics: DriftMetrics) -> tuple:
    return (
        metrics.timestamp,
        metrics.code,
        metrics.strategy,
        metrics.kl_divergence,
        metrics.psi_score,
        metrics.confidence_mean,
        metrics.confidence_std,
        metrics.sharpe_5d,
        metrics.sharpe_20d,
        metrics.win_rate_5d,
        metrics.win_rate_20d,
    )


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

    def _build_connection_params(self) -> dict:
        """Build connection parameters including TLS settings.

        Returns:
            dict: Connection parameters for SyncClient
        """
        params = {
            "host": self.config.host,
            "port": self.config.port,
            "user": self.config.user,
            "password": self.config.password,
            "database": self.config.database,
            "connect_timeout": self.config.connect_timeout,
        }

        # Add TLS settings if enabled
        if self.config.secure:
            params["secure"] = True
            params["verify"] = self.config.verify_ssl

            # Add certificate paths if provided
            if self.config.ca_cert:
                params["ca_certs"] = self.config.ca_cert
            if self.config.client_cert:
                params["certfile"] = self.config.client_cert
            if self.config.client_key:
                params["keyfile"] = self.config.client_key

        return params

    def get_sync_client(self) -> SyncClient:
        """Get or create sync client."""
        if self._sync_client is None:
            params = self._build_connection_params()
            self._sync_client = SyncClient(**params)
            protocol = "TLS" if self.config.secure else "plain"
            logger.info(f"Connected to ClickHouse (Sync, {protocol}): {self.config.host}:{self.config.port}")
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
            # Build connection params without database
            temp_params = self._build_connection_params()
            temp_params.pop("database", None)  # Remove database from params
            temp_client = SyncClient(**temp_params)
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
            data = [_daily_candle_to_tuple(c) for c in candles]
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
            return [_daily_candle_from_row(r) for r in result]
        except Exception as e:
            logger.error(f"Failed to get daily candles: {e}")
            return []

    def insert_minute_candles(self, candles: List[MinuteCandle]) -> int:
        if not candles:
            return 0
        try:
            client = self.get_sync_client()
            data = [_minute_candle_to_tuple(c) for c in candles]
            client.execute(
                f"INSERT INTO {self.config.database}.minute_candles "
                "(code, datetime, open, high, low, close, volume, value) VALUES",
                data
            )
            return len(candles)
        except Exception as e:
            logger.error(f"Failed to insert minute candles: {e}")
            return 0

    def insert_drift_metrics(self, metrics: List[DriftMetrics]) -> int:
        """Batch insert drift metrics."""
        if not metrics:
            return 0
        try:
            client = self.get_sync_client()
            data = [_drift_metrics_to_tuple(m) for m in metrics]
            client.execute(
                f"INSERT INTO {self.config.database}.rl_drift_metrics "
                "(timestamp, code, strategy, kl_divergence, psi_score, confidence_mean, "
                "confidence_std, sharpe_5d, sharpe_20d, win_rate_5d, win_rate_20d) VALUES",
                data
            )
            return len(metrics)
        except Exception as e:
            logger.error(f"Failed to insert drift metrics: {e}")
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
            return [_minute_candle_from_row(r) for r in result]
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
        self._initialized: bool = False

    def _build_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Build SSL context for async client.

        Returns:
            ssl.SSLContext if TLS is enabled, None otherwise
        """
        if not self.config.secure:
            return None

        # Create SSL context
        ssl_context = ssl.create_default_context()

        # Configure certificate verification
        if not self.config.verify_ssl:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        else:
            ssl_context.verify_mode = ssl.CERT_REQUIRED

        # Load CA certificate if provided
        if self.config.ca_cert:
            ssl_context.load_verify_locations(cafile=self.config.ca_cert)

        # Load client certificate and key for mutual TLS
        if self.config.client_cert and self.config.client_key:
            ssl_context.load_cert_chain(
                certfile=self.config.client_cert,
                keyfile=self.config.client_key
            )

        return ssl_context

    async def connect(self):
        if self._session is None:
            # Build SSL context if TLS is enabled
            ssl_context = self._build_ssl_context()

            # Create connector with SSL context
            connector = TCPConnector(ssl=ssl_context) if ssl_context else None
            session = ClientSession(connector=connector)

            try:
                # Use https:// for secure connections, http:// otherwise
                protocol = "https" if self.config.secure else "http"
                url = f"{protocol}://{self.config.host}:{self.config.http_port}"

                self._client = ChClient(
                    session,
                    url=url,
                    user=self.config.user,
                    password=self.config.password,
                    database=self.config.database,
                )
                self._session = session
                self._initialized = True
                protocol_desc = "HTTPS/TLS" if self.config.secure else "HTTP"
                logger.info(f"Connected to ClickHouse (Async, {protocol_desc}): {self.config.host}:{self.config.http_port}")
            except Exception:
                await session.close()
                raise

    async def close(self) -> None:
        """Close all resources properly."""
        errors = []

        # 1. Close ChClient first (if it has close method)
        if self._client is not None:
            try:
                if hasattr(self._client, 'close'):
                    close_method = self._client.close
                    if asyncio.iscoroutinefunction(close_method):
                        await close_method()
                    else:
                        close_method()
            except Exception as e:
                errors.append(f"ChClient close error: {e}")
            finally:
                self._client = None

        # 2. Close aiohttp session
        if self._session is not None:
            try:
                await self._session.close()
            except Exception as e:
                errors.append(f"Session close error: {e}")
            finally:
                self._session = None

        self._initialized = False

        if errors:
            logger.warning(f"Errors during AsyncClickHouseClient close: {errors}")

    async def __aenter__(self) -> "AsyncClickHouseClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

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
            data = [_daily_candle_to_tuple(c) for c in candles]
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
            return [_daily_candle_from_row(r) for r in result]
        except Exception as e:
            logger.error(f"Async get daily failed: {e}")
            return []

    async def insert_minute_candles(self, candles: List[MinuteCandle]) -> int:
        if not candles:
            return 0
        try:
            client = await self.get_client()
            data = [_minute_candle_to_tuple(c) for c in candles]
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
            return [_minute_candle_from_row(r) for r in result]
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
