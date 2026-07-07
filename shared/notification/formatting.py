"""Deterministic, concise Telegram message formatting (NO LLM).

Companion to ``shared/notification/telegram.py``: that module owns *delivery*
(``TelegramNotifier.send_message`` et al.); this module owns *content* — the
concise "header / numbers-line / strategy·time" style adopted in
``docs/plans/2026-07-07-telegram-interactive-alerts-design.md`` to replace the
old hand-built multi-line ``━━━``-divided strings, plus the inline-keyboard
builders needed for the interactive-alerts feature (Naver Finance link,
approve/reject, close-position).

callback_data scheme (bot-service handlers MUST parse exactly this):
    ``approve:{approval_id}``   — approve a pending signal.
    ``reject:{approval_id}``    — reject / discard a pending signal.
    ``close:{asset}:{code}``    — close an open position.

    ``approval_id`` is ``"{asset}:{signal_id}"`` (see
    :func:`shared.streaming.approval_keys.approval_field_id`) — it already
    contains a colon, so a callback_data of ``"approve:stock:ab12cd34"``
    is parsed by splitting on the FIRST colon only:
    ``action, approval_id = callback_data.split(":", 1)``. For ``close``,
    split on the first TWO colons: ``_, asset, code = callback_data.split(
    ":", 2)``. Every builder in this module runs its output through
    :func:`_callback_data`, which raises if the encoded value would exceed
    Telegram's :data:`CALLBACK_DATA_MAX_BYTES` (64-byte) limit — signal ids
    are ``uuid4().hex`` (32 hex chars), so worst case
    (``"approve:futures:" + 32 hex chars`` = 48 bytes) is comfortably under
    the limit.
"""

from __future__ import annotations

from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from shared.strategy.market_time import now_kst

# Telegram inline-keyboard callback_data hard limit (UTF-8 encoded bytes).
CALLBACK_DATA_MAX_BYTES = 64

_APPROVE_PREFIX = "approve:"
_REJECT_PREFIX = "reject:"
_CLOSE_PREFIX = "close:"

_NAVER_STOCK_URL_TEMPLATE = "https://finance.naver.com/item/main.naver?code={code}"


def _callback_data(value: str) -> str:
    """Return *value* unchanged, or raise if it exceeds Telegram's byte limit.

    Args:
        value: Candidate callback_data string.

    Returns:
        *value*, unchanged.

    Raises:
        ValueError: If the UTF-8 encoded length exceeds
            :data:`CALLBACK_DATA_MAX_BYTES`.
    """
    encoded_len = len(value.encode("utf-8"))
    if encoded_len > CALLBACK_DATA_MAX_BYTES:
        raise ValueError(
            f"callback_data exceeds Telegram's {CALLBACK_DATA_MAX_BYTES}-byte "
            f"limit ({encoded_len} bytes): {value!r}"
        )
    return value


def _hhmm(generated_at: datetime | None) -> str:
    """Return ``HH:MM`` for *generated_at*, defaulting to the current KST time.

    CLAUDE.md: trading/session logic is KST-native. A naive *generated_at* is
    formatted as-is (assumed already KST by the caller); only the default
    (``None``) path explicitly resolves KST "now".
    """
    moment = generated_at if generated_at is not None else now_kst()
    return moment.strftime("%H:%M")


def _footer(strategy: str, generated_at: datetime | None) -> str:
    """Return the common ``strategy · HH:MM`` footer line.

    Falls back to just ``HH:MM`` when *strategy* is blank (e.g. a sell signal
    triggered by a generic exit reason rather than an entry strategy name).
    """
    ts = _hhmm(generated_at)
    return f"{strategy} · {ts}" if strategy else ts


# ---------------------------------------------------------------------------
# Context links
# ---------------------------------------------------------------------------


def naver_stock_url(code: str) -> str:
    """Return the Naver Finance stock page URL for *code*.

    Args:
        code: Stock symbol/code, e.g. ``"005930"``.

    Returns:
        ``https://finance.naver.com/item/main.naver?code={code}``.
    """
    return _NAVER_STOCK_URL_TEMPLATE.format(code=code)


# ---------------------------------------------------------------------------
# Inline keyboards
# ---------------------------------------------------------------------------


def stock_link_button(code: str) -> InlineKeyboardMarkup:
    """Return a one-button keyboard linking to the Naver Finance page for *code*."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📊 네이버 증권", url=naver_stock_url(code))]]
    )


def approval_buttons(approval_id: str) -> InlineKeyboardMarkup:
    """Return the [승인]/[거부] keyboard for a pending-approval signal.

    Args:
        approval_id: ``"{asset}:{signal_id}"``, as returned by
            :func:`shared.streaming.approval_gate.record_pending`.

    Returns:
        A two-button row: ``approve:{approval_id}`` / ``reject:{approval_id}``
        callback_data.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ 승인",
                    callback_data=_callback_data(f"{_APPROVE_PREFIX}{approval_id}"),
                ),
                InlineKeyboardButton(
                    "❌ 거부",
                    callback_data=_callback_data(f"{_REJECT_PREFIX}{approval_id}"),
                ),
            ]
        ]
    )


def close_button(asset: str, code: str) -> InlineKeyboardMarkup:
    """Return a one-button [청산] keyboard for closing an open position.

    Args:
        asset: Asset class, e.g. ``"stock"`` or ``"futures"``.
        code: Position symbol/code.

    Returns:
        A single-button row with ``close:{asset}:{code}`` callback_data.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔴 청산",
                    callback_data=_callback_data(f"{_CLOSE_PREFIX}{asset}:{code}"),
                )
            ]
        ]
    )


# ---------------------------------------------------------------------------
# Concise message formatters
# ---------------------------------------------------------------------------
#
# Every formatter renders exactly 3 lines:
#   1. "{emoji} {event} · {name}"
#   2. compact numbers line
#   3. "{strategy} · HH:MM" (see _footer)


def format_buy_signal(
    *,
    code: str,
    name: str,
    price: float,
    strategy: str,
    confidence: float | None = None,
    reason: str | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Format a buy-signal notification (see module docstring for the style)."""
    header = f"🟢 매수 시그널 · {name}"
    parts = [code, f"{price:,.0f}원"]
    if confidence is not None:
        parts.append(f"신뢰도 {confidence:.0%}")
    if reason:
        parts.append(reason)
    numbers = " · ".join(parts)
    return "\n".join([header, numbers, _footer(strategy, generated_at)])


def format_sell_signal(
    *,
    code: str,
    name: str,
    price: float,
    reason: str,
    profit_rate: float | None = None,
    holding_time: str | None = None,
    strategy: str = "",
    generated_at: datetime | None = None,
) -> str:
    """Format a sell-signal notification.

    Emoji mirrors the legacy ``TelegramNotifier.send_sell_signal`` logic:
    🔴 when *profit_rate* is known and negative, 🟡 otherwise.
    """
    emoji = "🔴" if profit_rate is not None and profit_rate < 0 else "🟡"
    header = f"{emoji} 매도 시그널 · {name}"
    parts = [code, f"{price:,.0f}원"]
    if profit_rate is not None:
        sign = "+" if profit_rate >= 0 else ""
        parts.append(f"{sign}{profit_rate:.2%}")
    parts.append(reason)
    if holding_time:
        parts.append(holding_time)
    numbers = " · ".join(parts)
    return "\n".join([header, numbers, _footer(strategy, generated_at)])


def format_buy_fill(
    *,
    code: str,
    name: str,
    price: float,
    quantity: int,
    amount: float,
    strategy: str,
    generated_at: datetime | None = None,
) -> str:
    """Format a buy-fill notification.

    Example (see design doc)::

        ✅ 매수 체결 · 삼성전자
        005930 · 10주 @ 71,200 (712,000원)
        bb_reversion · 10:32
    """
    header = f"✅ 매수 체결 · {name}"
    numbers = f"{code} · {quantity}주 @ {price:,.0f} ({amount:,.0f}원)"
    return "\n".join([header, numbers, _footer(strategy, generated_at)])


def format_sell_fill(
    *,
    code: str,
    name: str,
    price: float,
    quantity: int,
    amount: float,
    profit: float,
    profit_rate: float,
    strategy: str = "",
    generated_at: datetime | None = None,
) -> str:
    """Format a sell-fill notification.

    Emoji/sign mirror the legacy ``TelegramNotifier.send_sell_executed``
    logic: ✅/+ when *profit* is non-negative, ❌ (no sign) otherwise.
    """
    emoji = "✅" if profit >= 0 else "❌"
    sign = "+" if profit >= 0 else ""
    header = f"{emoji} 매도 체결 · {name}"
    numbers = (
        f"{code} · {quantity}주 @ {price:,.0f} ({amount:,.0f}원) · "
        f"{sign}{profit:,.0f}원 ({sign}{profit_rate:.2%})"
    )
    return "\n".join([header, numbers, _footer(strategy, generated_at)])
