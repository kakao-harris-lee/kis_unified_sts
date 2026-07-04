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
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from services.trading.data_provider_models import (
    DataSourceMode,
    MarketDataCache,
    MarketDataSource,
)
from services.trading.data_provider_runtime import MarketDataProviderRuntimeMixin
from shared.notification.telegram import TelegramNotifier

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
MIN_STARTUP_GRACE_SECONDS = 0.0
MAX_STARTUP_GRACE_SECONDS = 600.0
MIN_HEALTH_CONFIRMATION_CHECKS = 1
MAX_HEALTH_CONFIRMATION_CHECKS = 100


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
    health_check_interval_seconds: float = 10.0

    # Failover: REST polling interval in seconds (when in fallback mode)
    rest_poll_interval_seconds: float = 10.0

    # Failover: Data staleness threshold in seconds (trigger failover if no data)
    staleness_threshold_seconds: float = 30.0

    # Failover: Minimum fresh-symbol ratio (fresh / subscribed).  Trigger
    # failover when ratio drops below this even if some symbols still tick.
    # Catches the silent-stall case where most symbols stop ticking but
    # health check's `_last_tick_ts` still looks fresh because of a few
    # noisy symbols (observed 2026-05-11: 13:09–13:35 KST stock orchestrator
    # had 0 fresh trade-target symbols but health check passed because
    # non-universe dip-candidate symbols kept producing ticks).
    # Set to 0.0 to disable (legacy behaviour: only fail when ALL symbols
    # are stale).  Default 0.25 tolerates low-liquidity symbol tick gaps.
    min_fresh_ratio: float = 0.25

    # Failover: grace period after health monitoring starts.  KIS stock
    # WebSocket subscriptions do not receive first ticks for all symbols at
    # the same time right after market open; applying min_fresh_ratio during
    # this short bootstrap window causes unnecessary REST fallback storms.
    startup_grace_seconds: float = 120.0

    # Failover: Limit per-cycle REST polling scope to avoid rate-limit storms.
    rest_fallback_max_symbols: int | None = None

    # Failover: Send Telegram alerts on failover/recovery.
    # Deprecated operationally: transitions are logged only to avoid noisy
    # Telegram flapping during normal WebSocket tick gaps.
    send_telegram_alerts: bool = False

    # Failover: require consecutive unhealthy checks before entering REST mode.
    failover_unhealthy_threshold: int = 3

    # Recovery: require consecutive healthy checks before returning to WebSocket.
    recovery_healthy_threshold: int = 3

    def __post_init__(self):
        """Validate configuration values."""
        self._validate()

    def _validate(self):
        """Validate all configuration parameters."""
        if not (
            MIN_CACHE_TTL_SECONDS <= self.cache_ttl_seconds <= MAX_CACHE_TTL_SECONDS
        ):
            raise ValueError(
                f"cache_ttl_seconds must be between {MIN_CACHE_TTL_SECONDS} "
                f"and {MAX_CACHE_TTL_SECONDS}, got {self.cache_ttl_seconds}"
            )

        if not (MIN_BATCH_SIZE <= self.batch_size <= MAX_BATCH_SIZE):
            raise ValueError(
                f"batch_size must be between {MIN_BATCH_SIZE} "
                f"and {MAX_BATCH_SIZE}, got {self.batch_size}"
            )

        if not (
            MIN_TIMEOUT_SECONDS <= self.fetch_timeout_seconds <= MAX_TIMEOUT_SECONDS
        ):
            raise ValueError(
                f"fetch_timeout_seconds must be between {MIN_TIMEOUT_SECONDS} "
                f"and {MAX_TIMEOUT_SECONDS}, got {self.fetch_timeout_seconds}"
            )

        if self.mock_seed is not None and not isinstance(self.mock_seed, int):
            raise TypeError(
                f"mock_seed must be int or None, got {type(self.mock_seed)}"
            )

        if not (
            MIN_TIMEOUT_SECONDS
            <= self.health_check_interval_seconds
            <= MAX_TIMEOUT_SECONDS
        ):
            raise ValueError(
                f"health_check_interval_seconds must be between {MIN_TIMEOUT_SECONDS} "
                f"and {MAX_TIMEOUT_SECONDS}, got {self.health_check_interval_seconds}"
            )

        if not (
            MIN_CACHE_TTL_SECONDS
            <= self.rest_poll_interval_seconds
            <= MAX_CACHE_TTL_SECONDS
        ):
            raise ValueError(
                f"rest_poll_interval_seconds must be between {MIN_CACHE_TTL_SECONDS} "
                f"and {MAX_CACHE_TTL_SECONDS}, got {self.rest_poll_interval_seconds}"
            )

        if not (
            MIN_CACHE_TTL_SECONDS
            <= self.staleness_threshold_seconds
            <= MAX_CACHE_TTL_SECONDS
        ):
            raise ValueError(
                f"staleness_threshold_seconds must be between {MIN_CACHE_TTL_SECONDS} "
                f"and {MAX_CACHE_TTL_SECONDS}, got {self.staleness_threshold_seconds}"
            )

        if self.rest_fallback_max_symbols is not None and not (
            MIN_BATCH_SIZE <= self.rest_fallback_max_symbols <= MAX_BATCH_SIZE
        ):
            raise ValueError(
                f"rest_fallback_max_symbols must be between {MIN_BATCH_SIZE} "
                f"and {MAX_BATCH_SIZE}, got {self.rest_fallback_max_symbols}"
            )
        if not (
            MIN_STARTUP_GRACE_SECONDS
            <= self.startup_grace_seconds
            <= MAX_STARTUP_GRACE_SECONDS
        ):
            raise ValueError(
                "startup_grace_seconds must be between "
                f"{MIN_STARTUP_GRACE_SECONDS} and {MAX_STARTUP_GRACE_SECONDS}, "
                f"got {self.startup_grace_seconds}"
            )
        for field_name, value in (
            ("failover_unhealthy_threshold", self.failover_unhealthy_threshold),
            ("recovery_healthy_threshold", self.recovery_healthy_threshold),
        ):
            if not (
                MIN_HEALTH_CONFIRMATION_CHECKS
                <= value
                <= MAX_HEALTH_CONFIRMATION_CHECKS
            ):
                raise ValueError(
                    f"{field_name} must be between "
                    f"{MIN_HEALTH_CONFIRMATION_CHECKS} and "
                    f"{MAX_HEALTH_CONFIRMATION_CHECKS}, got {value}"
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
        health_check_interval = data.get("health_check_interval_seconds", 10.0)
        rest_poll_interval = data.get("rest_poll_interval_seconds", 10.0)
        staleness_threshold = data.get("staleness_threshold_seconds", 30.0)
        min_fresh_ratio = data.get("min_fresh_ratio", 0.25)
        startup_grace_seconds = data.get("startup_grace_seconds", 120.0)
        rest_fallback_max_symbols = data.get("rest_fallback_max_symbols")
        send_telegram_alerts = data.get("send_telegram_alerts", False)
        failover_unhealthy_threshold = data.get("failover_unhealthy_threshold", 3)
        recovery_healthy_threshold = data.get("recovery_healthy_threshold", 3)

        # Type validation
        if not isinstance(cache_ttl, (int, float)):
            raise TypeError(f"cache_ttl_seconds must be numeric, got {type(cache_ttl)}")
        if not isinstance(batch_size, int):
            raise TypeError(f"batch_size must be int, got {type(batch_size)}")
        if not isinstance(timeout, (int, float)):
            raise TypeError(
                f"fetch_timeout_seconds must be numeric, got {type(timeout)}"
            )
        if not isinstance(health_check_interval, (int, float)):
            raise TypeError(
                f"health_check_interval_seconds must be numeric, got {type(health_check_interval)}"
            )
        if not isinstance(rest_poll_interval, (int, float)):
            raise TypeError(
                f"rest_poll_interval_seconds must be numeric, got {type(rest_poll_interval)}"
            )
        if not isinstance(staleness_threshold, (int, float)):
            raise TypeError(
                f"staleness_threshold_seconds must be numeric, got {type(staleness_threshold)}"
            )
        if not isinstance(min_fresh_ratio, (int, float)):
            raise TypeError(
                f"min_fresh_ratio must be numeric, got {type(min_fresh_ratio)}"
            )
        if not isinstance(startup_grace_seconds, (int, float)):
            raise TypeError(
                f"startup_grace_seconds must be numeric, got {type(startup_grace_seconds)}"
            )
        if rest_fallback_max_symbols is not None and not isinstance(
            rest_fallback_max_symbols, int
        ):
            raise TypeError(
                f"rest_fallback_max_symbols must be int or None, got {type(rest_fallback_max_symbols)}"
            )
        if not isinstance(send_telegram_alerts, bool):
            raise TypeError(
                f"send_telegram_alerts must be bool, got {type(send_telegram_alerts)}"
            )
        if not isinstance(failover_unhealthy_threshold, int):
            raise TypeError(
                "failover_unhealthy_threshold must be int, "
                f"got {type(failover_unhealthy_threshold)}"
            )
        if not isinstance(recovery_healthy_threshold, int):
            raise TypeError(
                "recovery_healthy_threshold must be int, "
                f"got {type(recovery_healthy_threshold)}"
            )

        return cls(
            cache_ttl_seconds=float(cache_ttl),
            batch_size=int(batch_size),
            fetch_timeout_seconds=float(timeout),
            mock_seed=mock_seed,
            health_check_interval_seconds=float(health_check_interval),
            rest_poll_interval_seconds=float(rest_poll_interval),
            staleness_threshold_seconds=float(staleness_threshold),
            min_fresh_ratio=float(min_fresh_ratio),
            startup_grace_seconds=float(startup_grace_seconds),
            rest_fallback_max_symbols=rest_fallback_max_symbols,
            send_telegram_alerts=bool(send_telegram_alerts),
            failover_unhealthy_threshold=int(failover_unhealthy_threshold),
            recovery_healthy_threshold=int(recovery_healthy_threshold),
        )


@dataclass
class MarketDataProvider(MarketDataProviderRuntimeMixin):
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
        self._health_monitor_started_at: float | None = None
        self._consecutive_unhealthy_checks = 0
        self._consecutive_recovery_checks = 0

        logger.info(
            f"MarketDataProvider initialized: {len(self.symbols)} symbols, "
            f"TTL={self.config.cache_ttl_seconds}s, mode={self._current_mode.value}"
        )

        # Continue checking despite errors

        # Continue with manual fetches via get_data() if polling task fails
