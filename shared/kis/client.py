"""KIS API Client.

Lightweight async client for KIS API, focusing on market data and order execution.
Implements MarketDataSource protocol for integration with MarketDataProvider.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import date, datetime, timedelta
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from shared.config.loader import ConfigLoader
from shared.http import AsyncSessionMixin
from shared.kis.auth import KISAuthConfig, KISAuthManager
from shared.kis.error_rate import KISApiErrorRateTracker
from shared.utils.parsing import parse_float

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
_KST = ZoneInfo("Asia/Seoul")
_INVEST_OPINION_PATH = "/uapi/domestic-stock/v1/quotations/invest-opinion"
_INVEST_OPINION_TR_ID = "FHKST663300C0"


class _RateLimiter:
    """Fixed-interval rate limiter with exponential backoff for KIS API.

    Enforces a minimum interval (1/rate) between consecutive requests.
    On rate limit errors, applies exponential backoff: base * 2^(consecutive-1),
    capped at max_penalty_seconds.

    Auto-resets after max_consecutive penalties to prevent death spirals where
    the server keeps rejecting requests even after the penalty window.
    """

    _MAX_CONSECUTIVE = int(_rl_cfg.get("max_consecutive_penalties", 10))
    _COOLDOWN_SECONDS = float(_rl_cfg.get("cooldown_seconds", 300.0))

    def __init__(self, max_requests: int, window_seconds: float = 1.0):
        self._interval = window_seconds / max_requests
        self._last_request = 0.0
        self._penalty_until = 0.0
        self._consecutive_penalties = 0
        self._max_penalty = float(_rl_cfg.get("max_penalty_seconds", 30.0))
        self._lock = asyncio.Lock()

    @property
    def is_penalized(self) -> bool:
        """True if currently in a penalty or cooldown period."""
        return time.monotonic() < self._penalty_until

    @property
    def consecutive_penalties(self) -> int:
        return self._consecutive_penalties

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
        After max_consecutive penalties, enters a longer cooldown period and
        resets the counter to break infinite penalty loops.
        """
        self._consecutive_penalties += 1

        if self._consecutive_penalties >= self._MAX_CONSECUTIVE:
            # Break the death spiral: long cooldown then reset
            self._penalty_until = time.monotonic() + self._COOLDOWN_SECONDS
            logger.warning(
                f"Rate limit: {self._consecutive_penalties} consecutive penalties, "
                f"entering {self._COOLDOWN_SECONDS:.0f}s cooldown"
            )
            self._consecutive_penalties = 0
            return

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

    @property
    def is_rate_limited(self) -> bool:
        """True if the rate limiter is currently in a penalty period."""
        return self._rate_limiter.is_penalized

    async def close(self):
        """Close the session."""
        await self._close_session()

    @staticmethod
    def _normalize_account_no(account_no: str) -> str:
        """Normalize account number to digits-only 10-char format."""
        return "".join(ch for ch in (account_no or "") if ch.isdigit())

    @staticmethod
    def _resolve_account_no(asset: str) -> str:
        """Resolve account number from environment with explicit, fail-loud semantics.

        Asset-specific env var takes precedence:
            - asset='stock'   -> KIS_STOCK_ACCOUNT_NO
            - asset='futures' -> KIS_FUTURES_ACCOUNT_NO

        Fallback to the legacy single-account env var ``KIS_ACCOUNT_NO`` is
        DISABLED by default to prevent stock/futures cross-routing (e.g. a
        futures order being placed against a stock account). To opt into the
        legacy behavior for backward compatibility, set
        ``KIS_LEGACY_ACCOUNT_FALLBACK=1`` — a warning is emitted each time
        the legacy value is used.

        Returns an empty string if no value is configured; callers retain
        their existing length / fail-fast behavior on empty.
        """
        if asset == "stock":
            primary_key = "KIS_STOCK_ACCOUNT_NO"
        elif asset == "futures":
            primary_key = "KIS_FUTURES_ACCOUNT_NO"
        else:
            raise ValueError(
                f"_resolve_account_no: unknown asset '{asset}' (expected 'stock' or 'futures')"
            )

        primary = os.getenv(primary_key, "").strip()
        if primary:
            return primary

        legacy = os.getenv("KIS_ACCOUNT_NO", "").strip()
        if legacy and os.getenv("KIS_LEGACY_ACCOUNT_FALLBACK", "0").strip() in (
            "1",
            "true",
            "TRUE",
            "yes",
        ):
            logger.warning(
                "[KISClient] %s not set; using legacy KIS_ACCOUNT_NO fallback "
                "(asset=%s). Set %s explicitly and remove KIS_LEGACY_ACCOUNT_FALLBACK "
                "to silence this warning.",
                primary_key,
                asset,
                primary_key,
            )
            return legacy

        return ""

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

    async def fetch_invest_opinion(
        self,
        symbol: str,
        *,
        start_date: date | datetime | str | None = None,
        end_date: date | datetime | str | None = None,
        lookback_days: int = 180,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch KIS domestic stock analyst opinions and target prices."""
        if self._is_futures(symbol):
            return []
        if not self.config.is_real:
            raise RuntimeError(
                "KIS invest-opinion API is not supported in mock investment."
            )

        end_yyyymmdd = self._format_kis_date(end_date or datetime.now(_KST).date())
        if start_date is None:
            days = max(int(lookback_days), 1)
            start = datetime.strptime(end_yyyymmdd, "%Y%m%d").date() - timedelta(
                days=days
            )
            start_yyyymmdd = self._format_kis_date(start)
        else:
            start_yyyymmdd = self._format_kis_date(start_date)

        rows: list[dict[str, Any]] = []
        tr_cont = ""
        pages = max(int(max_pages), 1)

        for _ in range(pages):
            await self._rate_limiter.acquire()
            session = await self._get_session()
            headers = await self.auth_manager.get_auth_headers_async()
            headers["tr_id"] = _INVEST_OPINION_TR_ID
            headers["custtype"] = "P"
            if tr_cont:
                headers["tr_cont"] = tr_cont

            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_COND_SCR_DIV_CODE": "16633",
                "FID_INPUT_ISCD": symbol,
                "FID_INPUT_DATE_1": start_yyyymmdd,
                "FID_INPUT_DATE_2": end_yyyymmdd,
            }
            url = f"{self.config.base_url}{_INVEST_OPINION_PATH}"
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
                    KISApiErrorRateTracker.get_instance().record_error()
                    raise RuntimeError(
                        f"KIS invest-opinion HTTP {response.status}: {text[:2000]}"
                    )

                data = await response.json(content_type=None)
                response_tr_cont = str(response.headers.get("tr_cont", "")).strip()

            if data.get("rt_cd") != "0":
                msg = data.get("msg1", "Unknown error")
                if "EGW00201" in msg:
                    self._rate_limiter.penalty()
                KISApiErrorRateTracker.get_instance().record_error()
                raise RuntimeError(f"KIS invest-opinion API error: {msg}")

            self._rate_limiter.reset_backoff()
            KISApiErrorRateTracker.get_instance().record_success()
            rows.extend(self._extract_output_rows(data))

            if response_tr_cont != "M":
                break
            tr_cont = "N"

        return rows

    async def summarize_target_price(
        self,
        symbol: str,
        *,
        current_price: float,
        lookback_days: int = 180,
        recent_days: int = 30,
    ) -> dict[str, Any]:
        """Summarize KIS analyst target-price rows for stock LLM scoring."""
        rows = await self.fetch_invest_opinion(
            symbol,
            lookback_days=lookback_days,
        )
        reports = [
            report
            for report in (
                self._normalize_target_price_report(row, current_price) for row in rows
            )
            if report["target_price"] > 0
        ]
        if not reports:
            return self._empty_target_price_summary()

        reports.sort(key=lambda item: item["_sort_date"], reverse=True)
        target_prices = [float(item["target_price"]) for item in reports]
        consensus_target = float(median(target_prices))
        latest = reports[0]
        reference_price = float(current_price or latest["previous_close"] or 0.0)
        upside_pct = (
            (consensus_target / reference_price - 1.0) * 100.0
            if reference_price > 0
            else 0.0
        )
        latest_upside_pct = (
            (float(latest["target_price"]) / reference_price - 1.0) * 100.0
            if reference_price > 0
            else 0.0
        )

        today = datetime.now(_KST).date()
        latest_date = latest["_sort_date"]
        staleness_days = (today - latest_date).days if latest_date else 0
        brokers = {
            str(item["broker"]).strip()
            for item in reports
            if str(item["broker"]).strip()
        }
        opinion_distribution: dict[str, int] = {}
        for item in reports:
            opinion = str(item["opinion"]).strip()
            if opinion:
                opinion_distribution[opinion] = opinion_distribution.get(opinion, 0) + 1

        revision_pct = self._calc_target_revision_pct(
            reports, recent_days=max(int(recent_days), 1)
        )
        revision_direction = self._target_revision_direction(revision_pct)
        dispersion_pct = (
            (max(target_prices) - min(target_prices)) / consensus_target * 100.0
            if consensus_target > 0 and len(target_prices) > 1
            else 0.0
        )

        recent_reports = [
            {
                "date": item["date"],
                "broker": item["broker"],
                "opinion": item["opinion"],
                "previous_opinion": item["previous_opinion"],
                "target_price": item["target_price"],
                "upside_pct": round(float(item["upside_pct"]), 2),
            }
            for item in reports[:5]
        ]

        return {
            "available": True,
            "target_price": consensus_target,
            "latest_target_price": float(latest["target_price"]),
            "latest_target_upside_pct": latest_upside_pct,
            "upside_pct": upside_pct,
            "opinion": str(latest["opinion"]),
            "date": str(latest["date"]),
            "latest_broker": str(latest["broker"]),
            "sample_count": len(reports),
            "coverage_count": len(brokers) if brokers else len(reports),
            "dispersion_pct": dispersion_pct,
            "revision_30d_pct": revision_pct,
            "revision_direction": revision_direction,
            "staleness_days": staleness_days,
            "opinion_distribution": opinion_distribution,
            "recent_reports": recent_reports,
        }

    @staticmethod
    def _empty_target_price_summary() -> dict[str, Any]:
        return {
            "available": False,
            "target_price": 0.0,
            "latest_target_price": 0.0,
            "latest_target_upside_pct": 0.0,
            "upside_pct": 0.0,
            "opinion": "",
            "date": "",
            "latest_broker": "",
            "sample_count": 0,
            "coverage_count": 0,
            "dispersion_pct": 0.0,
            "revision_30d_pct": 0.0,
            "revision_direction": "",
            "staleness_days": 0,
            "opinion_distribution": {},
            "recent_reports": [],
        }

    @staticmethod
    def _extract_output_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
        value = payload.get("output")
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _format_kis_date(value: date | datetime | str) -> str:
        if isinstance(value, datetime):
            return value.date().strftime("%Y%m%d")
        if isinstance(value, date):
            return value.strftime("%Y%m%d")
        text = str(value or "").strip().replace("-", "")
        if len(text) == 8 and text.isdigit():
            return text
        raise ValueError(f"Invalid KIS date: {value!r}")

    @staticmethod
    def _parse_kis_date(value: Any) -> date | None:
        text = str(value or "").strip().replace("-", "")
        if len(text) != 8 or not text.isdigit():
            return None
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None

    @classmethod
    def _normalize_target_price_report(
        cls, row: dict[str, Any], current_price: float
    ) -> dict[str, Any]:
        report_date = cls._parse_kis_date(row.get("stck_bsop_date"))
        target_price = parse_float(row.get("hts_goal_prc"))
        previous_close = parse_float(row.get("stck_prdy_clpr"))
        reference_price = float(current_price or previous_close or 0.0)
        upside_pct = (
            (target_price / reference_price - 1.0) * 100.0
            if target_price > 0 and reference_price > 0
            else 0.0
        )
        return {
            "date": (
                report_date.isoformat()
                if report_date
                else str(row.get("stck_bsop_date", "")).strip()
            ),
            "_sort_date": report_date or date.min,
            "broker": str(row.get("mbcr_name", "")).strip(),
            "opinion": str(row.get("invt_opnn", "")).strip(),
            "previous_opinion": str(row.get("rgbf_invt_opnn", "")).strip(),
            "target_price": target_price,
            "previous_close": previous_close,
            "upside_pct": upside_pct,
        }

    @staticmethod
    def _calc_target_revision_pct(
        reports: list[dict[str, Any]], recent_days: int
    ) -> float:
        if not reports:
            return 0.0
        latest_date = max(item["_sort_date"] for item in reports)
        if latest_date == date.min:
            return 0.0
        recent_cutoff = latest_date - timedelta(days=recent_days)
        recent_targets = [
            float(item["target_price"])
            for item in reports
            if item["_sort_date"] >= recent_cutoff and float(item["target_price"]) > 0
        ]
        prior_targets = [
            float(item["target_price"])
            for item in reports
            if item["_sort_date"] < recent_cutoff and float(item["target_price"]) > 0
        ]
        if not recent_targets or not prior_targets:
            return 0.0
        prior_median = float(median(prior_targets))
        if prior_median <= 0:
            return 0.0
        return (float(median(recent_targets)) / prior_median - 1.0) * 100.0

    @staticmethod
    def _target_revision_direction(revision_pct: float) -> str:
        if revision_pct > 0:
            return "up"
        if revision_pct < 0:
            return "down"
        return "flat"

    async def _get_stock_price(self, symbol: str) -> dict[str, Any]:
        """Fetch current price for a Stock symbol."""
        session = await self._get_session()
        headers = await self.auth_manager.get_auth_headers_async()

        # Add TR ID for Current Price (Stock) - "주식현재가 시세"
        headers["tr_id"] = "FHKST01010100"
        headers["custtype"] = "P"

        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol}

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
                KISApiErrorRateTracker.get_instance().record_error()
                logger.error(f"KIS API Error {response.status} for {symbol}: {text}")
                raise Exception(f"KIS API Error {response.status}")

            data = await response.json()
            if data.get("rt_cd") != "0":
                msg = data.get("msg1", "Unknown error")
                logger.error(f"KIS Logic Error for {symbol}: {msg}")
                raise Exception(f"KIS Logic Error: {msg}")

            self._rate_limiter.reset_backoff()
            KISApiErrorRateTracker.get_instance().record_success()
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
                "change": (
                    float(output.get("prdy_ctrt", 0)) / 100.0
                    if output.get("prdy_ctrt")
                    else 0.0
                ),
                "timestamp": time.time(),  # Use local time as approx
            }

    async def _get_futures_price(self, symbol: str) -> dict[str, Any]:
        """Fetch current price for a Futures symbol."""
        session = await self._get_session()
        headers = await self.auth_manager.get_auth_headers_async()

        # TR ID: FHMIF10000000 (선물옵션 현재가)
        headers["tr_id"] = "FHMIF10000000"
        headers["custtype"] = "P"

        params = {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": symbol}

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
                KISApiErrorRateTracker.get_instance().record_error()
                logger.error(
                    f"KIS Futures API Error {response.status} for {symbol}: {text}"
                )
                raise Exception(f"KIS API Error {type}")

            data = await response.json()
            if data.get("rt_cd") != "0":
                msg = data.get("msg1", "Unknown error")
                logger.error(f"KIS Logic Error for {symbol} (Futures): {msg}")
                raise Exception(f"KIS Logic Error: {msg}")

            self._rate_limiter.reset_backoff()
            KISApiErrorRateTracker.get_instance().record_success()
            # FHMIF10000000 returns output1 (price), output2/3 (index info)
            output = data.get("output1", {})

            return {
                "code": symbol,
                "close": float(output.get("futs_prpr", 0)),
                "open": float(output.get("futs_oprc", 0)),
                "high": float(output.get("futs_hgpr", 0)),
                "low": float(output.get("futs_lwpr", 0)),
                "volume": int(output.get("acml_vol", 0)),
                "change": (
                    float(output.get("futs_prdy_ctrt", 0)) / 100.0
                    if output.get("futs_prdy_ctrt")
                    else 0.0
                ),
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
                    KISApiErrorRateTracker.get_instance().record_error()
                    return []

                data = await response.json()
                if data.get("rt_cd") != "0":
                    return []

                self._rate_limiter.reset_backoff()
                KISApiErrorRateTracker.get_instance().record_success()
                rows = data.get("output2", [])
                candles: list[dict[str, Any]] = []
                for row in rows[:count]:
                    try:
                        candles.append(
                            {
                                "open": float(row.get("stck_oprc", 0)),
                                "high": float(row.get("stck_hgpr", 0)),
                                "low": float(row.get("stck_lwpr", 0)),
                                "close": float(row.get("stck_prpr", 0)),
                                "volume": int(row.get("cntg_vol", 0)),
                            }
                        )
                    except (ValueError, TypeError):
                        continue

                candles.reverse()  # API returns newest first; we need oldest first
                return candles

        except Exception as e:
            logger.debug(f"Failed to fetch minute bars for {symbol}: {e}")
            KISApiErrorRateTracker.get_instance().record_error()
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
            path = (
                "/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
            )
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
                    KISApiErrorRateTracker.get_instance().record_error()
                    return []

                data = await response.json()
                if data.get("rt_cd") != "0":
                    return []

                self._rate_limiter.reset_backoff()
                KISApiErrorRateTracker.get_instance().record_success()
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
                        candles.append(
                            {
                                "open": float(row.get("stck_oprc", 0)),
                                "high": float(row.get("stck_hgpr", 0)),
                                "low": float(row.get("stck_lwpr", 0)),
                                "close": float(row.get("stck_prpr", 0)),
                                "volume": int(row.get("cntg_vol", 0)),
                            }
                        )
                    except (ValueError, TypeError):
                        continue

                candles.reverse()
                return candles

        except Exception as e:
            logger.debug(f"Failed to fetch futures bars for {symbol}: {e}")
            KISApiErrorRateTracker.get_instance().record_error()
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
            account_no = self._resolve_account_no("stock")
        account_no = self._normalize_account_no(account_no)
        if len(account_no) != 10:
            logger.warning(
                "Stock account number not configured; skipping balance inquiry"
            )
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
                    KISApiErrorRateTracker.get_instance().record_error()
                    logger.error(
                        f"Stock balance inquiry failed ({response.status}): {text}"
                    )
                    return []

                data = await response.json()
                if data.get("rt_cd") != "0":
                    logger.error(f"Stock balance inquiry error: {data.get('msg1', '')}")
                    return []

                self._rate_limiter.reset_backoff()
                KISApiErrorRateTracker.get_instance().record_success()
                positions = []
                for item in data.get("output1", []):
                    qty = int(item.get("hldg_qty", 0))
                    if qty <= 0:
                        continue
                    positions.append(
                        {
                            "code": item.get("pdno", ""),
                            "name": item.get("prdt_name", ""),
                            "side": "long",
                            "quantity": qty,
                            "avg_price": float(item.get("pchs_avg_pric", 0)),
                            "current_price": float(item.get("prpr", 0)),
                            "unrealized_pnl": float(item.get("evlu_pfls_amt", 0)),
                        }
                    )
                return positions

        except Exception as e:
            logger.warning(f"Stock balance inquiry exception: {e}")
            KISApiErrorRateTracker.get_instance().record_error()
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
            account_no = self._resolve_account_no("futures")
        account_no = self._normalize_account_no(account_no)
        if len(account_no) != 10:
            logger.warning(
                "Futures account number not configured; skipping balance inquiry"
            )
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
                    KISApiErrorRateTracker.get_instance().record_error()
                    logger.error(
                        f"Futures balance inquiry failed ({response.status}): {text}"
                    )
                    return []

                data = await response.json()
                if data.get("rt_cd") != "0":
                    logger.error(
                        f"Futures balance inquiry error: {data.get('msg1', '')}"
                    )
                    return []

                self._rate_limiter.reset_backoff()
                KISApiErrorRateTracker.get_instance().record_success()
                positions = []
                for item in data.get("output1", []):
                    qty = int(item.get("cblc_qty", 0))
                    if qty <= 0:
                        continue
                    # sll_buy_dvsn_cd: 01=매도(short), 02=매수(long)
                    side = "short" if item.get("sll_buy_dvsn_cd") == "01" else "long"
                    positions.append(
                        {
                            "code": item.get("pdno", ""),
                            "name": item.get("prdt_name", ""),
                            "side": side,
                            "quantity": qty,
                            "avg_price": float(item.get("pchs_avg_pric", 0)),
                            "current_price": float(
                                item.get("prpr", item.get("now_pric2", 0))
                            ),
                            "unrealized_pnl": float(item.get("evlu_pfls_amt", 0)),
                        }
                    )
                return positions

        except Exception as e:
            logger.warning(f"Futures balance inquiry exception: {e}")
            KISApiErrorRateTracker.get_instance().record_error()
            return []

    # ------------------------------------------------------------------
    # ATS Order Submission (Alternative Trading System - 넥스트레이드)
    # ------------------------------------------------------------------

    async def submit_ats_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float = 0,
        order_type: str = "00",
        account_no: str = "",
    ) -> dict[str, Any]:
        """Submit stock order to ATS (넥스트레이드) venue.

        Args:
            symbol: Stock code (6 digits)
            side: Order side ("BUY" or "SELL")
            quantity: Order quantity
            price: Order price (0 for market orders)
            order_type: Order division code (00=market, 01=limit, etc.)
            account_no: Account number (defaults to KIS_STOCK_ACCOUNT_NO env var)

        Returns:
            dict with keys: success (bool), order_no (str), message (str)

        Raises:
            Exception: On API errors or invalid parameters
        """
        if not account_no:
            account_no = self._resolve_account_no("stock")
        account_no = self._normalize_account_no(account_no)
        if len(account_no) != 10:
            raise ValueError("Account number must be 10 digits")

        if self._is_futures(symbol):
            raise ValueError(f"ATS orders only support stocks, not futures: {symbol}")

        await self._rate_limiter.acquire()
        session = await self._get_session()
        headers = await self.auth_manager.get_auth_headers_async()

        # TR IDs for ATS orders (distinct from KRX TR codes)
        is_buy = side.upper() == "BUY"
        if self.config.is_real:
            tr_id = "TTTC0852U" if is_buy else "TTTC0851U"
        else:
            tr_id = "VTTC0852U" if is_buy else "VTTC0851U"

        headers["tr_id"] = tr_id
        headers["custtype"] = "P"

        body = {
            "CANO": account_no[:8],
            "ACNT_PRDT_CD": account_no[8:10],
            "PDNO": symbol,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(int(price)) if price else "0",
        }

        # ATS endpoint path (based on context.json assumption)
        path = "/uapi/domestic-stock/v1/trading/order-ats"
        url = f"{self.config.base_url}{path}"

        timeout_seconds = getattr(
            self.config, "request_timeout_seconds", _DEFAULT_REQUEST_TIMEOUT
        )
        request_timeout = aiohttp.ClientTimeout(total=float(timeout_seconds))

        try:
            async with session.post(
                url, headers=headers, json=body, timeout=request_timeout
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    if "EGW00201" in text:
                        self._rate_limiter.penalty()
                    KISApiErrorRateTracker.get_instance().record_error()
                    logger.error(
                        f"ATS order failed ({response.status}) for {symbol}: {text}"
                    )
                    return {
                        "success": False,
                        "order_no": None,
                        "message": f"HTTP {response.status}: {text[:200]}",
                    }

                data = await response.json()
                if data.get("rt_cd") != "0":
                    error_msg = data.get("msg1", "Unknown error")
                    logger.error(
                        f"ATS order error for {symbol}: [{data.get('rt_cd')}] {error_msg}"
                    )
                    return {
                        "success": False,
                        "order_no": None,
                        "message": f"[{data.get('rt_cd')}] {error_msg}",
                    }

                self._rate_limiter.reset_backoff()
                KISApiErrorRateTracker.get_instance().record_success()
                output = data.get("output", {})
                order_no = str(output.get("ODNO") or output.get("odno") or "").strip()

                return {
                    "success": True,
                    "order_no": order_no or None,
                    "message": data.get("msg1", "Success"),
                }

        except TimeoutError:
            KISApiErrorRateTracker.get_instance().record_error()
            logger.error(f"ATS order timeout for {symbol}")
            return {
                "success": False,
                "order_no": None,
                "message": "Request timeout",
            }
        except Exception as e:
            KISApiErrorRateTracker.get_instance().record_error()
            logger.warning(f"ATS order exception for {symbol}: {e}")
            return {
                "success": False,
                "order_no": None,
                "message": str(e),
            }
