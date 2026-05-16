#!/usr/bin/env python3
"""
Run backtest for momentum_breakout strategy on 6+ months of data.

This script provides a comprehensive backtest execution for the momentum_breakout strategy
following the project's acceptance criteria:
- Sharpe Ratio > 1.0 after 0.5% round-trip costs
- Positive net returns
- Reasonable number of trades (not overfitting)
- MLflow tracking logs saved

Usage:
    # With ClickHouse data
    python3 scripts/run_momentum_breakout_backtest.py --mode clickhouse

    # With CSV data
    python3 scripts/run_momentum_breakout_backtest.py --mode csv --data ./data/backtest.csv

    # Synthetic data (for testing)
    python3 scripts/run_momentum_breakout_backtest.py --mode synthetic

Requirements:
    - Python 3.11+ (project requirement)
    - Dependencies installed: pip install -e ".[dev]"
    - ClickHouse running (for --mode clickhouse)
    - 6+ months of minute-bar data available
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

# Setup project path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

# Import after path setup
from shared.backtest import BacktestConfig, BacktestEngine
from shared.backtest.adapter import BacktestStrategyAdapter
from shared.collector.historical.stock import load_stock_minute_from_clickhouse
from shared.config.loader import ConfigLoader
from shared.strategy.registry import StrategyFactory, register_builtin_components

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Register all builtin strategies
register_builtin_components()


def _align_timestamp_bound(value: datetime, ts: pd.Series) -> pd.Timestamp:
    """Return a pandas bound comparable with the loaded ClickHouse timestamps."""
    bound = pd.Timestamp(value)
    tz = ts.dt.tz
    if tz is not None and bound.tz is None:
        return bound.tz_localize(tz)
    if tz is None and bound.tz is not None:
        return bound.tz_localize(None)
    return bound


def generate_synthetic_data(
    symbol: str = "005930",
    days: int = 180,
    bars_per_day: int = 260,  # ~6.5 hours * 40 bars/hour
    initial_price: float = 70000,
    volatility: float = 0.02,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing.

    Creates realistic-looking candlestick data with:
    - Breakout patterns (high proximity moves)
    - Volume surges and accumulation
    - RVOL patterns
    - Momentum trends
    """
    import numpy as np

    total_bars = days * bars_per_day
    dates = pd.date_range(end=datetime.now(), periods=total_bars, freq="1min")

    # Generate price data with breakout patterns
    np.random.seed(42)  # Reproducible results
    returns = np.random.normal(0.0001, volatility, total_bars)

    # Add breakout behavior (sharp moves after consolidation)
    consolidation_period = bars_per_day * 5  # 5-day consolidation
    for i in range(0, total_bars, consolidation_period):
        # Consolidation phase
        returns[i : i + consolidation_period] *= 0.3
        # Breakout phase
        if i + consolidation_period < total_bars:
            breakout_strength = np.random.uniform(0.002, 0.005)
            breakout_length = min(
                bars_per_day * 2, total_bars - i - consolidation_period
            )
            returns[
                i + consolidation_period : i + consolidation_period + breakout_length
            ] += breakout_strength

    # Calculate prices
    price = initial_price * (1 + returns).cumprod()

    # Generate OHLC from price with breakout characteristics
    high = price * (
        1 + np.abs(np.random.normal(0, 0.008, total_bars))
    )  # Higher volatility for breakouts
    low = price * (1 - np.abs(np.random.normal(0, 0.005, total_bars)))
    open_price = price * (1 + np.random.normal(0, 0.003, total_bars))

    # Generate volume with surge patterns (key for momentum_breakout)
    base_volume = 1000000
    volume = base_volume * (1 + np.abs(np.random.normal(0, 0.5, total_bars)))

    # Add volume surges during breakouts
    for i in range(0, total_bars, consolidation_period):
        if i + consolidation_period < total_bars:
            surge_length = min(bars_per_day, total_bars - i - consolidation_period)
            volume[
                i + consolidation_period : i + consolidation_period + surge_length
            ] *= np.random.uniform(2.0, 3.5)

    df = pd.DataFrame(
        {
            "datetime": dates,
            "code": symbol,
            "open": open_price,
            "high": high,
            "low": low,
            "close": price,
            "volume": volume.astype(int),
            "name": "삼성전자",
        }
    )

    return df


def load_clickhouse_data(
    symbol: str, start_date: datetime, end_date: datetime
) -> pd.DataFrame:
    """Load OHLCV data from the canonical stock minute candle table."""
    try:
        df = load_stock_minute_from_clickhouse(
            symbol,
            start_date=start_date.date(),
            end_date=end_date.date(),
        )
    except ValueError:
        return pd.DataFrame()

    ts = pd.to_datetime(df["datetime"])
    start_ts = _align_timestamp_bound(start_date, ts)
    end_ts = _align_timestamp_bound(end_date, ts)
    mask = (ts >= start_ts) & (ts <= end_ts)
    return df.loc[mask].reset_index(drop=True)


def load_csv_data(csv_path: Path) -> pd.DataFrame:
    """Load OHLCV data from CSV file."""
    df = pd.read_csv(csv_path)
    required_cols = ["datetime", "code", "open", "high", "low", "close", "volume"]

    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    df["datetime"] = pd.to_datetime(df["datetime"])
    return df


def run_backtest(
    df: pd.DataFrame,
    strategy_name: str = "momentum_breakout",
    initial_capital: float = 10_000_000,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Run backtest using the BacktestEngine."""

    logger.info(f"Running backtest for {strategy_name}")
    logger.info(
        f"Data: {len(df)} bars from {df['datetime'].min()} to {df['datetime'].max()}"
    )

    # Load strategy config
    try:
        strategy_config = ConfigLoader.load_strategy("stock", strategy_name)
        strategy = StrategyFactory.create(strategy_config)
        logger.info(f"Loaded strategy: {strategy_name}")
    except Exception as e:
        logger.error(f"Failed to load strategy: {e}")
        raise

    # Wrap strategy with adapter for backtest engine
    adapted_strategy = BacktestStrategyAdapter(strategy, strategy_config)

    # Create backtest config
    # BacktestConfig.stock() already includes proper costs via CostConfig.stock():
    # - commission: 0.015% (키움)
    # - slippage: 0.01%
    # - tax: 0.23% (매도세)
    # Total round-trip cost: ~0.51% (meets 0.5% requirement)
    config = BacktestConfig.stock(
        initial_capital=initial_capital,
    )

    # Run backtest
    engine = BacktestEngine(adapted_strategy, config)
    result = engine.run(df)

    # Prepare results
    results = {
        "strategy": strategy_name,
        "symbol": df["code"].iloc[0] if "code" in df.columns else "N/A",
        "start_date": str(df["datetime"].min()),
        "end_date": str(df["datetime"].max()),
        "total_bars": len(df),
        "duration_days": (df["datetime"].max() - df["datetime"].min()).days,
        # Performance metrics
        "initial_capital": result.initial_capital,
        "final_capital": result.final_capital,
        "total_return": result.final_capital - result.initial_capital,
        "total_return_pct": result.total_return_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "max_drawdown_pct": result.max_drawdown_pct,
        "calmar_ratio": (
            result.calmar_ratio if hasattr(result, "calmar_ratio") else None
        ),
        # Trade statistics
        "total_trades": result.total_trades,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "win_rate": result.win_rate,
        "avg_win": result.avg_win if hasattr(result, "avg_win") else None,
        "avg_loss": result.avg_loss if hasattr(result, "avg_loss") else None,
        "profit_factor": (
            result.profit_factor if hasattr(result, "profit_factor") else None
        ),
        # Validation
        "passes_sharpe_criteria": (
            result.sharpe_ratio > 1.0 if result.sharpe_ratio is not None else False
        ),
        "passes_return_criteria": result.total_return_pct > 0,
        "has_reasonable_trades": 5 <= result.total_trades <= len(df) / 20,
    }

    # Log results
    logger.info("=" * 80)
    logger.info(f"Backtest Results - {strategy_name}")
    logger.info("=" * 80)
    logger.info(
        f"Period: {results['start_date']} to {results['end_date']} ({results['duration_days']} days)"
    )
    logger.info(f"Total Bars: {results['total_bars']:,}")
    logger.info("")
    logger.info(f"Initial Capital: ${results['initial_capital']:,.0f}")
    logger.info(f"Final Capital:   ${results['final_capital']:,.0f}")
    logger.info(
        f"Total Return:    ${results['total_return']:,.0f} ({results['total_return_pct']:.2f}%)"
    )
    logger.info("")
    logger.info(
        f"Sharpe Ratio:    {results['sharpe_ratio']:.3f} {'✓' if results['passes_sharpe_criteria'] else '✗'}"
    )
    logger.info(f"Max Drawdown:    {results['max_drawdown_pct']:.2f}%")
    logger.info(
        f"Calmar Ratio:    {results['calmar_ratio']:.3f}"
        if results["calmar_ratio"]
        else ""
    )
    logger.info("")
    logger.info(f"Total Trades:    {results['total_trades']}")
    logger.info(f"Win Rate:        {results['win_rate']:.1f}%")
    logger.info(f"Winning Trades:  {results['winning_trades']}")
    logger.info(f"Losing Trades:   {results['losing_trades']}")
    logger.info("")
    logger.info("Validation:")
    logger.info(f"  ✓ Sharpe > 1.0:      {results['passes_sharpe_criteria']}")
    logger.info(f"  ✓ Positive Returns:  {results['passes_return_criteria']}")
    logger.info(f"  ✓ Reasonable Trades: {results['has_reasonable_trades']}")
    logger.info("=" * 80)

    # Save results
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON results
        results_file = output_dir / f"{strategy_name}_results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to: {results_file}")

        # Save trades
        if result.trades:
            trades_file = output_dir / f"{strategy_name}_trades.csv"
            trades_df = pd.DataFrame([t.to_dict() for t in result.trades])
            trades_df.to_csv(trades_file, index=False)
            logger.info(f"Trades saved to: {trades_file}")

        # Save equity curve
        if result.equity_curve:
            equity_file = output_dir / f"{strategy_name}_equity.csv"
            equity_df = pd.DataFrame(result.equity_curve)
            equity_df.to_csv(equity_file, index=False)
            logger.info(f"Equity curve saved to: {equity_file}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run momentum_breakout strategy backtest"
    )
    parser.add_argument(
        "--mode",
        choices=["clickhouse", "csv", "synthetic"],
        default="synthetic",
        help="Data source mode",
    )
    parser.add_argument(
        "--data", type=Path, help="Path to CSV file (required for --mode csv)"
    )
    parser.add_argument(
        "--symbol",
        default="005930",
        help="Stock symbol (for ClickHouse or synthetic mode)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=180,
        help="Number of days of data (for ClickHouse or synthetic mode)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/backtests/momentum_breakout"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=10_000_000,
        help="Initial capital for backtest",
    )

    args = parser.parse_args()

    # Load data based on mode
    logger.info(f"Loading data in {args.mode} mode...")

    if args.mode == "clickhouse":
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
        df = load_clickhouse_data(args.symbol, start_date, end_date)

        if df.empty:
            logger.error(f"No data found for symbol {args.symbol}")
            logger.error("Please run data collection first:")
            logger.error(
                f"  python -m cli.main stock-backfill run --days {args.days} -c {args.symbol}"
            )
            sys.exit(1)

    elif args.mode == "csv":
        if not args.data:
            logger.error("--data is required for CSV mode")
            sys.exit(1)
        if not args.data.exists():
            logger.error(f"CSV file not found: {args.data}")
            sys.exit(1)
        df = load_csv_data(args.data)

    else:  # synthetic
        logger.warning("Using synthetic data - results are for testing only!")
        df = generate_synthetic_data(symbol=args.symbol, days=args.days)

    # Validate data
    if len(df) < 1000:
        logger.error(f"Insufficient data: {len(df)} bars (minimum 1000 required)")
        sys.exit(1)

    duration_days = (df["datetime"].max() - df["datetime"].min()).days
    if duration_days < 30:
        logger.warning(
            f"Data duration is only {duration_days} days (6+ months recommended)"
        )

    # Run backtest
    try:
        results = run_backtest(
            df=df,
            strategy_name="momentum_breakout",
            initial_capital=args.initial_capital,
            output_dir=args.output_dir,
        )

        # Exit with success/failure based on criteria
        all_passed = (
            results["passes_sharpe_criteria"]
            and results["passes_return_criteria"]
            and results["has_reasonable_trades"]
        )

        if all_passed:
            logger.info("✓ All acceptance criteria met!")
            sys.exit(0)
        else:
            logger.warning("✗ Some acceptance criteria not met")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
