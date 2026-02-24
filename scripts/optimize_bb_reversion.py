#!/usr/bin/env python3
"""bb_reversion 전략 파라미터 최적화 스크립트

대표 종목(삼성전자, SK하이닉스, 카카오 등)의 ClickHouse 분봉 데이터로
entry/exit 파라미터를 Optuna TPE로 탐색한다.

Usage:
    python scripts/optimize_bb_reversion.py --trials 100 --symbol 005930
    python scripts/optimize_bb_reversion.py --trials 50 --tier top
"""

from __future__ import annotations

import argparse
import copy
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from shared.backtest.config import BacktestConfig
from shared.backtest.engine import BacktestEngine
from shared.backtest.optimizer import ParamSpec, StrategyOptimizer
from shared.collector.historical.stock import (
    STOCK_UNIVERSE,
    load_stock_minute_from_clickhouse,
)
from shared.config.loader import ConfigLoader
from shared.strategy.registry import (
    EntryRegistry,
    ExitRegistry,
    SizerRegistry,
    StrategyFactory,
    register_builtin_components,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# 전략 레지스트리 초기화
register_builtin_components()


def load_data_for_symbol(code: str) -> pd.DataFrame | None:
    """ClickHouse에서 종목 분봉 데이터 로드"""
    try:
        df = load_stock_minute_from_clickhouse(code)
        if df is not None and len(df) >= 100:
            return df
    except Exception as e:
        logger.warning(f"Failed to load {code}: {e}")
    return None


def build_adapter_from_params(params: dict):
    """파라미터 dict로 BacktestStrategyAdapter 생성"""
    from shared.backtest.adapter import BacktestStrategyAdapter

    base_config = ConfigLoader.load_strategy("stock", "bb_reversion")
    cfg = copy.deepcopy(base_config)
    strategy_cfg = cfg.get("strategy", cfg)

    # entry params 업데이트
    entry_params = strategy_cfg["entry"]["params"]
    for k, v in params.items():
        if k.startswith("exit_"):
            continue
        if k in entry_params:
            entry_params[k] = v

    # exit params 업데이트
    exit_params = strategy_cfg["exit"]["params"]
    for k, v in params.items():
        if k.startswith("exit_"):
            real_key = k[5:]  # "exit_stop_loss_pct" → "stop_loss_pct"
            if real_key in exit_params:
                exit_params[real_key] = v

    # overshoot_trailing은 trailing_stop보다 타이트해야 함
    trailing = abs(exit_params.get("trailing_stop_pct", -0.03))
    overshoot = abs(exit_params.get("overshoot_trailing_pct", -0.02))
    if overshoot >= trailing:
        exit_params["overshoot_trailing_pct"] = -(trailing * 0.6)

    strategy = StrategyFactory.create(cfg)
    return BacktestStrategyAdapter(strategy, cfg)


def multi_symbol_objective(
    params: dict,
    datasets: dict[str, pd.DataFrame],
    backtest_config: BacktestConfig,
) -> float:
    """여러 종목에 대해 평균 Sharpe 반환"""
    sharpes = []
    for code, df in datasets.items():
        try:
            adapter = build_adapter_from_params(params)
            engine = BacktestEngine(adapter, backtest_config)
            result = engine.run(df.copy())
            metrics = result.to_metrics_dict()
            sharpe = metrics.get("sharpe_ratio", -10.0)
            # NaN/inf 방지
            if pd.isna(sharpe) or abs(sharpe) > 100:
                sharpe = -10.0
            sharpes.append(sharpe)
        except Exception as e:
            logger.debug(f"Trial failed for {code}: {e}")
            sharpes.append(-10.0)

    if not sharpes:
        return -10.0
    return sum(sharpes) / len(sharpes)


def run_optimization(
    symbols: list[dict],
    n_trials: int = 100,
    metric: str = "sharpe_ratio",
):
    """최적화 실행"""
    import optuna
    from optuna.samplers import TPESampler

    # 데이터 로드
    print(f"\n{'='*60}")
    print(f"Loading data for {len(symbols)} symbols...")
    datasets: dict[str, pd.DataFrame] = {}
    for s in symbols:
        code = s["code"]
        name = s["name"]
        df = load_data_for_symbol(code)
        if df is not None:
            datasets[code] = df
            print(f"  {code} ({name}): {len(df)} bars")
        else:
            print(f"  {code} ({name}): SKIPPED (no data)")

    if not datasets:
        print("ERROR: No data loaded!")
        return None

    print(f"\nLoaded {len(datasets)} symbols")
    backtest_config = BacktestConfig.stock(
        initial_capital=10_000_000,
        position_size_pct=10.0,
        max_positions=5,
    )

    # 파라미터 탐색 공간
    def objective(trial: optuna.Trial) -> float:
        params = {
            # Entry params
            "bb_period": trial.suggest_int("bb_period", 10, 30),
            "bb_std": trial.suggest_float("bb_std", 1.5, 3.0, step=0.1),
            "bb_touch_buffer": trial.suggest_float("bb_touch_buffer", 1.00, 1.03, step=0.005),
            "rsi_period": trial.suggest_int("rsi_period", 7, 21),
            "rsi_oversold": trial.suggest_int("rsi_oversold", 25, 45),
            # Exit params (prefixed with exit_)
            "exit_stop_loss_pct": trial.suggest_float("exit_stop_loss_pct", -0.05, -0.01, step=0.005),
            "exit_breakeven_threshold_pct": trial.suggest_float("exit_breakeven_threshold_pct", 0.01, 0.04, step=0.005),
            "exit_maximize_threshold_pct": trial.suggest_float("exit_maximize_threshold_pct", 0.02, 0.08, step=0.005),
            "exit_trailing_stop_pct": trial.suggest_float("exit_trailing_stop_pct", -0.05, -0.01, step=0.005),
        }
        try:
            return multi_symbol_objective(params, datasets, backtest_config)
        except Exception:
            return -10.0

    # Optuna study
    sampler = TPESampler(seed=42)
    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        study_name="bb_reversion_optimize",
    )

    print(f"\n{'='*60}")
    print(f"Starting optimization: {n_trials} trials")
    print(f"Symbols: {len(datasets)}, Metric: {metric}")
    print(f"{'='*60}\n")

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    # 결과 출력
    print(f"\n{'='*60}")
    print("OPTIMIZATION RESULTS")
    print(f"{'='*60}")
    print(f"Best {metric}: {study.best_value:.4f}")
    print(f"\nBest parameters:")
    for k, v in sorted(study.best_params.items()):
        print(f"  {k}: {v}")

    # 현재 파라미터와 비교
    print(f"\n{'='*60}")
    print("CURRENT vs BEST comparison")
    print(f"{'='*60}")
    current = {
        "bb_period": 20, "bb_std": 2.0, "bb_touch_buffer": 1.01,
        "rsi_period": 14, "rsi_oversold": 38,
        "exit_stop_loss_pct": -0.03, "exit_breakeven_threshold_pct": 0.02,
        "exit_maximize_threshold_pct": 0.03, "exit_trailing_stop_pct": -0.03,
    }
    current_sharpe = multi_symbol_objective(current, datasets, backtest_config)
    print(f"{'Parameter':<35} {'Current':>10} {'Best':>10}")
    print(f"{'-'*55}")
    for k in sorted(current.keys()):
        cv = current[k]
        bv = study.best_params.get(k, "N/A")
        changed = " *" if cv != bv else ""
        print(f"{k:<35} {cv:>10} {bv:>10}{changed}")
    print(f"{'-'*55}")
    print(f"{'Avg Sharpe':<35} {current_sharpe:>10.4f} {study.best_value:>10.4f}")

    # 파라미터 중요도
    try:
        importances = optuna.importance.get_param_importances(study)
        print(f"\n{'='*60}")
        print("PARAMETER IMPORTANCE")
        print(f"{'='*60}")
        for param, imp in sorted(importances.items(), key=lambda x: -x[1]):
            bar = "#" * int(imp * 40)
            print(f"  {param:<35} {imp:.3f} {bar}")
    except Exception:
        pass

    # Top 5 trials
    print(f"\n{'='*60}")
    print("TOP 5 TRIALS")
    print(f"{'='*60}")
    trials_sorted = sorted(study.trials, key=lambda t: t.value if t.value is not None else -999, reverse=True)
    for i, t in enumerate(trials_sorted[:5]):
        print(f"  #{i+1}: Sharpe={t.value:.4f} | {t.params}")

    return study


def main():
    parser = argparse.ArgumentParser(description="bb_reversion 파라미터 최적화")
    parser.add_argument("--trials", "-n", type=int, default=100, help="Trial count")
    parser.add_argument("--symbol", "-s", type=str, default=None, help="Single symbol code")
    parser.add_argument("--tier", "-t", type=str, default=None,
                        choices=["top", "mid", "bottom", "all"],
                        help="Stock tier")
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
        # 기본: 각 tier에서 대표 3종목 (총 9종목)
        top3 = [s for s in STOCK_UNIVERSE if s["tier"] == "top"][:3]
        mid3 = [s for s in STOCK_UNIVERSE if s["tier"] == "mid"][:3]
        bot3 = [s for s in STOCK_UNIVERSE if s["tier"] == "bottom"][:3]
        symbols = top3 + mid3 + bot3

    run_optimization(symbols, n_trials=args.trials)


if __name__ == "__main__":
    main()
