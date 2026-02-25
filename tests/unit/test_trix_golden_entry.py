"""Unit tests for shared/strategy/entry/trix_golden.py

Tests TRIX Golden Signal Entry strategy — 5 AND-condition logic,
time filters, cooldown, OBV filter, and signal metadata.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from shared.indicators.momentum import calculate_all_momentum
from shared.strategy.base import EntryContext
from shared.strategy.entry.trix_golden import TrixGoldenConfig, TrixGoldenEntry

# =============================================================================
# Helpers
# =============================================================================


def _make_ohlcv(close_values: list[float], volume: float = 10000.0) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame from close values."""
    n = len(close_values)
    return pd.DataFrame(
        {
            "open": close_values,
            "high": [c * 1.01 for c in close_values],
            "low": [c * 0.99 for c in close_values],
            "close": close_values,
            "volume": [volume] * n,
        }
    )


def _build_golden_df(n: int = 80) -> pd.DataFrame:
    """Build a DataFrame that satisfies all 5 golden signal conditions.

    Strategy:
    - Uptrend → positive TRIX, positive MACD osc
    - Construct so that the last bar has TRIX golden cross, Stochastic golden cross,
      CCI < 200, and OBV rising.

    We achieve this by creating a dip-then-surge price pattern.
    """
    # Base price: flat then dip then sharp rise at end
    closes = []
    for i in range(n):
        if i < n - 15:
            closes.append(100.0)
        elif i < n - 5:
            closes.append(100.0 - (i - (n - 15)) * 0.5)  # Gentle dip
        else:
            closes.append(95.0 + (i - (n - 5)) * 2.0)  # Sharp rise

    df = _make_ohlcv(closes)
    df = calculate_all_momentum(df)
    return df


def _build_context_with_momentum(
    df: pd.DataFrame,
    code: str = "005930",
    name: str = "삼성전자",
    timestamp: datetime | None = None,
) -> EntryContext:
    """Build an EntryContext with momentum_5m DataFrame data."""
    ts = timestamp or datetime(2026, 3, 15, 10, 30, 0)  # Valid trading time
    close_price = float(df["close"].iloc[-1])

    momentum_data = {
        "trix": float(df["trix"].iloc[-1]),
        "trix_signal": float(df["trix_signal"].iloc[-1]),
        "cci": float(df["cci"].iloc[-1]),
        "macd_oscillator": float(df["macd_oscillator"].iloc[-1]),
        "sto_k": float(df["sto_k"].iloc[-1]),
        "sto_d": float(df["sto_d"].iloc[-1]),
        "df": df,
    }

    return EntryContext(
        market_data={
            "code": code,
            "name": name,
            "close": close_price,
        },
        indicators={"momentum_5m": momentum_data},
        timestamp=ts,
    )


def _force_golden_cross(df: pd.DataFrame) -> pd.DataFrame:
    """Manually tweak the last two bars to guarantee TRIX and Stochastic golden crosses.

    This ensures:
      - prev bar: trix <= trix_signal, sto_k <= sto_d
      - last bar: trix > trix_signal, sto_k > sto_d
      - macd_oscillator > 0
      - cci < 200
      - obv rising
    """
    df = df.copy()
    n = len(df)

    # TRIX golden cross
    df.loc[n - 2, "trix"] = 0.01
    df.loc[n - 2, "trix_signal"] = 0.02  # prev: trix <= signal
    df.loc[n - 1, "trix"] = 0.05
    df.loc[n - 1, "trix_signal"] = 0.03  # cur: trix > signal

    # MACD osc > 0
    df.loc[n - 1, "macd_oscillator"] = 0.5

    # Stochastic golden cross
    df.loc[n - 2, "sto_k"] = 40.0
    df.loc[n - 2, "sto_d"] = 45.0  # prev: K <= D
    df.loc[n - 1, "sto_k"] = 55.0
    df.loc[n - 1, "sto_d"] = 50.0  # cur: K > D

    # CCI < 200
    df.loc[n - 1, "cci"] = 80.0

    # OBV rising
    df.loc[n - 2, "obv"] = 100000
    df.loc[n - 1, "obv"] = 120000

    return df


# =============================================================================
# Tests
# =============================================================================


class TestTrixGoldenConfig:
    def test_default_values(self):
        config = TrixGoldenConfig()
        assert config.trix_n == 12
        assert config.trix_signal == 9
        assert config.cci_upper == 300.0
        assert config.cci_lower == 0.0
        assert config.stop_loss_pct == 3.0
        assert config.trix_entry_mode == "acceleration"
        assert config.use_uncorrelated_filters is True

    def test_legacy_defaults(self):
        config = TrixGoldenConfig(trix_entry_mode="crossover", cci_upper=200.0)
        assert config.cci_upper == 200.0


class TestTrixGoldenEntryInit:
    def test_create_with_defaults(self):
        entry = TrixGoldenEntry(TrixGoldenConfig())
        assert entry.name == "trix_golden"
        assert "momentum_5m" in entry.required_indicators

    def test_validate_config_bad_mode(self):
        """Invalid entry mode raises assertion."""
        with pytest.raises(AssertionError):
            TrixGoldenEntry(TrixGoldenConfig(trix_entry_mode="invalid"))


def _crossover_config(**kwargs) -> TrixGoldenConfig:
    """Create a config in legacy crossover mode for backward-compat tests."""
    defaults = dict(
        trix_entry_mode="crossover",
        use_uncorrelated_filters=False,
        cci_upper=200.0,
        cci_lower=-999.0,
        min_candles=10,
    )
    defaults.update(kwargs)
    return TrixGoldenConfig(**defaults)


class TestTrixGoldenEntryGenerate:
    @pytest.mark.asyncio
    async def test_golden_signal_fires(self):
        """All 5 conditions met (crossover mode) → signal generated."""
        df = _build_golden_df(80)
        df = _force_golden_cross(df)

        entry = TrixGoldenEntry(_crossover_config())
        ctx = _build_context_with_momentum(df)
        signal = await entry.generate(ctx)

        assert signal is not None
        assert signal.code == "005930"
        assert signal.strategy == "trix_golden"
        assert signal.metadata["signal_direction"] == "long"
        assert signal.metadata["stop_loss_pct"] == 3.0
        assert 0.0 <= signal.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_no_signal_when_trix_no_cross(self):
        """TRIX not crossing signal → no signal (crossover mode)."""
        df = _build_golden_df(80)
        df = _force_golden_cross(df)
        n = len(df)
        df.loc[n - 2, "trix"] = 0.05
        df.loc[n - 2, "trix_signal"] = 0.02

        entry = TrixGoldenEntry(_crossover_config())
        ctx = _build_context_with_momentum(df)
        signal = await entry.generate(ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_no_signal_when_macd_negative(self):
        """MACD oscillator negative → no signal (crossover mode)."""
        df = _build_golden_df(80)
        df = _force_golden_cross(df)
        df.loc[len(df) - 1, "macd_oscillator"] = -0.1

        entry = TrixGoldenEntry(_crossover_config())
        ctx = _build_context_with_momentum(df)
        signal = await entry.generate(ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_no_signal_when_stochastic_bearish(self):
        """Stochastic bearish state (%K < %D) → no signal (crossover mode)."""
        df = _build_golden_df(80)
        df = _force_golden_cross(df)
        n = len(df)
        df.loc[n - 1, "sto_k"] = 40.0
        df.loc[n - 1, "sto_d"] = 60.0

        entry = TrixGoldenEntry(_crossover_config())
        ctx = _build_context_with_momentum(df)
        signal = await entry.generate(ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_no_signal_when_cci_high(self):
        """CCI >= upper threshold → no signal (crossover mode)."""
        df = _build_golden_df(80)
        df = _force_golden_cross(df)
        df.loc[len(df) - 1, "cci"] = 250.0

        entry = TrixGoldenEntry(_crossover_config())
        ctx = _build_context_with_momentum(df)
        signal = await entry.generate(ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_no_signal_when_obv_falling(self):
        """OBV not rising with obv_filter=True → no signal (crossover mode)."""
        df = _build_golden_df(80)
        df = _force_golden_cross(df)
        n = len(df)
        df.loc[n - 1, "obv"] = 90000
        df.loc[n - 2, "obv"] = 100000

        entry = TrixGoldenEntry(_crossover_config(obv_filter=True))
        ctx = _build_context_with_momentum(df)
        signal = await entry.generate(ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_signal_fires_without_obv_filter(self):
        """OBV falling but obv_filter=False → signal still fires (crossover mode)."""
        df = _build_golden_df(80)
        df = _force_golden_cross(df)
        n = len(df)
        df.loc[n - 1, "obv"] = 90000
        df.loc[n - 2, "obv"] = 100000

        entry = TrixGoldenEntry(_crossover_config(obv_filter=False))
        ctx = _build_context_with_momentum(df)
        signal = await entry.generate(ctx)
        assert signal is not None


class TestTrixGoldenAccelerationMode:
    """Tests for the v2 acceleration entry mode."""

    def _build_acceleration_df(self, n: int = 80) -> pd.DataFrame:
        """Build a DataFrame that satisfies acceleration conditions."""
        closes = [100.0] * n
        # Gentle uptrend at the end
        for i in range(n - 10, n):
            closes[i] = 100.0 + (i - (n - 10)) * 0.5

        df = _make_ohlcv(closes)
        df = calculate_all_momentum(df)

        # Force acceleration conditions:
        # - TRIX > 0 and rising at last bar
        # - TRIX was negative within last N bars
        # - CCI in range [0, 300]
        # - close > SMA20
        nn = len(df)
        for j in range(nn - 5, nn - 1):
            df.loc[j, "trix"] = -0.01  # negative in recent bars
        df.loc[nn - 2, "trix"] = 0.001  # prev: barely positive
        df.loc[nn - 1, "trix"] = 0.01  # current: positive and rising
        df.loc[nn - 1, "trix_signal"] = 0.005
        df.loc[nn - 1, "cci"] = 50.0  # within [0, 300]
        return df

    @pytest.mark.asyncio
    async def test_acceleration_signal_fires(self):
        """Acceleration conditions met → signal generated."""
        df = self._build_acceleration_df(80)
        config = TrixGoldenConfig(
            min_candles=10,
            obv_filter=False,
            require_above_sma=False,  # Skip SMA check for simplicity
        )
        entry = TrixGoldenEntry(config)
        ctx = _build_context_with_momentum(df)
        signal = await entry.generate(ctx)
        assert signal is not None
        assert signal.metadata["entry_mode"] == "acceleration"

    @pytest.mark.asyncio
    async def test_no_signal_when_trix_not_rising(self):
        """TRIX not rising → no signal in acceleration mode."""
        df = self._build_acceleration_df(80)
        n = len(df)
        df.loc[n - 1, "trix"] = 0.005  # Less than prev (0.001→0.005 is rising,
        df.loc[n - 2, "trix"] = 0.01   # but here prev=0.01 > cur=0.005 → not rising)
        config = TrixGoldenConfig(min_candles=10, obv_filter=False, require_above_sma=False)
        entry = TrixGoldenEntry(config)
        ctx = _build_context_with_momentum(df)
        signal = await entry.generate(ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_no_signal_when_cci_below_lower(self):
        """CCI below cci_lower → no signal."""
        df = self._build_acceleration_df(80)
        df.loc[len(df) - 1, "cci"] = -50.0  # Below cci_lower=0
        config = TrixGoldenConfig(min_candles=10, obv_filter=False, require_above_sma=False)
        entry = TrixGoldenEntry(config)
        ctx = _build_context_with_momentum(df)
        signal = await entry.generate(ctx)
        assert signal is None


class TestTrixGoldenEntryTimeFilter:
    @pytest.mark.asyncio
    async def test_no_signal_before_market_cutoff(self):
        """Within skip_market_open_minutes window → no signal."""
        df = _build_golden_df(80)
        df = _force_golden_cross(df)
        entry = TrixGoldenEntry(
            _crossover_config(skip_market_open_minutes=30)
        )
        ts = datetime(2026, 3, 15, 9, 15, 0)
        ctx = _build_context_with_momentum(df, timestamp=ts)
        assert await entry.generate(ctx) is None

    @pytest.mark.asyncio
    async def test_no_signal_near_close(self):
        """Within skip_market_close_minutes → no signal."""
        df = _build_golden_df(80)
        df = _force_golden_cross(df)
        entry = TrixGoldenEntry(
            _crossover_config(skip_market_close_minutes=15)
        )
        ts = datetime(2026, 3, 15, 15, 5, 0)
        ctx = _build_context_with_momentum(df, timestamp=ts)
        assert await entry.generate(ctx) is None


class TestTrixGoldenEntryCooldown:
    @pytest.mark.asyncio
    async def test_cooldown_blocks_rapid_signals(self):
        """Second signal within cooldown period → blocked."""
        df = _build_golden_df(80)
        df = _force_golden_cross(df)
        entry = TrixGoldenEntry(
            _crossover_config(signal_cooldown_seconds=300)
        )

        ts1 = datetime(2026, 3, 15, 10, 30, 0)
        ctx1 = _build_context_with_momentum(df, timestamp=ts1)
        sig1 = await entry.generate(ctx1)
        assert sig1 is not None

        # 2 minutes later — within 5 min cooldown
        ts2 = ts1 + timedelta(minutes=2)
        ctx2 = _build_context_with_momentum(df, timestamp=ts2)
        sig2 = await entry.generate(ctx2)
        assert sig2 is None

    @pytest.mark.asyncio
    async def test_cooldown_allows_after_expiry(self):
        """Signal after cooldown expiry → allowed."""
        df = _build_golden_df(80)
        df = _force_golden_cross(df)
        entry = TrixGoldenEntry(
            _crossover_config(signal_cooldown_seconds=60)
        )

        ts1 = datetime(2026, 3, 15, 10, 30, 0)
        ctx1 = _build_context_with_momentum(df, timestamp=ts1)
        sig1 = await entry.generate(ctx1)
        assert sig1 is not None

        # 2 minutes later — past 60s cooldown
        ts2 = ts1 + timedelta(minutes=2)
        ctx2 = _build_context_with_momentum(df, timestamp=ts2)
        sig2 = await entry.generate(ctx2)
        assert sig2 is not None


class TestTrixGoldenEntryEdgeCases:
    @pytest.mark.asyncio
    async def test_no_momentum_data(self):
        """No momentum_5m → no signal."""
        entry = TrixGoldenEntry(TrixGoldenConfig(min_candles=10))
        ctx = EntryContext(
            market_data={"code": "005930", "name": "삼성전자", "close": 100},
            indicators={},
            timestamp=datetime(2026, 3, 15, 10, 30, 0),
        )
        assert await entry.generate(ctx) is None

    @pytest.mark.asyncio
    async def test_insufficient_candles(self):
        """Fewer candles than min_candles → no signal."""
        df = _build_golden_df(20)
        df = _force_golden_cross(df)
        entry = TrixGoldenEntry(TrixGoldenConfig(min_candles=50))  # needs 50
        ctx = _build_context_with_momentum(df)
        assert await entry.generate(ctx) is None

    @pytest.mark.asyncio
    async def test_no_code_in_market_data(self):
        """Empty code → no signal."""
        entry = TrixGoldenEntry(TrixGoldenConfig(min_candles=10))
        ctx = EntryContext(
            market_data={"code": "", "name": ""},
            indicators={},
            timestamp=datetime(2026, 3, 15, 10, 30, 0),
        )
        assert await entry.generate(ctx) is None
