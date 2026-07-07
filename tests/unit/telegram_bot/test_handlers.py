"""Unit tests for services/telegram_bot/handlers.py.

Hermetic: fakeredis for Redis, hand-rolled duck-typed fakes for
``telegram.Update`` / ``CallbackQuery`` / ``Chat`` / ``Message`` — no real
``telegram.ext.Application`` and no network. Handlers only ever touch
``update.effective_chat``, ``update.callback_query``, ``query.data``,
``query.answer()``, ``query.edit_message_text()``, and ``chat.send_message()``,
so the fakes below only need to implement that surface.
"""

from __future__ import annotations

import json

import fakeredis.aioredis
import pytest

from services.telegram_bot import handlers
from services.telegram_bot.config import TelegramBotConfig
from shared.streaming.approval_keys import approval_field_id, pending_approval_key


class FakeChat:
    def __init__(self, chat_id: str) -> None:
        self.id = chat_id
        self.sent: list[tuple[str, object]] = []

    async def send_message(self, text: str, reply_markup: object | None = None) -> None:
        self.sent.append((text, reply_markup))


class FakeCallbackQuery:
    def __init__(self, data: str, chat: FakeChat) -> None:
        self.data = data
        self._chat = chat
        self.answered = False
        self.edits: list[tuple[str, object]] = []

    async def answer(self) -> None:
        self.answered = True

    async def edit_message_text(
        self, text: str, reply_markup: object | None = None
    ) -> None:
        self.edits.append((text, reply_markup))


class FakeUpdate:
    """Duck-typed stand-in for telegram.Update.

    Supports either a plain command update (``callback_query=None``) or a
    callback-query update — mirrors real ``Update.effective_chat`` semantics
    where both message and callback_query updates resolve to a chat.
    """

    def __init__(
        self, chat: FakeChat, callback_query: FakeCallbackQuery | None = None
    ) -> None:
        self.effective_chat = chat
        self.callback_query = callback_query


class FakeContext:
    def __init__(self, *, redis: object, config: TelegramBotConfig) -> None:
        self.bot_data = {"redis": redis, "config": config}


ALLOWED_CHAT_ID = "111"
OTHER_CHAT_ID = "999"


def _config(**overrides: object) -> TelegramBotConfig:
    defaults: dict[str, object] = {
        "enabled": True,
        "allowed_chat_ids": [ALLOWED_CHAT_ID],
        "poll_interval_seconds": 2,
    }
    defaults.update(overrides)
    return TelegramBotConfig(**defaults)


@pytest.fixture
def redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(db=1)


# ---------------------------------------------------------------------------
# Whitelist rejection
# ---------------------------------------------------------------------------


class TestWhitelistRejection:
    async def test_approve_callback_ignored_for_non_whitelisted_chat(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        approval_id = approval_field_id("stock", "sig-1")
        await redis.hset(
            pending_approval_key("stock"), approval_id, json.dumps({"code": "005930"})
        )

        chat = FakeChat(OTHER_CHAT_ID)
        query = FakeCallbackQuery(f"approve:{approval_id}", chat)
        update = FakeUpdate(chat, callback_query=query)
        context = FakeContext(redis=redis, config=_config())

        await handlers.approve_callback(update, context)

        # No side effects: query never answered/edited, pending record intact.
        assert query.answered is False
        assert query.edits == []
        assert await redis.hget(pending_approval_key("stock"), approval_id) is not None

    async def test_positions_command_ignored_for_non_whitelisted_chat(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        chat = FakeChat(OTHER_CHAT_ID)
        update = FakeUpdate(chat)
        context = FakeContext(redis=redis, config=_config())

        await handlers.positions_command(update, context)

        assert chat.sent == []

    async def test_help_command_ignored_for_non_whitelisted_chat(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        chat = FakeChat(OTHER_CHAT_ID)
        update = FakeUpdate(chat)
        context = FakeContext(redis=redis, config=_config())

        await handlers.help_command(update, context)

        assert chat.sent == []


# ---------------------------------------------------------------------------
# Approve -> final XADD replay
# ---------------------------------------------------------------------------


class TestApproveCallback:
    async def test_approve_replays_pending_fields_to_final_stream(
        self, redis: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("STOCK_RISK_FILTER", raising=False)
        monkeypatch.delenv("STOCK_FINAL_STREAM", raising=False)
        # STOCK_RISK_FILTER unset -> _resolve_mode() == "off" in
        # services.stock_risk_filter.main, but _streams_for("off") still
        # resolves the unsuffixed live stream name (mirrors _streams_for's
        # only-shadow-is-special contract) — assert against that directly
        # rather than hardcoding the literal.
        from services.stock_risk_filter.main import _streams_for

        _candidate, expected_final_stream = _streams_for("off")

        fields = {
            "signal_id": "sig-1",
            "code": "005930",
            "name": "삼성전자",
            "strategy": "vr_composite",
            "direction": "long",
            "price": "71000.0",
        }
        approval_id = approval_field_id("stock", "sig-1")
        await redis.hset(pending_approval_key("stock"), approval_id, json.dumps(fields))

        chat = FakeChat(ALLOWED_CHAT_ID)
        query = FakeCallbackQuery(f"approve:{approval_id}", chat)
        update = FakeUpdate(chat, callback_query=query)
        context = FakeContext(redis=redis, config=_config())

        await handlers.approve_callback(update, context)

        assert query.answered is True
        assert query.edits == [("✅ 승인됨", None)]

        # Final stream carries the exact fields dict, verbatim.
        entries = await redis.xrange(expected_final_stream)
        assert len(entries) == 1
        _msg_id, stream_fields = entries[0]
        decoded = {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in stream_fields.items()
        }
        assert decoded == fields

        # Pending field removed after replay.
        assert await redis.hget(pending_approval_key("stock"), approval_id) is None

    async def test_approve_missing_pending_edits_to_expired(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        approval_id = approval_field_id("futures", "sig-missing")
        chat = FakeChat(ALLOWED_CHAT_ID)
        query = FakeCallbackQuery(f"approve:{approval_id}", chat)
        update = FakeUpdate(chat, callback_query=query)
        context = FakeContext(redis=redis, config=_config())

        await handlers.approve_callback(update, context)

        assert query.edits == [("⌛ 만료됨", None)]


# ---------------------------------------------------------------------------
# Reject -> HDEL, no XADD
# ---------------------------------------------------------------------------


class TestRejectCallback:
    async def test_reject_deletes_pending_without_xadd(
        self, redis: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FUTURES_RISK_FILTER", raising=False)
        from services.risk_filter.main import _streams_for

        _candidate, final_stream = _streams_for("off")

        approval_id = approval_field_id("futures", "sig-2")
        await redis.hset(
            pending_approval_key("futures"),
            approval_id,
            json.dumps({"symbol": "A05603"}),
        )

        chat = FakeChat(ALLOWED_CHAT_ID)
        query = FakeCallbackQuery(f"reject:{approval_id}", chat)
        update = FakeUpdate(chat, callback_query=query)
        context = FakeContext(redis=redis, config=_config())

        await handlers.reject_callback(update, context)

        assert query.answered is True
        assert query.edits == [("🚫 거부됨", None)]
        assert await redis.hget(pending_approval_key("futures"), approval_id) is None
        assert await redis.xlen(final_stream) == 0


# ---------------------------------------------------------------------------
# Close -> intent=close XADD
# ---------------------------------------------------------------------------


class TestCloseCallback:
    async def test_close_xadds_intent_close(
        self, redis: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("STOCK_RISK_FILTER", raising=False)
        from services.stock_risk_filter.main import _streams_for

        _candidate, final_stream = _streams_for("off")

        chat = FakeChat(ALLOWED_CHAT_ID)
        query = FakeCallbackQuery("close:stock:005930", chat)
        update = FakeUpdate(chat, callback_query=query)
        context = FakeContext(redis=redis, config=_config())

        await handlers.close_callback(update, context)

        assert query.answered is True
        assert query.edits == [("🔴 청산 요청됨 · 005930", None)]

        entries = await redis.xrange(final_stream)
        assert len(entries) == 1
        _msg_id, stream_fields = entries[0]
        decoded = {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in stream_fields.items()
        }
        assert decoded["intent"] == "close"
        assert decoded["asset"] == "stock"
        assert decoded["code"] == "005930"
        assert decoded["symbol"] == "005930"
        assert "signal_id" in decoded


# ---------------------------------------------------------------------------
# /pending, /help, /start (spot checks — not the focus of this test file but
# cheap to cover for regression safety).
# ---------------------------------------------------------------------------


class TestMiscCommands:
    async def test_pending_command_lists_pending_approvals(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        approval_id = approval_field_id("stock", "sig-3")
        await redis.hset(
            pending_approval_key("stock"),
            approval_id,
            json.dumps({"code": "005930", "setup_type": "vr_composite"}),
        )
        chat = FakeChat(ALLOWED_CHAT_ID)
        update = FakeUpdate(chat)
        context = FakeContext(redis=redis, config=_config())

        await handlers.pending_command(update, context)

        assert len(chat.sent) == 1
        text, reply_markup = chat.sent[0]
        assert approval_id in text
        assert reply_markup is not None

    async def test_pending_command_reports_none_when_empty(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        chat = FakeChat(ALLOWED_CHAT_ID)
        update = FakeUpdate(chat)
        context = FakeContext(redis=redis, config=_config())

        await handlers.pending_command(update, context)

        assert chat.sent == [("대기 중인 승인 없음", None)]

    async def test_help_command_sends_usage(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        chat = FakeChat(ALLOWED_CHAT_ID)
        update = FakeUpdate(chat)
        context = FakeContext(redis=redis, config=_config())

        await handlers.help_command(update, context)

        assert chat.sent == [(handlers.HELP_TEXT, None)]
