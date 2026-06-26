"""Unit tests for CTAMomentumEntry (daily/swing TS-momentum, roll-aware).

Hermetic: synthetic close/date series only — no real data, no network.
"""

from __future__ import annotations

import asyncio
import math
from datetime import UTC, date, datetime

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.cta_momentum import (
    CTAMomentumConfig,
    CTAMomentumEntry,
    is_quarterly_roll_day,
    roll_aware_log_returns,
)

# ---------------------------------------------------------------------------
# Roll-day detection
# ---------------------------------------------------------------------------


def test_quarterly_roll_day_is_second_thursday():
    # 2024: 2nd Thursdays of Mar/Jun/Sep/Dec.
    assert is_quarterly_roll_day(date(2024, 3, 14))
    assert is_quarterly_roll_day(date(2024, 6, 13))
    assert is_quarterly_roll_day(date(2024, 9, 12))
    assert is_quarterly_roll_day(date(2024, 12, 12))


def test_non_roll_days_rejected():
    assert not is_quarterly_roll_day(date(2024, 6, 12))  # Wednesday before
    assert not is_quarterly_roll_day(date(2024, 6, 6))  # 1st Thursday
    assert not is_quarterly_roll_day(date(2024, 6, 20))  # 3rd Thursday
    assert not is_quarterly_roll_day(date(2024, 7, 11))  # non-quarterly month


def test_exactly_four_roll_days_per_year():
    for year in range(2010, 2027):
        days = [date(year, m, d) for m in (3, 6, 9, 12) for d in range(1, 29)]
        rolls = [d for d in days if is_quarterly_roll_day(d)]
        assert len(rolls) == 4, (year, rolls)


# ---------------------------------------------------------------------------
# Roll-aware returns
# ---------------------------------------------------------------------------


def test_roll_aware_returns_zero_on_roll_day():
    # A big jump landing on a roll day must be neutralised to 0.
    dates = [date(2024, 6, 12), date(2024, 6, 13)]  # 2nd is a roll day
    closes = [300.0, 360.0]  # +20% step (carry spread, not momentum)
    rets = roll_aware_log_returns(closes, dates)
    assert rets[0] == 0.0
    assert rets[1] == 0.0  # neutralised


def test_roll_aware_returns_normal_on_non_roll_day():
    dates = [date(2024, 6, 11), date(2024, 6, 12)]  # neither is a roll day
    closes = [300.0, 303.0]
    rets = roll_aware_log_returns(closes, dates)
    assert rets[1] == pytest.approx(math.log(303.0 / 300.0))


def test_roll_aware_returns_guards_nonpositive():
    dates = [date(2024, 7, 1), date(2024, 7, 2)]
    rets = roll_aware_log_returns([300.0, 0.0], dates)
    assert rets[1] == 0.0


# ---------------------------------------------------------------------------
# Direction logic
# ---------------------------------------------------------------------------


def _dates(n: int, start: date = date(2020, 1, 1)) -> list[date]:
    # Plain calendar days; roll-day logic is tested separately. Avoid quarterly
    # roll months so the synthetic trend is not partially neutralised.
    out: list[date] = []
    d = start
    import datetime as _dt

    while len(out) < n:
        if d.month not in (3, 6, 9, 12):
            out.append(d)
        d = d + _dt.timedelta(days=1)
    return out


def _uptrend(n: int, start: float = 300.0, step: float = 1.0) -> list[float]:
    return [start + i * step for i in range(n)]


def _downtrend(n: int, start: float = 600.0, step: float = 1.0) -> list[float]:
    return [start - i * step for i in range(n)]


def test_direction_long_on_uptrend():
    cfg = CTAMomentumConfig(
        momentum_lookback=20, ma_fast_period=5, ma_slow_period=20, min_bars=21
    )
    entry = CTAMomentumEntry(cfg)
    n = 60
    assert entry.evaluate_direction(_uptrend(n), _dates(n)) == "long"


def test_direction_short_on_downtrend():
    cfg = CTAMomentumConfig(
        momentum_lookback=20, ma_fast_period=5, ma_slow_period=20, min_bars=21
    )
    entry = CTAMomentumEntry(cfg)
    n = 60
    assert entry.evaluate_direction(_downtrend(n), _dates(n)) == "short"


def test_direction_none_when_ma_disagrees_with_momentum():
    # Construct: positive long-run momentum (start << end) but a mild recent dip
    # that pulls the fast SMA below the slow SMA → regime veto → None.
    cfg = CTAMomentumConfig(
        momentum_lookback=40, ma_fast_period=5, ma_slow_period=20, min_bars=41
    )
    entry = CTAMomentumEntry(cfg)
    n = 60
    closes = _uptrend(n, start=300.0, step=2.0)  # strong overall uptrend
    # Mild pullback over the last 6 bars: enough to flip fast<slow, small enough
    # that the 40-bar momentum (close[-1] vs close[-41]) stays clearly positive.
    peak = closes[n - 7]
    for k, i in enumerate(range(n - 6, n)):
        closes[i] = peak - (k + 1) * 7.0
    # sanity: 40d momentum still positive, fast SMA below slow SMA.
    assert closes[-1] > closes[-41]
    fast = sum(closes[-5:]) / 5
    slow = sum(closes[-20:]) / 20
    assert fast < slow
    direction = entry.evaluate_direction(closes, _dates(n))
    assert direction is None


def test_direction_none_below_min_bars():
    cfg = CTAMomentumConfig(min_bars=120)
    entry = CTAMomentumEntry(cfg)
    assert entry.evaluate_direction(_uptrend(50), _dates(50)) is None


def test_deadband_suppresses_flat_series():
    cfg = CTAMomentumConfig(
        momentum_lookback=20,
        use_ma_filter=False,
        momentum_deadband=0.05,
        ma_slow_period=20,
        min_bars=21,
    )
    entry = CTAMomentumEntry(cfg)
    n = 40
    flat = [300.0] * n  # zero momentum
    assert entry.evaluate_direction(flat, _dates(n)) is None


def test_allow_short_false_blocks_short():
    cfg = CTAMomentumConfig(
        momentum_lookback=20,
        ma_fast_period=5,
        ma_slow_period=20,
        min_bars=21,
        allow_short=False,
    )
    entry = CTAMomentumEntry(cfg)
    n = 60
    assert entry.evaluate_direction(_downtrend(n), _dates(n)) is None


# ---------------------------------------------------------------------------
# Wilder ATR
# ---------------------------------------------------------------------------


def test_wilder_atr_constant_range():
    cfg = CTAMomentumConfig(atr_period=5, min_bars=120)
    entry = CTAMomentumEntry(cfg)
    n = 30
    closes = [300.0] * n
    highs = [301.0] * n
    lows = [299.0] * n
    atr = entry.wilder_atr(highs, lows, closes)
    # TR each day = max(2, |301-300|, |299-300|) = 2 → ATR == 2.
    assert atr == pytest.approx(2.0)


def test_wilder_atr_none_when_short():
    cfg = CTAMomentumConfig(atr_period=20, min_bars=120)
    entry = CTAMomentumEntry(cfg)
    assert entry.wilder_atr([1.0] * 5, [1.0] * 5, [1.0] * 5) is None


# ---------------------------------------------------------------------------
# Async generate() — full signal
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _market_data(closes, highs, lows, dates, code="krx_kospi200f_continuous"):
    return {
        "code": code,
        "close": closes[-1],
        "daily_closes": closes,
        "daily_highs": highs,
        "daily_lows": lows,
        "daily_dates": dates,
    }


def test_generate_emits_long_signal_with_stop_below_entry():
    cfg = CTAMomentumConfig(
        momentum_lookback=20,
        ma_fast_period=5,
        ma_slow_period=20,
        atr_period=5,
        initial_stop_atr_mult=3.0,
        min_bars=21,
    )
    entry = CTAMomentumEntry(cfg)
    n = 60
    closes = _uptrend(n)
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    dates = _dates(n)
    ctx = EntryContext(
        market_data=_market_data(closes, highs, lows, dates),
        timestamp=datetime(2020, 6, 1, tzinfo=UTC),
    )
    sig = _run(entry.generate(ctx))
    assert sig is not None
    assert sig.metadata["signal_direction"] == "long"
    assert sig.metadata["stop_loss"] < sig.price  # long stop below entry
    assert sig.metadata["entry_atr"] > 0
    assert sig.strategy == "cta_momentum"


def test_generate_emits_short_signal_with_stop_above_entry():
    cfg = CTAMomentumConfig(
        momentum_lookback=20,
        ma_fast_period=5,
        ma_slow_period=20,
        atr_period=5,
        initial_stop_atr_mult=3.0,
        min_bars=21,
    )
    entry = CTAMomentumEntry(cfg)
    n = 60
    closes = _downtrend(n)
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    dates = _dates(n)
    ctx = EntryContext(
        market_data=_market_data(closes, highs, lows, dates),
        timestamp=datetime(2020, 6, 1, tzinfo=UTC),
    )
    sig = _run(entry.generate(ctx))
    assert sig is not None
    assert sig.metadata["signal_direction"] == "short"
    assert sig.metadata["stop_loss"] > sig.price  # short stop above entry


def test_generate_blocks_entry_on_roll_day():
    cfg = CTAMomentumConfig(
        momentum_lookback=20,
        ma_fast_period=5,
        ma_slow_period=20,
        atr_period=5,
        min_bars=21,
    )
    entry = CTAMomentumEntry(cfg)
    n = 60
    closes = _uptrend(n)
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    dates = _dates(n)
    dates[-1] = date(2024, 6, 13)  # force the decision day to be a roll day
    ctx = EntryContext(
        market_data=_market_data(closes, highs, lows, dates),
        timestamp=datetime(2024, 6, 13, tzinfo=UTC),
    )
    assert _run(entry.generate(ctx)) is None


def test_generate_returns_none_without_code():
    cfg = CTAMomentumConfig(
        min_bars=21, momentum_lookback=20, ma_fast_period=5, ma_slow_period=20
    )
    entry = CTAMomentumEntry(cfg)
    ctx = EntryContext(
        market_data={"daily_closes": _uptrend(60)},
        timestamp=datetime(2020, 6, 1, tzinfo=UTC),
    )
    assert _run(entry.generate(ctx)) is None


def test_required_indicators_empty_no_mtf_footgun():
    # Daily-cadence strategy must NOT request momentum_/mtf_base_ packs.
    entry = CTAMomentumEntry(CTAMomentumConfig())
    assert entry.required_indicators == []


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def test_config_rejects_inverted_ma_periods():
    with pytest.raises(ValueError):
        CTAMomentumConfig(ma_fast_period=100, ma_slow_period=20).validate()


def test_config_rejects_min_bars_below_floor():
    with pytest.raises(ValueError):
        CTAMomentumConfig(
            momentum_lookback=60, ma_slow_period=100, min_bars=50
        ).validate()


def test_config_rejects_both_directions_disabled():
    with pytest.raises(ValueError):
        CTAMomentumConfig(allow_long=False, allow_short=False).validate()
