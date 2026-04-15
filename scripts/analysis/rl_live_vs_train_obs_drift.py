"""Compare live paper-trading obs distribution vs training obs distribution.

Live obs are the 31-dim vectors passed to the RL model at trade entry, captured in
kospi.rl_trades.metadata_json["obs"] since the obs-capture patch was deployed.

The 31-dim structure is: [25 scaled market features | position_side | contracts |
                          unrealized_pnl | sin(time) | cos(time) | progress]

Train distribution is computed by:
    1. Load training CSV (kospi200f_1m_clean.csv)
    2. Compute raw RL_FEATURE_COLUMNS features (25 dims)
    3. Apply the same StandardScaler used in production

Comparison is done on the market feature slice (dims 0-24) because the position/time
features are expected to differ in distribution by design.

Usage:
    python scripts/analysis/rl_live_vs_train_obs_drift.py --live-days 7

Outputs:
    - Per-feature mean/std for both populations
    - PSI (Population Stability Index) per feature
    - Flagged features with PSI > 0.25 (significant drift)

PSI Interpretation:
    < 0.10  → stable
    0.10–0.25 → moderate drift (monitor)
    > 0.25  → significant drift (investigate)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Number of market-feature dims in the obs vector (must match training config)
N_MARKET_FEATURES = 25


def load_live_obs(days: int) -> tuple[np.ndarray, list[str]]:
    """Read live obs samples from kospi.rl_trades metadata_json field.

    Returns:
        (obs_matrix, feature_names) where obs_matrix shape is (N, 31).
        Returns (empty, []) if no obs found.
    """
    import clickhouse_connect

    ch = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database="kospi",
    )

    result = ch.query(
        f"""
        SELECT metadata_json FROM kospi.rl_trades
        WHERE exit_date >= now() - INTERVAL {days} DAY
        ORDER BY exit_date DESC LIMIT 500
        """
    ).result_rows

    obs_list: list[list[float]] = []
    for (meta_json,) in result:
        try:
            meta = json.loads(meta_json) if isinstance(meta_json, str) else meta_json
        except (ValueError, TypeError):
            continue
        obs = meta.get("obs")
        if isinstance(obs, list) and all(isinstance(x, (int, float)) for x in obs):
            obs_list.append([float(x) for x in obs])

    if not obs_list:
        return np.empty((0, 0)), []

    matrix = np.asarray(obs_list, dtype=np.float64)
    # Full 31-dim feature names for reference
    from shared.ml.rl.features import RL_FEATURE_COLUMNS

    feat_names = list(RL_FEATURE_COLUMNS) + [
        "position_side",
        "contracts",
        "unrealized_pnl",
        "time_progress",
        "time_sin",
        "time_cos",
    ]
    return matrix, feat_names


def load_train_obs_sample(
    csv_path: Path, scaler_path: Path | None, n: int = 5000
) -> np.ndarray:
    """Sample scaled training market features from the CSV used to train the baseline model.

    Returns matrix of shape (N, N_MARKET_FEATURES) — scaled, matching the first 25
    dims of the live obs vector.
    """
    import joblib

    from shared.ml.rl.features import RL_FEATURE_COLUMNS, RLFeatureCalculator

    df = pd.read_csv(csv_path)
    if "datetime" not in df.columns:
        df["datetime"] = pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq="1min")

    calc = RLFeatureCalculator()
    feat_df = calc.calculate(df)
    feat_df = feat_df[RL_FEATURE_COLUMNS].dropna()

    if len(feat_df) > n:
        feat_df = feat_df.sample(n=n, random_state=42)

    raw = feat_df.to_numpy()

    # Apply scaler if available — live obs were scaled before being stored
    if scaler_path and scaler_path.exists():
        scaler = joblib.load(scaler_path)
        logger.info(f"Scaler loaded: {scaler_path} (n_features_in_={scaler.n_features_in_})")
        raw = scaler.transform(raw.astype(np.float32))
        raw = np.clip(raw, -5.0, 5.0)
    else:
        logger.warning("No scaler found — comparing raw (unscaled) training features vs scaled live obs. "
                       "Mean/std will differ even without drift.")

    return raw.astype(np.float64)


def compute_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index for a single feature."""
    if expected.size == 0 or actual.size == 0:
        return float("nan")
    breakpoints = np.quantile(expected, np.linspace(0, 1, bins + 1))
    breakpoints[0] -= 1e-9
    breakpoints[-1] += 1e-9
    unique_bp = np.unique(breakpoints)
    if len(unique_bp) < 2:
        return 0.0
    e_counts, _ = np.histogram(expected, bins=unique_bp)
    a_counts, _ = np.histogram(actual, bins=unique_bp)
    e_pct = np.clip(e_counts / max(e_counts.sum(), 1), 1e-6, None)
    a_pct = np.clip(a_counts / max(a_counts.sum(), 1), 1e-6, None)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare live paper-trading obs vs training obs distributions (PSI)"
    )
    parser.add_argument("--live-days", type=int, default=7, help="Days of live trades to load")
    parser.add_argument(
        "--train-data",
        type=Path,
        default=Path("data/kospi200f_1m_clean.csv"),
        help="Training CSV path",
    )
    parser.add_argument(
        "--scaler",
        type=Path,
        default=Path("models/futures/rl/scaler.joblib"),
        help="StandardScaler joblib path",
    )
    parser.add_argument(
        "--train-samples",
        type=int,
        default=5000,
        help="Max training obs samples to draw",
    )
    args = parser.parse_args()

    # --- Load live obs ---
    logger.info(f"Loading live obs from last {args.live_days} days ...")
    live, feat_names = load_live_obs(args.live_days)
    logger.info(f"Live obs shape: {live.shape}")

    if live.size == 0:
        print(
            "\nNO LIVE OBS CAPTURED — metadata_json does not contain 'obs' key.\n"
            "Fix: The obs-capture patch adds obs to signal.metadata in RLMPPOEntry,\n"
            "     and the orchestrator forwards it to position.metadata via the 'obs' key.\n"
            "     Wait for ≥50 new trades to accumulate before re-running this diagnostic."
        )
        sys.exit(2)

    print(f"\nLive obs samples: {live.shape[0]}  (dims: {live.shape[1]})")

    if live.shape[1] != 31:
        print(
            f"\nWARNING: Expected 31-dim obs but got {live.shape[1]}. "
            "Obs builder may have drifted from training config."
        )

    # Slice market features (first N_MARKET_FEATURES dims)
    live_market = live[:, :N_MARKET_FEATURES]

    # --- Load training obs ---
    if not args.train_data.exists():
        logger.warning(f"Training data not found at {args.train_data} — skipping train comparison.")
        print("\nCannot compare: training CSV not found.")
        return

    logger.info(f"Loading training features from {args.train_data} ...")
    train_market = load_train_obs_sample(args.train_data, args.scaler, n=args.train_samples)
    logger.info(f"Train obs shape: {train_market.shape}")
    print(f"Train obs samples: {train_market.shape[0]}  (dims: {train_market.shape[1]})\n")

    # Dimension mismatch check
    if train_market.shape[1] != live_market.shape[1]:
        print(
            f"\nDIMENSION MISMATCH: live market slice = {live_market.shape[1]} dims, "
            f"train market = {train_market.shape[1]} dims.\n"
            "RL obs builder may not match RL_FEATURE_COLUMNS in features.py."
        )
        sys.exit(3)

    # --- Per-feature PSI table ---
    from shared.ml.rl.features import RL_FEATURE_COLUMNS

    market_feat_names = list(RL_FEATURE_COLUMNS[:N_MARKET_FEATURES])

    print("Per-feature drift analysis (live market features vs scaled train):")
    print(f"{'feature':<28} {'live_mean':>10} {'live_std':>10} {'train_mean':>10} {'train_std':>10} {'PSI':>8}  status")
    print("-" * 90)

    high_drift = []
    moderate_drift = []
    for i, name in enumerate(market_feat_names):
        lv = live_market[:, i]
        tr = train_market[:, i]
        psi = compute_psi(tr, lv)
        status = "OK"
        if psi > 0.25:
            status = "DRIFT"
            high_drift.append((name, psi))
        elif psi > 0.10:
            status = "WATCH"
            moderate_drift.append((name, psi))
        print(
            f"{name:<28} {lv.mean():>10.4f} {lv.std():>10.4f} "
            f"{tr.mean():>10.4f} {tr.std():>10.4f} {psi:>8.3f}  {status}"
        )

    print("\nPSI Interpretation: <0.10 stable | 0.10-0.25 moderate drift | >0.25 significant drift")

    if high_drift:
        print(f"\nHIGH DRIFT features (PSI > 0.25): {len(high_drift)}")
        for name, psi in sorted(high_drift, key=lambda x: -x[1]):
            print(f"  {name:<28} PSI={psi:.3f}")
    else:
        print("\nNo features with PSI > 0.25 (no significant drift detected).")

    if moderate_drift:
        print(f"\nMODERATE DRIFT features (0.10 < PSI ≤ 0.25): {len(moderate_drift)}")
        for name, psi in sorted(moderate_drift, key=lambda x: -x[1]):
            print(f"  {name:<28} PSI={psi:.3f}")

    # --- Position/time feature stats (info only) ---
    if live.shape[1] >= 31:
        pos_labels = ["position_side", "contracts", "unrealized_pnl", "time_progress", "time_sin", "time_cos"]
        print("\nPosition + time feature stats (live only — no training baseline):")
        print(f"{'feature':<20} {'live_mean':>10} {'live_std':>10}")
        print("-" * 44)
        for j, label in enumerate(pos_labels):
            col = live[:, N_MARKET_FEATURES + j]
            print(f"{label:<20} {col.mean():>10.4f} {col.std():>10.4f}")


if __name__ == "__main__":
    main()
