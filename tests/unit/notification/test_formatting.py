"""Tests for shared/notification/formatting.py — concise message + keyboards."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from telegram import InlineKeyboardMarkup

from shared.notification.formatting import (
    CALLBACK_DATA_MAX_BYTES,
    approval_buttons,
    close_button,
    format_buy_fill,
    format_buy_signal,
    format_sell_fill,
    format_sell_signal,
    is_stock_code,
    naver_stock_url,
    stock_link_button,
)

_GENERATED_AT = datetime(2026, 7, 7, 10, 32, tzinfo=UTC)


def test_naver_stock_url_formats_code():
    assert (
        naver_stock_url("005930")
        == "https://finance.naver.com/item/main.naver?code=005930"
    )


def test_stock_link_button_is_url_button():
    markup = stock_link_button("005930")
    assert isinstance(markup, InlineKeyboardMarkup)
    button = markup.inline_keyboard[0][0]
    assert button.url == naver_stock_url("005930")


def test_approval_buttons_callback_data_scheme():
    markup = approval_buttons("stock:abc123")
    approve, reject = markup.inline_keyboard[0]
    assert approve.callback_data == "approve:stock:abc123"
    assert reject.callback_data == "reject:stock:abc123"


def test_close_button_callback_data_scheme():
    markup = close_button("futures", "101V3000")
    (button,) = markup.inline_keyboard[0]
    assert button.callback_data == "close:futures:101V3000"


def test_callback_data_within_telegram_limit_for_realistic_ids():
    # uuid4().hex is 32 hex chars — the realistic worst case for signal ids.
    signal_id = "a" * 32
    markup = approval_buttons(f"futures:{signal_id}")
    for button in markup.inline_keyboard[0]:
        assert len(button.callback_data.encode("utf-8")) <= CALLBACK_DATA_MAX_BYTES


def test_approval_buttons_raises_over_callback_data_limit():
    too_long_id = "asset:" + "x" * 100
    with pytest.raises(ValueError, match="64-byte"):
        approval_buttons(too_long_id)


def test_format_buy_signal_three_lines_with_header_numbers_footer():
    msg = format_buy_signal(
        code="005930",
        name="삼성전자",
        price=71200,
        strategy="bb_reversion",
        confidence=0.82,
        reason="bb_lower_touch",
        generated_at=_GENERATED_AT,
    )
    lines = msg.splitlines()
    assert lines[0] == "🟢 매수 시그널 · 삼성전자"
    assert "005930" in lines[1]
    assert "71,200원" in lines[1]
    assert "82%" in lines[1]
    assert lines[2] == "bb_reversion · 10:32"


def test_format_sell_signal_negative_profit_uses_red_emoji():
    msg = format_sell_signal(
        code="005930",
        name="삼성전자",
        price=70000,
        reason="stop_loss",
        profit_rate=-0.02,
        strategy="bb_reversion",
        generated_at=_GENERATED_AT,
    )
    assert msg.startswith("🔴 매도 시그널 · 삼성전자")
    assert "-2.00%" in msg


def test_format_sell_signal_positive_profit_uses_yellow_emoji():
    msg = format_sell_signal(
        code="005930",
        name="삼성전자",
        price=73000,
        reason="take_profit",
        profit_rate=0.03,
        generated_at=_GENERATED_AT,
    )
    assert msg.startswith("🟡 매도 시그널 · 삼성전자")
    assert "+3.00%" in msg


def test_format_buy_fill_matches_design_doc_example():
    msg = format_buy_fill(
        code="005930",
        name="삼성전자",
        price=71200,
        quantity=10,
        amount=712000,
        strategy="bb_reversion",
        generated_at=_GENERATED_AT,
    )
    assert msg == (
        "✅ 매수 체결 · 삼성전자\n"
        "005930 · 10주 @ 71,200 (712,000원)\n"
        "bb_reversion · 10:32"
    )


def test_format_sell_fill_profit_positive_sign_and_emoji():
    msg = format_sell_fill(
        code="005930",
        name="삼성전자",
        price=73000,
        quantity=10,
        amount=730000,
        profit=18000,
        profit_rate=0.025,
        strategy="bb_reversion",
        generated_at=_GENERATED_AT,
    )
    assert msg.startswith("✅ 매도 체결 · 삼성전자")
    assert "+18,000원" in msg
    assert "+2.50%" in msg


def test_format_sell_fill_loss_uses_cross_emoji_no_sign():
    msg = format_sell_fill(
        code="005930",
        name="삼성전자",
        price=69000,
        quantity=10,
        amount=690000,
        profit=-20000,
        profit_rate=-0.028,
        generated_at=_GENERATED_AT,
    )
    assert msg.startswith("❌ 매도 체결 · 삼성전자")
    assert "-20,000원" in msg
    assert "-2.80%" in msg


def test_format_buy_signal_defaults_footer_to_current_kst_when_no_timestamp():
    msg = format_buy_signal(
        code="005930",
        name="삼성전자",
        price=71200,
        strategy="bb_reversion",
    )
    footer = msg.splitlines()[-1]
    assert footer.startswith("bb_reversion · ")


# ---------------------------------------------------------------------------
# is_stock_code — stock vs futures code-shape guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", ["005930", "000660", "123456"])
def test_is_stock_code_true_for_six_digit_codes(code):
    assert is_stock_code(code) is True


@pytest.mark.parametrize(
    "code",
    [
        "101V3000",  # futures instrument code (alphanumeric)
        "101S6000",
        "12345",  # too short
        "1234567",  # too long
        "",
    ],
)
def test_is_stock_code_false_for_non_stock_shapes(code):
    assert is_stock_code(code) is False


# ---------------------------------------------------------------------------
# HTML escaping — parse_mode="HTML" safety for dynamic free-text fields
# ---------------------------------------------------------------------------


def test_format_buy_signal_escapes_html_sensitive_name_and_strategy():
    msg = format_buy_signal(
        code="005930",
        name="<b>탈출</b>",
        price=71200,
        strategy="bb & reversion",
        reason="a<b",
    )
    assert "<b>탈출</b>" not in msg
    assert "&lt;b&gt;탈출&lt;/b&gt;" in msg
    assert "bb &amp; reversion" in msg
    assert "a&lt;b" in msg


def test_format_sell_fill_escapes_html_sensitive_strategy():
    msg = format_sell_fill(
        code="005930",
        name="삼성전자",
        price=73000,
        quantity=10,
        amount=730000,
        profit=18000,
        profit_rate=0.025,
        strategy="<i>fast exit</i>",
    )
    assert "<i>fast exit</i>" not in msg
    assert "&lt;i&gt;fast exit&lt;/i&gt;" in msg
