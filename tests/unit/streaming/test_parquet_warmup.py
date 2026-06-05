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
    """Returns MORE than lookback_minutes bars in ASC order.

    Old bars (rows 0..N-lookback_minutes-1) have close=BAD_PRICE (555.0).
    Recent tail (last lookback_minutes rows) have close=GOOD_PRICE (350.0).
    The warmup must seed from the RECENT tail, not the head.
    """

    BAD_PRICE = 555.0
    GOOD_PRICE = 350.0

    def __init__(self, total_rows: int = 60) -> None:
        self._total_rows = total_rows

    def get_minute_bars(self, symbol, start=None, end=None, limit=None):  # noqa: ARG002
        lookback = 240  # default in warmup_engine_from_parquet
        bad_count = max(0, self._total_rows - lookback)
        rows = [
            {
                "open": self.BAD_PRICE,
                "high": self.BAD_PRICE + 1,
                "low": self.BAD_PRICE - 1,
                "close": self.BAD_PRICE,
                "volume": 1,
            }
            for _ in range(bad_count)
        ] + [
            {
                "open": self.GOOD_PRICE,
                "high": self.GOOD_PRICE + 1,
                "low": self.GOOD_PRICE - 1,
                "close": self.GOOD_PRICE,
                "volume": 1,
            }
            for _ in range(self._total_rows - bad_count)
        ]
        return pd.DataFrame(rows)


def test_uses_most_recent_bars_not_oldest():
    """Regression: warmup must tail the most recent bars.

    The store returns 300 bars in ASC order: the first 60 have close=555.0
    (old/bad), the last 240 have close=350.0 (recent/good).  After warmup the
    engine's last seeded close must be 350.0, not 555.0.
    """
    store = _StoreTailCheck(total_rows=300)
    eng = StreamingIndicatorEngine()
    warmup_engine_from_parquet(eng, store, "A05")

    assert eng.is_warm("A05"), "Engine should be warm after seeding ≥20 candles"
    last_price = eng.get_last_price("A05")
    assert last_price == pytest.approx(_StoreTailCheck.GOOD_PRICE, abs=0.01), (
        f"Warmup seeded from OLD bars (got {last_price}); expected recent close "
        f"{_StoreTailCheck.GOOD_PRICE}"
    )


def test_with_fewer_bars_than_lookback():
    """When fewer bars exist than lookback_minutes, all bars are used (no crash)."""
    # Store returns only 25 bars (< 240 lookback) — engine should still warm.
    store = _StoreTailCheck(total_rows=25)
    eng = StreamingIndicatorEngine()
    warmup_engine_from_parquet(eng, store, "A05")
    assert eng.is_warm("A05") is True
