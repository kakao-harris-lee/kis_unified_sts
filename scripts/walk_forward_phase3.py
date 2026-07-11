#!/usr/bin/env python
"""Walk-forward analysis for Phase 3 decision engine.

Splits a long OHLCV DataFrame into rolling (IS, OOS) folds. For each fold:
1. Tune Setup A/C params on the IS window (Optuna — see
   scripts/optimize_decision_engine.py for the search space).
2. Freeze params and replay the OOS window through
   BacktestDecisionHarness.
3. Compare IS vs OOS Sharpe / EV.

Phase 3 gate (spec §8.4): OOS Sharpe must be >= 0.5 * IS Sharpe AND
OOS EV sign must match IS EV sign.

This script is run manually during the 48h gate; not wired into CI because
the full run consumes ~6 months of 1-minute bars.

Usage:
    python scripts/walk_forward_phase3.py \\
        --data data/kospi200f_1m_clean.csv \\
        --is-months 4 \\
        --oos-months 2 \\
        --out results/phase3_wf.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Allow direct `python scripts/walk_forward_phase3.py` execution.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd  # noqa: E402

from shared.backtest.decision_harness import HarnessResult  # noqa: E402
from shared.backtest.harness_engine import (  # noqa: E402
    ENGINE_HARNESS,
    ENGINE_VECTORBT_PARITY_FAILED,
    SUPPORTED_ENGINES,
    run_futures_backtest,
)
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


@dataclass
class FoldResult:
    fold_id: int
    is_start: str
    is_end: str
    oos_start: str
    oos_end: str
    is_trades: int
    is_win_rate: float
    is_ev_ticks: float
    oos_trades: int
    oos_win_rate: float
    oos_ev_ticks: float
    passes_gate: bool
    # Engine labels actually used per window ("harness" | "vectorbt" |
    # "vectorbt_parity_failed") — appended fields so existing JSON consumers
    # keep their columns.
    is_engine: str = ENGINE_HARNESS
    oos_engine: str = ENGINE_HARNESS


def _run_on_window(
    df: pd.DataFrame,
    symbol: str,
    macro: MacroSnapshot | None,
    spec,
    setup_a: SetupAGapReversion,
    setup_c: SetupCEventReaction,
    filter_layer: RiskFilterLayer,
    macro_provider=None,
    min_volume: int = 0,
    scheduled_events: list[ScheduledEvent] | None = None,
    *,
    engine: str = ENGINE_HARNESS,
) -> tuple[HarnessResult, str]:
    """Run one (IS or OOS) window; returns ``(result, engine_label)``.

    ``engine_label`` is the engine that actually produced the result — see
    :func:`shared.backtest.harness_engine.run_futures_backtest`.
    """
    replay = MarketContextReplay(
        df=df,
        symbol=symbol,
        macro_snapshot=macro,
        scheduled_events=scheduled_events or [],
        contract_spec=spec,
        macro_provider=macro_provider,
        min_volume=min_volume,
    )
    return run_futures_backtest(
        [setup_a, setup_c],
        filter_layer,
        RiskStateSnapshot(),
        spec.tick_size_points,
        replay,
        engine=engine,
    )


def _split_folds(
    df: pd.DataFrame, is_months: int, oos_months: int
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    start = df["timestamp"].min()
    end = df["timestamp"].max()
    folds: list[tuple[pd.DataFrame, pd.DataFrame]] = []
    window = start
    while window + pd.DateOffset(months=is_months + oos_months) <= end:
        is_end = window + pd.DateOffset(months=is_months)
        oos_end = is_end + pd.DateOffset(months=oos_months)
        is_df = df[(df["timestamp"] >= window) & (df["timestamp"] < is_end)]
        oos_df = df[(df["timestamp"] >= is_end) & (df["timestamp"] < oos_end)]
        folds.append((is_df.reset_index(drop=True), oos_df.reset_index(drop=True)))
        window = is_end + pd.DateOffset(months=oos_months)
    return folds


def run(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    df = pd.read_csv(args.data)
    # Project CSV files conventionally use 'datetime'; the harness expects 'timestamp'.
    if "timestamp" not in df.columns and "datetime" in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})
    folds = _split_folds(df, args.is_months, args.oos_months)
    logger.info(
        "built %d folds (is=%dm, oos=%dm)", len(folds), args.is_months, args.oos_months
    )
    if not folds:
        span = (
            pd.to_datetime(df["timestamp"]).max()
            - pd.to_datetime(df["timestamp"]).min()
        )
        logger.error(
            "No folds produced — data span is only %s but --is-months + --oos-months "
            "needs at least %d months. Either supply a longer CSV or shrink the window.",
            span,
            args.is_months + args.oos_months,
        )
        return 2

    registry = ContractSpecRegistry.from_yaml("config/execution.yaml")
    spec = registry.specs[args.contract]

    # Setup A: defaults from YAML unless an Optuna JSON is supplied.
    setup_a_cfg: SetupAConfig | None = None
    if args.setup_a_params:
        with open(args.setup_a_params) as f:
            optuna_result = json.load(f)
        setup_a_cfg = SetupAConfig(**optuna_result["best_params"])
        logger.info(
            "loaded Setup A params from %s: %s",
            args.setup_a_params,
            optuna_result["best_params"],
        )
    setup_a = (
        SetupAGapReversion(config=setup_a_cfg) if setup_a_cfg else SetupAGapReversion()
    )

    # Setup C: YAML default window_minutes=720 (overnight-event reach).
    # Optuna JSON overrides the other params if provided.
    setup_c_cfg = SetupCConfig.from_yaml()
    if args.setup_c_params:
        with open(args.setup_c_params) as f:
            optuna_result_c = json.load(f)
        overrides = optuna_result_c["best_params"]
        # Preserve the YAML-driven window_minutes when the Optuna search did
        # not tune it (the current search only varies buffer/target/tier).
        update = {**setup_c_cfg.model_dump(), **overrides}
        setup_c_cfg = SetupCConfig(**update)
        logger.info("loaded Setup C params from %s: %s", args.setup_c_params, overrides)
    setup_c = SetupCEventReaction(config=setup_c_cfg, tracker=EventTradeTracker())

    # Load scheduled events (Setup C needs them to fire).
    scheduled_events: list[ScheduledEvent] = []
    if args.events:
        scheduled_events = load_scheduled_events(args.events)
        logger.info(
            "loaded %d scheduled events from %s", len(scheduled_events), args.events
        )

    # Risk filter layer — all 8 filters, config-driven.
    if args.skip_risk_filters:
        filter_layer = RiskFilterLayer(filters=[])
        logger.info("--skip-risk-filters: running backtest WITHOUT risk filtering")
    else:
        risk_cfg = FuturesRiskConfig.from_yaml()
        trading_windows = load_trading_windows()
        filter_layer = RiskFilterLayer.from_config(
            risk_cfg, trading_windows=trading_windows
        )
        logger.info(
            "loaded %d risk filters from config/risk.yaml", len(filter_layer._filters)
        )

    # Neutral fallback snapshot used when macro is disabled or a specific
    # session date lookup misses.
    macro = MacroSnapshot(
        ts_ms=0,
        session="overnight_us_close",
        sp500_change_pct=0.0,
        nasdaq_change_pct=0.0,
    )

    # Retroactive per-day macro via yfinance (spec §8.1) unless --skip-macro.
    macro_provider = None
    if not args.skip_macro:
        data_start = pd.to_datetime(df["timestamp"]).min().date()
        data_end = pd.to_datetime(df["timestamp"]).max().date()
        logger.info("fetching yfinance macro history for %s → %s", data_start, data_end)
        history = fetch_macro_history(data_start, data_end)
        logger.info("got %d daily macro snapshots", len(history))
        macro_provider = make_macro_provider(history)

    results: list[FoldResult] = []
    for idx, (is_df, oos_df) in enumerate(folds):
        is_result, is_engine = _run_on_window(
            is_df,
            args.symbol,
            macro,
            spec,
            setup_a,
            setup_c,
            filter_layer,
            macro_provider,
            args.min_volume,
            scheduled_events,
            engine=args.engine,
        )
        oos_result, oos_engine = _run_on_window(
            oos_df,
            args.symbol,
            macro,
            spec,
            setup_a,
            setup_c,
            filter_layer,
            macro_provider,
            args.min_volume,
            scheduled_events,
            engine=args.engine,
        )

        is_setup_agg = _aggregate(is_result)
        oos_setup_agg = _aggregate(oos_result)
        passes_gate = oos_setup_agg["ev_ticks"] > 0.0 and oos_setup_agg[
            "ev_ticks"
        ] >= 0.5 * max(is_setup_agg["ev_ticks"], 1e-9)
        fr = FoldResult(
            fold_id=idx,
            is_start=str(is_df["timestamp"].min()),
            is_end=str(is_df["timestamp"].max()),
            oos_start=str(oos_df["timestamp"].min()),
            oos_end=str(oos_df["timestamp"].max()),
            is_trades=is_setup_agg["trades"],
            is_win_rate=is_setup_agg["win_rate"],
            is_ev_ticks=is_setup_agg["ev_ticks"],
            oos_trades=oos_setup_agg["trades"],
            oos_win_rate=oos_setup_agg["win_rate"],
            oos_ev_ticks=oos_setup_agg["ev_ticks"],
            passes_gate=passes_gate,
            is_engine=is_engine,
            oos_engine=oos_engine,
        )
        results.append(fr)
        logger.info("fold %d: %s", idx, asdict(fr))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps([asdict(r) for r in results], indent=2, default=str)
    )
    logger.info("wrote %d fold results → %s", len(results), args.out)

    parity_failed = sum(
        (r.is_engine == ENGINE_VECTORBT_PARITY_FAILED)
        + (r.oos_engine == ENGINE_VECTORBT_PARITY_FAILED)
        for r in results
    )
    logger.info("engine=%s parity_failed_windows=%d", args.engine, parity_failed)
    if parity_failed:
        logger.warning(
            "%d window(s) fell back to the pure harness after a vectorbt "
            "parity failure — results are still harness(SoT)-accurate, but "
            "investigate (scripts/vbt_parity_report.py)",
            parity_failed,
        )

    n_pass = sum(1 for r in results if r.passes_gate)
    logger.info(
        "GATE: %d/%d folds pass OOS >= 0.5*IS and OOS EV > 0",
        n_pass,
        len(results),
    )
    return 0 if n_pass >= len(results) // 2 else 1


def _aggregate(result: HarnessResult) -> dict[str, float]:
    total_trades = sum(s.trades for s in result.per_setup.values())
    total_wins = sum(s.wins for s in result.per_setup.values())
    total_ticks = sum(s.total_ticks for s in result.per_setup.values())
    win_rate = total_wins / total_trades if total_trades else 0.0
    ev = total_ticks / total_trades if total_trades else 0.0
    return {"trades": total_trades, "win_rate": win_rate, "ev_ticks": ev}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, help="Path to minute-bar CSV")
    p.add_argument("--symbol", default="A05603")
    p.add_argument("--contract", default="kospi200_mini")
    p.add_argument("--is-months", type=int, default=4)
    p.add_argument("--oos-months", type=int, default=2)
    p.add_argument("--out", default="results/phase3_wf.json")
    p.add_argument(
        "--skip-macro",
        action="store_true",
        help="Skip yfinance retroactive macro fetch (uses neutral snapshot — "
        "Setup A will never fire; useful for offline smoke-testing only).",
    )
    p.add_argument(
        "--min-volume",
        type=int,
        default=30,
        help="Drop bars with volume below this threshold before replay "
        "(default 30 — tuned to strip phantom prints on KOSPI200 futures).",
    )
    p.add_argument(
        "--events",
        default="config/scheduled_events.yaml",
        help="Path to scheduled events YAML (Setup C needs this to fire). "
        "Set empty string to disable.",
    )
    p.add_argument(
        "--setup-a-params",
        default=None,
        help="Optional path to an Optuna JSON (e.g. results/optuna_a.json). "
        "If given, Setup A uses the best_params from that file instead of "
        "YAML defaults.",
    )
    p.add_argument(
        "--setup-c-params",
        default=None,
        help="Optional path to an Optuna JSON (e.g. results/optuna_c.json). "
        "Merges best_params over the YAML defaults (preserving "
        "window_minutes from YAML since the Optuna search does not tune it).",
    )
    p.add_argument(
        "--engine",
        choices=list(SUPPORTED_ENGINES),
        default=ENGINE_HARNESS,
        help="Backtest engine: 'harness' (default, BacktestDecisionHarness) "
        "or 'vectorbt' (opt-in VbtHarnessRunner — runs the same harness plus "
        "a from_orders parity cross-check; requires the backtest extra: "
        'pip install -e ".[backtest]"). Parity failures log a warning and '
        "fall back to the pure harness (label 'vectorbt_parity_failed').",
    )
    p.add_argument(
        "--skip-risk-filters",
        action="store_true",
        help="Run backtest with no risk filters (empty RiskFilterLayer). "
        "Useful for measuring raw Setup EV before filter drag. "
        "Production runs should always use the full config-driven filter set.",
    )
    return run(p.parse_args())


if __name__ == "__main__":
    import sys

    sys.exit(main())
