"""F-4: canonical MarketContext assembler + default policy."""

from __future__ import annotations

from datetime import UTC, datetime

from shared.decision.context import MarketContext, build_market_context

_NOW = datetime(2026, 6, 8, 0, 30, tzinfo=UTC)


def _base() -> dict:
    return {
        "now": _NOW,
        "symbol": "A05603",
        "current_price": 331.20,
        "prev_close": 331.00,
        "today_open": 331.10,
        "atr_14": 2.0,
        "last_15min_high": 332.0,
        "last_15min_low": 330.0,
    }


def test_defaults_applied_when_omitted() -> None:
    ctx = build_market_context(**_base())
    assert isinstance(ctx, MarketContext)
    assert ctx.vwap == 331.20  # -> current_price
    assert ctx.atr_90th_percentile == 3.0  # -> atr_14 * 1.5
    assert ctx.current_spread_ticks == 1.0  # -> 1.0
    assert ctx.scheduled_events == []


def test_explicit_values_honored() -> None:
    ctx = build_market_context(
        **_base(), vwap=999.0, atr_90th_percentile=5.0, current_spread_ticks=2.0
    )
    assert ctx.vwap == 999.0
    assert ctx.atr_90th_percentile == 5.0
    assert ctx.current_spread_ticks == 2.0


def test_core_fields_passed_through() -> None:
    ctx = build_market_context(**_base())
    assert ctx.now == _NOW
    assert ctx.symbol == "A05603"
    assert ctx.current_price == 331.20
    assert ctx.prev_close == 331.00
    assert ctx.today_open == 331.10
    assert ctx.atr_14 == 2.0
    assert ctx.last_15min_high == 332.0
    assert ctx.last_15min_low == 330.0
    assert ctx.macro_overnight is None
