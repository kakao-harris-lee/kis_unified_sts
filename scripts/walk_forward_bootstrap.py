#!/usr/bin/env python
"""Bootstrap walk-forward — Phase 3 alternative gate driver.

Replaces the ≥12-month calendar-wait dependency with a Politis-Romano
stationary block bootstrap on the existing ~14-month clean dataset.

Pipeline
--------
1. Load the same data source as ``walk_forward_phase3.py``.
2. Generate ``--n-samples`` bootstrap-resampled time series via
   :func:`shared.backtest.bootstrap.stationary_block_bootstrap`.
3. Run the standard walk-forward on each bootstrap (delegating to the
   plumbing in ``walk_forward_phase3.py``).
4. Aggregate per-fold OOS EV across all bootstrap iterations and emit:
   - 5%, 50%, 95% quantiles of OOS EV
   - per-setup OOS EV distributions
   - new gate decision: 5% quantile > 0 AND median ≥ 0.5 × IS EV median

The new gate does not replace Task 20 (paper) — it gives Phase 3
provisional sign-off on backtest evidence alone, with paper data in
Phase 4 providing the final confirmation.

Usage
-----

    python scripts/walk_forward_bootstrap.py \\
        --data data/kospi200f_1m_clean.csv \\
        --is-months 4 --oos-months 2 \\
        --n-samples 200 --seed 42 \\
        --out results/phase3_bootstrap.json

Computation: ~1-2 minutes per sample × 200 samples = 3-7 hours.
Use --n-samples 20 for smoke test (~20 minutes).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow direct execution from a checkout root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Reuse the existing walk-forward fold runner — no need to duplicate the
# Setup/RiskFilter wiring.
from scripts.walk_forward_phase3 import _split_folds  # noqa: E402
from shared.backtest.bootstrap import stationary_block_bootstrap  # noqa: E402

logger = logging.getLogger(__name__)


def _aggregate_distribution(values: list[float]) -> dict[str, float]:
    if not values:
        return {"n": 0, "mean": 0.0, "p05": 0.0, "p50": 0.0, "p95": 0.0}
    arr = np.asarray(values, dtype=float)
    return {
        "n": int(len(arr)),
        "mean": float(np.mean(arr)),
        "p05": float(np.quantile(arr, 0.05)),
        "p50": float(np.quantile(arr, 0.50)),
        "p95": float(np.quantile(arr, 0.95)),
    }


def _evaluate_bootstrap_gate(
    is_ev_distribution: list[float],
    oos_ev_distribution: list[float],
    half_is_threshold: float = 0.5,
) -> dict:
    """Phase 3 alternative gate.

    Pass criteria (replacing the calendar-12-month frequentist gate):
      1. OOS EV 5% quantile > 0  (i.e. ≥95% of bootstrap iterations
         produced a non-negative-edge OOS).
      2. OOS EV median ≥ ``half_is_threshold`` × IS EV median.
    """
    is_stats = _aggregate_distribution(is_ev_distribution)
    oos_stats = _aggregate_distribution(oos_ev_distribution)

    rule1_pass = oos_stats["p05"] > 0
    rule2_pass = oos_stats["p50"] >= half_is_threshold * is_stats["p50"]
    overall_pass = rule1_pass and rule2_pass

    return {
        "is_ev": is_stats,
        "oos_ev": oos_stats,
        "rule1_oos_p05_positive": {
            "threshold": 0.0,
            "actual": oos_stats["p05"],
            "passed": rule1_pass,
        },
        "rule2_oos_median_vs_is": {
            "threshold": half_is_threshold * is_stats["p50"],
            "actual": oos_stats["p50"],
            "ratio": (oos_stats["p50"] / is_stats["p50"]) if is_stats["p50"] else 0.0,
            "passed": rule2_pass,
        },
        "passes_gate": overall_pass,
    }


def _run_one_bootstrap(
    sample_idx: int,
    sample_df: pd.DataFrame,
    is_months: int,
    oos_months: int,
    args: argparse.Namespace,
) -> tuple[list[float], list[float]]:
    """Run walk-forward folds on one bootstrap sample.

    Returns ``(is_ev_per_fold, oos_ev_per_fold)``. Empty lists when the
    sample has insufficient span for any fold.
    """
    # Lazy imports — defer heavy modules until we actually need them.
    import json as _json

    from scripts.walk_forward_phase3 import _aggregate, _run_on_window
    from shared.backtest.macro_history import fetch_macro_history, make_macro_provider
    from shared.decision.context import load_scheduled_events
    from shared.decision.setups.event_reaction import (
        EventTradeTracker,
        SetupCConfig,
        SetupCEventReaction,
    )
    from shared.decision.setups.gap_reversion import (
        SetupAConfig,
        SetupAGapReversion,
    )
    from shared.execution.contract_spec import ContractSpecRegistry
    from shared.risk.config import FuturesRiskConfig, load_trading_windows
    from shared.risk.layer import RiskFilterLayer

    folds = _split_folds(sample_df, is_months, oos_months)
    if not folds:
        return [], []

    registry = ContractSpecRegistry.from_yaml("config/execution.yaml")
    spec = registry.specs[args.contract]

    # Optional tuned-params overrides — mirror walk_forward_phase3.run.
    setup_a_cfg: SetupAConfig | None = None
    if args.setup_a_params:
        with open(args.setup_a_params) as f:
            optuna_a = _json.load(f)
        setup_a_cfg = SetupAConfig(**optuna_a["best_params"])
    setup_a = (
        SetupAGapReversion(config=setup_a_cfg) if setup_a_cfg else SetupAGapReversion()
    )

    setup_c_tracker = EventTradeTracker()
    setup_c_cfg: SetupCConfig | None = None
    if args.setup_c_params:
        with open(args.setup_c_params) as f:
            optuna_c = _json.load(f)
        setup_c_cfg = SetupCConfig(**optuna_c["best_params"])
    setup_c = (
        SetupCEventReaction(config=setup_c_cfg, tracker=setup_c_tracker)
        if setup_c_cfg
        else SetupCEventReaction(tracker=setup_c_tracker)
    )

    # Risk filter: optional — same flag the standard walk-forward uses
    if args.with_risk_filters:
        risk_cfg = FuturesRiskConfig.from_yaml()
        windows = load_trading_windows()
        layer = RiskFilterLayer.from_config(risk_cfg, windows)
    else:
        layer = RiskFilterLayer(filters=[])

    if args.with_macro:
        ts_min = pd.to_datetime(sample_df["timestamp"]).min().date()
        ts_max = pd.to_datetime(sample_df["timestamp"]).max().date()
        macro_provider = make_macro_provider(
            fetch_macro_history(start=ts_min, end=ts_max)
        )
    else:
        macro_provider = None
    scheduled = (
        load_scheduled_events("config/scheduled_events.yaml")
        if args.with_events
        else []
    )

    is_ev_list: list[float] = []
    oos_ev_list: list[float] = []
    for fold_id, (is_df, oos_df) in enumerate(folds):
        try:
            is_result = _run_on_window(
                is_df,
                args.symbol,
                None,
                spec,
                setup_a,
                setup_c,
                layer,
                macro_provider=macro_provider,
                min_volume=args.min_volume,
                scheduled_events=scheduled,
            )
            oos_result = _run_on_window(
                oos_df,
                args.symbol,
                None,
                spec,
                setup_a,
                setup_c,
                layer,
                macro_provider=macro_provider,
                min_volume=args.min_volume,
                scheduled_events=scheduled,
            )
        except Exception:
            logger.exception(
                "bootstrap %d fold %d failed; skipping", sample_idx, fold_id
            )
            continue

        is_summary = _aggregate(is_result)
        oos_summary = _aggregate(oos_result)
        is_ev_list.append(is_summary["ev_ticks"])
        oos_ev_list.append(oos_summary["ev_ticks"])

    return is_ev_list, oos_ev_list


def run(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    df = pd.read_csv(args.data)
    if "timestamp" not in df.columns and "datetime" in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})

    logger.info(
        "loaded %d bars from %s; generating %d bootstrap samples (mean block %d min, seed=%s)",
        len(df),
        args.data,
        args.n_samples,
        args.mean_block_minutes,
        args.seed,
    )
    samples = stationary_block_bootstrap(
        df,
        n_samples=args.n_samples,
        mean_block_minutes=args.mean_block_minutes,
        seed=args.seed,
    )

    all_is_ev: list[float] = []
    all_oos_ev: list[float] = []
    for i, sample_df in enumerate(samples):
        is_evs, oos_evs = _run_one_bootstrap(
            sample_idx=i,
            sample_df=sample_df,
            is_months=args.is_months,
            oos_months=args.oos_months,
            args=args,
        )
        all_is_ev.extend(is_evs)
        all_oos_ev.extend(oos_evs)
        if (i + 1) % max(1, args.n_samples // 10) == 0:
            logger.info(
                "progress %d/%d samples; cumulative folds: IS=%d OOS=%d",
                i + 1,
                args.n_samples,
                len(all_is_ev),
                len(all_oos_ev),
            )

    if not all_oos_ev:
        logger.error(
            "No OOS folds produced across %d bootstrap samples — check "
            "is/oos months vs. data span.",
            args.n_samples,
        )
        return 2

    gate_result = _evaluate_bootstrap_gate(all_is_ev, all_oos_ev)

    output = {
        "n_samples": args.n_samples,
        "mean_block_minutes": args.mean_block_minutes,
        "seed": args.seed,
        "is_months": args.is_months,
        "oos_months": args.oos_months,
        "gate": gate_result,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))

    logger.info("=" * 60)
    logger.info(
        "PHASE 3 BOOTSTRAP GATE: %s", "PASS" if gate_result["passes_gate"] else "FAIL"
    )
    logger.info(
        "  IS EV     median=%.3f p05=%.3f p95=%.3f",
        gate_result["is_ev"]["p50"],
        gate_result["is_ev"]["p05"],
        gate_result["is_ev"]["p95"],
    )
    logger.info(
        "  OOS EV    median=%.3f p05=%.3f p95=%.3f",
        gate_result["oos_ev"]["p50"],
        gate_result["oos_ev"]["p05"],
        gate_result["oos_ev"]["p95"],
    )
    logger.info(
        "  Rule 1 (OOS p05 > 0):       %s",
        "PASS" if gate_result["rule1_oos_p05_positive"]["passed"] else "FAIL",
    )
    logger.info(
        "  Rule 2 (OOS median ≥ 0.5×IS): %s",
        "PASS" if gate_result["rule2_oos_median_vs_is"]["passed"] else "FAIL",
    )
    logger.info("written to %s", out_path)
    return 0 if gate_result["passes_gate"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        default="data/kospi200f_1m_clean.csv",
        help="OHLCV CSV with monotonic 1-minute timestamps",
    )
    parser.add_argument("--symbol", default="101S6000")
    parser.add_argument("--contract", default="kospi200_full")
    parser.add_argument("--is-months", type=int, default=4)
    parser.add_argument("--oos-months", type=int, default=2)
    parser.add_argument(
        "--n-samples",
        type=int,
        default=200,
        help="Number of bootstrap iterations (200 = ~3-7 hours)",
    )
    parser.add_argument(
        "--mean-block-minutes",
        type=int,
        default=5 * 24 * 60,
        help="Mean block length in minutes (default ~5 trading days)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-volume", type=int, default=30)
    parser.add_argument(
        "--with-macro",
        action="store_true",
        help="Use yfinance macro provider for Setup A",
    )
    parser.add_argument(
        "--with-events", action="store_true", help="Load scheduled events for Setup C"
    )
    parser.add_argument(
        "--with-risk-filters",
        action="store_true",
        help="Apply 8-filter RiskFilterLayer (default: skip)",
    )
    parser.add_argument(
        "--setup-a-params",
        type=str,
        default=None,
        help="Path to Optuna JSON with tuned Setup A params (best_params section).",
    )
    parser.add_argument(
        "--setup-c-params",
        type=str,
        default=None,
        help="Path to Optuna JSON with tuned Setup C params (best_params section).",
    )
    parser.add_argument("--out", default="results/phase3_bootstrap.json")
    args = parser.parse_args()

    return run(args)


if __name__ == "__main__":
    sys.exit(main())
