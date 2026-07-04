"""Pure helpers for post-exit entry re-entry cooldowns."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import Any

from services.trading.runtime_config import EntryReentryGuardConfig


def reentry_guard_key(
    config: EntryReentryGuardConfig,
    code: str,
    strategy: str | None,
) -> str:
    if config.scope == "symbol":
        return str(code)
    return f"{code}:{strategy or ''}"


def record_recent_exit_cooldown(
    recent: MutableMapping[str, dict[str, Any]],
    config: EntryReentryGuardConfig,
    *,
    closed: Any,
    signal: Any,
    reason: str,
    now: datetime | None = None,
) -> None:
    """Record a filled exit so near-term re-entry can be blocked."""
    if not config.enabled:
        return

    cooldown_seconds = config.cooldown_for(reason)
    if cooldown_seconds <= 0:
        return

    code = str(getattr(signal, "code", "") or getattr(closed, "code", "") or "")
    if not code:
        return
    strategy = str(
        getattr(signal, "strategy", "") or getattr(closed, "strategy", "") or ""
    )
    key = reentry_guard_key(config, code, strategy)

    recent[key] = {
        "code": code,
        "strategy": strategy,
        "reason": str(reason).lower(),
        "exit_time": now or datetime.now(UTC),
        "cooldown_seconds": float(cooldown_seconds),
    }


def reentry_guard_block(
    recent: MutableMapping[str, dict[str, Any]],
    config: EntryReentryGuardConfig,
    *,
    code: str,
    strategy: str | None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Return block metadata when an entry signal violates exit cooldown."""
    if not config.enabled or not recent:
        return None

    now_utc = now or datetime.now(UTC)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    else:
        now_utc = now_utc.astimezone(UTC)

    key = reentry_guard_key(config, code, strategy)
    record = recent.get(key)
    if not record:
        return None

    exit_time = record.get("exit_time")
    if not isinstance(exit_time, datetime):
        recent.pop(key, None)
        return None
    if exit_time.tzinfo is None:
        exit_time = exit_time.replace(tzinfo=UTC)
    else:
        exit_time = exit_time.astimezone(UTC)

    cooldown_seconds = float(record.get("cooldown_seconds", 0.0) or 0.0)
    elapsed = max(0.0, (now_utc - exit_time).total_seconds())
    remaining = cooldown_seconds - elapsed
    if remaining <= 0:
        recent.pop(key, None)
        return None

    return {
        **record,
        "remaining_seconds": remaining,
        "elapsed_seconds": elapsed,
    }
