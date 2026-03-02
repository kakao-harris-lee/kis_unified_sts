#!/usr/bin/env python3
"""Portfolio-style stock backtest for multi-symbol minute strategies.

This script runs a single BacktestEngine instance over an interleaved
multi-symbol minute stream (datetime, code order), so capital and position
limits are shared like a portfolio.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from shared.backtest import BacktestConfig, BacktestEngine  # noqa: E402
from shared.backtest.adapter import BacktestStrategyAdapter  # noqa: E402
from shared.backtest.config import RiskConfig  # noqa: E402
from shared.collector.historical.stock import (  # noqa: E402
    STOCK_UNIVERSE,
    load_stock_minute_from_clickhouse,
)
from shared.config.loader import ConfigLoader  # noqa: E402
from shared.strategy.registry import StrategyFactory, register_builtin_components  # noqa: E402


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _select_stocks(tier: str) -> list[dict[str, str]]:
    if tier == "all":
        return list(STOCK_UNIVERSE)
    return [s for s in STOCK_UNIVERSE if s["tier"] == tier]


def _build_backtest_config(strategy_config: dict[str, Any], initial_capital: float) -> BacktestConfig:
    bt_override = strategy_config.get("strategy", {}).get("backtest", {})
    position_params = (
        strategy_config.get("strategy", {})
        .get("position", {})
        .get("params", {})
    )

    bt_capital = float(bt_override.get("initial_capital", initial_capital))
    bt_position_size_pct = float(bt_override.get("position_size_pct", 10.0) or 10.0)
    max_positions = int(position_params.get("max_positions", 5) or 5)
    order_amount_per_stock = float(position_params.get("order_amount_per_stock", 0) or 0)
    if order_amount_per_stock <= 0:
        order_amount_per_stock = None

    config = BacktestConfig.stock(
        initial_capital=bt_capital,
        position_size_pct=bt_position_size_pct,
        order_amount_per_stock=order_amount_per_stock,
        max_positions=max_positions,
    )
    if "risk" in bt_override:
        config.risk = RiskConfig.from_dict(bt_override["risk"])
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run portfolio-style stock backtest.")
    parser.add_argument("--strategy", required=True, help="Strategy name (stock minute only)")
    parser.add_argument("--tier", default="all", choices=["top", "mid", "bottom", "all"])
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=100_000_000)
    parser.add_argument("--output-dir", default="output/analysis/portfolio_backtest")
    args = parser.parse_args()

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    if end < start:
        raise SystemExit("end must be >= start")

    register_builtin_components()
    strategy_config = ConfigLoader.load_strategy("stock", args.strategy)
    timeframe = strategy_config.get("strategy", {}).get("timeframe", "minute")
    if timeframe != "minute":
        raise SystemExit(
            f"Strategy '{args.strategy}' uses timeframe='{timeframe}'. "
            "This script supports minute strategies only."
        )

    stocks = _select_stocks(args.tier)
    if not stocks:
        raise SystemExit("No stocks selected")

    frames: list[pd.DataFrame] = []
    missing: list[str] = []
    for s in stocks:
        code = s["code"]
        try:
            df = load_stock_minute_from_clickhouse(code, start, end)
        except Exception:
            missing.append(code)
            continue
        if df is None or df.empty:
            missing.append(code)
            continue
        # Keep only required columns for portfolio backtest.
        cols = ["datetime", "open", "high", "low", "close", "volume", "code", "name"]
        for col in cols:
            if col not in df.columns:
                if col == "code":
                    df[col] = code
                elif col == "name":
                    df[col] = s["name"]
        frames.append(df[cols].copy())

    if not frames:
        raise SystemExit("No symbol data loaded")

    data = pd.concat(frames, ignore_index=True).sort_values(["datetime", "code"]).reset_index(drop=True)

    config = _build_backtest_config(strategy_config, initial_capital=args.capital)
    strategy = StrategyFactory.create(strategy_config)
    adapted = BacktestStrategyAdapter(strategy, strategy_config)
    result = BacktestEngine(adapted, config).run(data)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"{args.strategy}_{args.tier}_{args.start}_{args.end}_{stamp}"
    metrics_path = output_dir / f"{tag}_metrics.json"
    trades_path = output_dir / f"{tag}_trades.csv"

    metrics = result.to_dict()
    metrics["strategy"] = args.strategy
    metrics["tier"] = args.tier
    metrics["start"] = args.start
    metrics["end"] = args.end
    metrics["symbols_requested"] = len(stocks)
    metrics["symbols_loaded"] = len(frames)
    metrics["symbols_missing"] = missing
    metrics["bars"] = len(data)
    metrics["config"] = config.to_dict()
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    trades_df = pd.DataFrame([t.to_dict() for t in result.trades])
    if not trades_df.empty:
        trades_df.to_csv(trades_path, index=False)
    else:
        trades_path.write_text("code,name,strategy,side,entry_time,exit_time,entry_price,exit_price,quantity,pnl,pnl_pct,commission,exit_reason\n", encoding="utf-8")

    print(f"strategy={args.strategy} tier={args.tier} period={args.start}~{args.end}")
    print(f"symbols_loaded={len(frames)}/{len(stocks)} bars={len(data)} trades={result.total_trades}")
    print(
        f"return={result.total_return_pct:+.3f}% sharpe={result.sharpe_ratio:.3f} "
        f"mdd={result.max_drawdown_pct:.3f}% win_rate={result.win_rate:.2f}%"
    )
    print(f"metrics={metrics_path}")
    print(f"trades={trades_path}")


if __name__ == "__main__":
    main()
