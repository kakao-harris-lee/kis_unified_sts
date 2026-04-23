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

from shared.backtest.decision_harness import (  # noqa: E402
    BacktestDecisionHarness,
    HarnessResult,
)
from shared.backtest.macro_history import (  # noqa: E402
    fetch_macro_history,
    make_macro_provider,
)
from shared.backtest.market_context_replay import MarketContextReplay  # noqa: E402
from shared.decision.setups.event_reaction import (  # noqa: E402
    EventTradeTracker,
    SetupCEventReaction,
)
from shared.decision.setups.gap_reversion import SetupAGapReversion  # noqa: E402
from shared.execution.contract_spec import ContractSpecRegistry  # noqa: E402
from shared.macro.base import MacroSnapshot  # noqa: E402
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


def _run_on_window(
    df: pd.DataFrame,
    symbol: str,
    macro: MacroSnapshot | None,
    spec,
    setup_a: SetupAGapReversion,
    setup_c: SetupCEventReaction,
    macro_provider=None,
) -> HarnessResult:
    replay = MarketContextReplay(
        df=df,
        symbol=symbol,
        macro_snapshot=macro,
        scheduled_events=[],
        contract_spec=spec,
        macro_provider=macro_provider,
    )
    harness = BacktestDecisionHarness(
        setups=[setup_a, setup_c],
        filter_layer=RiskFilterLayer(filters=[]),
        state=RiskStateSnapshot(),
        tick_size_points=spec.tick_size_points,
    )
    return harness.run(replay)


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
    # Default params from YAML; Optuna tuning is a follow-up wire-in via
    # scripts/optimize_decision_engine.py. Phase 3 gate measures raw default
    # performance first; tuning is optional if default fails.
    setup_a = SetupAGapReversion()
    setup_c = SetupCEventReaction(tracker=EventTradeTracker())

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
        is_result = _run_on_window(
            is_df, args.symbol, macro, spec, setup_a, setup_c, macro_provider
        )
        oos_result = _run_on_window(
            oos_df, args.symbol, macro, spec, setup_a, setup_c, macro_provider
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
        )
        results.append(fr)
        logger.info("fold %d: %s", idx, asdict(fr))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps([asdict(r) for r in results], indent=2, default=str)
    )
    logger.info("wrote %d fold results → %s", len(results), args.out)

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
    return run(p.parse_args())


if __name__ == "__main__":
    import sys

    sys.exit(main())
