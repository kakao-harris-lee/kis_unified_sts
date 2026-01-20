"""Order execution engine."""
import asyncio
import logging
import uuid
from typing import Optional

import aiohttp

from .config import ExecutionConfig, TradingMode
from .models import OrderRequest, OrderResponse, OrderSide

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

        # Account parsing
        self.account_prefix = ""
        self.account_suffix = ""
        if config.account_no and len(config.account_no) >= 10:
            self.account_prefix = config.account_no[:8]
            self.account_suffix = config.account_no[8:10]

    async def initialize(self) -> None:
        """Initialize HTTP session."""
        if not self._initialized:
            self.session = aiohttp.ClientSession()
            self._initialized = True
            logger.debug("OrderExecutor initialized")

    async def cleanup(self) -> None:
        """Cleanup HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
        self._initialized = False
        logger.debug("OrderExecutor cleaned up")

    async def execute_order(self, order: OrderRequest) -> OrderResponse:
        """Execute order with retry logic.

        Args:
            order: Order request

        Returns:
            OrderResponse with result
        """
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

        if mode == TradingMode.PAPER.value:
            return await self._simulate_order(order)
        elif mode == TradingMode.MOCK.value:
            return await self._send_kis_order(order, is_mock=True)
        elif mode == TradingMode.REAL.value:
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
            await self.initialize()

        # Get auth headers
        headers = await self.auth_manager.get_auth_headers()

        # Determine TR code
        if order.side == OrderSide.BUY.value:
            tr_id = "VTTC0802U" if is_mock else "TTTC0802U"
        else:
            tr_id = "VTTC0801U" if is_mock else "TTTC0801U"

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

        # Send request
        base_url = "https://openapivts.koreainvestment.com:29443" if is_mock else "https://openapi.koreainvestment.com:9443"
        url = f"{base_url}/uapi/domestic-stock/v1/trading/order-cash"

        try:
            async with self.session.post(url, headers=headers, json=body) as response:
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
