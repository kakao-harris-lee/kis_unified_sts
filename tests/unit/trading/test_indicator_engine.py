"""Tests for StreamingIndicatorEngine helpers."""

from __future__ import annotations

from datetime import datetime

from services.trading.indicator_engine import StreamingIndicatorEngine


def test_get_recent_candles_returns_ohlcv_dicts():
    engine = StreamingIndicatorEngine()
    symbol = "A01603"

    engine.on_tick(symbol, {"close": 100.0, "high": 101.0, "low": 99.5, "volume": 10}, datetime(2026, 2, 12, 9, 0, 10))
    engine.on_tick(symbol, {"close": 101.0, "high": 101.5, "low": 100.2, "volume": 12}, datetime(2026, 2, 12, 9, 1, 5))
    engine.on_tick(symbol, {"close": 102.0, "high": 102.4, "low": 101.7, "volume": 8}, datetime(2026, 2, 12, 9, 2, 5))

    candles = engine.get_recent_candles(symbol, limit=5)
    assert len(candles) == 2  # completed candles only
    assert set(candles[0].keys()) == {"open", "high", "low", "close", "volume"}
