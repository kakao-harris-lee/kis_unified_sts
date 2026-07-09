"""Unit tests for services/telegram_bot/main.py.

Covers the inert-by-default entrypoint contract (mirrors every other daemon's
``_resolve_mode() == "off"`` inertness test convention — see e.g.
``tests/unit/stock_risk_filter/test_entrypoint.py::test_off_mode_is_inert``)
and ``build_application``'s handler wiring, WITHOUT touching the network:
``build_application`` only calls ``Application.builder().token(...).build()``
(pure local object construction — python-telegram-bot does not hit the
network until ``initialize()``/polling starts), so it is safe to call
directly with a syntactically-valid dummy token.
"""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest

import services.telegram_bot.main as m
from services.telegram_bot.config import TelegramBotConfig

# Syntactically valid (python-telegram-bot validates the "digits:token" shape
# locally, no network call) but not a real bot token.
_DUMMY_TOKEN = "123456:ABCDEFabcdefABCDEFabcdefABCDEFabcde"


def test_inert_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        TelegramBotConfig,
        "from_yaml",
        classmethod(lambda cls, *a, **k: TelegramBotConfig(enabled=False)),
    )
    rc = asyncio.run(m._build_and_run())
    assert rc == 0


def test_inert_when_no_allowed_chat_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        TelegramBotConfig,
        "from_yaml",
        classmethod(
            lambda cls, *a, **k: TelegramBotConfig(enabled=True, allowed_chat_ids=[])
        ),
    )
    rc = asyncio.run(m._build_and_run())
    assert rc == 0


def test_inert_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        TelegramBotConfig,
        "from_yaml",
        classmethod(
            lambda cls, *a, **k: TelegramBotConfig(
                enabled=True, allowed_chat_ids=["111"]
            )
        ),
    )
    monkeypatch.delenv("TELEGRAM_STOCK_BOT_TOKEN", raising=False)
    rc = asyncio.run(m._build_and_run())
    assert rc == 0


def test_build_application_registers_all_handlers() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    config = TelegramBotConfig(enabled=True, allowed_chat_ids=["111"])

    application = m.build_application(token=_DUMMY_TOKEN, redis=redis, config=config)

    assert application.bot_data["redis"] is redis
    assert application.bot_data["config"] is config
    # 4 command handlers (/positions, /pending, /help, /start) + 3 callback
    # handlers (approve/reject/close) share telegram's default group (0).
    handlers_in_group_0 = application.handlers[0]
    assert len(handlers_in_group_0) == 7
