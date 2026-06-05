"""Shared parquet warmup helper seeds the engine correctly."""

from __future__ import annotations

import pandas as pd
import pytest

from services.trading.indicator_engine import StreamingIndicatorEngine
from shared.streaming.parquet_warmup import warmup_engine_from_parquet


class _Store:
    def get_minute_bars(self, symbol, start=None, end=None, limit=None):  # noqa: ARG002
        rows = [
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1}
            for _ in range(30)
        ]
        return pd.DataFrame(rows)


def test_seeds_candles_into_engine():
    """30 seeded 1-min bars >= bb_period(20) → engine is warm."""
    eng = StreamingIndicatorEngine()
    warmup_engine_from_parquet(eng, _Store(), "A05")
    assert eng.is_warm("A05") is True


class _StoreTailCheck:
    """Returns MORE than lookback_minutes bars in ASC order with monotonic closes.

    close[i] = 100 + i, so every row has a distinct close that encodes its
    position in the sequence.  This makes tail vs head distinguishable at the
    LAST seeded bar — the correct check:

      correct tail-slice  iloc[-240:] → rows 60-299 → last close = 100+299 = 399
      buggy   head-slice  iloc[:240]  → rows  0-239 → last close = 100+239 = 339

    The previous two-band design (BAD_PRICE / GOOD_PRICE) was ambiguous: a
    head-slice of rows 0-239 still ends on GOOD_PRICE (row 239 is in the GOOD
    band), so the test passed even on the bug.  Monotonic closes eliminate that
    false-pass.
    """

    TOTAL_ROWS = 300
    BASE = 100  # close[i] = BASE + i

    @classmethod
    def expected_last_close(cls) -> float:
        """Last close after correct tail-slice of TOTAL_ROWS with lookback=240."""
        return float(cls.BASE + cls.TOTAL_ROWS - 1)  # 100 + 299 = 399

    def get_minute_bars(self, symbol, start=None, end=None, limit=None):  # noqa: ARG002
        rows = [
            {
                "open": float(self.BASE + i),
                "high": float(self.BASE + i + 1),
                "low": float(self.BASE + i - 1),
                "close": float(self.BASE + i),
                "volume": 1,
            }
            for i in range(self.TOTAL_ROWS)
        ]
        return pd.DataFrame(rows)


class _StoreSmall:
    """Returns fewer bars than the lookback window for the no-crash test."""

    TOTAL_ROWS = 25

    def get_minute_bars(self, symbol, start=None, end=None, limit=None):  # noqa: ARG002
        rows = [
            {
                "open": float(100 + i),
                "high": float(101 + i),
                "low": float(99 + i),
                "close": float(100 + i),
                "volume": 1,
            }
            for i in range(self.TOTAL_ROWS)
        ]
        return pd.DataFrame(rows)


def test_uses_most_recent_bars_not_oldest():
    """Regression (#414): warmup must tail the most recent bars.

    The store returns 300 ASC bars with close[i] = 100+i (monotonic).

      correct tail-slice  iloc[-240:] → rows 60-299 → last close = 399.0
      buggy   head-slice  iloc[:240]  → rows  0-239 → last close = 339.0

    Asserting last close == 399.0 catches the head-slice bug; 339.0 would fail.
    """
    store = _StoreTailCheck()
    eng = StreamingIndicatorEngine()
    warmup_engine_from_parquet(eng, store, "A05")

    assert eng.is_warm("A05"), "Engine should be warm after seeding ≥20 candles"
    last_price = eng.get_last_price("A05")
    expected = _StoreTailCheck.expected_last_close()
    assert last_price == pytest.approx(expected, abs=0.01), (
        f"Expected last close {expected} (tail-slice); got {last_price} "
        f"(head-slice would give {_StoreTailCheck.BASE + 240 - 1}.0 = 339.0)"
    )


def test_with_fewer_bars_than_lookback():
    """When fewer bars exist than lookback_minutes, all bars are used (no crash)."""
    eng = StreamingIndicatorEngine()
    warmup_engine_from_parquet(eng, _StoreSmall(), "A05")
    assert eng.is_warm("A05") is True
