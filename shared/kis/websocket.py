"""
KIS WebSocket Adapter for Realtime Futures Data

KIS OpenAPI WebSocket을 통해 실시간 선물 호가/체결 데이터를 수신합니다.
BaseAPIAdapter를 구현하여 통합 프로젝트의 DataCollector와 연동됩니다.

Features:
    - 선물 호가(H0IFASP0) / 체결(H0IFCNT0) 실시간 수신
    - AES256 암호화 데이터 복호화
    - L5 호가 파싱
    - OHLC 데이터 파싱

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
import hashlib
import json
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass
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


class WSMessageType(str, Enum):
    """WebSocket message types."""
    SUBSCRIBE = "1"
    UNSUBSCRIBE = "2"


# =============================================================================
# WebSocket Adapter
# =============================================================================


class KISWebSocketAdapter(BaseAPIAdapter):
    """KIS WebSocket Adapter for realtime futures data.

    Implements BaseAPIAdapter interface for integration with DataCollector.

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

        self.ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._running = False
        self._connected = False

        # Callback
        self._callback: Optional[Callable[[TickData], None]] = None
        self._subscribed_symbols: List[str] = []

        # AES decryption key (obtained from approval response)
        self._aes_key: Optional[bytes] = None
        self._aes_iv: Optional[bytes] = None

        # Approval key (for subscription)
        self._approval_key: Optional[str] = None

        # Message queue for thread safety
        self._message_queue: queue.Queue = queue.Queue()

    # -------------------------------------------------------------------------
    # BaseAPIAdapter Implementation
    # -------------------------------------------------------------------------

    def connect(self) -> None:
        """Establish WebSocket connection."""
        if self._connected:
            logger.warning("Already connected")
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

        # Start WebSocket in background thread
        self._running = True
        self._ws_thread = threading.Thread(
            target=self._run_websocket,
            daemon=True
        )
        self._ws_thread.start()

        # Wait for connection
        timeout = 10.0
        start = time.time()
        while not self._connected and time.time() - start < timeout:
            time.sleep(0.1)

        if not self._connected:
            raise ConnectionError("WebSocket connection timeout")

        logger.info(f"[KIS WS] Connected to {self.ws_url}")

    def subscribe(
        self,
        symbols: List[str],
        callback: Callable[[TickData], None]
    ) -> None:
        """Subscribe to symbols and start receiving data.

        This method blocks until disconnect() is called.

        Args:
            symbols: List of futures codes to subscribe
            callback: Function called on each tick
        """
        self._callback = callback
        self._subscribed_symbols = symbols

        # Subscribe to each symbol for both orderbook and trade
        for symbol in symbols:
            self._send_subscribe(symbol, TR_FUTURES_ASK)
            time.sleep(0.1)  # Rate limit
            self._send_subscribe(symbol, TR_FUTURES_CNT)
            time.sleep(0.1)

        logger.info(f"[KIS WS] Subscribed to {len(symbols)} symbols")

        # Process messages from queue (blocking)
        while self._running:
            try:
                msg = self._message_queue.get(timeout=1.0)
                self._process_message(msg)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[KIS WS] Error processing message: {e}")

    def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._running = False

        if self.ws:
            # Unsubscribe from all symbols
            for symbol in self._subscribed_symbols:
                try:
                    self._send_unsubscribe(symbol, TR_FUTURES_ASK)
                    self._send_unsubscribe(symbol, TR_FUTURES_CNT)
                except Exception:
                    pass

            self.ws.close()

        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=5.0)

        self._connected = False
        logger.info("[KIS WS] Disconnected")

    # -------------------------------------------------------------------------
    # Approval Key
    # -------------------------------------------------------------------------

    def _get_approval_key(self) -> None:
        """Get WebSocket approval key via REST API."""
        import requests

        url = f"{self.config.base_url}/oauth2/Approval"
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
                raise ValueError(f"Failed to get approval key: {data}")

            self._approval_key = data["approval_key"]
            logger.info("[KIS WS] Approval key obtained")

        except Exception as e:
            logger.error(f"[KIS WS] Failed to get approval key: {e}")
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
            self._connected = False
            self._running = False

    def _on_open(self, ws) -> None:
        """WebSocket connection opened."""
        logger.info("[KIS WS] Connection opened")
        self._connected = True

    def _on_message(self, ws, message: str) -> None:
        """WebSocket message received."""
        # Queue message for processing in main thread
        self._message_queue.put(message)

    def _on_error(self, ws, error) -> None:
        """WebSocket error occurred."""
        logger.error(f"[KIS WS] Error: {error}")

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        """WebSocket connection closed."""
        logger.info(f"[KIS WS] Connection closed: {close_status_code} {close_msg}")
        self._connected = False

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
            }
        }

        if self.ws and self._connected:
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
            }
        }

        if self.ws and self._connected:
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
                    data_str = self._decrypt(data_str)

                # Parse based on TR ID
                tick = None
                if tr_id == TR_FUTURES_ASK:
                    tick = self._parse_futures_ask(parts[2], data_str)
                elif tr_id == TR_FUTURES_CNT:
                    tick = self._parse_futures_cnt(parts[2], data_str)

                if tick and self._callback:
                    self._callback(tick)

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

        tr_id = header.get("tr_id")

        # Check for encryption key
        if "output" in body:
            output = body["output"]
            if "key" in output and "iv" in output:
                # Store AES key and IV for decryption
                self._aes_key = output["key"].encode("utf-8")
                self._aes_iv = output["iv"].encode("utf-8")
                logger.info("[KIS WS] AES key received")

        # Check for error
        if header.get("tr_cd") == "PINGPONG":
            # Respond to ping
            self.ws.send(message)

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
        """
        if not self._aes_key or not self._aes_iv:
            raise ValueError("AES key not initialized")

        try:
            encrypted_bytes = base64.b64decode(encrypted_data)
            cipher = AES.new(self._aes_key, AES.MODE_CBC, self._aes_iv)
            decrypted = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"[KIS WS] Decryption failed: {e}")
            raise

    # -------------------------------------------------------------------------
    # Futures Data Parsing
    # -------------------------------------------------------------------------

    def _parse_futures_ask(self, symbol: str, data: str) -> Optional[TickData]:
        """Parse futures orderbook (호가) data.

        Format: ^-separated fields
        주요 필드:
            - 0: 종목코드
            - 1: 영업시간
            - 2-11: 매도호가 1-10 (2,3=1차, 4,5=2차, ...)
            - 12-21: 매도호가잔량 1-10
            - 22-31: 매수호가 1-10
            - 32-41: 매수호가잔량 1-10
        """
        try:
            fields = data.split("^")
            if len(fields) < 42:
                return None

            # L5 호가 파싱
            tick = TickData(
                symbol=symbol,
                timestamp=time.time(),
                # 매수호가 (bid)
                bid_price_1=float(fields[22]) if fields[22] else 0.0,
                bid_qty_1=float(fields[32]) if fields[32] else 0.0,
                bid_price_2=float(fields[23]) if fields[23] else None,
                bid_qty_2=float(fields[33]) if fields[33] else None,
                bid_price_3=float(fields[24]) if fields[24] else None,
                bid_qty_3=float(fields[34]) if fields[34] else None,
                bid_price_4=float(fields[25]) if fields[25] else None,
                bid_qty_4=float(fields[35]) if fields[35] else None,
                bid_price_5=float(fields[26]) if fields[26] else None,
                bid_qty_5=float(fields[36]) if fields[36] else None,
                # 매도호가 (ask)
                ask_price_1=float(fields[2]) if fields[2] else 0.0,
                ask_qty_1=float(fields[12]) if fields[12] else 0.0,
                ask_price_2=float(fields[3]) if fields[3] else None,
                ask_qty_2=float(fields[13]) if fields[13] else None,
                ask_price_3=float(fields[4]) if fields[4] else None,
                ask_qty_3=float(fields[14]) if fields[14] else None,
                ask_price_4=float(fields[5]) if fields[5] else None,
                ask_qty_4=float(fields[15]) if fields[15] else None,
                ask_price_5=float(fields[6]) if fields[6] else None,
                ask_qty_5=float(fields[16]) if fields[16] else None,
            )

            return tick

        except (ValueError, IndexError) as e:
            logger.warning(f"[KIS WS] Failed to parse orderbook: {e}")
            return None

    def _parse_futures_cnt(self, symbol: str, data: str) -> Optional[TickData]:
        """Parse futures trade (체결) data.

        Format: ^-separated fields
        주요 필드:
            - 0: 종목코드
            - 1: 영업시간
            - 2: 현재가
            - 3: 전일대비부호
            - 4: 전일대비
            - 5: 등락율
            - 6: 시가
            - 7: 고가
            - 8: 저가
            - 11: 체결량 (tick volume)
            - 12: 누적거래량
            - 13: 누적거래대금
            - 14: 미결제약정
        """
        try:
            fields = data.split("^")
            if len(fields) < 15:
                return None

            # 체결 데이터 파싱
            tick = TickData(
                symbol=symbol,
                timestamp=time.time(),
                # 최우선 호가 (체결 시점의 호가는 없으므로 0으로 설정)
                bid_price_1=0.0,
                bid_qty_1=0.0,
                ask_price_1=0.0,
                ask_qty_1=0.0,
                # 체결가 및 OHLC
                current_price=float(fields[2]) if fields[2] else None,
                open_price=float(fields[6]) if fields[6] else None,
                high_price=float(fields[7]) if fields[7] else None,
                low_price=float(fields[8]) if fields[8] else None,
                # 거래량
                tick_volume=float(fields[11]) if fields[11] else None,
                cumulative_volume=float(fields[12]) if fields[12] else None,
                # 미결제약정
                open_interest=float(fields[14]) if fields[14] else None,
            )

            return tick

        except (ValueError, IndexError) as e:
            logger.warning(f"[KIS WS] Failed to parse trade: {e}")
            return None


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
