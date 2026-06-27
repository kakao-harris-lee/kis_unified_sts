#!/usr/bin/env python3
"""3개 주식 전략 파라미터 최적화 스크립트

trend_pullback, momentum_breakout, vr_composite 전략의
entry/exit 파라미터를 Optuna TPE로 탐색한다.

Usage:
    python scripts/optimize_strategies.py --strategy trend_pullback --trials 100
    python scripts/optimize_strategies.py --strategy momentum_breakout --trials 50 --tier top
    python scripts/optimize_strategies.py --strategy vr_composite --trials 100 --tier all
"""

from __future__ import annotations

import argparse
import copy
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from shared.backtest.config import BacktestConfig
from shared.backtest.engine import BacktestEngine
from shared.collector.historical.stock import (
    STOCK_UNIVERSE,
    load_stock_minute_from_parquet,
)
from shared.config.loader import ConfigLoader
from shared.strategy.registry import (
    StrategyFactory,
    register_builtin_components,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

register_builtin_components()


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def load_minute_data(code: str) -> pd.DataFrame | None:
    """Parquet에서 1분봉 로드."""
    try:
        df = load_stock_minute_from_parquet(code)
        if df is not None and len(df) >= 100:
            return df
    except Exception as e:
        logger.warning(f"Failed to load minute data {code}: {e}")
    return None


def load_daily_data(code: str) -> pd.DataFrame | None:
    """Parquet에서 일봉 로드."""
    try:
        from shared.backtest.daily_adapter import load_stock_daily_from_parquet

        df = load_stock_daily_from_parquet(code)
        if df is not None and len(df) >= 100:
            return df
    except Exception as e:
        logger.warning(f"Failed to load daily data {code}: {e}")
    return None


# ---------------------------------------------------------------------------
# Adapter builders
# ---------------------------------------------------------------------------


def build_minute_adapter(strategy_name: str, params: dict):
    """1분봉 전략용 BacktestStrategyAdapter 생성."""
    from shared.backtest.adapter import BacktestStrategyAdapter

    cfg = copy.deepcopy(ConfigLoader.load_strategy("stock", strategy_name))
    strategy_cfg = cfg.get("strategy", cfg)

    entry_params = strategy_cfg["entry"]["params"]
    exit_params = strategy_cfg["exit"]["params"]

    for k, v in params.items():
        if k.startswith("exit_"):
            real_key = k[5:]
            if real_key in exit_params:
                exit_params[real_key] = v
        elif k in entry_params:
            entry_params[k] = v

    strategy = StrategyFactory.create(cfg)
    return BacktestStrategyAdapter(strategy, cfg)


def build_daily_adapter(strategy_name: str, params: dict):
    """일봉 전략용 DailyBacktestAdapter 생성."""
    from shared.backtest.daily_adapter import DailyBacktestAdapter

    cfg = copy.deepcopy(ConfigLoader.load_strategy("stock", strategy_name))
    strategy_cfg = cfg.get("strategy", cfg)

    entry_params = strategy_cfg["entry"]["params"]
    exit_params = strategy_cfg["exit"]["params"]

    for k, v in params.items():
        if k.startswith("exit_"):
            real_key = k[5:]
            if real_key in exit_params:
                exit_params[real_key] = v
        elif k in entry_params:
            entry_params[k] = v

    strategy = StrategyFactory.create(cfg)
    return DailyBacktestAdapter(strategy, cfg)


# ---------------------------------------------------------------------------
# Objective
# ---------------------------------------------------------------------------


def multi_symbol_objective(
    params: dict,
    datasets: dict[str, pd.DataFrame],
    backtest_config: BacktestConfig,
    strategy_name: str,
    is_daily: bool,
) -> float:
    """여러 종목 평균 Sharpe 반환."""
    sharpes = []
    for code, df in datasets.items():
        try:
            if is_daily:
                adapter = build_daily_adapter(strategy_name, params)
                adapter.prescan_data(df)
            else:
                adapter = build_minute_adapter(strategy_name, params)

            engine = BacktestEngine(adapter, backtest_config)
            result = engine.run(df.copy())
            metrics = result.to_metrics_dict()
            sharpe = metrics.get("sharpe_ratio", -10.0)
            if pd.isna(sharpe) or abs(sharpe) > 100:
                sharpe = -10.0
            sharpes.append(sharpe)
        except Exception as e:
            logger.debug(f"Trial failed for {code}: {e}")
            sharpes.append(-10.0)

    return sum(sharpes) / len(sharpes) if sharpes else -10.0


# ---------------------------------------------------------------------------
# Search spaces per strategy
# ---------------------------------------------------------------------------


def define_trend_pullback_params(trial):
    return {
        "bb_touch_buffer": trial.suggest_float(
            "bb_touch_buffer", 1.000, 1.020, step=0.005
        ),
        "rsi_oversold": trial.suggest_int("rsi_oversold", 30, 48),
        "stop_atr_multiplier": trial.suggest_float(
            "stop_atr_multiplier", 2.0, 4.0, step=0.5
        ),
        "signal_cooldown_seconds": trial.suggest_int(
            "signal_cooldown_seconds", 120, 360, step=60
        ),
        "exit_stop_atr_multiplier": trial.suggest_float(
            "exit_stop_atr_multiplier", 2.0, 4.0, step=0.5
        ),
        "exit_trail_activation_atr": trial.suggest_float(
            "exit_trail_activation_atr", 0.5, 2.0, step=0.5
        ),
        "exit_trail_atr_multiplier": trial.suggest_float(
            "exit_trail_atr_multiplier", 1.0, 2.5, step=0.5
        ),
    }


def define_momentum_breakout_params(trial):
    return {
        "breakout_buffer_pct": trial.suggest_float(
            "breakout_buffer_pct", 0.03, 0.15, step=0.01
        ),
        "rvol_threshold": trial.suggest_float("rvol_threshold", 1.0, 2.0, step=0.1),
        "accumulation_score_min": trial.suggest_int(
            "accumulation_score_min", 30, 70, step=5
        ),
        "stop_atr_multiplier": trial.suggest_float(
            "stop_atr_multiplier", 1.0, 3.0, step=0.5
        ),
        "signal_cooldown_seconds": trial.suggest_int(
            "signal_cooldown_seconds", 180, 720, step=60
        ),
        "exit_stop_atr_multiplier": trial.suggest_float(
            "exit_stop_atr_multiplier", 1.0, 3.0, step=0.5
        ),
        "exit_trail_activation_atr": trial.suggest_float(
            "exit_trail_activation_atr", 0.5, 2.0, step=0.5
        ),
        "exit_trail_atr_multiplier": trial.suggest_float(
            "exit_trail_atr_multiplier", 0.5, 2.5, step=0.5
        ),
        "exit_max_hold_days": trial.suggest_int("exit_max_hold_days", 3, 10),
    }


def define_vr_composite_params(trial):
    return {
        "vr_bottom_threshold": trial.suggest_float(
            "vr_bottom_threshold", 50.0, 85.0, step=5.0
        ),
        "vr_depression_threshold": trial.suggest_float(
            "vr_depression_threshold", 70.0, 100.0, step=5.0
        ),
        "rsi_weak_oversold": trial.suggest_float(
            "rsi_weak_oversold", 35.0, 50.0, step=2.5
        ),
        "signal_cooldown_days": trial.suggest_int("signal_cooldown_days", 1, 5),
        "exit_vr_overheat_threshold": trial.suggest_float(
            "exit_vr_overheat_threshold", 250.0, 450.0, step=25.0
        ),
        "exit_vr_extreme_overheat_threshold": trial.suggest_float(
            "exit_vr_extreme_overheat_threshold", 350.0, 550.0, step=25.0
        ),
        "exit_rsi_overbought": trial.suggest_float(
            "exit_rsi_overbought", 65.0, 85.0, step=5.0
        ),
        "exit_hard_stop_pct": trial.suggest_float(
            "exit_hard_stop_pct", -0.08, -0.04, step=0.01
        ),
    }


PARAM_DEFINERS = {
    "trend_pullback": define_trend_pullback_params,
    "momentum_breakout": define_momentum_breakout_params,
    "vr_composite": define_vr_composite_params,
}

DAILY_STRATEGIES = {"vr_composite"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_optimization(
    strategy_name: str,
    symbols: list[dict],
    n_trials: int = 100,
):
    import optuna
    from optuna.samplers import TPESampler

    is_daily = strategy_name in DAILY_STRATEGIES
    loader = load_daily_data if is_daily else load_minute_data

    print(f"\n{'='*60}")
    print(
        f"Loading {'daily' if is_daily else 'minute'} data for {len(symbols)} symbols..."
    )
    datasets: dict[str, pd.DataFrame] = {}
    for s in symbols:
        code, name = s["code"], s["name"]
        df = loader(code)
        if df is not None:
            datasets[code] = df
            print(f"  {code} ({name}): {len(df)} bars")
        else:
            print(f"  {code} ({name}): SKIPPED")

    if not datasets:
        print("ERROR: No data loaded!")
        return None

    print(f"\nLoaded {len(datasets)} symbols")

    if is_daily:
        backtest_config = BacktestConfig.stock(
            initial_capital=100_000_000,
            position_size_pct=10.0,
            max_positions=5,
        )
    else:
        backtest_config = BacktestConfig.stock(
            initial_capital=10_000_000,
            position_size_pct=10.0,
            max_positions=5,
        )

    # Load strategy-specific risk config from YAML
    strategy_config = ConfigLoader.load_strategy("stock", strategy_name)
    bt_override = strategy_config.get("strategy", {}).get("backtest", {})
    if "risk" in bt_override:
        from shared.backtest.config import RiskConfig

        backtest_config.risk = RiskConfig.from_dict(bt_override["risk"])

    param_definer = PARAM_DEFINERS[strategy_name]

    def objective(trial: optuna.Trial) -> float:
        params = param_definer(trial)
        try:
            return multi_symbol_objective(
                params,
                datasets,
                backtest_config,
                strategy_name,
                is_daily,
            )
        except Exception:
            return -10.0

    sampler = TPESampler(seed=42)
    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        study_name=f"{strategy_name}_optimize",
    )

    print(f"\n{'='*60}")
    print(f"Strategy: {strategy_name} ({'daily' if is_daily else '1min'})")
    print(f"Trials: {n_trials}, Symbols: {len(datasets)}")
    print(f"{'='*60}\n")

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    # --- Results ---
    print(f"\n{'='*60}")
    print("OPTIMIZATION RESULTS")
    print(f"{'='*60}")
    print(f"Best Sharpe: {study.best_value:.4f}")
    print("\nBest parameters:")
    for k, v in sorted(study.best_params.items()):
        print(f"  {k}: {v}")

    # Current baseline
    print(f"\n{'='*60}")
    print("CURRENT vs BEST")
    print(f"{'='*60}")
    current_params = param_definer(
        type(
            "FakeTrial",
            (),
            {
                "suggest_float": lambda _self, name, *_args, **_kwargs: _get_current(
                    strategy_name, name
                ),
                "suggest_int": lambda _self, name, *_args, **_kwargs: _get_current(
                    strategy_name, name
                ),
            },
        )()
    )
    current_sharpe = multi_symbol_objective(
        current_params,
        datasets,
        backtest_config,
        strategy_name,
        is_daily,
    )
    print(f"{'Parameter':<40} {'Current':>10} {'Best':>10}")
    print(f"{'-'*60}")
    for k in sorted(current_params.keys()):
        cv = current_params[k]
        bv = study.best_params.get(k, "N/A")
        changed = " *" if cv != bv else ""
        print(f"{k:<40} {cv:>10} {bv:>10}{changed}")
    print(f"{'-'*60}")
    print(f"{'Avg Sharpe':<40} {current_sharpe:>10.4f} {study.best_value:>10.4f}")

    # Parameter importance
    try:
        importances = optuna.importance.get_param_importances(study)
        print(f"\n{'='*60}")
        print("PARAMETER IMPORTANCE")
        print(f"{'='*60}")
        for param, imp in sorted(importances.items(), key=lambda x: -x[1]):
            bar = "#" * int(imp * 40)
            print(f"  {param:<40} {imp:.3f} {bar}")
    except Exception:
        pass

    # Top 5 trials
    print(f"\n{'='*60}")
    print("TOP 5 TRIALS")
    print(f"{'='*60}")
    trials_sorted = sorted(
        study.trials,
        key=lambda t: t.value if t.value is not None else -999,
        reverse=True,
    )
    for i, t in enumerate(trials_sorted[:5]):
        print(f"  #{i+1}: Sharpe={t.value:.4f} | {t.params}")

    return study


def _get_current(strategy_name: str, param_name: str):
    """YAML에서 현재 파라미터 값 읽기."""
    cfg = ConfigLoader.load_strategy("stock", strategy_name)
    strategy_cfg = cfg.get("strategy", cfg)
    entry_params = strategy_cfg["entry"]["params"]
    exit_params = strategy_cfg["exit"]["params"]

    if param_name.startswith("exit_"):
        real_key = param_name[5:]
        return exit_params.get(real_key, 0)
    return entry_params.get(param_name, 0)


def main():
    parser = argparse.ArgumentParser(description="주식 전략 파라미터 최적화")
    parser.add_argument(
        "--strategy",
        "-s",
        required=True,
        choices=["trend_pullback", "momentum_breakout", "vr_composite"],
    )
    parser.add_argument("--trials", "-n", type=int, default=100)
    parser.add_argument(
        "--tier",
        "-t",
        type=str,
        default=None,
        choices=["top", "mid", "bottom", "all"],
    )
    parser.add_argument("--symbol", type=str, default=None)
    args = parser.parse_args()

    if args.symbol:
        symbols = [s for s in STOCK_UNIVERSE if s["code"] == args.symbol]
        if not symbols:
            symbols = [{"code": args.symbol, "name": args.symbol, "tier": "unknown"}]
    elif args.tier:
        if args.tier == "all":
            symbols = STOCK_UNIVERSE
        else:
            symbols = [s for s in STOCK_UNIVERSE if s["tier"] == args.tier]
    else:
        # Default: 3 per tier (9 symbols)
        top3 = [s for s in STOCK_UNIVERSE if s["tier"] == "top"][:3]
        mid3 = [s for s in STOCK_UNIVERSE if s["tier"] == "mid"][:3]
        bot3 = [s for s in STOCK_UNIVERSE if s["tier"] == "bottom"][:3]
        symbols = top3 + mid3 + bot3

    run_optimization(args.strategy, symbols, n_trials=args.trials)


if __name__ == "__main__":
    main()
