#!/usr/bin/env python
"""Optuna TPE optimizer for Phase 3 Setup A / Setup C parameters.

Follows the existing ``scripts/optimize_strategies.py`` pattern — search over
a small tunable surface per Setup, maximize EV in ticks.

Usage:
    python scripts/optimize_decision_engine.py \\
        --setup a \\
        --data data/kospi200f_1m_clean.csv \\
        --trials 50 \\
        --out results/optuna_phase3_a.json

Tunable ranges per spec Appendix A:
  Setup A:
    min_kr_gap_pct       [0.2, 0.6]
    retrace_min          [0.25, 0.40]
    retrace_max          [0.50, 0.60]
    stop_atr_mult        [1.0, 2.5]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

try:
    import optuna
except ImportError as exc:
    raise SystemExit(
        "optuna is not installed. `pip install optuna` (or use the"
        " project optimization extra)."
    ) from exc

from shared.backtest.decision_harness import BacktestDecisionHarness
from shared.backtest.market_context_replay import MarketContextReplay
from shared.decision.setups.event_reaction import (
    EventTradeTracker,
    SetupCConfig,
    SetupCEventReaction,
)
from shared.decision.setups.gap_reversion import SetupAConfig, SetupAGapReversion
from shared.execution.contract_spec import ContractSpecRegistry
from shared.macro.base import MacroSnapshot
from shared.risk.layer import RiskFilterLayer
from shared.risk.state import RiskStateSnapshot

logger = logging.getLogger(__name__)


def _objective_a(trial: optuna.Trial, df: pd.DataFrame, symbol: str, spec) -> float:
    cfg = SetupAConfig(
        min_kr_gap_pct=trial.suggest_float("min_kr_gap_pct", 0.2, 0.6),
        retrace_min=trial.suggest_float("retrace_min", 0.25, 0.40),
        retrace_max=trial.suggest_float("retrace_max", 0.50, 0.60),
        stop_atr_mult=trial.suggest_float("stop_atr_mult", 1.0, 2.5),
    )
    setup = SetupAGapReversion(config=cfg)
    return _run_and_score([setup], df, symbol, spec)


def _objective_c(trial: optuna.Trial, df: pd.DataFrame, symbol: str, spec) -> float:
    cfg = SetupCConfig(
        breakout_buffer_atr_mult=trial.suggest_float(
            "breakout_buffer_atr_mult", 0.2, 1.0
        ),
        target_atr_mult=trial.suggest_float("target_atr_mult", 1.5, 4.0),
        min_impact_tier=trial.suggest_int("min_impact_tier", 1, 3),
    )
    setup = SetupCEventReaction(config=cfg, tracker=EventTradeTracker())
    return _run_and_score([setup], df, symbol, spec)


def _run_and_score(setups, df, symbol, spec) -> float:
    replay = MarketContextReplay(
        df=df,
        symbol=symbol,
        macro_snapshot=MacroSnapshot(
            ts_ms=0,
            session="overnight_us_close",
            sp500_change_pct=0.0,
            nasdaq_change_pct=0.0,
        ),
        scheduled_events=[],
        contract_spec=spec,
    )
    harness = BacktestDecisionHarness(
        setups=setups,
        filter_layer=RiskFilterLayer(filters=[]),
        state=RiskStateSnapshot(),
        tick_size_points=spec.tick_size_points,
    )
    result = harness.run(replay)
    total_trades = sum(s.trades for s in result.per_setup.values())
    if total_trades < 10:
        return -1e6  # penalize param sets that barely trade
    total_ticks = sum(s.total_ticks for s in result.per_setup.values())
    return total_ticks / total_trades  # EV per trade in ticks


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    p = argparse.ArgumentParser()
    p.add_argument("--setup", choices=["a", "c"], required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--symbol", default="A05603")
    p.add_argument("--contract", default="kospi200_mini")
    p.add_argument("--trials", type=int, default=50)
    p.add_argument("--out", default="results/optuna_phase3.json")
    args = p.parse_args()

    df = pd.read_csv(args.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    registry = ContractSpecRegistry.from_yaml("config/execution.yaml")
    spec = registry.specs[args.contract]

    study = optuna.create_study(direction="maximize")
    objective = _objective_a if args.setup == "a" else _objective_c
    study.optimize(lambda t: objective(t, df, args.symbol, spec), n_trials=args.trials)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(
            {
                "setup": args.setup,
                "best_value": study.best_value,
                "best_params": study.best_params,
                "trials": [
                    {"number": t.number, "value": t.value, "params": t.params}
                    for t in study.trials
                ],
            },
            indent=2,
        )
    )
    logger.info("best_value=%.4f best_params=%s", study.best_value, study.best_params)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
