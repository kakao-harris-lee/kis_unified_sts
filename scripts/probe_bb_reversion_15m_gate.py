#!/usr/bin/env python3
"""Decisive probe: does `bb_reversion_15m` — the ONLY KOSPI200-futures
strategy that ever survived walk-forward (docs: Train 5.16 → Test 3.84,
−25.5% degradation, 2026-02) — clear the *re-scoped robust gate* on
current 101S6000 data?

Why this is the cheapest decisive test (operator-approved 2026-05-18):
every KOSPI200-futures intraday signal ever tried failed WF/counterfactual
(memory/futures_strategy_history.md); the lone exception is
`bb_reversion_15m` at 15-min resampling. If even the historical WF-winner
cannot clear the distribution-based robust gate on current data, the
"no robust futures intraday edge" prior is confirmed and option (a)
(new indicators / multi-timeframe) is dead. If it clears, one viable
futures signal exists and is worth productionizing.

Correctness note (critical): `mean_reversion.required_indicators` has NO
timeframe-suffixed keys, so the backtest adapter's MTF auto-derivation
does NOT resample. Running the registered backtest path on the 1-min CSV
would silently test a *1-minute* bb_reversion (the known catastrophic
FAIL: docs "1min WF Train 3.88 → Test −2.94, −175.8%"), NOT the 15-min
survivor. So this probe explicitly resamples 1m→15m OHLCV (exactly what
`timeframe: 15min` means) and feeds 15-min bars to the engine. The
adapter has no `strategy.timeframe`-keyed resample, so there is no
double-resample.

Gate logic (`_rescoped_gate`, `_objective_value`, `_run_backtest`) is
imported verbatim from `optimize_llm_directed_indicator` so the bar is
*identical* to the one that deprecated `llm_directed_indicator` — the
comparison is apples-to-apples.

Usage:
    python scripts/probe_bb_reversion_15m_gate.py \
        --data data/kospi200f_1m_ch_101S6000.csv \
        --trials 70 --holdout-split 2026-02-01 --min-trades 25
"""

from __future__ import annotations

# ruff: noqa: E402 — sys.path is set before the sibling/shared imports.
import argparse
import copy
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_SCRIPTS.parent))

import pandas as pd
from optimize_llm_directed_indicator import (  # noqa: E402 — path set above
    _CSV_KW,
    _fmt,
    _objective_value,
    _rescoped_gate,
    _run_backtest,
)

from shared.backtest.config import BacktestConfig  # noqa: E402
from shared.config.loader import ConfigLoader  # noqa: E402
from shared.validation.cli_validators import validate_csv_file  # noqa: E402

_ASSET = "futures"
_STRATEGY = "bb_reversion_15m"
_DEFAULT_DATA = "data/kospi200f_1m_ch_101S6000.csv"
_GATE_SHARPE, _GATE_PF = 1.0, 1.2  # legacy reference line only


def _resample_15m(df: pd.DataFrame) -> pd.DataFrame:
    """1-min OHLCV → 15-min OHLCV. Bins are right-open 15-min grid on the
    KST session clock; empty overnight bins dropped. This is exactly what
    `timeframe: 15min` denotes ("1분봉 데이터를 15분으로 리샘플링")."""
    d = df.copy()
    d["datetime"] = pd.to_datetime(d["datetime"])
    code = d["code"].iloc[0] if "code" in d.columns and len(d) else "101S6000"
    agg = (
        d.set_index("datetime")
        .resample("15min", label="left", closed="left")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )
    agg["code"] = code
    return agg


def _apply_params(base_cfg: dict, params: dict[str, Any]) -> dict:
    """`exit_<k>` → strategy.exit.params[k]; else → strategy.entry.params.
    `timeframe` forced to 'minute' — bars are ALREADY 15-min, so no code
    path must resample again (defensive; adapter doesn't anyway)."""
    cfg = copy.deepcopy(base_cfg)
    s = cfg["strategy"]
    s["timeframe"] = "minute"
    entry_p = s["entry"]["params"]
    exit_p = s["exit"]["params"]
    for k, v in params.items():
        if k.startswith("exit_"):
            exit_p[k[5:]] = v
        else:
            entry_p[k] = v
    return cfg


def _suggest_params(trial) -> dict[str, Any]:
    """ENTRY-ONLY search (mean_reversion). The three_stage exit is left
    at the YAML's WF-validated values — this is faithful to how
    bb_reversion_15m was actually walk-forward-validated (entry-tuned;
    param-importance was bb_touch_buffer 58% / rsi_oversold 30% /
    min_bb_bandwidth 5% — exit barely mattered) AND avoids three_stage's
    internal constraint (maximize_threshold_pct > breakeven_threshold_pct)
    that an unconstrained exit search violates. Also minimizes overfit
    surface, consistent with the re-scoped-gate philosophy. Ranges
    bracket the documented WF-optimal (bb 43/1.4/1.06, rsi 16/45/83,
    bw 0.003)."""
    return {
        "bb_period": trial.suggest_int("bb_period", 20, 60, step=2),
        "bb_std": trial.suggest_float("bb_std", 1.2, 2.6, step=0.1),
        "bb_touch_buffer": trial.suggest_float(
            "bb_touch_buffer", 1.00, 1.10, step=0.005
        ),
        "rsi_period": trial.suggest_int("rsi_period", 8, 24, step=1),
        "rsi_oversold": trial.suggest_int("rsi_oversold", 30, 50, step=1),
        "rsi_overbought": trial.suggest_int("rsi_overbought", 70, 90, step=1),
        "min_bb_bandwidth": trial.suggest_float(
            "min_bb_bandwidth", 0.001, 0.010, step=0.001
        ),
    }


def run_probe(data_path, n_trials, holdout_split, min_trades, out_path):
    import optuna
    from optuna.samplers import TPESampler

    print(f"\n{'=' * 70}\nDECISIVE PROBE — bb_reversion_15m vs re-scoped "
          f"robust gate\n{'=' * 70}")
    df1 = validate_csv_file(data_path, **_CSV_KW)
    df = _resample_15m(df1)
    print(f"1m bars: {len(df1)}  →  15m bars: {len(df)}  "
          f"({df['datetime'].min()} ~ {df['datetime'].max()})")

    base_cfg = ConfigLoader.load_strategy(_ASSET, _STRATEGY)
    bt = BacktestConfig.futures(initial_capital=10_000_000, point_value=50_000)

    opt_df, oos_df = df, None
    if holdout_split:
        ts = pd.Timestamp(holdout_split)
        if df["datetime"].dt.tz is not None and ts.tzinfo is None:
            ts = ts.tz_localize(df["datetime"].dt.tz)
        opt_df = df[df["datetime"] < ts].reset_index(drop=True)
        oos_df = df[df["datetime"] >= ts].reset_index(drop=True)
        print(f"Holdout @ {holdout_split}: TRAIN={len(opt_df)} 15m bars  "
              f"OOS={len(oos_df)} 15m bars")
        if len(opt_df) < 200 or len(oos_df) < 100:
            print("ERROR: too few 15m bars on one side of the split.")
            return None

    base_m = _run_backtest(base_cfg, opt_df, bt)
    print(f"\nBaseline (WF-optimal YAML params, 15m): {_fmt(base_m)}")

    def objective(trial):
        p = _suggest_params(trial)
        try:
            m = _run_backtest(_apply_params(base_cfg, p), opt_df, bt)
        except Exception as exc:  # noqa: BLE001
            trial.set_user_attr("error", str(exc)[:200])
            return -10.0
        for k in ("profit_factor", "total_trades", "win_rate",
                  "total_return_pct", "max_drawdown_pct"):
            trial.set_user_attr(k, float(m.get(k, 0.0)))
        return _objective_value(m, min_trades)

    study = optuna.create_study(
        direction="maximize", sampler=TPESampler(seed=42),
        study_name="bb_reversion_15m_probe",
    )
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    print(f"\nTrials: {n_trials}  min_trades={min_trades}  "
          f"objective=sharpe (re-scoped robust gate)\n")

    def _log(st, tr):
        ua = tr.user_attrs
        v = tr.value if tr.value is not None else float("nan")
        print(f"[trial {tr.number}] sharpe={v:.3f} "
              f"pf={ua.get('profit_factor', 0):.3f} "
              f"trades={ua.get('total_trades', 0)} "
              f"best={st.best_value:.3f}", flush=True)

    study.optimize(objective, n_trials=n_trials, show_progress_bar=False,
                   callbacks=[_log])

    best = study.best_trial
    print(f"\n{'=' * 70}\nBEST TRIAL\n{'=' * 70}")
    print(_fmt(best.user_attrs | {"sharpe_ratio": best.value}))
    print("params: " + ", ".join(f"{k}={v}" for k, v in
                                  sorted(best.params.items())))

    oos_m: dict[str, float] = {}
    if oos_df is not None:
        try:
            oos_m = _run_backtest(_apply_params(base_cfg, best.params),
                                  oos_df, bt)
        except Exception as exc:  # noqa: BLE001
            print(f"OOS backtest failed: {exc}")
        print(f"\nSELECTED cfg  TRAIN: "
              f"{_fmt(best.user_attrs | {'sharpe_ratio': best.value})}")
        print(f"SELECTED cfg  OOS  : {_fmt(oos_m)}")

    rg = _rescoped_gate(study, oos_m)
    ok = lambda x: "PASS ✅" if x else "FAIL ❌"  # noqa: E731
    print(f"\n{'=' * 70}\nRE-SCOPED ROBUST GATE — bb_reversion_15m"
          f"\n{'=' * 70}")
    print(f"  valid trials: {rg['n_valid']}")
    print(f"  (a) MEDIAN valid TRAIN  Sharpe={rg['median_sharpe']:.3f} "
          f"PF={rg['median_pf']:.3f}  {ok(rg['a'])}")
    print(f"  (b) BASIN  {rg['basin_cleared']}/{rg['n_valid']} = "
          f"{rg['basin_frac'] * 100:.1f}%  {ok(rg['b'])}")
    print(f"  (c) SELECTED cfg OOS non-catastrophic  {ok(rg['c'])}")
    print(f"\n  >>> RE-SCOPED GATE: "
          f"{'PASS ✅ — a viable futures signal EXISTS' if rg['pass'] else 'FAIL ❌'}")
    if rg["pass"]:
        print("      → bb_reversion_15m clears the robust bar on current "
              "data.\n      Scope productionizing it (15m resample wiring "
              "+ paper).")
    else:
        print("      → even the lone historical WF-survivor fails the "
              "robust gate\n      on current data. The 'no robust "
              "KOSPI200-futures intraday edge'\n      prior is CONFIRMED "
              "— option (a) is dead. Stop intraday-signal\n      R&D or "
              "pivot to already-persisted non-price information.")
    print(f"\n  [reference] legacy best-trial gate "
          f"(Sharpe>{_GATE_SHARPE}&PF>{_GATE_PF}): "
          f"{'pass' if (best.value > _GATE_SHARPE and best.user_attrs.get('profit_factor', 0) > _GATE_PF) else 'fail'} "
          f"— NOT the bar")

    if out_path:
        import yaml
        tuned = _apply_params(base_cfg, best.params)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as fh:
            yaml.safe_dump(tuned, fh, sort_keys=False, allow_unicode=True)
        print(f"\nBest-param config → {out_path} (artifact; apply only if "
              "gate PASSED, and keep enabled:false pending operator)")
    return study


def main():
    ap = argparse.ArgumentParser(description="bb_reversion_15m robust-gate probe")
    ap.add_argument("--data", "-d", default=_DEFAULT_DATA)
    ap.add_argument("--trials", "-n", type=int, default=70)
    ap.add_argument("--holdout-split", "-H", default="2026-02-01")
    ap.add_argument("--min-trades", "-M", type=int, default=25,
                    help="15m bars → far fewer trades than 1m; historical "
                         "WF Test had 34 (≥30 = significance boundary)")
    ap.add_argument("--out", "-o",
                    default="reports/optuna/bb_reversion_15m_probe.yaml")
    a = ap.parse_args()
    run_probe(a.data, a.trials, a.holdout_split, a.min_trades, a.out)


if __name__ == "__main__":
    main()
