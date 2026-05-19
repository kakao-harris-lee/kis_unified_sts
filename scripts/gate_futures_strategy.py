#!/usr/bin/env python3
"""Generalized re-scoped robust-gate runner for ANY futures strategy.

Spec 2026-05-19 §7. Reuses shared.backtest.robust_gate (DRY).
Usage:
  python scripts/gate_futures_strategy.py --strategy williams_r_15m \
    --data data/kospi200f_1m_ch_101S6000.csv \
    --space config/optuna/futures/williams_r_15m.yaml \
    --holdout-split 2026-02-01 --min-trades 50 --trials 70
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import optuna
import pandas as pd
import yaml
from optuna.samplers import TPESampler

from shared.backtest.adapter import BacktestStrategyAdapter
from shared.backtest.config import BacktestConfig
from shared.backtest.engine import BacktestEngine
from shared.backtest.robust_gate import objective_value, rescoped_gate
from shared.config.loader import ConfigLoader
from shared.strategy.registry import StrategyFactory, register_builtin_components

register_builtin_components()

_DEFAULT_DATA = "data/kospi200f_1m_ch_101S6000.csv"


def apply_params(base_cfg: dict, params: dict) -> dict:
    cfg = copy.deepcopy(base_cfg)
    for dotted, val in params.items():
        node = cfg["strategy"]
        parts = dotted.split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = val
    return cfg


def suggest_params(trial, space: dict) -> dict:
    out = {}
    for name, spec in space.items():
        if spec["type"] == "int":
            out[name] = trial.suggest_int(name, spec["low"], spec["high"])
        else:
            out[name] = trial.suggest_float(name, spec["low"], spec["high"])
    return out


def _run_backtest(cfg: dict, df, bt_config: BacktestConfig) -> dict:
    strategy = StrategyFactory.create(cfg)
    adapter = BacktestStrategyAdapter(strategy, cfg)
    engine = BacktestEngine(adapter, bt_config)
    return engine.run(df.copy()).to_metrics_dict()


def _load_data(path: str):
    from shared.validation.cli_validators import validate_csv_file

    return validate_csv_file(
        path,
        reject_duplicate_datetime=True,
        require_monotonic_datetime=True,
        max_zero_volume_ratio=0.95,
        max_zero_volume_price_move_ratio=0.20,
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--asset", default="futures")
    ap.add_argument("--data", "-d", default=_DEFAULT_DATA)
    ap.add_argument("--space", required=True)
    ap.add_argument("--trials", "-n", type=int, default=70)
    ap.add_argument("--holdout-split", "-H", default=None)
    ap.add_argument("--min-trades", "-M", type=int, default=50)
    a = ap.parse_args(argv)

    base_cfg = ConfigLoader.load_strategy(a.asset, a.strategy)
    space = yaml.safe_load(Path(a.space).read_text())["search_space"]
    bt_over = base_cfg.get("strategy", {}).get("backtest", {}) or {}
    bt_config = BacktestConfig.futures(
        initial_capital=bt_over.get("initial_capital", 10_000_000),
        point_value=bt_over.get("point_value", 50_000),
    )

    df = _load_data(a.data)
    opt_df, oos_df = df, None
    if a.holdout_split:
        split = pd.Timestamp(a.holdout_split)
        tz = df["datetime"].dt.tz
        if tz is not None and split.tzinfo is None:
            split = split.tz_localize(tz)
        opt_df = df[df["datetime"] < split].reset_index(drop=True)
        oos_df = df[df["datetime"] >= split].reset_index(drop=True)
        if len(opt_df) < 500 or len(oos_df) < 500:
            print("ERROR: split leaves too few bars on one side.")
            return 2

    def objective(trial):
        params = suggest_params(trial, space)
        cfg = apply_params(base_cfg, params)
        m = _run_backtest(cfg, opt_df, bt_config)
        for k in (
            "profit_factor",
            "total_trades",
            "win_rate",
            "total_return_pct",
            "max_drawdown_pct",
        ):
            trial.set_user_attr(k, float(m.get(k, 0.0)))
        return objective_value(m, a.min_trades)

    study = optuna.create_study(
        direction="maximize",
        sampler=TPESampler(seed=42),
        study_name=f"{a.strategy}_gate",
    )
    study.optimize(objective, n_trials=a.trials)

    print(f"best_params: {study.best_params}")
    print(f"best_value (train Sharpe): {study.best_value:.4f}")

    oos_m = {}
    if oos_df is not None:
        best_cfg = apply_params(base_cfg, study.best_params)
        oos_m = _run_backtest(best_cfg, oos_df, bt_config)
        print(
            f"OOS metrics: sharpe={oos_m.get('sharpe_ratio', float('nan')):.4f} "
            f"pf={oos_m.get('profit_factor', float('nan')):.4f} "
            f"mdd={oos_m.get('max_drawdown_pct', float('nan')):.2f}% "
            f"ret={oos_m.get('total_return_pct', float('nan')):.4f}% "
            f"trades={oos_m.get('total_trades', 0):.0f}"
        )

    rg = rescoped_gate(study, oos_m)
    verdict = "PASS" if rg["pass"] else "FAIL"
    print(
        f">>> RE-SCOPED GATE: {verdict} "
        f"(a={rg['a']} b={rg['b']} c={rg['c']} | "
        f"median_sharpe={rg['median_sharpe']:.2f} "
        f"basin={rg['basin_frac']:.1%} n_valid={rg['n_valid']})"
    )
    return 0 if rg["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
