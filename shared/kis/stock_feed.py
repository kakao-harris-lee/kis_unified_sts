"""KIS WebSocket Stock Price Feed (H0STCNT0)

Real-time stock price feed via KIS WebSocket.
Implements MarketDataSource protocol for drop-in replacement of REST API polling.

Key benefits over REST API:
- Zero API calls for price data (push-based, no rate limit issues)
- Real-time price updates (vs 2s polling interval)
- No EGW00201 "초당 거래건수 초과" errors

Limitations:
- Max 40 symbols per WebSocket connection (KIS limit: 41)
- get_minute_bars() still requires REST API (prewarm only)

Usage:
    feed = KISStockPriceFeed(config)
    await feed.start()
    feed.update_symbols(["005930", "000660"])
    price = await feed.get_current_price("005930")
    await feed.stop()
"""

from __future__ import annotations

import base64
import json
import logging
import queue
import threading
import time
from datetime import datetime
from typing import Any, Callable, Optional

import websocket
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from shared.config.loader import ConfigLoader
from shared.kis.auth import KISAuthConfig

logger = logging.getLogger(__name__)

# H0STCNT0 field indices (^-separated)
# Reference: KIS API 국내주식 실시간체결가
_F_SYMBOL = 0       # MKSC_SHRN_ISCD - 종목코드
_F_TIME = 1         # STCK_CNTG_HOUR - 체결시간 (HHMMSS)
_F_PRICE = 2        # STCK_PRPR - 현재가
_F_CHANGE_PCT = 5   # PRDY_CTRT - 전일대비율
_F_OPEN = 7         # STCK_OPRC - 시가
_F_HIGH = 8         # STCK_HGPR - 고가
_F_LOW = 9          # STCK_LWPR - 저가
_F_VOLUME = 13      # ACML_VOL - 누적거래량

TR_STOCK_TRADE = "H0STCNT0"


def _load_feed_config() -> dict[str, Any]:
    """Load stock_feed section from config/streaming.yaml."""
    try:
        cfg = ConfigLoader.load("streaming.yaml")
        return cfg.get("stock_feed", {})
    except Exception:
        logger.warning("[StockPriceFeed] Failed to load config, using defaults")
        return {}


def _parse_stock_trade(data: str) -> Optional[dict[str, Any]]:
    """Parse H0STCNT0 stock trade data into price dict.

    Returns dict compatible with MarketDataSource protocol (same schema
    as KISClient.get_current_price()), or None on parse error.
    """
    fields = data.split("^")
    if len(fields) < 14:
        return None

    try:
        symbol = fields[_F_SYMBOL]
        if not symbol or not symbol.isdigit() or len(symbol) != 6:
            return None

        price = float(fields[_F_PRICE])
        if price <= 0 or price > 100_000_000:
            return None

        volume = int(float(fields[_F_VOLUME]))
        if volume < 0:
            return None

        change_pct = float(fields[_F_CHANGE_PCT]) if fields[_F_CHANGE_PCT] else 0.0
        return {
            "code": symbol,
            "close": price,
            "open": float(fields[_F_OPEN]),
            "high": float(fields[_F_HIGH]),
            "low": float(fields[_F_LOW]),
            "volume": volume,
            "change": change_pct / 100.0,
            "timestamp": time.time(),
        }
    except (ValueError, IndexError):
        return None


class KISStockPriceFeed:
    """Real-time stock price feed via KIS WebSocket (H0STCNT0).

    Implements MarketDataSource protocol for seamless integration
    with MarketDataProvider. Falls back to REST API client for symbols
    without cached WebSocket data.

    Thread model:
    - WebSocket runs in a daemon thread (receives messages)
    - Message processing runs in a second daemon thread (parses and caches)
    - get_current_price() reads from cache (thread-safe dict access)
    """

    WS_URL_REAL = "ws://ops.koreainvestment.com:21000"
    WS_URL_MOCK = "ws://ops.koreainvestment.com:31000"

    def __init__(
        self,
        config: KISAuthConfig,
        tick_callback: Callable[[str, dict[str, Any], datetime], None] | None = None,
    ):
        """
        Args:
            config: KIS authentication config (same as REST client).
            tick_callback: Optional per-tick callback (symbol, data, timestamp).
        """
        self._config = config
        self._tick_callback = tick_callback
        self._ws_url = self.WS_URL_REAL if config.is_real else self.WS_URL_MOCK

        # Load feed config from streaming.yaml
        feed_cfg = _load_feed_config()
        self._max_symbols = int(feed_cfg.get("max_symbols", 40))
        self._ping_interval = int(feed_cfg.get("ping_interval", 30))
        self._ping_timeout = int(feed_cfg.get("ping_timeout", 10))
        self._connection_timeout = float(feed_cfg.get("connection_timeout", 10.0))
        self._subscription_delay = float(feed_cfg.get("subscription_delay", 0.05))
        self._approval_key_timeout = int(feed_cfg.get("approval_key_timeout", 10))
        queue_maxsize = int(feed_cfg.get("queue_maxsize", 10000))
        self._stale_threshold = float(
            feed_cfg.get("stale_threshold_seconds", 3.0)
        )

        # Price cache: {symbol: price_dict}
        self._prices: dict[str, dict[str, Any]] = {}
        self._prices_lock = threading.Lock()
        self._symbol_tick_ts: dict[str, float] = {}

        # WebSocket state
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._proc_thread: Optional[threading.Thread] = None
        self._running = False
        self._connected = threading.Event()

        # Approval key for WebSocket subscription
        self._approval_key: Optional[str] = None

        # AES decryption
        self._aes_key: Optional[bytes] = None
        self._aes_iv: Optional[bytes] = None

        # Message queue
        self._queue: queue.Queue = queue.Queue(maxsize=queue_maxsize)

        # Subscribed symbols
        self._subscribed: set[str] = set()
        self._sub_lock = threading.Lock()

        # Stats
        self._tick_count = 0
        self._dropped_count = 0
        self._last_tick_ts: float | None = None

        # Reconnect state
        self._reconnect_delay = float(feed_cfg.get("reconnect_initial_delay", 1.0))
        self._max_reconnect_delay = float(feed_cfg.get("reconnect_max_delay", 60.0))
        self._initial_reconnect_delay = self._reconnect_delay

    def set_tick_callback(
        self, callback: Callable[[str, dict[str, Any], datetime], None] | None
    ) -> None:
        self._tick_callback = callback

    # ----- MarketDataSource protocol -----

    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        """Get latest price for symbol.

        Returns instantly from WebSocket cache. Returns empty dict if no
        data is available yet (no REST fallback to avoid rate-limit pressure).
        """
        with self._prices_lock:
            data = self._prices.get(symbol)
        if data is not None:
            return data
        return {}

    # ----- Lifecycle -----

    async def start(self) -> None:
        """Start WebSocket connection and message processing."""
        if self._running:
            return

        self._get_approval_key()

        self._ws = websocket.WebSocketApp(
            self._ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        self._connected.clear()
        self._running = True

        self._ws_thread = threading.Thread(
            target=self._ws.run_forever,
            kwargs={
                "ping_interval": self._ping_interval,
                "ping_timeout": self._ping_timeout,
            },
            daemon=True,
            name="StockPriceFeed-WS",
        )
        self._ws_thread.start()

        self._proc_thread = threading.Thread(
            target=self._process_loop,
            daemon=True,
            name="StockPriceFeed-Proc",
        )
        self._proc_thread.start()

        if not self._connected.wait(timeout=self._connection_timeout):
            self._running = False
            raise ConnectionError("Stock WebSocket connection timeout")

        logger.info(f"[StockPriceFeed] Connected to {self._ws_url}")

    async def stop(self) -> None:
        """Stop WebSocket and cleanup."""
        self._running = False

        if self._ws:
            self._ws.close()

        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=5.0)
        if self._proc_thread and self._proc_thread.is_alive():
            self._proc_thread.join(timeout=5.0)

        self._connected.clear()
        self._subscribed.clear()
        with self._prices_lock:
            self._prices.clear()
            self._symbol_tick_ts.clear()
        logger.info(
            f"[StockPriceFeed] Stopped (processed {self._tick_count} ticks)"
        )

    def update_symbols(self, symbols: list[str]) -> None:
        """Update subscribed symbols (subscribe new, unsubscribe removed).

        Respects max_symbols limit. Excess symbols are silently dropped.
        """
        desired = set(symbols[:self._max_symbols])

        with self._sub_lock:
            to_add = desired - self._subscribed
            to_remove = self._subscribed - desired

            for sym in to_remove:
                self._send_unsub(sym)
                self._subscribed.discard(sym)
                with self._prices_lock:
                    self._prices.pop(sym, None)
                    self._symbol_tick_ts.pop(sym, None)

            for sym in to_add:
                self._send_sub(sym)
                self._subscribed.add(sym)
                time.sleep(self._subscription_delay)

            if to_add or to_remove:
                logger.info(
                    f"[StockPriceFeed] Symbols: "
                    f"+{len(to_add)} -{len(to_remove)} "
                    f"= {len(self._subscribed)} total"
                )

    @property
    def symbol_count(self) -> int:
        return len(self._subscribed)

    def has_price(self, symbol: str) -> bool:
        return symbol in self._prices

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

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
        return staleness < self._stale_threshold

    def get_health_status(self) -> dict[str, Any]:
        """Get detailed health status for diagnostics.

        Returns:
            Dictionary with health metrics:
            - running: bool - whether feed is running
            - connected: bool - whether WebSocket is connected
            - last_tick_ts: float | None - timestamp of last tick
            - staleness_seconds: float | None - seconds since last tick
            - is_healthy: bool - overall health status
            - symbol_count: int - number of subscribed symbols
            - cached_symbols: list[str] - symbols with cached data
            - tick_count: int - total ticks processed
            - dropped_count: int - total dropped messages
        """
        with self._prices_lock:
            cached_symbols = list(self._prices.keys())
            fresh_symbol_count = 0
            stale_symbol_count = 0
            now = time.time()
            for symbol in self._subscribed:
                last_symbol_tick = self._symbol_tick_ts.get(symbol)
                if last_symbol_tick is None:
                    stale_symbol_count += 1
                elif now - last_symbol_tick < self._stale_threshold:
                    fresh_symbol_count += 1
                else:
                    stale_symbol_count += 1

        staleness = self.get_staleness_seconds()

        return {
            "running": self._running,
            "connected": self._connected.is_set(),
            "last_tick_ts": self._last_tick_ts,
            "staleness_seconds": staleness,
            "is_healthy": self.is_healthy(),
            "symbol_count": len(self._subscribed),
            "cached_symbols": cached_symbols,
            "fresh_symbol_count": fresh_symbol_count,
            "stale_symbol_count": stale_symbol_count,
            "stale_threshold_seconds": self._stale_threshold,
            "tick_count": self._tick_count,
            "dropped_count": self._dropped_count,
        }

    @property
    def supports_instant_read(self) -> bool:
        """Signal to data provider that reads are instant (no stagger needed)."""
        return True

    # ----- Approval Key -----

    def _get_approval_key(self) -> None:
        import requests

        url = f"{self._config.base_url}/oauth2/Approval"
        if not url.startswith("https://"):
            raise ValueError("Approval key request requires HTTPS")

        try:
            resp = requests.post(
                url,
                json={
                    "grant_type": "client_credentials",
                    "appkey": self._config.app_key,
                    "secretkey": self._config.app_secret,
                },
                headers={"content-type": "application/json"},
                timeout=self._approval_key_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ConnectionError(f"Approval key request failed: {e}") from e

        if "approval_key" not in data:
            error_code = data.get("error_code", data.get("msg_cd", "unknown"))
            raise ValueError(f"Failed to get approval key: {error_code}")

        self._approval_key = data["approval_key"]
        logger.info("[StockPriceFeed] Approval key obtained")

    # ----- WebSocket Handlers -----

    def _on_open(self, _ws):
        logger.info("[StockPriceFeed] Connection opened")
        self._connected.set()

    def _on_message(self, _ws, message: str):
        try:
            self._queue.put_nowait(message)
        except queue.Full:
            self._dropped_count += 1
            if self._dropped_count % 1000 == 1:
                logger.warning(
                    f"[StockPriceFeed] Queue full, dropped {self._dropped_count} msgs total"
                )
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(message)
            except queue.Empty:
                pass

    def _on_error(self, _ws, error):
        logger.error(f"[StockPriceFeed] WS error: {error}")

    def _on_close(self, _ws, code, msg):
        logger.info(f"[StockPriceFeed] Connection closed: {code} {msg}")
        self._connected.clear()
        with self._prices_lock:
            self._prices.clear()  # Invalidate stale cache
            self._symbol_tick_ts.clear()

        if self._running:
            threading.Thread(
                target=self._reconnect,
                daemon=True,
                name="StockPriceFeed-Reconnect",
            ).start()

    def _reconnect(self):
        """Reconnect with exponential backoff."""
        delay = self._reconnect_delay
        while self._running and not self._connected.is_set():
            logger.info(f"[StockPriceFeed] Reconnecting in {delay:.1f}s...")
            time.sleep(delay)
            if not self._running:
                break

            try:
                self._get_approval_key()
                self._aes_key = None
                self._aes_iv = None

                self._ws = websocket.WebSocketApp(
                    self._ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )

                self._ws_thread = threading.Thread(
                    target=self._ws.run_forever,
                    kwargs={
                        "ping_interval": self._ping_interval,
                        "ping_timeout": self._ping_timeout,
                    },
                    daemon=True,
                    name="StockPriceFeed-WS",
                )
                self._ws_thread.start()

                if self._connected.wait(timeout=self._connection_timeout):
                    logger.info("[StockPriceFeed] Reconnected successfully")
                    self._reconnect_delay = self._initial_reconnect_delay
                    # Re-subscribe all symbols
                    with self._sub_lock:
                        for sym in list(self._subscribed):
                            self._send_sub(sym)
                            time.sleep(0.05)
                    return
            except Exception as e:
                logger.error(f"[StockPriceFeed] Reconnect failed: {e}")

            delay = min(delay * 2, self._max_reconnect_delay)

    # ----- Message Processing -----

    def _process_loop(self):
        """Process messages from queue in background thread."""
        while self._running:
            try:
                msg = self._queue.get(timeout=1.0)
                self._handle_message(msg)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[StockPriceFeed] Process error: {e}")

    def _handle_message(self, message: str):
        if "|" in message:
            parts = message.split("|")
            if len(parts) >= 4:
                is_encrypted = parts[0] == "1"
                tr_id = parts[1]
                data_str = parts[3]

                if is_encrypted and self._aes_key:
                    try:
                        data_str = self._decrypt(data_str)
                    except Exception as e:
                        logger.warning(
                            f"[StockPriceFeed] Decryption failed: {e}"
                        )
                        return

                if tr_id == TR_STOCK_TRADE:
                    parsed = _parse_stock_trade(data_str)
                    if parsed:
                        with self._prices_lock:
                            self._prices[parsed["code"]] = parsed
                            self._tick_count += 1
                            ts = parsed.get("timestamp")
                            self._last_tick_ts = ts if ts is not None else time.time()
                            self._symbol_tick_ts[parsed["code"]] = self._last_tick_ts
                        # Per-tick callback (outside lock to prevent deadlock)
                        if self._tick_callback:
                            try:
                                tick_ts = datetime.fromtimestamp(
                                    parsed.get("timestamp", time.time())
                                )
                            except (OSError, ValueError, TypeError):
                                tick_ts = datetime.now()
                            try:
                                self._tick_callback(parsed["code"], parsed, tick_ts)
                            except Exception as e:
                                logger.debug(f"[StockPriceFeed] Tick callback error: {e}")
        else:
            try:
                data = json.loads(message)
                self._handle_json(data)
            except json.JSONDecodeError:
                pass

    def _handle_json(self, data: dict):
        header = data.get("header", {})
        body = data.get("body", {})

        # Store AES key/IV from subscription response
        output = body.get("output", {})
        if "key" in output and "iv" in output:
            self._aes_key = output["key"].encode("utf-8")
            self._aes_iv = output["iv"].encode("utf-8")
            logger.debug("[StockPriceFeed] AES key received")

        # PINGPONG keepalive
        if header.get("tr_cd") == "PINGPONG":
            if self._ws and self._connected.is_set():
                self._ws.send(json.dumps(data))

        msg_code = body.get("msg_cd", "")
        if msg_code and msg_code != "OPSP0000":
            logger.warning(
                f"[StockPriceFeed] {msg_code}: {body.get('msg1', '')}"
            )

    # ----- Subscribe / Unsubscribe -----

    def _send_sub(self, symbol: str):
        msg = {
            "header": {
                "approval_key": self._approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": TR_STOCK_TRADE,
                    "tr_key": symbol,
                }
            },
        }
        if self._ws and self._connected.is_set():
            self._ws.send(json.dumps(msg))
            logger.debug(f"[StockPriceFeed] Subscribed: {symbol}")

    def _send_unsub(self, symbol: str):
        msg = {
            "header": {
                "approval_key": self._approval_key,
                "custtype": "P",
                "tr_type": "2",
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": TR_STOCK_TRADE,
                    "tr_key": symbol,
                }
            },
        }
        if self._ws and self._connected.is_set():
            self._ws.send(json.dumps(msg))
            logger.debug(f"[StockPriceFeed] Unsubscribed: {symbol}")

    # ----- AES Decryption -----

    def _decrypt(self, encrypted_data: str) -> str:
        if not self._aes_key or not self._aes_iv:
            raise ValueError("AES key not initialized")
        encrypted_bytes = base64.b64decode(encrypted_data)
        cipher = AES.new(self._aes_key, AES.MODE_CBC, self._aes_iv)
        decrypted = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
        return decrypted.decode("utf-8")
