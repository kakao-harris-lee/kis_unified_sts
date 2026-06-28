"""Small helpers for low-noise Redis stream audit logging."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Mapping
from typing import Any

SAFE_AUDIT_FIELDS = (
    "signal_id",
    "symbol",
    "code",
    "strategy",
    "setup_type",
    "direction",
)

_SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9._:/@+-]+$")


def decode_stream_id(value: Any) -> str:
    """Normalize Redis byte/string identifiers for log output."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _decode_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def extract_audit_fields(fields: Mapping[Any, Any]) -> dict[str, str]:
    """Extract non-sensitive identifiers from Redis message fields."""
    decoded = {_decode_field(key): _decode_field(value) for key, value in fields.items()}
    return {
        key: value
        for key in SAFE_AUDIT_FIELDS
        if (value := decoded.get(key)) not in {None, ""}
    }


def format_audit_kv(**items: Any) -> str:
    """Render stable key=value tokens while dropping empty values."""
    tokens = []
    for key, value in items.items():
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            rendered = str(value).lower()
        elif isinstance(value, bytes):
            rendered = decode_stream_id(value)
        else:
            rendered = str(value)
        if not _SAFE_VALUE_RE.fullmatch(rendered):
            rendered = json.dumps(rendered, ensure_ascii=True)
        tokens.append(f"{key}={rendered}")
    return " ".join(tokens)


class RateLimitedLog:
    """Emit first exception traceback, then summarize repeated failures."""

    def __init__(
        self,
        *,
        cooldown_seconds: float = 30.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock or time.monotonic
        self._last_emit_at: float | None = None
        self._suppressed_count = 0

    def exception(
        self,
        logger: logging.Logger,
        message: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Log the current exception if due, otherwise count suppression."""
        now = self._clock()
        if self._last_emit_at is None:
            logger.exception(message, *args, **kwargs)
            self._last_emit_at = now
            return

        if now - self._last_emit_at < self.cooldown_seconds:
            self._suppressed_count += 1
            return

        if self._suppressed_count:
            rendered = message % args if args else message
            logger.error("%s suppressed_count=%d", rendered, self._suppressed_count)
            self._suppressed_count = 0
        else:
            logger.exception(message, *args, **kwargs)
        self._last_emit_at = now

    def reset(self) -> None:
        """Mark the guarded operation as recovered so the next error is visible."""
        self._last_emit_at = None
        self._suppressed_count = 0
