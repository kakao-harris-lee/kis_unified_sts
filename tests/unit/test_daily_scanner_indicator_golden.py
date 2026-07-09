"""Golden pins: services/daily_scanner.py hand-rolled RSI / ATR (P1-b3).

Pins the exact numeric behavior of the scanner's pure indicator helpers
BEFORE/AFTER their delegation to the indicator package
(``docs/plans/2026-07-08-new-architecture-refactoring-plan.md`` §3, P1-b item 3):

* ``_rsi`` — trailing-window simple-average RSI (Cutler-style: plain mean of
  the last ``period`` gains/losses; NOT Wilder-smoothed). ``avg_loss == 0``
  (including a perfectly flat window) returns 100.0.
* ``_atr`` — plain mean of the last ``period`` True Ranges.

``_orig_*`` below are verbatim copies of the pre-refactor loops. Assertions
are EXACT (``==``): the delegation must be bit-identical.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from services.daily_scanner import DailyBar, _atr, _rsi

# ---------------------------------------------------------------------------
# Verbatim pre-refactor implementations (the golden reference)
# ---------------------------------------------------------------------------


def _orig_rsi(closes: list[float], period: int) -> float | None:
    if len(closes) < period + 1:
        return None
    window = closes[-(period + 1) :]
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(window)):
        delta = window[i] - window[i - 1]
        if delta >= 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-delta)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _orig_atr(bars: list[DailyBar], period: int) -> float | None:
    if len(bars) < period + 1:
        return None
    window = bars[-(period + 1) :]
    true_ranges: list[float] = []
    for i in range(1, len(window)):
        prev_close = window[i - 1].close
        high = window[i].high
        low = window[i].low
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        true_ranges.append(tr)
    return sum(true_ranges) / period


# ---------------------------------------------------------------------------
# Seeded input generators
# ---------------------------------------------------------------------------


def _make_bars(
    closes: np.ndarray, spreads: np.ndarray, opens: np.ndarray
) -> list[DailyBar]:
    d0 = date(2026, 1, 5)
    return [
        DailyBar(
            code="005930",
            date=d0 + timedelta(days=i),
            open=float(opens[i]),
            high=float(closes[i] + spreads[i]),
            low=float(closes[i] - spreads[i]),
            close=float(closes[i]),
            volume=int(1_000_000 + i),
        )
        for i in range(len(closes))
    ]


class TestScannerRsiGolden:
    def test_seeded_walks_bit_identical(self):
        rng = np.random.default_rng(1111)
        for _ in range(120):
            n = int(rng.integers(2, 80))
            closes = [float(v) for v in 100.0 + np.cumsum(rng.normal(0.0, 1.0, n))]
            for period in (5, 9, 14, 20):
                assert _rsi(closes, period) == _orig_rsi(closes, period), (
                    f"n={n} period={period}"
                )

    def test_degenerate_windows(self):
        period = 14
        up = [float(100 + i) for i in range(period + 1)]  # all gains -> 100.0
        down = [float(200 - i) for i in range(period + 1)]  # all losses -> 0.0
        flat = [100.0] * (period + 1)  # flat -> 100.0 (avg_loss == 0 short-circuit)
        short = [100.0] * period  # insufficient -> None
        for closes in (up, down, flat, short):
            assert _rsi(closes, period) == _orig_rsi(closes, period)
        assert _rsi(up, period) == 100.0
        assert _rsi(down, period) == 0.0
        assert _rsi(flat, period) == 100.0
        assert _rsi(short, period) is None

    def test_exact_boundary_length(self):
        rng = np.random.default_rng(2222)
        for period in (5, 14):
            closes = [
                float(v) for v in 100.0 + np.cumsum(rng.normal(0.0, 1.0, period + 1))
            ]
            assert _rsi(closes, period) == _orig_rsi(closes, period)


class TestScannerAtrGolden:
    def test_seeded_walks_bit_identical(self):
        rng = np.random.default_rng(3333)
        for _ in range(120):
            n = int(rng.integers(2, 60))
            closes = 100.0 + np.cumsum(rng.normal(0.0, 1.5, n))
            spreads = np.abs(rng.normal(0.0, 0.8, n))
            opens = closes + rng.normal(0.0, 0.3, n)
            bars = _make_bars(closes, spreads, opens)
            for period in (5, 14, 20):
                assert _atr(bars, period) == _orig_atr(bars, period), (
                    f"n={n} period={period}"
                )

    def test_insufficient_and_boundary(self):
        rng = np.random.default_rng(4444)
        period = 14
        closes = 100.0 + np.cumsum(rng.normal(0.0, 1.0, period + 1))
        spreads = np.abs(rng.normal(0.0, 0.5, period + 1))
        bars = _make_bars(closes, spreads, closes)
        assert _atr(bars, period) == _orig_atr(bars, period)
        assert _atr(bars[:period], period) is None
        assert _orig_atr(bars[:period], period) is None

    def test_gap_bars_use_prev_close_tr(self):
        # Gapped bars where |high - prev_close| / |low - prev_close| dominate.
        closes = np.array([100.0, 120.0, 90.0, 130.0, 85.0, 140.0])
        spreads = np.full(6, 0.5)
        bars = _make_bars(closes, spreads, closes)
        assert _atr(bars, 5) == _orig_atr(bars, 5)
