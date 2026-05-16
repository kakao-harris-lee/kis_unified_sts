#!/usr/bin/env python3
"""Portfolio-style stock backtest for multi-symbol minute strategies.

This script runs a single BacktestEngine instance over an interleaved
multi-symbol minute stream (datetime, code order), so capital and position
limits are shared like a portfolio.
"""

from __future__ import annotations

import argparse
import copy
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
from shared.backtest.daily_adapter import (  # noqa: E402
    DailyBacktestAdapter,
    load_stock_daily_from_clickhouse,
)
from shared.collector.historical.stock import (  # noqa: E402
    STOCK_UNIVERSE,
    load_stock_minute_from_clickhouse,
)
from shared.config.loader import ConfigLoader  # noqa: E402
from shared.strategy.registry import (  # noqa: E402
    StrategyFactory,
    register_builtin_components,
)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _select_stocks(tier: str) -> list[dict[str, str]]:
    if tier == "all":
        return list(STOCK_UNIVERSE)
    return [s for s in STOCK_UNIVERSE if s["tier"] == tier]


def _build_backtest_config(
    strategy_config: dict[str, Any],
    initial_capital: float,
    *,
    order_amount_per_stock: float | None = None,
    max_positions: int | None = None,
) -> BacktestConfig:
    bt_override = strategy_config.get("strategy", {}).get("backtest", {})
    position_params = (
        strategy_config.get("strategy", {}).get("position", {}).get("params", {})
    )

    # CLI capital represents the portfolio/account size for the experiment.
    # Strategy YAML may keep legacy standalone defaults, but this portfolio
    # runner should honor the explicit command-line capital.
    bt_capital = float(initial_capital)
    bt_position_size_pct = float(bt_override.get("position_size_pct", 10.0) or 10.0)
    resolved_max_positions = int(position_params.get("max_positions", 5) or 5)
    resolved_order_amount = float(position_params.get("order_amount_per_stock", 0) or 0)
    if order_amount_per_stock is not None:
        resolved_order_amount = float(order_amount_per_stock)
    if max_positions is not None:
        resolved_max_positions = int(max_positions)
    if resolved_order_amount <= 0:
        resolved_order_amount = None

    config = BacktestConfig.stock(
        initial_capital=bt_capital,
        position_size_pct=bt_position_size_pct,
        order_amount_per_stock=resolved_order_amount,
        max_positions=resolved_max_positions,
    )
    if "risk" in bt_override:
        config.risk = RiskConfig.from_dict(bt_override["risk"])
    return config


class DailyPortfolioAdapter:
    """Route each symbol to its own DailyBacktestAdapter in a portfolio engine.

    DailyBacktestAdapter precomputes rolling indicators over one symbol. The
    portfolio engine feeds interleaved multi-symbol bars, so sharing one daily
    adapter would mix SMA/RSI/ATR windows across symbols.
    """

    def __init__(self, strategy_config: dict[str, Any]):
        strategy_name = strategy_config.get("strategy", {}).get(
            "name", "daily_strategy"
        )
        self.name = strategy_name
        self._strategy_config = strategy_config
        self._adapters: dict[str, DailyBacktestAdapter] = {}
        self._pending_position: dict[str, Any] | None = None

    def prescan_data(self, data: pd.DataFrame) -> None:
        if "code" not in data.columns:
            raise ValueError("Daily portfolio backtest requires a code column")

        self._adapters.clear()
        for code, group in data.groupby("code", sort=False):
            cfg = copy.deepcopy(self._strategy_config)
            strategy = StrategyFactory.create(cfg)
            adapter = DailyBacktestAdapter(strategy, cfg)
            adapter.prescan_data(group.sort_values("datetime").reset_index(drop=True))
            self._adapters[str(code)] = adapter

    def set_position(self, position: dict[str, Any] | None) -> None:
        self._pending_position = position

    def _adapter_for_bar(self, bar: dict[str, Any]) -> DailyBacktestAdapter | None:
        code = str(bar.get("code", "") or "")
        adapter = self._adapters.get(code)
        if adapter is not None:
            adapter.set_position(self._pending_position)
        return adapter

    def check_exit(self, bar: dict[str, Any]):
        adapter = self._adapter_for_bar(bar)
        if adapter is None:
            return False, None
        return adapter.check_exit(bar)

    def on_bar(self, bar: dict[str, Any]):
        adapter = self._adapter_for_bar(bar)
        if adapter is None:
            from shared.backtest.engine import SignalType

            return SignalType.HOLD
        return adapter.on_bar(bar)


def _load_symbol_data(
    *,
    code: str,
    name: str,
    timeframe: str,
    start: date,
    end: date,
) -> pd.DataFrame | None:
    if timeframe == "daily":
        df = load_stock_daily_from_clickhouse(code, start, end)
    else:
        df = load_stock_minute_from_clickhouse(code, start, end)

    if df is None or df.empty:
        return None

    cols = ["datetime", "open", "high", "low", "close", "volume", "code", "name"]
    for col in cols:
        if col not in df.columns:
            if col == "code":
                df[col] = code
            elif col == "name":
                df[col] = name
    return df[cols].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run portfolio-style stock backtest.")
    parser.add_argument(
        "--strategy", required=True, help="Strategy name (stock minute only)"
    )
    parser.add_argument(
        "--tier", default="all", choices=["top", "mid", "bottom", "all"]
    )
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=100_000_000)
    parser.add_argument(
        "--order-amount-per-stock",
        type=float,
        default=None,
        help="Override stock fixed order amount from strategy YAML.",
    )
    parser.add_argument(
        "--max-positions",
        type=int,
        default=None,
        help="Override max concurrent positions from strategy YAML.",
    )
    parser.add_argument("--output-dir", default="output/analysis/portfolio_backtest")
    args = parser.parse_args()

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    if end < start:
        raise SystemExit("end must be >= start")

    register_builtin_components()
    strategy_config = ConfigLoader.load_strategy("stock", args.strategy)
    timeframe = strategy_config.get("strategy", {}).get("timeframe", "minute")
    if timeframe not in ("minute", "daily"):
        raise SystemExit(f"Unsupported timeframe for '{args.strategy}': {timeframe}")

    stocks = _select_stocks(args.tier)
    if not stocks:
        raise SystemExit("No stocks selected")

    frames: list[pd.DataFrame] = []
    missing: list[str] = []
    for s in stocks:
        code = s["code"]
        try:
            df = _load_symbol_data(
                code=code,
                name=s["name"],
                timeframe=timeframe,
                start=start,
                end=end,
            )
        except Exception:
            missing.append(code)
            continue
        if df is None:
            missing.append(code)
            continue
        frames.append(df)

    if not frames:
        raise SystemExit("No symbol data loaded")

    data = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["datetime", "code"])
        .reset_index(drop=True)
    )

    config = _build_backtest_config(
        strategy_config,
        initial_capital=args.capital,
        order_amount_per_stock=args.order_amount_per_stock,
        max_positions=args.max_positions,
    )
    if timeframe == "daily":
        adapted = DailyPortfolioAdapter(strategy_config)
    else:
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
    metrics["timeframe"] = timeframe
    metrics["tier"] = args.tier
    metrics["start"] = args.start
    metrics["end"] = args.end
    metrics["symbols_requested"] = len(stocks)
    metrics["symbols_loaded"] = len(frames)
    metrics["symbols_missing"] = missing
    metrics["bars"] = len(data)
    metrics["config"] = config.to_dict()
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    trades_df = pd.DataFrame([t.to_dict() for t in result.trades])
    if not trades_df.empty:
        trades_df.to_csv(trades_path, index=False)
    else:
        trades_path.write_text(
            "code,name,strategy,side,entry_time,exit_time,entry_price,exit_price,quantity,pnl,pnl_pct,commission,exit_reason\n",
            encoding="utf-8",
        )

    print(f"strategy={args.strategy} tier={args.tier} period={args.start}~{args.end}")
    print(
        f"symbols_loaded={len(frames)}/{len(stocks)} bars={len(data)} trades={result.total_trades}"
    )
    print(
        f"return={result.total_return_pct:+.3f}% sharpe={result.sharpe_ratio:.3f} "
        f"mdd={result.max_drawdown_pct:.3f}% win_rate={result.win_rate:.2f}%"
    )
    print(f"metrics={metrics_path}")
    print(f"trades={trades_path}")


if __name__ == "__main__":
    main()
