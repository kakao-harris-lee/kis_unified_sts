"""Fan-out order fill events to Redis stream plus optional ClickHouse mirror.

Phase 4 Task 3 — mirrors :class:`shared.scoring.publisher.ScoredPublisher` so
the consumer-group invariant from Phase 2 carries forward unchanged: any
When the optional ClickHouse mirror is enabled, failures are re-raised so the
caller can leave the source signal message pending for redelivery rather than
half-XACKing.

Schema source: ``infra/clickhouse/migrations/V3__create_order_fills.sql`` and
``docs/plans/2026-04-20-futures-paradigm-phase4-execution.md`` §5.1/§5.2.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400  # Redis TTL policy — stream keys 24 h.

_CH_INSERT = (
    "INSERT INTO kospi.order_fills "
    "(signal_id, order_id, symbol, side, order_type, "
    "requested_price, filled_price, tick_size_points, slippage_ticks, "
    "quantity, requested_at, filled_at, latency_ms, venue, trade_role, "
    "broker_error_code) VALUES"
)


def _ms_to_naive_utc(ms: int) -> datetime:
    """Convert epoch-ms to a tz-naive UTC datetime for ``aiochclient``."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).replace(tzinfo=None)


class FillLogger:
    """Log every order fill to Redis stream plus optional ClickHouse buffer.

    Args:
        redis: ``redis.asyncio`` (or ``fakeredis``) connection.
        ch_client: Optional ``aiochclient`` :class:`AsyncClickHouseClient` mirror.
        runtime_ledger: Optional durable runtime ledger. This is the primary
            persistence path when the ClickHouse mirror is disabled.
        stream: Target Redis stream key (default ``stream:order.fill``).
        maxlen: ``MAXLEN ~`` cap passed to ``XADD`` to bound stream size.
        ch_batch_size: Rows accumulated before flushing to CH (spec §5.2 = 10).
        asset_class: Optional asset-class tag recorded in the runtime ledger.
    """

    def __init__(
        self,
        *,
        redis: Any,
        ch_client: Any,
        runtime_ledger: Any | None = None,
        stream: str = "stream:order.fill",
        maxlen: int = 10_000,
        ch_batch_size: int = 10,
        asset_class: str | None = None,
    ) -> None:
        self.redis = redis
        self.ch = ch_client
        self.runtime_ledger = runtime_ledger
        self.stream = stream
        self.maxlen = maxlen
        self.ch_batch_size = ch_batch_size
        self.asset_class = asset_class
        self._mirror_enabled = ch_client is not None and ch_batch_size > 0
        self._buffer: list[tuple] = []
        self._lock = asyncio.Lock()

    async def log_fill(
        self,
        *,
        signal_id: str,
        order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        requested_price: float,
        filled_price: float,
        tick_size_points: float,
        slippage_ticks: float,
        quantity: int,
        requested_at_ms: int,
        filled_at_ms: int,
        venue: str,
        trade_role: str,
        broker_error_code: str = "",
    ) -> None:
        """Publish to ``stream:order.fill`` and enqueue for CH batch insert.

        ``latency_ms = max(filled_at_ms - requested_at_ms, 0)`` — clamped at
        zero to absorb clock skew between order-place and fill-event sources.
        ``UInt32`` in CH cannot represent negatives, so this is also a
        schema-safety guard.
        """
        latency_ms = max(filled_at_ms - requested_at_ms, 0)

        fields: dict[str, str] = {
            "signal_id": signal_id,
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "requested_price": str(requested_price),
            "filled_price": str(filled_price),
            "tick_size_points": str(tick_size_points),
            "slippage_ticks": str(slippage_ticks),
            "quantity": str(quantity),
            "requested_at_ms": str(requested_at_ms),
            "filled_at_ms": str(filled_at_ms),
            "latency_ms": str(latency_ms),
            "venue": venue,
            "trade_role": trade_role,
            "broker_error_code": broker_error_code,
        }
        await self.redis.xadd(self.stream, fields, maxlen=self.maxlen, approximate=True)
        await self.redis.expire(self.stream, _STREAM_TTL_SECONDS)
        if self.runtime_ledger is not None:
            try:
                await asyncio.to_thread(
                    self.runtime_ledger.record_fill,
                    self._runtime_ledger_payload(
                        signal_id=signal_id,
                        order_id=order_id,
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        requested_price=requested_price,
                        filled_price=filled_price,
                        tick_size_points=tick_size_points,
                        slippage_ticks=slippage_ticks,
                        quantity=quantity,
                        requested_at_ms=requested_at_ms,
                        filled_at_ms=filled_at_ms,
                        latency_ms=latency_ms,
                        venue=venue,
                        trade_role=trade_role,
                        broker_error_code=broker_error_code,
                    ),
                )
            except Exception:
                logger.exception("runtime ledger fill persist failed: %s", order_id)
                raise
        if not self._mirror_enabled:
            return

        row = (
            signal_id,
            order_id,
            symbol,
            side,
            order_type,
            float(requested_price),
            float(filled_price),
            float(tick_size_points),
            float(slippage_ticks),
            int(quantity),
            _ms_to_naive_utc(requested_at_ms),
            _ms_to_naive_utc(filled_at_ms),
            int(latency_ms),
            venue,
            trade_role,
            broker_error_code,
        )
        async with self._lock:
            self._buffer.append(row)
            should_flush = len(self._buffer) >= self.ch_batch_size

        if should_flush:
            await self.flush()

    async def flush(self) -> None:
        """Flush buffered rows to ClickHouse when the optional mirror is enabled.

        Same rationale as :class:`ScoredPublisher.flush` when enabled:
        swallowing a CH error would XADD-succeed + CH-fail + caller-XACK.
        """
        if not self._mirror_enabled:
            return
        async with self._lock:
            if not self._buffer:
                return
            rows = self._buffer
            self._buffer = []
        try:
            await self.ch.execute(_CH_INSERT, rows)
        except Exception:
            logger.exception(
                "order_fills flush failed; %d rows pending redelivery", len(rows)
            )
            raise

    def _runtime_ledger_payload(
        self,
        *,
        signal_id: str,
        order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        requested_price: float,
        filled_price: float,
        tick_size_points: float,
        slippage_ticks: float,
        quantity: int,
        requested_at_ms: int,
        filled_at_ms: int,
        latency_ms: int,
        venue: str,
        trade_role: str,
        broker_error_code: str,
    ) -> dict[str, Any]:
        fill_id = f"fill:{order_id}:{trade_role}:{filled_at_ms}"
        return {
            "id": fill_id,
            "idempotency_key": fill_id,
            "fill_id": fill_id,
            "signal_id": signal_id,
            "order_id": order_id,
            "asset_class": self.asset_class,
            "symbol": symbol,
            "code": symbol,
            "side": side,
            "order_type": order_type,
            "requested_price": float(requested_price),
            "filled_price": float(filled_price),
            "price": float(filled_price),
            "tick_size_points": float(tick_size_points),
            "slippage_ticks": float(slippage_ticks),
            "quantity": int(quantity),
            "requested_at": _ms_to_naive_utc(requested_at_ms).isoformat(),
            "filled_at": _ms_to_naive_utc(filled_at_ms).isoformat(),
            "requested_at_ms": int(requested_at_ms),
            "filled_at_ms": int(filled_at_ms),
            "latency_ms": int(latency_ms),
            "venue": venue,
            "trade_role": trade_role,
            "broker_error_code": broker_error_code,
        }
