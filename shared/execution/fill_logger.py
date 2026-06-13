"""Fan-out order fill events to Redis stream and RuntimeLedger.

Phase 4 Task 3 — mirrors :class:`shared.scoring.publisher.ScoredPublisher` so
the consumer-group invariant from Phase 2 carries forward unchanged: any
runtime ledger failure is re-raised so the caller can leave the source signal
message pending for redelivery rather than half-XACKing.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400  # Redis TTL policy — stream keys 24 h.


def _ms_to_utc_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()


class FillLogger:
    """Log every order fill to Redis stream plus optional RuntimeLedger.

    Args:
        redis: ``redis.asyncio`` (or ``fakeredis``) connection.
        archive_client: Ignored legacy archive hook.
        runtime_ledger: Optional durable runtime ledger.
        stream: Target Redis stream key (default ``stream:order.fill``).
        maxlen: ``MAXLEN ~`` cap passed to ``XADD`` to bound stream size.
        batch_size: Ignored legacy batch size.
        asset_class: Optional asset-class tag recorded in the runtime ledger.
    """

    def __init__(
        self,
        *,
        redis: Any,
        archive_client: Any | None = None,
        runtime_ledger: Any | None = None,
        stream: str = "stream:order.fill",
        maxlen: int = 10_000,
        batch_size: int = 10,
        asset_class: str | None = None,
        **legacy_kwargs: Any,
    ) -> None:
        self.redis = redis
        _ = archive_client, batch_size, legacy_kwargs
        self.runtime_ledger = runtime_ledger
        self.stream = stream
        self.maxlen = maxlen
        self.asset_class = asset_class

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
        strategy: str = "",
    ) -> None:
        """Publish to ``stream:order.fill`` and persist to RuntimeLedger if enabled.

        ``latency_ms = max(filled_at_ms - requested_at_ms, 0)`` — clamped at
        zero to absorb clock skew between order-place and fill-event sources.
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
            "strategy": strategy,
        }
        await self.redis.xadd(self.stream, fields, maxlen=self.maxlen, approximate=True)
        await self.redis.expire(self.stream, _STREAM_TTL_SECONDS)
        if self.runtime_ledger is not None:
            try:
                import asyncio

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
                        strategy=strategy,
                    ),
                )
            except Exception:
                logger.exception("runtime ledger fill persist failed: %s", order_id)
                raise

    async def flush(self) -> None:
        """Compatibility no-op."""
        return None

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
        strategy: str = "",
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
            "strategy": strategy,
            "side": side,
            "order_type": order_type,
            "requested_price": float(requested_price),
            "filled_price": float(filled_price),
            "price": float(filled_price),
            "tick_size_points": float(tick_size_points),
            "slippage_ticks": float(slippage_ticks),
            "quantity": int(quantity),
            "requested_at": _ms_to_utc_iso(requested_at_ms),
            "filled_at": _ms_to_utc_iso(filled_at_ms),
            "requested_at_ms": int(requested_at_ms),
            "filled_at_ms": int(filled_at_ms),
            "latency_ms": int(latency_ms),
            "venue": venue,
            "trade_role": trade_role,
            "broker_error_code": broker_error_code,
        }
