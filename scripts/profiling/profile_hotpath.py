#!/usr/bin/env python3
"""Profile the indicator + forecasting hot paths (line-level).

Reusable, non-intrusive profiler for the momentum-indicator and HAR-RV
forecasting compute paths. It does not modify any source; target functions are
registered with ``line_profiler`` programmatically. Synthetic OHLCV/RV inputs
are used, so this measures *compute cost*, not data-dependent behaviour.

Two passes:
  1. Clean wall-clock (no profiler overhead) -> real us/ms per component.
  2. line_profiler -> line-level attribution inside the hottest functions.

Usage (from repo root, dev extras installed for line_profiler):
    pip install -e ".[dev]"
    python scripts/profiling/profile_hotpath.py

See scripts/profiling/README.md for interpretation and the optimization history.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from shared.forecasting.config import HARRVConfig
from shared.forecasting.realized_variance import (
    compute_intraday_realized_variance,
    daily_rv_series,
    resample_to_5min,
)
from shared.forecasting.volatility_har_rv import (
    VolatilityForecaster,
    _build_har_regressors,
)
from shared.indicators.momentum import (
    CCICalculator,
    MACDCalculator,
    OBVDataFrameCalculator,
    RSICalculator,
    StochasticCalculator,
    TRIXCalculator,
    WilliamsRCalculator,
    calculate_all_momentum,
)

RNG = np.random.default_rng(7)


def make_ohlcv(n: int) -> pd.DataFrame:
    """Realistic OHLCV window (random-walk close, bounded H/L, positive volume)."""
    close = 100 + np.cumsum(RNG.normal(0, 0.3, n))
    high = close + np.abs(RNG.normal(0, 0.2, n))
    low = close - np.abs(RNG.normal(0, 0.2, n))
    open_ = close + RNG.normal(0, 0.1, n)
    vol = RNG.integers(1000, 100_000, n).astype(float)
    idx = pd.date_range("2025-01-02 00:00", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def make_1m_multiday(days: int, minutes_per_day: int = 390) -> pd.DataFrame:
    """1-minute bars over ``days`` business days, KST 09:00-15:29, UTC-indexed."""
    day_starts = pd.bdate_range("2025-01-02", periods=days, tz="Asia/Seoul")
    parts = []
    for ds in day_starts:
        base = ds.normalize() + pd.Timedelta(hours=9)  # 09:00 KST
        parts.append(pd.date_range(base, periods=minutes_per_day, freq="1min"))
    idx = parts[0]
    for p in parts[1:]:
        idx = idx.append(p)
    n = len(idx)
    close = 100 + np.cumsum(RNG.normal(0, 0.15, n))
    return pd.DataFrame({"close": close}, index=idx.tz_convert("UTC"))


def make_daily_rv(days: int) -> pd.Series:
    """Smooth, highly-autoregressive daily RV (deterministic) so HAR-RV fit passes."""
    g = np.random.default_rng(123)
    t = np.arange(days)
    trend = 1e-4 * (1.0 + 0.5 * np.sin(t / 20.0) + 0.001 * t)
    rv = np.clip(trend + g.normal(0, 1e-6, days), 1e-8, None)
    idx = pd.bdate_range("2024-06-03", periods=days).date
    return pd.Series(rv, index=idx, name="rv")


def _bench(fn, iters: int) -> float:
    """Return mean ms/call over ``iters``."""
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    return (time.perf_counter() - t0) / iters * 1e3


def wall_clock_report() -> None:
    print("=" * 78)
    print("PASS 1 - WALL-CLOCK (no profiler overhead), real ms/call")
    print("=" * 78)

    win = make_ohlcv(250)
    iters = 2000

    calcs = {
        "TRIXCalculator.calculate": lambda d: TRIXCalculator().calculate(d),
        "CCICalculator.calculate": lambda d: CCICalculator().calculate(d),
        "MACDCalculator.calculate": lambda d: MACDCalculator().calculate(d),
        "StochasticCalculator.calculate": lambda d: StochasticCalculator().calculate(d),
        "WilliamsRCalculator.calculate": lambda d: WilliamsRCalculator().calculate(d),
        "OBVDataFrameCalculator.calculate": lambda d: OBVDataFrameCalculator().calculate(
            d
        ),
        "RSICalculator.calculate": lambda d: RSICalculator().calculate(d),
    }
    print(f"\n[indicators] window=250 bars, iters={iters}")
    rows = []
    for name, fn in calcs.items():
        d = win.copy()
        # bind loop vars as defaults (lambda is consumed within the iteration)
        rows.append((name, _bench(lambda fn=fn, d=d: fn(d), iters)))
    agg = _bench(lambda: calculate_all_momentum(win.copy()), iters)
    rows.sort(key=lambda r: r[1], reverse=True)
    total_parts = sum(r[1] for r in rows)
    for name, ms in rows:
        share = ms / total_parts * 100
        print(f"  {name:38s} {ms * 1000:8.1f} us/call  {share:5.1f}%")
    print(f"  {'-' * 38} {'-' * 8}")
    print(
        f"  {'calculate_all_momentum (full)':38s} {agg * 1000:8.1f} us/call  (incl .copy)"
    )

    print("\n[forecasting]")
    bars = make_1m_multiday(60)
    print(f"  daily_rv_series input: {len(bars):,} 1m bars over 60 business days")
    ms_rv = _bench(lambda: daily_rv_series(bars), 50)
    print(f"  {'daily_rv_series (60d of 1m bars)':38s} {ms_rv:8.2f} ms/call")

    rv_hist = make_daily_rv(250)
    cfg = HARRVConfig(min_r2_oos=-1.0)  # profiling harness: don't gate on fit quality
    fc = VolatilityForecaster(cfg)
    ms_fit = _bench(lambda: fc.fit(rv_hist), 200)
    fc.fit(rv_hist)
    now = datetime.now(UTC)
    ms_fore = _bench(lambda: fc.forecast(now, 380.0), 5000)
    print(f"  {'VolatilityForecaster.fit (250d)':38s} {ms_fit:8.3f} ms/call")
    print(f"  {'VolatilityForecaster.forecast':38s} {ms_fore * 1000:8.2f} us/call")


def line_profiler_report() -> None:
    from line_profiler import LineProfiler

    print("\n" + "=" * 78)
    print("PASS 2 - line_profiler (line-level attribution inside hot functions)")
    print("=" * 78)

    lp = LineProfiler()
    for fn in (
        calculate_all_momentum,
        TRIXCalculator.calculate,
        CCICalculator.calculate,
        MACDCalculator.calculate,
        StochasticCalculator.calculate,
        WilliamsRCalculator.calculate,
        OBVDataFrameCalculator.calculate,
        RSICalculator.calculate,
        daily_rv_series,
        compute_intraday_realized_variance,
        resample_to_5min,
        VolatilityForecaster.fit,
        _build_har_regressors,
    ):
        lp.add_function(fn)

    win = make_ohlcv(250)
    bars = make_1m_multiday(60)
    rv_hist = make_daily_rv(250)
    fc = VolatilityForecaster(HARRVConfig(min_r2_oos=-1.0))

    def workload() -> None:
        for _ in range(500):
            calculate_all_momentum(win.copy())
        for _ in range(30):
            daily_rv_series(bars)
        for _ in range(100):
            fc.fit(rv_hist)

    lp.runcall(workload)
    lp.print_stats(output_unit=1e-6)  # microseconds


def main() -> None:
    print(f"numpy {np.__version__}  pandas {pd.__version__}\n")
    wall_clock_report()
    line_profiler_report()


if __name__ == "__main__":
    main()
