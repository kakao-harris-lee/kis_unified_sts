"""Inbound Telegram handlers for the interactive-alerts feature.

Design: docs/plans/2026-07-07-telegram-interactive-alerts-design.md
("Method A": ``services/{risk_filter,stock_risk_filter}/main.py`` records a
gated signal as *pending* instead of XADDing to ``signal.final.{asset}``; this
module is the consumer/resolver side that either replays the pending record
to the final stream (approve) or discards it (reject/expiry), plus the
``/positions`` -> close-button flow.

Every handler is gated by the ``allowed_chat_ids`` whitelist first
(:func:`_require_allowed_chat`) — an update from an unlisted chat_id is
ignored silently (logged at WARNING) with no further side effects.

Dependencies (Redis client, :class:`TelegramBotConfig`) are injected via
``context.bot_data`` (the standard python-telegram-bot DI idiom — see
``services/telegram_bot/main.py::_build_application``), so handlers stay
plain functions that tests can call directly with a fake ``context.bot_data``
dict and a duck-typed fake ``Update`` (no real ``telegram.Update`` /
``Application`` needed, no network).
"""

from __future__ import annotations

import functools
import json
import logging
import time
import uuid
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from shared.notification.formatting import approval_buttons, close_button
from shared.streaming.approval_keys import pending_approval_key
from shared.streaming.trading_state import TradingStateReader

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

    from services.telegram_bot.config import TelegramBotConfig

logger = logging.getLogger(__name__)

# CLAUDE.md "New Redis keys need TTLs; default operational TTL is 24h" — the
# bot's own XADDs (approve-replay, close) refresh the final stream's TTL the
# same way services/risk_filter/main.py and services/stock_risk_filter/main.py
# already do after every XADD to signal.final.{asset}.
_STREAM_TTL_SECONDS = 86400
# Mirrors the risk_filter daemons' final_maxlen=10_000 (bounded stream growth).
_FINAL_STREAM_MAXLEN = 10_000

_ASSETS = ("stock", "futures")

HELP_TEXT = (
    "/positions - 보유 포지션 조회 (청산 버튼 포함)\n"
    "/pending - 대기 중인 승인 신호 조회\n"
    "/help - 도움말"
)

_HandlerFn = Callable[
    ["Update", "ContextTypes.DEFAULT_TYPE"], Coroutine[Any, Any, None]
]


def _final_stream_for(asset: str) -> str:
    """Return the ``signal.final.{asset}`` stream this bot should XADD to.

    Reuses the SAME mode-resolution + stream-naming helpers the risk_filter
    daemons use internally (``_resolve_mode`` / ``_streams_for``) — imported
    directly rather than re-implemented — so the bot's replay XADD (approve)
    or close-intent XADD always lands on whichever final stream the
    currently-deployed risk_filter for *asset* would itself write to (shadow
    vs. live), without duplicating the env-var / naming logic here. Mirrors
    the existing cross-service private-helper import precedent in
    ``services/order_router/main.py`` (``from services.risk_filter.main
    import _signal_from_stream_fields``).

    Args:
        asset: ``"stock"`` or ``"futures"``.

    Returns:
        The final-stream name, e.g. ``"signal.final.stock"`` or
        ``"signal.final.futures.shadow"``.
    """
    if asset == "stock":
        from services.stock_risk_filter.main import _resolve_mode, _streams_for
    else:
        from services.risk_filter.main import _resolve_mode, _streams_for
    mode = _resolve_mode()
    _candidate_stream, final_stream = _streams_for(mode)
    return final_stream


def _is_authorized(update: Update, config: TelegramBotConfig) -> bool:
    """Return True if *update* originates from a whitelisted chat_id."""
    chat = update.effective_chat
    return chat is not None and str(chat.id) in config.allowed_chat_ids


def _require_allowed_chat(handler: _HandlerFn) -> _HandlerFn:
    """Decorator: silently ignore (+ log a warning) updates outside the whitelist.

    Applied to every handler in this module so the chat_id gate is enforced
    exactly once, in one place, rather than repeated per-handler.
    """

    @functools.wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        config: TelegramBotConfig = context.bot_data["config"]
        if not _is_authorized(update, config):
            chat = update.effective_chat
            logger.warning(
                "Ignoring update from non-whitelisted chat_id=%s",
                chat.id if chat is not None else None,
            )
            return
        await handler(update, context)

    return wrapped


def _decode_hash(raw: dict[Any, Any]) -> dict[str, str]:
    """Decode a Redis HASH mapping (bytes or str keys/values) to ``dict[str, str]``."""
    out: dict[str, str] = {}
    for key, value in raw.items():
        k = key.decode() if isinstance(key, bytes) else str(key)
        v = value.decode() if isinstance(value, bytes) else str(value)
        out[k] = v
    return out


def _decode_value(raw: Any) -> str:
    """Decode a single Redis HGET value (bytes or str) to ``str``."""
    return raw.decode() if isinstance(raw, bytes) else str(raw)


# ---------------------------------------------------------------------------
# Approve / reject (pending-approval resolution)
# ---------------------------------------------------------------------------


@_require_allowed_chat
async def approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``approve:{approval_id}``: replay the pending signal to final.

    Loads the pending record from ``signal:pending_approval:{asset}`` (field =
    approval_id); if present, XADDs the stored fields dict verbatim to
    ``signal.final.{asset}``, HDELs the pending field, and edits the message
    to a "승인됨" state. If the pending record is missing (already resolved
    or expired), edits the message to "만료됨" without touching any stream.
    """
    query = update.callback_query
    assert query is not None  # CallbackQueryHandler guarantees this
    await query.answer()

    assert query.data is not None  # pattern-matched CallbackQueryHandler
    _, approval_id = query.data.split(":", 1)
    asset, _signal_id = approval_id.split(":", 1)

    redis = context.bot_data["redis"]
    key = pending_approval_key(asset)
    raw = await redis.hget(key, approval_id)
    if raw is None:
        await query.edit_message_text("⌛ 만료됨", reply_markup=None)
        return

    fields = json.loads(_decode_value(raw))
    final_stream = _final_stream_for(asset)
    await redis.xadd(
        final_stream, fields, maxlen=_FINAL_STREAM_MAXLEN, approximate=True
    )
    await redis.expire(final_stream, _STREAM_TTL_SECONDS)
    await redis.hdel(key, approval_id)
    await query.edit_message_text("✅ 승인됨", reply_markup=None)


@_require_allowed_chat
async def reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``reject:{approval_id}``: discard the pending signal, no order."""
    query = update.callback_query
    assert query is not None
    await query.answer()

    assert query.data is not None
    _, approval_id = query.data.split(":", 1)
    asset, _signal_id = approval_id.split(":", 1)

    redis = context.bot_data["redis"]
    await redis.hdel(pending_approval_key(asset), approval_id)
    await query.edit_message_text("🚫 거부됨", reply_markup=None)


# ---------------------------------------------------------------------------
# Positions / close
# ---------------------------------------------------------------------------


def _format_position_line(asset: str, position: dict[str, Any]) -> str:
    """Render a concise 2-line summary for one open position."""
    code = str(position.get("code") or position.get("symbol") or "")
    name = position.get("name") or ""
    side = str(position.get("side", "long"))
    quantity = position.get("quantity", 0)
    entry_price = float(position.get("entry_price", 0) or 0)
    current_price = float(position.get("current_price", entry_price) or entry_price)
    pnl_pct = float(position.get("pnl_pct", 0) or 0)
    sign = "+" if pnl_pct >= 0 else ""
    label = f"{name} ({code})" if name else code
    header = f"📌 [{asset}] {label}"
    numbers = (
        f"{side} {quantity} @ {entry_price:,.0f} → {current_price:,.0f} "
        f"({sign}{pnl_pct:.2f}%)"
    )
    return "\n".join([header, numbers])


@_require_allowed_chat
async def positions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/positions``: one message per open position (both assets), with a 청산 button."""
    chat = update.effective_chat
    assert chat is not None
    found = False
    for asset in _ASSETS:
        positions = TradingStateReader(asset).get_positions()
        for position in positions:
            found = True
            code = str(position.get("code") or position.get("symbol") or "")
            text = _format_position_line(asset, position)
            await chat.send_message(text, reply_markup=close_button(asset, code))
    if not found:
        await chat.send_message("보유 포지션 없음")


@_require_allowed_chat
async def close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``close:{asset}:{code}``: XADD an intent=close message.

    Does NOT call a broker directly (CLAUDE.md / design doc: only the order
    router holds wallet authority). The message is deliberately minimal — the
    order-router's intent=close branch resolves quantity/direction from its
    own positions hash (see ``services/futures_monitor/positions.py`` /
    ``services/stock_exit/positions.py`` for the position-record shape it
    reads).
    """
    query = update.callback_query
    assert query is not None
    await query.answer()

    assert query.data is not None
    _, asset, code = query.data.split(":", 2)

    redis = context.bot_data["redis"]
    final_stream = _final_stream_for(asset)
    fields = {
        "intent": "close",
        "asset": asset,
        "code": code,
        "symbol": code,
        "signal_id": uuid.uuid4().hex,
        "requested_at_ms": str(int(time.time() * 1000)),
    }
    await redis.xadd(
        final_stream, fields, maxlen=_FINAL_STREAM_MAXLEN, approximate=True
    )
    await redis.expire(final_stream, _STREAM_TTL_SECONDS)
    await query.edit_message_text(f"🔴 청산 요청됨 · {code}", reply_markup=None)


# ---------------------------------------------------------------------------
# /pending, /help, /start
# ---------------------------------------------------------------------------


@_require_allowed_chat
async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/pending``: list current pending approvals (both assets)."""
    chat = update.effective_chat
    assert chat is not None
    redis = context.bot_data["redis"]

    found = False
    for asset in _ASSETS:
        raw = await redis.hgetall(pending_approval_key(asset))
        for approval_id, value in _decode_hash(raw).items():
            found = True
            try:
                fields = json.loads(value)
            except json.JSONDecodeError:
                fields = {}
            label = fields.get("symbol") or fields.get("code") or ""
            strategy = fields.get("setup_type") or fields.get("strategy") or ""
            text = f"⏳ [{asset}] {label} · {strategy}\n{approval_id}"
            await chat.send_message(text, reply_markup=approval_buttons(approval_id))
    if not found:
        await chat.send_message("대기 중인 승인 없음")


@_require_allowed_chat
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/help``: usage summary."""
    chat = update.effective_chat
    assert chat is not None
    await chat.send_message(HELP_TEXT)


@_require_allowed_chat
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/start``: greeting (only ever sent to a whitelisted chat)."""
    chat = update.effective_chat
    assert chat is not None
    await chat.send_message("🤖 트레이딩 알림 봇입니다.\n" + HELP_TEXT)
