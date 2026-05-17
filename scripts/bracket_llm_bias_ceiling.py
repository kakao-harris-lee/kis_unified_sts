#!/usr/bin/env python3
"""Sensitivity bracket: the *ceiling* a directional-bias layer could add
to `llm_directed_indicator`.

Why this exists: historical LLM `market_context` was never persisted
(only a 24h-TTL Redis key), so the spec §4(b) "replay logged context"
evaluation is impossible — there is nothing to replay. Instead we bound
the **maximum value any directional-bias mask could ever add** by
forcing the mask per run over the full backtest range:

  * FLAT    — mask off (the spec §4(a) baseline; re-scoped gate already
              FAILs this — see reports/optuna/FINDINGS.md)
  * LONG    — every bar LONG_BIAS (longs only)
  * SHORT   — every bar SHORT_BIAS (shorts only)
  * ORACLE  — per bar, the bias that matches the *future* return sign
              (LOOK-AHEAD ON PURPOSE — the theoretical ceiling of a
              perfect directional mask on this exact indicator strategy)

Decision rule (operator-approved 2026-05-17): if the ORACLE ceiling
still FAILs the re-scoped non-catastrophic bar (Sharpe≥0, PF≥1.0,
MDD≤25%, ret≥0 — and ideally a comfortable margin), then NO real
(imperfect) LLM bias can rescue the floor → the approach is dead and we
should NOT invest weeks collecting live LLM context. If ORACLE clears it
comfortably, the bias layer is worth the data-collection investment.

Injection seam: a thin proxy wraps the `TradingStrategy` and sets
`context.market_context` before delegating `check_entry`. The shared
`BacktestStrategyAdapter` / `on_bar` and the FLAT-default contract are
untouched (production code unchanged).

Usage:
    python scripts/bracket_llm_bias_ceiling.py
    python scripts/bracket_llm_bias_ceiling.py --oracle-horizon 60
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.backtest.adapter import BacktestStrategyAdapter
from shared.backtest.config import BacktestConfig
from shared.backtest.engine import BacktestEngine
from shared.config.loader import ConfigLoader
from shared.llm.data_classes import MarketSignal
from shared.llm.market_context import MarketContext
from shared.strategy.registry import (
    StrategyFactory,
    register_builtin_components,
)
from shared.validation.cli_validators import validate_csv_file

register_builtin_components()

_ASSET = "futures"
_STRATEGY = "llm_directed_indicator"
_DEFAULT_DATA = "data/kospi200f_1m_ch_101S6000.csv"
_CSV_KW = {
    "reject_duplicate_datetime": True,
    "require_monotonic_datetime": True,
    "max_zero_volume_ratio": 0.95,
    "max_zero_volume_price_move_ratio": 0.20,
}

# Min trades for a verdict to be statistically meaningful. Without this,
# Sharpe/PF on a handful of look-ahead-selected trades reads as a fake
# "comfortable" ceiling (same low-trade-count degeneracy the Optuna
# objective's min-trades floor fixes — see _objective_value in
# scripts/optimize_llm_directed_indicator.py). Below it → INCONCLUSIVE.
_MIN_TRADES = 30
# Non-catastrophic floor (re-scoped §6 gate component (c)).
_FLOOR_SHARPE, _FLOOR_PF, _MDD_MAX, _RET_MIN = 0.0, 1.0, 25.0, 0.0
# "Comfortable" margin — a ceiling only worth chasing if it clears this.
_COMFORT_SHARPE, _COMFORT_PF = 1.0, 1.3

_BULL = MarketContext(overall_signal=MarketSignal.STRONG_BULLISH, confidence=1.0)
_BEAR = MarketContext(overall_signal=MarketSignal.STRONG_BEARISH, confidence=1.0)


class _ForcedBiasStrategy:
    """Delegates everything to the wrapped strategy, but stamps a forced
    ``market_context`` onto the EntryContext first. Only ``check_entry``
    is intercepted — the directional mask is entry-only, which is exactly
    the layer being bracketed."""

    def __init__(self, inner, mode: str, oracle: dict[int, str] | None = None):
        self._inner = inner
        self._mode = mode
        self._oracle = oracle or {}

    def __getattr__(self, name):  # delegate name/entry/exit/sizer/etc.
        return getattr(self._inner, name)

    def _ctx(self, context) -> MarketContext | None:
        if self._mode == "FLAT":
            return None
        if self._mode == "LONG":
            return _BULL
        if self._mode == "SHORT":
            return _BEAR
        # ORACLE — key by epoch seconds of the bar timestamp.
        ts = getattr(context, "timestamp", None)
        key = int(ts.timestamp()) if ts is not None else -1
        d = self._oracle.get(key, "FLAT")
        return _BULL if d == "LONG" else _BEAR if d == "SHORT" else None

    async def check_entry(self, context):
        context.market_context = self._ctx(context)
        return await self._inner.check_entry(context)


def _build_oracle(df, horizon: int) -> dict[int, str]:
    """Per-bar perfect-hindsight direction: sign of the forward return
    over ``horizon`` bars. Keyed by epoch-seconds of the bar datetime."""
    close = df["close"].to_numpy(dtype=float)
    dt = df["datetime"]
    n = len(close)
    out: dict[int, str] = {}
    for i in range(n):
        j = min(i + horizon, n - 1)
        fwd = (close[j] / close[i] - 1.0) if close[i] else 0.0
        d = "LONG" if fwd > 0 else "SHORT" if fwd < 0 else "FLAT"
        out[int(dt.iloc[i].timestamp())] = d
    return out


def _load_cfg(params_yaml: str | None) -> dict:
    if not params_yaml:
        return ConfigLoader.load_strategy(_ASSET, _STRATEGY)  # defaults
    import yaml
    with open(params_yaml) as fh:
        return yaml.safe_load(fh)


def _run(mode, df, bt_config, oracle, params_yaml) -> dict[str, float]:
    cfg = _load_cfg(params_yaml)
    strat = _ForcedBiasStrategy(StrategyFactory.create(cfg), mode, oracle)
    adapter = BacktestStrategyAdapter(strat, cfg)
    return BacktestEngine(adapter, bt_config).run(df.copy()).to_metrics_dict()


def _verdict(m: dict[str, float]) -> tuple[bool, bool, bool]:
    """Returns (enough_trades, non_catastrophic, comfortable).

    non_cat / comfortable are FALSE unless the run has ≥ _MIN_TRADES —
    Sharpe/PF on a few look-ahead-picked trades is noise, not a ceiling.
    """
    enough = int(m.get("total_trades", 0)) >= _MIN_TRADES
    non_cat = enough and (
        m.get("sharpe_ratio", -99) >= _FLOOR_SHARPE
        and m.get("profit_factor", 0) >= _FLOOR_PF
        and m.get("max_drawdown_pct", 1e9) <= _MDD_MAX
        and m.get("total_return_pct", -1e9) >= _RET_MIN
    )
    comfortable = (
        non_cat
        and m.get("sharpe_ratio", -99) >= _COMFORT_SHARPE
        and m.get("profit_factor", 0) >= _COMFORT_PF
    )
    return enough, non_cat, comfortable


def main():
    ap = argparse.ArgumentParser(description="LLM-bias ceiling bracket")
    ap.add_argument("--data", "-d", default=_DEFAULT_DATA)
    ap.add_argument("--oracle-horizon", "-H", type=int, default=30,
                    help="forward bars for the perfect-hindsight oracle")
    ap.add_argument("--params-yaml", "-p", default=None,
                    help="strategy YAML with tuned params (default: the "
                         "registered default config). Use a higher-"
                         "activity config so the oracle has enough trades "
                         "for a meaningful ceiling.")
    args = ap.parse_args()

    src = args.params_yaml or "default params"
    print(f"\n{'=' * 70}\nLLM-bias CEILING bracket — {_STRATEGY} "
          f"({src})\n{'=' * 70}")
    df = validate_csv_file(args.data, **_CSV_KW)
    print(f"Data: {args.data}  ({len(df)} bars, "
          f"{df['datetime'].min()} ~ {df['datetime'].max()})")
    print(f"Oracle horizon: {args.oracle_horizon} bars  "
          f"(look-ahead — theoretical ceiling)")
    print(f"Min-trades for a meaningful verdict: {_MIN_TRADES}\n")

    bt = BacktestConfig.futures(initial_capital=10_000_000, point_value=50_000)
    oracle = _build_oracle(df, args.oracle_horizon)

    rows = []
    for mode in ("FLAT", "LONG", "SHORT", "ORACLE"):
        m = _run(mode, df, bt, oracle, args.params_yaml)
        enough, nc, comf = _verdict(m)
        rows.append((mode, m, enough, nc, comf))
        tag = ("INSUFFICIENT-TRADES" if not enough
               else "comfortable" if comf
               else "non-cat" if nc else "CATASTROPHIC")
        print(f"  {mode:<7} Sharpe={m.get('sharpe_ratio', float('nan')):7.3f}  "
              f"PF={m.get('profit_factor', float('nan')):6.3f}  "
              f"trades={int(m.get('total_trades', 0)):4d}  "
              f"win={m.get('win_rate', 0):4.1f}%  "
              f"ret={m.get('total_return_pct', 0):8.1f}%  "
              f"MDD={m.get('max_drawdown_pct', 0):5.1f}%  {tag}")

    _, om, oenough, onc, ocomf = rows[-1]
    print(f"\n{'=' * 70}\nDECISION (operator rule)\n{'=' * 70}")
    print("  Ceiling = ORACLE (perfect-hindsight direction; the best any "
          "directional\n  mask could ever do on this exact indicator "
          "strategy).")
    if not oenough:
        print(f"\n  >>> ORACLE produced < {_MIN_TRADES} trades "
              f"({int(om.get('total_trades', 0))}) → its Sharpe/PF are "
              "statistical NOISE,\n      not a ceiling. A directional "
              "mask only ever *removes* trades, so\n      the ensemble "
              "must trade enough on its own first. With this config the\n"
              "      ceiling is UNMEASURABLE / economically negligible "
              "(ret "
              f"{om.get('total_return_pct', 0):.1f}%). Treat as: NO "
              "evidence the bias\n      layer can rescue the floor — do "
              "NOT invest in live LLM-context\n      collection on this "
              "basis. Re-run with a higher-activity config to\n      "
              "confirm, else the approach is dead.")
    elif not onc:
        print("\n  >>> ORACLE ceiling is CATASTROPHIC → no real LLM bias "
              "can rescue\n      the floor. APPROACH IS DEAD — do NOT "
              "invest in live LLM-context\n      collection. Reconsider "
              "the strategy / LLM-absent fallback.")
    elif not ocomf:
        print("\n  >>> ORACLE clears non-catastrophic but only MARGINALLY "
              f"(< Sharpe {_COMFORT_SHARPE}/PF {_COMFORT_PF}). Even a "
              "*perfect* mask barely helps →\n      poor ROI on weeks of "
              "LLM-context collection. Likely not worth it.")
    else:
        print(f"\n  >>> ORACLE clears COMFORTABLY (≥ Sharpe "
              f"{_COMFORT_SHARPE}/PF {_COMFORT_PF}, ≥{_MIN_TRADES} "
              "trades). A directional bias\n      layer has real headroom "
              "→ collecting live LLM context to evaluate\n      the "
              "*real* (imperfect) bias is justified.")
    print("\n  NB: ORACLE is look-ahead by construction — an unreachable "
          "upper bound,\n  not an achievable result. Real LLM bias is "
          "strictly worse than this.")
    print(
        "\n  ⚠️  COUPLING CAVEAT: this bracket is only decision-meaningful "
        "when run\n  on a config that PASSES the re-scoped §6 gate "
        "(scripts/optimize_llm_\n  directed_indicator.py). On a "
        "gate-FAILING config the FLAT/ORACLE\n  numbers are "
        "overfitting artifacts — a high FLAT just means the config is\n"
        "  a curve-fit, and the ORACLE 'lift' is measured off that "
        "inflated base.\n  If FLAT is already 'comfortable', the bias "
        "layer is not what's carrying\n  the result. Bracket ⊥ gate: "
        "you need BOTH (robust floor AND headroom)."
    )


if __name__ == "__main__":
    main()
