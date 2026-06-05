#!/usr/bin/env python3
"""A/B backtest comparison: same strategy with use_llm_context=true vs false.

Compares strategy performance (Sharpe ratio, win rate, max drawdown, etc.)
with and without LLM market context integration.

Usage:
    python scripts/analysis/compare_llm_context_backtest.py \\
        --strategy bb_reversion \\
        --asset stock \\
        --data ./data/sample.csv

    # From Parquet market data
    python scripts/analysis/compare_llm_context_backtest.py \\
        --strategy bb_reversion \\
        --asset stock \\
        --symbol 005930 \\
        --start-date 2025-01-01 \\
        --end-date 2025-12-31

Output:
    - artifacts/llm_ab_compare/{strategy}/comparison.csv
    - artifacts/llm_ab_compare/{strategy}/summary.md
    - Console output with metrics table
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.backtest import BacktestConfig, BacktestEngine
from shared.config import ConfigLoader
from shared.storage import StorageConfig, load_market_bars_for_backtest
from shared.strategy import StrategyFactory


def _load_data_from_csv(csv_path: Path) -> pd.DataFrame:
    """Load OHLCV data from CSV file.

    Required columns: datetime, open, high, low, close, volume
    Optional columns: code, name
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Data file not found: {csv_path}")

    df = pd.read_csv(csv_path)

    # Validate required columns
    required = ["datetime", "open", "high", "low", "close", "volume"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Parse datetime
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"])

    return df.sort_values("datetime").reset_index(drop=True)


def _load_data_from_parquet(
    asset_class: str, symbol: str, start_date: str, end_date: str
) -> pd.DataFrame:
    """Load OHLCV data from the configured Parquet market-data store.

    Args:
        asset_class: "stock" or "futures"
        symbol: Symbol/code to load
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with OHLCV data
    """
    df = load_market_bars_for_backtest(
        symbol=symbol,
        asset_class=asset_class,  # type: ignore[arg-type]
        timeframe="minute",
        start=datetime.strptime(start_date, "%Y-%m-%d").date(),
        end=datetime.strptime(end_date, "%Y-%m-%d").date(),
        config=StorageConfig.load_or_default(),
    )
    if df.empty:
        raise ValueError(
            f"No Parquet data found for {symbol} from {start_date} to {end_date}"
        )
    if "name" not in df.columns:
        df["name"] = symbol
    return df.sort_values("datetime").reset_index(drop=True)


def _run_backtest(
    strategy_name: str,
    asset_class: str,
    data: pd.DataFrame,
    use_llm_context: bool,
    initial_capital: float,
) -> dict[str, Any]:
    """Run backtest with specified LLM context setting.

    Args:
        strategy_name: Strategy name (e.g., "bb_reversion")
        asset_class: "stock" or "futures"
        data: OHLCV DataFrame
        use_llm_context: Enable LLM context integration
        initial_capital: Initial capital

    Returns:
        Dictionary with backtest results
    """
    # Load strategy config
    config_dict = ConfigLoader.load_strategy(asset_class, strategy_name)

    # Override use_llm_context setting
    if "strategy" not in config_dict:
        config_dict["strategy"] = {}
    config_dict["strategy"]["use_llm_context"] = use_llm_context

    # Create strategy from config
    strategy = StrategyFactory.create_from_config(config_dict)

    # Create backtest config
    if asset_class == "stock":
        bt_config = BacktestConfig.stock(initial_capital=initial_capital)
    else:
        bt_config = BacktestConfig.futures(initial_capital=initial_capital)

    # Run backtest
    engine = BacktestEngine(strategy, bt_config)
    result = engine.run(data)

    return {
        "use_llm_context": use_llm_context,
        "total_bars": result.total_bars,
        "total_return_pct": result.total_return_pct,
        "annualized_return": result.annualized_return,
        "sharpe_ratio": result.sharpe_ratio,
        "sortino_ratio": result.sortino_ratio,
        "max_drawdown_pct": result.max_drawdown_pct,
        "total_trades": result.total_trades,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "win_rate": result.win_rate,
        "avg_profit": result.avg_profit,
        "avg_loss": result.avg_loss,
        "profit_factor": result.profit_factor,
        "avg_holding_days": result.avg_holding_days,
        "final_capital": result.final_capital,
    }


def _calculate_improvement(baseline: float, improved: float) -> float:
    """Calculate improvement percentage.

    Args:
        baseline: Baseline value (without LLM)
        improved: Improved value (with LLM)

    Returns:
        Improvement percentage
    """
    if baseline == 0:
        return 0.0
    return ((improved - baseline) / abs(baseline)) * 100


def _write_comparison_csv(
    output_path: Path, result_a: dict[str, Any], result_b: dict[str, Any]
) -> None:
    """Write comparison results to CSV.

    Args:
        output_path: Output CSV path
        result_a: Results without LLM context
        result_b: Results with LLM context
    """
    rows = []
    for key in result_a.keys():
        if key == "use_llm_context":
            continue
        val_a = result_a[key]
        val_b = result_b[key]
        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
            improvement = _calculate_improvement(val_a, val_b)
        else:
            improvement = None

        rows.append(
            {
                "metric": key,
                "without_llm": val_a,
                "with_llm": val_b,
                "improvement_pct": improvement,
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, float_format="%.2f")


def _write_summary_md(
    output_path: Path,
    strategy_name: str,
    asset_class: str,
    data_info: dict[str, Any],
    result_a: dict[str, Any],
    result_b: dict[str, Any],
) -> None:
    """Write summary report in Markdown format.

    Args:
        output_path: Output markdown path
        strategy_name: Strategy name
        asset_class: Asset class
        data_info: Data information (bars, period, symbol)
        result_a: Results without LLM context
        result_b: Results with LLM context
    """
    lines = []
    lines.append(f"# A/B Backtest Comparison: {strategy_name}")
    lines.append("")
    lines.append("## Configuration")
    lines.append(f"- Strategy: {strategy_name}")
    lines.append(f"- Asset Class: {asset_class}")
    lines.append(
        f"- Data Period: {data_info.get('start_date', 'N/A')} ~ {data_info.get('end_date', 'N/A')}"
    )
    lines.append(f"- Total Bars: {data_info.get('total_bars', 'N/A'):,}")
    if "symbol" in data_info:
        lines.append(f"- Symbol: {data_info['symbol']}")
    lines.append("")

    lines.append("## Results Comparison")
    lines.append("")

    # Key metrics table
    lines.append("### Key Metrics")
    lines.append("")
    lines.append("| Metric | Without LLM | With LLM | Improvement |")
    lines.append("|--------|-------------|----------|-------------|")

    key_metrics = [
        ("sharpe_ratio", "Sharpe Ratio", ":.2f"),
        ("total_return_pct", "Total Return %", ":.2f"),
        ("annualized_return", "Annualized Return %", ":.2f"),
        ("max_drawdown_pct", "Max Drawdown %", ":.2f"),
        ("win_rate", "Win Rate %", ":.1f"),
        ("profit_factor", "Profit Factor", ":.2f"),
    ]

    for key, label, fmt in key_metrics:
        val_a = result_a[key]
        val_b = result_b[key]
        improvement = _calculate_improvement(val_a, val_b)
        lines.append(
            f"| {label} | {val_a:{fmt}} | {val_b:{fmt}} | {improvement:+.1f}% |"
        )

    lines.append("")

    # Trading statistics
    lines.append("### Trading Statistics")
    lines.append("")
    lines.append("| Metric | Without LLM | With LLM | Improvement |")
    lines.append("|--------|-------------|----------|-------------|")

    trade_metrics = [
        ("total_trades", "Total Trades", ""),
        ("winning_trades", "Winning Trades", ""),
        ("losing_trades", "Losing Trades", ""),
        ("avg_holding_days", "Avg Holding Days", ":.1f"),
    ]

    for key, label, fmt in trade_metrics:
        val_a = result_a[key]
        val_b = result_b[key]
        if fmt:
            val_a_str = f"{val_a:{fmt}}"
            val_b_str = f"{val_b:{fmt}}"
        else:
            val_a_str = str(int(val_a))
            val_b_str = str(int(val_b))
        improvement = _calculate_improvement(val_a, val_b)
        lines.append(f"| {label} | {val_a_str} | {val_b_str} | {improvement:+.1f}% |")

    lines.append("")

    # Summary verdict
    lines.append("## Summary")
    lines.append("")
    sharpe_improvement = _calculate_improvement(
        result_a["sharpe_ratio"], result_b["sharpe_ratio"]
    )
    if sharpe_improvement > 5:
        verdict = "✅ **LLM context shows significant improvement**"
    elif sharpe_improvement > 0:
        verdict = "⚠️ **LLM context shows marginal improvement**"
    else:
        verdict = "❌ **LLM context does not improve performance**"

    lines.append(verdict)
    lines.append("")
    lines.append(f"- Sharpe ratio improvement: {sharpe_improvement:+.1f}%")
    lines.append(
        f"- Return improvement: {_calculate_improvement(result_a['total_return_pct'], result_b['total_return_pct']):+.1f}%"
    )
    lines.append(
        f"- Drawdown change: {_calculate_improvement(result_a['max_drawdown_pct'], result_b['max_drawdown_pct']):+.1f}%"
    )
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _print_results(result_a: dict[str, Any], result_b: dict[str, Any]) -> None:
    """Print results comparison to console.

    Args:
        result_a: Results without LLM context
        result_b: Results with LLM context
    """
    print("\n" + "=" * 80)
    print("A/B BACKTEST COMPARISON RESULTS")
    print("=" * 80)
    print()
    print(f"{'Metric':<30} {'Without LLM':>15} {'With LLM':>15} {'Improvement':>15}")
    print("-" * 80)

    metrics_to_print = [
        ("sharpe_ratio", "Sharpe Ratio", ":.2f"),
        ("total_return_pct", "Total Return %", ":.2f"),
        ("annualized_return", "Annualized Return %", ":.2f"),
        ("max_drawdown_pct", "Max Drawdown %", ":.2f"),
        ("win_rate", "Win Rate %", ":.1f"),
        ("total_trades", "Total Trades", ""),
        ("profit_factor", "Profit Factor", ":.2f"),
        ("avg_holding_days", "Avg Holding Days", ":.1f"),
    ]

    for key, label, fmt in metrics_to_print:
        val_a = result_a[key]
        val_b = result_b[key]
        improvement = _calculate_improvement(val_a, val_b)

        if fmt:
            val_a_str = f"{val_a:{fmt}}"
            val_b_str = f"{val_b:{fmt}}"
        else:
            val_a_str = str(int(val_a))
            val_b_str = str(int(val_b))

        print(f"{label:<30} {val_a_str:>15} {val_b_str:>15} {improvement:>+14.1f}%")

    print("=" * 80)
    print()

    # Highlight key result
    sharpe_improvement = _calculate_improvement(
        result_a["sharpe_ratio"], result_b["sharpe_ratio"]
    )
    print(f"Sharpe Ratio Improvement: {sharpe_improvement:+.2f}%")
    if sharpe_improvement > 0:
        print("✅ LLM context improves strategy performance")
    else:
        print("❌ LLM context does not improve strategy performance")
    print()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="A/B backtest comparison: use_llm_context=true vs false"
    )

    # Strategy config
    parser.add_argument(
        "--strategy", required=True, help="Strategy name (e.g., bb_reversion)"
    )
    parser.add_argument(
        "--asset", default="stock", choices=["stock", "futures"], help="Asset class"
    )
    parser.add_argument(
        "--initial-capital", type=float, default=10_000_000, help="Initial capital"
    )

    # Data source (mutually exclusive)
    data_group = parser.add_mutually_exclusive_group(required=True)
    data_group.add_argument("--data", type=Path, help="Path to CSV data file")
    data_group.add_argument("--symbol", help="Symbol to load from Parquet market data")

    # Parquet options (required if --symbol is used)
    parser.add_argument(
        "--start-date", help="Start date (YYYY-MM-DD, required with --symbol)"
    )
    parser.add_argument(
        "--end-date", help="End date (YYYY-MM-DD, required with --symbol)"
    )

    # Output
    parser.add_argument(
        "--output-dir", default="artifacts/llm_ab_compare", help="Output directory"
    )

    args = parser.parse_args()

    # Validate Parquet args
    if args.symbol and (not args.start_date or not args.end_date):
        parser.error("--start-date and --end-date are required when using --symbol")

    # Load data
    print("Loading data...")
    if args.data:
        data = _load_data_from_csv(args.data)
        symbol = data["code"].iloc[0] if "code" in data.columns else "unknown"
    else:
        data = _load_data_from_parquet(
            args.asset, args.symbol, args.start_date, args.end_date
        )
        symbol = args.symbol

    if data.empty:
        print("Error: No data loaded")
        return 1

    print(f"  Loaded {len(data):,} bars")
    print(f"  Period: {data['datetime'].min()} ~ {data['datetime'].max()}")
    print()

    # Run backtests
    print("Running backtest A (without LLM context)...")
    result_a = _run_backtest(
        args.strategy,
        args.asset,
        data,
        use_llm_context=False,
        initial_capital=args.initial_capital,
    )
    print(
        f"  Sharpe: {result_a['sharpe_ratio']:.2f}, Return: {result_a['total_return_pct']:.2f}%"
    )
    print()

    print("Running backtest B (with LLM context)...")
    result_b = _run_backtest(
        args.strategy,
        args.asset,
        data,
        use_llm_context=True,
        initial_capital=args.initial_capital,
    )
    print(
        f"  Sharpe: {result_b['sharpe_ratio']:.2f}, Return: {result_b['total_return_pct']:.2f}%"
    )
    print()

    # Print comparison
    _print_results(result_a, result_b)

    # Write output files
    output_dir = Path(args.output_dir) / args.strategy
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "comparison.csv"
    _write_comparison_csv(csv_path, result_a, result_b)
    print(f"Wrote comparison CSV: {csv_path}")

    data_info = {
        "start_date": str(data["datetime"].min().date()),
        "end_date": str(data["datetime"].max().date()),
        "total_bars": len(data),
        "symbol": symbol,
    }
    md_path = output_dir / "summary.md"
    _write_summary_md(md_path, args.strategy, args.asset, data_info, result_a, result_b)
    print(f"Wrote summary report: {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
