"""Stock risk-filter consumer-group daemon (M4-R, flag-gated, shadow-first).

Reads stock candidates from ``signal.candidate.stock.shadow`` (M4-P output),
runs the 8-filter RiskFilterLayer with stock config + session windows, and on
pass re-emits all candidate fields + size_multiplier + filtered_at_ms to
``signal.final.stock.shadow``.

Error taxonomy (mirrors services.risk_filter.main):
- Parse error            -> XACK (poison-pill drop)
- Filter eval raises     -> NO XACK (leave pending)
- final XADD raises      -> NO XACK
"""

from __future__ import annotations

import logging
import time
from typing import Any

from services.stock_risk_filter.codec import (
    decode_fields,
    stock_signal_from_stream_fields,
)
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState
from shared.streaming.stage import StreamStage

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400


class StockRiskFilterDaemon(StreamStage):
    """Apply the 8-filter RiskFilterLayer to every stock candidate."""

    def __init__(
        self,
        *,
        redis: Any,
        layer: RiskFilterLayer,
        runtime_state: RuntimeRiskState,
        candidate_stream: str,
        final_stream: str,
        consumer_group: str,
        worker_id: str,
        final_maxlen: int,
        xread_block_ms: int,
        batch_size: int,
    ) -> None:
        super().__init__(
            redis=redis,
            input_stream=candidate_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=0.5,
        )
        self.layer = layer
        self.runtime_state = runtime_state
        self.final_stream = final_stream
        self.final_maxlen = final_maxlen

    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]  # noqa: ARG002
    ) -> bool:
        try:
            signal_id, signal = stock_signal_from_stream_fields(fields)
            passthrough = decode_fields(fields)
        except Exception:
            logger.exception("Unparseable stock candidate; ACKing as poison-pill")
            return True  # poison-pill: consume

        try:
            snapshot = await self.runtime_state.snapshot()
            result = self.layer.evaluate(signal, snapshot)  # type: ignore[arg-type]  # StockRiskSignal is duck-typed: filters only read .symbol + .generated_at
        except Exception:
            logger.exception(
                "Stock filter eval failed signal_id=%s; leaving pending", signal_id
            )
            return False

        if not result.passed:
            logger.info(
                "Stock candidate rejected signal_id=%s reason=%s",
                signal_id,
                result.skip_reason,
            )
            return True  # rejected: consume (no final)

        try:
            fields_out = dict(passthrough)
            fields_out["size_multiplier"] = str(result.size_multiplier)
            fields_out["filtered_at_ms"] = str(int(time.time() * 1000))
            await self.redis.xadd(
                self.final_stream,
                fields_out,
                maxlen=self.final_maxlen,
                approximate=True,
            )
            await self.redis.expire(self.final_stream, _STREAM_TTL_SECONDS)
        except Exception:
            logger.exception(
                "Stock final XADD failed signal_id=%s; leaving pending", signal_id
            )
            return False

        return True
