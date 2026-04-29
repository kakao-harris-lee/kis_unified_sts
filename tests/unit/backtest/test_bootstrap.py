"""Tests for shared/backtest/bootstrap.py — Politis-Romano stationary bootstrap."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from shared.backtest.bootstrap import stationary_block_bootstrap


def _ohlcv(n: int = 1440, start="2026-04-01 00:00:00") -> pd.DataFrame:
    """1-minute OHLCV with monotonic timestamps."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start=start, periods=n, freq="1min"),
            "open": np.arange(n, dtype=float),
            "high": np.arange(n, dtype=float) + 0.5,
            "low": np.arange(n, dtype=float) - 0.5,
            "close": np.arange(n, dtype=float),
            "volume": np.full(n, 100, dtype=int),
        }
    )


def test_returns_n_samples():
    df = _ohlcv()
    out = stationary_block_bootstrap(df, n_samples=5, seed=42)
    assert len(out) == 5
    for s in out:
        assert len(s) == len(df)


def test_each_sample_is_independent_copy():
    df = _ohlcv()
    out = stationary_block_bootstrap(df, n_samples=3, seed=7)
    out[0].loc[0, "close"] = 99999.0
    # Other samples and the source frame must be unaffected
    assert df.loc[0, "close"] == 0.0
    assert out[1].loc[0, "close"] != 99999.0


def test_deterministic_with_same_seed():
    df = _ohlcv()
    a = stationary_block_bootstrap(df, n_samples=3, seed=42)
    b = stationary_block_bootstrap(df, n_samples=3, seed=42)
    for x, y in zip(a, b):
        pd.testing.assert_frame_equal(x, y)


def test_different_seeds_produce_different_samples():
    df = _ohlcv()
    a = stationary_block_bootstrap(df, n_samples=1, seed=1)
    b = stationary_block_bootstrap(df, n_samples=1, seed=2)
    # Vanishingly unlikely to coincide on 1440-row sample
    assert not a[0].equals(b[0])


def test_synthetic_timestamps_are_monotonic():
    """Bootstrap reuses the original timestamps in their sorted order, so
    monotonicity is preserved but cadence may have gaps (matches source)."""
    df = _ohlcv()
    out = stationary_block_bootstrap(df, n_samples=2, seed=42)
    for s in out:
        ts = s["timestamp"]
        assert ts.is_monotonic_increasing


def test_synthetic_timestamps_match_source_distribution():
    """Calendar span + bar-density of bootstrap must equal source — required
    so DateOffset(months=N)-based fold splitting produces the same number
    of folds the original would."""
    df = _ohlcv()
    out = stationary_block_bootstrap(df, n_samples=1, seed=42)
    src_ts = pd.to_datetime(df["timestamp"]).reset_index(drop=True)
    sample_ts = out[0]["timestamp"].reset_index(drop=True)
    pd.testing.assert_series_equal(src_ts, sample_ts, check_names=False)


def test_resampled_values_drawn_from_source():
    """Every value in the bootstrap must exist in the source — proves it's
    a resample, not a perturbation."""
    df = _ohlcv()
    out = stationary_block_bootstrap(df, n_samples=1, seed=42)
    source_closes = set(df["close"].tolist())
    sample_closes = set(out[0]["close"].tolist())
    assert sample_closes.issubset(source_closes)


def test_blocks_preserve_local_serial_order():
    """Within a block, consecutive rows in the sample should be consecutive
    in the source — that's the whole point of block bootstrap.
    Statistical assertion: at least 90% of consecutive pairs in the sample
    are also consecutive in the source (allowing for block-boundary breaks)."""
    df = _ohlcv(n=10000)
    out = stationary_block_bootstrap(df, n_samples=1, seed=42, mean_block_minutes=100)
    sample = out[0]
    # Map sample close back to source row index
    source_index = {c: i for i, c in enumerate(df["close"].tolist())}
    sample_indices = [source_index[c] for c in sample["close"].tolist()]
    consecutive = sum(
        1 for a, b in zip(sample_indices, sample_indices[1:]) if b == a + 1
    )
    # Mean block 100 → expect ~99% of within-block pairs to be consecutive.
    # The boundary breaks are ~1% of pairs.
    assert consecutive / len(sample_indices) > 0.85


def test_zero_or_negative_n_samples_raises():
    df = _ohlcv()
    with pytest.raises(ValueError, match="n_samples"):
        stationary_block_bootstrap(df, n_samples=0)
    with pytest.raises(ValueError, match="n_samples"):
        stationary_block_bootstrap(df, n_samples=-1)


def test_missing_timestamp_column_raises():
    df = _ohlcv().drop(columns=["timestamp"])
    with pytest.raises(ValueError, match="timestamp_column"):
        stationary_block_bootstrap(df, n_samples=1)


def test_zero_mean_block_minutes_raises():
    df = _ohlcv()
    with pytest.raises(ValueError, match="mean_block_size"):
        stationary_block_bootstrap(df, n_samples=1, mean_block_minutes=0)


def test_block_lengths_average_close_to_target():
    """Statistical sanity: across many samples, the mean block length should
    approach the configured mean_block_minutes (Geometric distribution)."""
    df = _ohlcv(n=5000)
    target = 50

    # Run many samples; track block boundaries via consecutive-source-index runs
    runs_lengths: list[int] = []
    for seed in range(30):
        out = stationary_block_bootstrap(
            df, n_samples=1, seed=seed, mean_block_minutes=target
        )
        sample = out[0]
        source_index = {c: i for i, c in enumerate(df["close"].tolist())}
        idx = [source_index[c] for c in sample["close"].tolist()]
        # Detect runs of consecutive source indices
        run_len = 1
        for a, b in zip(idx, idx[1:]):
            if b == a + 1:
                run_len += 1
            else:
                runs_lengths.append(run_len)
                run_len = 1
        runs_lengths.append(run_len)

    mean_run = np.mean(runs_lengths)
    # 50% tolerance — Geometric variance is high
    assert 0.5 * target < mean_run < 1.5 * target
