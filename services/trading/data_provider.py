"""Market Data Provider

Shared market data fetching with caching for trading strategies.

Fetches data once per interval, caches for all strategies to share.
Reduces API calls while providing fresh data.

Usage:
    provider = MarketDataProvider(symbols=["005930", "000660"])

    # Get cached data (fetches if stale)
    data = await provider.get_data()

    # Get data with indicators
    data = await provider.get_with_indicators("005930", ["rsi", "bb_lower"])
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from shared.exceptions import APIError, NetworkError, ValidationError
from shared.notification.telegram import TelegramNotifier

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DataSourceMode(Enum):
    """Data source operational mode for failover state machine"""

    WEBSOCKET = "websocket"
    REST_FALLBACK = "rest_fallback"


# Validation constants
MIN_CACHE_TTL_SECONDS = 0.1
MAX_CACHE_TTL_SECONDS = 300.0
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 100
MIN_TIMEOUT_SECONDS = 0.5
MAX_TIMEOUT_SECONDS = 60.0


@runtime_checkable
class MarketDataSource(Protocol):
    """Protocol for market data sources (KIS, mock, etc.)

    Implement this protocol to create custom data sources.

    Example:
        class CustomDataSource:
            async def get_current_price(self, symbol: str) -> dict[str, Any]:
                return {"close": 50000, "volume": 1000}

        provider = MarketDataProvider(
            symbols=["005930"],
            data_source=CustomDataSource(),
        )
    """

    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        """Fetch current price for a symbol."""
        ...


@dataclass
class DataProviderConfig:
    """Data provider configuration"""

    # Cache TTL in seconds
    cache_ttl_seconds: float = 1.0

    # Maximum symbols per batch request
    batch_size: int = 20

    # Timeout for data fetch
    fetch_timeout_seconds: float = 5.0

    # Stagger delay between requests in a batch (seconds)
    stagger_delay_seconds: float = 0.1

    # Mock data seed for reproducibility (None = random)
    mock_seed: int | None = None

    # Failover: Health check interval in seconds
    health_check_interval_seconds: float = 5.0

    # Failover: REST polling interval in seconds (when in fallback mode)
    rest_poll_interval_seconds: float = 5.0

    # Failover: Data staleness threshold in seconds (trigger failover if no data)
    staleness_threshold_seconds: float = 10.0

    # Failover: Send Telegram alerts on failover/recovery
    send_telegram_alerts: bool = True

    def __post_init__(self):
        """Validate configuration values."""
        self._validate()

    def _validate(self):
        """Validate all configuration parameters."""
        if not (MIN_CACHE_TTL_SECONDS <= self.cache_ttl_seconds <= MAX_CACHE_TTL_SECONDS):
            raise ValueError(
                f"cache_ttl_seconds must be between {MIN_CACHE_TTL_SECONDS} "
                f"and {MAX_CACHE_TTL_SECONDS}, got {self.cache_ttl_seconds}"
            )

        if not (MIN_BATCH_SIZE <= self.batch_size <= MAX_BATCH_SIZE):
            raise ValueError(
                f"batch_size must be between {MIN_BATCH_SIZE} "
                f"and {MAX_BATCH_SIZE}, got {self.batch_size}"
            )

        if not (MIN_TIMEOUT_SECONDS <= self.fetch_timeout_seconds <= MAX_TIMEOUT_SECONDS):
            raise ValueError(
                f"fetch_timeout_seconds must be between {MIN_TIMEOUT_SECONDS} "
                f"and {MAX_TIMEOUT_SECONDS}, got {self.fetch_timeout_seconds}"
            )

        if self.mock_seed is not None and not isinstance(self.mock_seed, int):
            raise TypeError(f"mock_seed must be int or None, got {type(self.mock_seed)}")

        if not (MIN_TIMEOUT_SECONDS <= self.health_check_interval_seconds <= MAX_TIMEOUT_SECONDS):
            raise ValueError(
                f"health_check_interval_seconds must be between {MIN_TIMEOUT_SECONDS} "
                f"and {MAX_TIMEOUT_SECONDS}, got {self.health_check_interval_seconds}"
            )

        if not (MIN_CACHE_TTL_SECONDS <= self.rest_poll_interval_seconds <= MAX_CACHE_TTL_SECONDS):
            raise ValueError(
                f"rest_poll_interval_seconds must be between {MIN_CACHE_TTL_SECONDS} "
                f"and {MAX_CACHE_TTL_SECONDS}, got {self.rest_poll_interval_seconds}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DataProviderConfig:
        """Create config from dict with validation.

        Args:
            data: Configuration dictionary

        Returns:
            Validated DataProviderConfig

        Raises:
            ValueError: If validation fails
            TypeError: If type validation fails
        """
        cache_ttl = data.get("cache_ttl_seconds", 1.0)
        batch_size = data.get("batch_size", 20)
        timeout = data.get("fetch_timeout_seconds", 5.0)
        mock_seed = data.get("mock_seed")
        health_check_interval = data.get("health_check_interval_seconds", 5.0)
        rest_poll_interval = data.get("rest_poll_interval_seconds", 5.0)
        send_telegram_alerts = data.get("send_telegram_alerts", True)

        # Type validation
        if not isinstance(cache_ttl, (int, float)):
            raise TypeError(f"cache_ttl_seconds must be numeric, got {type(cache_ttl)}")
        if not isinstance(batch_size, int):
            raise TypeError(f"batch_size must be int, got {type(batch_size)}")
        if not isinstance(timeout, (int, float)):
            raise TypeError(f"fetch_timeout_seconds must be numeric, got {type(timeout)}")
        if not isinstance(health_check_interval, (int, float)):
            raise TypeError(f"health_check_interval_seconds must be numeric, got {type(health_check_interval)}")
        if not isinstance(rest_poll_interval, (int, float)):
            raise TypeError(f"rest_poll_interval_seconds must be numeric, got {type(rest_poll_interval)}")
        if not isinstance(send_telegram_alerts, bool):
            raise TypeError(f"send_telegram_alerts must be bool, got {type(send_telegram_alerts)}")

        return cls(
            cache_ttl_seconds=float(cache_ttl),
            batch_size=int(batch_size),
            fetch_timeout_seconds=float(timeout),
            mock_seed=mock_seed,
            health_check_interval_seconds=float(health_check_interval),
            rest_poll_interval_seconds=float(rest_poll_interval),
            send_telegram_alerts=bool(send_telegram_alerts),
        )


@dataclass
class MarketDataCache:
    """Cached market data for a symbol"""

    symbol: str
    data: dict[str, Any]
    fetched_at: datetime
    indicators: dict[str, float] = field(default_factory=dict)

    def is_stale(self, ttl_seconds: float) -> bool:
        """Check if cache is stale"""
        age = (datetime.now() - self.fetched_at).total_seconds()
        return age > ttl_seconds


class MarketDataProvider:
    """Market data provider with caching

    Fetches market data for configured symbols and caches results.
    Multiple strategies can share the same data without redundant API calls.

    Usage:
        provider = MarketDataProvider(
            symbols=["005930", "000660"],
            config=DataProviderConfig(cache_ttl_seconds=1.0),
        )

        # Fetch data (uses cache if fresh)
        data = await provider.get_data()
        # Returns: {"005930": {"close": 71000, "volume": 1000000, ...}, ...}

        # Force refresh
        data = await provider.get_data(force_refresh=True)

        # With custom data source (protocol-based)
        provider = MarketDataProvider(
            symbols=["005930"],
            data_source=CustomDataSource(),  # Implements MarketDataSource protocol
        )
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        config: DataProviderConfig | None = None,
        kis_client: Any | None = None,
        data_source: MarketDataSource | None = None,
        telegram_notifier: TelegramNotifier | None = None,
    ):
        """
        Args:
            symbols: List of stock codes to track
            config: Provider configuration
            kis_client: KIS API client (optional, uses mock if None)
            data_source: Custom data source implementing MarketDataSource protocol
            telegram_notifier: Telegram notifier for failover alerts (optional)
        """
        self.symbols = symbols or []
        self.config = config or DataProviderConfig()
        self._kis_client = kis_client
        self._data_source = data_source
        self._telegram_notifier = telegram_notifier

        # Cache: symbol -> MarketDataCache
        self._cache: dict[str, MarketDataCache] = {}
        self._last_batch_fetch: datetime | None = None
        self._lock = asyncio.Lock()

        # Initialize random generator for mock data (with optional seed)
        self._rng = random.Random(self.config.mock_seed)

        # Failover state machine
        self._current_mode: DataSourceMode = DataSourceMode.WEBSOCKET
        self._fallback_poll_task: asyncio.Task[None] | None = None
        self._health_check_task: asyncio.Task[None] | None = None

        logger.info(
            f"MarketDataProvider initialized: {len(self.symbols)} symbols, "
            f"TTL={self.config.cache_ttl_seconds}s, mode={self._current_mode.value}"
        )

    async def start_background_tasks(self) -> None:
        """Start background health monitoring for WebSocket failover.

        Starts the health check loop only when a WebSocket-style data source is
        available and exposes health-related hooks. Calling this method multiple
        times is safe.
        """
        if self._data_source is None:
            logger.debug("Failover monitoring skipped: no primary data source configured")
            return

        supports_health_monitoring = any(
            hasattr(self._data_source, attr)
            for attr in ("is_healthy", "get_health_status")
        )
        if not supports_health_monitoring:
            logger.debug(
                "Failover monitoring skipped: data source has no health hooks"
            )
            return

        if self._health_check_task is not None and not self._health_check_task.done():
            logger.debug("Failover health check already running")
            return

        self._health_check_task = asyncio.create_task(
            self._health_check_loop(),
            name="market_data_provider_health_check",
        )
        logger.info("Started MarketDataProvider failover health monitoring")

    async def stop_background_tasks(self) -> None:
        """Stop health monitoring and fallback polling tasks.

        This is used during orchestrator shutdown to avoid false failover events
        while feeds are intentionally being torn down.
        """
        tasks: list[asyncio.Task[None]] = []

        if self._health_check_task is not None and not self._health_check_task.done():
            self._health_check_task.cancel()
            tasks.append(self._health_check_task)

        if self._fallback_poll_task is not None and not self._fallback_poll_task.done():
            self._fallback_poll_task.cancel()
            tasks.append(self._fallback_poll_task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._health_check_task = None
        self._fallback_poll_task = None
        self._current_mode = DataSourceMode.WEBSOCKET
        logger.info("Stopped MarketDataProvider background tasks")

    @property
    def current_mode(self) -> DataSourceMode:
        """Get current data source mode (WEBSOCKET or REST_FALLBACK)"""
        return self._current_mode

    @property
    def is_in_failover_mode(self) -> bool:
        """Check if currently in REST fallback mode"""
        return self._current_mode == DataSourceMode.REST_FALLBACK

    def add_symbols(self, symbols: list[str]):
        """Add symbols to track"""
        for symbol in symbols:
            if symbol not in self.symbols:
                self.symbols.append(symbol)
                logger.debug(f"Added symbol: {symbol}")

    def remove_symbol(self, symbol: str):
        """Remove symbol from tracking"""
        if symbol in self.symbols:
            self.symbols.remove(symbol)
            self._cache.pop(symbol, None)

    async def get_data(
        self,
        symbols: list[str] | None = None,
        force_refresh: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """Get market data for symbols

        Args:
            symbols: Specific symbols to fetch (None = all tracked)
            force_refresh: Force cache refresh

        Returns:
            Dict mapping symbol to market data
            {"005930": {"close": 71000, "open": 70500, "high": 71500, ...}}
        """
        target_symbols = symbols or self.symbols

        if not target_symbols:
            return {}

        async with self._lock:
            # Check which symbols need refresh
            stale_symbols = []
            for symbol in target_symbols:
                cache = self._cache.get(symbol)
                if force_refresh or cache is None or cache.is_stale(self.config.cache_ttl_seconds):
                    stale_symbols.append(symbol)

            # Fetch stale data
            if stale_symbols:
                await self._fetch_batch(stale_symbols)

        # Return cached data
        result = {}
        for symbol in target_symbols:
            cache = self._cache.get(symbol)
            if cache:
                result[symbol] = cache.data

        return result

    async def get_single(
        self,
        symbol: str,
        force_refresh: bool = False,
    ) -> dict[str, Any] | None:
        """Get market data for a single symbol"""
        data = await self.get_data([symbol], force_refresh)
        return data.get(symbol)

    async def get_with_indicators(
        self,
        symbol: str,
        indicators: list[str],
    ) -> dict[str, Any]:
        """Get market data with calculated indicators

        Args:
            symbol: Stock code
            indicators: List of indicator names (e.g., ["rsi", "bb_lower"])

        Returns:
            Market data dict with indicator values added
        """
        data = await self.get_single(symbol)
        if not data:
            return {}

        result = dict(data)

        # Add cached indicators if available
        cache = self._cache.get(symbol)
        if cache and cache.indicators:
            for ind_name in indicators:
                if ind_name in cache.indicators:
                    result[ind_name] = cache.indicators[ind_name]

        return result

    def update_indicators(self, symbol: str, indicators: dict[str, float]):
        """Update cached indicators for a symbol

        Called by external indicator calculator.
        """
        cache = self._cache.get(symbol)
        if cache:
            cache.indicators.update(indicators)

    async def _fetch_batch(self, symbols: list[str]):
        """Fetch market data for a batch of symbols"""
        now = datetime.now()

        source_candidates: list[tuple[str, MarketDataSource | Any]] = []
        if self._current_mode == DataSourceMode.REST_FALLBACK:
            # In REST fallback mode, use KIS REST client exclusively
            if self._kis_client is not None:
                source_candidates.append(("kis_client", self._kis_client))
        else:
            # In WEBSOCKET mode, only use the WebSocket data source.
            # Do NOT fall through to kis_client here — doing so would trigger
            # REST API calls on every WS cache miss, causing rate-limit pressure
            # (see commit bba111f). Failover to REST is handled separately by
            # _health_check_loop → _failover_to_rest.
            if self._data_source is not None:
                source_candidates.append(("data_source", self._data_source))
            elif self._kis_client is not None:
                # No WebSocket source configured at all — use REST as primary
                source_candidates.append(("kis_client", self._kis_client))

        for source_name, source in source_candidates:
            try:
                data = await self._fetch_from_source(symbols, source)
                for symbol, symbol_data in data.items():
                    self._cache[symbol] = MarketDataCache(
                        symbol=symbol,
                        data=symbol_data,
                        fetched_at=now,
                    )
                self._last_batch_fetch = now
                logger.debug(
                    "Fetched data for %d symbols from %s (mode=%s)",
                    len(symbols),
                    source_name,
                    self._current_mode.value,
                )
                return
            except (NetworkError, APIError, ValidationError) as e:
                logger.error("%s fetch failed: %s", source_name, e, exc_info=True)
            except Exception as e:
                logger.error(
                    "Unexpected %s fetch error: %s: %s",
                    source_name,
                    type(e).__name__,
                    e,
                    exc_info=True,
                )

        # Fallback: Generate mock data (for testing/paper trading)
        for symbol in symbols:
            self._cache[symbol] = MarketDataCache(
                symbol=symbol,
                data=self._generate_mock_data(symbol),
                fetched_at=now,
            )

        self._last_batch_fetch = now
        logger.debug(f"Generated mock data for {len(symbols)} symbols")

    async def _fetch_from_source(
        self,
        symbols: list[str],
        source: MarketDataSource | Any,
    ) -> dict[str, dict[str, Any]]:
        """Fetch data from source using parallel requests.

        Uses asyncio.gather for parallel API calls within batch limits.

        Args:
            symbols: List of symbols to fetch
            source: Data source with get_current_price method

        Returns:
            Dict mapping symbol to market data
        """
        if not hasattr(source, "get_current_price"):
            raise ValueError("Data source must have get_current_price method")

        result: dict[str, dict[str, Any]] = {}

        supports_parallel = getattr(source, "supports_parallel", True)

        if not supports_parallel:
            for symbol in symbols:
                try:
                    price_data = await asyncio.wait_for(
                        source.get_current_price(symbol),
                        timeout=self.config.fetch_timeout_seconds,
                    )
                    if price_data:
                        result[symbol] = price_data
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout fetching {symbol}")
                except (NetworkError, APIError) as e:
                    logger.warning(f"Error fetching {symbol}: {e}")
            return result

        # Batch fetch in groups (respect API rate limits)
        for i in range(0, len(symbols), self.config.batch_size):
            batch = symbols[i : i + self.config.batch_size]

            # Skip stagger for instant-read sources (e.g. WebSocket cache)
            instant = getattr(source, "supports_instant_read", False)

            # Create tasks with staggered start to avoid KIS API rate limit
            async def fetch_single(symbol: str, idx: int) -> tuple[str, dict[str, Any] | None]:
                try:
                    if idx > 0 and not instant:
                        await asyncio.sleep(idx * self.config.stagger_delay_seconds)
                    price_data = await asyncio.wait_for(
                        source.get_current_price(symbol),
                        timeout=self.config.fetch_timeout_seconds,
                    )
                    return (symbol, price_data)
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout fetching {symbol}")
                    return (symbol, None)
                except (NetworkError, APIError) as e:
                    logger.warning(f"Error fetching {symbol}: {e}")
                    return (symbol, None)

            # Execute fetches in parallel with staggered starts (50ms apart)
            # Prevents KIS "초당 거래건수 초과" rate limit on burst
            tasks = [fetch_single(symbol, idx) for idx, symbol in enumerate(batch)]
            try:
                # Overall timeout is 2x individual timeout to allow for overhead
                batch_timeout = self.config.fetch_timeout_seconds * 2
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=batch_timeout,
                )
            except asyncio.TimeoutError:
                logger.error(f"Batch fetch timeout after {batch_timeout}s for {len(batch)} symbols")
                results = []  # Skip this batch on timeout

            for item in results:
                if isinstance(item, Exception):
                    logger.error(f"Batch fetch error: {item}", exc_info=True)
                    continue
                symbol, data = item
                if data:
                    result[symbol] = data

            # Pause between batches to avoid sustained rate limiting
            if i + self.config.batch_size < len(symbols):
                await asyncio.sleep(1.0)

        return result

    def _generate_mock_data(self, symbol: str) -> dict[str, Any]:
        """Generate mock market data for testing.

        Uses seeded RNG for reproducibility when mock_seed is set.

        Args:
            symbol: Stock symbol

        Returns:
            Mock market data dict
        """
        # Base price varies by symbol (deterministic based on symbol)
        base = hash(symbol) % 100000 + 10000

        return {
            "code": symbol,
            "name": f"Mock-{symbol}",
            "close": base + self._rng.randint(-500, 500),
            "open": base + self._rng.randint(-300, 300),
            "high": base + self._rng.randint(0, 1000),
            "low": base + self._rng.randint(-1000, 0),
            "volume": self._rng.randint(100000, 10000000),
            "change": self._rng.uniform(-0.05, 0.05),
            "timestamp": datetime.now().isoformat(),
        }

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics including failover state"""
        fresh_count = sum(
            1 for c in self._cache.values()
            if not c.is_stale(self.config.cache_ttl_seconds)
        )

        return {
            "total_symbols": len(self.symbols),
            "cached_symbols": len(self._cache),
            "fresh_count": fresh_count,
            "stale_count": len(self._cache) - fresh_count,
            "last_batch_fetch": (
                self._last_batch_fetch.isoformat() if self._last_batch_fetch else None
            ),
            "current_mode": self._current_mode.value,
            "is_in_failover": self.is_in_failover_mode,
            "health_check_active": self._health_check_task is not None and not self._health_check_task.done(),
            "fallback_poll_active": self._fallback_poll_task is not None and not self._fallback_poll_task.done(),
        }

    async def _health_check_loop(self):
        """Health monitoring loop for WebSocket data source.

        Checks data source health at regular intervals and triggers failover
        to REST polling if WebSocket becomes unhealthy.

        The loop checks:
        - If data source has is_healthy() method, call it
        - If data source has get_health_status() method, log detailed status
        - Trigger failover if data source is unhealthy

        This runs continuously until cancelled via task cancellation.
        """
        logger.info(
            f"Starting health check loop (interval: {self.config.health_check_interval_seconds}s)"
        )

        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval_seconds)

                # Check if we're in WebSocket mode (no need to check if in fallback)
                if self._current_mode != DataSourceMode.WEBSOCKET:
                    logger.debug("Health check: in REST fallback mode, checking for recovery")
                    # Check if WebSocket is healthy again for recovery
                    if hasattr(self._data_source, "is_healthy"):
                        try:
                            is_healthy = (
                                await self._data_source.is_healthy()
                                if asyncio.iscoroutinefunction(self._data_source.is_healthy)
                                else self._data_source.is_healthy()
                            )
                            if is_healthy:
                                logger.info("WebSocket is healthy again, attempting recovery")
                                await self._recover_to_websocket()
                        except Exception as e:
                            logger.debug(f"Error checking WebSocket health for recovery: {e}")
                    continue

                # We're in WebSocket mode, check health
                if self._data_source is None:
                    logger.debug("Health check: no data source configured (using mock data)")
                    continue

                # Get detailed health status if available
                health_status = None
                if hasattr(self._data_source, "get_health_status"):
                    try:
                        health_status = (
                            await self._data_source.get_health_status()
                            if asyncio.iscoroutinefunction(self._data_source.get_health_status)
                            else self._data_source.get_health_status()
                        )
                        logger.debug(f"Health check: data source status = {health_status}")
                    except Exception as e:
                        logger.warning(f"Error getting health status: {e}")

                # Check if data source is healthy
                is_healthy = True
                if hasattr(self._data_source, "is_healthy"):
                    try:
                        is_healthy = (
                            await self._data_source.is_healthy()
                            if asyncio.iscoroutinefunction(self._data_source.is_healthy)
                            else self._data_source.is_healthy()
                        )
                        logger.debug(f"Health check: is_healthy = {is_healthy}")
                    except Exception as e:
                        logger.warning(f"Error checking is_healthy: {e}")
                        is_healthy = False

                # Trigger failover if unhealthy
                if not is_healthy:
                    logger.warning(
                        f"Data source unhealthy, triggering failover to REST polling. "
                        f"Health status: {health_status}"
                    )
                    await self._failover_to_rest()

            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in health check loop: {type(e).__name__}: {e}", exc_info=True)
                # Continue checking despite errors

    async def _failover_to_rest(self):
        """Fail over from WebSocket to REST polling mode.

        Called when WebSocket data source becomes unhealthy. Switches to
        REST API polling as a fallback to maintain data availability.

        This method is idempotent - calling it multiple times has no effect
        if already in REST fallback mode.
        """
        # Already in fallback mode, nothing to do
        if self._current_mode == DataSourceMode.REST_FALLBACK:
            logger.debug("Already in REST fallback mode, ignoring failover request")
            return

        logger.warning(
            f"Failing over to REST polling mode "
            f"(interval: {self.config.rest_poll_interval_seconds}s)"
        )

        # Switch mode
        self._current_mode = DataSourceMode.REST_FALLBACK

        # Send Telegram alert if configured
        if self.config.send_telegram_alerts and self._telegram_notifier is not None:
            try:
                await self._telegram_notifier.send_message(
                    f"⚠️ <b>WebSocket Failover</b>\n"
                    f"WebSocket 연결이 끊어져 REST API 모드로 전환합니다.\n"
                    f"Polling 간격: {self.config.rest_poll_interval_seconds}초\n"
                    f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    is_critical=True,
                )
                logger.info("Sent Telegram alert for WebSocket failover")
            except Exception as e:
                # Don't let telegram failures break failover
                logger.error(f"Failed to send Telegram failover alert: {e}", exc_info=False)

        # Create KIS client if not already available
        if self._kis_client is None:
            logger.warning("No KIS client available for REST fallback, using mock data")
            # Fallback will use mock data via _generate_mock_data in _fetch_batch
            return

        # Start REST polling loop task
        # This will be implemented in subtask-2-4
        if self._fallback_poll_task is None or self._fallback_poll_task.done():
            try:
                self._fallback_poll_task = asyncio.create_task(self._rest_poll_loop())
                logger.info("Started REST polling task")
            except Exception as e:
                logger.error(f"Failed to start REST polling task: {e}", exc_info=True)
                # Continue with manual fetches via get_data() if polling task fails

    async def _rest_poll_loop(self):
        """REST polling loop for fallback mode.

        Continuously polls market data via REST API when WebSocket is unavailable.
        This method runs until cancelled or until recovery to WebSocket mode.

        Fetches all tracked symbols using KIS client at regular intervals,
        respecting rate limits and handling errors gracefully.
        """
        logger.info(
            f"Starting REST polling loop (interval: {self.config.rest_poll_interval_seconds}s)"
        )

        while self._current_mode == DataSourceMode.REST_FALLBACK:
            try:
                # Skip polling if no symbols tracked
                if not self.symbols:
                    logger.debug("REST poll cycle: no symbols to fetch")
                    await asyncio.sleep(self.config.rest_poll_interval_seconds)
                    continue

                # Fetch all tracked symbols via KIS client (or data source)
                # This uses existing _fetch_batch which:
                # - Handles rate limiting via staggered requests
                # - Updates cache with fresh data
                # - Falls back to mock data if needed
                logger.debug(f"REST poll cycle: fetching {len(self.symbols)} symbols")

                async with self._lock:
                    await self._fetch_batch(self.symbols)

                logger.debug(
                    f"REST poll cycle: successfully fetched {len(self.symbols)} symbols"
                )

                # Sleep until next poll interval
                await asyncio.sleep(self.config.rest_poll_interval_seconds)

            except asyncio.CancelledError:
                logger.info("REST polling loop cancelled")
                raise
            except (NetworkError, APIError) as e:
                # Expected errors during REST polling - log at warning level
                logger.warning(
                    f"REST polling network/API error: {type(e).__name__}: {e}"
                )
                # Brief pause before retry on error (shorter than normal interval)
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error(
                    f"Unexpected error in REST polling loop: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                # Brief pause before retry on error
                await asyncio.sleep(1.0)

    async def _recover_to_websocket(self):
        """Recover from REST fallback to WebSocket mode.

        Called when WebSocket data source becomes healthy again. Switches back
        to WebSocket mode from REST polling fallback.

        This method is idempotent - calling it multiple times has no effect
        if already in WebSocket mode.
        """
        # Already in WebSocket mode, nothing to do
        if self._current_mode == DataSourceMode.WEBSOCKET:
            logger.debug("Already in WebSocket mode, ignoring recovery request")
            return

        # Verify WebSocket is actually healthy before recovering
        if self._data_source is None:
            logger.warning("Cannot recover to WebSocket: no data source configured")
            return

        # Check if data source is healthy
        is_healthy = False
        if hasattr(self._data_source, "is_healthy"):
            try:
                is_healthy = (
                    await self._data_source.is_healthy()
                    if asyncio.iscoroutinefunction(self._data_source.is_healthy)
                    else self._data_source.is_healthy()
                )
            except Exception as e:
                logger.warning(f"Error checking WebSocket health during recovery: {e}")
                return

        if not is_healthy:
            logger.debug("WebSocket not healthy, cannot recover yet")
            return

        logger.info("Recovering to WebSocket mode from REST fallback")

        # Switch mode (this will stop the REST polling loop via its condition check)
        self._current_mode = DataSourceMode.WEBSOCKET

        # Cancel REST polling task if it's still running
        if self._fallback_poll_task is not None and not self._fallback_poll_task.done():
            try:
                self._fallback_poll_task.cancel()
                # Wait briefly for task to finish cancelling
                try:
                    await asyncio.wait_for(self._fallback_poll_task, timeout=1.0)
                except asyncio.CancelledError:
                    pass
                except asyncio.TimeoutError:
                    logger.warning("REST polling task did not cancel within timeout")
                logger.info("Stopped REST polling task")
            except Exception as e:
                logger.error(f"Error stopping REST polling task: {e}", exc_info=True)

        logger.info("Successfully recovered to WebSocket mode")

        # Send Telegram alert if configured
        if self.config.send_telegram_alerts and self._telegram_notifier is not None:
            try:
                await self._telegram_notifier.send_message(
                    f"✅ <b>WebSocket 복구</b>\n"
                    f"WebSocket 연결이 복구되어 실시간 데이터 피드를 재개합니다.\n"
                    f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    is_critical=True,
                )
                logger.info("Sent Telegram alert for WebSocket recovery")
            except Exception as e:
                # Don't let telegram failures break recovery
                logger.error(f"Failed to send Telegram recovery alert: {e}", exc_info=False)

    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self._last_batch_fetch = None
        logger.info("Cache cleared")
