"""Unit tests for services/telegram_bot/handlers.py.

Hermetic: fakeredis for Redis, hand-rolled duck-typed fakes for
``telegram.Update`` / ``CallbackQuery`` / ``Chat`` / ``Message`` — no real
``telegram.ext.Application`` and no network. Handlers only ever touch
``update.effective_chat``, ``update.callback_query``, ``query.data``,
``query.answer()``, ``query.edit_message_text()``, and ``chat.send_message()``,
so the fakes below only need to implement that surface.
"""

from __future__ import annotations

import asyncio
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
# _final_stream_for: stream-resolution parity with the risk_filter daemons.
#
# The real deployment bug this guards against: docker-compose.yml's
# telegram_bot service environment block failed to forward
# STOCK_RISK_FILTER/FUTURES_RISK_FILTER (the same mode vars stock-risk-filter
# / futures-risk-filter derive from ${STOCK_PIPELINE_MODE:-shadow} /
# ${FUTURES_PIPELINE_MODE:-shadow}), so inside the bot container the vars
# were unset, _resolve_mode() fell back to "off", and the bot's approve/close
# XADDs silently landed on the unsuffixed LIVE stream while
# stock-order-router/futures-order-router (correctly wired to "shadow")
# consumed the .shadow-suffixed stream — i.e. bot actions vanished (or, mid
# live-cutover, could fire a real order) without anything erroring.
#
# These tests assert the INVARIANT directly — bot and risk_filter/order_router
# must resolve to the identical final stream for a given env — rather than
# hardcoding stream-name literals, so the test still catches a regression if
# the naming scheme itself changes later.
# ---------------------------------------------------------------------------


class TestFinalStreamForParity:
    def test_stock_shadow_matches_risk_filter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("STOCK_RISK_FILTER", "shadow")
        from services.stock_risk_filter.main import _resolve_mode, _streams_for

        _candidate, expected = _streams_for(_resolve_mode())
        assert handlers._final_stream_for("stock") == expected

    def test_stock_live_matches_risk_filter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("STOCK_RISK_FILTER", "live")
        from services.stock_risk_filter.main import _resolve_mode, _streams_for

        _candidate, expected = _streams_for(_resolve_mode())
        assert handlers._final_stream_for("stock") == expected

    def test_futures_shadow_matches_risk_filter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FUTURES_RISK_FILTER", "shadow")
        from services.risk_filter.main import _resolve_mode, _streams_for

        _candidate, expected = _streams_for(_resolve_mode())
        assert handlers._final_stream_for("futures") == expected

    def test_futures_live_matches_risk_filter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FUTURES_RISK_FILTER", "live")
        from services.risk_filter.main import _resolve_mode, _streams_for

        _candidate, expected = _streams_for(_resolve_mode())
        assert handlers._final_stream_for("futures") == expected


# ---------------------------------------------------------------------------
# _claim_pending: atomic get-and-delete (the double-order fix's linchpin)
# ---------------------------------------------------------------------------


class TestClaimPending:
    async def test_concurrent_claims_only_one_winner(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        """Two truly-concurrent claims on the SAME field: exactly one wins.

        This is the atomicity property the whole fix rests on — a sequential
        double-tap (covered by TestApproveCallback) only proves idempotency
        after the fact, not that a genuine race can't let both callers see
        the value. Firing both claims via ``asyncio.gather`` interleaves
        their awaits, exercising the WATCH/MULTI/EXEC retry loop for real.
        """
        key = pending_approval_key("stock")
        field = approval_field_id("stock", "sig-race")
        await redis.hset(key, field, json.dumps({"code": "005930"}))

        results = await asyncio.gather(
            handlers._claim_pending(redis, key, field),
            handlers._claim_pending(redis, key, field),
        )

        non_none = [r for r in results if r is not None]
        assert len(non_none) == 1
        assert results.count(None) == 1
        assert await redis.hget(key, field) is None

    async def test_claim_missing_field_returns_none(
        self, redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        key = pending_approval_key("stock")
        result = await handlers._claim_pending(redis, key, "stock:never-existed")
        assert result is None


# ---------------------------------------------------------------------------
# Approve -> final XADD replay
# ---------------------------------------------------------------------------


class TestApproveCallback:
    async def test_approve_replays_pending_fields_to_final_stream(
        self, redis: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Compose (docker-compose.yml telegram_bot + stock-risk-filter) sets
        # STOCK_RISK_FILTER to the SAME shadow/live mode var for both
        # services, so this test mirrors that instead of leaving the env var
        # unset (which produced "off" — the deployment-bug scenario where
        # the bot's XADD silently diverged from where stock-order-router
        # actually reads from).
        monkeypatch.setenv("STOCK_RISK_FILTER", "shadow")
        monkeypatch.delenv("STOCK_FINAL_STREAM", raising=False)
        from services.stock_risk_filter.main import _resolve_mode, _streams_for

        _candidate, expected_final_stream = _streams_for(_resolve_mode())
        assert expected_final_stream == "signal.final.stock.shadow"

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

    async def test_double_approve_only_xadds_once(
        self, redis: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Double-order regression: a re-tap of an already-approved button.

        Reproduces the original bug's trigger (operator re-taps [승인] after
        the first tap already went through) and asserts the atomic claim
        (:func:`handlers._claim_pending`) makes the second tap a no-op: only
        ONE XADD ever lands on the final stream, and the second callback
        query is told "만료됨"/already-handled rather than replaying the
        same fields again.
        """
        monkeypatch.setenv("STOCK_RISK_FILTER", "shadow")
        from services.stock_risk_filter.main import _resolve_mode, _streams_for

        _candidate, final_stream = _streams_for(_resolve_mode())
        assert final_stream == "signal.final.stock.shadow"

        fields = {"signal_id": "sig-dup", "code": "005930", "direction": "long"}
        approval_id = approval_field_id("stock", "sig-dup")
        await redis.hset(pending_approval_key("stock"), approval_id, json.dumps(fields))

        chat = FakeChat(ALLOWED_CHAT_ID)

        # First tap: approves for real.
        query1 = FakeCallbackQuery(f"approve:{approval_id}", chat)
        update1 = FakeUpdate(chat, callback_query=query1)
        context1 = FakeContext(redis=redis, config=_config())
        await handlers.approve_callback(update1, context1)

        # Second tap: operator re-taps the same (still-visible) button.
        query2 = FakeCallbackQuery(f"approve:{approval_id}", chat)
        update2 = FakeUpdate(chat, callback_query=query2)
        context2 = FakeContext(redis=redis, config=_config())
        await handlers.approve_callback(update2, context2)

        assert query1.edits == [("✅ 승인됨", None)]
        assert query2.edits == [("⌛ 만료됨", None)]

        # Exactly one XADD reached the final stream — no double order.
        entries = await redis.xrange(final_stream)
        assert len(entries) == 1

        # Pending record stays gone (not resurrected by the second tap).
        assert await redis.hget(pending_approval_key("stock"), approval_id) is None

    async def test_retap_after_pending_field_already_gone_does_not_xadd(
        self, redis: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulates the crash window: pending field already claimed/removed
        (as it would be right after a successful approve, or after a crash
        that landed post-claim), and a re-tap must not XADD again.
        """
        monkeypatch.setenv("FUTURES_RISK_FILTER", "shadow")
        from services.risk_filter.main import _resolve_mode, _streams_for

        _candidate, final_stream = _streams_for(_resolve_mode())
        assert final_stream == "signal.final.futures.shadow"

        approval_id = approval_field_id("futures", "sig-crash")
        # No HSET here: the pending field is already gone, exactly as it
        # would be the instant after `_claim_pending` succeeded (whether or
        # not the XADD that followed actually completed).

        chat = FakeChat(ALLOWED_CHAT_ID)
        query = FakeCallbackQuery(f"approve:{approval_id}", chat)
        update = FakeUpdate(chat, callback_query=query)
        context = FakeContext(redis=redis, config=_config())

        await handlers.approve_callback(update, context)

        assert query.edits == [("⌛ 만료됨", None)]
        assert await redis.xlen(final_stream) == 0

    async def test_approve_after_reject_does_not_xadd(
        self, redis: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A reject followed by a (stale/racing) approve tap must not XADD:
        reject's HDEL wins the field first, so approve's claim finds nothing.
        """
        monkeypatch.setenv("STOCK_RISK_FILTER", "shadow")
        from services.stock_risk_filter.main import _resolve_mode, _streams_for

        _candidate, final_stream = _streams_for(_resolve_mode())
        assert final_stream == "signal.final.stock.shadow"

        fields = {"signal_id": "sig-rej", "code": "000660", "direction": "short"}
        approval_id = approval_field_id("stock", "sig-rej")
        await redis.hset(pending_approval_key("stock"), approval_id, json.dumps(fields))

        chat = FakeChat(ALLOWED_CHAT_ID)

        reject_query = FakeCallbackQuery(f"reject:{approval_id}", chat)
        reject_update = FakeUpdate(chat, callback_query=reject_query)
        reject_context = FakeContext(redis=redis, config=_config())
        await handlers.reject_callback(reject_update, reject_context)

        approve_query = FakeCallbackQuery(f"approve:{approval_id}", chat)
        approve_update = FakeUpdate(chat, callback_query=approve_query)
        approve_context = FakeContext(redis=redis, config=_config())
        await handlers.approve_callback(approve_update, approve_context)

        assert reject_query.edits == [("🚫 거부됨", None)]
        assert approve_query.edits == [("⌛ 만료됨", None)]
        assert await redis.xlen(final_stream) == 0


# ---------------------------------------------------------------------------
# Reject -> HDEL, no XADD
# ---------------------------------------------------------------------------


class TestRejectCallback:
    async def test_reject_deletes_pending_without_xadd(
        self, redis: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FUTURES_RISK_FILTER", "shadow")
        from services.risk_filter.main import _resolve_mode, _streams_for

        _candidate, final_stream = _streams_for(_resolve_mode())
        assert final_stream == "signal.final.futures.shadow"

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
        monkeypatch.setenv("STOCK_RISK_FILTER", "shadow")
        from services.stock_risk_filter.main import _resolve_mode, _streams_for

        _candidate, final_stream = _streams_for(_resolve_mode())
        assert final_stream == "signal.final.stock.shadow"

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
