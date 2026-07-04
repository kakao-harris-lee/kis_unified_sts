"""Market-data bootstrap helpers for the trading orchestrator."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import yaml

from services.trading.data_provider import DataProviderConfig, MarketDataProvider
from shared.config.loader import ConfigLoader
from shared.config.runtime_defaults import redis_url_from_env
from shared.exceptions import (
    APIError,
    ConfigurationError,
    InfrastructureError,
    InvalidConfigError,
    MissingConfigError,
    NetworkError,
    WebSocketDisconnectError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KisClientInitResult:
    """KIS client bootstrap result."""

    client: Any | None
    auth_config: Any | None


@dataclass(frozen=True)
class PriceFeedInitResult:
    """Price-feed bootstrap result."""

    data_source: Any | None
    stock_price_feed: Any | None = None
    futures_price_feed: Any | None = None
    stream_consumer_feed: Any | None = None
    stream_redis: Any | None = None


@dataclass(frozen=True)
class DataProviderInitResult:
    """Market data provider bootstrap result."""

    provider: Any
    failover_enabled: bool


@dataclass(frozen=True)
class TickStreamPublisherInitResult:
    """Tick stream publisher bootstrap result."""

    publisher: Any | None


def init_kis_client(config: Any) -> KisClientInitResult:
    """Initialize KIS REST API client and auth config."""
    try:
        from shared.kis.auth import KISAuthConfig
        from shared.kis.client import KISClient

        if config.asset_class == "futures":
            app_key = os.getenv("KIS_FUTURES_APP_KEY", os.getenv("KIS_APP_KEY", ""))
            app_secret = os.getenv(
                "KIS_FUTURES_APP_SECRET", os.getenv("KIS_APP_SECRET", "")
            )
            # Futures quotes are available from the real KIS endpoint only.
            is_real = True
        else:
            app_key = os.getenv("KIS_APP_KEY", "")
            app_secret = os.getenv("KIS_APP_SECRET", "")
            market = os.getenv("KIS_STOCK_MARKET", "real")
            is_real = market.lower() == "real"
        kis_config = KISAuthConfig(
            app_key=app_key, app_secret=app_secret, is_real=is_real
        )
        client = KISClient(kis_config)
        logger.info("KIS Client initialized")
        return KisClientInitResult(client=client, auth_config=kis_config)
    except (ConfigurationError, APIError, NetworkError) as e:
        logger.warning(f"Failed to initialize KIS Client: {e}")
        return KisClientInitResult(client=None, auth_config=None)


def load_stream_staleness_threshold() -> float:
    """Staleness threshold for the stream feed."""
    try:
        failover_cfg = ConfigLoader.load("streaming.yaml").get("failover", {})
        return float(failover_cfg.get("staleness_threshold_seconds", 30.0))
    except (
        InvalidConfigError,
        MissingConfigError,
        OSError,
        yaml.YAMLError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return 30.0


def init_price_feeds(
    *,
    config: Any,
    kis_client: Any | None,
    kis_config: Any | None,
) -> PriceFeedInitResult:
    """Initialize stock/futures price-feed dependencies."""
    if not kis_client or not kis_config:
        return PriceFeedInitResult(data_source=None)

    if config.asset_class == "stock":
        return _init_stock_price_feed(kis_config)
    if config.asset_class == "futures":
        return _init_futures_price_feed(kis_config)
    return PriceFeedInitResult(data_source=None)


def _init_stock_price_feed(kis_config: Any) -> PriceFeedInitResult:
    source_mode = os.getenv("STOCK_MARKET_DATA_SOURCE", "websocket").strip().lower()
    if source_mode == "stream":
        import redis.asyncio as aioredis

        from services.trading.stream_consumer_feed import StreamConsumerFeed

        stream_name = os.getenv("MARKET_TICK_STREAM", "market:ticks")
        stream_redis = aioredis.from_url(redis_url_from_env())
        stream_consumer_feed = StreamConsumerFeed(
            redis=stream_redis,
            stream=stream_name,
            stale_threshold_seconds=load_stream_staleness_threshold(),
        )
        logger.info(
            "Stock data source = STREAM (%s); KIS WebSocket feed skipped",
            stream_name,
        )
        return PriceFeedInitResult(
            data_source=stream_consumer_feed,
            stream_consumer_feed=stream_consumer_feed,
            stream_redis=stream_redis,
        )

    try:
        from shared.kis.stock_feed import KISStockPriceFeed

        stock_price_feed = KISStockPriceFeed(config=kis_config)
        logger.info("Stock WebSocket price feed initialized")
        return PriceFeedInitResult(
            data_source=stock_price_feed,
            stock_price_feed=stock_price_feed,
        )
    except (NetworkError, WebSocketDisconnectError, ConfigurationError) as e:
        logger.warning(f"Stock WebSocket feed init failed: {e}")
        return PriceFeedInitResult(data_source=None)


def _init_futures_price_feed(kis_config: Any) -> PriceFeedInitResult:
    try:
        from shared.kis.futures_feed import KISFuturesPriceFeed

        futures_price_feed = KISFuturesPriceFeed(config=kis_config)
        logger.info("Futures WebSocket price feed initialized")
        return PriceFeedInitResult(
            data_source=futures_price_feed,
            futures_price_feed=futures_price_feed,
        )
    except (NetworkError, WebSocketDisconnectError, ConfigurationError) as e:
        logger.warning(f"Futures WebSocket feed init failed: {e}")
        return PriceFeedInitResult(data_source=None)


def init_data_provider(
    *,
    config: Any,
    kis_client: Any | None,
    data_source: Any | None,
) -> DataProviderInitResult:
    """Initialize MarketDataProvider and expose failover state."""
    dp_cfg, failover_cfg = _load_data_provider_config()
    cache_ttl = _cache_ttl_seconds(
        asset_class=config.asset_class,
        data_source=data_source,
        dp_cfg=dp_cfg,
    )
    stagger_delay = float(dp_cfg.get("stagger_delay", 0.1))
    send_telegram_alerts = bool(failover_cfg.get("send_telegram_alerts", False))

    provider = MarketDataProvider(
        symbols=config.symbols,
        config=DataProviderConfig(
            cache_ttl_seconds=cache_ttl,
            batch_size=int(dp_cfg.get("batch_size", 20)),
            fetch_timeout_seconds=float(dp_cfg.get("fetch_timeout_seconds", 5.0)),
            stagger_delay_seconds=stagger_delay,
            health_check_interval_seconds=float(
                failover_cfg.get("health_check_interval_seconds", 10.0)
            ),
            rest_poll_interval_seconds=float(
                failover_cfg.get("rest_poll_interval_seconds", 10.0)
            ),
            staleness_threshold_seconds=float(
                failover_cfg.get("staleness_threshold_seconds", 30.0)
            ),
            min_fresh_ratio=float(failover_cfg.get("min_fresh_ratio", 0.25)),
            startup_grace_seconds=float(
                failover_cfg.get("startup_grace_seconds", 120.0)
            ),
            rest_fallback_max_symbols=failover_cfg.get("rest_fallback_max_symbols"),
            send_telegram_alerts=send_telegram_alerts,
            failover_unhealthy_threshold=int(
                failover_cfg.get("failover_unhealthy_threshold", 3)
            ),
            recovery_healthy_threshold=int(
                failover_cfg.get("recovery_healthy_threshold", 3)
            ),
        ),
        kis_client=kis_client,
        data_source=data_source,
        telegram_notifier=_build_failover_notifier(
            config=config,
            send_telegram_alerts=send_telegram_alerts,
        ),
    )
    return DataProviderInitResult(
        provider=provider,
        failover_enabled=bool(failover_cfg.get("enabled", False)),
    )


def _load_data_provider_config() -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        streaming_cfg = ConfigLoader.load("streaming.yaml")
        return (
            dict(streaming_cfg.get("data_provider", {})),
            dict(streaming_cfg.get("failover", {})),
        )
    except (
        InvalidConfigError,
        MissingConfigError,
        OSError,
        yaml.YAMLError,
        KeyError,
        TypeError,
    ):
        return {}, {}


def _cache_ttl_seconds(
    *,
    asset_class: str,
    data_source: Any | None,
    dp_cfg: dict[str, Any],
) -> float:
    if data_source:
        return float(dp_cfg.get("cache_ttl_websocket", 2.0))
    if asset_class == "stock":
        return float(dp_cfg.get("cache_ttl_stock", 30.0))
    return float(dp_cfg.get("cache_ttl_futures", 5.0))


def _build_failover_notifier(
    *,
    config: Any,
    send_telegram_alerts: bool,
) -> Any | None:
    if not config.enable_telegram or not send_telegram_alerts:
        return None
    try:
        from shared.notification.telegram import (
            TelegramNotifier,
            resolve_domain_credentials,
        )

        domain = (
            config.asset_class if config.asset_class in ("stock", "futures") else None
        )
        # Avoid the legacy TELEGRAM_BOT_TOKEN fallback crossing stock/futures domains.
        env_token, env_chat = resolve_domain_credentials(domain)
        bot_token = config.telegram_token or env_token
        chat_id = config.telegram_chat_id or env_chat
        if bot_token and chat_id:
            return TelegramNotifier(
                bot_token=bot_token,
                chat_id=chat_id,
            )
    except Exception as e:
        logger.warning("Failed to initialize failover telegram notifier: %s", e)
    return None


def init_tick_stream_publisher(
    *,
    stream_consumer_feed: Any | None,
) -> TickStreamPublisherInitResult:
    """Initialize optional Redis tick mirroring for monitoring."""
    if stream_consumer_feed is not None:
        logger.info("Tick stream publisher skipped (stock data source = stream)")
        return TickStreamPublisherInitResult(publisher=None)

    try:
        from services.monitoring.tick_stream_publisher import (
            TickStreamPublisher,
            TickStreamPublisherConfig,
        )

        cfg = TickStreamPublisherConfig.from_env()
        if not cfg.enabled:
            logger.info("Tick stream publisher disabled by env")
            return TickStreamPublisherInitResult(publisher=None)

        publisher = TickStreamPublisher(cfg)
        logger.info(
            "Tick stream publisher enabled "
            "(async=%s, stock_stream=%s, futures_stream=%s, "
            "stock_interval=%.2fs, futures_interval=%.2fs, queue=%d, batch=%d)",
            cfg.async_publish,
            cfg.stock_stream,
            cfg.futures_stream,
            cfg.stock_min_interval_seconds,
            cfg.futures_min_interval_seconds,
            cfg.queue_maxsize,
            cfg.flush_batch_size,
        )
        return TickStreamPublisherInitResult(publisher=publisher)
    except (ConfigurationError, InfrastructureError) as e:
        logger.warning(f"Tick stream publisher init failed: {e}")
        return TickStreamPublisherInitResult(publisher=None)
