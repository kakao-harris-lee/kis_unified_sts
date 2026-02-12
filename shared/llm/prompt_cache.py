"""Prompt cache for LLM requests."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromptCacheConfig:
    enabled: bool = True
    ttl_seconds: int = 21_600
    key_prefix: str = "llm:prompt_cache"


class LLMPromptCache:
    """Redis-backed prompt cache with in-memory fallback."""

    def __init__(self, config: PromptCacheConfig):
        self.config = config
        self._redis = None
        self._memory: dict[str, tuple[float, str]] = {}

        if self.config.enabled:
            try:
                from shared.streaming.client import RedisClient

                self._redis = RedisClient.get_client()
            except Exception as e:
                logger.debug(f"Prompt cache redis unavailable, fallback to memory: {e}")

    @staticmethod
    def build_key(
        *,
        key_prefix: str,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        extra: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "provider": provider,
            "model": model,
            "system": system_prompt,
            "user": user_prompt,
            "extra": extra or {},
        }
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        return f"{key_prefix}:{digest}"

    def get(self, key: str) -> str | None:
        if not self.config.enabled:
            return None

        if self._redis is not None:
            try:
                v = self._redis.get(key)
                if isinstance(v, str) and v:
                    return v
            except Exception as e:
                logger.debug(f"Prompt cache redis get failed: {e}")

        entry = self._memory.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            self._memory.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str) -> None:
        if not self.config.enabled:
            return

        if self._redis is not None:
            try:
                self._redis.setex(key, self.config.ttl_seconds, value)
                return
            except Exception as e:
                logger.debug(f"Prompt cache redis set failed: {e}")

        self._memory[key] = (time.time() + max(1, self.config.ttl_seconds), value)
