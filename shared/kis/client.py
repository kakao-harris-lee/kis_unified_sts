"""KIS API Client.

Lightweight async client for KIS API, focusing on market data and order execution.
Implements MarketDataSource protocol for integration with MarketDataProvider.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

from shared.http import AsyncSessionMixin
from shared.kis.auth import KISAuthConfig, KISAuthManager

logger = logging.getLogger(__name__)

# Default timeout for KIS API requests (seconds)
_DEFAULT_REQUEST_TIMEOUT = 10.0


class KISClient(AsyncSessionMixin):
    """KIS API Client wrapper."""

    def __init__(self, config: KISAuthConfig):
        self.config = config
        self.auth_manager = KISAuthManager.get_instance(config)

    async def close(self):
        """Close the session."""
        await self._close_session()

    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        """Fetch current price for a Stock symbol.

        Implements MarketDataSource protocol.
        """
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
                    # "origin": "kis_api"
                }

        except Exception as e:
            logger.warning(f"Failed to fetch price for {symbol}: {e}")
            raise
