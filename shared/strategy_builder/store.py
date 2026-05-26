"""Redis-backed Strategy Builder state."""

from __future__ import annotations

import logging
import time

from shared.strategy_builder.catalog import get_builder_ttl_seconds
from shared.strategy_builder.schema import BuilderSignal

logger = logging.getLogger(__name__)

_MEMORY: dict[str, tuple[str, float]] = {}


def reset_memory_store() -> None:
    _MEMORY.clear()


class StrategyBuilderStore:
    def __init__(self, *, use_redis: bool = True) -> None:
        self.use_redis = use_redis
        self.ttl_seconds = get_builder_ttl_seconds()

    def store_signal(self, signal: BuilderSignal) -> BuilderSignal:
        self._set(self._signal_key(signal.signal_id), signal.model_dump_json())
        return signal

    def get_signal(self, signal_id: str) -> BuilderSignal | None:
        payload = self._get(self._signal_key(signal_id))
        if not payload:
            return None
        return BuilderSignal.model_validate_json(payload)

    def _set(self, key: str, payload: str) -> None:
        if self.use_redis:
            try:
                self._redis().set(key, payload, ex=self.ttl_seconds)
                return
            except Exception:
                logger.debug("Strategy Builder Redis write failed", exc_info=True)
        _MEMORY[key] = (payload, time.time() + self.ttl_seconds)

    def _get(self, key: str) -> str | None:
        if self.use_redis:
            try:
                payload = self._redis().get(key)
                if payload:
                    if isinstance(payload, bytes):
                        return payload.decode("utf-8")
                    return str(payload)
            except Exception:
                logger.debug("Strategy Builder Redis read failed", exc_info=True)
        item = _MEMORY.get(key)
        if item is None:
            return None
        payload, expires_at = item
        if expires_at <= time.time():
            _MEMORY.pop(key, None)
            return None
        return payload

    def _redis(self):
        from shared.streaming.client import RedisClient

        return RedisClient.get_client()

    def _signal_key(self, signal_id: str) -> str:
        return f"strategy_builder:signal:{signal_id}"
