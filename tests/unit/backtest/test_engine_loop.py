"""Tests for BacktestEngine.run() — verify bar dict structure after itertuples migration."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from shared.backtest.config import BacktestConfig
from shared.backtest.engine import BacktestEngine, SignalType, SimpleMAStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int = 100, code: str = "005930") -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    base = datetime(2024, 1, 2, 9, 0)
    rng = np.random.default_rng(42)
    price = 100.0
    rows: list[dict] = []
    for i in range(n):
        price += rng.uniform(-1, 1.2)
        rows.append(
            {
                "code": code,
                "name": code,
                "datetime": base + timedelta(minutes=i),
                "open": round(price - 0.2, 2),
                "high": round(price + 0.5, 2),
                "low": round(price - 0.5, 2),
                "close": round(price, 2),
                "volume": 1000 + i,
            }
        )
    return pd.DataFrame(rows)


class _SpyStrategy:
    """Captures bar dicts passed to on_bar()."""

    name = "spy"

    def __init__(self) -> None:
        self.bars: list[dict] = []

    def on_bar(self, bar: dict) -> SignalType:
        self.bars.append(dict(bar))
        return SignalType.HOLD


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBarDictStructure:
    """Verify bar dict keys and types after itertuples migration."""

    def test_bar_keys_match_dataframe_columns(self):
        """Bar dict keys should exactly match DataFrame columns (no extra Index key)."""
        spy = _SpyStrategy()
        df = _make_ohlcv(5)
        engine = BacktestEngine(spy, BacktestConfig())
        engine.run(df)

        expected_keys = set(df.columns)
        assert set(spy.bars[0].keys()) == expected_keys
        assert "Index" not in spy.bars[0]

    def test_bar_datetime_is_timestamp(self):
        """datetime value must be a pandas Timestamp (not string or other type)."""
        spy = _SpyStrategy()
        engine = BacktestEngine(spy, BacktestConfig())
        engine.run(_make_ohlcv(3))

        assert isinstance(spy.bars[0]["datetime"], pd.Timestamp)

    def test_bar_numeric_types(self):
        """close/open/high/low should be numeric, volume should be usable as number."""
        spy = _SpyStrategy()
        engine = BacktestEngine(spy, BacktestConfig())
        engine.run(_make_ohlcv(3))

        bar = spy.bars[0]
        # Must support float() conversion
        assert isinstance(float(bar["close"]), float)
        assert isinstance(float(bar["volume"]), float)
        # Arithmetic must work correctly
        assert bar["high"] >= bar["low"]

    def test_nan_values_propagated(self):
        """NaN in optional columns should remain NaN (compatible with np.isnan)."""
        spy = _SpyStrategy()
        df = _make_ohlcv(5)
        df["atr"] = [np.nan, 1.5, np.nan, 2.0, 1.8]

        engine = BacktestEngine(spy, BacktestConfig())
        engine.run(df)

        # First bar has NaN ATR — must work with np.isnan
        assert np.isnan(spy.bars[0]["atr"])
        # Second bar has valid ATR
        assert spy.bars[1]["atr"] == 1.5

    def test_string_column_preserved(self):
        """String columns (code, name) should remain strings."""
        spy = _SpyStrategy()
        engine = BacktestEngine(spy, BacktestConfig())
        engine.run(_make_ohlcv(3, code="005930"))

        assert spy.bars[0]["code"] == "005930"
        assert isinstance(spy.bars[0]["code"], str)

    def test_all_rows_processed(self):
        """Every row in the DataFrame should be passed to on_bar()."""
        spy = _SpyStrategy()
        n = 50
        engine = BacktestEngine(spy, BacktestConfig())
        engine.run(_make_ohlcv(n))

        assert len(spy.bars) == n

    def test_mixed_dtypes_preserved(self):
        """int64 volume and float64 close should coexist without issue."""
        spy = _SpyStrategy()
        df = _make_ohlcv(5)
        df["volume"] = df["volume"].astype(np.int64)

        engine = BacktestEngine(spy, BacktestConfig())
        engine.run(df)

        bar = spy.bars[0]
        # Division must produce float (Python 3 true division)
        assert isinstance(bar["close"] / bar["volume"], float)


class TestEngineRunEndToEnd:
    """Smoke tests: BacktestEngine.run() produces valid BacktestResult."""

    def test_simple_ma_generates_result(self):
        """SimpleMAStrategy should produce a valid BacktestResult."""
        engine = BacktestEngine(SimpleMAStrategy(5, 20), BacktestConfig())
        result = engine.run(_make_ohlcv(200))

        assert result.total_bars == 200
        assert result.total_trades >= 0
        assert result.initial_capital == BacktestConfig().initial_capital

    def test_empty_data_raises(self):
        """Empty DataFrame should raise ValueError."""
        engine = BacktestEngine(SimpleMAStrategy(), BacktestConfig())
        with pytest.raises(ValueError, match="Empty data"):
            engine.run(pd.DataFrame())

    def test_last_bar_forced_liquidation(self):
        """Open positions should be force-closed at end of data."""

        class AlwaysBuyOnce:
            name = "always_buy_once"
            _bought = False

            def on_bar(self, bar: dict) -> SignalType:
                if not self._bought:
                    self._bought = True
                    return SignalType.BUY
                return SignalType.HOLD

        engine = BacktestEngine(AlwaysBuyOnce(), BacktestConfig())
        result = engine.run(_make_ohlcv(50))

        # Position should be closed (force liquidation at end)
        assert result.total_trades >= 1

    def test_multi_symbol_backtest(self):
        """Backtest with multiple symbols should process all bars."""
        spy = _SpyStrategy()
        df1 = _make_ohlcv(30, code="005930")
        df2 = _make_ohlcv(30, code="000660")
        df = pd.concat([df1, df2], ignore_index=True)

        engine = BacktestEngine(spy, BacktestConfig())
        engine.run(df)

        codes = {bar["code"] for bar in spy.bars}
        assert codes == {"005930", "000660"}
        assert len(spy.bars) == 60
