"""Order execution engine."""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import time as dt_time
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import aiohttp

from shared.kis.auth import is_token_expired_error, retry_once_on_token_expiry

from .config import ExecutionConfig, TradingMode
from .exceptions import RateLimitExceeded
from .models import ExecutionVenue, OrderRequest, OrderResponse, OrderSide

if TYPE_CHECKING:
    from .rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)


KST = ZoneInfo("Asia/Seoul")
NIGHT_START_KST = dt_time(18, 0)
NIGHT_END_KST = dt_time(6, 0)


@dataclass
class _FuturesFillStatus:
    """Internal futures fill status snapshot."""

    found: bool = False
    order_no: str = ""
    order_qty: int = 0
    filled_qty: int = 0
    remaining_qty: int = 0
    avg_fill_price: float = 0.0
    rejected_qty: int = 0
    reject_reason: str = ""


def _normalize_odno(value: str) -> str:
    stripped = str(value or "").strip()
    if not stripped:
        return ""
    return stripped.lstrip("0") or "0"


def _to_int(value: Any) -> int:
    try:
        return int(str(value).replace(",", "").strip() or "0")
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", "").strip() or "0")
    except (TypeError, ValueError):
        return 0.0


class OrderExecutor:
    """Order execution engine.

    Handles order routing to KIS API with:
    - Multiple trading modes (PAPER, MOCK, REAL)
    - Automatic retry on failure
    - Rate limiting
    """

    def __init__(
        self,
        config: ExecutionConfig,
        auth_manager=None,
        notifier=None,
    ):
        self.config = config
        self.auth_manager = auth_manager
        self.notifier = notifier

        # Session management
        self.session: aiohttp.ClientSession | None = None
        self._initialized = False

        # Rate limiter (optional, requires redis_url)
        self._rate_limiter: RedisRateLimiter | None = None
        if config.redis_url:
            from .rate_limiter import RedisRateLimiter
            self._rate_limiter = RedisRateLimiter(
                redis_url=config.redis_url,
                key_prefix=config.rate_limit_key,
                requests_per_second=config.requests_per_second,
                initial_retry_delay=config.rate_limit_initial_delay,
                max_retry_delay=config.rate_limit_max_delay,
                backoff_multiplier=config.rate_limit_backoff_multiplier,
                metrics_cache_ttl=config.metrics_cache_ttl,
                circuit_breaker_threshold=config.circuit_breaker_threshold,
                circuit_breaker_timeout=config.circuit_breaker_timeout,
            )

        # Account parsing — strip dash so "50110648-01" → prefix="50110648", suffix="01"
        self.account_prefix = ""
        self.account_suffix = ""
        clean_no = config.account_no.replace("-", "") if config.account_no else ""
        if clean_no and len(clean_no) >= 10:
            self.account_prefix = clean_no[:8]
            self.account_suffix = clean_no[8:10]

    async def initialize(self) -> None:
        """Initialize HTTP session with connection pooling.

        Should be called during application startup to avoid latency
        on first order. If not called, will be auto-initialized on
        first order with a warning.
        """
        if not self._initialized:
            # Configure connection pool for optimal performance
            connector = aiohttp.TCPConnector(
                limit=10,               # Total connection pool size
                limit_per_host=5,       # Per-host connection limit
                ttl_dns_cache=300,      # DNS cache TTL (5 minutes)
                keepalive_timeout=30,   # Keep-alive for connection reuse
            )
            self.session = aiohttp.ClientSession(connector=connector)
            self._initialized = True
            logger.debug("OrderExecutor initialized with connection pooling")

    async def warmup(self) -> bool:
        """Pre-establish HTTP connections to KIS API endpoints.

        Call this during application startup (after initialize()) to
        reduce latency on the first real order. Makes HEAD requests to
        pre-warm the connection pool and DNS cache.

        Returns:
            True if warmup succeeded, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        mode = self.config.trading_mode
        if mode == TradingMode.PAPER.value:
            logger.debug("Skipping warmup for PAPER mode")
            return True

        # Determine target URL based on mode
        if mode == TradingMode.MOCK.value:
            base_url = self.config.kis_mock_base_url
        else:
            base_url = self.config.kis_real_base_url

        try:
            # HEAD request to establish connection without full response
            async with self.session.head(base_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                logger.info(f"Connection warmup to {base_url}: status={response.status}")
                return True
        except Exception as e:
            logger.warning(f"Connection warmup failed for {base_url}: {e}")
            return False

    async def cleanup(self) -> None:
        """Cleanup HTTP session and rate limiter."""
        if self.session:
            await self.session.close()
            self.session = None
        if self._rate_limiter:
            await self._rate_limiter.close()
        self._initialized = False
        logger.debug("OrderExecutor cleaned up")

    async def execute_order(self, order: OrderRequest) -> OrderResponse:
        """Execute order with retry logic.

        Args:
            order: Order request

        Returns:
            OrderResponse with result
        """
        # Acquire rate limit before retry loop
        if self._rate_limiter:
            try:
                await self._rate_limiter.acquire(timeout=self.config.rate_limit_timeout)
            except RateLimitExceeded:
                return OrderResponse(
                    success=False,
                    message="Rate limit exceeded, try again later"
                )

        for attempt in range(self.config.max_retries):
            try:
                response = await self._send_order(order)
                if response.success:
                    await self._log_success(order, response)
                    return response

                # If broker accepted an order number, do not auto-retry to avoid
                # accidental duplicate orders (e.g., timeout-then-cancel flow).
                if response.order_no:
                    logger.warning(
                        f"Order attempt {attempt + 1} stopped without retry: "
                        f"{response.message} (order_no={response.order_no})"
                    )
                    return response

                logger.warning(f"Order attempt {attempt + 1} failed: {response.message}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)

            except Exception as e:
                logger.error(f"Order attempt {attempt + 1} exception: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    return OrderResponse(success=False, message=str(e))

        return OrderResponse(
            success=False,
            message=f"Failed after {self.config.max_retries} retries"
        )

    async def _send_order(self, order: OrderRequest) -> OrderResponse:
        """Send order based on trading mode."""
        mode = str(self.config.trading_mode or "").upper()

        if mode == TradingMode.PAPER.value:
            return await self._simulate_order(order)
        if mode not in {TradingMode.MOCK.value, TradingMode.REAL.value}:
            return OrderResponse(success=False, message=f"Unknown mode: {mode}")

        is_mock = mode == TradingMode.MOCK.value
        if self._is_futures_order(order):
            if is_mock:
                logger.warning("KIS mock server does not support futures; routing to real server")
            return await self._send_kis_futures_order(order, is_mock=False)
        return await self._send_kis_stock_order(order, is_mock=is_mock)

    async def _simulate_order(self, order: OrderRequest) -> OrderResponse:
        """Simulate order for paper trading."""
        # Generate fake order number
        order_no = f"PAPER-{uuid.uuid4().hex[:8].upper()}"

        # Preserve venue from order request
        venue = order.venue if order.venue else ExecutionVenue.KRX.value

        logger.info(
            f"[PAPER] Order simulated: {order.side} {order.code} "
            f"x{order.quantity} @ {order.price or 'MARKET'} venue={venue}"
        )

        return OrderResponse(
            success=True,
            order_no=order_no,
            message="Paper order simulated",
            filled_qty=order.quantity,
            venue=venue,
        )

    async def _send_kis_stock_order(
        self, order: OrderRequest, is_mock: bool
    ) -> OrderResponse:
        """Send domestic stock order to KIS API with venue-specific routing."""
        # Determine venue (default to KRX if not specified)
        venue = order.venue if order.venue else ExecutionVenue.KRX.value
        is_ats = venue == ExecutionVenue.ATS.value

        # Select TR code based on venue, mode, and side
        if is_ats:
            if order.side == OrderSide.BUY.value:
                tr_id = self.config.tr_code_ats_buy_mock if is_mock else self.config.tr_code_ats_buy_real
            else:
                tr_id = self.config.tr_code_ats_sell_mock if is_mock else self.config.tr_code_ats_sell_real
        else:
            if order.side == OrderSide.BUY.value:
                tr_id = self.config.tr_code_buy_mock if is_mock else self.config.tr_code_buy_real
            else:
                tr_id = self.config.tr_code_sell_mock if is_mock else self.config.tr_code_sell_real

        headers = await self._build_auth_headers(tr_id=tr_id)
        if headers is None:
            return OrderResponse(
                success=False,
                message="Failed to get auth headers",
                venue=venue
            )

        body = {
            "CANO": self.account_prefix,
            "ACNT_PRDT_CD": self.account_suffix,
            "PDNO": order.code,
            "ORD_DVSN": order.order_type,
            "ORD_QTY": str(order.quantity),
            "ORD_UNPR": str(int(order.price)) if order.price else "0",
        }

        # Route to venue-specific endpoint
        base_url = self.config.kis_mock_base_url if is_mock else self.config.kis_real_base_url
        endpoint = "order-ats" if is_ats else "order-cash"
        url = f"{base_url}/uapi/domestic-stock/v1/trading/{endpoint}"

        logger.debug(f"Routing order to venue={venue}, endpoint={endpoint}")

        data, status = await self._request_json("POST", url, headers=headers, json=body)
        if status == 200 and data.get("rt_cd") == "0":
            return OrderResponse(
                success=True,
                order_no=data.get("output", {}).get("ODNO"),
                message=data.get("msg1", "Success"),
                venue=venue,
            )
        return OrderResponse(
            success=False,
            message=f"[{data.get('rt_cd')}] {data.get('msg1', 'Unknown error')}",
            venue=venue,
        )

    async def _send_kis_futures_order(
        self, order: OrderRequest, is_mock: bool
    ) -> OrderResponse:
        """Send domestic futures order and monitor fill/cancel when configured."""
        # Futures always use KRX venue
        venue = order.venue if order.venue else ExecutionVenue.KRX.value

        is_night = self._is_night_session()
        # Phase 5 legal-review §4: night session is disabled by default.
        # `config/market_schedule.yaml::futures.night.enabled` must be true
        # AND the operator must complete the night-session compliance review
        # before night orders are accepted. Fail-closed otherwise.
        if is_night:
            from shared.strategy.market_time import is_futures_night_session_enabled

            if not is_futures_night_session_enabled():
                logger.warning(
                    "night session refused: code=%s qty=%s "
                    "(market_schedule.yaml::futures.night.enabled is false)",
                    order.code,
                    order.quantity,
                )
                return OrderResponse(
                    success=False,
                    message=(
                        "Night session disabled in "
                        "config/market_schedule.yaml::futures.night.enabled"
                    ),
                    venue=venue,
                )
        tr_id = self._resolve_futures_order_tr_id(is_mock=is_mock, is_night=is_night)

        headers = await self._build_auth_headers(tr_id=tr_id)
        if headers is None:
            return OrderResponse(
                success=False,
                message="Failed to get auth headers",
                venue=venue
            )

        ord_dvsn_cd = self._map_futures_order_type(order.order_type)
        body = {
            "ORD_PRCS_DVSN_CD": "02",
            "CANO": self.account_prefix,
            "ACNT_PRDT_CD": self.account_suffix,
            "SLL_BUY_DVSN_CD": "02" if order.side == OrderSide.BUY.value else "01",
            "SHTN_PDNO": order.code,
            "ORD_QTY": str(order.quantity),
            "UNIT_PRICE": str(order.price) if order.price else "0",
            "NMPR_TYPE_CD": "",
            "KRX_NMPR_CNDT_CD": "",
            "CTAC_TLNO": "",
            "FUOP_ITEM_DVSN_CD": "",
            "ORD_DVSN_CD": ord_dvsn_cd,
        }

        base_url = self.config.kis_mock_base_url if is_mock else self.config.kis_real_base_url
        url = f"{base_url}/uapi/domestic-futureoption/v1/trading/order"
        data, status = await self._request_json("POST", url, headers=headers, json=body)
        if status != 200 or data.get("rt_cd") != "0":
            return OrderResponse(
                success=False,
                message=f"[{data.get('rt_cd')}] {data.get('msg1', 'Unknown error')}",
                venue=venue,
            )

        output = data.get("output", {}) if isinstance(data.get("output"), dict) else {}
        order_no = str(output.get("ODNO") or output.get("odno") or "").strip()
        accepted = OrderResponse(
            success=True,
            order_no=order_no or None,
            message=data.get("msg1", "Success"),
            venue=venue,
        )

        should_check_fill = (
            self.config.futures_fill_check_enabled
            and bool(order_no)
            and ord_dvsn_cd.startswith("01")
        )
        if not should_check_fill:
            return accepted

        return await self._await_futures_fill_or_cancel(
            order=order,
            order_no=order_no,
            is_mock=is_mock,
            is_night=is_night,
        )

    async def _await_futures_fill_or_cancel(
        self,
        *,
        order: OrderRequest,
        order_no: str,
        is_mock: bool,
        is_night: bool,
    ) -> OrderResponse:
        """Wait for futures fill status and cancel unfilled remainder on timeout."""
        # Futures always use KRX venue
        venue = order.venue if order.venue else ExecutionVenue.KRX.value

        poll = float(self.config.futures_fill_check_poll_interval_seconds)
        timeout = float(self.config.futures_fill_check_timeout_seconds)
        deadline = datetime.now() + timedelta(seconds=timeout)

        last_status = _FuturesFillStatus(found=False, order_no=order_no, order_qty=order.quantity)
        while datetime.now() < deadline:
            status = await self._inquire_futures_fill_status(
                order=order,
                order_no=order_no,
                is_mock=is_mock,
                is_night=is_night,
            )
            if status.found:
                last_status = status
                if status.rejected_qty > 0:
                    reason = status.reject_reason or "order_rejected"
                    return OrderResponse(
                        success=False,
                        order_no=order_no,
                        message=f"Futures order rejected: {reason}",
                        filled_qty=status.filled_qty,
                        filled_price=status.avg_fill_price,
                        venue=venue,
                    )
                if status.filled_qty >= order.quantity:
                    return OrderResponse(
                        success=True,
                        order_no=order_no,
                        message="Futures order fully filled",
                        filled_qty=status.filled_qty,
                        filled_price=status.avg_fill_price,
                        venue=venue,
                    )
            await asyncio.sleep(poll)

        if not self.config.futures_auto_cancel_unfilled:
            return OrderResponse(
                success=False,
                order_no=order_no,
                message="Futures order fill timeout",
                filled_qty=last_status.filled_qty,
                filled_price=last_status.avg_fill_price,
                venue=venue,
            )

        cancel_qty = last_status.remaining_qty if last_status.remaining_qty > 0 else max(
            0, order.quantity - last_status.filled_qty
        )
        cancel_resp = await self._cancel_futures_order(
            order_no=order_no,
            cancel_quantity=cancel_qty,
            is_mock=is_mock,
            is_night=is_night,
        )
        if not cancel_resp.success:
            return OrderResponse(
                success=False,
                order_no=order_no,
                message=f"Futures fill timeout and cancel failed: {cancel_resp.message}",
                filled_qty=last_status.filled_qty,
                filled_price=last_status.avg_fill_price,
                venue=venue,
            )

        refreshed = await self._inquire_futures_fill_status(
            order=order,
            order_no=order_no,
            is_mock=is_mock,
            is_night=is_night,
        )
        filled_qty = refreshed.filled_qty if refreshed.found else last_status.filled_qty
        filled_price = (
            refreshed.avg_fill_price if refreshed.found else last_status.avg_fill_price
        )
        return OrderResponse(
            success=False,
            order_no=order_no,
            message=f"Futures unfilled order cancelled: {cancel_resp.message}",
            filled_qty=filled_qty,
            filled_price=filled_price,
            venue=venue,
        )

    async def _inquire_futures_fill_status(
        self,
        *,
        order: OrderRequest,
        order_no: str,
        is_mock: bool,
        is_night: bool,
    ) -> _FuturesFillStatus:
        """Query futures order/fill status using KIS inquire-ccnl API."""
        tr_id, path = self._resolve_futures_inquire_tr_id_and_path(
            is_mock=is_mock, is_night=is_night
        )
        headers = await self._build_auth_headers(tr_id=tr_id)
        if headers is None:
            return _FuturesFillStatus(found=False, order_no=order_no, order_qty=order.quantity)

        today = datetime.now(KST).date()
        query_dates = [today, today - timedelta(days=1)]
        target_odno = _normalize_odno(order_no)

        for order_date in query_dates:
            params: dict[str, str] = {
                "CANO": self.account_prefix,
                "ACNT_PRDT_CD": self.account_suffix,
                "STRT_ORD_DT": order_date.strftime("%Y%m%d"),
                "END_ORD_DT": order_date.strftime("%Y%m%d"),
                "SLL_BUY_DVSN_CD": "00",
                "CCLD_NCCS_DVSN": "00",
                "SORT_SQN": "DS",
                "STRT_ODNO": order_no,
                "PDNO": order.code,
                "MKET_ID_CD": "",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": "",
            }
            if is_night and not is_mock:
                params["FUOP_DVSN_CD"] = ""
                params["SCRN_DVSN"] = "02"

            base_url = self.config.kis_mock_base_url if is_mock else self.config.kis_real_base_url
            url = f"{base_url}{path}"
            data, status = await self._request_json("GET", url, headers=headers, params=params)
            if status != 200 or data.get("rt_cd") != "0":
                continue

            rows = data.get("output1") if isinstance(data.get("output1"), list) else []
            for row in rows:
                odno_raw = str(row.get("odno", "")).strip()
                if _normalize_odno(odno_raw) != target_odno:
                    continue
                filled_qty = _to_int(row.get("tot_ccld_qty"))
                remaining_qty = _to_int(row.get("qty"))
                order_qty = _to_int(row.get("ord_qty"))
                if order_qty <= 0:
                    order_qty = order.quantity
                return _FuturesFillStatus(
                    found=True,
                    order_no=odno_raw or order_no,
                    order_qty=order_qty,
                    filled_qty=filled_qty,
                    remaining_qty=remaining_qty,
                    avg_fill_price=_to_float(row.get("avg_idx")),
                    rejected_qty=_to_int(row.get("rjct_qty")),
                    reject_reason=str(row.get("ingr_trad_rjct_rson_name", "")).strip(),
                )

        return _FuturesFillStatus(found=False, order_no=order_no, order_qty=order.quantity)

    async def _cancel_futures_order(
        self,
        *,
        order_no: str,
        cancel_quantity: int,
        is_mock: bool,
        is_night: bool,
    ) -> OrderResponse:
        """Cancel futures order using order-rvsecncl API."""
        tr_id = self._resolve_futures_cancel_tr_id(is_mock=is_mock, is_night=is_night)
        headers = await self._build_auth_headers(tr_id=tr_id)
        if headers is None:
            return OrderResponse(success=False, message="Failed to get auth headers")

        ord_qty_value = cancel_quantity if cancel_quantity > 0 else 0
        body = {
            "ORD_PRCS_DVSN_CD": "02",
            "CANO": self.account_prefix,
            "ACNT_PRDT_CD": self.account_suffix,
            "RVSE_CNCL_DVSN_CD": "02",
            "ORGN_ODNO": order_no,
            "ORD_QTY": str(ord_qty_value),
            "UNIT_PRICE": "0",
            "NMPR_TYPE_CD": "01",
            "KRX_NMPR_CNDT_CD": "0",
            "RMN_QTY_YN": "Y",
            "CTAC_TLNO": "",
            "FUOP_ITEM_DVSN_CD": "",
            "ORD_DVSN_CD": "01",
        }

        base_url = self.config.kis_mock_base_url if is_mock else self.config.kis_real_base_url
        url = f"{base_url}/uapi/domestic-futureoption/v1/trading/order-rvsecncl"
        data, status = await self._request_json("POST", url, headers=headers, json=body)
        if status == 200 and data.get("rt_cd") == "0":
            return OrderResponse(
                success=True,
                order_no=data.get("output", {}).get("ODNO"),
                message=data.get("msg1", "Cancel success"),
            )
        return OrderResponse(
            success=False,
            message=f"[{data.get('rt_cd')}] {data.get('msg1', 'Cancel failed')}",
        )

    async def _build_auth_headers(self, tr_id: str) -> dict[str, Any] | None:
        """Build KIS auth headers with TR_ID."""
        if not self.auth_manager:
            return None

        if not self.session:
            logger.warning(
                "OrderExecutor not initialized - calling initialize() now. "
                "For predictable latency, call initialize() during app startup."
            )
            await self.initialize()

        # Get auth headers (supports both sync + async auth managers).
        headers = None
        try:
            maybe = self.auth_manager.get_auth_headers()
            if asyncio.iscoroutine(maybe):
                headers = await maybe
            else:
                headers = maybe
        except Exception:
            # Prefer explicit async method when available.
            if hasattr(self.auth_manager, "get_auth_headers_async"):
                headers = await self.auth_manager.get_auth_headers_async()

        if not isinstance(headers, dict) or not headers:
            return None
        headers["tr_id"] = tr_id
        headers.setdefault("custtype", "P")
        return headers

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, Any],
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], int]:
        """Execute HTTP request and parse JSON body."""
        if self._rate_limiter:
            try:
                await self._rate_limiter.acquire(timeout=self.config.rate_limit_timeout)
            except RateLimitExceeded:
                return {"rt_cd": "RATE_LIMIT", "msg1": "Rate limit exceeded"}, 429

        async def do_request(current_headers: dict[str, Any]) -> tuple[dict[str, Any], int]:
            request_timeout = aiohttp.ClientTimeout(
                total=float(self.config.order_request_timeout_seconds)
            )
            async with self.session.request(
                method,
                url,
                headers=current_headers,
                params=params,
                json=json,
                timeout=request_timeout,
            ) as response:
                try:
                    data = await response.json(content_type=None)
                except Exception:
                    text = await response.text()
                    data = {
                        "rt_cd": str(response.status),
                        "msg1": text,
                    }
                return data if isinstance(data, dict) else {"output": data}, int(response.status)

        async def attempt(retry: int) -> tuple[dict[str, Any], int]:
            current_headers = headers
            if retry:
                tr_id = str(headers.get("tr_id") or "")
                refreshed = await self._build_auth_headers(tr_id) if tr_id else None
                if refreshed is not None:
                    current_headers = refreshed
            return await do_request(current_headers)

        try:
            return await retry_once_on_token_expiry(
                attempt,
                self.auth_manager,
                is_expired=lambda result: is_token_expired_error(result[0]),
            )
        except Exception as e:
            logger.error(f"KIS request error ({method} {url}): {e}")
            raise

    @staticmethod
    def _is_futures_code(code: str) -> bool:
        return len(code) != 6 or not code.isdigit()

    def _is_futures_order(self, order: OrderRequest) -> bool:
        key = str(getattr(self.config, "rate_limit_key", "")).strip().lower()
        if key == "futures":
            return True
        return self._is_futures_code(order.code)

    @staticmethod
    def _is_night_session(now: datetime | None = None) -> bool:
        current = now.astimezone(KST) if now and now.tzinfo else datetime.now(KST)
        t = current.time()
        return (t >= NIGHT_START_KST) or (t < NIGHT_END_KST)

    def _resolve_futures_order_tr_id(self, *, is_mock: bool, is_night: bool) -> str:
        if is_mock:
            return self.config.futures_tr_code_order_day_mock
        if is_night:
            return self.config.futures_tr_code_order_night_real
        return self.config.futures_tr_code_order_day_real

    def _resolve_futures_cancel_tr_id(self, *, is_mock: bool, is_night: bool) -> str:
        if is_mock:
            return self.config.futures_tr_code_cancel_day_mock
        if is_night:
            return self.config.futures_tr_code_cancel_night_real
        return self.config.futures_tr_code_cancel_day_real

    def _resolve_futures_inquire_tr_id_and_path(
        self, *, is_mock: bool, is_night: bool
    ) -> tuple[str, str]:
        if is_mock:
            return (
                self.config.futures_tr_code_inquire_day_mock,
                "/uapi/domestic-futureoption/v1/trading/inquire-ccnl",
            )
        if is_night:
            return (
                self.config.futures_tr_code_inquire_night_real,
                "/uapi/domestic-futureoption/v1/trading/inquire-ngt-ccnl",
            )
        return (
            self.config.futures_tr_code_inquire_day_real,
            "/uapi/domestic-futureoption/v1/trading/inquire-ccnl",
        )

    @staticmethod
    def _map_futures_order_type(order_type: str) -> str:
        mapping = {
            "00": "01",  # stock limit -> futures limit
            "01": "02",  # stock market -> futures market
            "02": "03",  # stock conditional -> futures conditional
        }
        if order_type in mapping:
            return mapping[order_type]
        if order_type in {"01", "02", "03", "04", "10", "11", "12", "13", "14", "15"}:
            return order_type
        return "01"

    async def _log_success(self, order: OrderRequest, response: OrderResponse) -> None:
        """Log successful order."""
        logger.info(
            f"Order executed: {order.side} {order.code} x{order.quantity} "
            f"-> {response.order_no}"
        )

        if self.notifier:
            await self.notifier.send_message(
                f"Order Executed: {order.side} {order.code} x{order.quantity}"
            )
