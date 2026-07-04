"""Runtime fetch/cache/failover methods for MarketDataProvider."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from shared.exceptions import APIError, NetworkError, ValidationError

from .data_provider_models import DataSourceMode, MarketDataCache, MarketDataSource

logger = logging.getLogger("services.trading.data_provider")


class MarketDataProviderRuntimeMixin:
    async def start_background_tasks(self) -> None:
        """Start background health monitoring for WebSocket failover.

        Starts the health check loop only when a WebSocket-style data source is
        available and exposes health-related hooks. Calling this method multiple
        times is safe.
        """
        if self._data_source is None:
            logger.debug(
                "Failover monitoring skipped: no primary data source configured"
            )
            return

        supports_health_monitoring = any(
            hasattr(self._data_source, attr)
            for attr in ("is_healthy", "get_health_status")
        )
        if not supports_health_monitoring:
            logger.debug("Failover monitoring skipped: data source has no health hooks")
            return

        if self._health_check_task is not None and not self._health_check_task.done():
            logger.debug("Failover health check already running")
            return

        self._health_check_task = asyncio.create_task(
            self._health_check_loop(),
            name="market_data_provider_health_check",
        )
        self._health_monitor_started_at = time.monotonic()
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
        self._health_monitor_started_at = None
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
                if (
                    force_refresh
                    or cache is None
                    or cache.is_stale(self.config.cache_ttl_seconds)
                ):
                    stale_symbols.append(symbol)

            # Fetch stale data
            if stale_symbols:
                if not force_refresh:
                    stale_symbols = self._select_fetch_symbols_for_mode(stale_symbols)
                if stale_symbols:
                    await self._fetch_batch(stale_symbols)

        # Return cached data
        result = {}
        for symbol in target_symbols:
            cache = self._cache.get(symbol)
            if cache:
                result[symbol] = cache.data

        return result

    def _select_fetch_symbols_for_mode(self, stale_symbols: list[str]) -> list[str]:
        """Throttle foreground REST fetches while fallback polling is active."""
        if self._current_mode != DataSourceMode.REST_FALLBACK:
            return stale_symbols

        poll_active = (
            self._fallback_poll_task is not None and not self._fallback_poll_task.done()
        )
        if poll_active:
            # The fallback poller owns REST refresh cadence.  Foreground callers
            # should consume cache only; otherwise the market-data loop can race
            # the poller and trip KIS per-second limits.
            return []

        max_symbols = self.config.rest_fallback_max_symbols
        if max_symbols is None or max_symbols >= len(stale_symbols):
            return stale_symbols

        return self._select_rest_poll_symbols(stale_symbols)[:max_symbols]

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

        if source_candidates:
            logger.warning(
                "All configured market data sources failed for %d symbols; preserving existing cache",
                len(symbols),
            )
            return

        # Fallback: Generate mock data only when no real source is configured.
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
                except TimeoutError:
                    logger.warning(f"Timeout fetching {symbol}")
                except (NetworkError, APIError) as e:
                    logger.warning(f"Error fetching {symbol}: {e}")
                except Exception as e:
                    logger.warning(
                        "Unexpected error fetching %s: %s: %s",
                        symbol,
                        type(e).__name__,
                        e,
                    )
            return result

        # Batch fetch in groups (respect API rate limits)
        for i in range(0, len(symbols), self.config.batch_size):
            batch = symbols[i : i + self.config.batch_size]

            # Skip stagger for instant-read sources (e.g. WebSocket cache)
            instant = getattr(source, "supports_instant_read", False)

            # Create tasks with staggered start to avoid KIS API rate limit
            async def fetch_single(
                symbol: str, idx: int, instant: bool = instant
            ) -> tuple[str, dict[str, Any] | None]:
                try:
                    if idx > 0 and not instant:
                        await asyncio.sleep(idx * self.config.stagger_delay_seconds)
                    price_data = await asyncio.wait_for(
                        source.get_current_price(symbol),
                        timeout=self.config.fetch_timeout_seconds,
                    )
                    return (symbol, price_data)
                except TimeoutError:
                    logger.warning(f"Timeout fetching {symbol}")
                    return (symbol, None)
                except (NetworkError, APIError) as e:
                    logger.warning(f"Error fetching {symbol}: {e}")
                    return (symbol, None)
                except Exception as e:
                    logger.warning(
                        "Unexpected error fetching %s: %s: %s",
                        symbol,
                        type(e).__name__,
                        e,
                    )
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
            except TimeoutError:
                logger.error(
                    f"Batch fetch timeout after {batch_timeout}s for {len(batch)} symbols"
                )
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
        current_symbols = list(dict.fromkeys(self.symbols))
        freshness_threshold = self.config.staleness_threshold_seconds
        fresh_count = sum(
            1
            for symbol in current_symbols
            if (
                (cache := self._cache.get(symbol)) is not None
                and not cache.is_stale(freshness_threshold)
            )
        )
        cached_count = sum(1 for symbol in current_symbols if symbol in self._cache)

        return {
            "total_symbols": len(current_symbols),
            "cached_symbols": cached_count,
            "fresh_count": fresh_count,
            "stale_count": len(current_symbols) - fresh_count,
            "cache_entries": len(self._cache),
            "freshness_threshold_seconds": freshness_threshold,
            "last_batch_fetch": (
                self._last_batch_fetch.isoformat() if self._last_batch_fetch else None
            ),
            "current_mode": self._current_mode.value,
            "is_in_failover": self.is_in_failover_mode,
            "health_check_active": self._health_check_task is not None
            and not self._health_check_task.done(),
            "fallback_poll_active": self._fallback_poll_task is not None
            and not self._fallback_poll_task.done(),
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
                    logger.debug(
                        "Health check: in REST fallback mode, checking for recovery"
                    )
                    try:
                        is_healthy, _ = await self._check_data_source_health()
                        if is_healthy:
                            self._consecutive_recovery_checks += 1
                            if (
                                self._consecutive_recovery_checks
                                >= self.config.recovery_healthy_threshold
                            ):
                                logger.info(
                                    "WebSocket healthy for %d/%d checks, "
                                    "attempting recovery",
                                    self._consecutive_recovery_checks,
                                    self.config.recovery_healthy_threshold,
                                )
                                await self._recover_to_websocket()
                                self._consecutive_recovery_checks = 0
                        else:
                            self._consecutive_recovery_checks = 0
                    except Exception as e:
                        self._consecutive_recovery_checks = 0
                        logger.debug(
                            f"Error checking WebSocket health for recovery: {e}"
                        )
                    continue

                # We're in WebSocket mode, check health
                if self._data_source is None:
                    logger.debug(
                        "Health check: no data source configured (using mock data)"
                    )
                    continue

                is_healthy, health_status = await self._check_data_source_health()

                # Trigger failover if unhealthy
                if not is_healthy:
                    self._consecutive_unhealthy_checks += 1
                    if (
                        self._consecutive_unhealthy_checks
                        >= self.config.failover_unhealthy_threshold
                    ):
                        logger.warning(
                            "Data source unhealthy for %d/%d checks, "
                            "triggering failover to REST polling. Health status: %s",
                            self._consecutive_unhealthy_checks,
                            self.config.failover_unhealthy_threshold,
                            health_status,
                        )
                        await self._failover_to_rest()
                        self._consecutive_unhealthy_checks = 0
                    else:
                        logger.info(
                            "Data source unhealthy check %d/%d; waiting before failover. "
                            "Health status: %s",
                            self._consecutive_unhealthy_checks,
                            self.config.failover_unhealthy_threshold,
                            health_status,
                        )
                else:
                    self._consecutive_unhealthy_checks = 0

            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                raise
            except Exception as e:
                logger.error(
                    f"Error in health check loop: {type(e).__name__}: {e}",
                    exc_info=True,
                )

    async def _check_data_source_health(self) -> tuple[bool, dict[str, Any] | None]:
        """Evaluate source health using provider-level failover semantics."""
        if self._data_source is None:
            return True, None

        health_status = await self._get_data_source_health_status()
        if health_status is not None:
            logger.debug(f"Health check: data source status = {health_status}")

            if (
                health_status.get("running") is False
                or health_status.get("connected") is False
            ):
                return False, health_status

            in_grace = self._is_startup_grace_active()
            staleness = health_status.get("staleness_seconds")
            if staleness is None:
                if in_grace:
                    logger.debug(
                        "Failover startup grace active: no tick yet, keeping WebSocket healthy"
                    )
                    return True, health_status
                return False, health_status

            fresh_symbol_count = health_status.get("fresh_symbol_count")
            symbol_count = health_status.get("symbol_count")
            if (
                isinstance(fresh_symbol_count, int)
                and isinstance(symbol_count, int)
                and symbol_count > 0
            ):
                # Hard failure: ALL symbols stale.
                if fresh_symbol_count <= 0:
                    if in_grace:
                        logger.debug(
                            "Failover startup grace active: fresh_ratio=0/%d, "
                            "keeping WebSocket healthy",
                            symbol_count,
                        )
                        return True, health_status
                    return False, health_status
                # Silent-stall guard: too few fresh symbols even though
                # overall `_last_tick_ts` looks recent.  See
                # DataProviderConfig.min_fresh_ratio for context.
                min_ratio = self.config.min_fresh_ratio
                if min_ratio > 0.0:
                    fresh_ratio = fresh_symbol_count / symbol_count
                    if fresh_ratio < min_ratio:
                        if in_grace:
                            logger.debug(
                                "Failover startup grace active: fresh_ratio=%.2f "
                                "(%d/%d) < %.2f, keeping WebSocket healthy",
                                fresh_ratio,
                                fresh_symbol_count,
                                symbol_count,
                                min_ratio,
                            )
                            return True, health_status
                        logger.warning(
                            "Silent-stall guard: fresh_ratio=%.2f (%d/%d) < %.2f, "
                            "marking unhealthy",
                            fresh_ratio,
                            fresh_symbol_count,
                            symbol_count,
                            min_ratio,
                        )
                        return False, health_status

            return staleness < self.config.staleness_threshold_seconds, health_status

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

        return is_healthy, None

    def _is_startup_grace_active(self) -> bool:
        """Return True while WebSocket failover is in its startup grace window."""
        grace_seconds = self.config.startup_grace_seconds
        if grace_seconds <= 0.0 or self._health_monitor_started_at is None:
            return False
        return (time.monotonic() - self._health_monitor_started_at) < grace_seconds

    async def _get_data_source_health_status(self) -> dict[str, Any] | None:
        """Fetch structured health status from the primary data source when available."""
        if self._data_source is None or not hasattr(
            self._data_source, "get_health_status"
        ):
            return None

        try:
            return (
                await self._data_source.get_health_status()
                if asyncio.iscoroutinefunction(self._data_source.get_health_status)
                else self._data_source.get_health_status()
            )
        except Exception as e:
            logger.warning(f"Error getting health status: {e}")
            return None

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
        self._consecutive_recovery_checks = 0

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

                if self._kis_client is not None and getattr(
                    self._kis_client, "is_rate_limited", False
                ):
                    logger.debug(
                        "REST poll cycle: skipping while KIS client is rate-limited"
                    )
                    await asyncio.sleep(self.config.rest_poll_interval_seconds)
                    continue

                poll_symbols = self._select_rest_poll_symbols()
                if not poll_symbols:
                    logger.debug("REST poll cycle: no symbols selected for fetch")
                    await asyncio.sleep(self.config.rest_poll_interval_seconds)
                    continue

                # Fetch selected tracked symbols via KIS client
                # This uses existing _fetch_batch which:
                # - Handles rate limiting via staggered requests
                # - Updates cache with fresh data
                # - Preserves existing cache if the REST source fails
                logger.debug(f"REST poll cycle: fetching {len(poll_symbols)} symbols")

                async with self._lock:
                    await self._fetch_batch(poll_symbols)

                logger.debug(
                    f"REST poll cycle: successfully fetched {len(poll_symbols)} symbols"
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

        try:
            is_healthy, _ = await self._check_data_source_health()
        except Exception as e:
            logger.warning(f"Error checking WebSocket health during recovery: {e}")
            return

        if not is_healthy:
            logger.debug("WebSocket not healthy, cannot recover yet")
            return

        logger.info("Recovering to WebSocket mode from REST fallback")

        # Switch mode (this will stop the REST polling loop via its condition check)
        self._current_mode = DataSourceMode.WEBSOCKET
        self._health_monitor_started_at = time.monotonic()
        self._consecutive_unhealthy_checks = 0

        # Cancel REST polling task if it's still running
        if self._fallback_poll_task is not None and not self._fallback_poll_task.done():
            try:
                self._fallback_poll_task.cancel()
                # Wait briefly for task to finish cancelling
                try:
                    await asyncio.wait_for(self._fallback_poll_task, timeout=1.0)
                except asyncio.CancelledError:
                    pass
                except TimeoutError:
                    logger.warning("REST polling task did not cancel within timeout")
                logger.info("Stopped REST polling task")
            except Exception as e:
                logger.error(f"Error stopping REST polling task: {e}", exc_info=True)

        logger.info("Successfully recovered to WebSocket mode")

    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self._last_batch_fetch = None
        logger.info("Cache cleared")

    def _select_rest_poll_symbols(self, symbols: list[str] | None = None) -> list[str]:
        """Choose the stalest cached symbols first during REST fallback."""
        target_symbols = list(self.symbols if symbols is None else symbols)
        if not target_symbols:
            return []

        max_symbols = self.config.rest_fallback_max_symbols
        if max_symbols is None or max_symbols >= len(target_symbols):
            return target_symbols

        return sorted(
            target_symbols,
            key=lambda symbol: (
                self._cache[symbol].fetched_at
                if symbol in self._cache
                else datetime.min
            ),
        )[:max_symbols]
