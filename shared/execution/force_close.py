"""Force-close — the three whitelisted market-order paths.

Phase 4 Task 8 — spec §4.3 lists the only conditions under which a market
order is permitted. Anything else routes through the passive maker.

  1. ``close_for_valid_until_expiry`` — signal's ``valid_until`` elapsed,
     so the bracket can no longer be allowed to drift.
  2. ``close_for_eod`` — session-end approaching (default 15:10 KST,
     ahead of the 15:45 futures close), to flatten before close.
  3. ``close_for_kill_switch`` — kill-switch fired (Task 13), immediate
     force-flat regardless of bracket state.

All three log fills with ``trade_role="force_close"`` + ``order_type="market"``.
The reason for the close is preserved in the OrderResult and emitted to
``stream:risk.event`` separately by the kill-switch / EOD scheduler — the
``order_fills`` row itself stays minimal.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from datetime import time as dt_time
from typing import Any
from zoneinfo import ZoneInfo

from shared.execution.fill_logger import FillLogger
from shared.execution.order_result import OrderResult
from shared.execution.tick_math import _compute_slippage_ticks

KST = ZoneInfo("Asia/Seoul")
DEFAULT_EOD_TIME = dt_time(15, 10)


@dataclass(frozen=True, slots=True)
class OpenPosition:
    signal_id: str
    symbol: str
    direction: str  # "long" | "short"
    quantity: int
    entry_price: float
    tick_size_points: float


def _opposite(direction: str) -> str:
    return "short" if direction == "long" else "long"


class ForceCloseExecutor:
    """Execute one of the three whitelisted market-order force-closes."""

    def __init__(
        self,
        *,
        kis_client: Any,
        fill_logger: FillLogger,
        eod_time: dt_time = DEFAULT_EOD_TIME,
        venue: str = "KRX",
    ) -> None:
        self.kis = kis_client
        self.fill_logger = fill_logger
        self.eod_time = eod_time
        self.venue = venue

    async def close_for_valid_until_expiry(
        self, *, position: OpenPosition, now_ms: int
    ) -> OrderResult:
        return await self._market_close(position=position, now_ms=now_ms)

    async def close_for_eod(
        self, *, position: OpenPosition, now_ms: int
    ) -> OrderResult:
        return await self._market_close(position=position, now_ms=now_ms)

    async def close_for_kill_switch(
        self, *, position: OpenPosition, reason: str, now_ms: int
    ) -> OrderResult:
        return await self._market_close(
            position=position, now_ms=now_ms, broker_error_code=reason
        )

    def is_eod(self, now: datetime) -> bool:
        """Return True if ``now`` is at or past the configured EOD time in KST.

        Naive datetimes are assumed to already be KST per project default
        (see ``CLAUDE.md`` on Asia/Seoul session boundaries).
        """
        kst_now = now if now.tzinfo is None else now.astimezone(KST)
        return kst_now.timetz().replace(tzinfo=None) >= self.eod_time

    async def _market_close(
        self,
        *,
        position: OpenPosition,
        now_ms: int,
        broker_error_code: str = "",
    ) -> OrderResult:
        closing_side = _opposite(position.direction)
        requested_at_ms = now_ms or int(time.time() * 1000)
        order_id = await self.kis.place_futures_order(
            symbol=position.symbol,
            side=closing_side,
            quantity=position.quantity,
            order_type="market",
            price=None,
        )
        fill = await self.kis.await_fill(order_id, 30)
        if fill is None:
            return OrderResult.error(
                reason="force_close_market_no_fill", order_id=order_id
            )

        slippage_ticks = _compute_slippage_ticks(
            requested=position.entry_price,
            filled=fill.price,
            direction=position.direction,
            tick_size=position.tick_size_points,
        )
        await self.fill_logger.log_fill(
            signal_id=position.signal_id,
            order_id=order_id,
            symbol=position.symbol,
            side=closing_side,
            order_type="market",
            requested_price=position.entry_price,
            filled_price=fill.price,
            tick_size_points=position.tick_size_points,
            slippage_ticks=slippage_ticks,
            quantity=position.quantity,
            requested_at_ms=requested_at_ms,
            filled_at_ms=fill.filled_at_ms,
            venue=self.venue,
            trade_role="force_close",
            broker_error_code=broker_error_code,
        )
        return OrderResult.filled(fill, slippage_ticks=slippage_ticks)
