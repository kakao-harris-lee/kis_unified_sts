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

from shared.config.loader import ConfigLoader
from shared.http import AsyncSessionMixin
from shared.kis.auth import KISAuthConfig, KISAuthManager

logger = logging.getLogger(__name__)


def _load_rate_limiter_config() -> dict[str, Any]:
    """Load rate_limiter section from config/streaming.yaml."""
    try:
        cfg = ConfigLoader.load("streaming.yaml")
        return cfg.get("rate_limiter", {})
    except Exception:
        logger.warning("[KISClient] Failed to load rate limiter config, using defaults")
        return {}


_rl_cfg = _load_rate_limiter_config()
_DEFAULT_REQUEST_TIMEOUT = float(_rl_cfg.get("request_timeout", 10.0))
_DEFAULT_RATE_LIMIT = int(_rl_cfg.get("default_rate", 5))
_RATE_LIMIT_PENALTY = float(_rl_cfg.get("penalty_seconds", 1.0))


class _RateLimiter:
    """Fixed-interval rate limiter with exponential backoff for KIS API.

    Enforces a minimum interval (1/rate) between consecutive requests.
    On rate limit errors, applies exponential backoff: base * 2^(consecutive-1),
    capped at max_penalty_seconds.
    """

    def __init__(self, max_requests: int, window_seconds: float = 1.0):
        self._interval = window_seconds / max_requests
        self._last_request = 0.0
        self._penalty_until = 0.0
        self._consecutive_penalties = 0
        self._max_penalty = float(_rl_cfg.get("max_penalty_seconds", 30.0))
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
        """Apply exponential backoff penalty on rate limit error.

        Consecutive calls double the penalty each time, capped at max_penalty.
        A successful acquire after the penalty window resets the counter.
        """
        self._consecutive_penalties += 1
        backoff = min(
            seconds * (2 ** (self._consecutive_penalties - 1)),
            self._max_penalty,
        )
        self._penalty_until = time.monotonic() + backoff
        logger.warning(
            f"Rate limit penalty: {backoff:.1f}s "
            f"(consecutive={self._consecutive_penalties})"
        )

    def reset_backoff(self):
        """Reset consecutive penalty counter after a successful request."""
        if self._consecutive_penalties > 0:
            self._consecutive_penalties = 0


class KISClient(AsyncSessionMixin):
    """KIS API Client wrapper with built-in rate limiting."""

    def __init__(self, config: KISAuthConfig):
        self.config = config
        self.auth_manager = KISAuthManager.get_instance(config)
        rate_limit = int(os.environ.get("KIS_API_RATE_LIMIT", str(_DEFAULT_RATE_LIMIT)))
        self._rate_limiter = _RateLimiter(max_requests=rate_limit)
        logger.info(f"[KISClient] Rate limiter: {rate_limit} req/s")
        # KIS client is internally rate-limited; avoid parallel fetches upstream
        self.supports_parallel = False

    async def close(self):
        """Close the session."""
        await self._close_session()


    def _is_futures(self, symbol: str) -> bool:
        """Check if symbol is a futures code (KOSPI 200 / Mini)."""
        # Futures codes start with '1' and are usually 8 chars (e.g. 101S6000)
        # Stocks are 6 digits (e.g. 005930)
        return len(symbol) != 6 or not symbol.isdigit()

    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        """Fetch current price for a Stock or Futures symbol.

        Implements MarketDataSource protocol.
        """
        await self._rate_limiter.acquire()
        try:
            if self._is_futures(symbol):
                return await self._get_futures_price(symbol)

            return await self._get_stock_price(symbol)

        except Exception as e:
            logger.warning(f"Failed to fetch price for {symbol}: {e}")
            raise

    async def _get_stock_price(self, symbol: str) -> dict[str, Any]:
        """Fetch current price for a Stock symbol."""
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

            self._rate_limiter.reset_backoff()
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

    async def _get_futures_price(self, symbol: str) -> dict[str, Any]:
        """Fetch current price for a Futures symbol."""
        session = await self._get_session()
        headers = await self.auth_manager.get_auth_headers_async()

        # TR ID: FHMIF10000000 (선물옵션 현재가)
        headers["tr_id"] = "FHMIF10000000"
        headers["custtype"] = "P"

        params = {
            "FID_COND_MRKT_DIV_CODE": "F",
            "FID_INPUT_ISCD": symbol
        }

        path = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
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
                logger.error(f"KIS Futures API Error {response.status} for {symbol}: {text}")
                raise Exception(f"KIS API Error {type}")

            data = await response.json()
            if data.get("rt_cd") != "0":
                msg = data.get("msg1", "Unknown error")
                logger.error(f"KIS Logic Error for {symbol} (Futures): {msg}")
                raise Exception(f"KIS Logic Error: {msg}")

            self._rate_limiter.reset_backoff()
            # FHMIF10000000 returns output1 (price), output2/3 (index info)
            output = data.get("output1", {})

            return {
                "code": symbol,
                "close": float(output.get("futs_prpr", 0)),
                "open": float(output.get("futs_oprc", 0)),
                "high": float(output.get("futs_hgpr", 0)),
                "low": float(output.get("futs_lwpr", 0)),
                "volume": int(output.get("acml_vol", 0)),
                "change": float(output.get("futs_prdy_ctrt", 0)) / 100.0 if output.get("futs_prdy_ctrt") else 0.0,
                "timestamp": time.time(),
            }


    async def get_minute_bars(
        self, symbol: str, count: int = 30
    ) -> list[dict[str, Any]]:
        """Fetch recent intraday 1-minute bars for a stock or futures symbol.

        Uses KIS 주식당일분봉조회 (FHKST03010200) or Futures Minute Chart (FHKIF03020200).

        Args:
            symbol: Stock/Futures code
            count: Number of bars to return (max ~30 for current session)
        """
        if self._is_futures(symbol):
            return await self._get_futures_minute_bars(symbol, count)

        return await self._get_stock_minute_bars(symbol, count)

    async def _get_stock_minute_bars(
        self, symbol: str, count: int = 30
    ) -> list[dict[str, Any]]:
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

                self._rate_limiter.reset_backoff()
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

    async def _get_futures_minute_bars(
        self, symbol: str, count: int = 30
    ) -> list[dict[str, Any]]:
        await self._rate_limiter.acquire()
        try:
            session = await self._get_session()
            headers = await self.auth_manager.get_auth_headers_async()

            headers["tr_id"] = "FHKIF03020200"
            headers["custtype"] = "P"

            from datetime import datetime as _dt
            now_str = _dt.now().strftime("%H%M%S")

            # Futures param keys differ slightly (FID_COND_MRKT_DIV_CODE='F')
            params = {
                "FID_COND_MRKT_DIV_CODE": "F",
                "FID_INPUT_ISCD": symbol,
                "FID_INPUT_HOUR_1": now_str,
                "FID_PW_DATA_INCU_YN": "N",
            }
            # Although ID is "fuopchartprice", check path carefully.
            # Usually /uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice
            path = "/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
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

                self._rate_limiter.reset_backoff()
                rows = data.get("output2", [])
                candles: list[dict[str, Any]] = []

                # Futures parsing (Fields: stck_prpr -> futures_prpr etc? No, KIS usually reuses keys in output2)
                # We need to verify response structure. Common KIS pattern is "stck_prpr" even for futures in chart.
                # However, for FHKIF03020200, keys are:
                # stck_prpr (Current)
                # stck_oprc (Open)
                # ...

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

                candles.reverse()
                return candles

        except Exception as e:
            logger.debug(f"Failed to fetch futures bars for {symbol}: {e}")
            return []

    # ------------------------------------------------------------------
    # Balance Inquiry (잔고조회) — for broker position verification
    # ------------------------------------------------------------------

    async def get_stock_balance(self, account_no: str = "") -> list[dict[str, Any]]:
        """주식 잔고조회 (TTTC8434R / VTTC8434R).

        Returns list of dicts with: code, name, side, quantity, avg_price,
        current_price, unrealized_pnl.
        """
        if not account_no:
            account_no = os.getenv(
                "KIS_STOCK_ACCOUNT_NO", os.getenv("KIS_ACCOUNT_NO", "")
            )
        if not account_no or len(account_no) < 10:
            logger.warning("Stock account number not configured; skipping balance inquiry")
            return []

        await self._rate_limiter.acquire()
        session = await self._get_session()
        headers = await self.auth_manager.get_auth_headers_async()

        tr_id = "TTTC8434R" if self.config.is_real else "VTTC8434R"
        headers["tr_id"] = tr_id
        headers["custtype"] = "P"

        params = {
            "CANO": account_no[:8],
            "ACNT_PRDT_CD": account_no[8:10],
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }

        path = "/uapi/domestic-stock/v1/trading/inquire-balance"
        url = f"{self.config.base_url}{path}"
        timeout_seconds = getattr(
            self.config, "request_timeout_seconds", _DEFAULT_REQUEST_TIMEOUT
        )
        request_timeout = aiohttp.ClientTimeout(total=float(timeout_seconds))

        try:
            async with session.get(
                url, headers=headers, params=params, timeout=request_timeout
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    if "EGW00201" in text:
                        self._rate_limiter.penalty()
                    logger.error(f"Stock balance inquiry failed ({response.status}): {text}")
                    return []

                data = await response.json()
                if data.get("rt_cd") != "0":
                    logger.error(f"Stock balance inquiry error: {data.get('msg1', '')}")
                    return []

                self._rate_limiter.reset_backoff()
                positions = []
                for item in data.get("output1", []):
                    qty = int(item.get("hldg_qty", 0))
                    if qty <= 0:
                        continue
                    positions.append({
                        "code": item.get("pdno", ""),
                        "name": item.get("prdt_name", ""),
                        "side": "long",
                        "quantity": qty,
                        "avg_price": float(item.get("pchs_avg_pric", 0)),
                        "current_price": float(item.get("prpr", 0)),
                        "unrealized_pnl": float(item.get("evlu_pfls_amt", 0)),
                    })
                return positions

        except Exception as e:
            logger.warning(f"Stock balance inquiry exception: {e}")
            return []

    async def get_futures_balance(self, account_no: str = "") -> list[dict[str, Any]]:
        """선물옵션 잔고조회 (CTFO6118R).

        NOTE: 모의서버는 선물 잔고조회 미지원. is_real=True 필수.

        Returns list of dicts with: code, name, side, quantity, avg_price,
        current_price, unrealized_pnl.
        """
        if not self.config.is_real:
            logger.debug("Futures balance inquiry not supported on mock server")
            return []

        if not account_no:
            account_no = os.getenv(
                "KIS_FUTURES_ACCOUNT_NO", os.getenv("KIS_ACCOUNT_NO", "")
            )
        if not account_no or len(account_no) < 10:
            logger.warning("Futures account number not configured; skipping balance inquiry")
            return []

        await self._rate_limiter.acquire()
        session = await self._get_session()
        headers = await self.auth_manager.get_auth_headers_async()

        headers["tr_id"] = "CTFO6118R"
        headers["custtype"] = "P"

        params = {
            "CANO": account_no[:8],
            "ACNT_PRDT_CD": account_no[8:10],
            "SORT_SQN": "DS",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        }

        path = "/uapi/domestic-futureoption/v1/trading/inquire-balance"
        url = f"{self.config.base_url}{path}"
        timeout_seconds = getattr(
            self.config, "request_timeout_seconds", _DEFAULT_REQUEST_TIMEOUT
        )
        request_timeout = aiohttp.ClientTimeout(total=float(timeout_seconds))

        try:
            async with session.get(
                url, headers=headers, params=params, timeout=request_timeout
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    if "EGW00201" in text:
                        self._rate_limiter.penalty()
                    logger.error(f"Futures balance inquiry failed ({response.status}): {text}")
                    return []

                data = await response.json()
                if data.get("rt_cd") != "0":
                    logger.error(f"Futures balance inquiry error: {data.get('msg1', '')}")
                    return []

                self._rate_limiter.reset_backoff()
                positions = []
                for item in data.get("output1", []):
                    qty = int(item.get("cblc_qty", 0))
                    if qty <= 0:
                        continue
                    # sll_buy_dvsn_cd: 01=매도(short), 02=매수(long)
                    side = "short" if item.get("sll_buy_dvsn_cd") == "01" else "long"
                    positions.append({
                        "code": item.get("pdno", ""),
                        "name": item.get("prdt_name", ""),
                        "side": side,
                        "quantity": qty,
                        "avg_price": float(item.get("pchs_avg_pric", 0)),
                        "current_price": float(item.get("prpr", item.get("now_pric2", 0))),
                        "unrealized_pnl": float(item.get("evlu_pfls_amt", 0)),
                    })
                return positions

        except Exception as e:
            logger.warning(f"Futures balance inquiry exception: {e}")
            return []
