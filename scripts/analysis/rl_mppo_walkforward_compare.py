#!/usr/bin/env python3
"""Walk-forward backtest comparison for RL MPPO strategy profiles.

This script runs rolling-window backtests using existing strategy YAML files
and prints a compact comparison for PnL / win-rate oriented profiles.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.backtest import BacktestConfig, BacktestEngine
from shared.backtest.adapter import BacktestStrategyAdapter
from shared.backtest.config import RiskConfig
from shared.config.loader import ConfigLoader
from shared.strategy.registry import StrategyFactory, register_builtin_components


@dataclass(frozen=True)
class Window:
    index: int
    start: datetime
    end: datetime


@dataclass
class WindowMetric:
    strategy: str
    window_index: int
    start: datetime
    end: datetime
    bars: int
    total_pnl: float
    total_return_pct: float
    win_rate: float
    trades: int
    sharpe: float
    max_drawdown_pct: float


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Walk-forward compare RL MPPO strategy YAML profiles",
    )
    parser.add_argument(
        "--data",
        default="data/kospi200f_1m_clean.csv",
        help="CSV data path (datetime, open, high, low, close, volume)",
    )
    parser.add_argument(
        "--asset",
        default="futures",
        help="Asset class for ConfigLoader strategy lookup",
    )
    parser.add_argument(
        "--strategies",
        default="rl_mppo,rl_mppo_profile_pnl,rl_mppo_profile_winrate",
        help="Comma-separated strategy YAML names",
    )
    parser.add_argument(
        "--start",
        default="2025-01-02",
        help="Backtest start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        default="2025-12-31",
        help="Backtest end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=60,
        help="Rolling window size in days",
    )
    parser.add_argument(
        "--step-days",
        type=int,
        default=60,
        help="Rolling step size in days",
    )
    parser.add_argument(
        "--max-windows",
        type=int,
        default=0,
        help="Max number of windows (0 = all)",
    )
    parser.add_argument(
        "--min-bars",
        type=int,
        default=300,
        help="Minimum bars required for a valid window",
    )
    parser.add_argument(
        "--output-csv",
        default="output/analysis/rl_mppo_walkforward_compare.csv",
        help="Optional CSV output path",
    )
    parser.add_argument(
        "--output-json",
        default="output/analysis/rl_mppo_walkforward_compare.json",
        help="Optional JSON output path",
    )
    return parser.parse_args()


def _load_data(path: Path, start: datetime, end: datetime) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    df = pd.read_csv(path)
    if "datetime" not in df.columns:
        raise ValueError("CSV must contain 'datetime' column")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df = df[(df["datetime"] >= start) & (df["datetime"] <= end)].copy()
    if df.empty:
        raise ValueError("No data rows in selected date range")
    return df


def _build_windows(
    df: pd.DataFrame,
    *,
    start: datetime,
    end: datetime,
    window_days: int,
    step_days: int,
    min_bars: int,
    max_windows: int,
) -> list[Window]:
    if window_days < 1:
        raise ValueError("window_days must be >= 1")
    if step_days < 1:
        raise ValueError("step_days must be >= 1")

    windows: list[Window] = []
    cur = start
    idx = 1
    while cur <= end:
        win_end = min(end, cur + timedelta(days=window_days) - timedelta(seconds=1))
        bars = int(((df["datetime"] >= cur) & (df["datetime"] <= win_end)).sum())
        if bars >= min_bars:
            windows.append(Window(index=idx, start=cur, end=win_end))
            idx += 1
            if max_windows > 0 and len(windows) >= max_windows:
                break
        cur = cur + timedelta(days=step_days)
    if not windows:
        raise ValueError("No valid rolling windows after applying min_bars filter")
    return windows


def _make_backtest_config(strategy_cfg: dict[str, Any]) -> BacktestConfig:
    bt_override = strategy_cfg.get("strategy", {}).get("backtest", {})
    initial_capital = float(bt_override.get("initial_capital", 100_000_000))
    point_value = float(bt_override.get("point_value", 250_000))
    config = BacktestConfig.futures(
        initial_capital=initial_capital,
        point_value=point_value,
    )
    if "risk" in bt_override:
        config.risk = RiskConfig.from_dict(bt_override["risk"])
    return config


def _run_window(
    strategy_name: str,
    strategy_cfg: dict[str, Any],
    window: Window,
    window_df: pd.DataFrame,
) -> WindowMetric:
    strategy = StrategyFactory.create(strategy_cfg)
    adapted = BacktestStrategyAdapter(strategy, strategy_cfg)
    engine = BacktestEngine(adapted, _make_backtest_config(strategy_cfg))
    result = engine.run(window_df)
    return WindowMetric(
        strategy=strategy_name,
        window_index=window.index,
        start=window.start,
        end=window.end,
        bars=int(len(window_df)),
        total_pnl=float(result.total_pnl),
        total_return_pct=float(result.total_return_pct),
        win_rate=float(result.win_rate),
        trades=int(result.total_trades),
        sharpe=float(result.sharpe_ratio),
        max_drawdown_pct=float(result.max_drawdown_pct),
    )


def _aggregate(metrics: list[WindowMetric]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[WindowMetric]] = {}
    for row in metrics:
        grouped.setdefault(row.strategy, []).append(row)

    summary: dict[str, dict[str, float]] = {}
    for strategy, rows in grouped.items():
        rets = [r.total_return_pct for r in rows]
        wins = [r.win_rate for r in rows]
        pnls = [r.total_pnl for r in rows]
        sharpes = [r.sharpe for r in rows]
        mdds = [r.max_drawdown_pct for r in rows]
        trades = [r.trades for r in rows]
        total_trades = sum(trades)
        weighted_win = (
            sum(r.win_rate * r.trades for r in rows) / total_trades if total_trades > 0 else 0.0
        )
        summary[strategy] = {
            "windows": float(len(rows)),
            "total_pnl_sum": float(sum(pnls)),
            "avg_return_pct": float(mean(rets)),
            "median_return_pct": float(median(rets)),
            "avg_win_rate": float(mean(wins)),
            "weighted_win_rate": float(weighted_win),
            "positive_window_ratio": float(sum(1 for v in rets if v > 0.0) / len(rows)),
            "avg_sharpe": float(mean(sharpes)),
            "avg_max_drawdown_pct": float(mean(mdds)),
            "total_trades": float(total_trades),
        }
    return summary


def _save_outputs(
    metrics: list[WindowMetric],
    summary: dict[str, dict[str, float]],
    csv_path: Path,
    json_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "strategy",
                "window_index",
                "start",
                "end",
                "bars",
                "total_pnl",
                "total_return_pct",
                "win_rate",
                "trades",
                "sharpe",
                "max_drawdown_pct",
            ],
        )
        writer.writeheader()
        for row in metrics:
            writer.writerow(
                {
                    "strategy": row.strategy,
                    "window_index": row.window_index,
                    "start": row.start.isoformat(),
                    "end": row.end.isoformat(),
                    "bars": row.bars,
                    "total_pnl": round(row.total_pnl, 2),
                    "total_return_pct": round(row.total_return_pct, 4),
                    "win_rate": round(row.win_rate, 4),
                    "trades": row.trades,
                    "sharpe": round(row.sharpe, 4),
                    "max_drawdown_pct": round(row.max_drawdown_pct, 4),
                }
            )

    payload = {
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_summary(summary: dict[str, dict[str, float]]) -> None:
    print(
        f"{'strategy':<28} {'wins':>4} {'avg_ret%':>9} {'wgt_win%':>9} "
        f"{'pnl_sum':>14} {'avg_sharpe':>10} {'avg_mdd%':>9}"
    )
    ranked = sorted(
        summary.items(),
        key=lambda kv: (kv[1]["total_pnl_sum"], kv[1]["weighted_win_rate"]),
        reverse=True,
    )
    for strategy, s in ranked:
        print(
            f"{strategy:<28} "
            f"{int(s['windows']):>4} "
            f"{s['avg_return_pct']:>9.2f} "
            f"{s['weighted_win_rate']:>9.2f} "
            f"{s['total_pnl_sum']:>14,.0f} "
            f"{s['avg_sharpe']:>10.2f} "
            f"{s['avg_max_drawdown_pct']:>9.2f}"
        )


def main() -> int:
    args = _parse_args()
    register_builtin_components()

    strategies = [item.strip() for item in args.strategies.split(",") if item.strip()]
    if not strategies:
        raise ValueError("No strategies provided")

    start = datetime.fromisoformat(str(args.start))
    end = datetime.fromisoformat(str(args.end))
    if end < start:
        raise ValueError("end must be >= start")

    df = _load_data(Path(args.data), start=start, end=end)
    windows = _build_windows(
        df,
        start=start,
        end=end,
        window_days=int(args.window_days),
        step_days=int(args.step_days),
        min_bars=int(args.min_bars),
        max_windows=int(args.max_windows),
    )

    strategy_cfgs: dict[str, dict[str, Any]] = {}
    for strategy in strategies:
        strategy_cfgs[strategy] = ConfigLoader.load_strategy(
            args.asset, strategy, use_cache=False
        )

    metrics: list[WindowMetric] = []
    for window in windows:
        window_df = df[(df["datetime"] >= window.start) & (df["datetime"] <= window.end)].copy()
        for strategy in strategies:
            metrics.append(
                _run_window(
                    strategy_name=strategy,
                    strategy_cfg=strategy_cfgs[strategy],
                    window=window,
                    window_df=window_df,
                )
            )

    summary = _aggregate(metrics)
    _print_summary(summary)
    _save_outputs(
        metrics=metrics,
        summary=summary,
        csv_path=Path(args.output_csv),
        json_path=Path(args.output_json),
    )
    print(f"\nSaved CSV : {args.output_csv}")
    print(f"Saved JSON: {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
