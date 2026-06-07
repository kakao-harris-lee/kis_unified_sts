"""Live exit executor for the decoupled futures order_router (F-6).

On a PseudoOCO stop/target/expiry trigger, place a REAL market order to flatten
the position via the KIS adapter. Guard-blocked: when live trading is suspended
(``futures:live:suspended`` or ``futures_live.enabled=false``) the exit is NOT
placed and ``flatten`` returns ``None`` so PseudoOCO keeps the handle active for
the next poll. (Operator-accepted trade-off: no auto-flatten while suspended —
emergency flatten is the kill_switch daemon's job. See the F-6 design doc §3.4.)
"""

from __future__ import annotations

import logging
from typing import Any

from shared.execution.passive_maker import Fill

logger = logging.getLogger(__name__)

# Market exits should fill near-immediately; this bounds the await.
_EXIT_FILL_TIMEOUT_SECONDS = 5.0


class LiveExitExecutor:
    """Place real market flatten orders for triggered brackets (guard-blocked)."""

    def __init__(self, *, kis_client: Any, live_mode_guard: Any, redis: Any) -> None:
        self._kis = kis_client
        self._guard = live_mode_guard
        self._redis = redis

    async def flatten(
        self,
        *,
        symbol: str,
        side: str,
        quantity: int,
        requested_price: float,  # noqa: ARG002 — audit price; market order ignores it
        now_ms: int,  # noqa: ARG002 — part of the close-executor interface
    ) -> Fill | None:
        if self._guard is not None and await self._guard.is_live_suspended(self._redis):
            logger.warning(
                "live exit blocked (suspended) symbol=%s side=%s qty=%d",
                symbol,
                side,
                quantity,
            )
            return None
        order_id = await self._kis.place_futures_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type="market",
            price=None,
        )
        fill: Fill | None = await self._kis.await_fill(
            order_id, timeout_seconds=_EXIT_FILL_TIMEOUT_SECONDS
        )
        if fill is None:
            logger.error(
                "live exit order %s not filled within %.1fs symbol=%s",
                order_id,
                _EXIT_FILL_TIMEOUT_SECONDS,
                symbol,
            )
        return fill
