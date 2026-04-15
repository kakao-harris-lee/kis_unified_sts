"""Validate mini-fit scaler on held-out 101S6000 data (2026-03-01 to present).

Runs the February champion model (mppo_best_5m_backup.zip) twice:
  - Run A: production scaler (scaler.joblib) — baseline
  - Run B: mini-fit scaler  (scaler_mini.joblib) — candidate

Success criterion (Task 1.2 plan): Sharpe degradation < 10%.

Usage:
    cd /home/deploy/project/kis_unified_sts
    source .venv/bin/activate
    python scripts/analysis/rl_backtest_with_mini_scaler.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("rl_backtest_with_mini_scaler")

# ── Paths ─────────────────────────────────────────────────────────────────────
# Use the February champion (genuine out-of-sample model; mppo_best may be retrained)
MODEL_PATH = ROOT / "models/futures/rl/mppo_best_5m_backup.zip"
PROD_SCALER_PATH = ROOT / "models/futures/rl/scaler.joblib"
MINI_SCALER_PATH = ROOT / "models/futures/rl/scaler_mini.joblib"
CONFIG_PATH = "ml/rl_mppo.yaml"

SYMBOL = "101S6000"
DATABASE = "kospi"
TABLE = "kospi200f_1m"
START_DATE = "2026-03-01"
END_DATE = "2026-04-14"
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
    """Compute features, apply scaler, split by date."""
    calc = RLFeatureCalculator()
    df = calc.calculate(df)
    df = df.dropna(subset=RL_FEATURE_COLUMNS)

    df["date"] = pd.to_datetime(df["datetime"]).dt.date
    all_dates = sorted(df["date"].unique())

    test_days, test_prices, valid_dates = [], [], []
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


def run_with_scaler(
    model,
    evaluator,
    scaler,
    scaler_label: str,
    df: pd.DataFrame,
) -> dict:
    """Prepare test days and evaluate model with given scaler."""
    logger.info(f"\n{'='*60}")
    logger.info(f"  Backtest with {scaler_label}")
    logger.info(f"{'='*60}")
    test_days, test_prices, valid_dates = prepare_test_days(df.copy(), scaler)
    if not test_days:
        logger.error("No valid test days after bar-count filter")
        return {}

    metrics = evaluator.evaluate_model(
        model,
        test_days,
        test_prices,
        slippage=0.0,
        deterministic=True,
    )

    n_days = len(test_days)
    date_first = valid_dates[0] if valid_dates else "?"
    date_last = valid_dates[-1] if valid_dates else "?"

    print(f"\n  Scaler         : {scaler_label}")
    print(f"  Period         : {date_first} to {date_last}")
    print(f"  Trading days   : {n_days}")
    print(f"  Total bars     : {sum(len(d) for d in test_days):,}")
    print(f"  Sharpe ratio   : {metrics.get('sharpe_ratio', float('nan')):.2f}")
    print(f"  Win rate       : {metrics.get('win_rate_pct', float('nan')):.1f}%")
    print(f"  Avg return/day : {metrics.get('avg_return_pct', float('nan')):.3f}%")
    print(f"  Total return   : {metrics.get('total_return_pct', float('nan')):.2f}%")
    print(f"  Max drawdown   : {metrics.get('max_drawdown_pct', float('nan')):.2f}%")
    print(f"  R/R ratio      : {metrics.get('rr_ratio', float('nan')):.2f}")
    print(f"  Total trades   : {metrics.get('total_trades', '?')}")

    daily_returns = metrics.get("daily_returns", [])
    if daily_returns:
        pos_days = sum(1 for r in daily_returns if r > 0)
        neg_days = sum(1 for r in daily_returns if r < 0)
        zero_days = sum(1 for r in daily_returns if r == 0)
        print(f"  Daily P&L dist : +{pos_days} / ={zero_days} / -{neg_days}")

    return metrics


def main() -> int:
    # Verify all paths exist
    for label, path in [
        ("Model (Feb champion)", MODEL_PATH),
        ("Prod scaler", PROD_SCALER_PATH),
        ("Mini scaler", MINI_SCALER_PATH),
    ]:
        if not path.exists():
            logger.error(f"{label} not found: {path}")
            return 1
        logger.info(f"{label}: {path}")

    # Load scalers
    prod_scaler = joblib.load(PROD_SCALER_PATH)
    mini_scaler = joblib.load(MINI_SCALER_PATH)
    logger.info(
        f"Prod scaler: n_features_in_={getattr(prod_scaler, 'n_features_in_', '?')}"
    )
    logger.info(
        f"Mini scaler: n_features_in_={getattr(mini_scaler, 'n_features_in_', '?')}"
    )

    # Load data (once, shared by both runs)
    df = load_data()
    if df.empty:
        logger.error("No data returned from ClickHouse")
        return 1

    # Load model
    from sb3_contrib import MaskablePPO

    model = MaskablePPO.load(str(MODEL_PATH))
    logger.info("Model loaded successfully")

    # Load evaluator
    from shared.ml.rl.evaluator import RLEvaluator

    evaluator = RLEvaluator(config_path=CONFIG_PATH)

    # Run A: production scaler (baseline)
    prod_metrics = run_with_scaler(model, evaluator, prod_scaler, "PRODUCTION scaler.joblib", df)
    if not prod_metrics:
        logger.error("Production scaler backtest failed — aborting")
        return 1

    # Run B: mini-fit scaler
    mini_metrics = run_with_scaler(model, evaluator, mini_scaler, "MINI-FIT scaler_mini.joblib", df)
    if not mini_metrics:
        logger.error("Mini scaler backtest failed — aborting")
        return 1

    # Compare
    prod_sh = float(prod_metrics.get("sharpe_ratio", 0.0))
    mini_sh = float(mini_metrics.get("sharpe_ratio", 0.0))

    print("\n" + "=" * 60)
    print("  Mini-Scaler Validation — Sharpe Delta Report")
    print("=" * 60)
    print(f"  Model          : {MODEL_PATH.name} (Feb champion)")
    print(f"  Production Sharpe : {prod_sh:.2f}")
    print(f"  Mini-fit Sharpe   : {mini_sh:.2f}")

    if prod_sh == 0.0:
        print("  WARNING: Production Sharpe is 0 — cannot compute delta percentage")
        delta_pct = float("nan")
    else:
        delta_pct = (mini_sh - prod_sh) / abs(prod_sh) * 100
        print(f"  Sharpe delta      : {delta_pct:+.1f}%")

    print()

    verdict: str
    if np.isnan(delta_pct):
        verdict = "INCONCLUSIVE — production Sharpe is 0"
        print(f"  Verdict: {verdict}")
        rc = 1
    elif delta_pct >= -10.0:
        verdict = "SAFE — mini scaler degradation < 10%; opt-in activation recommended"
        print(f"  Verdict: {verdict}")
        print("  Action : Set scaler_path_override: 'models/futures/rl/scaler_mini.joblib'")
        print("           in config/ml/rl_mppo.yaml, or export RL_MPPO_SCALER_PATH=...")
        rc = 0
    else:
        verdict = f"DO NOT ACTIVATE — Sharpe degradation {delta_pct:+.1f}% exceeds -10% threshold"
        print(f"  Verdict: {verdict}")
        rc = 2

    print("=" * 60 + "\n")

    # Save a brief log to /tmp for the caller
    with open("/tmp/mini_scaler_backtest.log", "w") as fh:
        fh.write(f"prod_sharpe={prod_sh:.4f}\n")
        fh.write(f"mini_sharpe={mini_sh:.4f}\n")
        fh.write(f"delta_pct={delta_pct:.2f}\n" if not np.isnan(delta_pct) else "delta_pct=nan\n")
        fh.write(f"verdict={verdict}\n")
        fh.write(
            f"prod_wr={prod_metrics.get('win_rate_pct', float('nan')):.1f}%\n"
        )
        fh.write(
            f"mini_wr={mini_metrics.get('win_rate_pct', float('nan')):.1f}%\n"
        )
        fh.write(
            f"prod_trades={prod_metrics.get('total_trades', '?')}\n"
        )
        fh.write(
            f"mini_trades={mini_metrics.get('total_trades', '?')}\n"
        )
    logger.info("Results written to /tmp/mini_scaler_backtest.log")

    return rc


if __name__ == "__main__":
    sys.exit(main())
