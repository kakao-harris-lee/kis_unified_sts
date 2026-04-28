"""Batched writer for ``kospi.signals_all``.

Phase 3 persists every (candidate, layer_result) pair — rejected and accepted
alike — so the backtest can be replayed against different filter configurations
without re-running Setup logic.

Lessons carried from Phase 1/2:
- tz-aware datetimes are stripped to naive before sending to
  ``DateTime64(3, 'UTC')`` (aiochclient otherwise serializes with ``+00:00``).
- CH failures are logged and **re-raised** (no silent swallow) so the caller
  can decide whether to abort the run.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC
from typing import Any

from shared.decision.signal import Signal
from shared.risk.layer import LayerResult

logger = logging.getLogger(__name__)

_INSERT_SQL = (
    "INSERT INTO kospi.signals_all "
    "(signal_id, generated_at, setup_type, direction, entry_price, stop_loss, "
    "take_profit, confidence, executed, skip_reason, reason_tags) VALUES"
)


class SignalsAllWriter:
    """Buffers rows in memory and flushes on size-trigger or explicit call."""

    def __init__(
        self,
        ch_client: Any,
        *,
        batch_size: int = 50,
    ):
        self.ch = ch_client
        self.batch_size = batch_size
        self._buffer: list[tuple] = []
        self._lock = asyncio.Lock()

    async def enqueue(
        self,
        signal: Signal,
        layer_result: LayerResult,
        *,
        executed: bool = False,
        signal_id: str | None = None,
    ) -> None:
        """Buffer one signal+result row for ``kospi.signals_all``.

        Args:
            signal_id: When the caller has a stable identifier (Phase 4 streaming
                pipeline: the UUID minted by ``decision_engine`` and threaded
                through ``risk_filter`` → ``order_router`` → ``order_fills``),
                pass it through so spec §5.3 ``signals_all JOIN order_fills ON
                signal_id`` actually matches. Backtest harness callers without
                a pre-existing id fall through to a fresh ``uuid4`` per row.
        """
        generated_at = signal.generated_at
        if generated_at.tzinfo is not None:
            generated_at = generated_at.astimezone(UTC).replace(tzinfo=None)

        row = (
            signal_id if signal_id is not None else str(uuid.uuid4()),
            generated_at,
            signal.setup_type,
            signal.direction,
            signal.entry_price,
            signal.stop_loss,
            signal.take_profit,
            signal.confidence,
            1 if executed else 0,
            layer_result.skip_reason or "",
            list(signal.reason_tags),
        )
        async with self._lock:
            self._buffer.append(row)
            should_flush = len(self._buffer) >= self.batch_size
        if should_flush:
            await self.flush()

    async def flush(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            rows = self._buffer
            self._buffer = []
        try:
            await self.ch.execute(_INSERT_SQL, rows)
        except Exception:
            logger.exception(
                "signals_all flush failed; %d rows pending redelivery", len(rows)
            )
            raise
