"""Order execution engine."""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import time as dt_time
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import aiohttp

from shared.kis.auth import is_token_expired_error, retry_once_on_token_expiry

from .config import ExecutionConfig, TradingMode
from .exceptions import OrderExecutionError, RateLimitExceeded
from .models import ExecutionVenue, OrderRequest, OrderResponse, OrderSide

if TYPE_CHECKING:
    from .rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)


#: KIS gateway code for "초당 거래건수를 초과하였습니다" (per-second transaction
#: count exceeded). Measured shape (broker-probe artifact P-13): HTTP 500 +
#: ``rt_cd="1"`` + ``msg_cd="EGW00201"``. This is a SELF-INFLICTED pacing
#: rejection — the broker is reachable and healthy — so it must not be retried
#: at the ordinary retry delay and must not count as a KIS-side infra failure.
KIS_THROTTLE_MSG_CD = "EGW00201"

#: Anchored match for the throttle code inside a free-text message body.
#: ``_request_json``'s non-JSON branch assigns the ENTIRE response body to
#: ``msg1``, so a bare substring test would silently exclude any gateway error
#: page that merely mentions the token (e.g. in a help link or a log echo).
#: The boundary requires the code to stand alone as a KIS-style code.
_THROTTLE_MSG_CD_RE = re.compile(rf"(?<![0-9A-Z]){KIS_THROTTLE_MSG_CD}(?![0-9A-Z])")

#: Transport-level failures reaching the broker. These are NOT protocol
#: answers: a call site that needs an outcome (fill status, cancel) must
#: convert them into its own failure state instead of letting them unwind the
#: caller, which would take the recovery path with them.
_TRANSPORT_ERRORS = (aiohttp.ClientError, TimeoutError, OSError)


def _broker_msg_cd(data: dict[str, Any]) -> str:
    """Extract the broker's ``msg_cd`` from a parsed KIS response body."""
    return str(data.get("msg_cd") or "").strip().upper()


def _is_throttle_response(data: dict[str, Any]) -> bool:
    """True when the broker refused the request for exceeding its rate.

    Checks the structured ``msg_cd`` first and falls back to an ANCHORED match
    on the message body, because some KIS gateway errors surface the code only
    inside ``msg1``.
    """
    if _broker_msg_cd(data) == KIS_THROTTLE_MSG_CD:
        return True
    return bool(_THROTTLE_MSG_CD_RE.search(str(data.get("msg1") or "")))


def _record_kis_api_outcome(*, is_error: bool) -> None:
    """Feed an OrderExecutor KIS REST outcome into the shared error-rate tracker.

    The tracker (a process-global singleton) publishes the futures kill-switch's
    ``kill_switch:metrics:api_error_rate_5min:{source}`` signal. OrderExecutor is
    the only continuous KIS REST caller in the decoupled futures pipeline (the
    price feed is WebSocket), so its order/query outcomes are that pipeline's
    api-error signal. Only KIS-side infra failures (5xx / 429 / network) count;
    business rejects (KIS reachable) do not. Telemetry must never break order
    placement, so every failure here is swallowed.
    """
    try:
        from shared.kis.error_rate import KISApiErrorRateTracker

        tracker = KISApiErrorRateTracker.get_instance()
        if is_error:
            tracker.record_error()
        else:
            tracker.record_success()
    except Exception:  # noqa: BLE001 — telemetry is best-effort, never fatal
        logger.debug("error-rate tracker record failed", exc_info=True)


KST = ZoneInfo("Asia/Seoul")
NIGHT_START_KST = dt_time(18, 0)
NIGHT_END_KST = dt_time(6, 0)


# ---------------------------------------------------------------------------
# KIS order-type wire codes.
#
# Source: KIS official ``open-trading-api`` ``examples_llm`` wrappers
# (accessed 2026-07-29):
#   domestic_stock/inquire_psbl_order   (order_cash enumerates no ORD_DVSN value)
#       ORD_DVSN          00:지정가, 01:시장가
#                         02:조건부지정가 — inquire_psbl_order 산문 및
#                         models.py:19 기준; 공식 열거 미확정
#   domestic_futureoption/order
#       ORD_DVSN_CD       [필수] 01:지정가 02:시장가 03:조건부 04:최유리
#                                10:지정가(IOC) 11:지정가(FOK) 12:시장가(IOC)
#                                13:시장가(FOK) 14:최유리(IOC) 15:최유리(FOK)
#       NMPR_TYPE_CD      [필수] 01:지정가, 02:시장가, 03:조건부, 04:최유리
#       KRX_NMPR_CNDT_CD  [필수] 0:없음, 3:IOC, 4:FOK
#
# WARNING: the two asset classes give OPPOSITE meanings to "01" — stock
# ORD_DVSN "01" is 시장가 (market) while futures ORD_DVSN_CD "01" is 지정가
# (limit). Because of that inversion these tables deliberately have NO default
# entry: an unmapped order type is refused (fail-closed) instead of being
# silently coerced into a code that could turn a limit order into a market one.
# ---------------------------------------------------------------------------

#: Internal ``OrderType`` value -> stock ``ORD_DVSN``.
_STOCK_ORD_DVSN: dict[str, str] = {
    "00": "00",  # 지정가 (limit)
    "01": "01",  # 시장가 (market)
    "02": "02",  # 조건부지정가 (conditional limit)
}

#: Internal ``OrderType`` value (stock code system) -> futures ``ORD_DVSN_CD``.
_FUTURES_ORD_DVSN_CD: dict[str, str] = {
    "00": "01",  # stock limit -> futures limit
    "01": "02",  # stock market -> futures market
    "02": "03",  # stock conditional -> futures conditional
}

#: Futures-native ``ORD_DVSN_CD`` values accepted verbatim (KIS enumeration).
_FUTURES_ORD_DVSN_CD_NATIVE: frozenset[str] = frozenset(
    {"01", "02", "03", "04", "10", "11", "12", "13", "14", "15"}
)

#: Futures ``ORD_DVSN_CD`` -> (``NMPR_TYPE_CD``, ``KRX_NMPR_CNDT_CD``).
#:
#: Both target fields are [필수] in the KIS futures order contract. The pair is
#: derived structurally from the order type itself (base quote type + the TIF
#: folded into ORD_DVSN_CD), which matches the official wrapper example
#: ``ord_dvsn_cd="02"`` sent together with ``nmpr_type_cd="02"`` and
#: ``krx_nmpr_cndt_cd="0"``.
_FUTURES_NMPR_CODES: dict[str, tuple[str, str]] = {
    "01": ("01", "0"),  # 지정가
    "02": ("02", "0"),  # 시장가
    "03": ("03", "0"),  # 조건부
    "04": ("04", "0"),  # 최유리
    "10": ("01", "3"),  # 지정가 (IOC)
    "11": ("01", "4"),  # 지정가 (FOK)
    "12": ("02", "3"),  # 시장가 (IOC)
    "13": ("02", "4"),  # 시장가 (FOK)
    "14": ("04", "3"),  # 최유리 (IOC)
    "15": ("04", "4"),  # 최유리 (FOK)
}


class FillQueryOutcome(StrEnum):
    """Outcome of a futures fill-status query.

    The three states are NOT interchangeable and must never collapse into one
    another:

    - ``FOUND``: the broker answered and the order row was present. The
      quantities on the snapshot are a measurement.
    - ``NOT_PRESENT``: the broker answered and the order row was absent. This
      is authoritative evidence of "no fill visible yet".
    - ``QUERY_FAILED``: we never got an answer (transport error, throttle,
      ``rt_cd != "0"``, missing auth headers). Nothing at all is known about the
      fill; reading ``filled_qty == 0`` off such a snapshot as "unfilled" is how
      a filled position gets reported as a flat book.
    """

    FOUND = "FOUND"
    NOT_PRESENT = "NOT_PRESENT"
    QUERY_FAILED = "QUERY_FAILED"


@dataclass
class _FuturesFillStatus:
    """Internal futures fill status snapshot.

    ``outcome`` is the single source of truth; ``found`` is derived from it so
    the two can never disagree.
    """

    outcome: FillQueryOutcome = FillQueryOutcome.NOT_PRESENT
    order_no: str = ""
    order_qty: int = 0
    filled_qty: int = 0
    remaining_qty: int = 0
    avg_fill_price: float = 0.0
    rejected_qty: int = 0
    reject_reason: str = ""

    @property
    def found(self) -> bool:
        """True only for ``FOUND`` — never for ``QUERY_FAILED``."""
        return self.outcome is FillQueryOutcome.FOUND

    @property
    def query_failed(self) -> bool:
        """True when the fill state could not be established at all."""
        return self.outcome is FillQueryOutcome.QUERY_FAILED


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

        # Consecutive broker-throttle responses — the throttle-storm signal.
        self._throttle_streak = 0

        # Rate limiter (optional, requires redis_url)
        self._rate_limiter: RedisRateLimiter | None = None
        # Separate bucket for the timeout cancel. One futures order issues a
        # submit plus several fill polls plus a re-query through the main
        # bucket (see the per-order request budget documented in
        # config/execution.yaml), so a cancel sharing that bucket can be
        # starved by the very polls that decided the cancel was needed — the
        # "order left resting at the broker" outcome D-5 exists to prevent.
        # A cancel is a safety operation and is deliberately not queued behind
        # them. Both buckets use the same configured requests_per_second; the
        # broker-side aggregate ceiling is deferred to a measured bound.
        self._cancel_rate_limiter: RedisRateLimiter | None = None
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
            self._cancel_rate_limiter = RedisRateLimiter(
                redis_url=config.redis_url,
                key_prefix=f"{config.rate_limit_key}{config.cancel_rate_limit_suffix}",
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
        if self._cancel_rate_limiter:
            await self._cancel_rate_limiter.close()
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

        throttle_streak = 0
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
                    if response.broker_msg_cd == KIS_THROTTLE_MSG_CD:
                        throttle_streak += 1
                        delay = self._throttle_backoff_delay(throttle_streak)
                        logger.warning(
                            "KIS throttle (%s) on order attempt %d — backing off "
                            "%.2fs instead of retry_delay=%.2fs (retrying at or "
                            "below the pacing that was just refused would only "
                            "deepen the throttle)",
                            KIS_THROTTLE_MSG_CD,
                            attempt + 1,
                            delay,
                            self.config.retry_delay,
                        )
                    else:
                        throttle_streak = 0
                        delay = self.config.retry_delay
                    await asyncio.sleep(delay)

            except OrderExecutionError as e:
                # Deterministic refusal (e.g. an order type outside the explicit
                # ORD_DVSN / ORD_DVSN_CD tables). Retrying cannot change the
                # outcome, so fail closed at once rather than burning
                # `max_retries` sleeps and counting the same error three times.
                logger.error(f"Order refused without retry: {e}")
                return OrderResponse(success=False, message=str(e))

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

    @staticmethod
    def _reject_msg_cd(data: dict[str, Any]) -> str:
        """Broker ``msg_cd`` for a rejected request, normalized for throttles.

        A throttle that arrives with the code only in ``msg1`` is reported as
        ``EGW00201`` too, so every caller can branch on one structured value
        instead of substring-matching a human-readable message.
        """
        if _is_throttle_response(data):
            return KIS_THROTTLE_MSG_CD
        return _broker_msg_cd(data)

    def _throttle_backoff_delay(self, streak: int) -> float:
        """Backoff for the ``streak``-th consecutive broker throttle rejection.

        Geometric growth from ``throttle_backoff_initial_seconds``, capped at
        ``throttle_backoff_max_seconds``. All three parameters are config-driven
        (``config/execution.yaml::execution``).
        """
        steps = max(int(streak), 1) - 1
        delay = float(self.config.throttle_backoff_initial_seconds) * (
            float(self.config.throttle_backoff_multiplier) ** steps
        )
        return min(delay, float(self.config.throttle_backoff_max_seconds))

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
            "ORD_DVSN": self._map_stock_order_type(order.order_type),
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
            broker_msg_cd=self._reject_msg_cd(data),
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
        nmpr_type_cd, krx_nmpr_cndt_cd = self._futures_quote_type_codes(ord_dvsn_cd)
        body = {
            "ORD_PRCS_DVSN_CD": "02",
            "CANO": self.account_prefix,
            "ACNT_PRDT_CD": self.account_suffix,
            "SLL_BUY_DVSN_CD": "02" if order.side == OrderSide.BUY.value else "01",
            "SHTN_PDNO": order.code,
            "ORD_QTY": str(order.quantity),
            "UNIT_PRICE": str(order.price) if order.price else "0",
            "NMPR_TYPE_CD": nmpr_type_cd,
            "KRX_NMPR_CNDT_CD": krx_nmpr_cndt_cd,
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
                broker_msg_cd=self._reject_msg_cd(data),
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

        last_status = _FuturesFillStatus(
            outcome=FillQueryOutcome.NOT_PRESENT,
            order_no=order_no,
            order_qty=order.quantity,
        )
        # Outcome of the MOST RECENT poll. QUERY_FAILED here means the timeout
        # below is being reached without evidence, not with evidence of no fill.
        last_outcome = FillQueryOutcome.NOT_PRESENT
        while datetime.now() < deadline:
            status = await self._inquire_futures_fill_status(
                order=order,
                order_no=order_no,
                is_mock=is_mock,
                is_night=is_night,
            )
            last_outcome = status.outcome
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
            # QUERY_FAILED keeps polling (the failure may be transient) but is
            # deliberately NOT folded into `last_status` — an unanswered query
            # must not overwrite the last measured snapshot.
            await asyncio.sleep(poll)

        if last_outcome is FillQueryOutcome.QUERY_FAILED:
            logger.warning(
                "futures fill check timed out with an UNANSWERED status query "
                "(order_no=%s code=%s qty=%s): fill state is unknown, not zero",
                order_no,
                order.code,
                order.quantity,
            )

        if not self.config.futures_auto_cancel_unfilled:
            return OrderResponse(
                success=False,
                order_no=order_no,
                message="Futures order fill timeout",
                filled_qty=last_status.filled_qty,
                filled_price=last_status.avg_fill_price,
                venue=venue,
                fill_state_unknown=last_outcome is FillQueryOutcome.QUERY_FAILED,
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

        # Re-query on BOTH cancel outcomes. The old code re-queried only after a
        # successful cancel, so the one case where our "unfilled" belief is most
        # likely wrong — the broker rejecting the cancel because the order had
        # already filled — was the one case that reported filled_qty=0.
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

        if not cancel_resp.success:
            # The cancel was refused, so the broker's book disagrees with our
            # "still resting, unfilled" belief. Only a FOUND re-query settles it.
            fully_filled = refreshed.found and filled_qty >= order.quantity
            unknown = not refreshed.found
            if unknown:
                logger.warning(
                    "futures cancel rejected AND fill state unresolved "
                    "(order_no=%s code=%s cancel_msg=%s requery=%s): order may "
                    "be resting or filled at the broker",
                    order_no,
                    order.code,
                    cancel_resp.message,
                    refreshed.outcome.value,
                )
            elif filled_qty > 0:
                logger.warning(
                    "futures cancel rejected because the order had filled "
                    "(order_no=%s code=%s filled_qty=%s): reporting the true "
                    "fill instead of a flat book",
                    order_no,
                    order.code,
                    filled_qty,
                )
            return OrderResponse(
                success=fully_filled,
                order_no=order_no,
                message=(
                    f"Futures fill timeout and cancel failed: {cancel_resp.message}"
                ),
                filled_qty=filled_qty,
                filled_price=filled_price,
                venue=venue,
                broker_msg_cd=cancel_resp.broker_msg_cd,
                fill_state_unknown=unknown,
            )

        return OrderResponse(
            success=False,
            order_no=order_no,
            message=f"Futures unfilled order cancelled: {cancel_resp.message}",
            filled_qty=filled_qty,
            filled_price=filled_price,
            venue=venue,
            # A successful cancel establishes only "not FULLY filled" — it does
            # NOT establish "filled nothing". `cancel_qty` above is the full
            # order quantity whenever no poll ever answered, so this cancel may
            # have removed the remainder of a PARTIAL fill while `filled_qty`
            # still reads the 0 we started with. Reporting that 0 as measured
            # would be asserting more than the evidence supports, so the
            # quantity is unknown whenever the confirming re-query failed, or
            # whenever no poll ever measured a quantity and the re-query did
            # not supply one either.
            fill_state_unknown=(
                refreshed.query_failed
                or (
                    last_outcome is FillQueryOutcome.QUERY_FAILED
                    and not refreshed.found
                )
            ),
        )

    async def _inquire_futures_fill_status(
        self,
        *,
        order: OrderRequest,
        order_no: str,
        is_mock: bool,
        is_night: bool,
    ) -> _FuturesFillStatus:
        """Query futures order/fill status using KIS inquire-ccnl API.

        Returns a three-state outcome. A query we could not complete is
        reported as ``QUERY_FAILED``, never as an empty ``NOT_PRESENT``
        snapshot: the caller must be able to tell "the broker says there is no
        fill" apart from "the broker did not answer".
        """
        tr_id, path = self._resolve_futures_inquire_tr_id_and_path(
            is_mock=is_mock, is_night=is_night
        )
        headers = await self._build_auth_headers(tr_id=tr_id)
        if headers is None:
            logger.warning(
                "futures fill status query FAILED (no auth headers): "
                "order_no=%s code=%s tr_id=%s — fill state unknown",
                order_no,
                order.code,
                tr_id,
            )
            return _FuturesFillStatus(
                outcome=FillQueryOutcome.QUERY_FAILED,
                order_no=order_no,
                order_qty=order.quantity,
            )

        today = datetime.now(KST).date()
        query_dates = [today, today - timedelta(days=1)]
        target_odno = _normalize_odno(order_no)
        any_query_failed = False

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
            try:
                data, status = await self._request_json(
                    "GET",
                    url,
                    headers=headers,
                    params=params,
                    rate_limit_timeout=float(
                        self.config.futures_fill_check_rate_limit_timeout_seconds
                    ),
                )
            except _TRANSPORT_ERRORS as exc:
                # A transport failure is definitionally an unanswered query, not
                # an exception for the caller to handle. Letting it propagate
                # unwound the whole fill/cancel path, taking the D-2 re-query
                # and the "may still be resting" diagnostics with it.
                any_query_failed = True
                logger.warning(
                    "futures fill status query FAILED (transport): order_no=%s "
                    "code=%s date=%s err=%s — fill state unknown, NOT 'unfilled'",
                    order_no,
                    order.code,
                    order_date.strftime("%Y%m%d"),
                    exc,
                )
                continue
            if status != 200 or data.get("rt_cd") != "0":
                any_query_failed = True
                logger.warning(
                    "futures fill status query FAILED: order_no=%s code=%s "
                    "date=%s http=%s rt_cd=%s msg_cd=%s msg=%s — fill state "
                    "unknown, NOT 'unfilled'",
                    order_no,
                    order.code,
                    order_date.strftime("%Y%m%d"),
                    status,
                    data.get("rt_cd"),
                    self._reject_msg_cd(data),
                    str(data.get("msg1", ""))[:200],
                )
                continue

            raw_rows = data.get("output1")
            rows: list[dict[str, Any]] = raw_rows if isinstance(raw_rows, list) else []
            self._warn_if_page_may_be_truncated(
                data=data,
                row_count=len(rows),
                order_no=order_no,
                order_date=order_date.strftime("%Y%m%d"),
            )
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
                    outcome=FillQueryOutcome.FOUND,
                    order_no=odno_raw or order_no,
                    order_qty=order_qty,
                    filled_qty=filled_qty,
                    remaining_qty=remaining_qty,
                    avg_fill_price=_to_float(row.get("avg_idx")),
                    rejected_qty=_to_int(row.get("rjct_qty")),
                    reject_reason=str(row.get("ingr_trad_rjct_rson_name", "")).strip(),
                )

        # Fail-closed: if ANY leg of the walk went unanswered we did not see the
        # whole picture, so the absence of the row is not evidence of no fill.
        return _FuturesFillStatus(
            outcome=(
                FillQueryOutcome.QUERY_FAILED
                if any_query_failed
                else FillQueryOutcome.NOT_PRESENT
            ),
            order_no=order_no,
            order_qty=order.quantity,
        )

    def _warn_if_page_may_be_truncated(
        self,
        *,
        data: dict[str, Any],
        row_count: int,
        order_no: str,
        order_date: str,
    ) -> None:
        """Flag a fill-status page that may have been cut off.

        This call site is a TARGETED lookup (``STRT_ODNO`` + ``PDNO`` +
        ``SORT_SQN=DS``) for the order just submitted, which is the highest
        ODNO and therefore row 1 — truncation is not expected here. What was
        missing is any way to NOTICE if that ever stopped holding, since the
        request sends empty continuation keys and the response's keys were
        never read. Detection only: a full continuation walk belongs at a
        call site that actually needs every row (see
        ``shared/kis/client.py::fetch_invest_opinion``).
        """
        continuation = str(
            data.get("ctx_area_nk200") or data.get("CTX_AREA_NK200") or ""
        ).strip()
        if not continuation:
            return
        page_size = int(self.config.futures_inquire_page_size)
        if row_count < page_size:
            return
        logger.warning(
            "futures fill status page may be TRUNCATED: order_no=%s date=%s "
            "rows=%d >= page_size=%d with a continuation key present — the "
            "targeted lookup no longer fits on page 1",
            order_no,
            order_date,
            row_count,
            page_size,
        )

    async def _cancel_futures_order(
        self,
        *,
        order_no: str,
        cancel_quantity: int,
        is_mock: bool,
        is_night: bool,
    ) -> OrderResponse:
        """Cancel futures order using order-rvsecncl API, with bounded retry.

        A cancel that fails once leaves the order RESTING at the broker, so a
        single attempt is not enough — the observed failure (broker-probe
        artifact P-8) was a throttle rejection that left order 0000003144 live.
        Retries are bounded by ``futures_cancel_max_attempts`` and are spent
        only on failures where a retry can plausibly change the answer:
        throttles, 5xx, 429 and transport errors. A deterministic business
        reject (e.g. "정정/취소할 수량이 없습니다") returns immediately — the
        caller re-queries the fill state instead of hammering the broker.
        """
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

        attempts = max(int(self.config.futures_cancel_max_attempts), 1)
        throttle_streak = 0
        made = 0
        failure = OrderResponse(success=False, message="Cancel not attempted")
        for attempt in range(attempts):
            made = attempt + 1
            try:
                data, status = await self._request_json(
                    "POST",
                    url,
                    headers=headers,
                    json=body,
                    rate_limiter=self._cancel_rate_limiter,
                )
            except _TRANSPORT_ERRORS as exc:
                # A transport failure must never unwind this loop: doing so
                # skipped the caller's re-query, left `fill_state_unknown`
                # unset, and suppressed the "may still be resting" ERROR — D-5
                # with its diagnostics removed. Treat it as a retryable failure.
                failure = OrderResponse(
                    success=False,
                    message=f"[TRANSPORT] cancel request failed: {exc}",
                )
                logger.warning(
                    "futures cancel attempt %d/%d failed (transport): "
                    "order_no=%s err=%s retryable=True",
                    attempt + 1,
                    attempts,
                    order_no,
                    exc,
                )
                if attempt >= attempts - 1:
                    break
                throttle_streak = 0
                await asyncio.sleep(
                    float(self.config.futures_cancel_retry_delay_seconds)
                )
                continue

            if status == 200 and data.get("rt_cd") == "0":
                return OrderResponse(
                    success=True,
                    order_no=data.get("output", {}).get("ODNO"),
                    message=data.get("msg1", "Cancel success"),
                )

            msg_cd = self._reject_msg_cd(data)
            failure = OrderResponse(
                success=False,
                message=f"[{data.get('rt_cd')}] {data.get('msg1', 'Cancel failed')}",
                broker_msg_cd=msg_cd,
            )
            throttled = msg_cd == KIS_THROTTLE_MSG_CD
            retryable = throttled or status >= 500 or status == 429
            logger.warning(
                "futures cancel attempt %d/%d failed: order_no=%s http=%s "
                "msg_cd=%s msg=%s retryable=%s",
                attempt + 1,
                attempts,
                order_no,
                status,
                msg_cd or "-",
                str(data.get("msg1", ""))[:200],
                retryable,
            )
            if not retryable or attempt >= attempts - 1:
                break

            if throttled:
                throttle_streak += 1
                delay = self._throttle_backoff_delay(throttle_streak)
            else:
                throttle_streak = 0
                delay = float(self.config.futures_cancel_retry_delay_seconds)
            await asyncio.sleep(delay)

        logger.error(
            "futures cancel FAILED after %d/%d attempt(s): order_no=%s may still "
            "be resting at the broker (%s)",
            made,
            attempts,
            order_no,
            failure.message,
        )
        return failure

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
        rate_limiter: RedisRateLimiter | None = None,
        rate_limit_timeout: float | None = None,
    ) -> tuple[dict[str, Any], int]:
        """Execute HTTP request and parse JSON body.

        Args:
            rate_limiter: Bucket to acquire from. Defaults to the executor's
                main bucket; the cancel path passes its own so a safety cancel
                cannot queue behind the fill polls of the order it cancels.
            rate_limit_timeout: Acquire timeout override. Defaults to
                ``config.rate_limit_timeout``.
        """
        limiter = rate_limiter if rate_limiter is not None else self._rate_limiter
        if limiter:
            timeout = (
                self.config.rate_limit_timeout
                if rate_limit_timeout is None
                else rate_limit_timeout
            )
            try:
                await limiter.acquire(timeout=timeout)
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
            data, status = await retry_once_on_token_expiry(
                attempt,
                self.auth_manager,
                is_expired=lambda result: is_token_expired_error(result[0]),
            )
        except Exception as e:
            # Network/timeout reaching KIS = infra failure.
            _record_kis_api_outcome(is_error=True)
            logger.error(f"KIS request error ({method} {url}): {e}")
            raise
        # 5xx / 429 = KIS-side infra failure; any other response = KIS reachable.
        #
        # EGW00201 is the one exception: KIS returns it as HTTP 500, but it is a
        # business reject meaning "you paced yourself too fast" — the gateway
        # answered us. Counting our own pacing against the kill switch's
        # api_error_rate_5min signal would let a throttle burst force-flatten
        # live positions (config/kill_switch.yaml). Excluded per this function's
        # own contract: only KIS-side infra failures count.
        throttled = _is_throttle_response(data)
        self._record_throttle_outcome(throttled=throttled, method=method, url=url)
        _record_kis_api_outcome(
            is_error=(status >= 500 or status == 429) and not throttled
        )
        return data, status

    def _record_throttle_outcome(
        self, *, throttled: bool, method: str, url: str
    ) -> None:
        """Track consecutive throttles so a throttle STORM is still visible.

        Excluding EGW00201 from ``api_error_rate_5min`` is right for a single
        throttle, but it fails open on a degraded gateway that answers
        EGW00201 to everything: the api-error signal would stay at 0 forever
        while no order — including a protective exit — can be placed. This
        counter is the distinct signal for that state, with its own
        config-driven threshold. It is a COUNT, not a rate.
        """
        if not throttled:
            self._throttle_streak = 0
            return

        self._throttle_streak += 1
        logger.warning(
            "KIS throttle (%s) on %s %s — excluded from the api-error signal "
            "(self-inflicted pacing, broker reachable); consecutive=%d",
            KIS_THROTTLE_MSG_CD,
            method,
            url,
            self._throttle_streak,
        )
        threshold = int(self.config.throttle_storm_alert_threshold)
        if self._throttle_streak >= threshold:
            logger.error(
                "KIS THROTTLE STORM: %d consecutive %s responses (threshold=%d) "
                "on %s — the gateway is refusing everything; order placement, "
                "including protective exits, is effectively down. This state is "
                "deliberately excluded from api_error_rate_5min, so THIS is the "
                "signal to alert on.",
                self._throttle_streak,
                KIS_THROTTLE_MSG_CD,
                threshold,
                url,
            )

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
    def _map_stock_order_type(order_type: str) -> str:
        """Map an internal order type to the KIS stock ``ORD_DVSN`` code.

        Args:
            order_type: Internal ``OrderType`` value ("00"/"01"/"02").

        Returns:
            The stock ``ORD_DVSN`` wire code.

        Raises:
            OrderExecutionError: The order type is not in the explicit table.
                There is no fallback on purpose — see the module-level note on
                the stock/futures "01" inversion.
        """
        code = _STOCK_ORD_DVSN.get(str(order_type))
        if code is None:
            known = sorted(_STOCK_ORD_DVSN)
            logger.error(
                "unknown order type refused (previously forwarded verbatim as "
                "ORD_DVSN): order_type=%r asset_class=stock known=%s",
                order_type,
                known,
            )
            raise OrderExecutionError(
                f"unknown order type {order_type!r} refused "
                f"(asset_class=stock, known={known})"
            )
        return code

    @staticmethod
    def _map_futures_order_type(order_type: str) -> str:
        """Map an internal order type to the KIS futures ``ORD_DVSN_CD`` code.

        Args:
            order_type: Internal ``OrderType`` value (stock code system) or a
                futures-native ``ORD_DVSN_CD``.

        Returns:
            The futures ``ORD_DVSN_CD`` wire code.

        Raises:
            OrderExecutionError: The order type is neither an internal order
                type nor a futures-native ``ORD_DVSN_CD``. The previous silent
                ``"01"`` fallback is removed: it made an unknown order type
                look like a valid 지정가 order on the futures wire, and the same
                literal means 시장가 on the stock wire.
        """
        key = str(order_type)
        if key in _FUTURES_ORD_DVSN_CD:
            return _FUTURES_ORD_DVSN_CD[key]
        if key in _FUTURES_ORD_DVSN_CD_NATIVE:
            return key
        known = sorted(set(_FUTURES_ORD_DVSN_CD) | _FUTURES_ORD_DVSN_CD_NATIVE)
        logger.error(
            "unknown order type refused (previously silently became "
            'ORD_DVSN_CD="01" = 지정가): order_type=%r asset_class=futures '
            "known=%s",
            order_type,
            known,
        )
        raise OrderExecutionError(
            f"unknown order type {order_type!r} refused "
            f"(asset_class=futures, known={known})"
        )

    @staticmethod
    def _futures_quote_type_codes(ord_dvsn_cd: str) -> tuple[str, str]:
        """Return ``(NMPR_TYPE_CD, KRX_NMPR_CNDT_CD)`` for a futures order type.

        Both fields are [필수] in the KIS futures order contract. Sending an
        empty string delegates the quote type and the TIF (IOC/FOK) semantics
        to an undocumented broker default; deriving them from ``ORD_DVSN_CD``
        keeps the wire value in agreement with the requested order type.

        Args:
            ord_dvsn_cd: Futures ``ORD_DVSN_CD`` wire code.

        Returns:
            ``(NMPR_TYPE_CD, KRX_NMPR_CNDT_CD)``.

        Raises:
            OrderExecutionError: ``ord_dvsn_cd`` is outside the KIS enumeration.
        """
        codes = _FUTURES_NMPR_CODES.get(str(ord_dvsn_cd))
        if codes is None:
            known = sorted(_FUTURES_NMPR_CODES)
            logger.error(
                "unknown ORD_DVSN_CD refused: ord_dvsn_cd=%r "
                "asset_class=futures known=%s",
                ord_dvsn_cd,
                known,
            )
            raise OrderExecutionError(
                f"unknown ORD_DVSN_CD {ord_dvsn_cd!r} refused "
                f"(asset_class=futures, known={known})"
            )
        return codes

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
