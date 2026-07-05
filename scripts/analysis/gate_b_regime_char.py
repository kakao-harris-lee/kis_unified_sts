"""Gate B — AdaptiveRegimeDetector ADX-threshold characterization (reproducer).

Answers #562's deferred question: with the now-canonical (doubled) ADX and the
UNCHANGED textbook thresholds (adx_strong_trend=25, adx_weak_trend=20), does the
detector over-classify TRENDING? Runs the current 25/20 against 50/40 (the
"old effective" calibration, since the pre-#562 ADX ran ~half-scale) and a
forward-return counterfactual per regime label.

Report: docs/analysis/2026-07-05-gate-b-regime-adx-characterization.md
Run:    PYTHONPATH=. .venv/bin/python scripts/analysis/gate_b_regime_char.py

Reads daily bars from data/market/stock/daily (parquet). Re-run on a longer,
multi-regime dataset (bull/bear/range, >=3y) before trusting the thresholds or
enabling adaptive regime mode.
"""

from __future__ import annotations

import glob
import warnings

import duckdb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from shared.regime.adaptive_detector import (  # noqa: E402
    AdaptiveRegimeConfig,
    AdaptiveRegimeDetector,
)

WINDOW = 55  # trailing bars per detect() call (>= min_bars 50 + warmup)
FWD = 5  # forward-return horizon (bars)
MAX_SYMBOLS = 250
MIN_BARS = WINDOW + FWD + 1
DAILY_ROOT = "data/market/stock/daily"


def _load(con: duckdb.DuckDBPyConnection, sym: str) -> pd.DataFrame:
    return con.execute(
        f"SELECT datetime, open, high, low, close, volume "
        f"FROM read_parquet('{DAILY_ROOT}/code={sym}/**/*.parquet') "
        f"ORDER BY datetime"
    ).df()


def _detector(strong: float, weak: float) -> AdaptiveRegimeDetector:
    cfg = AdaptiveRegimeConfig()
    cfg.adx_strong_trend = strong
    cfg.adx_weak_trend = weak
    return AdaptiveRegimeDetector(cfg)


def main() -> None:
    con = duckdb.connect()
    dirs = sorted(glob.glob(f"{DAILY_ROOT}/code=*"))
    det_cur = _detector(25.0, 20.0)  # current (post-#562, canonical ADX)
    det_h2h = _detector(50.0, 40.0)  # head-to-head: "old effective" calibration

    rows: list[dict] = []
    n_sym = 0
    for d in dirs:
        sym = d.split("code=")[-1]
        try:
            df = _load(con, sym)
        except Exception:
            continue
        n = len(df)
        if n < MIN_BARS:
            continue
        n_sym += 1
        if n_sym > MAX_SYMBOLS:
            break
        closes = df["close"].to_numpy(dtype=float)
        for i in range(WINDOW, n - FWD):
            window = df.iloc[i - WINDOW : i].reset_index(drop=True)
            entry = closes[i - 1]
            fwd = (closes[i - 1 + FWD] - entry) / entry if entry > 0 else np.nan
            sig_c = det_cur.detect(window)
            sig_h = det_h2h.detect(window)
            rows.append(
                {
                    "adx": sig_c.indicators.get("adx") if sig_c.indicators else None,
                    "state_cur": str(sig_c.state),
                    "state_h2h": str(sig_h.state),
                    "fwd": fwd,
                }
            )

    r = pd.DataFrame(rows)
    print(f"symbols used: {n_sym - 1}   observations: {len(r)}")
    print("=" * 64)

    adx = r["adx"].dropna()
    print("\n[1] Canonical ADX distribution (what 25/20 splits):")
    print(
        f"  n={len(adx)}  mean={adx.mean():.2f}  median={adx.median():.2f}  "
        f"p90={adx.quantile(0.9):.2f}"
    )
    print(f"  P(ADX>25 strong) = {(adx > 25).mean() * 100:5.1f}%")
    print(f"  P(20<=ADX<=25)   = {((adx >= 20) & (adx <= 25)).mean() * 100:5.1f}%")
    print(f"  P(ADX<20 weak)   = {(adx < 20).mean() * 100:5.1f}%")
    print(f"  P(ADX>40)        = {(adx > 40).mean() * 100:5.1f}%")

    def _dist(col: str) -> pd.Series:
        return r[col].value_counts(normalize=True) * 100

    print("\n[2] Regime distribution — CURRENT thresholds 25/20 (canonical ADX):")
    for k, v in _dist("state_cur").items():
        print(f"  {k:20s} {v:5.1f}%")

    print("\n[3] Head-to-head — thresholds 50/40 ('old effective' calibration):")
    for k, v in _dist("state_h2h").items():
        print(f"  {k:20s} {v:5.1f}%")

    trend_cur = r["state_cur"].str.contains("TRENDING").mean() * 100
    trend_h2h = r["state_h2h"].str.contains("TRENDING").mean() * 100
    print(
        f"\n  TRENDING share: 25/20 = {trend_cur:.1f}%   vs   50/40 = {trend_h2h:.1f}%   "
        f"(shift {trend_cur - trend_h2h:+.1f}pp)"
    )

    print(f"\n[4] Counterfactual — mean forward {FWD}-bar return by CURRENT regime:")
    g = r.dropna(subset=["fwd"]).groupby("state_cur")["fwd"]
    for state, sub in g:
        print(
            f"  {state:20s} n={len(sub):6d}  mean={sub.mean() * 100:+6.3f}%  "
            f"median={sub.median() * 100:+6.3f}%"
        )
    overall = r["fwd"].dropna()
    print(f"  {'(ALL)':20s} n={len(overall):6d}  mean={overall.mean() * 100:+6.3f}%")

    bull = r[r.state_cur.str.contains("BULL")]["fwd"].dropna()
    bear = r[r.state_cur.str.contains("BEAR")]["fwd"].dropna()
    if len(bull) and len(bear):
        print(
            f"\n  directional: BULL fwd {bull.mean() * 100:+.3f}%  vs  "
            f"BEAR fwd {bear.mean() * 100:+.3f}%  "
            f"(spread {(bull.mean() - bear.mean()) * 100:+.3f}pp)"
        )


if __name__ == "__main__":
    main()
