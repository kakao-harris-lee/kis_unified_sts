"""Order execution engine."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Optional

import aiohttp

from .config import ExecutionConfig, TradingMode
from .exceptions import RateLimitExceeded
from .models import OrderRequest, OrderResponse, OrderSide

if TYPE_CHECKING:
    from .rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)


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
        self.session: Optional[aiohttp.ClientSession] = None
        self._initialized = False

        # Rate limiter (optional, requires redis_url)
        self._rate_limiter: Optional[RedisRateLimiter] = None
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

        # Account parsing
        self.account_prefix = ""
        self.account_suffix = ""
        if config.account_no and len(config.account_no) >= 10:
            self.account_prefix = config.account_no[:8]
            self.account_suffix = config.account_no[8:10]

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
        mode = self.config.trading_mode

        # Compare against enum values (config uses use_enum_values=True)
        if mode == TradingMode.PAPER:
            return await self._simulate_order(order)
        elif mode == TradingMode.MOCK:
            return await self._send_kis_order(order, is_mock=True)
        elif mode == TradingMode.REAL:
            return await self._send_kis_order(order, is_mock=False)
        else:
            return OrderResponse(success=False, message=f"Unknown mode: {mode}")

    async def _simulate_order(self, order: OrderRequest) -> OrderResponse:
        """Simulate order for paper trading."""
        # Generate fake order number
        order_no = f"PAPER-{uuid.uuid4().hex[:8].upper()}"

        logger.info(
            f"[PAPER] Order simulated: {order.side} {order.code} "
            f"x{order.quantity} @ {order.price or 'MARKET'}"
        )

        return OrderResponse(
            success=True,
            order_no=order_no,
            message="Paper order simulated",
            filled_qty=order.quantity,
        )

    async def _send_kis_order(self, order: OrderRequest, is_mock: bool) -> OrderResponse:
        """Send order to KIS API."""
        if not self.auth_manager:
            return OrderResponse(success=False, message="Auth manager not configured")

        if not self.session:
            logger.warning(
                "OrderExecutor not initialized - calling initialize() now. "
                "For predictable latency, call initialize() during app startup."
            )
            await self.initialize()

        # Get auth headers
        headers = await self.auth_manager.get_auth_headers()

        # Determine TR code from config
        if order.side == OrderSide.BUY.value:
            tr_id = self.config.tr_code_buy_mock if is_mock else self.config.tr_code_buy_real
        else:
            tr_id = self.config.tr_code_sell_mock if is_mock else self.config.tr_code_sell_real

        headers["tr_id"] = tr_id

        # Build request body
        body = {
            "CANO": self.account_prefix,
            "ACNT_PRDT_CD": self.account_suffix,
            "PDNO": order.code,
            "ORD_DVSN": order.order_type,
            "ORD_QTY": str(order.quantity),
            "ORD_UNPR": str(int(order.price)) if order.price else "0",
        }

        # Send request using configured base URL
        base_url = self.config.kis_mock_base_url if is_mock else self.config.kis_real_base_url
        url = f"{base_url}/uapi/domestic-stock/v1/trading/order-cash"

        try:
            request_timeout = aiohttp.ClientTimeout(
                total=float(self.config.order_request_timeout_seconds)
            )
            async with self.session.post(
                url, headers=headers, json=body, timeout=request_timeout
            ) as response:
                data = await response.json()

                if response.status == 200 and data.get("rt_cd") == "0":
                    return OrderResponse(
                        success=True,
                        order_no=data.get("output", {}).get("ODNO"),
                        message=data.get("msg1", "Success"),
                    )
                else:
                    return OrderResponse(
                        success=False,
                        message=f"[{data.get('rt_cd')}] {data.get('msg1', 'Unknown error')}",
                    )
        except Exception as e:
            logger.error(f"KIS order error: {e}")
            raise

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
