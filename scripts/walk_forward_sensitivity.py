#!/usr/bin/env python
"""Parameter sensitivity walk-forward — Phase 3 corroborating gate (path 2).

Perturbs the top-3 Setup A parameters by ±20% and reruns the standard
walk-forward. Pass criteria (corroborating, not blocking by itself):
≥80% of perturbations retain OOS EV > 0.

Combine with bootstrap (path 1) and paper-data fold-in (path 3) for
final Phase 3 sign-off — see ``docs/runbooks/phase3-verification.md``.

Usage:
    python scripts/walk_forward_sensitivity.py \\
        --data data/kospi200f_1m_full.csv \\
        --is-months 4 --oos-months 2 \\
        --pct 0.20 \\
        --out results/phase3_sensitivity.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)

# Top 3 sensitive parameters per Optuna importance ranking
# (see docs/runbooks/phase3-verification.md §4 historical results).
_PERTURBED_FIELDS = ("min_sp500_gap_pct", "retrace_min", "stop_atr_mult")


def _perturb_combinations(base_a: dict, pct: float) -> list[dict]:
    """Generate (1 + 2*N) configurations: baseline + each field at ±pct.

    For N=3 fields, this produces 7 configs. Combined perturbations would
    be 3^3 = 27 — kept off by default to bound runtime.
    """
    configs: list[dict] = [dict(base_a)]
    for field in _PERTURBED_FIELDS:
        if field not in base_a:
            continue
        original = base_a[field]
        for delta in (-pct, +pct):
            perturbed = dict(base_a)
            perturbed[field] = original * (1.0 + delta)
            configs.append(perturbed)
    return configs


def run(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    # Lazy imports to keep --help fast.
    from scripts.walk_forward_phase3 import (
        _aggregate,
        _run_on_window,
        _split_folds,
    )
    from shared.backtest.harness_engine import ENGINE_VECTORBT_PARITY_FAILED
    from shared.backtest.macro_history import (
        fetch_macro_history,
        make_macro_provider,
    )
    from shared.decision.context import load_scheduled_events
    from shared.decision.setups.event_reaction import (
        EventTradeTracker,
        SetupCEventReaction,
    )
    from shared.decision.setups.gap_reversion import (
        SetupAConfig,
        SetupAGapReversion,
    )
    from shared.execution.contract_spec import ContractSpecRegistry
    from shared.risk.config import FuturesRiskConfig, load_trading_windows
    from shared.risk.layer import RiskFilterLayer

    df = pd.read_csv(args.data)
    if "timestamp" not in df.columns and "datetime" in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})

    folds = _split_folds(df, args.is_months, args.oos_months)
    if not folds:
        logger.error("no folds — data span insufficient")
        return 2

    if args.setup_a_params:
        import json as _json

        with open(args.setup_a_params) as f:
            optuna_a = _json.load(f)
        # Merge tuned best_params over defaults so untouched fields stay sane.
        base_cfg = SetupAConfig(**optuna_a["best_params"]).model_dump()
        logger.info(
            "loaded tuned Setup A params from %s as perturbation base",
            args.setup_a_params,
        )
    else:
        base_cfg = SetupAConfig().model_dump()
    perturbed = _perturb_combinations(base_cfg, args.pct)
    logger.info(
        "running %d configs (1 base + %d perturbations) × %d folds",
        len(perturbed),
        len(perturbed) - 1,
        len(folds),
    )

    registry = ContractSpecRegistry.from_yaml("config/execution.yaml")
    spec = registry.specs[args.contract]

    if args.with_risk_filters:
        risk_cfg = FuturesRiskConfig.from_yaml()
        layer = RiskFilterLayer.from_config(risk_cfg, load_trading_windows())
    else:
        layer = RiskFilterLayer(filters=[])

    ts_min = pd.to_datetime(df["timestamp"]).min().date()
    ts_max = pd.to_datetime(df["timestamp"]).max().date()
    macro_provider = (
        make_macro_provider(fetch_macro_history(start=ts_min, end=ts_max))
        if args.with_macro
        else None
    )
    scheduled = (
        load_scheduled_events("config/scheduled_events.yaml")
        if args.with_events
        else []
    )

    results = []
    parity_failed_windows = 0
    for i, raw_cfg in enumerate(perturbed):
        # Cast to SetupAConfig (Pydantic re-validates ranges).
        try:
            cfg = SetupAConfig(**raw_cfg)
        except Exception as exc:
            logger.warning("config %d invalid (%s); skipping", i, exc)
            continue
        setup_a = SetupAGapReversion(config=cfg)
        setup_c = SetupCEventReaction(tracker=EventTradeTracker())

        oos_evs = []
        for _is_df, oos_df in folds:
            try:
                oos_result, oos_engine = _run_on_window(
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
                    engine=args.engine,
                )
                parity_failed_windows += oos_engine == ENGINE_VECTORBT_PARITY_FAILED
                oos_evs.append(_aggregate(oos_result)["ev_ticks"])
            except Exception:
                logger.exception("config %d fold failed; skipping", i)
                continue

        median_oos = float(pd.Series(oos_evs).median()) if oos_evs else 0.0
        delta_label = "baseline" if i == 0 else f"perturb_{i}"
        results.append(
            {
                "label": delta_label,
                "config": raw_cfg,
                "oos_ev_per_fold": oos_evs,
                "oos_ev_median": median_oos,
                "oos_positive": median_oos > 0,
            }
        )
        logger.info(
            "config %d (%s): OOS EV median=%.3f over %d folds %s",
            i,
            delta_label,
            median_oos,
            len(oos_evs),
            "✅" if median_oos > 0 else "❌",
        )

    n_total = len(results)
    n_positive = sum(1 for r in results if r["oos_positive"])
    pct_positive = n_positive / n_total if n_total else 0.0
    passed = pct_positive >= args.min_pass_rate

    if parity_failed_windows:
        logger.warning(
            "%d window(s) fell back to the pure harness after a vectorbt "
            "parity failure — results are still harness(SoT)-accurate, but "
            "investigate (scripts/vbt_parity_report.py)",
            parity_failed_windows,
        )

    output = {
        "n_configs": n_total,
        "n_positive": n_positive,
        "pct_positive": pct_positive,
        "min_pass_rate": args.min_pass_rate,
        "perturbed_pct": args.pct,
        "perturbed_fields": list(_PERTURBED_FIELDS),
        "engine": args.engine,
        "parity_failed_windows": parity_failed_windows,
        "passed": passed,
        "configs": results,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2))

    logger.info("=" * 60)
    logger.info(
        "PHASE 3 SENSITIVITY GATE: %s (%d/%d=%d%% positive vs threshold %d%%)",
        "PASS" if passed else "FAIL",
        n_positive,
        n_total,
        int(100 * pct_positive),
        int(100 * args.min_pass_rate),
    )
    logger.info("written to %s", out)
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/kospi200f_1m_full.csv")
    parser.add_argument("--symbol", default="101S6000")
    parser.add_argument("--contract", default="kospi200_full")
    parser.add_argument("--is-months", type=int, default=4)
    parser.add_argument("--oos-months", type=int, default=2)
    parser.add_argument("--pct", type=float, default=0.20)
    parser.add_argument("--min-pass-rate", type=float, default=0.80)
    parser.add_argument("--min-volume", type=int, default=30)
    parser.add_argument("--with-macro", action="store_true")
    parser.add_argument("--with-events", action="store_true")
    parser.add_argument("--with-risk-filters", action="store_true")
    parser.add_argument(
        "--setup-a-params",
        type=str,
        default=None,
        help="Path to Optuna JSON; if given, perturbation centres on tuned params.",
    )
    parser.add_argument(
        "--engine",
        choices=["harness", "vectorbt"],
        default="harness",
        help="Backtest engine: 'harness' (default, BacktestDecisionHarness) "
        "or 'vectorbt' (opt-in VbtHarnessRunner — same harness plus a "
        "from_orders parity cross-check; requires the backtest extra: "
        'pip install -e ".[backtest]").',
    )
    parser.add_argument("--out", default="results/phase3_sensitivity.json")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
