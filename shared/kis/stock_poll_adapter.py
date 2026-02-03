"""Stock polling adapter for KIS REST API.

This adapter implements `BaseAPIAdapter` so it can be used with existing
collection/publishing patterns, but it uses REST polling (not WebSocket).

It is intended as a pragmatic baseline for `market:ticks` ingestion until a
full stock WebSocket adapter is implemented.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional

import requests

from shared.collector.adapter import BaseAPIAdapter
from shared.collector.models import TickData
from shared.kis.auth import KISAuthConfig, KISAuthManager

logger = logging.getLogger(__name__)


class KISStockPollingAdapter(BaseAPIAdapter):
    """Poll KIS 'inquire-price' endpoint and emit TickData."""

    TR_ID_INQUIRE_PRICE = "FHKST01010100"
    PATH_INQUIRE_PRICE = "/uapi/domestic-stock/v1/quotations/inquire-price"

    def __init__(
        self,
        config: KISAuthConfig,
        poll_interval_seconds: float = 1.0,
        max_workers: int = 8,
        request_timeout_seconds: float | None = None,
    ):
        self.config = config
        self.auth_manager = KISAuthManager.get_instance(config)

        self.poll_interval_seconds = float(poll_interval_seconds)
        self.max_workers = int(max_workers)
        self.request_timeout_seconds = float(
            request_timeout_seconds
            if request_timeout_seconds is not None
            else getattr(config, "request_timeout_seconds", 30)
        )

        self._running = False
        self._callback: Optional[Callable[[TickData], None]] = None

        self._symbols: List[str] = []
        self._lock = threading.Lock()

        self._last_cumulative_volume: Dict[str, int] = {}
        self._thread_local = threading.local()

    def connect(self) -> None:
        self._running = True
        logger.info("KISStockPollingAdapter connected")

    def disconnect(self) -> None:
        self._running = False
        logger.info("KISStockPollingAdapter disconnected")

    def update_symbols(self, symbols: List[str]) -> None:
        # Preserve order while deduplicating
        seen = set()
        cleaned: List[str] = []
        for s in symbols:
            s = (s or "").strip()
            if not s:
                continue
            if s in seen:
                continue
            seen.add(s)
            cleaned.append(s)

        with self._lock:
            self._symbols = cleaned

    def subscribe(self, symbols: List[str], callback: Callable[[TickData], None]) -> None:
        self._callback = callback
        self.update_symbols(symbols)
        self._running = True

        while self._running:
            start = time.time()

            with self._lock:
                current_symbols = list(self._symbols)

            if not current_symbols:
                time.sleep(self.poll_interval_seconds)
                continue

            ticks = self._fetch_ticks(current_symbols)
            for tick in ticks:
                try:
                    callback(tick)
                except Exception as e:
                    logger.warning(f"Tick callback failed: {e}")

            elapsed = time.time() - start
            time.sleep(max(0.0, self.poll_interval_seconds - elapsed))

    def _get_session(self) -> requests.Session:
        sess = getattr(self._thread_local, "session", None)
        if sess is None:
            sess = requests.Session()
            self._thread_local.session = sess
        return sess

    def _fetch_ticks(self, symbols: List[str]) -> List[TickData]:
        if self.max_workers <= 1 or len(symbols) <= 1:
            ticks: List[TickData] = []
            for s in symbols:
                tick = self._fetch_one(s)
                if tick is not None:
                    ticks.append(tick)
            return ticks

        ticks = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = [ex.submit(self._fetch_one, s) for s in symbols]
            for fut in as_completed(futures):
                try:
                    tick = fut.result()
                    if tick is not None:
                        ticks.append(tick)
                except Exception as e:
                    logger.debug(f"Polling failed: {e}")
        return ticks

    def _fetch_one(self, symbol: str) -> Optional[TickData]:
        headers = self.auth_manager.get_auth_headers()
        headers["tr_id"] = self.TR_ID_INQUIRE_PRICE
        headers["custtype"] = "P"

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
        }

        url = f"{self.config.base_url}{self.PATH_INQUIRE_PRICE}"
        session = self._get_session()
        resp = session.get(
            url,
            headers=headers,
            params=params,
            timeout=self.request_timeout_seconds,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("rt_cd") != "0":
            return None

        output = data.get("output", {}) or {}
        price = float(output.get("stck_prpr", 0) or 0)
        bid = float(output.get("bidp", 0) or 0)
        ask = float(output.get("askp", 0) or 0)

        cumulative_volume = int(float(output.get("acml_vol", 0) or 0))
        prev = self._last_cumulative_volume.get(symbol)
        tick_volume: Optional[float] = None
        if prev is not None and cumulative_volume >= prev:
            tick_volume = float(cumulative_volume - prev)
        self._last_cumulative_volume[symbol] = cumulative_volume

        return TickData(
            symbol=symbol,
            timestamp=time.time(),
            bid_price_1=bid,
            bid_qty_1=0.0,
            ask_price_1=ask,
            ask_qty_1=0.0,
            current_price=price,
            tick_volume=tick_volume,
            cumulative_volume=float(cumulative_volume),
            open_price=float(output.get("stck_oprc", 0) or 0) if output.get("stck_oprc") else None,
            high_price=float(output.get("stck_hgpr", 0) or 0) if output.get("stck_hgpr") else None,
            low_price=float(output.get("stck_lwpr", 0) or 0) if output.get("stck_lwpr") else None,
        )

