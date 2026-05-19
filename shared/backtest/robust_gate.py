"""Re-scoped robust non-catastrophic gate (spec 2026-05-16 §6 / 2026-05-19 §7).

Single DRY home shared by scripts/optimize_llm_directed_indicator.py and
(Task 4) scripts/gate_futures_strategy.py. Logic moved verbatim 2026-05-19;
behavior must not change.
"""
from __future__ import annotations

import statistics as _st

SENTINEL = -10.0
FLOOR_SHARPE = 0.0
FLOOR_PF = 1.0
FLOOR_BASIN_FRAC = 0.25
OOS_MDD_MAX = 25.0
OOS_RET_MIN = 0.0


def rescoped_gate(study, oos_m: dict[str, float]) -> dict[str, object]:
    """Re-scoped §6 gate: robust non-catastrophic floor.

    Judges the *distribution* of valid trials (so one lucky curve-fit
    cannot pass) plus an out-of-sample non-catastrophic check on the
    selected config.

    A "valid" trial = one that cleared the min-trades floor and was not
    NaN/pathological, i.e. its objective is not the sentinel. The trial
    objective IS its train Sharpe; train PF is in user_attrs.
    """
    valid = [
        t for t in study.trials
        if t.value is not None and t.value > SENTINEL + 0.1
    ]
    n = len(valid)
    sh = [t.value for t in valid]
    pf = [
        float(t.user_attrs.get("profit_factor", 0.0))
        for t in valid
    ]
    pf_finite = [p for p in pf if p == p and p != float("inf")]

    med_s = _st.median(sh) if sh else float("nan")
    med_pf = _st.median(pf_finite) if pf_finite else float("nan")
    a = (n > 0) and med_s >= FLOOR_SHARPE and med_pf >= FLOOR_PF

    cleared = sum(
        1 for t in valid
        if t.value >= FLOOR_SHARPE
        and float(t.user_attrs.get("profit_factor", 0.0)) >= FLOOR_PF
    )
    frac = (cleared / n) if n else 0.0
    b = frac >= FLOOR_BASIN_FRAC

    c = bool(oos_m) and (
        oos_m.get("sharpe_ratio", -99) >= FLOOR_SHARPE
        and oos_m.get("profit_factor", 0.0) >= FLOOR_PF
        and oos_m.get("max_drawdown_pct", 1e9) <= OOS_MDD_MAX
        and oos_m.get("total_return_pct", -1e9) >= OOS_RET_MIN
    )
    return {
        "n_valid": n, "median_sharpe": med_s, "median_pf": med_pf,
        "basin_frac": frac, "basin_cleared": cleared,
        "a": a, "b": b, "c": c, "pass": bool(a and b and c),
    }


def objective_value(metrics: dict[str, float], min_trades: int) -> float:
    """Maximize Sharpe; reject degenerate trials.

    Two degeneracies are rejected with the worst-possible sentinel so TPE
    steers away:

    * **0-trade** — the structural-zero failure this whole design exists
      to avoid.
    * **< ``min_trades``** — the *low-trade-count* degeneracy. Maximizing
      Sharpe with no trade floor lets the optimizer "win" by barely
      trading (e.g. 8 trades / 7 months): Sharpe/PF on a handful of
      trades is statistical noise, not an edge, and is wildly unstable
      across windows. Requiring a minimum trade count over the
      optimization window forces statistically meaningful, regime-robust
      solutions — the only kind that can credibly inform the §6 gate.
    """
    trades = metrics.get("total_trades", 0.0)
    sharpe = metrics.get("sharpe_ratio", SENTINEL)
    if not trades or trades < max(1, min_trades):
        return SENTINEL
    try:
        if sharpe != sharpe or abs(sharpe) > 100:  # NaN or pathological
            return SENTINEL
    except (TypeError, ValueError):
        return SENTINEL
    return float(sharpe)
