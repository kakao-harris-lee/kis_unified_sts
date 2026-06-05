"""Parquet warmup seeds the engine so it is warm without live ticks.

This file provides a thin smoke test covering the futures-daemon warmup path.
The canonical recency regression suite lives in
tests/unit/streaming/test_parquet_warmup.py (shared helper).
"""

from __future__ import annotations

import pandas as pd
import pytest

from services.trading.indicator_engine import StreamingIndicatorEngine
from shared.streaming.parquet_warmup import (
    warmup_engine_from_parquet as _warmup_engine_from_parquet,
)


class _Store:
    def get_minute_bars(self, symbol, start=None, end=None, limit=None):  # noqa: ARG002
        rows = [
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1}
            for _ in range(30)
        ]
        return pd.DataFrame(rows)


def test_warmup_seeds_candles_into_engine():
    eng = StreamingIndicatorEngine()
    _warmup_engine_from_parquet(eng, _Store(), "A05")
    # 30 seeded 1-min bars >= bb_period(20) -> warm
    assert eng.is_warm("A05") is True


class _StoreTailCheck:
    """Returns MORE than lookback_minutes bars in ASC order with monotonic closes.

    close[i] = 100 + i, so every row has a distinct close that encodes its
    position in the sequence.  This makes tail vs head distinguishable at the
    LAST seeded bar:

      correct tail-slice  iloc[-240:] → rows 60-299 → last close = 100+299 = 399
      buggy   head-slice  iloc[:240]  → rows  0-239 → last close = 100+239 = 339
    """

    TOTAL_ROWS = 300
    BASE = 100  # close[i] = BASE + i

    @classmethod
    def expected_last_close(cls) -> float:
        return float(cls.BASE + cls.TOTAL_ROWS - 1)  # 399.0

    def __init__(self, total_rows: int | None = None) -> None:
        self._total_rows = total_rows if total_rows is not None else self.TOTAL_ROWS

    def get_minute_bars(self, symbol, start=None, end=None, limit=None):  # noqa: ARG002
        rows = [
            {
                "open": float(self.BASE + i),
                "high": float(self.BASE + i + 1),
                "low": float(self.BASE + i - 1),
                "close": float(self.BASE + i),
                "volume": 1,
            }
            for i in range(self._total_rows)
        ]
        return pd.DataFrame(rows)


def test_warmup_uses_most_recent_bars_not_oldest():
    """Regression (#414): warmup must tail the most recent bars.

    300 ASC bars, close[i]=100+i.  Tail-slice → last close 399.0;
    head-slice → 339.0 → test fails → regression caught.
    """
    store = _StoreTailCheck()
    eng = StreamingIndicatorEngine()
    _warmup_engine_from_parquet(eng, store, "A05")

    assert eng.is_warm("A05"), "Engine should be warm after seeding ≥20 candles"
    last_price = eng.get_last_price("A05")
    expected = _StoreTailCheck.expected_last_close()
    assert last_price == pytest.approx(expected, abs=0.01), (
        f"Expected last close {expected} (tail-slice); got {last_price} "
        f"(head-slice would give {_StoreTailCheck.BASE + 240 - 1}.0 = 339.0)"
    )


def test_warmup_with_fewer_bars_than_lookback():
    """When fewer bars exist than lookback_minutes, all bars are used (no crash)."""
    store = _StoreTailCheck(total_rows=25)
    eng = StreamingIndicatorEngine()
    _warmup_engine_from_parquet(eng, store, "A05")
    assert eng.is_warm("A05") is True
