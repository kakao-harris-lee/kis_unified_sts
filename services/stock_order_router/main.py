"""Stock order-router consumer-group daemon (M4-O, flag-gated, shadow-first).

Reads filtered stock signals from ``signal.final.stock.shadow``, paper-executes
via VirtualBroker (slippage modeled), logs the fill to ``order.fill.stock.shadow``
+ RuntimeLedger, and records the open position to the ``trading:stock:positions``
hash (read by M4-R OpenPositionFilter; consumed later by M4-X exit).

KRX-only (no ATS this increment); share-based sizing (no ContractSpec); no
PseudoOCO bracket (stock has no entry-time stop/target — M4-X owns exit).

Error taxonomy:
- Parse error        -> XACK (poison-pill drop)
- Broker raises      -> NO XACK (retry)
- Fill logging raises-> NO XACK
"""

from __future__ import annotations

import json
import logging
import math
import time
from typing import Any

from services.stock_risk_filter.codec import stock_signal_from_stream_fields
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker
from shared.paper.models import OrderSide, OrderType
from shared.streaming.stage import StreamStage

logger = logging.getLogger(__name__)


def _resolve_quantity(*, base_quantity: int, size_multiplier: float) -> int:
    """Scale base share quantity by size_multiplier; floor at 1 (never zero)."""
    scaled = int(math.floor(base_quantity * size_multiplier))
    return max(scaled, 1)


class StockOrderRouterDaemon(StreamStage):
    """Paper-execute stock entries and record open positions."""

    def __init__(
        self,
        *,
        redis: Any,
        broker: VirtualBroker,
        fill_logger: FillLogger,
        final_stream: str,
        consumer_group: str,
        worker_id: str,
        positions_key: str,
        xread_block_ms: int,
        batch_size: int,
    ) -> None:
        super().__init__(
            redis=redis,
            input_stream=final_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=0.5,
        )
        self.broker = broker
        self.fill_logger = fill_logger
        self.positions_key = positions_key

    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]  # noqa: ARG002
    ) -> bool:
        try:
            signal_id, signal = stock_signal_from_stream_fields(fields)
            size_multiplier = float(
                fields.get(b"size_multiplier", b"1.0").decode(errors="replace") or 1.0
            )
        except Exception:
            logger.exception("Unparseable stock final signal; ACK as poison-pill")
            return True  # poison-pill: consume

        quantity = _resolve_quantity(
            base_quantity=signal.quantity, size_multiplier=size_multiplier
        )

        try:
            order = await self.broker.submit_order(
                symbol=signal.code,
                side=OrderSide.BUY,
                quantity=quantity,
                price=signal.price,
                order_type=OrderType.MARKET,
                market_price=signal.price,
            )
        except Exception:
            logger.exception("broker raised signal_id=%s; leaving pending", signal_id)
            return False

        if not order.filled:
            logger.info(
                "stock paper order not filled signal_id=%s reason=%s",
                signal_id,
                order.rejection_reason,
            )
            return True  # final state, consumed

        filled_price = float(order.fill_price or signal.price)
        now_ms = int(time.time() * 1000)
        slippage = abs(filled_price - signal.price)

        try:
            await self.fill_logger.log_fill(
                signal_id=signal_id,
                order_id=order.order_id,
                symbol=signal.code,
                side="BUY",
                order_type="market",
                requested_price=signal.price,
                filled_price=filled_price,
                tick_size_points=0.0,
                slippage_ticks=slippage,
                quantity=quantity,
                requested_at_ms=now_ms,
                filled_at_ms=now_ms,
                venue="KRX",
                trade_role="entry",
            )
        except Exception:
            logger.exception(
                "fill logging failed signal_id=%s; leaving pending", signal_id
            )
            return False

        # Record open position (read by M4-R OpenPositionFilter; M4-X consumes).
        try:
            await self.redis.hset(
                self.positions_key,
                signal.code,
                json.dumps(
                    {
                        "code": signal.code,
                        "entry_price": filled_price,
                        "quantity": quantity,
                        "opened_at_ms": now_ms,
                        "state": "SURVIVAL",
                        "signal_id": signal_id,
                    }
                ),
            )
        except Exception:
            # Best-effort: the fill is already published; do not retry the order.
            logger.exception(
                "position record failed signal_id=%s code=%s", signal_id, signal.code
            )

        return True
