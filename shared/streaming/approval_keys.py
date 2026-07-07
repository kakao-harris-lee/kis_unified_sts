"""Pending-approval Redis key conventions.

Mirrors ``shared/streaming/stock_keys.py``: env-overridable key builder plus a
fixed pub/sub channel constant so producers (``risk_filter`` /
``stock_risk_filter``) and the consumer (``services/telegram_bot``) agree on
the exact same Redis surface without importing each other.

Data shape (see ``docs/plans/2026-07-07-telegram-interactive-alerts-design.md``):
    HASH ``signal:pending_approval:{asset}``
        field = ``{asset}:{signal_id}`` (see :func:`approval_field_id`)
        value = JSON-encoded dict of the full ``signal.final.{asset}``
                stream-dict that would have been XADDed, so the bot can
                replay it verbatim on approval.
"""

from __future__ import annotations

import os

DEFAULT_PENDING_APPROVAL_KEY = "signal:pending_approval:{asset}"

# Pub/sub channel the gate PUBLISHes to on every new pending approval.
# Mirrors the ``trading:events:{positions,signals,fills}`` convention in
# shared/streaming/trading_state.py — deliberately a single fixed channel
# (no per-asset suffix) since the bot subscribes once for both asset classes.
APPROVAL_EVENTS_CHANNEL = "trading:events:approval"

# CLAUDE.md "Redis: ... New Redis keys need TTLs; default operational TTL is
# 24h" — the pending-approval hash expires unapproved signals automatically
# so a forgotten approval can never linger and fire stale.
_APPROVAL_TTL_SECONDS = 86400


def pending_approval_key(asset: str) -> str:
    """Return the pending-approval HASH key for *asset*.

    Args:
        asset: Asset class, e.g. ``"stock"`` or ``"futures"``.

    Returns:
        Redis key, e.g. ``"signal:pending_approval:stock"``. Overridable via
        the ``PENDING_APPROVAL_KEY`` env var (used verbatim, ignoring
        *asset*) for tests/operators that need a non-default key.
    """
    override = os.environ.get("PENDING_APPROVAL_KEY", "").strip()
    if override:
        return override
    return DEFAULT_PENDING_APPROVAL_KEY.format(asset=asset)


def approval_field_id(asset: str, signal_id: str) -> str:
    """Return the HASH field id for a pending approval record.

    Args:
        asset: Asset class, e.g. ``"stock"`` or ``"futures"``.
        signal_id: The signal's unique id (same id carried on the stream
            message that would have gone to ``signal.final.{asset}``).

    Returns:
        Field id of the form ``"{asset}:{signal_id}"``, doubling as the
        ``approval_id`` referenced in Telegram callback_data.
    """
    return f"{asset}:{signal_id}"
