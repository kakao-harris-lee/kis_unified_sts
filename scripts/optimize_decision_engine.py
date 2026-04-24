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
import sys
from pathlib import Path

# Allow direct `python scripts/optimize_decision_engine.py` execution.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd  # noqa: E402

try:
    import optuna  # noqa: E402
except ImportError as exc:
    raise SystemExit(
        "optuna is not installed. `pip install optuna` (or use the"
        " project optimization extra)."
    ) from exc

from shared.backtest.decision_harness import BacktestDecisionHarness  # noqa: E402
from shared.backtest.macro_history import (  # noqa: E402
    fetch_macro_history,
    make_macro_provider,
)
from shared.backtest.market_context_replay import MarketContextReplay  # noqa: E402
from shared.decision.context import (  # noqa: E402
    ScheduledEvent,
    load_scheduled_events,
)
from shared.decision.setups.event_reaction import (  # noqa: E402
    EventTradeTracker,
    SetupCConfig,
    SetupCEventReaction,
)
from shared.decision.setups.gap_reversion import (  # noqa: E402
    SetupAConfig,
    SetupAGapReversion,
)
from shared.execution.contract_spec import ContractSpecRegistry  # noqa: E402
from shared.macro.base import MacroSnapshot  # noqa: E402
from shared.risk.config import FuturesRiskConfig, load_trading_windows  # noqa: E402
from shared.risk.layer import RiskFilterLayer  # noqa: E402
from shared.risk.state import RiskStateSnapshot  # noqa: E402

logger = logging.getLogger(__name__)


def _objective_a(
    trial: optuna.Trial,
    df: pd.DataFrame,
    symbol: str,
    spec,
    macro_provider,
    min_volume,
    filter_layer: RiskFilterLayer,
    scheduled_events: list[ScheduledEvent],
) -> float:
    cfg = SetupAConfig(
        min_kr_gap_pct=trial.suggest_float("min_kr_gap_pct", 0.2, 0.6),
        retrace_min=trial.suggest_float("retrace_min", 0.25, 0.40),
        retrace_max=trial.suggest_float("retrace_max", 0.50, 0.60),
        stop_atr_mult=trial.suggest_float("stop_atr_mult", 1.0, 2.5),
    )
    setup = SetupAGapReversion(config=cfg)
    return _run_and_score(
        [setup],
        df,
        symbol,
        spec,
        macro_provider,
        min_volume,
        filter_layer,
        scheduled_events,
    )


def _objective_c(
    trial: optuna.Trial,
    df: pd.DataFrame,
    symbol: str,
    spec,
    macro_provider,
    min_volume,
    filter_layer: RiskFilterLayer,
    scheduled_events: list[ScheduledEvent],
) -> float:
    cfg = SetupCConfig(
        # Keep the wide window_minutes (for KR-session overnight events —
        # default YAML value is 720 but SetupCConfig Python default is 15).
        window_minutes=720,
        breakout_buffer_atr_mult=trial.suggest_float(
            "breakout_buffer_atr_mult", 0.2, 1.0
        ),
        target_atr_mult=trial.suggest_float("target_atr_mult", 1.5, 4.0),
        min_impact_tier=trial.suggest_int("min_impact_tier", 1, 3),
    )
    setup = SetupCEventReaction(config=cfg, tracker=EventTradeTracker())
    return _run_and_score(
        [setup],
        df,
        symbol,
        spec,
        macro_provider,
        min_volume,
        filter_layer,
        scheduled_events,
    )


def _run_and_score(
    setups,
    df,
    symbol,
    spec,
    macro_provider,
    min_volume,
    filter_layer,
    scheduled_events,
) -> float:
    replay = MarketContextReplay(
        df=df,
        symbol=symbol,
        macro_snapshot=MacroSnapshot(
            ts_ms=0,
            session="overnight_us_close",
            sp500_change_pct=0.0,
            nasdaq_change_pct=0.0,
        ),
        scheduled_events=scheduled_events,
        contract_spec=spec,
        macro_provider=macro_provider,
        min_volume=min_volume,
    )
    harness = BacktestDecisionHarness(
        setups=setups,
        filter_layer=filter_layer,
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
    p.add_argument(
        "--skip-macro",
        action="store_true",
        help="Skip yfinance retroactive macro fetch (offline mode — "
        "Setup A will receive a neutral snapshot and never fire).",
    )
    p.add_argument(
        "--min-volume",
        type=int,
        default=30,
        help="Drop bars with volume below this threshold before replay "
        "(default 30 — tuned to strip phantom prints on KOSPI200 futures).",
    )
    p.add_argument(
        "--with-risk-filters",
        action="store_true",
        help="Wire the full 8-filter RiskFilterLayer during the search. "
        "Default is empty filters so the objective measures raw Setup EV "
        "unaffected by filter drag; filter tuning is a separate concern.",
    )
    p.add_argument(
        "--events",
        default="config/scheduled_events.yaml",
        help="Scheduled-events YAML (required for Setup C to fire). "
        "Set empty string to disable.",
    )
    args = p.parse_args()

    df = pd.read_csv(args.data)
    if "timestamp" not in df.columns and "datetime" in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    registry = ContractSpecRegistry.from_yaml("config/execution.yaml")
    spec = registry.specs[args.contract]

    macro_provider = None
    if not args.skip_macro:
        data_start = df["timestamp"].min().date()
        data_end = df["timestamp"].max().date()
        logger.info("fetching yfinance macro history for %s → %s", data_start, data_end)
        history = fetch_macro_history(data_start, data_end)
        logger.info("got %d daily macro snapshots", len(history))
        macro_provider = make_macro_provider(history)

    if args.with_risk_filters:
        risk_cfg = FuturesRiskConfig.from_yaml()
        trading_windows = load_trading_windows()
        filter_layer = RiskFilterLayer.from_config(
            risk_cfg, trading_windows=trading_windows
        )
        logger.info("using %d risk filters during search", len(filter_layer._filters))
    else:
        filter_layer = RiskFilterLayer(filters=[])

    scheduled_events: list[ScheduledEvent] = []
    if args.events:
        scheduled_events = load_scheduled_events(args.events)
        logger.info(
            "loaded %d scheduled events from %s", len(scheduled_events), args.events
        )

    study = optuna.create_study(direction="maximize")
    objective = _objective_a if args.setup == "a" else _objective_c
    study.optimize(
        lambda t: objective(
            t,
            df,
            args.symbol,
            spec,
            macro_provider,
            args.min_volume,
            filter_layer,
            scheduled_events,
        ),
        n_trials=args.trials,
    )

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
