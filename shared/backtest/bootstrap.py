"""Politis-Romano stationary block bootstrap for time-series resampling.

Phase 3 alternative gate (≥12 months calendar dependency replaced).

Background
----------
Standard non-parametric bootstrap (sample with replacement, individual
observations) breaks the serial correlation that defines a financial
time series. Block bootstrap preserves it: sample contiguous blocks
instead of single observations.

The Politis-Romano *stationary* variant draws block lengths from a
geometric distribution with mean ``p`` (rather than a fixed length).
This makes the resampled series stationary in the same sense the
original is, which matters for downstream Sharpe / EV calculations whose
asymptotic distributions assume stationarity.

Usage
-----

    from shared.backtest.bootstrap import stationary_block_bootstrap

    samples = stationary_block_bootstrap(
        df, n_samples=200, mean_block_minutes=5 * 24 * 60, seed=42
    )
    for resampled_df in samples:
        # run walk-forward, collect OOS EV
        ...

References
----------
- Politis & Romano (1994). "The Stationary Bootstrap." Journal of the
  American Statistical Association, 89(428), 1303-1313.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd

_DEFAULT_MEAN_BLOCK_MINUTES = 5 * 24 * 60  # ~5 trading days for 24h futures session


def _draw_block_starts_and_lengths(
    n_obs: int,
    target_length: int,
    mean_block_size: int,
    rng: np.random.Generator,
) -> Iterator[tuple[int, int]]:
    """Yield (start_index, length) pairs covering ``target_length`` observations.

    Block lengths are drawn from Geometric(p=1/mean_block_size). Each block
    starts at a uniform random index in [0, n_obs). Blocks wrap around the
    end of the data — this is the stationary variant's key property.
    """
    if mean_block_size <= 0:
        raise ValueError(f"mean_block_size must be positive, got {mean_block_size}")
    if n_obs <= 0:
        raise ValueError(f"n_obs must be positive, got {n_obs}")

    p = 1.0 / float(mean_block_size)
    accumulated = 0
    while accumulated < target_length:
        start = int(rng.integers(0, n_obs))
        # numpy's geometric counts trials until first success; matches the
        # Politis-Romano definition where block length L ~ Geometric(p).
        length = int(rng.geometric(p))
        # Cap at remaining target so we don't massively overshoot.
        length = min(length, target_length - accumulated)
        if length <= 0:
            continue
        yield start, length
        accumulated += length


def stationary_block_bootstrap(
    df: pd.DataFrame,
    *,
    n_samples: int,
    mean_block_minutes: int = _DEFAULT_MEAN_BLOCK_MINUTES,
    seed: int | None = None,
    timestamp_column: str = "timestamp",
) -> list[pd.DataFrame]:
    """Generate ``n_samples`` bootstrap-resampled copies of ``df``.

    The original ``timestamp_column`` is replaced with a contiguous synthetic
    index starting at the dataset's earliest real timestamp. This keeps
    downstream consumers (which expect monotonic minute-by-minute timestamps
    for VWAP, ATR, gap detection, etc.) happy without preserving the original
    calendar (which makes no sense after sampling with replacement).

    Args:
        df: Source dataframe; must be sorted by ``timestamp_column`` and have
            an even minute-bar cadence. Caller is responsible for deduping
            phantom prints.
        n_samples: Number of bootstrap samples to produce.
        mean_block_minutes: Mean block length in observations (typically
            minutes). Default ~5 trading days for 24h futures session.
        seed: RNG seed for reproducibility. ``None`` = OS entropy.
        timestamp_column: Name of the timestamp column to re-index.

    Returns:
        List of ``n_samples`` dataframes, each the same length as ``df`` and
        with a synthetic monotonic timestamp index.
    """
    if n_samples <= 0:
        raise ValueError(f"n_samples must be positive, got {n_samples}")
    if timestamp_column not in df.columns:
        raise ValueError(
            f"timestamp_column {timestamp_column!r} not found in df columns: "
            f"{list(df.columns)}"
        )

    df_sorted = df.sort_values(timestamp_column).reset_index(drop=True)
    n_obs = len(df_sorted)
    rng = np.random.default_rng(seed)

    # Pre-compute the synthetic timestamp index — every bootstrap sample
    # uses the same monotonic minute sequence starting at the original
    # min(timestamp). This keeps ATR/VWAP/spread computations consistent.
    base_ts = pd.to_datetime(df_sorted[timestamp_column].iloc[0])
    synthetic_ts = pd.date_range(
        start=base_ts, periods=n_obs, freq="1min", name=timestamp_column
    )

    samples: list[pd.DataFrame] = []
    for _ in range(n_samples):
        # Build the resampled index by concatenating block slices.
        idx_chunks: list[np.ndarray] = []
        for start, length in _draw_block_starts_and_lengths(
            n_obs=n_obs,
            target_length=n_obs,
            mean_block_size=mean_block_minutes,
            rng=rng,
        ):
            # Stationary bootstrap wraps when start + length exceeds n_obs.
            if start + length <= n_obs:
                idx_chunks.append(np.arange(start, start + length))
            else:
                head = np.arange(start, n_obs)
                tail = np.arange(0, length - len(head))
                idx_chunks.append(np.concatenate([head, tail]))

        idx = np.concatenate(idx_chunks)[:n_obs]  # exact target length
        sampled = df_sorted.iloc[idx].copy().reset_index(drop=True)
        sampled[timestamp_column] = synthetic_ts
        samples.append(sampled)

    return samples
