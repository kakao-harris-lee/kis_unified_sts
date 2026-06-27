#!/usr/bin/env python3
"""
Validate Backtest Results - Automated Acceptance Criteria Checker

This script automatically validates backtest results against the acceptance criteria
defined in the project spec (Sharpe > 1.0, positive returns, reasonable trades).

Usage:
    python3 scripts/validate_backtest_results.py \
        --trend-pullback output/backtests/trend_pullback/results.json \
        --momentum-breakout output/backtests/momentum_breakout/results.json

    # Or validate individually:
    python3 scripts/validate_backtest_results.py \
        --strategy-name trend_pullback \
        --results output/backtests/trend_pullback/results.json

Exit Codes:
    0 - All criteria met
    1 - Some criteria failed
    2 - Results file not found or invalid
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AcceptanceCriteria:
    """Acceptance criteria thresholds from spec.md"""
    min_sharpe_ratio: float = 1.0
    min_return_pct: float = 0.0  # Positive returns
    round_trip_cost_pct: float = 0.5
    min_trades: int = 5
    max_trade_ratio: float = 0.05  # Max trades = bars / 20


@dataclass
class ValidationResult:
    """Result of validating a single criterion"""
    criterion: str
    passed: bool
    actual_value: float
    threshold: float
    message: str


@dataclass
class StrategyValidation:
    """Complete validation results for a strategy"""
    strategy_name: str
    passed: bool
    results: list[ValidationResult]
    summary: str


def load_backtest_results(results_path: Path) -> dict | None:
    """Load backtest results from JSON file"""
    try:
        if not results_path.exists():
            print(f"❌ Results file not found: {results_path}")
            return None

        with open(results_path) as f:
            data = json.load(f)

        print(f"✓ Loaded results from {results_path}")
        return data

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {results_path}: {e}")
        return None
    except Exception as e:
        print(f"❌ Error loading {results_path}: {e}")
        return None


def validate_strategy_results(
    strategy_name: str,
    results: dict,
    criteria: AcceptanceCriteria
) -> StrategyValidation:
    """Validate backtest results against acceptance criteria"""

    validation_results = []

    # Extract metrics from results
    metrics = results.get('metrics', {})
    sharpe_ratio = metrics.get('sharpe_ratio', 0.0)
    total_return_pct = metrics.get('total_return_pct', 0.0)
    num_trades = metrics.get('num_trades', 0)
    num_bars = results.get('num_bars', 0)

    # 1. Sharpe Ratio > 1.0
    sharpe_passed = sharpe_ratio > criteria.min_sharpe_ratio
    validation_results.append(ValidationResult(
        criterion="Sharpe Ratio",
        passed=sharpe_passed,
        actual_value=sharpe_ratio,
        threshold=criteria.min_sharpe_ratio,
        message=f"Sharpe {sharpe_ratio:.2f} {'>' if sharpe_passed else '≤'} {criteria.min_sharpe_ratio:.2f}"
    ))

    # 2. Positive Net Returns
    return_passed = total_return_pct > criteria.min_return_pct
    validation_results.append(ValidationResult(
        criterion="Net Returns",
        passed=return_passed,
        actual_value=total_return_pct,
        threshold=criteria.min_return_pct,
        message=f"Return {total_return_pct:.2f}% {'>' if return_passed else '≤'} {criteria.min_return_pct:.2f}%"
    ))

    # 3. Reasonable Trade Count (5 ≤ trades ≤ bars/20)
    max_trades = num_bars / 20 if num_bars > 0 else float('inf')
    trades_passed = criteria.min_trades <= num_trades <= max_trades
    validation_results.append(ValidationResult(
        criterion="Trade Count",
        passed=trades_passed,
        actual_value=num_trades,
        threshold=criteria.min_trades,
        message=f"Trades {num_trades} in range [{criteria.min_trades}, {max_trades:.0f}]"
    ))

    # 4. Round-trip Costs Applied
    cost_applied = metrics.get('round_trip_cost_pct', 0.0)
    cost_passed = abs(cost_applied - criteria.round_trip_cost_pct) < 0.01
    validation_results.append(ValidationResult(
        criterion="Round-trip Costs",
        passed=cost_passed,
        actual_value=cost_applied,
        threshold=criteria.round_trip_cost_pct,
        message=f"Costs {cost_applied:.2f}% {'==' if cost_passed else '!='} {criteria.round_trip_cost_pct:.2f}%"
    ))

    # Overall pass/fail
    all_passed = all(r.passed for r in validation_results)

    # Generate summary
    if all_passed:
        summary = f"✅ {strategy_name}: ALL CRITERIA MET"
    else:
        failed_criteria = [r.criterion for r in validation_results if not r.passed]
        summary = f"❌ {strategy_name}: FAILED - {', '.join(failed_criteria)}"

    return StrategyValidation(
        strategy_name=strategy_name,
        passed=all_passed,
        results=validation_results,
        summary=summary
    )


def print_validation_report(validations: list[StrategyValidation]) -> None:
    """Print detailed validation report"""

    print("\n" + "="*80)
    print("BACKTEST VALIDATION REPORT")
    print("="*80 + "\n")

    for validation in validations:
        print(f"\n{validation.summary}\n")
        print(f"Strategy: {validation.strategy_name}")
        print("-" * 60)

        for result in validation.results:
            status = "✓" if result.passed else "✗"
            print(f"  {status} {result.criterion:20s} {result.message}")

        print()

    # Overall summary
    all_passed = all(v.passed for v in validations)
    print("\n" + "="*80)
    if all_passed:
        print("🎉 OVERALL RESULT: ALL STRATEGIES PASSED")
        print("\nReady to proceed to Phase 2: Paper Trading Deployment")
    else:
        failed_strategies = [v.strategy_name for v in validations if not v.passed]
        print(f"⚠️  OVERALL RESULT: {len(failed_strategies)} STRATEGY(IES) FAILED")
        print(f"\nFailed: {', '.join(failed_strategies)}")
        print("\nAction Required:")
        print("1. Review parameter tuning opportunities")
        print("2. Check data quality and date range")
        print("3. Verify strategy logic implementation")
        print("4. Consider re-running optimization (Optuna)")
    print("="*80 + "\n")


def generate_performance_summary(results: dict) -> str:
    """Generate human-readable performance summary"""

    metrics = results.get('metrics', {})

    summary = f"""
Performance Metrics Summary:
---------------------------
Total Return:       {metrics.get('total_return_pct', 0.0):.2f}%
Sharpe Ratio:       {metrics.get('sharpe_ratio', 0.0):.2f}
Max Drawdown:       {metrics.get('max_drawdown_pct', 0.0):.2f}%
Win Rate:           {metrics.get('win_rate', 0.0):.2f}%

Trade Statistics:
----------------
Total Trades:       {metrics.get('num_trades', 0)}
Winning Trades:     {metrics.get('num_wins', 0)}
Losing Trades:      {metrics.get('num_losses', 0)}
Average Win:        {metrics.get('avg_win_pct', 0.0):.2f}%
Average Loss:       {metrics.get('avg_loss_pct', 0.0):.2f}%
Profit Factor:      {metrics.get('profit_factor', 0.0):.2f}

Costs & Risk:
------------
Round-trip Cost:    {metrics.get('round_trip_cost_pct', 0.0):.2f}%
Total Costs:        {metrics.get('total_costs', 0.0):.2f}
Risk-Adjusted:      {metrics.get('calmar_ratio', 0.0):.2f} (Calmar)

Data Coverage:
-------------
Start Date:         {results.get('start_date', 'N/A')}
End Date:           {results.get('end_date', 'N/A')}
Total Bars:         {results.get('num_bars', 0):,}
Trading Days:       {results.get('num_bars', 0) // 390} (approx)
"""

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Validate backtest results against acceptance criteria",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--trend-pullback',
        type=Path,
        help='Path to trend_pullback results.json'
    )

    parser.add_argument(
        '--momentum-breakout',
        type=Path,
        help='Path to momentum_breakout results.json'
    )

    parser.add_argument(
        '--strategy-name',
        type=str,
        help='Strategy name (for single validation)'
    )

    parser.add_argument(
        '--results',
        type=Path,
        help='Path to results.json (for single validation)'
    )

    parser.add_argument(
        '--show-details',
        action='store_true',
        help='Show detailed performance metrics'
    )

    args = parser.parse_args()

    # Load criteria
    criteria = AcceptanceCriteria()

    # Collect validations
    validations = []

    # Validate trend_pullback
    if args.trend_pullback:
        results = load_backtest_results(args.trend_pullback)
        if results:
            validation = validate_strategy_results('trend_pullback', results, criteria)
            validations.append(validation)

            if args.show_details:
                print(generate_performance_summary(results))

    # Validate momentum_breakout
    if args.momentum_breakout:
        results = load_backtest_results(args.momentum_breakout)
        if results:
            validation = validate_strategy_results('momentum_breakout', results, criteria)
            validations.append(validation)

            if args.show_details:
                print(generate_performance_summary(results))

    # Single strategy validation
    if args.strategy_name and args.results:
        results = load_backtest_results(args.results)
        if results:
            validation = validate_strategy_results(args.strategy_name, results, criteria)
            validations.append(validation)

            if args.show_details:
                print(generate_performance_summary(results))

    # Generate report
    if validations:
        print_validation_report(validations)

        # Exit with appropriate code
        all_passed = all(v.passed for v in validations)
        sys.exit(0 if all_passed else 1)
    else:
        print("❌ No results to validate. Provide --trend-pullback, --momentum-breakout,")
        print("   or --strategy-name with --results")
        sys.exit(2)


if __name__ == '__main__':
    main()
