"""Test whether production scaler (fit on 101S6000 연결선물) is domain-compatible
with live trading symbols (A05xxx mini contracts).

Outputs:
1. Per-feature scaled-value distribution (mean/std/min/max) under both scalers
2. KS statistic per feature between distributions
3. Verdict: scaler re-fit on mini data warranted or not
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def load_mini_bars(days: int = 180) -> pd.DataFrame:
    import clickhouse_connect

    # CLICKHOUSE_PORT in this project is the HTTP port (8123).
    # clickhouse_connect uses HTTP protocol, so port=8123 is correct.
    ch = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database="kospi",
    )
    # Use the most liquid front-month mini code for the period
    # Group all mini codes together (they are the same product, rolling contracts)
    q = f"""
        SELECT datetime, open, high, low, close, volume
        FROM kospi.kospi_mini_1m
        WHERE datetime >= now() - INTERVAL {days} DAY
        ORDER BY datetime
    """
    rows = ch.query(q).result_rows
    df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
    return df


def load_101s_bars(
    sample_path: Path = Path("data/kospi200f_1m_clean.csv"),
) -> pd.DataFrame:
    """Load 101S6000 bars from the canonical training CSV."""
    return pd.read_csv(sample_path)


def main() -> int:
    from scipy.stats import ks_2samp
    from sklearn.preprocessing import MinMaxScaler

    from shared.ml.rl.features import RL_FEATURE_COLUMNS, RLFeatureCalculator

    prod_scaler_path = Path("models/futures/rl/scaler.joblib")
    if not prod_scaler_path.exists():
        print(f"FAIL: {prod_scaler_path} not found")
        return 1
    prod_scaler = joblib.load(prod_scaler_path)

    print("Loading 101S6000 training data ...")
    df_101s = load_101s_bars()
    print(f"  101S rows: {len(df_101s)}")

    print("Loading recent A05xxx mini data (180 days) ...")
    df_mini = load_mini_bars(180)
    print(f"  Mini rows: {len(df_mini)}")
    if len(df_mini) < 1000:
        print("WARN: mini data too sparse (<1000 rows) — results unreliable")

    calc = RLFeatureCalculator()
    feats_101s_df = calc.calculate(df_101s)
    feats_mini_df = calc.calculate(df_mini)

    # Extract only RL_FEATURE_COLUMNS and drop NaN rows
    feats_101s = feats_101s_df[RL_FEATURE_COLUMNS].dropna()
    feats_mini = feats_mini_df[RL_FEATURE_COLUMNS].dropna()
    print(f"  101S features: {feats_101s.shape}, Mini features: {feats_mini.shape}")

    if feats_mini.shape[0] < 500:
        print("ERROR: insufficient mini feature rows (<500) after feature calc — abort")
        return 2

    # Fit a new scaler on mini (domain-matched baseline)
    mini_scaler = MinMaxScaler()
    mini_scaler.fit(feats_mini.to_numpy())

    # Transform both datasets with both scalers
    scaled_mini_prod = prod_scaler.transform(feats_mini.to_numpy())   # as-is live path
    scaled_mini_mini = mini_scaler.transform(feats_mini.to_numpy())   # domain-matched
    scaled_101s_prod = prod_scaler.transform(feats_101s.to_numpy())   # training-time baseline

    print(f"\n{'feature':<32} {'101S_prod_med':>13} {'mini_prod_med':>13} "
          f"{'mini_self_med':>13} {'KS(prod vs self)':>18} {'%_clipped_prod':>15}")
    print("-" * 112)

    drift_count = 0
    clip_count = 0
    drift_features: list[tuple[str, float, float]] = []

    for i, name in enumerate(RL_FEATURE_COLUMNS):
        m_101s_prod = float(np.median(scaled_101s_prod[:, i]))
        m_mini_prod = float(np.median(scaled_mini_prod[:, i]))
        m_mini_self = float(np.median(scaled_mini_mini[:, i]))
        ks_stat, _ = ks_2samp(scaled_mini_prod[:, i], scaled_mini_mini[:, i])
        # % of mini data that falls outside [0, 1] under prod scaler (out-of-range clipping)
        outside = float(
            np.mean((scaled_mini_prod[:, i] < 0) | (scaled_mini_prod[:, i] > 1)) * 100
        )
        flags = ""
        if ks_stat > 0.3:
            flags += " DRIFT"
            drift_count += 1
            drift_features.append((name, ks_stat, outside))
        if outside > 5.0:
            flags += " CLIP"
            clip_count += 1
            if not any(f[0] == name for f in drift_features):
                drift_features.append((name, ks_stat, outside))
        print(
            f"{name:<32} {m_101s_prod:>13.3f} {m_mini_prod:>13.3f} "
            f"{m_mini_self:>13.3f} {ks_stat:>18.3f} {outside:>14.1f}%{flags}"
        )

    print(f"\nSummary: {drift_count} features with KS > 0.3, "
          f"{clip_count} features with >5% out-of-range under prod scaler.")

    if drift_features:
        print("\nTop drifting/clipping features:")
        drift_features.sort(key=lambda x: x[1], reverse=True)
        for name, ks, clip in drift_features[:5]:
            print(f"  {name}: KS={ks:.3f}, clipped={clip:.1f}%")

    print("\nVerdict:")
    if drift_count >= 5 or clip_count >= 3:
        print("  WARNING: Scaler domain mismatch CONFIRMED. Re-fit on mini data recommended.")
        print("  Next step: Task 1.2.4 — backtest with mini-fit scaler on held-out 101S6000 data")
        verdict = "CONFIRMED"
    elif drift_count >= 2:
        print("  PARTIAL: Partial drift observed. Consider re-fit if live performance doesn't improve after other fixes.")
        verdict = "PARTIAL"
    else:
        print("  OK: Scaler is domain-robust. Mismatch is NOT the primary cause of live degradation.")
        verdict = "NOT_PRIMARY_CAUSE"

    print(f"\nVerdict code: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
