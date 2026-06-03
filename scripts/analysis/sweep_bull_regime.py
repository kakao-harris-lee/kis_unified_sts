#!/usr/bin/env python3
"""Bull-regime parameter sweep for stock minute strategies.

Workflow:
1. Position matrix sweep (order_amount_per_stock x max_positions)
2. Pick best position combo per strategy (by total_return_pct)
3. Bull-regime parameter sweep on the best position combo

Outputs:
- CSV: all run results
- Markdown: best configs and top candidates
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
from shared.collector.historical.stock import (  # noqa: E402
    STOCK_UNIVERSE,
    load_stock_minute_from_clickhouse,
)
from shared.config.loader import ConfigLoader  # noqa: E402
from shared.strategy.registry import StrategyFactory, register_builtin_components  # noqa: E402


def _parse_date(v: str) -> date:
    return datetime.strptime(v, "%Y-%m-%d").date()


def _set_nested(data: dict[str, Any], path: str, value: Any) -> None:
    cur = data
    keys = path.split(".")
    for key in keys[:-1]:
        if key not in cur or not isinstance(cur[key], dict):
            cur[key] = {}
        cur = cur[key]
    cur[keys[-1]] = value


def _select_stocks(tier: str) -> list[dict[str, str]]:
    if tier == "all":
        return list(STOCK_UNIVERSE)
    return [s for s in STOCK_UNIVERSE if s["tier"] == tier]


def _load_portfolio_data(tier: str, start: date, end: date) -> tuple[pd.DataFrame, list[str], int]:
    stocks = _select_stocks(tier)
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
        cols = ["datetime", "open", "high", "low", "close", "volume", "code", "name"]
        for col in cols:
            if col not in df.columns:
                if col == "code":
                    df[col] = code
                elif col == "name":
                    df[col] = s["name"]
        frames.append(df[cols].copy())

    if not frames:
        raise RuntimeError("No symbol data loaded")

    data = pd.concat(frames, ignore_index=True).sort_values(["datetime", "code"]).reset_index(drop=True)
    return data, missing, len(stocks)


def _build_backtest_config(strategy_cfg: dict[str, Any], capital: float) -> BacktestConfig:
    bt = strategy_cfg.get("strategy", {}).get("backtest", {})
    pos = strategy_cfg.get("strategy", {}).get("position", {}).get("params", {})

    bt_capital = float(bt.get("initial_capital", capital))
    bt_position_size_pct = float(bt.get("position_size_pct", 10.0) or 10.0)
    max_positions = int(pos.get("max_positions", 5) or 5)
    order_amount = float(pos.get("order_amount_per_stock", 0) or 0)
    if order_amount <= 0:
        order_amount = None

    config = BacktestConfig.stock(
        initial_capital=bt_capital,
        position_size_pct=bt_position_size_pct,
        order_amount_per_stock=order_amount,
        max_positions=max_positions,
    )
    if "risk" in bt:
        config.risk = RiskConfig.from_dict(bt["risk"])
    return config


def _run_once(strategy_cfg: dict[str, Any], data: pd.DataFrame, capital: float) -> BacktestEngine:
    config = _build_backtest_config(strategy_cfg, capital)
    strategy = StrategyFactory.create(strategy_cfg)
    adapted = BacktestStrategyAdapter(strategy, strategy_cfg)
    engine = BacktestEngine(adapted, config)
    return engine.run(data)


def _position_grid() -> list[dict[str, Any]]:
    combos: list[dict[str, Any]] = []
    for order_amount in (1_000_000, 2_000_000):
        for max_positions in (5, 10):
            combos.append(
                {
                    "strategy.position.params.order_amount_per_stock": float(order_amount),
                    "strategy.position.params.max_positions": int(max_positions),
                }
            )
    return combos


def _bull_grid(strategy_name: str) -> list[dict[str, Any]]:
    combos: list[dict[str, Any]] = []
    if strategy_name == "trend_pullback":
        for rsi in (34.0, 38.0):
            for bb_touch in (1.005, 1.01, 1.015):
                for cooldown in (60, 120):
                    combos.append(
                        {
                            "strategy.entry.params.rsi_oversold": float(rsi),
                            "strategy.entry.params.bb_touch_buffer": float(bb_touch),
                            "strategy.entry.params.signal_cooldown_seconds": int(cooldown),
                        }
                    )
    elif strategy_name == "momentum_breakout":
        for rvol in (1.5, 1.9):
            for breakout in (0.02, 0.05, 0.08):
                for cooldown in (120, 300):
                    combos.append(
                        {
                            "strategy.entry.params.rvol_threshold": float(rvol),
                            "strategy.entry.params.breakout_buffer_pct": float(breakout),
                            "strategy.entry.params.signal_cooldown_seconds": int(cooldown),
                        }
                    )
    else:
        raise ValueError(f"Unsupported strategy for bull sweep: {strategy_name}")
    return combos


def _format_params(params: dict[str, Any]) -> str:
    return json.dumps(params, ensure_ascii=False, sort_keys=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep bull-regime parameters for minute stock strategies.")
    parser.add_argument("--start", default="2026-02-01", help="YYYY-MM-DD")
    parser.add_argument("--end", default="2026-02-26", help="YYYY-MM-DD")
    parser.add_argument("--tier", default="all", choices=["top", "mid", "bottom", "all"])
    parser.add_argument("--capital", type=float, default=100_000_000)
    parser.add_argument("--output-dir", default="output/analysis/bull_sweep")
    args = parser.parse_args()

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    if end < start:
        raise SystemExit("end must be >= start")

    register_builtin_components()
    data, missing, requested = _load_portfolio_data(args.tier, start, end)

    strategies = ["trend_pullback", "momentum_breakout"]
    rows: list[dict[str, Any]] = []

    print(
        f"[data] symbols_loaded={requested - len(missing)}/{requested} "
        f"missing={len(missing)} bars={len(data)}"
    )

    best_position_for_strategy: dict[str, dict[str, Any]] = {}
    run_idx = 0

    # Phase 1: position matrix
    for strategy_name in strategies:
        base_cfg = ConfigLoader.load_strategy("stock", strategy_name)
        combos = _position_grid()
        print(f"[phase1] {strategy_name} position combos={len(combos)}")
        for combo in combos:
            run_idx += 1
            cfg = copy.deepcopy(base_cfg)
            for path, value in combo.items():
                _set_nested(cfg, path, value)
            result = _run_once(cfg, data, args.capital)
            row = {
                "run_idx": run_idx,
                "phase": "position",
                "strategy": strategy_name,
                "params": _format_params(combo),
                "total_return_pct": float(result.total_return_pct),
                "sharpe_ratio": float(result.sharpe_ratio),
                "max_drawdown_pct": float(result.max_drawdown_pct),
                "total_trades": int(result.total_trades),
                "win_rate": float(result.win_rate),
            }
            rows.append(row)
            print(
                f"  [position] #{run_idx:03d} ret={row['total_return_pct']:+.3f}% "
                f"trades={row['total_trades']} sharpe={row['sharpe_ratio']:.3f}"
            )

        pos_df = pd.DataFrame([r for r in rows if r["phase"] == "position" and r["strategy"] == strategy_name])
        best_row = pos_df.sort_values(["total_return_pct", "sharpe_ratio"], ascending=False).iloc[0]
        best_position_for_strategy[strategy_name] = json.loads(best_row["params"])
        print(
            f"[phase1-best] {strategy_name} "
            f"ret={best_row['total_return_pct']:+.3f}% params={best_row['params']}"
        )

    # Phase 2: bull parameter sweep on best position combo
    for strategy_name in strategies:
        base_cfg = ConfigLoader.load_strategy("stock", strategy_name)
        position_best = best_position_for_strategy[strategy_name]
        bull_combos = _bull_grid(strategy_name)
        print(f"[phase2] {strategy_name} bull combos={len(bull_combos)}")

        for combo in bull_combos:
            run_idx += 1
            cfg = copy.deepcopy(base_cfg)
            merged_params = {}
            merged_params.update(position_best)
            merged_params.update(combo)
            for path, value in merged_params.items():
                _set_nested(cfg, path, value)
            result = _run_once(cfg, data, args.capital)
            row = {
                "run_idx": run_idx,
                "phase": "bull",
                "strategy": strategy_name,
                "params": _format_params(merged_params),
                "total_return_pct": float(result.total_return_pct),
                "sharpe_ratio": float(result.sharpe_ratio),
                "max_drawdown_pct": float(result.max_drawdown_pct),
                "total_trades": int(result.total_trades),
                "win_rate": float(result.win_rate),
            }
            rows.append(row)
            print(
                f"  [bull] #{run_idx:03d} ret={row['total_return_pct']:+.3f}% "
                f"trades={row['total_trades']} sharpe={row['sharpe_ratio']:.3f}"
            )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"bull_sweep_{args.start}_{args.end}_{stamp}.csv"
    md_path = out_dir / f"bull_sweep_{args.start}_{args.end}_{stamp}.md"

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)

    lines: list[str] = []
    lines.append("# Bull Regime Sweep Report")
    lines.append("")
    lines.append(f"- period: {args.start} ~ {args.end}")
    lines.append(f"- tier: {args.tier}")
    lines.append(f"- capital: {args.capital:,.0f}")
    lines.append(f"- symbols_loaded: {requested - len(missing)}/{requested}")
    lines.append(f"- bars: {len(data)}")
    lines.append("")
    for strategy_name in strategies:
        lines.append(f"## {strategy_name}")
        lines.append("")
        sdf = df[df["strategy"] == strategy_name].copy()
        best = sdf.sort_values(["total_return_pct", "sharpe_ratio"], ascending=False).iloc[0]
        lines.append(
            f"- best: return={best['total_return_pct']:+.3f}% "
            f"trades={int(best['total_trades'])} sharpe={best['sharpe_ratio']:.3f}"
        )
        lines.append(f"- params: `{best['params']}`")
        lines.append("")
        top5 = sdf.sort_values(["total_return_pct", "sharpe_ratio"], ascending=False).head(5)
        lines.append("| phase | return% | trades | sharpe | mdd% | params |")
        lines.append("|---|---:|---:|---:|---:|---|")
        for _, r in top5.iterrows():
            lines.append(
                f"| {r['phase']} | {r['total_return_pct']:+.3f} | {int(r['total_trades'])} | "
                f"{r['sharpe_ratio']:.3f} | {r['max_drawdown_pct']:.3f} | `{r['params']}` |"
            )
        lines.append("")

    md_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    print(f"[done] csv={csv_path}")
    print(f"[done] md={md_path}")


if __name__ == "__main__":
    main()
