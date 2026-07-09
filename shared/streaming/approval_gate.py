"""Shared approval-gate helper for the Telegram interactive-alerts feature.

Used by BOTH ``services/risk_filter/main.py`` (futures) and
``services/stock_risk_filter/main.py`` (stock) right before their final
``xadd(signal.final.{asset}, ...)`` call (see
``docs/plans/2026-07-07-telegram-interactive-alerts-design.md``, "Method A").
When a signal's strategy/symbol matches the configured gate list, the risk
filter calls :func:`record_pending` instead of XADDing to the final stream —
the pending record holds the exact stream-dict that *would* have been XADDed,
so ``services/telegram_bot`` can XADD it verbatim on operator approval.

Pure-async, redis-client-injected (no module-level singleton) so both daemons
and tests can supply their own connection (``fakeredis.aioredis`` in tests).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.streaming.approval_keys import (
    APPROVAL_EVENTS_CHANNEL,
    approval_field_id,
    pending_approval_key,
)

logger = logging.getLogger(__name__)


class ApprovalGateConfig(ServiceConfigBase):
    """Approval-gate settings, loaded from ``config/telegram_bot.yaml``.

    Section: ``approval_gate:``. Defaults to fully inert (``enabled=False``,
    empty target lists) so existing risk-filter behavior is unchanged until
    an operator explicitly opts a strategy/symbol in.
    """

    _default_config_file: ClassVar[str] = "telegram_bot.yaml"
    _default_section: ClassVar[str] = "approval_gate"
    _env_prefix: ClassVar[str] = "APPROVAL_GATE_"

    enabled: bool = Field(
        default=False,
        description="Master switch. False: is_gated() always returns False.",
    )
    gated_strategies: list[str] = Field(
        default_factory=list,
        description=(
            "Strategy identifiers held for approval — matches "
            "Signal.setup_type for futures (e.g. 'A_gap_reversion', "
            "'C_event_reaction') or signal.strategy for stock (e.g. "
            "'bb_reversion'), NOT the YAML strategy-file name."
        ),
    )
    gated_symbols: list[str] = Field(
        default_factory=list,
        description="Symbols/codes held for approval, e.g. ['005930'].",
    )
    pending_ttl_seconds: int = Field(
        default=86400,
        gt=0,
        description=(
            "TTL for the pending-approval HASH (CLAUDE.md 24h default "
            "operational TTL rule)."
        ),
    )


def log_gate_config(config: ApprovalGateConfig, *, asset: str) -> None:
    """Log which strategies/symbols are gated at daemon startup.

    A typo/case/rename in ``gated_strategies``/``gated_symbols`` silently
    gates nothing (see :func:`is_gated`) — there is no runtime signal that a
    configured value never matches. This INFO line is the cheap safeguard:
    an operator can eyeball the log at startup and confirm the intended
    strategy/symbol identifiers are the ones actually gated, instead of only
    discovering a no-op gate when an expected approval never arrives.

    No-ops (nothing is logged) when the gate is disabled or both lists are
    empty, since that is the default/inert state and would otherwise log on
    every daemon start.

    Args:
        config: Loaded :class:`ApprovalGateConfig`.
        asset: Asset class for log context, e.g. "futures" or "stock".
    """
    if not config.enabled:
        return
    if not config.gated_strategies and not config.gated_symbols:
        return
    logger.info(
        "approval_gate[%s] enabled: gating strategies=%s symbols=%s",
        asset,
        config.gated_strategies,
        config.gated_symbols,
    )


def is_gated(strategy: str, symbol: str, config: ApprovalGateConfig) -> bool:
    """Return True if a signal for *strategy*/*symbol* must be held for approval.

    A signal is gated when the gate is enabled AND its strategy is in
    ``config.gated_strategies`` OR its symbol is in ``config.gated_symbols``.
    Empty lists never match, so leaving both empty means nothing is gated
    even with ``enabled=True`` — the operator must opt specific
    strategies/symbols in.

    Comparison is case-insensitive and ignores surrounding whitespace on both
    sides (the signal's value and the configured list entries), so a stray
    case slip in ``config/telegram_bot.yaml`` (e.g. "a_gap_reversion" vs the
    real ``Signal.setup_type`` value "A_gap_reversion") still gates instead of
    silently matching nothing.

    Args:
        strategy: The signal's strategy/setup name — ``Signal.setup_type``
            for futures (e.g. "A_gap_reversion"), ``signal.strategy`` for
            stock (e.g. "bb_reversion").
        symbol: The signal's symbol/code (e.g. "005930").
        config: Loaded :class:`ApprovalGateConfig`.

    Returns:
        True if the signal should be held (recorded via :func:`record_pending`
        instead of reaching ``signal.final.{asset}``).
    """
    if not config.enabled:
        return False
    norm_strategy = strategy.strip().casefold()
    norm_symbol = symbol.strip().casefold()
    gated_strategies = {s.strip().casefold() for s in config.gated_strategies}
    gated_symbols = {s.strip().casefold() for s in config.gated_symbols}
    return norm_strategy in gated_strategies or norm_symbol in gated_symbols


async def record_pending(
    redis: Any,
    asset: str,
    signal_id: str,
    fields: dict[str, str],
    ttl: int,
) -> str:
    """Record a gated signal as pending approval and notify subscribers.

    Stores *fields* — the exact stream-dict that would have been XADDed to
    ``signal.final.{asset}`` — as a JSON-encoded value in the pending-approval
    HASH, refreshes the HASH's TTL, and publishes a lightweight wake-up event
    on :data:`shared.streaming.approval_keys.APPROVAL_EVENTS_CHANNEL` (mirrors
    the ``trading:events:{topic}`` cache-invalidation convention in
    ``shared/streaming/trading_state.py`` — a notification only, not the
    payload itself).

    Args:
        redis: Async Redis client (``redis.asyncio.Redis`` or
            ``fakeredis.aioredis.FakeRedis``) providing ``hset``/``expire``/
            ``publish``.
        asset: Asset class, e.g. "stock" or "futures".
        signal_id: The signal's unique id.
        fields: The full stream-dict that would have been XADDed to
            ``signal.final.{asset}`` — stored verbatim for replay on approval.
        ttl: Seconds until the pending record expires (unapproved signals are
            never actioned after expiry).

    Returns:
        The approval_id (``"{asset}:{signal_id}"``) — also the id embedded in
        the approve/reject callback_data (see
        ``shared/notification/formatting.py``).
    """
    approval_id = approval_field_id(asset, signal_id)
    key = pending_approval_key(asset)
    await redis.hset(key, approval_id, json.dumps(fields))
    # TTL is set on the whole per-asset HASH, so a later gated signal resets the
    # expiry of every still-pending field in it (i.e. expiry is per-asset, not
    # per-signal). Acceptable here: nothing acts on a per-signal deadline beyond
    # this HASH TTL. Revisit (e.g. per-field STRING keys) if precise per-signal
    # expiry is ever required.
    await redis.expire(key, ttl)
    try:
        await redis.publish(
            APPROVAL_EVENTS_CHANNEL,
            json.dumps(
                {
                    "asset_class": asset,
                    "approval_id": approval_id,
                    "signal_id": signal_id,
                    "recorded_at_ms": int(time.time() * 1000),
                }
            ),
        )
    except Exception:
        # Best-effort notification — the pending HASH write above already
        # succeeded, so a pub/sub hiccup must not fail the caller (mirrors
        # TradingStatePublisher._publish_event's fire-and-forget contract).
        logger.debug(
            "Failed to publish approval event for %s", approval_id, exc_info=True
        )
    return approval_id
