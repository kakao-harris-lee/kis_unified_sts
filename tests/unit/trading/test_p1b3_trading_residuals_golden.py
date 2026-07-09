"""Golden pins: services/trading indicator residuals (P1-b3, Priority A).

Pins the exact numeric behavior of the last hand-rolled indicator math in
``services/trading/indicator_calculations.py`` BEFORE/AFTER its delegation to
``shared.indicators.series`` (``docs/plans/2026-07-08-new-architecture-refactoring-plan.md``
§3, P1-b item 3):

* ``_ema_series`` / ``_ema_last``       — manual ``alpha = 2/(span+1)`` EMA loop
* ``_calc_daily_ema_aligned``           — live momentum_breakout daily-alignment
  gate (historically buggy, #audit-2026-07-05; semantics must not move)
* ``_calc_high_n``                      — trailing max over daily-session highs

Every ``_orig_*`` function below is a verbatim copy of the pre-refactor math.
Assertions are EXACT (``==``): the delegation must be bit-identical.

The consumer-path test pins ``get_indicators()`` outputs (MACD family, EMA
levels/alignment, ``high_N``, daily EMA alignment) so the live
momentum_breakout inputs are pinned end-to-end, not just helper-by-helper.
"""

from __future__ import annotations

from collections import deque

import numpy as np
import pytest

from services.trading.indicator_candles import Candle
from services.trading.indicator_engine import StreamingIndicatorEngine

# ---------------------------------------------------------------------------
# Verbatim pre-refactor implementations (the golden reference)
# ---------------------------------------------------------------------------


def _orig_ema_series(values: list[float], span: int) -> list[float]:
    alpha = 2.0 / (span + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(alpha * v + (1 - alpha) * result[-1])
    return result


def _orig_ema_last(values: list[float], span: int) -> float:
    alpha = 2.0 / (span + 1)
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema


def _orig_daily_ema_aligned(
    daily_closes: list[float], today_close: float, periods: list[int]
) -> bool:
    if not daily_closes:
        return False
    closes = list(daily_closes)
    if today_close > 0:
        closes.append(today_close)
    max_period = max(periods)
    if len(closes) < max_period:
        return False
    ema_values: dict[int, float] = {}
    for period in periods:
        alpha = 2.0 / (period + 1)
        ema_val = closes[0]
        for price in closes[1:]:
            ema_val = alpha * price + (1 - alpha) * ema_val
        ema_values[period] = ema_val
    sorted_periods = sorted(periods)
    fast = ema_values[sorted_periods[0]]
    mid = ema_values[sorted_periods[1]]
    slow = ema_values[sorted_periods[2]]
    return slow > 0 and fast > mid > slow


def _orig_high_n(
    daily_highs: list[float], high_period: int, candles: list[Candle]
) -> float:
    if daily_highs and len(daily_highs) > 0:
        period = min(high_period, len(daily_highs))
        return max(list(daily_highs)[-period:])
    period = min(high_period, len(candles))
    if period == 0:
        return 0.0
    return max(c.high for c in candles[-period:])


# ---------------------------------------------------------------------------
# Seeded input generators
# ---------------------------------------------------------------------------


def _walks(seed: int, count: int, min_len: int = 1, max_len: int = 150):
    rng = np.random.default_rng(seed)
    for _ in range(count):
        n = int(rng.integers(min_len, max_len + 1))
        yield [float(v) for v in 100.0 + np.cumsum(rng.normal(0.0, 1.2, n))]


def _make_candles(closes: list[float], rng: np.random.Generator) -> list[Candle]:
    out = []
    for i, close in enumerate(closes):
        spread = abs(float(rng.normal(0.0, 0.5)))
        out.append(
            Candle(
                open=close - float(rng.normal(0.0, 0.2)),
                high=close + spread,
                low=close - spread,
                close=close,
                volume=float(rng.lognormal(9.0, 0.5)),
                minute=930 + i,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Helper-level pins
# ---------------------------------------------------------------------------


class TestEmaHelpersGolden:
    SPANS = (2, 3, 5, 9, 10, 12, 20, 26, 60, 120)

    def test_ema_series_bit_identical(self):
        for values in _walks(seed=101, count=60):
            for span in self.SPANS:
                got = StreamingIndicatorEngine._ema_series(values, span)
                want = _orig_ema_series(values, span)
                assert got == want, f"span={span} len={len(values)}"

    def test_ema_last_bit_identical(self):
        for values in _walks(seed=202, count=60):
            for span in self.SPANS:
                got = StreamingIndicatorEngine._ema_last(values, span)
                want = _orig_ema_last(values, span)
                assert got == want, f"span={span} len={len(values)}"

    def test_ema_single_value_and_flat(self):
        assert StreamingIndicatorEngine._ema_series([250.5], 5) == [250.5]
        assert StreamingIndicatorEngine._ema_last([250.5], 5) == 250.5
        flat = [77.0] * 40
        assert StreamingIndicatorEngine._ema_series(flat, 10) == _orig_ema_series(
            flat, 10
        )
        assert StreamingIndicatorEngine._ema_last(flat, 10) == _orig_ema_last(flat, 10)


class TestDailyEmaAlignedGolden:
    PERIODS = [5, 10, 20]

    def _engine_with(self, closes: list[float], today_close: float):
        engine = StreamingIndicatorEngine(
            staleness_seconds=0, daily_ema_periods=list(self.PERIODS)
        )
        engine._daily_closes["005930"] = deque(closes, maxlen=60)
        if today_close:
            engine._intraday_last_close["005930"] = today_close
        return engine

    def test_seeded_walks_bit_identical(self):
        rng = np.random.default_rng(303)
        for _ in range(80):
            n = int(rng.integers(1, 45))
            closes = [float(v) for v in 100.0 + np.cumsum(rng.normal(0.05, 1.0, n))]
            today = float(closes[-1] + rng.normal(0.0, 1.0))
            engine = self._engine_with(closes, today)
            got = engine._calc_daily_ema_aligned("005930")
            want = _orig_daily_ema_aligned(closes, today, self.PERIODS)
            assert got == want, f"n={n}"

    @pytest.mark.parametrize(
        ("closes", "today"),
        [
            ([float(100 + 2 * i) for i in range(30)], 161.0),  # strong uptrend
            ([float(200 - 2 * i) for i in range(30)], 139.0),  # strong downtrend
            ([100.0] * 30, 100.0),  # flat
            ([float(100 + i) for i in range(19)], 0.0),  # boundary: 19 + no today
            ([float(100 + i) for i in range(19)], 120.0),  # boundary: 19 + today
            ([float(100 + i) for i in range(20)], 0.0),  # exactly max_period
            ([], 105.0),  # empty deque
            ([float(-100 - i) for i in range(25)], -80.0),  # negative prices
        ],
    )
    def test_edge_scenarios(self, closes, today):
        engine = self._engine_with(closes, today)
        got = engine._calc_daily_ema_aligned("005930")
        want = _orig_daily_ema_aligned(closes, today, self.PERIODS)
        assert got == want

    def test_missing_symbol_false(self):
        engine = StreamingIndicatorEngine(staleness_seconds=0)
        assert engine._calc_daily_ema_aligned("999999") is False


class TestHighNGolden:
    def test_daily_highs_path(self):
        rng = np.random.default_rng(404)
        for _ in range(40):
            n = int(rng.integers(1, 40))
            highs = [float(v) for v in 100.0 + np.cumsum(rng.normal(0.0, 2.0, n))]
            for high_period in (1, 3, 5, 30):
                engine = StreamingIndicatorEngine(
                    staleness_seconds=0, high_period=high_period
                )
                engine._daily_highs["005930"] = deque(highs, maxlen=30)
                got = engine._calc_high_n("005930", [])
                want = _orig_high_n(highs, high_period, [])
                assert got == want

    def test_intraday_fallback_path(self):
        rng = np.random.default_rng(505)
        for _ in range(40):
            n = int(rng.integers(0, 30))
            closes = [float(v) for v in 100.0 + np.cumsum(rng.normal(0.0, 1.0, n))]
            candles = _make_candles(closes, rng)
            for high_period in (1, 5, 20):
                engine = StreamingIndicatorEngine(
                    staleness_seconds=0, high_period=high_period
                )
                got = engine._calc_high_n("005930", candles)
                want = _orig_high_n([], high_period, candles)
                assert got == want

    def test_empty_everything_zero(self):
        engine = StreamingIndicatorEngine(staleness_seconds=0)
        assert engine._calc_high_n("005930", []) == 0.0


# ---------------------------------------------------------------------------
# Consumer-path pin (momentum_breakout live inputs via get_indicators)
# ---------------------------------------------------------------------------


class TestGetIndicatorsConsumerGolden:
    """Pin the get_indicators() keys produced by the refactored helpers."""

    def test_ema_macd_high_daily_keys_bit_identical(self):
        rng = np.random.default_rng(606)
        n = 150
        closes = [float(v) for v in 100.0 + np.cumsum(rng.normal(0.02, 0.8, n))]
        candles = _make_candles(closes, rng)

        engine = StreamingIndicatorEngine(
            staleness_seconds=0,
            high_period=5,
            ema_periods=[5, 20, 60],
            daily_ema_periods=[5, 10, 20],
        )
        engine.seed_candles(
            "005930",
            [
                {
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                    "minute": c.minute,
                }
                for c in candles
            ],
        )
        daily = [float(100 + 2 * i) for i in range(30)]
        engine._daily_closes["005930"] = deque(daily, maxlen=60)
        engine._intraday_last_close["005930"] = daily[-1] + 2.0

        result = engine.get_indicators("005930")
        assert result is not None

        # EMA levels + alignment (intraday)
        for period in (5, 20, 60):
            assert result[f"ema_{period}"] == _orig_ema_last(closes, period)
        want_aligned = (
            _orig_ema_last(closes, 60) > 0
            and _orig_ema_last(closes, 5)
            > _orig_ema_last(closes, 20)
            > _orig_ema_last(closes, 60)
        )
        assert result["ema_aligned"] == want_aligned

        # EMA ratios + MACD live in get_indicator_features (same helpers)
        features = engine.get_indicator_features("005930")
        assert features, "expected features (>=26 candles seeded)"
        cur_close = closes[-1]
        for w in (5, 10, 20):
            assert features[f"ema_ratio_{w}"] == cur_close / (
                _orig_ema_last(closes, w) + 1e-10
            )

        # MACD family (12/26/9 via _ema_series)
        ema12 = _orig_ema_series(closes, 12)
        ema26 = _orig_ema_series(closes, 26)
        macd_series = [f - s for f, s in zip(ema12, ema26)]
        macd_sig = _orig_ema_series(macd_series, 9)
        assert features["macd"] == macd_series[-1]
        assert features["macd_signal"] == macd_sig[-1]
        assert features["macd_hist"] == macd_series[-1] - macd_sig[-1]

        # high_N (intraday fallback: no daily highs seeded)
        assert result["high_5"] == _orig_high_n([], 5, candles)

        # Daily EMA alignment (momentum_breakout daily gate)
        assert result["ema_daily_aligned"] == _orig_daily_ema_aligned(
            daily, daily[-1] + 2.0, [5, 10, 20]
        )
