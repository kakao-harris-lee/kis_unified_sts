#!/usr/bin/env python3
"""
Backtest Comparison Script: ATR Dynamic vs Three Stage Exit (Synthetic Data)

This script runs backtests using synthetic stock data to compare the two exit strategies.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from shared.backtest import BacktestConfig, BacktestEngine
from shared.backtest.adapter import BacktestStrategyAdapter
from shared.backtest.config import RiskConfig
from shared.config.loader import ConfigLoader
from shared.strategy.registry import StrategyFactory, register_builtin_components


def generate_synthetic_stock_data(
    n_bars: int = 10000,
    start_price: float = 50000,
    volatility: float = 0.02,
    trend: float = 0.0001,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic stock data with realistic patterns."""
    np.random.seed(seed)

    # Generate timestamps (1-minute bars)
    start_date = datetime(2024, 1, 2, 9, 0)
    timestamps = []
    current_time = start_date

    for i in range(n_bars):
        timestamps.append(current_time)
        current_time += timedelta(minutes=1)

        # Skip non-trading hours (15:30 - 09:00 next day)
        if current_time.hour >= 15 and current_time.minute >= 30:
            current_time = current_time.replace(hour=9, minute=0) + timedelta(days=1)

    timestamps = timestamps[:n_bars]

    # Generate price data with trend and volatility
    returns = np.random.normal(trend, volatility, n_bars)

    # Add some autocorrelation for realism
    for i in range(1, len(returns)):
        returns[i] = 0.7 * returns[i] + 0.3 * returns[i - 1]

    # Calculate prices
    prices = start_price * np.exp(np.cumsum(returns))

    # Generate OHLC data
    opens = prices * (1 + np.random.normal(0, 0.001, n_bars))
    highs = np.maximum(opens, prices) * (1 + np.abs(np.random.normal(0, 0.002, n_bars)))
    lows = np.minimum(opens, prices) * (1 - np.abs(np.random.normal(0, 0.002, n_bars)))
    closes = prices

    # Generate volume (with some variation)
    base_volume = 100000
    volumes = base_volume * (1 + np.random.lognormal(0, 0.5, n_bars))

    # Create DataFrame
    df = pd.DataFrame({
        "datetime": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes.astype(int),
    })

    df["datetime"] = pd.to_datetime(df["datetime"])

    return df


def run_single_backtest(strategy_name: str, asset: str, data: pd.DataFrame):
    """Run backtest for a single strategy configuration."""
    print(f"\n{'='*80}")
    print(f"Running backtest: {strategy_name} ({asset})")
    print(f"{'='*80}\n")

    register_builtin_components()

    # Load strategy config
    try:
        strategy_config = ConfigLoader.load_strategy(asset, strategy_name)
    except FileNotFoundError:
        print(f"Error: Strategy config not found: {asset}/{strategy_name}")
        raise

    print(f"Loaded strategy config: {strategy_config['strategy']['name']}")
    print(f"Exit strategy: {strategy_config['strategy']['exit']['type']}")
    print(f"Data: {len(data)} bars from {data.index[0]} to {data.index[-1]}")

    # Create strategy instance
    strategy = StrategyFactory.create(strategy_config)

    # Create backtest adapter
    adapter = BacktestStrategyAdapter(strategy, strategy_config)

    # Create backtest engine config
    backtest_cfg_dict = strategy_config.get("strategy", {}).get("backtest", {})
    risk_cfg_dict = backtest_cfg_dict.get("risk", {})
    risk_config = RiskConfig(**risk_cfg_dict) if risk_cfg_dict else RiskConfig()

    backtest_config = BacktestConfig(
        initial_capital=10_000_000,
        risk=risk_config,
    )

    # Run backtest
    engine = BacktestEngine(adapter, backtest_config)
    results = engine.run(data)

    if not results:
        raise RuntimeError(f"Backtest failed for {strategy_name}")

    # Convert BacktestResult to dict
    results_dict = results.to_dict()

    print(f"\n{'='*80}")
    print(f"RESULTS for {strategy_name}")
    print(f"{'='*80}")
    print(f"Total Return: {results_dict.get('total_return_pct', 0):.2f}%")
    print(f"Sharpe Ratio: {results_dict.get('sharpe_ratio', 0):.3f}")
    print(f"Win Rate: {results_dict.get('win_rate', 0):.2f}%")
    print(f"Max Drawdown: {results_dict.get('max_drawdown_pct', 0):.2f}%")
    print(f"Total Trades: {results_dict.get('total_trades', 0)}")
    print(f"Avg Holding Days: {results_dict.get('avg_holding_days', 0):.1f}")
    print(f"Profit Factor: {results_dict.get('profit_factor', 0):.2f}")
    print(f"{'='*80}\n")

    return {
        "strategy_name": strategy_name,
        "exit_type": strategy_config['strategy']['exit']['type'],
        "metrics": results_dict,
    }


def compare_results(result_a: dict, result_b: dict) -> dict:
    """Compare two backtest results and generate comparison report."""
    metrics_a = result_a["metrics"]
    metrics_b = result_b["metrics"]

    comparison = {
        "sharpe_ratio": {
            "atr_dynamic": metrics_a.get("sharpe_ratio", 0),
            "three_stage": metrics_b.get("sharpe_ratio", 0),
            "difference": metrics_a.get("sharpe_ratio", 0) - metrics_b.get("sharpe_ratio", 0),
            "improvement_pct": (
                (metrics_a.get("sharpe_ratio", 0) - metrics_b.get("sharpe_ratio", 0))
                / abs(metrics_b.get("sharpe_ratio", 0.001))
                * 100
            ),
        },
        "win_rate": {
            "atr_dynamic": metrics_a.get("win_rate", 0),
            "three_stage": metrics_b.get("win_rate", 0),
            "difference": metrics_a.get("win_rate", 0) - metrics_b.get("win_rate", 0),
            "improvement_pct": (
                (metrics_a.get("win_rate", 0) - metrics_b.get("win_rate", 0))
                / max(metrics_b.get("win_rate", 1), 1)
                * 100
            ),
        },
        "max_drawdown": {
            "atr_dynamic": metrics_a.get("max_drawdown_pct", 0),
            "three_stage": metrics_b.get("max_drawdown_pct", 0),
            "difference": metrics_a.get("max_drawdown_pct", 0) - metrics_b.get("max_drawdown_pct", 0),
            "improvement_pct": (
                (metrics_b.get("max_drawdown_pct", 0) - metrics_a.get("max_drawdown_pct", 0))
                / max(abs(metrics_b.get("max_drawdown_pct", 0.001)), 0.001)
                * 100
            ),  # Lower is better, so inverted
        },
        "holding_time": {
            "atr_dynamic": metrics_a.get("avg_holding_days", 0),
            "three_stage": metrics_b.get("avg_holding_days", 0),
            "difference": metrics_a.get("avg_holding_days", 0) - metrics_b.get("avg_holding_days", 0),
        },
        "total_return": {
            "atr_dynamic": metrics_a.get("total_return_pct", 0),
            "three_stage": metrics_b.get("total_return_pct", 0),
            "difference": metrics_a.get("total_return_pct", 0) - metrics_b.get("total_return_pct", 0),
        },
        "profit_factor": {
            "atr_dynamic": metrics_a.get("profit_factor", 0),
            "three_stage": metrics_b.get("profit_factor", 0),
            "difference": metrics_a.get("profit_factor", 0) - metrics_b.get("profit_factor", 0),
        },
    }

    # Count improvements (main 3 metrics)
    improvements = 0
    if comparison["sharpe_ratio"]["difference"] > 0:
        improvements += 1
    if comparison["win_rate"]["difference"] > 0:
        improvements += 1
    if comparison["max_drawdown"]["difference"] < 0:  # Lower is better
        improvements += 1

    comparison["summary"] = {
        "improvements_count": improvements,
        "total_metrics": 3,
        "atr_dynamic_superior": improvements >= 2,
    }

    return comparison


def main():
    """Run backtest comparison and generate report."""
    print("\n" + "="*80)
    print("BACKTEST COMPARISON: ATR Dynamic vs Three Stage Exit")
    print("Using Synthetic Stock Data")
    print("="*80 + "\n")

    # Generate synthetic data (3 different scenarios)
    scenarios = [
        {"name": "Trending Market", "trend": 0.0003, "volatility": 0.015},
        {"name": "Volatile Market", "trend": 0.0, "volatility": 0.03},
        {"name": "Calm Market", "trend": 0.0001, "volatility": 0.01},
    ]

    all_results_a = []
    all_results_b = []

    for i, scenario in enumerate(scenarios):
        print(f"\n{'='*80}")
        print(f"SCENARIO {i+1}: {scenario['name']}")
        print(f"{'='*80}\n")

        # Generate data for this scenario
        data = generate_synthetic_stock_data(
            n_bars=5000,
            start_price=50000,
            volatility=scenario["volatility"],
            trend=scenario["trend"],
            seed=42 + i,
        )

        # Run backtest A (atr_dynamic)
        result_a = run_single_backtest(
            strategy_name="test_atr_vs_three_stage_a",
            asset="stock",
            data=data,
        )
        all_results_a.append(result_a)

        # Run backtest B (three_stage)
        result_b = run_single_backtest(
            strategy_name="test_atr_vs_three_stage_b",
            asset="stock",
            data=data,
        )
        all_results_b.append(result_b)

    # Calculate aggregate metrics
    def aggregate_metrics(results_list):
        sharpe = np.mean([r["metrics"].get("sharpe_ratio", 0) for r in results_list])
        win_rate = np.mean([r["metrics"].get("win_rate", 0) for r in results_list])
        max_dd = np.mean([r["metrics"].get("max_drawdown_pct", 0) for r in results_list])
        hold_time = np.mean([r["metrics"].get("avg_holding_days", 0) for r in results_list])
        total_return = np.mean([r["metrics"].get("total_return_pct", 0) for r in results_list])
        profit_factor = np.mean([r["metrics"].get("profit_factor", 0) for r in results_list])

        return {
            "sharpe_ratio": sharpe,
            "win_rate": win_rate,
            "max_drawdown_pct": max_dd,
            "avg_holding_days": hold_time,
            "total_return_pct": total_return,
            "profit_factor": profit_factor,
        }

    aggregate_a = {"metrics": aggregate_metrics(all_results_a)}
    aggregate_b = {"metrics": aggregate_metrics(all_results_b)}

    # Compare aggregate results
    comparison = compare_results(aggregate_a, aggregate_b)

    # Print comparison report
    print("\n" + "="*80)
    print("AGGREGATE COMPARISON REPORT (Across All Scenarios)")
    print("="*80 + "\n")

    print(f"1. Sharpe Ratio:")
    print(f"   ATR Dynamic:  {comparison['sharpe_ratio']['atr_dynamic']:>8.3f}")
    print(f"   Three Stage:  {comparison['sharpe_ratio']['three_stage']:>8.3f}")
    print(f"   Difference:   {comparison['sharpe_ratio']['difference']:>8.3f} "
          f"({comparison['sharpe_ratio']['improvement_pct']:+.1f}%)")
    print(f"   Winner: {'✓ ATR Dynamic' if comparison['sharpe_ratio']['difference'] > 0 else '✓ Three Stage'}\n")

    print(f"2. Win Rate:")
    print(f"   ATR Dynamic:  {comparison['win_rate']['atr_dynamic']:>8.2f}%")
    print(f"   Three Stage:  {comparison['win_rate']['three_stage']:>8.2f}%")
    print(f"   Difference:   {comparison['win_rate']['difference']:>8.2f}% "
          f"({comparison['win_rate']['improvement_pct']:+.1f}%)")
    print(f"   Winner: {'✓ ATR Dynamic' if comparison['win_rate']['difference'] > 0 else '✓ Three Stage'}\n")

    print(f"3. Max Drawdown:")
    print(f"   ATR Dynamic:  {comparison['max_drawdown']['atr_dynamic']:>8.2f}%")
    print(f"   Three Stage:  {comparison['max_drawdown']['three_stage']:>8.2f}%")
    print(f"   Difference:   {comparison['max_drawdown']['difference']:>8.2f}% "
          f"({comparison['max_drawdown']['improvement_pct']:+.1f}%)")
    print(f"   Winner: {'✓ ATR Dynamic' if comparison['max_drawdown']['difference'] < 0 else '✓ Three Stage'}\n")

    print(f"4. Average Holding Time:")
    print(f"   ATR Dynamic:  {comparison['holding_time']['atr_dynamic']:>8.1f} bars")
    print(f"   Three Stage:  {comparison['holding_time']['three_stage']:>8.1f} bars")
    print(f"   Difference:   {comparison['holding_time']['difference']:>8.1f} bars\n")

    print(f"5. Total Return:")
    print(f"   ATR Dynamic:  {comparison['total_return']['atr_dynamic']:>8.2f}%")
    print(f"   Three Stage:  {comparison['total_return']['three_stage']:>8.2f}%")
    print(f"   Difference:   {comparison['total_return']['difference']:>8.2f}%\n")

    print(f"6. Profit Factor:")
    print(f"   ATR Dynamic:  {comparison['profit_factor']['atr_dynamic']:>8.2f}")
    print(f"   Three Stage:  {comparison['profit_factor']['three_stage']:>8.2f}")
    print(f"   Difference:   {comparison['profit_factor']['difference']:>8.2f}\n")

    print("="*80)
    print(f"SUMMARY: ATR Dynamic shows improvement in {comparison['summary']['improvements_count']}/3 key metrics")
    print(f"Verdict: {'✓ ATR Dynamic OUTPERFORMS Three Stage' if comparison['summary']['atr_dynamic_superior'] else '⚠ Three Stage performs better'}")
    print("="*80 + "\n")

    # Save results to JSON
    output = {
        "test_type": "synthetic_data",
        "scenarios": scenarios,
        "result_a_all": all_results_a,
        "result_b_all": all_results_b,
        "aggregate_a": aggregate_a,
        "aggregate_b": aggregate_b,
        "comparison": comparison,
    }

    output_file = project_root / "backtest_comparison_results.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"Full results saved to: {output_file}")

    return comparison


if __name__ == "__main__":
    try:
        comparison = main()

        # Exit with appropriate status code
        if comparison["summary"]["atr_dynamic_superior"]:
            print("\n✓ Success: ATR Dynamic exit strategy validated")
            sys.exit(0)
        else:
            print("\n⚠ Warning: ATR Dynamic did not outperform in at least 2 metrics")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
