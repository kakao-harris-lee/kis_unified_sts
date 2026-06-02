"""
KIS WebSocket Adapter for Realtime Futures Data

KIS OpenAPI WebSocket을 통해 실시간 선물 호가/체결 데이터를 수신합니다.
BaseAPIAdapter를 구현하여 통합 프로젝트의 DataCollector와 연동됩니다.

Features:
    - 선물 호가(H0IFASP0) / 체결(H0IFCNT0) 실시간 수신
    - AES256 암호화 데이터 복호화
    - L5 호가 파싱
    - OHLC 데이터 파싱
    - Thread-safe state management

Usage:
    >>> from shared.kis.websocket import KISWebSocketAdapter
    >>> from shared.kis.auth import KISAuthConfig
    >>>
    >>> config = KISAuthConfig(app_key="...", app_secret="...", is_real=True)
    >>> adapter = KISWebSocketAdapter(config)
    >>> adapter.connect()
    >>> adapter.subscribe(["101V01"], callback)  # KOSPI200 Mini

Reference:
    - Migrated from kospi_mini_sts/src/collector/kis_websocket.py
"""

from __future__ import annotations

import base64
import json
import logging
import queue
import re
import threading
import time
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import websocket

from shared.collector.adapter import BaseAPIAdapter
from shared.collector.models import TickData
from shared.kis.auth import KISAuthConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# WebSocket TR IDs for Futures
TR_FUTURES_ASK = "H0IFASP0"  # 선물옵션 호가
TR_FUTURES_CNT = "H0IFCNT0"  # 선물옵션 체결

# Queue configuration
MESSAGE_QUEUE_MAXSIZE = 10000

# Symbol validation pattern (alphanumeric, 5-10 chars)
SYMBOL_PATTERN = re.compile(r"^[0-9A-Za-z]{5,10}$")

# Field indices for H0IFASP0 (orderbook)
ORDERBOOK_FIELDS = {
    # KIS H0IFASP0 (38 fields observed):
    #  - ask_price L1-L5: 2-6
    #  - bid_price L1-L5: 7-11
    #  - ask_qty   L1-L5: 12-16
    #  - bid_qty   L1-L5: 17-21
    "bid_price": [7, 8, 9, 10, 11],  # L1-L5
    "bid_qty": [17, 18, 19, 20, 21],
    "ask_price": [2, 3, 4, 5, 6],
    "ask_qty": [12, 13, 14, 15, 16],
}
ORDERBOOK_MIN_FIELDS = (
    max(
        max(ORDERBOOK_FIELDS["bid_price"]),
        max(ORDERBOOK_FIELDS["bid_qty"]),
        max(ORDERBOOK_FIELDS["ask_price"]),
        max(ORDERBOOK_FIELDS["ask_qty"]),
    )
    + 1
)

# Field indices for H0IFCNT0 (trade)
# [0]=종목코드, [1]=체결시간, [2]=전일대비, [3]=부호, [4]=대비율
# [5]=현재가, [6]=시가, [7]=고가, [8]=저가
# [9]=체결수량, [10]=누적체결수량, [11]=누적거래대금
# [18]=미결제약정
TRADE_FIELDS = {
    "current_price": 5,
    "open_price": 6,
    "high_price": 7,
    "low_price": 8,
    "tick_volume": 9,
    "cumulative_volume": 10,
    "open_interest": 18,
}

# Value bounds for validation
MAX_PRICE = 1e9
MIN_PRICE = -1e9


class WSMessageType(str, Enum):
    """WebSocket message types."""

    SUBSCRIBE = "1"
    UNSUBSCRIBE = "2"


# =============================================================================
# Pure Parsing Functions (for testability)
# =============================================================================


def _safe_float(
    fields: List[str], index: int, default: Optional[float] = None
) -> Optional[float]:
    """Safely extract and validate float from fields.

    Args:
        fields: List of string fields
        index: Index to extract from
        default: Default value if extraction fails

    Returns:
        Extracted float or default value
    """
    try:
        if index < len(fields) and fields[index]:
            value = float(fields[index])
            # Bounds validation
            if MIN_PRICE < value < MAX_PRICE:
                return value
            logger.debug(f"[KIS WS] Value out of bounds at index {index}: {value}")
            return default
        return default
    except (ValueError, IndexError):
        return default


def parse_futures_orderbook(
    symbol: str, data: str, timestamp: float
) -> Optional[TickData]:
    """Parse futures orderbook (호가) data.

    Pure function for easy testing.

    Args:
        symbol: Futures symbol code
        data: Pipe-separated data string
        timestamp: Unix timestamp

    Returns:
        TickData or None if parsing fails
    """
    fields = data.split("^")
    if len(fields) < ORDERBOOK_MIN_FIELDS:
        logger.debug(
            "[KIS WS] Orderbook parse skipped: insufficient fields (%d < %d)",
            len(fields),
            ORDERBOOK_MIN_FIELDS,
        )
        return None

    # field[0] = 종목코드: use actual symbol from data body
    actual_symbol = fields[0].strip() or symbol

    try:
        bid_price = ORDERBOOK_FIELDS["bid_price"]
        bid_qty = ORDERBOOK_FIELDS["bid_qty"]
        ask_price = ORDERBOOK_FIELDS["ask_price"]
        ask_qty = ORDERBOOK_FIELDS["ask_qty"]
        return TickData(
            symbol=actual_symbol,
            timestamp=timestamp,
            # 매수호가 (bid) L1-L5
            bid_price_1=_safe_float(fields, bid_price[0], 0.0),
            bid_qty_1=_safe_float(fields, bid_qty[0], 0.0),
            bid_price_2=_safe_float(fields, bid_price[1]),
            bid_qty_2=_safe_float(fields, bid_qty[1]),
            bid_price_3=_safe_float(fields, bid_price[2]),
            bid_qty_3=_safe_float(fields, bid_qty[2]),
            bid_price_4=_safe_float(fields, bid_price[3]),
            bid_qty_4=_safe_float(fields, bid_qty[3]),
            bid_price_5=_safe_float(fields, bid_price[4]),
            bid_qty_5=_safe_float(fields, bid_qty[4]),
            # 매도호가 (ask) L1-L5
            ask_price_1=_safe_float(fields, ask_price[0], 0.0),
            ask_qty_1=_safe_float(fields, ask_qty[0], 0.0),
            ask_price_2=_safe_float(fields, ask_price[1]),
            ask_qty_2=_safe_float(fields, ask_qty[1]),
            ask_price_3=_safe_float(fields, ask_price[2]),
            ask_qty_3=_safe_float(fields, ask_qty[2]),
            ask_price_4=_safe_float(fields, ask_price[3]),
            ask_qty_4=_safe_float(fields, ask_qty[3]),
            ask_price_5=_safe_float(fields, ask_price[4]),
            ask_qty_5=_safe_float(fields, ask_qty[4]),
        )
    except Exception as e:
        logger.warning(f"[KIS WS] Failed to parse orderbook: {e}")
        return None


def parse_futures_trade(symbol: str, data: str, timestamp: float) -> Optional[TickData]:
    """Parse futures trade (체결) data.

    Pure function for easy testing.

    Args:
        symbol: Futures symbol code
        data: Pipe-separated data string
        timestamp: Unix timestamp

    Returns:
        TickData or None if parsing fails
    """
    fields = data.split("^")
    if len(fields) < 19:
        return None

    # field[0] = 종목코드: use actual symbol from data body
    actual_symbol = fields[0].strip() or symbol

    try:
        return TickData(
            symbol=actual_symbol,
            timestamp=timestamp,
            # 최우선 호가 (체결 시점에는 없음)
            bid_price_1=0.0,
            bid_qty_1=0.0,
            ask_price_1=0.0,
            ask_qty_1=0.0,
            # 체결가 및 OHLC
            current_price=_safe_float(fields, TRADE_FIELDS["current_price"]),
            open_price=_safe_float(fields, TRADE_FIELDS["open_price"]),
            high_price=_safe_float(fields, TRADE_FIELDS["high_price"]),
            low_price=_safe_float(fields, TRADE_FIELDS["low_price"]),
            # 거래량
            tick_volume=_safe_float(fields, TRADE_FIELDS["tick_volume"]),
            cumulative_volume=_safe_float(fields, TRADE_FIELDS["cumulative_volume"]),
            # 미결제약정
            open_interest=_safe_float(fields, TRADE_FIELDS["open_interest"]),
        )
    except Exception as e:
        logger.warning(f"[KIS WS] Failed to parse trade: {e}")
        return None


# =============================================================================
# WebSocket Adapter
# =============================================================================


class KISWebSocketAdapter(BaseAPIAdapter):
    """KIS WebSocket Adapter for realtime futures data.

    Implements BaseAPIAdapter interface for integration with DataCollector.
    Thread-safe with proper locking and event-based synchronization.

    Attributes:
        config: KIS authentication configuration
        ws_url: WebSocket server URL
        ws: WebSocket connection instance
        callback: Tick data callback function

    Example:
        >>> config = KISAuthConfig(app_key="...", app_secret="...")
        >>> adapter = KISWebSocketAdapter(config)
        >>> adapter.connect()
        >>> adapter.subscribe(["101V01"], lambda tick: print(tick))
    """

    # WebSocket URLs
    WS_URL_REAL = "ws://ops.koreainvestment.com:21000"
    WS_URL_MOCK = "ws://ops.koreainvestment.com:31000"

    def __init__(self, config: KISAuthConfig):
        """Initialize WebSocket adapter.

        Args:
            config: KIS authentication configuration
        """
        self.config = config
        self.ws_url = self.WS_URL_REAL if config.is_real else self.WS_URL_MOCK

        # WebSocket instance
        self.ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None

        # Thread-safe state management
        self._state_lock = threading.Lock()
        self._connected_event = threading.Event()
        self._running = False
        self._connected = False

        # Callback (protected by _state_lock)
        self._callback: Optional[Callable[[TickData], None]] = None
        self._subscribed_symbols: List[str] = []

        # AES decryption key (obtained from approval response)
        self._aes_key: Optional[bytes] = None
        self._aes_iv: Optional[bytes] = None

        # Approval key (for subscription)
        self._approval_key: Optional[str] = None

        # Bounded message queue to prevent OOM
        self._message_queue: queue.Queue = queue.Queue(maxsize=MESSAGE_QUEUE_MAXSIZE)

        # Health monitoring
        self._last_message_ts: Optional[float] = None
        # Counters for message throughput and queue-drop tracking.
        # Both are incremented under _state_lock (same lock that guards
        # _last_message_ts) for thread-safe reads in get_health_status().
        self._messages_received: int = 0
        self._messages_dropped: int = 0

    # -------------------------------------------------------------------------
    # Thread-Safe State Accessors
    # -------------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Thread-safe connected state check."""
        with self._state_lock:
            return self._connected

    @property
    def is_running(self) -> bool:
        """Thread-safe running state check."""
        with self._state_lock:
            return self._running

    def _set_connected(self, value: bool) -> None:
        """Thread-safe connected state setter."""
        with self._state_lock:
            self._connected = value
        if value:
            self._connected_event.set()
        else:
            self._connected_event.clear()

    def _set_running(self, value: bool) -> None:
        """Thread-safe running state setter."""
        with self._state_lock:
            self._running = value

    # -------------------------------------------------------------------------
    # Health Monitoring
    # -------------------------------------------------------------------------

    def get_connection_staleness(self) -> Optional[float]:
        """Get time in seconds since last WebSocket message.

        Returns:
            Seconds since last message, or None if no messages received yet
        """
        with self._state_lock:
            if self._last_message_ts is None:
                return None
            return max(0.0, time.time() - self._last_message_ts)

    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of WebSocket connection.

        Returns:
            Dictionary containing:
                - connected: bool - WebSocket connection state
                - running: bool - Thread running state
                - last_message_ts: float | None - Unix timestamp of last message
                - staleness_seconds: float | None - Seconds since last message
                - messages_received: int - Total messages received
                - messages_dropped: int - Total messages dropped (queue full)
                - queue_depth: int - Current message queue size
        """
        with self._state_lock:
            last_msg_ts = self._last_message_ts
            connected = self._connected
            running = self._running
            messages_received = self._messages_received
            messages_dropped = self._messages_dropped

        staleness = None
        if last_msg_ts is not None:
            staleness = max(0.0, time.time() - last_msg_ts)

        return {
            "connected": connected,
            "running": running,
            "last_message_ts": last_msg_ts,
            "staleness_seconds": staleness,
            "messages_received": messages_received,
            "messages_dropped": messages_dropped,
            "queue_depth": self._message_queue.qsize(),
        }

    # -------------------------------------------------------------------------
    # BaseAPIAdapter Implementation
    # -------------------------------------------------------------------------

    def connect(self) -> None:
        """Establish WebSocket connection.

        Raises:
            ConnectionError: If connection times out
            ValueError: If approval key request fails
        """
        if self.is_connected:
            logger.warning("[KIS WS] Already connected")
            return

        # Get approval key first (REST API call)
        self._get_approval_key()

        # Create WebSocket connection
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        # Reset event before starting
        self._connected_event.clear()

        # Start WebSocket in background thread
        self._set_running(True)
        self._ws_thread = threading.Thread(
            target=self._run_websocket, daemon=True, name="KISWebSocket"
        )
        self._ws_thread.start()

        # Wait for connection using event (not busy-wait)
        if not self._connected_event.wait(timeout=10.0):
            self._set_running(False)
            raise ConnectionError("WebSocket connection timeout")

        logger.info(f"[KIS WS] Connected to {self.ws_url}")

    def subscribe(
        self, symbols: List[str], callback: Callable[[TickData], None]
    ) -> None:
        """Subscribe to symbols and start receiving data.

        This method blocks until disconnect() is called.

        Args:
            symbols: List of futures codes to subscribe
            callback: Function called on each tick

        Raises:
            ValueError: If symbols list is empty or contains invalid format
        """
        # Input validation
        if not symbols:
            raise ValueError("At least one symbol required")

        for symbol in symbols:
            if not SYMBOL_PATTERN.match(symbol):
                raise ValueError(f"Invalid symbol format: {symbol}")

        # Store callback and symbols (thread-safe)
        with self._state_lock:
            self._callback = callback
            self._subscribed_symbols = list(symbols)

        # Subscribe to each symbol for both orderbook and trade
        for symbol in symbols:
            self._send_subscribe(symbol, TR_FUTURES_ASK)
            time.sleep(0.1)  # Rate limit
            self._send_subscribe(symbol, TR_FUTURES_CNT)
            time.sleep(0.1)

        logger.info(f"[KIS WS] Subscribed to {len(symbols)} symbols")

        # Process messages from queue (blocking)
        while self.is_running:
            try:
                msg = self._message_queue.get(timeout=1.0)
                self._process_message(msg)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[KIS WS] Error processing message: {e}")

    def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._set_running(False)

        # Get subscribed symbols safely
        with self._state_lock:
            symbols_to_unsub = list(self._subscribed_symbols)

        if self.ws:
            # Unsubscribe from all symbols
            for symbol in symbols_to_unsub:
                try:
                    self._send_unsubscribe(symbol, TR_FUTURES_ASK)
                    self._send_unsubscribe(symbol, TR_FUTURES_CNT)
                except Exception:
                    pass

            self.ws.close()

        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=5.0)

        self._set_connected(False)
        logger.info("[KIS WS] Disconnected")

    # -------------------------------------------------------------------------
    # Approval Key
    # -------------------------------------------------------------------------

    def _get_approval_key(self) -> None:
        """Get WebSocket approval key via REST API.

        Raises:
            ValueError: If HTTPS is not used or approval key not received
        """
        import requests

        url = f"{self.config.base_url}/oauth2/Approval"

        # Security: Ensure HTTPS is used
        if not url.startswith("https://"):
            raise ValueError("Approval key request requires HTTPS")

        payload = {
            "grant_type": "client_credentials",
            "appkey": self.config.app_key,
            "secretkey": self.config.app_secret,
        }

        headers = {"content-type": "application/json"}

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()

            if "approval_key" not in data:
                # Sanitize error message (don't leak secrets)
                error_code = data.get("error_code", data.get("msg_cd", "unknown"))
                raise ValueError(f"Failed to get approval key: error_code={error_code}")

            self._approval_key = data["approval_key"]
            logger.info("[KIS WS] Approval key obtained")

        except requests.RequestException as e:
            logger.error(
                f"[KIS WS] Network error getting approval key: {type(e).__name__}"
            )
            raise
        except Exception as e:
            logger.error(f"[KIS WS] Failed to get approval key: {type(e).__name__}")
            raise

    # -------------------------------------------------------------------------
    # WebSocket Handlers
    # -------------------------------------------------------------------------

    def _run_websocket(self) -> None:
        """Run WebSocket event loop in background thread."""
        try:
            self.ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as e:
            logger.error(f"[KIS WS] WebSocket error: {e}")
        finally:
            self._set_connected(False)
            self._set_running(False)

    def _on_open(self, _ws) -> None:
        """WebSocket connection opened."""
        logger.info("[KIS WS] Connection opened")
        self._set_connected(True)

    def _on_message(self, _ws, message: str) -> None:
        """WebSocket message received.

        Uses bounded queue with overflow handling.
        """
        # Track timestamp and received count for health monitoring.
        # _messages_received is incremented here (every message); _state_lock
        # is acquired once for both fields to keep the critical section short.
        with self._state_lock:
            self._last_message_ts = time.time()
            self._messages_received += 1

        try:
            self._message_queue.put_nowait(message)
        except queue.Full:
            # Drop oldest message to make room; record the drop under the lock.
            logger.warning("[KIS WS] Message queue full, dropping oldest message")
            with self._state_lock:
                self._messages_dropped += 1
            try:
                self._message_queue.get_nowait()
                self._message_queue.put_nowait(message)
            except queue.Empty:
                pass

    def _on_error(self, _ws, error) -> None:
        """WebSocket error occurred."""
        logger.error(f"[KIS WS] Error: {error}")

    def _on_close(self, _ws, close_status_code, close_msg) -> None:
        """WebSocket connection closed."""
        logger.info(f"[KIS WS] Connection closed: {close_status_code} {close_msg}")
        self._set_connected(False)

    # -------------------------------------------------------------------------
    # Subscribe/Unsubscribe
    # -------------------------------------------------------------------------

    def _send_subscribe(self, symbol: str, tr_id: str) -> None:
        """Send subscription request."""
        msg = {
            "header": {
                "approval_key": self._approval_key,
                "custtype": "P",
                "tr_type": WSMessageType.SUBSCRIBE.value,
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": tr_id,
                    "tr_key": symbol,
                }
            },
        }

        if self.ws and self.is_connected:
            self.ws.send(json.dumps(msg))
            logger.debug(f"[KIS WS] Subscribed: {tr_id} {symbol}")

    def _send_unsubscribe(self, symbol: str, tr_id: str) -> None:
        """Send unsubscription request."""
        msg = {
            "header": {
                "approval_key": self._approval_key,
                "custtype": "P",
                "tr_type": WSMessageType.UNSUBSCRIBE.value,
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": tr_id,
                    "tr_key": symbol,
                }
            },
        }

        if self.ws and self.is_connected:
            self.ws.send(json.dumps(msg))
            logger.debug(f"[KIS WS] Unsubscribed: {tr_id} {symbol}")

    # -------------------------------------------------------------------------
    # Message Processing
    # -------------------------------------------------------------------------

    def _process_message(self, message: str) -> None:
        """Process incoming WebSocket message."""
        # Check if encrypted data (pipe-separated)
        if "|" in message:
            parts = message.split("|")
            if len(parts) >= 4:
                tr_id = parts[1]
                is_encrypted = parts[0] == "1"
                data_str = parts[3]

                if is_encrypted and self._aes_key:
                    # Decrypt data
                    try:
                        data_str = self._decrypt(data_str)
                    except Exception as e:
                        logger.warning(f"[KIS WS] Decryption failed, skipping: {e}")
                        return

                # Parse based on TR ID using pure functions
                timestamp = time.time()
                tick = None

                if tr_id == TR_FUTURES_ASK:
                    tick = parse_futures_orderbook(parts[2], data_str, timestamp)
                elif tr_id == TR_FUTURES_CNT:
                    tick = parse_futures_trade(parts[2], data_str, timestamp)

                # Invoke callback (thread-safe read)
                if tick:
                    with self._state_lock:
                        callback = self._callback
                    if callback:
                        try:
                            callback(tick)
                        except Exception as e:
                            logger.error(f"[KIS WS] Callback error: {e}")

        else:
            # JSON message (subscription response, etc.)
            try:
                data = json.loads(message)
                self._handle_json_message(data)
            except json.JSONDecodeError:
                logger.warning(f"[KIS WS] Unknown message format: {message[:100]}")

    def _handle_json_message(self, data: Dict[str, Any]) -> None:
        """Handle JSON formatted message (subscription response, etc.)."""
        header = data.get("header", {})
        body = data.get("body", {})

        # Check for encryption key
        if "output" in body:
            output = body["output"]
            if "key" in output and "iv" in output:
                # Store AES key and IV for decryption
                self._aes_key = output["key"].encode("utf-8")
                self._aes_iv = output["iv"].encode("utf-8")
                logger.info("[KIS WS] AES key received")

        # Respond to PINGPONG
        if header.get("tr_cd") == "PINGPONG":
            if self.ws and self.is_connected:
                self.ws.send(json.dumps(data))

        msg_code = body.get("msg_cd", "")
        if msg_code and msg_code != "OPSP0000":
            msg = body.get("msg1", "")
            logger.warning(f"[KIS WS] Response: {msg_code} - {msg}")

    # -------------------------------------------------------------------------
    # AES Decryption
    # -------------------------------------------------------------------------

    def _decrypt(self, encrypted_data: str) -> str:
        """Decrypt AES256 encrypted data.

        Args:
            encrypted_data: Base64 encoded encrypted data

        Returns:
            Decrypted string

        Raises:
            ValueError: If AES key not initialized
        """
        if not self._aes_key or not self._aes_iv:
            raise ValueError("AES key not initialized")

        encrypted_bytes = base64.b64decode(encrypted_data)
        cipher = AES.new(self._aes_key, AES.MODE_CBC, self._aes_iv)
        decrypted = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
        return decrypted.decode("utf-8")

    # -------------------------------------------------------------------------
    # Legacy Parsing Methods (delegate to pure functions)
    # -------------------------------------------------------------------------

    def _parse_futures_ask(self, symbol: str, data: str) -> Optional[TickData]:
        """Parse futures orderbook data. Delegates to pure function."""
        return parse_futures_orderbook(symbol, data, time.time())

    def _parse_futures_cnt(self, symbol: str, data: str) -> Optional[TickData]:
        """Parse futures trade data. Delegates to pure function."""
        return parse_futures_trade(symbol, data, time.time())


# =============================================================================
# Factory Function
# =============================================================================


def create_websocket_adapter(
    app_key: Optional[str] = None,
    app_secret: Optional[str] = None,
    is_real: bool = True,
) -> KISWebSocketAdapter:
    """Create KIS WebSocket adapter.

    Args:
        app_key: KIS API app key (env fallback: KIS_APP_KEY)
        app_secret: KIS API app secret (env fallback: KIS_APP_SECRET)
        is_real: True for real trading, False for mock

    Returns:
        KISWebSocketAdapter instance
    """
    config = KISAuthConfig(
        app_key=app_key or "",
        app_secret=app_secret or "",
        is_real=is_real,
    )

    return KISWebSocketAdapter(config)
