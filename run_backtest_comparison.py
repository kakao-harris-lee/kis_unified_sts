#!/usr/bin/env python3
"""
Backtest Comparison Script: ATR Dynamic vs Three Stage Exit

This script runs backtests for both exit strategies and compares performance metrics.
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from shared.backtest import BacktestConfig, BacktestEngine
from shared.backtest.adapter import BacktestStrategyAdapter
from shared.backtest.config import RiskConfig
from shared.collector.historical.stock import (
    STOCK_UNIVERSE,
    load_stock_minute_from_clickhouse,
)
from shared.config.loader import ConfigLoader
from shared.strategy.registry import StrategyFactory, register_builtin_components


def run_single_backtest(strategy_name: str, asset: str, tier: str = "top"):
    """Run backtest for a single strategy configuration."""
    print(f"\n{'='*80}")
    print(f"Running backtest: {strategy_name} ({asset})")
    print(f"{'='*80}\n")

    register_builtin_components()

    # Load strategy config
    try:
        strategy_config = ConfigLoader.load_strategy(asset, strategy_name)
    except FileNotFoundError as e:
        print(f"Error: Strategy config not found: {asset}/{strategy_name}")
        raise

    print(f"Loaded strategy config: {strategy_config['strategy']['name']}")
    print(f"Exit strategy: {strategy_config['strategy']['exit']['type']}")

    # Get stocks from tier
    tier_stocks = STOCK_UNIVERSE.get(tier, [])
    if not tier_stocks:
        raise ValueError(f"No stocks found for tier: {tier}")

    print(f"Testing on {len(tier_stocks)} stocks from '{tier}' tier")

    # Aggregate results
    all_results = []
    successful_runs = 0

    for stock_code in tier_stocks:
        print(f"\n--- Processing {stock_code} ---")

        try:
            # Load data from ClickHouse
            df = load_stock_minute_from_clickhouse(
                stock_code=stock_code,
                start_date=None,  # Use all available data
                end_date=None,
            )

            if df is None or df.empty:
                print(f"Warning: No data for {stock_code}, skipping")
                continue

            print(f"Loaded {len(df)} bars for {stock_code}")

            # Create strategy instance
            strategy = StrategyFactory.create_from_config(strategy_config)

            # Create backtest adapter
            adapter = BacktestStrategyAdapter(strategy)

            # Create backtest engine config
            backtest_cfg_dict = strategy_config.get("strategy", {}).get("backtest", {})
            risk_cfg_dict = backtest_cfg_dict.get("risk", {})
            risk_config = RiskConfig(**risk_cfg_dict) if risk_cfg_dict else RiskConfig()

            backtest_config = BacktestConfig(
                initial_capital=10_000_000,
                risk=risk_config,
            )

            # Run backtest
            engine = BacktestEngine(backtest_config, adapter)
            results = engine.run(df)

            if results:
                all_results.append({
                    "stock_code": stock_code,
                    "metrics": results,
                })
                successful_runs += 1
                print(f"✓ {stock_code}: Total Return={results.get('total_return_pct', 0):.2f}%, "
                      f"Sharpe={results.get('sharpe_ratio', 0):.3f}, "
                      f"Win Rate={results.get('win_rate', 0):.2f}%")

        except Exception as e:
            print(f"Error processing {stock_code}: {e}")
            continue

    if successful_runs == 0:
        raise RuntimeError(f"No successful backtests for {strategy_name}")

    # Calculate aggregate metrics
    aggregate_metrics = calculate_aggregate_metrics(all_results)

    print(f"\n{'='*80}")
    print(f"AGGREGATE RESULTS for {strategy_name}")
    print(f"{'='*80}")
    print(f"Successful runs: {successful_runs}/{len(tier_stocks)}")
    print(f"Average Sharpe Ratio: {aggregate_metrics['avg_sharpe_ratio']:.3f}")
    print(f"Average Win Rate: {aggregate_metrics['avg_win_rate']:.2f}%")
    print(f"Average Max Drawdown: {aggregate_metrics['avg_max_drawdown']:.2f}%")
    print(f"Average Holding Time: {aggregate_metrics['avg_holding_time']:.1f} bars")
    print(f"Average Total Return: {aggregate_metrics['avg_total_return']:.2f}%")
    print(f"{'='*80}\n")

    return {
        "strategy_name": strategy_name,
        "exit_type": strategy_config['strategy']['exit']['type'],
        "successful_runs": successful_runs,
        "total_stocks": len(tier_stocks),
        "aggregate_metrics": aggregate_metrics,
        "individual_results": all_results,
    }


def calculate_aggregate_metrics(results: list) -> dict:
    """Calculate aggregate metrics from multiple backtest runs."""
    if not results:
        return {}

    sharpe_ratios = []
    win_rates = []
    max_drawdowns = []
    holding_times = []
    total_returns = []

    for result in results:
        metrics = result["metrics"]
        sharpe_ratios.append(metrics.get("sharpe_ratio", 0))
        win_rates.append(metrics.get("win_rate", 0))
        max_drawdowns.append(metrics.get("max_drawdown", 0))
        holding_times.append(metrics.get("avg_hold_bars", 0))
        total_returns.append(metrics.get("total_return_pct", 0))

    return {
        "avg_sharpe_ratio": sum(sharpe_ratios) / len(sharpe_ratios),
        "avg_win_rate": sum(win_rates) / len(win_rates),
        "avg_max_drawdown": sum(max_drawdowns) / len(max_drawdowns),
        "avg_holding_time": sum(holding_times) / len(holding_times),
        "avg_total_return": sum(total_returns) / len(total_returns),
        "median_sharpe_ratio": sorted(sharpe_ratios)[len(sharpe_ratios) // 2],
        "median_win_rate": sorted(win_rates)[len(win_rates) // 2],
    }


def compare_results(result_a: dict, result_b: dict) -> dict:
    """Compare two backtest results and generate comparison report."""
    metrics_a = result_a["aggregate_metrics"]
    metrics_b = result_b["aggregate_metrics"]

    comparison = {
        "sharpe_ratio": {
            "atr_dynamic": metrics_a["avg_sharpe_ratio"],
            "three_stage": metrics_b["avg_sharpe_ratio"],
            "difference": metrics_a["avg_sharpe_ratio"] - metrics_b["avg_sharpe_ratio"],
            "improvement_pct": (
                (metrics_a["avg_sharpe_ratio"] - metrics_b["avg_sharpe_ratio"])
                / abs(metrics_b["avg_sharpe_ratio"])
                * 100
                if metrics_b["avg_sharpe_ratio"] != 0
                else 0
            ),
        },
        "win_rate": {
            "atr_dynamic": metrics_a["avg_win_rate"],
            "three_stage": metrics_b["avg_win_rate"],
            "difference": metrics_a["avg_win_rate"] - metrics_b["avg_win_rate"],
            "improvement_pct": (
                (metrics_a["avg_win_rate"] - metrics_b["avg_win_rate"])
                / metrics_b["avg_win_rate"]
                * 100
                if metrics_b["avg_win_rate"] != 0
                else 0
            ),
        },
        "max_drawdown": {
            "atr_dynamic": metrics_a["avg_max_drawdown"],
            "three_stage": metrics_b["avg_max_drawdown"],
            "difference": metrics_a["avg_max_drawdown"] - metrics_b["avg_max_drawdown"],
            "improvement_pct": (
                (metrics_b["avg_max_drawdown"] - metrics_a["avg_max_drawdown"])
                / abs(metrics_b["avg_max_drawdown"])
                * 100
                if metrics_b["avg_max_drawdown"] != 0
                else 0
            ),  # Lower is better, so inverted
        },
        "holding_time": {
            "atr_dynamic": metrics_a["avg_holding_time"],
            "three_stage": metrics_b["avg_holding_time"],
            "difference": metrics_a["avg_holding_time"] - metrics_b["avg_holding_time"],
        },
    }

    # Count improvements
    improvements = 0
    if comparison["sharpe_ratio"]["difference"] > 0:
        improvements += 1
    if comparison["win_rate"]["difference"] > 0:
        improvements += 1
    if comparison["max_drawdown"]["difference"] < 0:  # Lower is better
        improvements += 1

    comparison["summary"] = {
        "improvements_count": improvements,
        "total_metrics": 3,  # Excluding holding_time from improvement count
        "atr_dynamic_superior": improvements >= 2,
    }

    return comparison


def main():
    """Run backtest comparison and generate report."""
    print("\n" + "="*80)
    print("BACKTEST COMPARISON: ATR Dynamic vs Three Stage Exit")
    print("="*80 + "\n")

    # Run backtest A (atr_dynamic)
    result_a = run_single_backtest(
        strategy_name="test_atr_vs_three_stage_a",
        asset="stock",
        tier="top",  # Use top tier stocks for faster testing
    )

    # Run backtest B (three_stage)
    result_b = run_single_backtest(
        strategy_name="test_atr_vs_three_stage_b",
        asset="stock",
        tier="top",
    )

    # Compare results
    comparison = compare_results(result_a, result_b)

    # Print comparison report
    print("\n" + "="*80)
    print("COMPARISON REPORT")
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

    print("="*80)
    print(f"SUMMARY: ATR Dynamic shows improvement in {comparison['summary']['improvements_count']}/3 key metrics")
    print(f"Verdict: {'✓ ATR Dynamic OUTPERFORMS Three Stage' if comparison['summary']['atr_dynamic_superior'] else '⚠ Three Stage performs better'}")
    print("="*80 + "\n")

    # Save results to JSON
    output = {
        "result_a": result_a,
        "result_b": result_b,
        "comparison": comparison,
    }

    output_file = project_root / "backtest_comparison_results.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

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
