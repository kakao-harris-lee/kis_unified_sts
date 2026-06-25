"""Hermetic tests for the conviction-hold counterfactual harness math.

Covers only the pure, data-free helpers (efficiency ratio, ATR, MFI). The
data-loading / scoring path is exercised by the analysis script against parquet
and is intentionally not unit-tested here (no parquet in CI).
"""

import numpy as np
import pandas as pd

from scripts.analysis.conviction_hold_counterfactual import (
    atr_from_bars,
    kaufman_er,
    mfi_from_bars,
)


def test_kaufman_er_perfect_trend_is_one():
    closes = np.array([100.0, 101.0, 102.0, 103.0, 104.0])
    assert kaufman_er(closes) == 1.0


def test_kaufman_er_pure_chop_is_low():
    closes = np.array([100.0, 101.0, 100.0, 101.0, 100.0])
    # net move 0 over a long path => ER 0
    assert kaufman_er(closes) == 0.0


def test_kaufman_er_partial():
    closes = np.array([100.0, 102.0, 101.0, 103.0])  # net +3, path 2+1+2=5
    assert kaufman_er(closes) == 3.0 / 5.0


def test_kaufman_er_degenerate_inputs():
    assert kaufman_er(np.array([100.0])) == 0.0
    assert kaufman_er(np.array([])) == 0.0
    assert kaufman_er(np.array([100.0, 100.0])) == 0.0  # zero path


def _bars(rows):
    return pd.DataFrame(rows, columns=["high", "low", "close", "volume"])


def test_atr_from_bars_basic():
    bars = _bars([[10, 8, 9, 1], [11, 9, 10, 1], [12, 10, 11, 1]])
    atr = atr_from_bars(bars, period=14)
    # first TR = high-low = 2; subsequent TRs include prev close
    assert atr > 0


def test_atr_from_bars_too_few():
    assert atr_from_bars(_bars([[10, 8, 9, 1]]), period=14) == 0.0


def test_mfi_none_when_insufficient():
    bars = _bars([[10, 8, 9, 100]] * 5)
    assert mfi_from_bars(bars, period=14) is None


def test_mfi_all_up_saturates_high():
    # strictly rising typical price => all positive flow => MFI 100
    rows = [[float(10 + i), float(8 + i), float(9 + i), 100.0] for i in range(20)]
    val = mfi_from_bars(_bars(rows), period=14)
    assert val == 100.0


def test_mfi_all_down_saturates_low():
    rows = [[float(30 - i), float(28 - i), float(29 - i), 100.0] for i in range(20)]
    val = mfi_from_bars(_bars(rows), period=14)
    assert val is not None
    assert val < 10.0
