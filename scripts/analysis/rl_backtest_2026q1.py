"""Rolling backtest — mppo_best on 2026-03-01 to 2026-04-14 data.

Loads the champion model and the production scaler, runs day-by-day
evaluation on the period AFTER the model's original training window to
quantify out-of-sample / regime-shift degradation.

Usage:
    cd /home/deploy/project/kis_unified_sts
    source .venv/bin/activate
    python scripts/analysis/rl_backtest_2026q1.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# ── project root on sys.path ─────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS  # noqa: E402
from shared.ml.rl.evaluator import RLEvaluator  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("rl_backtest_2026q1")

# ── Configuration ─────────────────────────────────────────────────────────────
MODEL_PATH = ROOT / "models/futures/rl/mppo_best/best_model.zip"
SCALER_PATH = ROOT / "models/futures/rl/scaler.joblib"
CONFIG_PATH = "ml/rl_mppo.yaml"

SYMBOL = "101S6000"
DATABASE = "kospi"
TABLE = "kospi200f_1m"
START_DATE = "2026-03-01"
END_DATE = "2026-04-14"

# Minimum bars per day to consider valid (matches train_rl.py default)
MIN_BARS_PER_DAY = 300


def load_data() -> pd.DataFrame:
    """Load 2026-03+ OHLCV data from ClickHouse."""
    from clickhouse_driver import Client as CHSyncClient

    client = CHSyncClient(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", os.getenv("CLICKHOUSE_PORT", "9000"))),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "@1tidh6ls6ls"),
    )

    query = f"""
        SELECT datetime, open, high, low, close, volume
        FROM {DATABASE}.{TABLE}
        WHERE code = %(symbol)s
          AND datetime >= %(start_dt)s
          AND datetime <= %(end_dt)s
        ORDER BY datetime
    """
    params = {
        "symbol": SYMBOL,
        "start_dt": pd.to_datetime(START_DATE).to_pydatetime(),
        "end_dt": pd.to_datetime(END_DATE + " 23:59:59").to_pydatetime(),
    }

    rows = client.execute(query, params)
    df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
    logger.info(f"Loaded {len(df):,} rows from {DATABASE}.{TABLE} ({START_DATE} ~ {END_DATE})")
    return df


def prepare_test_days(
    df: pd.DataFrame,
    scaler,
) -> tuple[list[np.ndarray], list[np.ndarray], list]:
    """Compute features, apply scaler, split by date.

    Returns:
        (test_days, test_prices, valid_dates)
    """
    calc = RLFeatureCalculator()
    df = calc.calculate(df)
    df = df.dropna(subset=RL_FEATURE_COLUMNS)

    df["date"] = pd.to_datetime(df["datetime"]).dt.date
    all_dates = sorted(df["date"].unique())

    test_days = []
    test_prices = []
    valid_dates = []

    skipped = 0
    for d in all_dates:
        day_df = df[df["date"] == d]
        if len(day_df) < MIN_BARS_PER_DAY:
            logger.debug(f"Skipping {d} — only {len(day_df)} bars")
            skipped += 1
            continue
        features = scaler.transform(day_df[RL_FEATURE_COLUMNS].values).astype(np.float32)
        prices = day_df[["open", "high", "low", "close"]].values.astype(np.float32)
        test_days.append(features)
        test_prices.append(prices)
        valid_dates.append(d)

    logger.info(
        f"Valid days: {len(valid_dates)} (skipped {skipped} days with <{MIN_BARS_PER_DAY} bars)"
    )
    return test_days, test_prices, valid_dates


def run() -> None:
    # 1. Verify paths
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
    if not SCALER_PATH.exists():
        raise FileNotFoundError(f"Scaler not found: {SCALER_PATH}")

    logger.info(f"Model : {MODEL_PATH}")
    logger.info(f"Scaler: {SCALER_PATH}")

    # 2. Load scaler
    scaler = joblib.load(SCALER_PATH)
    logger.info(f"Scaler loaded — n_features_in={getattr(scaler, 'n_features_in_', '?')}")

    # 3. Load data
    df = load_data()
    if df.empty:
        raise ValueError("No data returned from ClickHouse.")

    # 4. Prepare test arrays
    test_days, test_prices, valid_dates = prepare_test_days(df, scaler)
    if not test_days:
        raise ValueError("No valid test days after bar-count filter.")

    # 5. Load model
    from sb3_contrib import MaskablePPO
    model = MaskablePPO.load(str(MODEL_PATH))
    logger.info("Model loaded successfully.")

    # 6. Run evaluation
    evaluator = RLEvaluator(config_path=CONFIG_PATH)
    metrics = evaluator.evaluate_model(
        model,
        test_days,
        test_prices,
        slippage=0.0,
        deterministic=True,
    )

    # 7. Print results
    n_days = len(test_days)
    date_first = valid_dates[0] if valid_dates else "?"
    date_last = valid_dates[-1] if valid_dates else "?"

    print("\n" + "=" * 60)
    print("  Rolling Backtest Results — mppo_best on 2026-03+ data")
    print("=" * 60)
    print(f"  Period         : {date_first} to {date_last}")
    print(f"  Trading days   : {n_days}")
    print(f"  Total bars     : {sum(len(d) for d in test_days):,}")
    print(f"  Sharpe ratio   : {metrics['sharpe_ratio']:.2f}")
    print(f"  Win rate       : {metrics['win_rate_pct']:.1f}%")
    print(f"  Avg return/day : {metrics['avg_return_pct']:.3f}%")
    print(f"  Total return   : {metrics['total_return_pct']:.2f}%")
    print(f"  Max drawdown   : {metrics['max_drawdown_pct']:.2f}%")
    print(f"  R/R ratio      : {metrics['rr_ratio']:.2f}")
    print(f"  Total trades   : {metrics['total_trades']}")
    print("=" * 60 + "\n")

    # Per-day trade distribution
    daily_returns = metrics.get("daily_returns", [])
    if daily_returns:
        pos_days = sum(1 for r in daily_returns if r > 0)
        neg_days = sum(1 for r in daily_returns if r < 0)
        zero_days = sum(1 for r in daily_returns if r == 0)
        print(f"  Daily P&L distribution: +{pos_days} / ={zero_days} / -{neg_days}")

    return metrics


if __name__ == "__main__":
    run()
