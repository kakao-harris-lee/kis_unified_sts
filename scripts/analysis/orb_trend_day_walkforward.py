"""Backtest + walk-forward validation for the ORB trend-day futures strategy.

Honest validation harness for ``orb_trend_day`` on KOSPI200 futures minute data
(symbol 101S6000) over the clean window Dec 2025 – Apr 2026.

Runs:
  1. A full-window backtest (headline metrics).
  2. A rolling walk-forward (IS/OOS folds) — the real test. Per-fold Sharpe, MDD,
     win-rate, trade count, and an OOS-vs-IS verdict.

Uses the SAME path the live registry uses: BacktestStrategyAdapter -> BacktestEngine.
Engine risk layer is left off; stops/trailing/EOD come from the strategy's
TrendTrailExit. close_on_day_change=True keeps positions intraday (futures).

Run:
    PYTHONPATH=<worktree> .venv/bin/python scripts/analysis/orb_trend_day_walkforward.py
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.backtest import BacktestConfig, BacktestEngine  # noqa: E402
from shared.backtest.adapter import BacktestStrategyAdapter  # noqa: E402
from shared.backtest.result import BacktestResult  # noqa: E402
from shared.config import ConfigLoader  # noqa: E402
from shared.storage.market_data_store import load_market_bars_for_backtest  # noqa: E402
from shared.strategy.registry import (  # noqa: E402
    StrategyFactory,
    register_builtin_components,
)

SYMBOL = "101S6000"
POINT_VALUE = 50_000  # KRW per KOSPI200 index point


def _load(start: datetime, end: datetime) -> pd.DataFrame:
    df = load_market_bars_for_backtest(
        symbol=SYMBOL, asset_class="futures", timeframe="minute", start=start, end=end
    )
    if df.empty:
        raise SystemExit(f"No data for {SYMBOL} in {start.date()}..{end.date()}")
    # Engine requires a `code` column; the loader provides it.
    return df.sort_values("datetime").reset_index(drop=True)


def _build_strategy_and_config():
    """Return (TradingStrategy, raw_config_dict) for the adapter.

    Loads the config the same way the factory does and keeps the dict so the
    BacktestStrategyAdapter can read entry params (e.g. timeframe_minutes).
    """
    register_builtin_components()
    cfg = ConfigLoader.load_strategy("futures", "orb_trend_day")
    strategy = StrategyFactory.create(cfg)
    return strategy, cfg


def _backtest(df: pd.DataFrame) -> BacktestResult:
    strategy, cfg = _build_strategy_and_config()
    adapter = BacktestStrategyAdapter(strategy, cfg)
    config = BacktestConfig.futures(
        initial_capital=100_000_000, contracts=1, point_value=POINT_VALUE
    )
    # Intraday futures: never hold overnight. Strategy exit owns stops/trailing/EOD.
    config.risk.close_on_day_change = True
    config.risk.stop_loss_pct = 100.0  # effectively disable engine % stop
    config.risk.take_profit_pct = 1000.0
    config.risk.trailing_stop_enabled = False
    config.risk.use_atr_stop = False
    engine = BacktestEngine(adapter, config)
    return engine.run(df)


@dataclass
class FoldResult:
    fold: int
    is_start: str
    is_end: str
    oos_start: str
    oos_end: str
    is_sharpe: float
    is_return: float
    is_trades: int
    oos_sharpe: float
    oos_return: float
    oos_mdd: float
    oos_win_rate: float
    oos_trades: int


def _split_folds(df: pd.DataFrame, is_months: int, oos_months: int):
    """Rolling calendar folds: (is_df, oos_df) pairs by month boundaries."""
    df = df.copy()
    df["_ym"] = df["datetime"].dt.to_period("M")
    months = sorted(df["_ym"].unique())
    folds = []
    i = 0
    while i + is_months + oos_months <= len(months):
        is_months_sel = months[i : i + is_months]
        oos_months_sel = months[i + is_months : i + is_months + oos_months]
        is_df = df[df["_ym"].isin(is_months_sel)].drop(columns="_ym")
        oos_df = df[df["_ym"].isin(oos_months_sel)].drop(columns="_ym")
        folds.append((is_df.reset_index(drop=True), oos_df.reset_index(drop=True)))
        i += oos_months  # step by OOS window (rolling)
    return folds


def _summary(r: BacktestResult) -> str:
    return (
        f"trades={r.total_trades:3d} ret={r.total_return_pct:+7.2f}% "
        f"sharpe={r.sharpe_ratio:+6.2f} mdd={r.max_drawdown_pct:5.2f}% "
        f"win={r.win_rate:5.1f}%"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2025-12-01")
    parser.add_argument("--end", default="2026-04-30")
    parser.add_argument("--is-months", type=int, default=2)
    parser.add_argument("--oos-months", type=int, default=1)
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end)

    print(f"Loading {SYMBOL} minute bars {start.date()}..{end.date()} ...")
    df = _load(start, end)
    print(f"  {len(df)} bars, {df['datetime'].dt.date.nunique()} trading days")

    print("\n=== FULL-WINDOW BACKTEST ===")
    full = _backtest(df)
    print(f"  {_summary(full)}")
    if full.exit_reasons:
        print(f"  exit_reasons: {dict(full.exit_reasons)}")

    print(
        f"\n=== WALK-FORWARD (IS={args.is_months}mo / OOS={args.oos_months}mo, "
        f"rolling) ==="
    )
    folds = _split_folds(df, args.is_months, args.oos_months)
    results: list[FoldResult] = []
    for k, (is_df, oos_df) in enumerate(folds, 1):
        is_r = _backtest(is_df)
        oos_r = _backtest(oos_df)
        fr = FoldResult(
            fold=k,
            is_start=str(is_df["datetime"].iloc[0].date()),
            is_end=str(is_df["datetime"].iloc[-1].date()),
            oos_start=str(oos_df["datetime"].iloc[0].date()),
            oos_end=str(oos_df["datetime"].iloc[-1].date()),
            is_sharpe=is_r.sharpe_ratio,
            is_return=is_r.total_return_pct,
            is_trades=is_r.total_trades,
            oos_sharpe=oos_r.sharpe_ratio,
            oos_return=oos_r.total_return_pct,
            oos_mdd=oos_r.max_drawdown_pct,
            oos_win_rate=oos_r.win_rate,
            oos_trades=oos_r.total_trades,
        )
        results.append(fr)
        print(
            f"  fold {k}: IS[{fr.is_start}..{fr.is_end}] "
            f"sharpe={fr.is_sharpe:+5.2f} trades={fr.is_trades:3d}  ->  "
            f"OOS[{fr.oos_start}..{fr.oos_end}] "
            f"ret={fr.oos_return:+6.2f}% sharpe={fr.oos_sharpe:+5.2f} "
            f"mdd={fr.oos_mdd:4.1f}% win={fr.oos_win_rate:4.1f}% "
            f"trades={fr.oos_trades:3d}"
        )

    if results:
        oos_rets = [r.oos_return for r in results]
        oos_sharpes = [r.oos_sharpe for r in results]
        oos_trades = sum(r.oos_trades for r in results)
        net_oos = sum(oos_rets)
        pos_folds = sum(1 for x in oos_rets if x > 0)
        print("\n=== WALK-FORWARD AGGREGATE (OOS) ===")
        print(f"  folds: {len(results)}  | OOS trades total: {oos_trades}")
        print(f"  net OOS return (sum of folds): {net_oos:+.2f}%")
        print(f"  mean OOS sharpe: {sum(oos_sharpes) / len(oos_sharpes):+.2f}")
        print(f"  positive-return folds: {pos_folds}/{len(results)}")
        print(
            "  VERDICT: "
            + (
                "OOS net-positive"
                if net_oos > 0 and pos_folds >= len(results) / 2
                else "OOS NOT robust (net-negative or majority losing folds)"
            )
        )


if __name__ == "__main__":
    main()
