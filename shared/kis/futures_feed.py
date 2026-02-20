"""KIS WebSocket Futures Price Feed (H0IFCNT0).

Wrapper around KISWebSocketAdapter to provide a MarketDataSource-compatible
interface for futures strategies. Caches the latest trade ticks and exposes
get_current_price() for MarketDataProvider.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Optional

from shared.collector.models import TickData
from shared.config.loader import ConfigLoader
from shared.kis.auth import KISAuthConfig
from shared.kis.websocket import KISWebSocketAdapter

logger = logging.getLogger(__name__)


def _load_futures_feed_config() -> dict[str, Any]:
    """Load futures_feed section from config/streaming.yaml."""
    cfg = ConfigLoader.load("streaming.yaml")
    feed_cfg = cfg.get("futures_feed") or cfg.get("stock_feed", {})
    if not feed_cfg:
        raise ValueError("futures_feed config missing in streaming.yaml")
    return feed_cfg


def _require_int(feed_cfg: dict[str, Any], key: str) -> int:
    value = feed_cfg.get(key)
    if value is None:
        raise ValueError(f"futures_feed.{key} missing")
    return int(value)


def _require_float(feed_cfg: dict[str, Any], key: str) -> float:
    value = feed_cfg.get(key)
    if value is None:
        raise ValueError(f"futures_feed.{key} missing")
    return float(value)


class KISFuturesPriceFeed:
    """Real-time futures price feed via KIS WebSocket.

    Uses KISWebSocketAdapter (H0IFCNT0) and caches latest ticks per symbol.
    Implements MarketDataSource protocol for MarketDataProvider.
    """

    def __init__(
        self,
        config: KISAuthConfig,
        fallback_client: Any = None,
        tick_callback: Callable[[str, dict[str, Any], datetime], None] | None = None,
    ) -> None:
        self._config = config
        self._fallback = fallback_client
        self._adapter = KISWebSocketAdapter(config)

        feed_cfg = _load_futures_feed_config()
        self._max_symbols = _require_int(feed_cfg, "max_symbols")
        self._subscription_delay = _require_float(feed_cfg, "subscription_delay")
        self._connection_timeout = _require_float(feed_cfg, "connection_timeout")
        self._shutdown_timeout = _require_float(feed_cfg, "shutdown_timeout")

        self._prices: dict[str, dict[str, Any]] = {}
        self._prices_lock = threading.Lock()
        self._tick_callback = tick_callback
        self._last_tick_ts: float | None = None

        self._symbols: list[str] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def supports_instant_read(self) -> bool:
        return True

    @property
    def symbol_count(self) -> int:
        return len(self._symbols)

    def get_last_tick_timestamp(self) -> float | None:
        return self._last_tick_ts

    def get_staleness_seconds(self) -> float | None:
        if self._last_tick_ts is None:
            return None
        return max(0.0, time.time() - self._last_tick_ts)

    def update_symbols(self, symbols: list[str]) -> None:
        if not symbols:
            raise ValueError("At least one futures symbol required")
        self._symbols = list(symbols[: self._max_symbols])
        if self._running:
            logger.warning("Futures feed update_symbols while running is not supported")

    def set_tick_callback(
        self, callback: Callable[[str, dict[str, Any], datetime], None] | None
    ) -> None:
        self._tick_callback = callback

    async def start(self) -> None:
        if self._running:
            return
        if not self._symbols:
            raise ValueError("No futures symbols configured for WebSocket feed")

        try:
            await asyncio.to_thread(self._adapter.connect)
        except Exception as e:
            logger.error(f"[FuturesPriceFeed] Connection failed: {e}")
            raise

        self._running = True
        self._thread = threading.Thread(
            target=self._adapter.subscribe,
            args=(self._symbols, self._on_tick),
            daemon=True,
            name="FuturesPriceFeed",
        )
        try:
            self._thread.start()
        except Exception as e:
            logger.error(f"[FuturesPriceFeed] Thread start failed: {e}")
            self._running = False
            raise
        logger.info(
            f"[FuturesPriceFeed] Started with {len(self._symbols)} symbols"
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._adapter.disconnect()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._shutdown_timeout)
        with self._prices_lock:
            self._prices.clear()
        logger.info("[FuturesPriceFeed] Stopped")

    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        with self._prices_lock:
            cached = self._prices.get(symbol)
        if cached is not None:
            return cached
        return {}

    def _on_tick(self, tick: TickData) -> None:
        if tick.current_price is None:
            return
        price = float(tick.current_price)
        if price <= 0:
            return

        open_price = float(tick.open_price) if tick.open_price is not None else price
        high_price = float(tick.high_price) if tick.high_price is not None else price
        low_price = float(tick.low_price) if tick.low_price is not None else price

        volume = None
        if tick.cumulative_volume is not None:
            volume = int(tick.cumulative_volume)
        elif tick.tick_volume is not None:
            volume = int(tick.tick_volume)

        change = None
        if open_price:
            change = (price - open_price) / open_price

        payload: dict[str, Any] = {
            "code": tick.symbol,
            "close": price,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "timestamp": tick.timestamp,
        }
        if volume is not None:
            payload["volume"] = volume
        if change is not None:
            payload["change"] = change

        with self._prices_lock:
            self._prices[tick.symbol] = payload
            self._last_tick_ts = tick.timestamp

        if self._tick_callback:
            try:
                ts = datetime.fromtimestamp(tick.timestamp)
            except (OSError, ValueError, TypeError):
                ts = datetime.now()
            try:
                self._tick_callback(tick.symbol, payload, ts)
            except Exception as e:
                logger.debug(f"[FuturesPriceFeed] Tick callback error: {e}")
