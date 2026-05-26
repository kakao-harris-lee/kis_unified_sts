"""Redis-backed Strategy Lab state with in-memory fallback."""

from __future__ import annotations

import json
import logging
import time
from typing import TypeVar

from pydantic import BaseModel

from shared.strategy_lab.config import (
    get_lab_position_ttl_seconds,
    get_lab_ttl_seconds,
)
from shared.strategy_lab.schema import (
    LabSignal,
    OrderTicket,
    PaperOrder,
    PaperPosition,
    SignalStatus,
)

logger = logging.getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)

_MEMORY: dict[str, tuple[str, float]] = {}


def _now() -> float:
    return time.time()


def reset_memory_store() -> None:
    """Clear fallback state for tests."""
    _MEMORY.clear()


class StrategyLabStore:
    """Persist short-lived Strategy Lab state.

    Redis DB selection is owned by ``shared.streaming.client.RedisClient`` and
    defaults to DB 1. Every key written by this store has an explicit TTL.
    """

    def __init__(self, *, use_redis: bool = True) -> None:
        self.use_redis = use_redis
        self.ttl_seconds = get_lab_ttl_seconds()
        self.position_ttl_seconds = get_lab_position_ttl_seconds()

    def store_signal(self, signal: LabSignal) -> LabSignal:
        self._set(self._signal_key(signal.signal_id), signal, self.ttl_seconds)
        self._append_index(
            self._draft_signals_key(signal.draft_id),
            signal.signal_id,
            self.ttl_seconds,
        )
        return signal

    def get_signal(self, signal_id: str) -> LabSignal | None:
        return self._get_model(self._signal_key(signal_id), LabSignal)

    def update_signal(self, signal: LabSignal) -> LabSignal:
        self._set(self._signal_key(signal.signal_id), signal, self.ttl_seconds)
        return signal

    def store_ticket(self, ticket: OrderTicket) -> OrderTicket:
        self._set(self._ticket_key(ticket.ticket_id), ticket, self.ttl_seconds)
        return ticket

    def get_ticket(self, ticket_id: str) -> OrderTicket | None:
        return self._get_model(self._ticket_key(ticket_id), OrderTicket)

    def store_order(self, order: PaperOrder) -> PaperOrder:
        self._set(self._order_key(order.order_id), order, self.ttl_seconds)
        self._append_index(
            self._draft_orders_key(order.draft_id),
            order.order_id,
            self.ttl_seconds,
        )
        return order

    def get_order(self, order_id: str) -> PaperOrder | None:
        return self._get_model(self._order_key(order_id), PaperOrder)

    def store_position(self, position: PaperPosition) -> PaperPosition:
        self._set(
            self._position_key(position.draft_id, position.symbol),
            position,
            self.position_ttl_seconds,
        )
        return position

    def get_position(self, draft_id: str, symbol: str) -> PaperPosition | None:
        return self._get_model(
            self._position_key(draft_id, symbol),
            PaperPosition,
        )

    def delete_position(self, draft_id: str, symbol: str) -> None:
        self._delete(self._position_key(draft_id, symbol))

    def mark_signal_status(
        self,
        signal: LabSignal,
        status: SignalStatus,
        *,
        paper_order_id: str | None = None,
        fill_id: str | None = None,
        position_id: str | None = None,
    ) -> LabSignal:
        updated = signal.model_copy(
            update={
                "status": status,
                "paper_order_id": paper_order_id or signal.paper_order_id,
                "fill_id": fill_id or signal.fill_id,
                "position_id": position_id or signal.position_id,
            }
        )
        return self.update_signal(updated)

    def _set(self, key: str, model: BaseModel, ttl_seconds: int) -> None:
        payload = model.model_dump_json()
        if self.use_redis:
            try:
                redis = self._redis()
                redis.set(key, payload, ex=ttl_seconds)
                return
            except Exception:
                logger.debug("Strategy Lab Redis write failed", exc_info=True)
        _MEMORY[key] = (payload, _now() + ttl_seconds)

    def _get_model(self, key: str, model: type[TModel]) -> TModel | None:
        payload: str | None = None
        if self.use_redis:
            try:
                payload = self._redis().get(key)
            except Exception:
                logger.debug("Strategy Lab Redis read failed", exc_info=True)
        if payload is None:
            payload = self._memory_get(key)
        if not payload:
            return None
        return model.model_validate_json(payload)

    def _append_index(self, key: str, value: str, ttl_seconds: int) -> None:
        if self.use_redis:
            try:
                redis = self._redis()
                pipe = redis.pipeline(transaction=False)
                pipe.lpush(key, value)
                pipe.ltrim(key, 0, 199)
                pipe.expire(key, ttl_seconds)
                pipe.execute()
                return
            except Exception:
                logger.debug("Strategy Lab Redis index write failed", exc_info=True)
        current = self._memory_get(key)
        values = json.loads(current) if current else []
        values.insert(0, value)
        _MEMORY[key] = (json.dumps(values[:200]), _now() + ttl_seconds)

    def _delete(self, key: str) -> None:
        if self.use_redis:
            try:
                self._redis().delete(key)
            except Exception:
                logger.debug("Strategy Lab Redis delete failed", exc_info=True)
        _MEMORY.pop(key, None)

    def _memory_get(self, key: str) -> str | None:
        item = _MEMORY.get(key)
        if item is None:
            return None
        payload, expires_at = item
        if expires_at <= _now():
            _MEMORY.pop(key, None)
            return None
        return payload

    def _redis(self):
        from shared.streaming.client import RedisClient

        return RedisClient.get_client()

    def _signal_key(self, signal_id: str) -> str:
        return f"strategy_lab:signal:{signal_id}"

    def _ticket_key(self, ticket_id: str) -> str:
        return f"strategy_lab:ticket:{ticket_id}"

    def _order_key(self, order_id: str) -> str:
        return f"strategy_lab:order:{order_id}"

    def _position_key(self, draft_id: str, symbol: str) -> str:
        return f"strategy_lab:position:{draft_id}:{symbol}"

    def _draft_signals_key(self, draft_id: str) -> str:
        return f"strategy_lab:draft:{draft_id}:signals"

    def _draft_orders_key(self, draft_id: str) -> str:
        return f"strategy_lab:draft:{draft_id}:orders"
