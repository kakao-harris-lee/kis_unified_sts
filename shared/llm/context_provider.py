"""LLM Context Provider

Provides cached access to LLM market analysis context from Redis.

The provider reads MarketContext from Redis (published by LLMContextPublisher)
and caches it in memory with TTL-based refresh to minimize Redis round-trips.
Gracefully degrades when LLM context is unavailable.

Usage:
    provider = LLMContextProvider(asset_class="stock")

    # Get cached context (refreshes if stale)
    context = provider.get_context()
    if context:
        print(f"Market regime: {context.regime}")
        print(f"Risk score: {context.risk_score}")
"""

from __future__ import annotations

import logging
import time
from threading import Lock

from shared.streaming.trading_state import TradingStateReader

logger = logging.getLogger(__name__)

# Cache TTL in seconds (60s default)
DEFAULT_CACHE_TTL_SECONDS = 60.0


class LLMContextProvider:
    """Provides cached LLM market context from Redis.

    Reads MarketContext from Redis and caches it in memory with TTL-based
    refresh logic. Thread-safe and gracefully handles Redis failures.

    Attributes:
        asset_class: Asset class (e.g., "stock", "futures")
        cache_ttl_seconds: Cache TTL in seconds (default 60s)

    Example:
        provider = LLMContextProvider("stock")

        # Get context (uses cache if fresh)
        context = provider.get_context()
        if context:
            if context.is_high_risk():
                # Reduce position size
                pass

        # Force refresh from Redis
        context = provider.get_context(force_refresh=True)
    """

    def __init__(
        self,
        asset_class: str,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
    ):
        """Initialize LLM context provider.

        Args:
            asset_class: Asset class identifier ("stock", "futures", etc.)
            cache_ttl_seconds: Cache TTL in seconds (default 60s)
        """
        self._asset_class = asset_class
        self._cache_ttl_seconds = cache_ttl_seconds

        # Thread-safe cache
        self._lock = Lock()
        self._cached_context: object | None = None
        self._cache_timestamp: float = 0.0

        # Redis reader (lazy initialization)
        self._reader: object | None = None

        logger.debug(
            f"LLMContextProvider initialized for {asset_class} "
            f"with cache TTL {cache_ttl_seconds}s"
        )

    def _get_reader(self) -> object:
        """Get or create TradingStateReader instance.

        Returns:
            TradingStateReader instance
        """
        if self._reader is None:
            self._reader = TradingStateReader(self._asset_class)
        return self._reader

    def _is_cache_stale(self) -> bool:
        """Check if cached context is stale.

        Returns:
            True if cache is stale or empty
        """
        if self._cached_context is None:
            return True

        age = time.monotonic() - self._cache_timestamp
        return age > self._cache_ttl_seconds

    def _refresh_from_redis(self) -> object | None:
        """Refresh context from Redis.

        Returns:
            MarketContext instance if available, None otherwise
        """
        try:
            reader = self._get_reader()
            context = reader.get_market_context()

            if context:
                logger.debug(
                    f"Refreshed LLM context for {self._asset_class}: "
                    f"{context.regime}, risk={context.risk_score:.1f}"
                )
            else:
                logger.debug(
                    f"No LLM context available for {self._asset_class} in Redis"
                )

            return context
        except Exception:
            logger.debug(
                f"Failed to refresh LLM context for {self._asset_class}",
                exc_info=True,
            )
            return None

    def get_context(self, force_refresh: bool = False) -> object | None:
        """Get LLM market context with caching.

        Returns cached context if fresh, otherwise refreshes from Redis.
        Thread-safe and gracefully handles failures by returning None.

        Args:
            force_refresh: If True, bypass cache and force refresh from Redis

        Returns:
            MarketContext instance if available, None otherwise

        Example:
            context = provider.get_context()
            if context and context.is_bearish():
                # Skip long entries in bearish regime
                return None
        """
        with self._lock:
            # Return cached context if fresh and not forcing refresh
            if not force_refresh and not self._is_cache_stale():
                return self._cached_context

            # Refresh from Redis
            context = self._refresh_from_redis()

            # Update cache
            self._cached_context = context
            self._cache_timestamp = time.monotonic()

            return context

    def clear_cache(self) -> None:
        """Clear the in-memory cache.

        Forces next get_context() call to refresh from Redis.
        Useful for testing or manual cache invalidation.
        """
        with self._lock:
            self._cached_context = None
            self._cache_timestamp = 0.0
            logger.debug(f"Cleared LLM context cache for {self._asset_class}")

    def get_cache_age(self) -> float | None:
        """Get the age of cached context in seconds.

        Returns:
            Cache age in seconds, or None if cache is empty
        """
        with self._lock:
            if self._cached_context is None:
                return None
            return time.monotonic() - self._cache_timestamp
