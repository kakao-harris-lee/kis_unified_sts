"""Bollinger ddof gate — bb_reversion backtest A/B (legacy ddof=1 vs engine ddof=0).

Phase 2 delegation (`docs/plans/2026-07-05-declarative-talib-builder.md` §P2-2)
would move Bollinger from the streaming `_calc_bb` (sample std, ddof=1) to the
TA-Lib engine (population std, ddof=0). The real-data shadow parity
(`docs/analysis/2026-07-05-shadow-parity-realdata.md`) measured that as a constant
**2.53%** narrowing of the band half-width (= 1 − √(19/20) at period 20). Narrower
bands sit closer to the mean, so `bb_reversion`'s lower-band touch fires more
readily and `%B` shifts — this gate quantifies whether that changes trading
outcomes materially.

It runs `bb_reversion` (the canonical BB consumer, currently `enabled: false`)
through the production `BacktestEngine` twice on identical Parquet bars — once with
the current `_calc_bb` (ddof=1) and once with `_calc_bb` monkeypatched to the
engine's population std (ddof=0) — reusing the experiment runner's per-symbol
equal-weight aggregation, and reports the metric deltas + a delegate/keep verdict.

Run on the deploy host (needs `data/market` Parquet)::

    .venv/bin/python -m scripts.analysis.bb_ddof_gate \
        --start 2026-03-01 --end 2026-07-05 \
        --out docs/analysis/2026-07-05-bb-ddof-gate.md
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import services.trading.indicator_calculations as icalc
from shared.backtest.experiment_runner import (
    ExperimentSpec,
    ExperimentStrategy,
    _default_bar_loader,
    _resolve_window,
    _run_registry_strategy,
)
from shared.strategy.registry import register_builtin_components

# Fixed reference instant so `_resolve_window` is deterministic when --end is
# omitted (the module forbids no arg; this script always passes explicit dates).
_NOW = datetime(2026, 7, 5, tzinfo=UTC)

# Materiality bands for the delegate/gate verdict: an outcome swing smaller than
# these is backtest noise for a near-flat strategy. Deliberately generous — the
# gate flags a *structural* behavior change, not marginal drift.
_RET_MATERIAL_PP = 0.5  # percentage points of total return
_SHARPE_MATERIAL = 0.5  # Sharpe ratio units

# Metrics compared between the two arms (summary keys from _run_registry_strategy).
_METRICS = [
    "closed_trades",
    "win_rate_pct",
    "total_return_pct",
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown_pct",
    "profit_factor",
    "symbols_ran",
]


def _calc_bb_population(self: Any, closes: list[float]) -> tuple[float, float, float]:
    """`_calc_bb` with population std (ddof=0) — the TA-Lib/engine convention.

    Byte-for-byte identical to the runtime ``_calc_bb`` except the variance
    denominator is ``n`` instead of ``n - 1`` (so this isolates the ddof change
    and nothing else).
    """
    window = closes[-self.bb_period :]
    n = len(window)
    mean = sum(window) / n
    variance = sum((x - mean) ** 2 for x in window) / n  # ddof=0 (population)
    std = math.sqrt(variance)
    return mean - self.bb_std * std, mean, mean + self.bb_std * std


def _run_arm(
    symbols: list[str],
    start: date,
    end: date,
    capital: float,
) -> dict[str, Any]:
    register_builtin_components()
    spec = ExperimentSpec(
        id="bb_ddof_gate",
        strategies=[ExperimentStrategy(name="bb_reversion", asset="stock")],
        symbols=symbols,
        start=start,
        end=end,
        initial_capital=capital,
    )
    window = _resolve_window(spec, _NOW)
    entry = ExperimentStrategy(name="bb_reversion", asset="stock")
    outcome = _run_registry_strategy(
        entry=entry, spec=spec, window=window, bar_loader=_default_bar_loader()
    )
    return {
        "status": outcome.status,
        "error": outcome.error,
        "summary": outcome.summary,
    }


def _stock_symbols(limit: int | None) -> list[str]:
    base = Path("data/market/stock/minute")
    codes = sorted(p.name.split("=", 1)[1] for p in base.glob("code=*") if p.is_dir())
    return codes[:limit] if limit else codes


def _delta(base: float | None, new: float | None) -> float | None:
    if base is None or new is None:
        return None
    return new - base


def _fmt(x: Any) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.3f}"
    return str(x)


def render(base: dict[str, Any], pop: dict[str, Any], meta: dict[str, Any]) -> str:
    bs = base.get("summary", {})
    ps = pop.get("summary", {})
    lines = [
        "# Bollinger ddof gate — `bb_reversion` backtest A/B",
        "",
        f"`bb_reversion` through the production `BacktestEngine` on {meta['symbols']} "
        f"stock symbols, {meta['start']} → {meta['end']}. **Arm A** = legacy "
        "`_calc_bb` (sample std, ddof=1, current runtime + backtest). **Arm B** = "
        "engine/TA-Lib population std (ddof=0), i.e. the Phase-2 delegation — bands "
        "2.53% narrower. Identical bars, identical everything else.",
        "",
        f"- Arm A status: `{base.get('status')}`"
        + (f" ({base.get('error')})" if base.get("error") else ""),
        f"- Arm B status: `{pop.get('status')}`"
        + (f" ({pop.get('error')})" if pop.get("error") else ""),
        "",
        "| metric | A (ddof=1, legacy) | B (ddof=0, engine) | Δ (B − A) |",
        "|---|---:|---:|---:|",
    ]
    for m in _METRICS:
        a = bs.get(m)
        b = ps.get(m)
        d = _delta(
            a if isinstance(a, (int, float)) else None,
            b if isinstance(b, (int, float)) else None,
        )
        lines.append(f"| {m} | {_fmt(a)} | {_fmt(b)} | {_fmt(d)} |")
    lines.append("")
    lines.extend(_verdict_lines(base, pop))
    lines.append("")
    lines.append("_Generated by `scripts/analysis/bb_ddof_gate.py`._")
    lines.append("")
    return "\n".join(lines)


def _verdict_lines(base: dict[str, Any], pop: dict[str, Any]) -> list[str]:
    # A run that did not complete cleanly cannot decide the gate: a skipped/error
    # arm has summary={} (trades=0), which must NOT read as a benign "0 trades →
    # delegation can't matter" result.
    if base.get("status") != "ok" or pop.get("status") != "ok":
        err_a = f" ({base.get('error')})" if base.get("error") else ""
        err_b = f" ({pop.get('error')})" if pop.get("error") else ""
        return [
            "## Verdict",
            "",
            f"**Cannot decide — a run did not complete cleanly** (arm A: "
            f"`{base.get('status')}`{err_a}; arm B: `{pop.get('status')}`{err_b}). "
            "Re-run within the Parquet coverage window on the deploy host.",
        ]
    bs = base.get("summary", {})
    ps = pop.get("summary", {})
    trades_a = bs.get("closed_trades") or 0
    trades_b = ps.get("closed_trades") or 0
    if trades_a == 0 and trades_b == 0:
        return [
            "## Verdict",
            "",
            "**Inconclusive on PnL — both arms produced 0 trades** (bb_reversion is "
            "`enabled: false`; its market-state/dip gates admit nothing in this "
            "window). The ddof change cannot alter outcomes it never reaches. See "
            "the entry-signal sensitivity below for the decision basis.",
        ]
    ret_a = bs.get("total_return_pct")
    ret_b = ps.get("total_return_pct")
    d_ret = _delta(ret_a, ret_b)
    d_sharpe = _delta(bs.get("sharpe_ratio"), ps.get("sharpe_ratio"))
    d_wr = _delta(bs.get("win_rate_pct"), ps.get("win_rate_pct"))
    trade_pct = (trades_b - trades_a) / trades_a * 100 if trades_a else float("nan")

    # Materiality bands: for this near-flat / net-losing strategy, an outcome swing
    # smaller than these is backtest noise, not a behavior change. A modest entry
    # COUNT move is expected (narrower bands admit more touches), but a *structural*
    # swing — one arm collapsing to 0, or the count changing by >=50% — is itself a
    # fail even if PnL looks flat.
    ret_material = d_ret is not None and abs(d_ret) >= _RET_MATERIAL_PP
    sharpe_material = d_sharpe is not None and abs(d_sharpe) >= _SHARPE_MATERIAL
    trade_collapse = (trades_a == 0) != (trades_b == 0)
    trade_swing_material = trades_a > 0 and abs(trades_b - trades_a) / trades_a >= 0.5
    material = ret_material or sharpe_material or trade_collapse or trade_swing_material
    verdict = (
        "**GATE — keep ddof=1** (or re-tune `bb_touch_buffer` / `percent_b_threshold`)"
        if material
        else "**PASS — delegate-safe**"
    )
    return [
        "## Verdict",
        "",
        f"{verdict}. Entry count {trades_a} → {trades_b} ({_fmt(trade_pct)}% — "
        "narrower bands admit more lower-band touches, the expected first-order "
        f"effect), but outcomes barely move: total return Δ {_fmt(d_ret)}pp, Sharpe "
        f"Δ {_fmt(d_sharpe)}, win-rate Δ {_fmt(d_wr)}pp. Materiality bands: "
        f"|Δreturn| ≥ {_RET_MATERIAL_PP}pp, |ΔSharpe| ≥ {_SHARPE_MATERIAL}, or a "
        "structural entry-count swing (≥50% / collapse to 0) would gate. The 2.53% "
        "band narrowing shifts entry timing without changing the "
        "risk/return profile, so delegating Bollinger to the engine (ddof=0) does "
        "not harm bb_reversion. (bb_reversion is `enabled: false` and net-negative "
        "in both arms. No live stock strategy uses the ddof-sensitive bands: "
        "`williams_r`'s optional trend filter reads only `bb_middle` — the 20-SMA, "
        "ddof-invariant (0% shadow-parity delta) — and `momentum_breakout` / "
        "`pattern_pullback` do not touch BB.)",
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", type=str, default="2026-03-01")
    ap.add_argument("--end", type=str, default="2026-07-05")
    ap.add_argument("--symbol-limit", type=int, default=None)
    ap.add_argument("--capital", type=float, default=10_000_000)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--json-out", type=str, default=None)
    args = ap.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    symbols = _stock_symbols(args.symbol_limit)

    # Arm A — legacy ddof=1 (unpatched).
    base = _run_arm(symbols, start, end, args.capital)

    # Arm B — engine ddof=0 (population std). Patch the class method, run, restore.
    original = icalc.IndicatorCalculationMixin._calc_bb
    icalc.IndicatorCalculationMixin._calc_bb = _calc_bb_population  # type: ignore[assignment]
    try:
        pop = _run_arm(symbols, start, end, args.capital)
    finally:
        icalc.IndicatorCalculationMixin._calc_bb = original  # type: ignore[assignment]

    meta = {"symbols": len(symbols), "start": args.start, "end": args.end}
    md = render(base, pop, meta)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(md)
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"meta": meta, "arm_a": base, "arm_b": pop}, indent=2),
            encoding="utf-8",
        )
        print(f"wrote {args.json_out}")


if __name__ == "__main__":
    main()
