"""KIS API Client.

Lightweight async client for KIS API, focusing on market data and order execution.
Implements MarketDataSource protocol for integration with MarketDataProvider.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import aiohttp

from shared.http import AsyncSessionMixin
from shared.kis.auth import KISAuthConfig, KISAuthManager

logger = logging.getLogger(__name__)

# Default timeout for KIS API requests (seconds)
_DEFAULT_REQUEST_TIMEOUT = 10.0

# KIS API rate limit per token.
# Real API: ~20 req/s. Mock/virtual API (openapivts): ~5 req/s.
# Override via KIS_API_RATE_LIMIT env var.
_DEFAULT_RATE_LIMIT = 5

# Cooldown after receiving a rate limit error (seconds)
_RATE_LIMIT_PENALTY = 1.0


class _RateLimiter:
    """Fixed-interval rate limiter with adaptive backoff for KIS API.

    Enforces a minimum interval (1/rate) between consecutive requests.
    On rate limit errors, adds a penalty cooldown to back off.
    """

    def __init__(self, max_requests: int, window_seconds: float = 1.0):
        self._interval = window_seconds / max_requests
        self._last_request = 0.0
        self._penalty_until = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until the next request slot is available."""
        async with self._lock:
            now = time.monotonic()

            # Respect penalty cooldown from rate limit errors
            if now < self._penalty_until:
                await asyncio.sleep(self._penalty_until - now)
                now = time.monotonic()

            elapsed = now - self._last_request
            if elapsed < self._interval:
                await asyncio.sleep(self._interval - elapsed)
            self._last_request = time.monotonic()

    def penalty(self, seconds: float = _RATE_LIMIT_PENALTY):
        """Add a cooldown penalty after receiving a rate limit error."""
        self._penalty_until = time.monotonic() + seconds


class KISClient(AsyncSessionMixin):
    """KIS API Client wrapper with built-in rate limiting."""

    def __init__(self, config: KISAuthConfig):
        self.config = config
        self.auth_manager = KISAuthManager.get_instance(config)
        rate_limit = int(os.environ.get("KIS_API_RATE_LIMIT", str(_DEFAULT_RATE_LIMIT)))
        self._rate_limiter = _RateLimiter(max_requests=rate_limit)
        logger.info(f"[KISClient] Rate limiter: {rate_limit} req/s")

    async def close(self):
        """Close the session."""
        await self._close_session()

    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        """Fetch current price for a Stock symbol.

        Implements MarketDataSource protocol.
        """
        await self._rate_limiter.acquire()
        try:
            session = await self._get_session()
            headers = await self.auth_manager.get_auth_headers_async()

            # Add TR ID for Current Price (Stock) - "주식현재가 시세"
            headers["tr_id"] = "FHKST01010100"
            headers["custtype"] = "P"

            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol
            }

            path = "/uapi/domestic-stock/v1/quotations/inquire-price"
            url = f"{self.config.base_url}{path}"

            timeout_seconds = getattr(
                self.config, "request_timeout_seconds", _DEFAULT_REQUEST_TIMEOUT
            )
            request_timeout = aiohttp.ClientTimeout(total=float(timeout_seconds))
            async with session.get(
                url, headers=headers, params=params, timeout=request_timeout
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    # Detect rate limit error and apply backoff
                    if "EGW00201" in text:
                        self._rate_limiter.penalty()
                    logger.error(f"KIS API Error {response.status} for {symbol}: {text}")
                    raise Exception(f"KIS API Error {response.status}")

                data = await response.json()
                if data.get("rt_cd") != "0":
                    msg = data.get("msg1", "Unknown error")
                    logger.error(f"KIS Logic Error for {symbol}: {msg}")
                    raise Exception(f"KIS Logic Error: {msg}")

                output = data.get("output", {})

                # Map KIS output fields to our standard schema
                # stck_prpr (Current), stck_oprc (Open), stck_hgpr (High), stck_lwpr (Low), acml_vol (Vol)
                return {
                    "code": symbol,
                    "close": float(output.get("stck_prpr", 0)),
                    "open": float(output.get("stck_oprc", 0)),
                    "high": float(output.get("stck_hgpr", 0)),
                    "low": float(output.get("stck_lwpr", 0)),
                    "volume": int(output.get("acml_vol", 0)),
                    "change": float(output.get("prdy_ctrt", 0)) / 100.0 if output.get("prdy_ctrt") else 0.0,
                    "timestamp": time.time(), # Use local time as approx
                }

        except Exception as e:
            logger.warning(f"Failed to fetch price for {symbol}: {e}")
            raise

    async def get_minute_bars(
        self, symbol: str, count: int = 30
    ) -> list[dict[str, Any]]:
        """Fetch recent intraday 1-minute bars for a stock symbol.

        Uses KIS 주식당일분봉조회 (FHKST03010200).

        Args:
            symbol: Stock code (e.g., '005930')
            count: Number of bars to return (max ~30 for current session)

        Returns:
            List of candle dicts with open, high, low, close, volume keys,
            sorted chronologically (oldest first).
        """
        await self._rate_limiter.acquire()
        try:
            session = await self._get_session()
            headers = await self.auth_manager.get_auth_headers_async()

            headers["tr_id"] = "FHKST03010200"
            headers["custtype"] = "P"

            from datetime import datetime as _dt

            now_str = _dt.now().strftime("%H%M%S")
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
                "FID_INPUT_HOUR_1": now_str,
                "FID_PW_DATA_INCU_YN": "N",
            }

            path = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
            url = f"{self.config.base_url}{path}"

            timeout_seconds = getattr(
                self.config, "request_timeout_seconds", _DEFAULT_REQUEST_TIMEOUT
            )
            request_timeout = aiohttp.ClientTimeout(total=float(timeout_seconds))
            async with session.get(
                url, headers=headers, params=params, timeout=request_timeout
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    if "EGW00201" in text:
                        self._rate_limiter.penalty()
                    return []

                data = await response.json()
                if data.get("rt_cd") != "0":
                    return []

                rows = data.get("output2", [])
                candles: list[dict[str, Any]] = []
                for row in rows[:count]:
                    try:
                        candles.append({
                            "open": float(row.get("stck_oprc", 0)),
                            "high": float(row.get("stck_hgpr", 0)),
                            "low": float(row.get("stck_lwpr", 0)),
                            "close": float(row.get("stck_prpr", 0)),
                            "volume": int(row.get("cntg_vol", 0)),
                        })
                    except (ValueError, TypeError):
                        continue

                candles.reverse()  # API returns newest first; we need oldest first
                return candles

        except Exception as e:
            logger.debug(f"Failed to fetch minute bars for {symbol}: {e}")
            return []
