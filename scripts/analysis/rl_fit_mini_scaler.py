"""Fit MinMaxScaler on kospi_mini_1m for domain-matched live obs normalization.

Saves artifact to models/futures/rl/scaler_mini.joblib. Does NOT overwrite
production scaler.joblib. Activation is opt-in via:
  - config/ml/rl_mppo.yaml: scaler_path_override field
  - RL_MPPO_SCALER_PATH env var (takes priority over config)

Usage:
    cd /home/deploy/project/kis_unified_sts
    source .venv/bin/activate
    python scripts/analysis/rl_fit_mini_scaler.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("rl_fit_mini_scaler")

OUT_PATH = ROOT / "models/futures/rl/scaler_mini.joblib"
DAYS = 180


def load_mini_bars(days: int = DAYS) -> pd.DataFrame:
    """Load recent kospi_mini_1m OHLCV bars from ClickHouse."""
    from shared.db.utils import clickhouse_client_from_env

    client = clickhouse_client_from_env(database="kospi")

    query = f"""
        SELECT datetime, open, high, low, close, volume
        FROM kospi.kospi_mini_1m
        WHERE datetime >= now() - INTERVAL {days} DAY
        ORDER BY datetime
    """
    rows = client.execute(query)
    df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
    logger.info(f"Loaded {len(df):,} kospi_mini_1m bars (last {days} days)")
    return df


def main() -> int:
    from shared.ml.rl.features import RL_FEATURE_COLUMNS, RLFeatureCalculator

    if OUT_PATH.exists():
        logger.warning(f"NOTE: {OUT_PATH} exists; will overwrite")

    df = load_mini_bars(days=DAYS)
    if len(df) < 1000:
        logger.error(f"Only {len(df)} mini bars available, need >= 1000")
        return 1

    calc = RLFeatureCalculator()
    feat_df = calc.calculate(df)
    feat_df = feat_df[RL_FEATURE_COLUMNS].dropna()

    logger.info(f"Features for scaler fit: {feat_df.shape} rows x {len(RL_FEATURE_COLUMNS)} cols")
    if feat_df.shape[0] < 500:
        logger.error(f"Only {feat_df.shape[0]} feature rows after dropna, need >= 500")
        return 1

    scaler = MinMaxScaler()
    scaler.fit(feat_df.to_numpy())

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, OUT_PATH)
    logger.info(f"Saved mini-fit scaler to {OUT_PATH}")

    import numpy as np
    logger.info(f"Features: {RL_FEATURE_COLUMNS}")
    logger.info(f"scaler.data_min_ (first 5): {scaler.data_min_[:5]}")
    logger.info(f"scaler.data_max_ (first 5): {scaler.data_max_[:5]}")
    logger.info(f"scaler.data_range_ (first 5): {scaler.data_range_[:5]}")

    # Sanity: compare with production scaler
    prod_path = ROOT / "models/futures/rl/scaler.joblib"
    if prod_path.exists():
        prod = joblib.load(prod_path)
        import numpy as np
        logger.info("\n--- Scaler range comparison (mini vs prod) ---")
        for i, col in enumerate(RL_FEATURE_COLUMNS):
            mini_r = scaler.data_range_[i]
            prod_r = prod.data_range_[i] if hasattr(prod, "data_range_") else float("nan")
            ratio = mini_r / prod_r if prod_r > 0 else float("nan")
            logger.info(f"  {col:30s}: mini={mini_r:.4f}, prod={prod_r:.4f}, ratio={ratio:.2f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
