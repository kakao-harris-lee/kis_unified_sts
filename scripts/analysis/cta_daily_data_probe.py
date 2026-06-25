"""Data-availability probe for THESIS B (daily/swing KOSPI200 futures momentum).

Binding-constraint check: there is NO `daily` futures parquet partition; only
`minute`. This script resamples the continuous near-month KOSPI200 future
(``101S6000``) minute bars to KST-session daily OHLCV and reports:

- calendar span and trading-day count,
- per-day minute-bar coverage (to flag thin / corrupt sessions),
- gap structure (missing weekdays),
- the longest contiguous "clean" daily window.

Run from the data-bearing checkout root so ``data/market`` resolves::

    .venv/bin/python .worktrees/futures-cta-swing/scripts/analysis/cta_daily_data_probe.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

SYMBOL = "101S6000"
# A liquid KOSPI200-future regular session has ~390 one-minute bars (09:00-15:45
# KST incl. close auction). Sessions far below this are thin / unreliable.
MIN_HEALTHY_MINUTE_BARS = 300


def _resolve_minute_dir() -> Path:
    """Locate the minute parquet partition for ``101S6000``."""
    candidates = [
        Path("data/market/futures/minute") / f"code={SYMBOL}",
        Path(__file__).resolve().parents[3]
        / "data/market/futures/minute"
        / f"code={SYMBOL}",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit(f"minute partition not found; tried: {candidates}")


def load_minute_bars(minute_dir: Path) -> pd.DataFrame:
    glob = str(minute_dir / "**" / "*.parquet")
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT datetime, open, high, low, close, volume
        FROM read_parquet('{glob}', hive_partitioning=1)
        ORDER BY datetime
        """).fetchdf()
    con.close()
    df["datetime"] = pd.to_datetime(df["datetime"])
    return df


def resample_daily(minute: pd.DataFrame) -> pd.DataFrame:
    """Resample minute bars to KST-session daily OHLCV with bar counts."""
    m = minute.copy()
    m["session"] = m["datetime"].dt.normalize()
    grouped = m.groupby("session")
    daily = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        minute_bars=("close", "size"),
    ).reset_index()
    daily = daily.rename(columns={"session": "date"})
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    return daily


def longest_clean_run(daily: pd.DataFrame) -> tuple[int, object, object]:
    """Longest contiguous run of healthy trading sessions (by bar count)."""
    healthy = daily[daily["minute_bars"] >= MIN_HEALTHY_MINUTE_BARS].reset_index(
        drop=True
    )
    if healthy.empty:
        return 0, None, None
    best_len = cur_len = 1
    best_start = cur_start = 0
    dates = list(healthy["date"])
    for i in range(1, len(dates)):
        gap_bdays = len(pd.bdate_range(dates[i - 1], dates[i])) - 1
        if gap_bdays <= 1:  # consecutive business day
            cur_len += 1
        else:
            cur_len = 1
            cur_start = i
        if cur_len > best_len:
            best_len = cur_len
            best_start = cur_start
    best_end = best_start + best_len - 1
    return best_len, dates[best_start], dates[best_end]


def main() -> int:
    minute_dir = _resolve_minute_dir()
    minute = load_minute_bars(minute_dir)
    if minute.empty:
        print("NO MINUTE DATA")
        return 1

    daily = resample_daily(minute)
    n_days = len(daily)
    first, last = daily["date"].iloc[0], daily["date"].iloc[-1]
    healthy = daily[daily["minute_bars"] >= MIN_HEALTHY_MINUTE_BARS]
    thin = daily[daily["minute_bars"] < MIN_HEALTHY_MINUTE_BARS]
    run_len, run_start, run_end = longest_clean_run(daily)

    cal_bdays = len(pd.bdate_range(first, last))

    print("=" * 70)
    print(f"DAILY DATA PROBE — {SYMBOL} (resampled from minute)")
    print("=" * 70)
    print(f"calendar span        : {first}  ->  {last}")
    print(f"calendar business-days: {cal_bdays}")
    print(f"trading days (sessions): {n_days}")
    print(f"  healthy (>= {MIN_HEALTHY_MINUTE_BARS} min-bars): {len(healthy)}")
    print(f"  thin    (<  {MIN_HEALTHY_MINUTE_BARS} min-bars): {len(thin)}")
    print(
        f"longest contiguous healthy run: {run_len} sessions "
        f"({run_start} -> {run_end})"
    )
    print()
    print("minute-bar count distribution per session:")
    print(daily["minute_bars"].describe().to_string())
    print()
    print("monthly session counts (healthy / total):")
    daily["ym"] = pd.to_datetime(daily["date"]).dt.to_period("M")
    monthly = daily.groupby("ym").agg(
        total=("minute_bars", "size"),
        healthy=("minute_bars", lambda s: int((s >= MIN_HEALTHY_MINUTE_BARS).sum())),
        median_bars=("minute_bars", "median"),
    )
    print(monthly.to_string())
    print()
    print("first 5 + last 5 sessions:")
    print(daily.drop(columns="ym").head().to_string(index=False))
    print(daily.drop(columns="ym").tail().to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
