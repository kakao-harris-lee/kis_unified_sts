"""Hermetic tests for the ORB trend-day entry.

The entry is stateful (per-day opening range + rolling closes for the efficiency
ratio), so each test drives a sequence of bars through ``generate`` and asserts on
the first emitted signal. Bars are KST-native (futures open 08:45). Indicators are
supplied directly (hermetic — no StreamingIndicatorEngine), matching the live
contract: base ``atr`` in points, ``macd_hist``, and ``market_state`` in metadata.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.orb_trend_day import (
    OpeningRangeBreakoutTrendConfig,
    OpeningRangeBreakoutTrendEntry,
)

KST = timezone(timedelta(hours=9))
ATR = 1.0  # 1 index point — keeps thresholds easy to reason about


def _cfg(**overrides) -> OpeningRangeBreakoutTrendConfig:
    base = {
        "timeframe_minutes": 5,
        "opening_range_minutes": 30,
        "no_entry_after_minutes": 300,
        "min_or_atr_mult": 0.8,
        "min_atr_norm": 0.0,  # disable the comatose-session floor for unit clarity
        # Realistic window: long enough that a single opening poke cannot dominate
        # the efficiency ratio (a too-short window lets the first breakout bar pass
        # before chop is established — see test_efficiency_ratio_window_sizing).
        "efficiency_window": 8,
        "min_efficiency": 0.35,
        "breakout_buffer_atr_mult": 0.25,
        "use_mfi_gate": True,
        "use_macd_slope_gate": True,
        "daily_bias_filter_enabled": False,
        "market_open_hour": 8,
        "market_open_minute": 45,
        "stop_atr_mult": 1.5,
        "allow_long": True,
        "allow_short": True,
    }
    base.update(overrides)
    return OpeningRangeBreakoutTrendConfig(**base)


def _ctx(
    *,
    minute_offset: int,
    close: float,
    high: float | None = None,
    low: float | None = None,
    macd_hist: float = 1.0,
    market_state: str = "BULL_STRONG",
    atr: float = ATR,
    open_h: int = 8,
    open_m: int = 45,
    daily_bias: str | None = None,
) -> EntryContext:
    ts = datetime(2026, 1, 5, open_h, open_m, tzinfo=KST) + timedelta(
        minutes=minute_offset
    )
    high = close if high is None else high
    low = close if low is None else low
    meta = {"market_state": market_state}
    if daily_bias is not None:
        meta["daily_bias"] = daily_bias
    return EntryContext(
        market_data={
            "code": "101S6000",
            "name": "KOSPI200",
            "close": close,
            "high": high,
            "low": low,
        },
        indicators={"atr": atr, "macd_hist": macd_hist, "close": close},
        timestamp=ts,
        metadata=meta,
    )


async def _drive_trend_up(
    entry, *, start_minute=0, bars=12, base=600.0, step=2.0, **ctx_overrides
):
    """Drive a clean up-trend day. Returns the first emitted signal (or None).

    Opening range (first 30 min) is built flat-ish at ``base``; after the range
    closes price marches up by ``step`` each 5-min bar (high efficiency).
    """
    signal = None
    # Opening range: 6 bars over 30 min, small oscillation so OR height ~ 1 ATR.
    or_prices = [base, base + 0.6, base - 0.4, base + 0.5, base - 0.3, base + 0.2]
    minute = start_minute
    for p in or_prices:
        ctx = _ctx(
            minute_offset=minute, close=p, high=p + 0.3, low=p - 0.3, **ctx_overrides
        )
        s = await entry.generate(ctx)
        signal = signal or s
        minute += 5
    # Post-range: steady march up (efficiency ratio -> ~1).
    price = base
    for i in range(bars):
        price = base + step * (i + 1)
        ctx = _ctx(
            minute_offset=minute,
            close=price,
            high=price + 0.2,
            low=price - 0.2,
            **ctx_overrides,
        )
        s = await entry.generate(ctx)
        if signal is None and s is not None:
            signal = s
        minute += 5
    return signal


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


async def test_clean_uptrend_fires_long():
    entry = OpeningRangeBreakoutTrendEntry(_cfg())
    sig = await _drive_trend_up(entry)
    assert sig is not None, "clean up-trend day should fire a long entry"
    assert sig.metadata["signal_direction"] == "long"
    assert sig.strategy == "orb_trend_day"
    assert sig.metadata["stop_loss"] < sig.price  # long stop below entry
    assert sig.metadata["efficiency_ratio"] >= 0.35


async def test_clean_downtrend_fires_short():
    """Long/short symmetry: a mirror-image down-trend day fires a short."""
    entry = OpeningRangeBreakoutTrendEntry(_cfg())
    signal = None
    base = 600.0
    or_prices = [base, base - 0.6, base + 0.4, base - 0.5, base + 0.3, base - 0.2]
    minute = 0
    for p in or_prices:
        s = await entry.generate(
            _ctx(
                minute_offset=minute,
                close=p,
                high=p + 0.3,
                low=p - 0.3,
                macd_hist=-1.0,
                market_state="BEAR_STRONG",
            )
        )
        signal = signal or s
        minute += 5
    for i in range(12):
        price = base - 2.0 * (i + 1)
        s = await entry.generate(
            _ctx(
                minute_offset=minute,
                close=price,
                high=price + 0.2,
                low=price - 0.2,
                macd_hist=-1.0,
                market_state="BEAR_STRONG",
            )
        )
        signal = signal or s
        minute += 5
    assert signal is not None, "clean down-trend day should fire a short entry"
    assert signal.metadata["signal_direction"] == "short"
    assert signal.metadata["stop_loss"] > signal.price  # short stop above entry


# ---------------------------------------------------------------------------
# The GATE — chop-day rejection (the whole point)
# ---------------------------------------------------------------------------


async def test_chop_day_no_entry():
    """A choppy session must NOT fire — net displacement stays small vs path length.

    A genuine chop day travels a long path with little net move (low Kaufman ER).
    Each bar pokes just past the opening-range edge but the window keeps reversing,
    so the efficiency ratio never clears ``min_efficiency``.
    """
    entry = OpeningRangeBreakoutTrendEntry(_cfg())
    base = 600.0
    minute = 0
    # Opening range.
    for p in [base, base + 0.6, base - 0.4, base + 0.5, base - 0.3, base + 0.2]:
        await entry.generate(
            _ctx(minute_offset=minute, close=p, high=p + 0.3, low=p - 0.3)
        )
        minute += 5
    # Post-range: tight whipsaw straddling the range edge (601.2 high / 599.0 low).
    # Big bar-to-bar moves (long path) but the window oscillates → net move ~0.
    fired = []
    for p in [601.2, 599.0, 601.1, 599.1, 601.2, 599.0, 601.1, 599.0, 601.2, 599.1]:
        s = await entry.generate(
            _ctx(minute_offset=minute, close=float(p), high=p + 0.5, low=p - 0.5)
        )
        if s is not None:
            fired.append(s)
        minute += 5
    assert fired == [], "choppy day must be rejected by the efficiency gate"


async def test_flat_opening_range_rejected_by_vol_expansion():
    """A dead-flat opening range fails the vol-expansion gate even if trend follows."""
    entry = OpeningRangeBreakoutTrendEntry(_cfg(min_or_atr_mult=2.0))  # demand big OR
    sig = await _drive_trend_up(entry, base=600.0, step=2.0)
    assert sig is None, "tiny opening range should block entry via vol-expansion gate"


# ---------------------------------------------------------------------------
# Direction-agreement gates
# ---------------------------------------------------------------------------


async def test_mfi_gate_blocks_long_in_bear_regime():
    entry = OpeningRangeBreakoutTrendEntry(_cfg())
    sig = await _drive_trend_up(entry, market_state="BEAR_STRONG")
    assert sig is None, "long break in a BEAR_STRONG regime must be blocked by MFI gate"


async def test_macd_slope_gate_blocks_long_when_negative():
    entry = OpeningRangeBreakoutTrendEntry(_cfg())
    sig = await _drive_trend_up(entry, macd_hist=-0.5)
    assert sig is None, "long break with negative MACD hist must be blocked"


async def test_daily_bias_gate_blocks_misaligned():
    entry = OpeningRangeBreakoutTrendEntry(_cfg(daily_bias_filter_enabled=True))
    sig = await _drive_trend_up(entry, daily_bias="short")  # bias disagrees with long
    assert sig is None, "daily bias 'short' must block a long break"


async def test_daily_bias_permissive_when_flat():
    entry = OpeningRangeBreakoutTrendEntry(_cfg(daily_bias_filter_enabled=True))
    sig = await _drive_trend_up(entry, daily_bias="flat")
    assert sig is not None, "flat/null daily bias must be permissive (not block)"


# ---------------------------------------------------------------------------
# Structural guards
# ---------------------------------------------------------------------------


async def test_one_entry_per_direction_per_day():
    """After firing long, a second long break on the same day must not re-fire."""
    entry = OpeningRangeBreakoutTrendEntry(_cfg())
    first = await _drive_trend_up(entry, bars=12)
    assert first is not None
    # Continue the same day with more up-bars; no new signal expected.
    more = []
    minute = 30 + 12 * 5
    price = 600.0 + 2.0 * 12
    for _ in range(6):
        price += 2.0
        s = await entry.generate(
            _ctx(minute_offset=minute, close=price, high=price + 0.2, low=price - 0.2)
        )
        if s is not None:
            more.append(s)
        minute += 5
    assert more == [], "must not re-enter the same direction the same day"


async def test_no_entry_before_opening_range_completes():
    entry = OpeningRangeBreakoutTrendEntry(_cfg())
    # A strong break at minute 10 (inside the 30-min opening range) must not fire.
    for minute in (0, 5, 10):
        s = await entry.generate(
            _ctx(
                minute_offset=minute,
                close=600.0 + minute,
                high=600.0 + minute,
                low=599.0,
            )
        )
        assert s is None, "no entry while the opening range is still forming"


async def test_no_entry_after_cutoff():
    entry = OpeningRangeBreakoutTrendEntry(_cfg(no_entry_after_minutes=60))
    # Build OR then attempt a clean break well after the 60-min cutoff.
    base = 600.0
    minute = 0
    for p in [base, base + 0.6, base - 0.4, base + 0.5, base - 0.3, base + 0.2]:
        await entry.generate(
            _ctx(minute_offset=minute, close=p, high=p + 0.3, low=p - 0.3)
        )
        minute += 5
    # Jump to minute 120 with a clean march — past cutoff.
    fired = []
    for i in range(6):
        price = base + 2.0 * (i + 1)
        s = await entry.generate(
            _ctx(
                minute_offset=120 + i * 5,
                close=price,
                high=price + 0.2,
                low=price - 0.2,
            )
        )
        if s is not None:
            fired.append(s)
    assert fired == [], "no new entries after the session cutoff"


async def test_allow_short_false_blocks_short():
    entry = OpeningRangeBreakoutTrendEntry(_cfg(allow_short=False))
    base = 600.0
    minute = 0
    for p in [base, base - 0.6, base + 0.4, base - 0.5, base + 0.3, base - 0.2]:
        await entry.generate(
            _ctx(
                minute_offset=minute,
                close=p,
                high=p + 0.3,
                low=p - 0.3,
                macd_hist=-1.0,
                market_state="BEAR_STRONG",
            )
        )
        minute += 5
    fired = []
    for i in range(8):
        price = base - 2.0 * (i + 1)
        s = await entry.generate(
            _ctx(
                minute_offset=minute,
                close=price,
                high=price + 0.2,
                low=price - 0.2,
                macd_hist=-1.0,
                market_state="BEAR_STRONG",
            )
        )
        if s is not None:
            fired.append(s)
        minute += 5
    assert fired == [], "allow_short=False must suppress short entries"


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def test_efficiency_ratio_window_sizing():
    """ER: clean trend -> ~1; whipsaw -> ~0; degenerate flat -> 0.

    Also documents the window-sizing lesson: a single sharp poke off a flat base
    can look efficient in a *short* window, so the production window (12 bars) is
    sized to dilute it.
    """
    er = OpeningRangeBreakoutTrendEntry._efficiency_ratio
    trend = [600 + i for i in range(9)]  # monotone up
    assert er(trend, 8) == pytest.approx(1.0)
    chop = [600, 601, 600, 601, 600, 601, 600, 601, 600]  # straddle
    assert er(chop, 8) < 0.2
    flat = [600.0] * 9
    assert er(flat, 8) == 0.0
    # Too few closes -> 0.0 (cannot trust a half-filled window).
    assert er([600, 601, 602], 8) == 0.0


def test_config_validation_rejects_bad_efficiency():
    with pytest.raises(AssertionError):
        OpeningRangeBreakoutTrendEntry(_cfg(min_efficiency=1.5))


def test_config_validation_rejects_no_side():
    with pytest.raises(AssertionError):
        OpeningRangeBreakoutTrendEntry(_cfg(allow_long=False, allow_short=False))
