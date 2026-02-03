"""DataEngine tests (skip if polars not installed)."""

import pytest

polars = pytest.importorskip("polars")

from core.data_engine import DataEngine, DataEngineConfig


def test_data_engine_load_history_and_ingest_tick():
    engine = DataEngine(DataEngineConfig(max_bars=5, timezone="UTC"))
    now = polars.datetime(2025, 1, 1, 9, 0, 0)

    rows = [
        {
            "code": "005930",
            "datetime": now,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
            "value": 100000,
        }
    ]
    engine.load_history("005930", rows)
    df = engine.get_frame("005930")
    assert df is not None
    assert df.height == 1

    engine.ingest_tick(
        {
            "symbol": "005930",
            "timestamp": 1735693205.0,  # 2025-01-01 09:00:05 UTC
            "current_price": 101.0,
            "tick_volume": 10,
        }
    )
    df2 = engine.get_frame("005930")
    assert df2 is not None
    assert df2.height >= 1

