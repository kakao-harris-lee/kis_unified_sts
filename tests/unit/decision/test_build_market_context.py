"""F-4: canonical MarketContext assembler + default policy."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from shared.decision.context import MarketContext, build_market_context

_NOW = datetime(2026, 6, 8, 0, 30, tzinfo=UTC)


def _base() -> dict:
    """Required builder inputs — ``vwap`` included: it has no default (F-9)."""
    return {
        "now": _NOW,
        "symbol": "A05603",
        "current_price": 331.20,
        "prev_close": 331.00,
        "today_open": 331.10,
        "atr_14": 2.0,
        "vwap": 330.40,
        "last_15min_high": 332.0,
        "last_15min_low": 330.0,
    }


def test_defaults_applied_when_omitted() -> None:
    ctx = build_market_context(**_base())
    assert isinstance(ctx, MarketContext)
    assert ctx.atr_90th_percentile == 3.0  # -> atr_14 * 1.5
    assert ctx.current_spread_ticks == 1.0  # -> 1.0
    assert ctx.scheduled_events == []


def test_vwap_is_required_and_has_no_fallback() -> None:
    """Omitting vwap raises rather than silently defaulting to current_price.

    The retired ``vwap := current_price`` fallback made Setup D's
    z = (price - vwap)/atr collapse to 0 on any producer that forgot the field
    — a silent inert, not a degraded value. Both live producers supply a real
    session VWAP now, so the omission must fail loudly.
    """
    without_vwap = {k: v for k, v in _base().items() if k != "vwap"}
    with pytest.raises(TypeError):
        build_market_context(**without_vwap)

    ctx = build_market_context(**_base())
    assert ctx.vwap == 330.40
    assert ctx.vwap != ctx.current_price


def test_explicit_values_honored() -> None:
    overrides = {k: v for k, v in _base().items() if k != "vwap"}
    ctx = build_market_context(
        **overrides, vwap=999.0, atr_90th_percentile=5.0, current_spread_ticks=2.0
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
