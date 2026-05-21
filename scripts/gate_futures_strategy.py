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


def load_gate_config(path: str):
    """Load a RegimeGate YAML config into a GateConfig dataclass."""
    from shared.strategy.gates.regime_gate import GateConfig

    data = yaml.safe_load(Path(path).read_text())
    return GateConfig(
        regime_percentile_max=float(data.get("regime_percentile_max", 80.0)),
        impact_score_max=int(data.get("impact_score_max", 70)),
        event_window_minutes=int(data.get("event_window_minutes", 15)),
        require_overnight_us_direction=bool(
            data.get("require_overnight_us_direction", False)
        ),
        permissive_on_missing=bool(data.get("permissive_on_missing", True)),
    )


def head_to_head_verdict(
    baseline_oos: dict,
    gated_oos: dict,
    delta_min: float,
    gated_gate_pass: bool,
) -> tuple[bool, float]:
    """spec §8: PASS iff gated clears its own robust gate AND
    OOS Sharpe improves by >= delta_min AND MDD does not worsen.
    Returns (ok, delta_sharpe)."""
    delta = gated_oos.get("sharpe_ratio", -99.0) - baseline_oos.get(
        "sharpe_ratio", -99.0
    )
    mdd_ok = gated_oos.get("max_drawdown_pct", 1e9) <= baseline_oos.get(
        "max_drawdown_pct", 1e9
    )
    return (bool(gated_gate_pass) and (delta >= delta_min) and mdd_ok, delta)


def _run_backtest(cfg: dict, df, bt_config: BacktestConfig, gate=None) -> dict:
    strategy = StrategyFactory.create(cfg)
    adapter = BacktestStrategyAdapter(strategy, cfg)
    engine = BacktestEngine(adapter, bt_config, gate=gate)
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
    ap.add_argument(
        "--gate",
        default=None,
        help="path to RegimeGate YAML; if set, the engine is "
        "wrapped with the gate during the run",
    )
    ap.add_argument(
        "--head-to-head",
        action="store_true",
        help="run baseline (no gate) then gated; require "
        "Δ Sharpe >= --delta-sharpe AND no MDD worsening",
    )
    ap.add_argument(
        "--delta-sharpe",
        type=float,
        default=0.5,
        help="spec §8 head-to-head margin (default 0.5)",
    )
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

    # Head-to-head: run gated study and compare vs baseline.
    if a.head_to_head and a.gate:
        gate_cfg = load_gate_config(a.gate)
        full_df = pd.concat([opt_df, oos_df]) if oos_df is not None else opt_df
        gate = _build_gate(gate_cfg, full_df)

        def objective_gated(trial):
            params = suggest_params(trial, space)
            cfg = apply_params(base_cfg, params)
            m = _run_backtest(cfg, opt_df, bt_config, gate=gate)
            for k in (
                "profit_factor",
                "total_trades",
                "win_rate",
                "total_return_pct",
                "max_drawdown_pct",
            ):
                trial.set_user_attr(k, float(m.get(k, 0.0)))
            return objective_value(m, a.min_trades)

        study_gated = optuna.create_study(
            direction="maximize",
            sampler=TPESampler(seed=42),
            study_name=f"{a.strategy}_gate_GATED",
        )
        study_gated.optimize(objective_gated, n_trials=a.trials)

        baseline_oos = _run_backtest(
            apply_params(base_cfg, study.best_params), oos_df, bt_config, gate=None
        )
        gated_oos = _run_backtest(
            apply_params(base_cfg, study_gated.best_params),
            oos_df,
            bt_config,
            gate=gate,
        )

        rg_gated = rescoped_gate(study_gated, gated_oos)
        ok, delta = head_to_head_verdict(
            baseline_oos, gated_oos, a.delta_sharpe, rg_gated["pass"]
        )
        print(
            f"baseline OOS: sharpe={baseline_oos.get('sharpe_ratio', 0):.4f} "
            f"mdd={baseline_oos.get('max_drawdown_pct', 0):.2f}%"
        )
        print(
            f"gated    OOS: sharpe={gated_oos.get('sharpe_ratio', 0):.4f} "
            f"mdd={gated_oos.get('max_drawdown_pct', 0):.2f}%"
        )
        print(
            f">>> HEAD-TO-HEAD: {'PASS' if ok else 'FAIL'} "
            f"(Δsharpe={delta:.3f} vs δ={a.delta_sharpe} | "
            f"gated_rescoped_pass={rg_gated['pass']})"
        )
        return 0 if ok else 1

    return 0 if rg["pass"] else 1


class _CHInputs:
    """Pre-loaded ClickHouse-backed inputs for RegimeGate (T5)."""

    def __init__(self, vol_rows, event_rows, macro_map):
        # vol_rows: sorted list of (asof_naive_utc, regime_percentile)
        # event_rows: sorted list of (asof_naive_utc, impact_score)
        # macro_map: dict[date, MacroSnapshot]
        self._vol = vol_rows
        self._events = event_rows
        self._macro = macro_map

    def latest_vol_at(self, ts):
        import datetime as _dt  # noqa: F401

        ts_n = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
        cand = [r for r in self._vol if r[0] <= ts_n]
        return cand[-1] if cand else None

    def events_within(self, ts, window_min):
        import datetime as _dt

        ts_n = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
        lo = ts_n - _dt.timedelta(minutes=window_min)
        return [r for r in self._events if lo <= r[0] <= ts_n]

    def macro_for(self, date):
        snap = self._macro.get(date)
        return getattr(snap, "sp500_change_pct", None) if snap else None


def _build_gate(gate_cfg, df):
    """Pre-load vol_forecasts / event_scores / macro_history for the df window,
    construct a RegimeGate ready to use as engine `gate=`."""
    from shared.backtest.macro_history import fetch_macro_history
    from shared.db.client import get_clickhouse_client
    from shared.db.config import ClickHouseConfig
    from shared.strategy.gates.regime_gate import RegimeGate

    start = df["datetime"].min().to_pydatetime()
    end = df["datetime"].max().to_pydatetime()
    start_n = start.replace(tzinfo=None) if getattr(start, "tzinfo", None) else start
    end_n = end.replace(tzinfo=None) if getattr(end, "tzinfo", None) else end

    cli = get_clickhouse_client(ClickHouseConfig.from_env())
    vol = cli.execute(
        "SELECT asof, regime_percentile FROM kospi.vol_forecasts "
        "WHERE asof >= %(s)s AND asof < %(e)s ORDER BY asof",
        {"s": start_n, "e": end_n},
    )
    ev = cli.execute(
        "SELECT asof, impact_score FROM kospi.event_scores "
        "WHERE asof >= %(s)s AND asof < %(e)s ORDER BY asof",
        {"s": start_n, "e": end_n},
    )
    macro = fetch_macro_history(start.date(), end.date())
    return RegimeGate(gate_cfg, _CHInputs(vol, ev, macro))


if __name__ == "__main__":
    sys.exit(main())
