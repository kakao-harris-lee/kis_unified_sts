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
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from shared.collector.models import TickData
from shared.config.loader import ConfigLoader
from shared.kis.auth import KISAuthConfig
from shared.kis.reconnect_policy import ReconnectPolicy
from shared.kis.websocket import KISWebSocketAdapter

logger = logging.getLogger(__name__)


def _record_ws_reconnect(feed: str) -> None:
    """Best-effort WS reconnect counter.

    Lazy guarded import so a missing/failing collector never breaks the
    WebSocket supervisor thread.
    """
    try:
        from services.monitoring.metrics import get_metrics_collector

        get_metrics_collector().record_ws_reconnect(feed)
    except Exception:  # noqa: BLE001 — observability must never break the WS thread
        pass


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
        tick_callback: Callable[[str, dict[str, Any], datetime], None] | None = None,
    ) -> None:
        self._config = config
        self._adapter = KISWebSocketAdapter(config)

        feed_cfg = _load_futures_feed_config()
        self._max_symbols = _require_int(feed_cfg, "max_symbols")
        self._subscription_delay = _require_float(feed_cfg, "subscription_delay")
        self._connection_timeout = _require_float(feed_cfg, "connection_timeout")
        self._shutdown_timeout = _require_float(feed_cfg, "shutdown_timeout")
        self._orderbook_stale_threshold = float(
            feed_cfg.get("orderbook_stale_threshold_seconds", 3.0)
        )
        self._orderbook_missing_warn_interval = float(
            feed_cfg.get("orderbook_missing_warn_interval_seconds", 30.0)
        )
        self._reconnect_initial_delay = float(
            feed_cfg.get("reconnect_initial_delay", 1.0)
        )
        self._reconnect_max_delay = float(feed_cfg.get("reconnect_max_delay", 60.0))
        # Circuit breaker: after N consecutive failed reconnects, back off to a
        # long cooldown rather than looping at the cap forever. KIS blocks the
        # account on unbounded reconnect attempts; the orchestrator's REST
        # failover carries data while the breaker is open.
        self._reconnect_breaker_threshold = int(
            feed_cfg.get("reconnect_breaker_threshold", 6)
        )
        self._reconnect_breaker_cooldown = float(
            feed_cfg.get("reconnect_breaker_cooldown_seconds", 300.0)
        )
        # Bounded retries for the *initial* connect. KIS intermittently resets
        # the WS right after the approval handshake; without this a single
        # startup reset leaves the feed permanently dead (the supervisor loop
        # only handles drops after a successful start), forcing the whole
        # session onto REST fallback. See _connect_initial_with_retry.
        self._connect_max_attempts = max(
            1, int(feed_cfg.get("connect_max_attempts", 3))
        )

        self._prices: dict[str, dict[str, Any]] = {}
        self._orderbooks: dict[str, dict[str, Any]] = {}
        self._prices_lock = threading.Lock()
        self._tick_callback = tick_callback
        self._last_tick_ts: float | None = None
        self._last_orderbook_ts: dict[str, float] = {}
        self._last_orderbook_warn_ts: dict[str, float] = {}

        self._symbols: list[str] = []
        self._auxiliary_symbols: list[str] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._first_tick_logged = False
        self._first_orderbook_logged = False

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

    def is_healthy(self) -> bool:
        """Check if the feed is healthy (receiving recent data).

        Returns:
            True if staleness is within threshold and feed is running, False otherwise.
        """
        if not self._running:
            return False
        staleness = self.get_staleness_seconds()
        if staleness is None:
            return False
        return staleness < self._orderbook_stale_threshold

    def get_health_status(self) -> dict[str, Any]:
        """Get detailed health status for diagnostics.

        Spreads adapter health (connected, messages_received, messages_dropped,
        queue_depth, …) then overlays feed-specific keys so that feed-level
        staleness / is_healthy semantics always win.

        Returns:
            Dictionary with health metrics:
            - running: bool - whether feed is running
            - last_tick_ts: float | None - timestamp of last tick
            - staleness_seconds: float | None - seconds since last tick (tick-based)
            - is_healthy: bool - overall health status (tick-based)
            - symbol_count: int - number of tracked symbols
            - cached_symbols: list[str] - symbols with cached data
            - messages_received: int - from adapter (cumulative)
            - messages_dropped: int - from adapter (cumulative, queue-full drops)
            - queue_depth: int - from adapter
            - connected: bool - WebSocket connection state
        """
        with self._prices_lock:
            cached_symbols = list(self._prices.keys())

        staleness = self.get_staleness_seconds()
        # Read adapter health once; spread it first so feed keys override.
        adapter_health = self._adapter.get_health_status()

        return {
            **adapter_health,
            # Feed-specific keys override adapter values for staleness/health
            # semantics (tick-based, not WS-message-based).
            "running": self._running,
            "last_tick_ts": self._last_tick_ts,
            "staleness_seconds": staleness,
            "is_healthy": self.is_healthy(),
            "symbol_count": len(self._symbols),
            "cached_symbols": cached_symbols,
        }

    def update_symbols(
        self,
        symbols: list[str],
        auxiliary_symbols: list[str] | None = None,
    ) -> None:
        if not symbols:
            raise ValueError("At least one futures symbol required")
        merged: list[str] = []
        for symbol in symbols:
            if symbol and symbol not in merged:
                merged.append(symbol)
        extras = auxiliary_symbols or []
        for symbol in extras:
            if symbol and symbol not in merged:
                merged.append(symbol)

        self._symbols = merged[: self._max_symbols]
        self._auxiliary_symbols = [
            symbol for symbol in self._symbols if symbol not in symbols
        ]
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

        await self._connect_initial_with_retry()

        self._running = True
        self._thread = threading.Thread(
            target=self._run_with_reconnect,
            daemon=True,
            name="FuturesPriceFeed",
        )
        try:
            self._thread.start()
        except Exception as e:
            logger.error(f"[FuturesPriceFeed] Thread start failed: {e}")
            self._running = False
            raise
        logger.info(f"[FuturesPriceFeed] Started with {len(self._symbols)} symbols")

    async def _connect_initial_with_retry(self) -> None:
        """Connect the initial adapter, retrying transient failures with backoff.

        KIS intermittently resets the WebSocket connection right after the
        approval handshake (``[Errno 104] Connection reset by peer``) — some
        sessions the first connect succeeds, others it is reset. Previously a
        single failed initial connect raised straight out of ``start()``,
        leaving the feed permanently dead: ``_run_with_reconnect`` only retries
        drops *after* a successful start, so on an initial failure it never even
        spawned, and ``MarketDataProvider`` failed over to REST polling with no
        path back to WebSocket for the rest of the session.

        Retrying the initial connect a bounded number of times (with exponential
        backoff, a fresh adapter per attempt) absorbs these transient resets. If
        every attempt fails we re-raise so the orchestrator still fails over to
        REST polling exactly as before.
        """
        delay = self._reconnect_initial_delay
        last_exc: Exception | None = None
        for attempt in range(1, self._connect_max_attempts + 1):
            if attempt > 1:
                # A failed adapter is spent (is_running permanently False); build
                # a fresh one per attempt, mirroring the supervisor loop.
                self._adapter = KISWebSocketAdapter(self._config)
            try:
                await asyncio.to_thread(self._adapter.connect)
                if attempt > 1:
                    logger.info(
                        "[FuturesPriceFeed] Initial connect succeeded on "
                        "attempt %d/%d",
                        attempt,
                        self._connect_max_attempts,
                    )
                return
            except Exception as e:  # noqa: BLE001 — retry transient connect resets
                last_exc = e
                logger.warning(
                    "[FuturesPriceFeed] Initial connect attempt %d/%d failed: %s",
                    attempt,
                    self._connect_max_attempts,
                    e,
                )
                if attempt < self._connect_max_attempts:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self._reconnect_max_delay)

        logger.error(
            "[FuturesPriceFeed] Connection failed after %d attempts: %s",
            self._connect_max_attempts,
            last_exc,
        )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("[FuturesPriceFeed] Connection failed: no attempts made")

    def _run_with_reconnect(self) -> None:
        """Worker thread: run the subscribe loop, reconnect on drop.

        Runs the initial ``subscribe`` (the adapter is already connected by
        ``start()``); it blocks until the WebSocket drops or ``stop()`` is
        called. On an *unexpected* drop (``_running`` still True), retries with
        exponential backoff using a fresh adapter per attempt, re-subscribes,
        and records ``record_ws_reconnect("futures")``. A deliberate ``stop()``
        (which sets ``_running=False`` before ``disconnect()``) ends the loop
        without reconnecting. Mirrors ``KISStockPriceFeed._reconnect``.
        """
        try:
            self._adapter.subscribe(self._symbols, self._on_tick)
        except Exception as e:  # noqa: BLE001 — log and fall through to reconnect
            logger.error(f"[FuturesPriceFeed] Subscribe loop error: {e}")

        policy = ReconnectPolicy(
            initial_delay=self._reconnect_initial_delay,
            max_delay=self._reconnect_max_delay,
            breaker_threshold=self._reconnect_breaker_threshold,
            breaker_cooldown=self._reconnect_breaker_cooldown,
        )
        delay = self._reconnect_initial_delay
        while self._running:
            if policy.breaker_open:
                logger.warning(
                    "[FuturesPriceFeed] Reconnect circuit breaker OPEN "
                    "(%d consecutive failures) — backing off %.0fs to avoid a KIS "
                    "account block; REST fallback covers data meanwhile",
                    policy.consecutive_failures,
                    delay,
                )
            time.sleep(delay)
            if not self._running:
                break
            try:
                # The previous adapter is spent (is_running permanently False);
                # build a fresh one for the new connection.
                self._adapter = KISWebSocketAdapter(self._config)
                self._adapter.connect()
                logger.info("[FuturesPriceFeed] Reconnected to futures WS feed")
                _record_ws_reconnect("futures")
                self._adapter.subscribe(self._symbols, self._on_tick)
                # subscribe() returned: the connection lived then dropped (or
                # stop()). Only now reset the breaker/backoff — resetting before
                # subscribe would let a connect-ok-but-subscribe-fails flap loop
                # forever without ever tripping the breaker.
                policy.reset()
                delay = self._reconnect_initial_delay
            except Exception as e:  # noqa: BLE001 — backoff and retry
                logger.error(f"[FuturesPriceFeed] Reconnect attempt failed: {e}")
                # Advance backoff / trip the breaker after repeated failures.
                delay = policy.record_failure()

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._adapter.disconnect()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._shutdown_timeout)
        with self._prices_lock:
            self._prices.clear()
            self._orderbooks.clear()
            self._last_orderbook_ts.clear()
            self._last_orderbook_warn_ts.clear()
        logger.info("[FuturesPriceFeed] Stopped")

    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        with self._prices_lock:
            cached = self._prices.get(symbol)
        if cached is not None:
            return dict(cached)
        return {}

    def get_orderbook_snapshot(self, symbol: str) -> dict[str, Any]:
        with self._prices_lock:
            cached = self._orderbooks.get(symbol)
            if cached is not None:
                return dict(cached)
            fallback = self._prices.get(symbol, {})
        if fallback:
            keys = {
                "code",
                "timestamp",
                "bid_price_1",
                "bid_qty_1",
                "ask_price_1",
                "ask_qty_1",
            }
            return {k: v for k, v in fallback.items() if k in keys}
        return {}

    def _on_tick(self, tick: TickData) -> None:
        has_orderbook = (
            tick.bid_price_1 is not None
            and tick.ask_price_1 is not None
            and float(tick.bid_price_1) > 0
            and float(tick.ask_price_1) > 0
        )
        trade_price = (
            float(tick.current_price)
            if tick.current_price is not None and float(tick.current_price) > 0
            else 0.0
        )

        orderbook_payload: dict[str, Any] = {}
        if has_orderbook:
            spread = float(tick.ask_price_1) - float(tick.bid_price_1)
            orderbook_payload = {
                "code": tick.symbol,
                "bid_price_1": float(tick.bid_price_1),
                "bid_qty_1": float(tick.bid_qty_1 or 0.0),
                "ask_price_1": float(tick.ask_price_1),
                "ask_qty_1": float(tick.ask_qty_1 or 0.0),
                "spread": spread,
                "timestamp": tick.timestamp,
            }

        payload: dict[str, Any] | None = None
        if trade_price > 0:
            open_price = (
                float(tick.open_price) if tick.open_price is not None else trade_price
            )
            day_high_price = (
                float(tick.high_price) if tick.high_price is not None else trade_price
            )
            day_low_price = (
                float(tick.low_price) if tick.low_price is not None else trade_price
            )

            volume = None
            volume_is_cumulative = True
            if tick.cumulative_volume is not None:
                volume = int(tick.cumulative_volume)
            elif tick.tick_volume is not None:
                volume = int(tick.tick_volume)
                volume_is_cumulative = False

            change = None
            if open_price:
                change = (trade_price - open_price) / open_price

            payload = {
                "code": tick.symbol,
                "close": trade_price,
                "open": open_price,
                "high": trade_price,
                "low": trade_price,
                "day_high": day_high_price,
                "day_low": day_low_price,
                "timestamp": tick.timestamp,
            }
            if volume is not None:
                payload["volume"] = volume
                if not volume_is_cumulative:
                    payload["volume_is_cumulative"] = False
            if change is not None:
                payload["change"] = change

        with self._prices_lock:
            if has_orderbook:
                self._orderbooks[tick.symbol] = orderbook_payload
                self._last_orderbook_ts[tick.symbol] = tick.timestamp
                merged = dict(self._prices.get(tick.symbol, {}))
                merged.update(orderbook_payload)
                self._prices[tick.symbol] = merged

            if payload is not None:
                merged = dict(self._orderbooks.get(tick.symbol, {}))
                merged.update(payload)
                self._prices[tick.symbol] = merged

            if not self._first_tick_logged and payload is not None:
                self._first_tick_logged = True
                logger.info(
                    f"[FuturesPriceFeed] First trade tick: symbol={tick.symbol} "
                    f"price={trade_price} symbols={list(self._prices.keys())}"
                )
            if not self._first_orderbook_logged and has_orderbook:
                self._first_orderbook_logged = True
                logger.info(
                    f"[FuturesPriceFeed] First orderbook tick: symbol={tick.symbol} "
                    f"bid={tick.bid_price_1} ask={tick.ask_price_1}"
                )

        if payload is None:
            return

        if not has_orderbook:
            self._log_orderbook_staleness(
                symbol=tick.symbol,
                trade_price=trade_price,
                ts=tick.timestamp,
            )

        if self._tick_callback:
            # tz-aware UTC: tick.timestamp is a Unix epoch (UTC seconds);
            # downstream (indicator_engine, paper_broker, slippage_control)
            # treats incoming ts as authoritative and compares against
            # tz-aware UTC. Naive datetimes here cascade into "can't compare
            # offset-naive and offset-aware" inside pipeline retries.
            try:
                ts = datetime.fromtimestamp(tick.timestamp, UTC)
            except (OSError, ValueError, TypeError):
                ts = datetime.now(UTC)
            try:
                self._tick_callback(tick.symbol, payload, ts)
            except Exception as e:
                logger.debug(f"[FuturesPriceFeed] Tick callback error: {e}")
                return

        self._last_tick_ts = tick.timestamp

    def _log_orderbook_staleness(
        self, *, symbol: str, trade_price: float, ts: float
    ) -> None:
        if self._orderbook_stale_threshold <= 0:
            return
        with self._prices_lock:
            last_orderbook_ts = self._last_orderbook_ts.get(symbol)
            last_warn_ts = self._last_orderbook_warn_ts.get(symbol, 0.0)
        if ts - last_warn_ts < self._orderbook_missing_warn_interval:
            return
        if last_orderbook_ts is None:
            age_label = "never"
        else:
            age = max(0.0, ts - last_orderbook_ts)
            if age < self._orderbook_stale_threshold:
                return
            age_label = f"{age:.1f}s"
        with self._prices_lock:
            self._last_orderbook_warn_ts[symbol] = ts
        logger.warning(
            "[FuturesPriceFeed] Orderbook stale/missing: symbol=%s age=%s trade_price=%.2f",
            symbol,
            age_label,
            trade_price,
        )
