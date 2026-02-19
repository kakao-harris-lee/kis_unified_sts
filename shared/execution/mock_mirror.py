"""Mock account mirror — fire-and-forget mirroring of paper trades to KIS mock server."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class MockAccountMirror:
    """Mirror paper trades to a KIS mock (모의투자) account.

    All public methods swallow exceptions so that mirror failures
    never affect the paper-trading main loop.
    """

    def __init__(self, asset_class: str = "stock"):
        self.asset_class = asset_class
        self._executor = None  # OrderExecutor | None
        self._initialized = False

    async def initialize(self) -> bool:
        """Connect to the KIS mock server. Returns True on success."""
        try:
            from shared.kis.auth import KISAuthConfig, KISAuthManager

            from .config import ExecutionConfig
            from .executor import OrderExecutor

            if self.asset_class == "stock":
                app_key = os.getenv("KIS_STOCK_APP_KEY", os.getenv("KIS_APP_KEY", ""))
                app_secret = os.getenv("KIS_STOCK_APP_SECRET", os.getenv("KIS_APP_SECRET", ""))
                account_no = os.getenv("KIS_STOCK_ACCOUNT_NO", os.getenv("KIS_ACCOUNT_NO", ""))
            else:
                logger.info("MockAccountMirror: futures mock mirroring not yet supported")
                return False

            if not app_key or not app_secret or not account_no:
                logger.warning(
                    "MockAccountMirror: missing credentials "
                    "(KIS_STOCK_APP_KEY / KIS_STOCK_APP_SECRET / KIS_STOCK_ACCOUNT_NO)"
                )
                return False

            auth_config = KISAuthConfig(
                app_key=app_key,
                app_secret=app_secret,
                is_real=False,  # 모의투자
            )
            auth_manager = KISAuthManager(auth_config)

            exec_cfg = ExecutionConfig(
                trading_mode="MOCK",
                account_no=account_no,
            )

            self._executor = OrderExecutor(config=exec_cfg, auth_manager=auth_manager)
            await self._executor.initialize()
            self._initialized = True
            logger.info("MockAccountMirror initialized (mock server)")
            return True

        except Exception:
            logger.exception("MockAccountMirror: initialization failed")
            self._initialized = False
            return False

    async def mirror_entry(
        self,
        code: str,
        side: str,
        quantity: int,
        price: float | None = None,
    ) -> None:
        """Mirror an entry order (fire-and-forget)."""
        await self._mirror_order(code, side, quantity, price, label="entry")

    async def mirror_exit(
        self,
        code: str,
        side: str,
        quantity: int,
        price: float | None = None,
    ) -> None:
        """Mirror an exit order (fire-and-forget)."""
        await self._mirror_order(code, side, quantity, price, label="exit")

    async def _mirror_order(
        self,
        code: str,
        side: str,
        quantity: int,
        _price: float | None,
        label: str,
    ) -> None:
        """Send one order to the mock account, logging success or failure."""
        if not self._initialized or self._executor is None:
            return

        try:
            from .models import OrderRequest, OrderSide, OrderType

            order = OrderRequest(
                code=code,
                side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=quantity,
                price=None,  # 시장가
            )
            response = await self._executor.execute_order(order)

            if response.success:
                tr_id = (
                    self._executor.config.tr_code_buy_mock
                    if side.upper() == "BUY"
                    else self._executor.config.tr_code_sell_mock
                )
                logger.info(
                    f"MockAccountMirror: {label} mirrored {tr_id} "
                    f"{code} x{quantity} -> order_no={response.order_no}"
                )
            else:
                logger.warning(
                    f"MockAccountMirror: {label} mirror failed "
                    f"{code} x{quantity} — {response.message}"
                )
        except Exception:
            logger.exception(f"MockAccountMirror: {label} mirror exception {code}")

    async def cleanup(self) -> None:
        """Release resources."""
        if self._executor is not None:
            try:
                await self._executor.cleanup()
            except Exception:
                logger.exception("MockAccountMirror: cleanup error")
            self._executor = None
        self._initialized = False
