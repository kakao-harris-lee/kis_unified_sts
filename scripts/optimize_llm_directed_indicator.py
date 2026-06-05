#!/usr/bin/env python3
"""Optuna TPE parameter optimization for the ``llm_directed_indicator``
futures strategy (succeeds RL_mppo).

Why this is a dedicated script (not ``scripts/optimize_strategies.py``):
that script is stock-only and hardcodes
``ConfigLoader.load_strategy("stock", ...)``. Futures use a
single connected-future CSV (``101S6000``) and a different BacktestConfig.

Backtest contract (spec section 4(a)): ``BacktestStrategyAdapter`` does
NOT inject ``market_context``, so ``_map_llm_bias`` returns ``FLAT`` and
the strategy runs the indicators-only floor. Consequences:

  * ``bias_confidence_min`` has **zero** effect in backtest (the mask is
    FLAT regardless of confidence) → it is intentionally EXCLUDED from
    the search space. Tuning it would waste trials and pollute
    parameter-importance. Live LLM-bias behaviour is a separate concern
    validated in unit tests, not here.
  * What is tunable here = the directional indicator ensemble + the ATR
    exit safety net. The §6 activation bar is the RE-SCOPED gate
    (robust non-catastrophic floor, see ``_rescoped_gate``): it judges
    the *distribution* of valid trials, not a single best curve-fit.

The BacktestConfig mirrors ``cli/main.py::backtest_run`` for futures
exactly (``BacktestConfig.futures(initial_capital=10_000_000,
point_value=50_000)``) so results are directly comparable to the smoke
baseline recorded when the strategy merged (PR #261).

Usage:
    python scripts/optimize_llm_directed_indicator.py --trials 80
    python scripts/optimize_llm_directed_indicator.py --trials 120 \
        --data data/kospi200f_1m_ch_101S6000.csv --out config/best.yaml
"""

from __future__ import annotations

import argparse
import copy
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from shared.backtest.adapter import BacktestStrategyAdapter
from shared.backtest.config import BacktestConfig
from shared.backtest.engine import BacktestEngine
from shared.config.loader import ConfigLoader
from shared.strategy.registry import (
    StrategyFactory,
    register_builtin_components,
)
from shared.backtest.robust_gate import (
    rescoped_gate as _rescoped_gate,
    objective_value as _objective_value,
    SENTINEL as _SENTINEL,
    FLOOR_SHARPE as _FLOOR_SHARPE,
    FLOOR_PF as _FLOOR_PF,
    FLOOR_BASIN_FRAC as _FLOOR_BASIN_FRAC,
    OOS_MDD_MAX as _OOS_MDD_MAX,
    OOS_RET_MIN as _OOS_RET_MIN,
)
from shared.validation.cli_validators import validate_csv_file

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

register_builtin_components()

_ASSET = "futures"
_STRATEGY = "llm_directed_indicator"
_DEFAULT_DATA = "data/kospi200f_1m_ch_101S6000.csv"

# --- Legacy numeric gate (spec §6, pre-2026-05-17). Kept ONLY as an
# informational reference line. It judged the single best trial by raw
# Sharpe, which rewarded knife-edge curve-fits — superseded below.
_GATE_SHARPE = 1.0
_GATE_PF = 1.2

# --- Re-scoped §6 gate (2026-05-17, operator-approved): "robust
# non-catastrophic floor". The FLAT-bias path is a *safety floor*, not
# the alpha (the LLM directional bias is the alpha); so the bar is that
# the floor is broadly non-catastrophic, NOT that its best curve-fit is
# great. PASS requires ALL of (a)+(b)+(c):
#   (a) MEDIAN of valid trials (train) is non-catastrophic
#   (b) a broad basin (≥ FLOOR_BASIN_FRAC of valid trials clear (a))
#   (c) the selected config is non-catastrophic out-of-sample
# (a)+(b) are the methodological fix: they judge the *distribution*, so a
# single lucky trial can no longer pass the gate.
# Constants are now in shared/backtest/robust_gate.py (imported above).

# Same guardrails the CLI applies to futures CSVs.
_CSV_KW = {
    "reject_duplicate_datetime": True,
    "require_monotonic_datetime": True,
    "max_zero_volume_ratio": 0.95,
    "max_zero_volume_price_move_ratio": 0.20,
}


# ---------------------------------------------------------------------------
# Search space
# ---------------------------------------------------------------------------


def _suggest_params(trial) -> dict[str, Any]:
    """Sample the tunable surface.

    ``atr_*`` keys are routed into the nested ``exit.params.atr`` dict;
    everything else into ``entry.params``. See ``_apply_params``.
    """
    return {
        # --- entry ensemble (raw weighted sum vs eff_threshold) ---
        "w_momentum": trial.suggest_float("w_momentum", 0.10, 0.60, step=0.05),
        "w_trend": trial.suggest_float("w_trend", 0.10, 0.60, step=0.05),
        "w_volume": trial.suggest_float("w_volume", 0.10, 0.60, step=0.05),
        "entry_threshold": trial.suggest_float(
            "entry_threshold", 0.15, 0.55, step=0.05
        ),
        "vol_threshold_mult": trial.suggest_float(
            "vol_threshold_mult", 0.0, 1.2, step=0.1
        ),
        # --- per-family scorer shape (decisive-probe spike) ---
        "mom_rsi_pivot": trial.suggest_float("mom_rsi_pivot", 35.0, 60.0, step=2.5),
        "trend_spread_saturation": trial.suggest_float(
            "trend_spread_saturation", 20.0, 100.0, step=10.0
        ),
        "trend_adx_full": trial.suggest_float("trend_adx_full", 15.0, 60.0, step=5.0),
        "signal_cooldown_seconds": trial.suggest_int(
            "signal_cooldown_seconds", 60, 600, step=60
        ),
        "stop_loss_pct": trial.suggest_float("stop_loss_pct", 2.0, 5.0, step=0.5),
        # --- ATR exit safety net (nested into exit.params.atr) ---
        "atr_stop_atr_multiplier": trial.suggest_float(
            "atr_stop_atr_multiplier", 1.5, 4.0, step=0.5
        ),
        "atr_trail_activation_atr": trial.suggest_float(
            "atr_trail_activation_atr", 0.5, 2.0, step=0.5
        ),
        "atr_trail_atr_multiplier": trial.suggest_float(
            "atr_trail_atr_multiplier", 1.0, 3.0, step=0.5
        ),
    }


def _apply_params(base_cfg: dict, params: dict[str, Any]) -> dict:
    """Deep-copy ``base_cfg`` and overlay sampled params.

    ``atr_<key>`` → ``strategy.exit.params.atr[<key>]`` (nested composite
    exit config); all other keys → ``strategy.entry.params``.
    """
    cfg = copy.deepcopy(base_cfg)
    s = cfg["strategy"]
    entry_params = s["entry"]["params"]
    atr_params = s["exit"]["params"].setdefault("atr", {})
    if atr_params is None:  # YAML literal ``atr: {}`` may parse as None
        atr_params = {}
        s["exit"]["params"]["atr"] = atr_params

    for k, v in params.items():
        if k.startswith("atr_"):
            atr_params[k[4:]] = v
        else:
            entry_params[k] = v
    return cfg


# ---------------------------------------------------------------------------
# Backtest objective
# ---------------------------------------------------------------------------


def _run_backtest(cfg: dict, df, bt_config: BacktestConfig) -> dict[str, float]:
    strategy = StrategyFactory.create(cfg)
    adapter = BacktestStrategyAdapter(strategy, cfg)
    engine = BacktestEngine(adapter, bt_config)
    result = engine.run(df.copy())
    return result.to_metrics_dict()


def _fmt(m: dict[str, float]) -> str:
    return (
        f"Sharpe={m.get('sharpe_ratio', float('nan')):.4f} "
        f"PF={m.get('profit_factor', float('nan')):.4f} "
        f"trades={int(m.get('total_trades', 0))} "
        f"win={m.get('win_rate', 0):.1f}% "
        f"ret={m.get('total_return_pct', 0):.2f}% "
        f"MDD={m.get('max_drawdown_pct', 0):.2f}%"
    )


def _gate(m: dict[str, float]) -> bool:
    """Legacy numeric gate — informational reference only."""
    return (
        m.get("sharpe_ratio", -99) > _GATE_SHARPE
        and m.get("profit_factor", 0) > _GATE_PF
    )


def run_optimization(
    data_path: str,
    n_trials: int,
    out_path: str | None,
    timeout_s: int | None = None,
    holdout_split: str | None = None,
    min_trades: int = 50,
):
    import optuna
    import pandas as pd
    from optuna.samplers import TPESampler

    print(f"\n{'=' * 64}")
    print(f"Optuna optimization — {_STRATEGY} ({_ASSET})")
    print(f"{'=' * 64}")

    df = validate_csv_file(data_path, **_CSV_KW)
    print(
        f"Data: {data_path}  ({len(df)} bars, "
        f"{df['datetime'].min()} ~ {df['datetime'].max()})"
    )

    # --- Out-of-sample split: optimize on train, judge best on untouched
    # test. The §6 gate decision is only meaningful out-of-sample; a
    # single in-sample fit on 10 dims will overfit (TPE finds the curve).
    opt_df = df
    oos_df = None
    if holdout_split:
        split_ts = pd.Timestamp(holdout_split)
        series_tz = df["datetime"].dt.tz
        if series_tz is not None and split_ts.tzinfo is None:
            split_ts = split_ts.tz_localize(series_tz)
        opt_df = df[df["datetime"] < split_ts].reset_index(drop=True)
        oos_df = df[df["datetime"] >= split_ts].reset_index(drop=True)
        print(
            f"Holdout split @ {holdout_split}: "
            f"TRAIN={len(opt_df)} bars  OOS={len(oos_df)} bars"
        )
        if len(opt_df) < 500 or len(oos_df) < 500:
            print("ERROR: split leaves too few bars on one side.")
            return None

    # Mirror cli/main.py::backtest_run futures path exactly.
    base_cfg = ConfigLoader.load_strategy(_ASSET, _STRATEGY)
    bt_override = base_cfg.get("strategy", {}).get("backtest", {}) or {}
    bt_config = BacktestConfig.futures(
        initial_capital=bt_override.get("initial_capital", 10_000_000),
        point_value=bt_override.get("point_value", 50_000),
    )

    # --- Baseline (YAML defaults, no overrides) ---
    base_metrics = _run_backtest(base_cfg, opt_df, bt_config)
    base_sharpe = base_metrics.get("sharpe_ratio", float("nan"))
    base_pf = base_metrics.get("profit_factor", float("nan"))
    base_trades = int(base_metrics.get("total_trades", 0))
    print(
        f"\nBaseline (YAML defaults): Sharpe={base_sharpe:.4f} "
        f"PF={base_pf:.4f} trades={base_trades} "
        f"ret={base_metrics.get('total_return_pct', 0):.2f}% "
        f"MDD={base_metrics.get('max_drawdown_pct', 0):.2f}%"
    )

    def objective(trial: optuna.Trial) -> float:
        params = _suggest_params(trial)
        try:
            metrics = _run_backtest(_apply_params(base_cfg, params), opt_df, bt_config)
        except Exception as exc:  # noqa: BLE001 — a bad param combo must
            logger.debug("trial failed: %s", exc)  # not abort the study
            trial.set_user_attr("error", str(exc)[:200])
            return _SENTINEL
        trial.set_user_attr("profit_factor", float(metrics.get("profit_factor", 0.0)))
        trial.set_user_attr("total_trades", int(metrics.get("total_trades", 0)))
        trial.set_user_attr("win_rate", float(metrics.get("win_rate", 0.0)))
        trial.set_user_attr(
            "total_return_pct", float(metrics.get("total_return_pct", 0.0))
        )
        trial.set_user_attr(
            "max_drawdown_pct", float(metrics.get("max_drawdown_pct", 0.0))
        )
        return _objective_value(metrics, min_trades)

    study = optuna.create_study(
        direction="maximize",
        sampler=TPESampler(seed=42),
        study_name=f"{_STRATEGY}_optimize",
    )
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    cap = f", wall-cap={timeout_s}s" if timeout_s else ""
    print(
        f"\nTrials: {n_trials} (objective=sharpe_ratio, "
        f"min_trades={min_trades} floor; gate=re-scoped robust "
        f"non-catastrophic{cap})"
    )
    print(
        "Each backtest ≈ 170s on full 101S6000 — progress prints per "
        "completed trial.\n"
    )

    def _log_trial(st, tr):
        ua = tr.user_attrs
        print(
            f"[trial {tr.number}] sharpe={tr.value if tr.value is not None else float('nan'):.3f} "
            f"pf={ua.get('profit_factor', 0):.3f} "
            f"trades={ua.get('total_trades', 0)} "
            f"best={st.best_value:.3f}",
            flush=True,
        )

    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout_s,
        show_progress_bar=False,
        callbacks=[_log_trial],
    )

    # --- Results ---
    best = study.best_trial
    print(f"\n{'=' * 64}\nBEST TRIAL\n{'=' * 64}")
    print(
        f"Sharpe={best.value:.4f}  "
        f"PF={best.user_attrs.get('profit_factor', 0):.4f}  "
        f"trades={best.user_attrs.get('total_trades', 0)}  "
        f"win={best.user_attrs.get('win_rate', 0):.1f}%  "
        f"ret={best.user_attrs.get('total_return_pct', 0):.2f}%  "
        f"MDD={best.user_attrs.get('max_drawdown_pct', 0):.2f}%"
    )
    print("\nBest parameters:")
    for k, v in sorted(best.params.items()):
        print(f"  {k}: {v}")

    # Legacy numeric gate — REFERENCE ONLY (judged one trial by raw
    # Sharpe; rewarded knife-edge curve-fits). Superseded by the
    # re-scoped robust gate below.
    legacy_best = (
        best.value > _GATE_SHARPE
        and best.user_attrs.get("profit_factor", 0.0) > _GATE_PF
    )
    print(
        f"\n[reference only] legacy best-trial gate "
        f"(Sharpe>{_GATE_SHARPE} & PF>{_GATE_PF}): "
        f"{'pass' if legacy_best else 'fail'}  "
        f"— NOT the activation bar"
    )

    # --- Out-of-sample evaluation of the selected config (chosen WITHOUT
    # seeing oos_df → honest generalization estimate). Feeds gate (c).
    oos_m: dict[str, float] = {}
    if oos_df is not None:
        oos_cfg = _apply_params(base_cfg, best.params)
        try:
            oos_m = _run_backtest(oos_cfg, oos_df, bt_config)
        except Exception as exc:  # noqa: BLE001
            print(f"\nOOS backtest failed: {exc}")
            oos_m = {}
        print(f"\n{'=' * 64}\nSELECTED CONFIG: TRAIN → OOS\n{'=' * 64}")
        print(f"  TRAIN: {_fmt(best.user_attrs | {'sharpe_ratio': best.value})}")
        print(f"  OOS  : {_fmt(oos_m)}")

    # --- Re-scoped §6 gate (operator-approved 2026-05-17): robust
    # non-catastrophic floor. THIS is the activation bar.
    rg = _rescoped_gate(study, oos_m)
    ok = lambda x: "PASS ✅" if x else "FAIL ❌"  # noqa: E731
    print(
        f"\n{'=' * 64}\nRE-SCOPED §6 GATE — robust non-catastrophic "
        f"floor\n{'=' * 64}"
    )
    print(f"  valid trials (min-trades, non-degenerate): {rg['n_valid']}")
    print(
        f"  (a) MEDIAN valid TRAIN  Sharpe={rg['median_sharpe']:.3f} "
        f"PF={rg['median_pf']:.3f}  "
        f"(need ≥{_FLOOR_SHARPE}/≥{_FLOOR_PF})  {ok(rg['a'])}"
    )
    print(
        f"  (b) BASIN  {rg['basin_cleared']}/{rg['n_valid']} = "
        f"{rg['basin_frac'] * 100:.1f}% clear (a)  "
        f"(need ≥{_FLOOR_BASIN_FRAC * 100:.0f}%)  {ok(rg['b'])}"
    )
    if oos_df is not None:
        print(
            f"  (c) SELECTED cfg OOS  Sharpe="
            f"{oos_m.get('sharpe_ratio', float('nan')):.3f} "
            f"PF={oos_m.get('profit_factor', float('nan')):.3f} "
            f"MDD={oos_m.get('max_drawdown_pct', float('nan')):.1f}% "
            f"ret={oos_m.get('total_return_pct', float('nan')):.1f}%  "
            f"(need Sharpe≥{_FLOOR_SHARPE}/PF≥{_FLOOR_PF}/"
            f"MDD≤{_OOS_MDD_MAX}/ret≥{_OOS_RET_MIN})  {ok(rg['c'])}"
        )
    else:
        print(
            "  (c) SELECTED cfg OOS  — n/a (run with --holdout-split "
            "for the decision-grade bar)"
        )
    print(
        f"\n  >>> RE-SCOPED GATE: "
        f"{'PASS ✅ — floor is robustly non-catastrophic' if rg['pass'] else 'FAIL ❌ — DO NOT activate'}"
    )
    print(
        "  (a)+(b) judge the trial DISTRIBUTION, so a single lucky "
        "curve-fit can no longer pass. The FLAT floor is a safety net, "
        "not the alpha — this bar only asks it be broadly "
        "non-catastrophic."
    )

    try:
        importances = optuna.importance.get_param_importances(study)
        print(f"\n{'=' * 64}\nPARAMETER IMPORTANCE\n{'=' * 64}")
        for p, imp in sorted(importances.items(), key=lambda x: -x[1]):
            print(f"  {p:<28} {imp:.3f} {'#' * int(imp * 40)}")
    except Exception:
        pass

    print(f"\n{'=' * 64}\nTOP 5 TRIALS (Sharpe / PF / trades)\n{'=' * 64}")
    ranked = sorted(
        (t for t in study.trials if t.value is not None),
        key=lambda t: t.value,
        reverse=True,
    )
    for i, t in enumerate(ranked[:5], 1):
        ua = t.user_attrs
        print(
            f"  #{i}: Sharpe={t.value:.4f}  "
            f"PF={ua.get('profit_factor', 0):.3f}  "
            f"trades={ua.get('total_trades', 0)}  "
            f"win={ua.get('win_rate', 0):.1f}%"
        )

    if out_path:
        tuned = _apply_params(base_cfg, best.params)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as fh:
            yaml.safe_dump(tuned, fh, sort_keys=False, allow_unicode=True)
        print(f"\nBest-param config written → {out_path}")
        print(
            "  (artifact only — best-train config. Do NOT apply unless "
            "the RE-SCOPED gate PASSes; keep enabled: false regardless "
            "until operator activation approval.)"
        )

    return study


def main():
    ap = argparse.ArgumentParser(
        description="Optuna tuning — llm_directed_indicator (futures)"
    )
    ap.add_argument("--trials", "-n", type=int, default=80)
    ap.add_argument(
        "--timeout",
        "-T",
        type=int,
        default=None,
        help="Optuna wall-clock cap in seconds (study stops at "
        "n_trials OR timeout, whichever first)",
    )
    ap.add_argument("--data", "-d", type=str, default=_DEFAULT_DATA)
    ap.add_argument(
        "--holdout-split",
        "-H",
        type=str,
        default=None,
        help="YYYY-MM-DD: optimize on bars before this date, then "
        "evaluate the best params on the held-out bars on/after it "
        "(decision-grade out-of-sample gate)",
    )
    ap.add_argument(
        "--min-trades",
        "-M",
        type=int,
        default=50,
        help="Reject trials with fewer trades than this over the "
        "optimization window (kills the low-trade-count Sharpe "
        "degeneracy; default 50)",
    )
    ap.add_argument(
        "--out",
        "-o",
        type=str,
        default="reports/optuna/llm_directed_indicator_best.yaml",
    )
    args = ap.parse_args()
    run_optimization(
        args.data,
        args.trials,
        args.out,
        args.timeout,
        args.holdout_split,
        args.min_trades,
    )


if __name__ == "__main__":
    main()
