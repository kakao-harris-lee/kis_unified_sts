"""Tests for TelegramNotifier's buy/sell signal & fill senders.

Covers the wiring added on top of `shared/notification/formatting.py`:
- message text now comes from the concise `format_*` functions.
- a Naver Finance link button is attached for 6-digit stock codes only —
  NOT for futures instrument codes (e.g. "101V3000").
- HTML-sensitive characters in dynamic fields (strategy/name) are escaped
  before formatting, since TelegramNotifier.send_message always uses
  parse_mode="HTML".
"""

from __future__ import annotations

from datetime import time
from unittest.mock import AsyncMock, patch

import pytest

from shared.notification.formatting import (
    format_buy_fill,
    format_sell_signal,
    stock_link_button,
)
from shared.notification.telegram import TelegramNotifier

_STOCK_CODE = "005930"
_FUTURES_CODE = "101V3000"

_WITHIN_ACTIVE_HOURS = time(10, 0)


def _make_notifier() -> TelegramNotifier:
    """A TelegramNotifier with a mocked bot, bypassing real network calls."""
    notifier = TelegramNotifier(bot_token="dummy_tok", chat_id="dummy_chat")
    notifier.bot = AsyncMock()
    return notifier


@pytest.fixture(autouse=True)
def _within_trading_hours():
    """Freeze the notifier's active-hours check to a time inside 08:30-15:40."""
    with patch("shared.notification.telegram.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = _WITHIN_ACTIVE_HOURS
        mock_dt.now.return_value.strftime.side_effect = lambda fmt: f"<frozen {fmt}>"
        yield


@pytest.mark.asyncio
async def test_send_buy_signal_uses_concise_formatter_and_stock_link():
    notifier = _make_notifier()

    await notifier.send_buy_signal(
        code=_STOCK_CODE,
        name="삼성전자",
        price=71200,
        strategy="bb_reversion",
        confidence=0.82,
        reason="bb_lower_touch",
    )

    notifier.bot.send_message.assert_awaited_once()
    _, kwargs = notifier.bot.send_message.call_args
    assert kwargs["parse_mode"] == "HTML"
    assert "매수 시그널" in kwargs["text"]
    assert "삼성전자" in kwargs["text"]
    assert "━━━" not in kwargs["text"]  # old hand-built divider is gone
    assert kwargs["reply_markup"] == stock_link_button(_STOCK_CODE)


@pytest.mark.asyncio
async def test_send_buy_signal_no_link_button_for_futures_code():
    notifier = _make_notifier()

    await notifier.send_buy_signal(
        code=_FUTURES_CODE,
        name="KOSPI200 선물",
        price=350.5,
        strategy="setup_a_gap_reversion",
    )

    notifier.bot.send_message.assert_awaited_once()
    _, kwargs = notifier.bot.send_message.call_args
    assert kwargs["reply_markup"] is None


@pytest.mark.asyncio
async def test_send_buy_executed_matches_formatter_output():
    notifier = _make_notifier()

    await notifier.send_buy_executed(
        code=_STOCK_CODE,
        name="삼성전자",
        price=71200,
        quantity=10,
        amount=712000,
        strategy="bb_reversion",
    )

    _, kwargs = notifier.bot.send_message.call_args
    expected_prefix = format_buy_fill(
        code=_STOCK_CODE,
        name="삼성전자",
        price=71200,
        quantity=10,
        amount=712000,
        strategy="bb_reversion",
        generated_at=None,
    ).rsplit("·", 1)[
        0
    ]  # footer timestamp is non-deterministic across calls
    assert kwargs["text"].startswith(expected_prefix)
    assert kwargs["reply_markup"] == stock_link_button(_STOCK_CODE)


@pytest.mark.asyncio
async def test_send_buy_executed_no_link_button_for_futures_code():
    notifier = _make_notifier()

    await notifier.send_buy_executed(
        code=_FUTURES_CODE,
        name="KOSPI200 선물",
        price=350.5,
        quantity=1,
        amount=350500,
        strategy="setup_a_gap_reversion",
    )

    _, kwargs = notifier.bot.send_message.call_args
    assert kwargs["reply_markup"] is None


@pytest.mark.asyncio
async def test_send_sell_signal_negative_profit_uses_red_emoji_and_stock_link():
    notifier = _make_notifier()

    await notifier.send_sell_signal(
        code=_STOCK_CODE,
        name="삼성전자",
        price=70000,
        reason="stop_loss",
        profit_rate=-0.02,
        holding_time="2h",
    )

    _, kwargs = notifier.bot.send_message.call_args
    assert kwargs["text"].startswith("🔴 매도 시그널 · 삼성전자")
    assert "-2.00%" in kwargs["text"]
    assert kwargs["reply_markup"] == stock_link_button(_STOCK_CODE)


@pytest.mark.asyncio
async def test_send_sell_signal_no_link_button_for_futures_code():
    notifier = _make_notifier()

    await notifier.send_sell_signal(
        code=_FUTURES_CODE,
        name="KOSPI200 선물",
        price=349.0,
        reason="stop_loss",
        profit_rate=-0.01,
    )

    _, kwargs = notifier.bot.send_message.call_args
    assert kwargs["reply_markup"] is None


@pytest.mark.asyncio
async def test_send_sell_executed_matches_formatter_output_and_stock_link():
    notifier = _make_notifier()

    await notifier.send_sell_executed(
        code=_STOCK_CODE,
        name="삼성전자",
        price=73000,
        quantity=10,
        amount=730000,
        profit=18000,
        profit_rate=0.025,
    )

    _, kwargs = notifier.bot.send_message.call_args
    assert kwargs["text"].startswith("✅ 매도 체결 · 삼성전자")
    assert "+18,000원" in kwargs["text"]
    assert "+2.50%" in kwargs["text"]
    assert kwargs["reply_markup"] == stock_link_button(_STOCK_CODE)


@pytest.mark.asyncio
async def test_send_sell_executed_no_link_button_for_futures_code():
    notifier = _make_notifier()

    await notifier.send_sell_executed(
        code=_FUTURES_CODE,
        name="KOSPI200 선물",
        price=349.0,
        quantity=1,
        amount=349000,
        profit=-1500,
        profit_rate=-0.005,
    )

    _, kwargs = notifier.bot.send_message.call_args
    assert kwargs["reply_markup"] is None


@pytest.mark.asyncio
async def test_send_buy_signal_escapes_html_sensitive_strategy_name():
    """A strategy/name containing HTML-sensitive chars must not break
    Telegram's HTML parse_mode or inject markup."""
    notifier = _make_notifier()

    await notifier.send_buy_signal(
        code=_STOCK_CODE,
        name="<script>alert(1)</script>",
        price=71200,
        strategy="bb<reversion>&co",
    )

    _, kwargs = notifier.bot.send_message.call_args
    text = kwargs["text"]
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "bb&lt;reversion&gt;&amp;co" in text


def test_format_sell_signal_escapes_html_sensitive_reason_directly():
    """Formatter-level check: format_sell_signal escapes free-text reason."""
    msg = format_sell_signal(
        code=_STOCK_CODE,
        name="삼성전자",
        price=70000,
        reason="<b>stop</b> & loss",
        profit_rate=-0.02,
    )
    assert "<b>stop</b>" not in msg
    assert "&lt;b&gt;stop&lt;/b&gt; &amp; loss" in msg
