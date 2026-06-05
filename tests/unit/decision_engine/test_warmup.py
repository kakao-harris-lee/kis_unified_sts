"""Parquet warmup seeds the engine so it is warm without live ticks."""

from __future__ import annotations

import pandas as pd

from services.decision_engine.main import _warmup_engine_from_parquet
from services.trading.indicator_engine import StreamingIndicatorEngine


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
