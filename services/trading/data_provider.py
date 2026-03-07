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
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from shared.exceptions import APIError, NetworkError, ValidationError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


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

        # Type validation
        if not isinstance(cache_ttl, (int, float)):
            raise TypeError(f"cache_ttl_seconds must be numeric, got {type(cache_ttl)}")
        if not isinstance(batch_size, int):
            raise TypeError(f"batch_size must be int, got {type(batch_size)}")
        if not isinstance(timeout, (int, float)):
            raise TypeError(f"fetch_timeout_seconds must be numeric, got {type(timeout)}")

        return cls(
            cache_ttl_seconds=float(cache_ttl),
            batch_size=int(batch_size),
            fetch_timeout_seconds=float(timeout),
            mock_seed=mock_seed,
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
    ):
        """
        Args:
            symbols: List of stock codes to track
            config: Provider configuration
            kis_client: KIS API client (optional, uses mock if None)
            data_source: Custom data source implementing MarketDataSource protocol
        """
        self.symbols = symbols or []
        self.config = config or DataProviderConfig()
        self._kis_client = kis_client
        self._data_source = data_source

        # Cache: symbol -> MarketDataCache
        self._cache: dict[str, MarketDataCache] = {}
        self._last_batch_fetch: datetime | None = None
        self._lock = asyncio.Lock()

        # Initialize random generator for mock data (with optional seed)
        self._rng = random.Random(self.config.mock_seed)

        logger.info(
            f"MarketDataProvider initialized: {len(self.symbols)} symbols, "
            f"TTL={self.config.cache_ttl_seconds}s"
        )

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

        # Use custom data source if provided (protocol-based)
        if self._data_source is not None:
            try:
                data = await self._fetch_from_source(symbols, self._data_source)
                for symbol, symbol_data in data.items():
                    self._cache[symbol] = MarketDataCache(
                        symbol=symbol,
                        data=symbol_data,
                        fetched_at=now,
                    )
                self._last_batch_fetch = now
                logger.debug(f"Fetched data for {len(symbols)} symbols from data_source")
                return
            except (NetworkError, APIError, ValidationError) as e:
                logger.error(f"Data source fetch failed: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected data source fetch error: {type(e).__name__}: {e}", exc_info=True)

        # Use KIS client if available
        if self._kis_client is not None:
            try:
                data = await self._fetch_from_source(symbols, self._kis_client)
                for symbol, symbol_data in data.items():
                    self._cache[symbol] = MarketDataCache(
                        symbol=symbol,
                        data=symbol_data,
                        fetched_at=now,
                    )
                self._last_batch_fetch = now
                logger.debug(f"Fetched data for {len(symbols)} symbols from KIS")
                return
            except (NetworkError, APIError) as e:
                logger.error(f"KIS fetch failed: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected KIS fetch error: {type(e).__name__}: {e}", exc_info=True)

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
        """Get cache statistics"""
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
        }

    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self._last_batch_fetch = None
        logger.info("Cache cleared")
