"""Golden pins: shared/regime hand-rolled SMA / return-volatility math (P1-b4).

Pins the exact numeric behavior of the regime detectors' residual inline math
BEFORE/AFTER delegation to ``shared.indicators.series``
(``docs/plans/2026-07-08-new-architecture-refactoring-plan.md`` §3, P1-b item 4):

* ``StockRegimeDetector.detect``                 — SMA fast/slow + trend_pct,
  return volatility (``pct_change().dropna()`` then rolling std, ddof=1)
* ``AdaptiveRegimeDetector._calculate_indicators`` — SMA fast/slow + trend_pct
  residual (MFI/ADX/ATR are already reference-delegated and pinned whole-dict)

``_orig_*`` below are verbatim copies of the pre-refactor expressions.
Assertions are EXACT (``==``): the delegation must be bit-identical.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from shared.regime.adaptive_detector import AdaptiveRegimeConfig, AdaptiveRegimeDetector
from shared.regime.detector import StockRegimeDetector
from shared.regime.models import RegimeConfig
from shared.utils.math import safe_divide

# ---------------------------------------------------------------------------
# Seeded inputs
# ---------------------------------------------------------------------------


def _ohlcv(seed: int, n: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 70_000.0 + np.cumsum(rng.normal(0.0, 350.0, n))
    spread = np.abs(rng.normal(0.0, 200.0, n))
    return pd.DataFrame(
        {
            "datetime": pd.date_range("2026-03-02 09:00", periods=n, freq="1min"),
            "open": close - rng.normal(0.0, 100.0, n),
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": rng.integers(1_000, 90_000, n).astype(float),
        }
    )


class TestStockRegimeDetectorGolden:
    def _orig_indicators(
        self, df: pd.DataFrame, config: RegimeConfig
    ) -> dict[str, float]:
        close = df["close"]
        sma_fast = close.rolling(config.sma_fast).mean()
        sma_slow = close.rolling(config.sma_slow).mean()
        current_sma_fast = sma_fast.iloc[-1]
        current_sma_slow = sma_slow.iloc[-1]
        trend_pct = safe_divide(
            current_sma_fast - current_sma_slow, current_sma_slow, default=0.0
        )
        returns = close.pct_change().dropna()
        if len(returns) < config.volatility_window:
            volatility = 0.0
        else:
            vol_series = returns.rolling(config.volatility_window).std()
            volatility = (
                vol_series.iloc[-1]
                if len(vol_series) > 0 and pd.notna(vol_series.iloc[-1])
                else 0.0
            )
        return {
            "sma_fast": current_sma_fast,
            "sma_slow": current_sma_slow,
            "trend_pct": trend_pct,
            "volatility": volatility,
        }

    def test_detect_bit_identical(self):
        config = RegimeConfig()
        detector = StockRegimeDetector(config)
        for seed in range(20):
            n = int(np.random.default_rng(seed).integers(50, 200))
            df = _ohlcv(seed=1500 + seed, n=n)
            signal = detector.detect(df)
            want = self._orig_indicators(df, config)
            assert signal.indicators == want, f"seed={seed} n={n}"

    def test_detect_trending_frames(self):
        config = RegimeConfig()
        detector = StockRegimeDetector(config)
        n = 120
        up = _ohlcv(seed=1600, n=n)
        up["close"] = np.linspace(50_000.0, 80_000.0, n)
        down = _ohlcv(seed=1601, n=n)
        down["close"] = np.linspace(80_000.0, 50_000.0, n)
        for df in (up, down):
            signal = detector.detect(df)
            assert signal.indicators == self._orig_indicators(df, config)

    def test_detect_insufficient_data_unknown(self):
        config = RegimeConfig()
        detector = StockRegimeDetector(config)
        df = _ohlcv(seed=1602, n=config.sma_slow - 1)
        signal = detector.detect(df)
        assert signal.confidence == 0.0
        assert not signal.indicators


class TestAdaptiveRegimeDetectorGolden:
    def test_calculate_indicators_bit_identical(self):
        config = AdaptiveRegimeConfig()
        detector = AdaptiveRegimeDetector(config)
        for seed in range(15):
            n = int(np.random.default_rng(seed).integers(config.min_bars, 200))
            df = _ohlcv(seed=1700 + seed, n=n).drop(columns=["datetime"])
            got = detector._calculate_indicators(df)

            close = df["close"].values
            sma_fast = pd.Series(close).rolling(config.sma_fast).mean().iloc[-1]
            sma_slow = pd.Series(close).rolling(config.sma_slow).mean().iloc[-1]
            trend_pct = safe_divide(sma_fast - sma_slow, sma_slow, default=0.0)

            # Residual SMA/trend math must be bit-identical.
            assert got["sma_fast"] == sma_fast
            assert got["sma_slow"] == sma_slow
            assert got["trend_pct"] == trend_pct
            assert got["close"] == close[-1]
            # Already-delegated metrics stay self-consistent (whole-dict guard).
            high = df["high"].values
            low = df["low"].values
            assert got["mfi"] == detector._calc_mfi(df, period=config.mfi_period)
            assert got["adx"] == detector._calc_adx(
                high, low, close, period=config.adx_period
            )
            assert got["atr"] == detector._calc_atr(
                high, low, close, period=config.atr_period
            )
            assert got["atr_ratio"] == safe_divide(
                got["atr"], close[-1], default=0.0
            )
