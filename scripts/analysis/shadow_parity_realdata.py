"""Real-data shadow-parity harness: engine vs legacy ``_calc_*`` on Parquet bars.

The fixed-seed unit harness (``tests/unit/indicators/engine/test_shadow_parity.py``)
pins the *kind* of each engine-vs-legacy relationship (ADX parity; ATR/Stochastic/
Bollinger divergence) on one synthetic series. This script re-measures the same
relationships across **real** stock and futures minute bars so the delegate-safe
vs. gate-required classification that drives Phase 2 (``_calc_*`` -> engine
delegation) rests on real market distributions, not a single seed.

For each sampled bar-close it feeds an identical bounded window (the runtime's
``candle_maxlen``) to both the TA-Lib/NumPy engine and the streaming
``IndicatorCalculationMixin._calc_*`` and records a :class:`ShadowDelta`. It then
reports, per indicator, the delta distribution (median / p95 / p99 / max relative
error) and an automatic classification.

Run on the deploy host (needs ``data/market`` Parquet + the TA-Lib wheel)::

    .venv/bin/python -m scripts.analysis.shadow_parity_realdata --asset both \
        --out docs/analysis/2026-07-05-shadow-parity-realdata.md

This is measurement only: it never writes trading state and touches no live path.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from services.trading.indicator_calculations import IndicatorCalculationMixin
from services.trading.indicator_candles import Candle
from shared.indicators.engine import (
    IndicatorComputationError,
    IndicatorSpec,
    TALibBackend,
    default_engine,
    window_from_bars,
)
from shared.indicators.engine.shadow import ShadowDelta
from shared.storage.market_data_store import ParquetMarketDataStore

# Runtime defaults (services/trading/indicator_engine.py __init__): the harness
# compares engine vs legacy for the *same* params so a delta reflects convention
# (Wilder vs SMA, ddof, fast vs slow), not a parameter mismatch.
BB_PERIOD = 20
BB_STD = 2.0
RSI_PERIOD = 14
RVOL_SHORT = 5
RVOL_LONG = 20
ATR_PERIOD = 14
ADX_PERIOD = 14
STOCH_PERIOD = 14
STOCH_SMOOTH = 3
MFI_PERIOD = 14

DEFAULT_WINDOW = 240  # matches StreamingIndicatorEngine.candle_maxlen deque bound


class _LegacyShim(IndicatorCalculationMixin):
    """Bare mixin instance carrying the runtime's default indicator params.

    ``_calc_bb``/``_calc_rsi``/``_calc_rvol``/``_calc_mfi`` read instance
    attributes; the static ``_calc_atr_raw``/``_calc_adx``/``_calc_stochastic``
    do not. We set the attributes to the runtime defaults above.
    """

    def __init__(self) -> None:
        self.bb_period = BB_PERIOD
        self.bb_std = BB_STD
        self.rsi_period = RSI_PERIOD
        self._rvol_short = RVOL_SHORT
        self._rvol_long = RVOL_LONG


# --- one comparison = an engine spec + how to read the legacy scalar -----------


@dataclass(frozen=True)
class Comparison:
    """A single engine-value vs. legacy-scalar comparison for one indicator.

    ``engine_value`` reads a scalar from the engine's ``flat_latest()`` dict.
    Most read one flat key; Bollinger reads the band *half-width*
    (``bb_upper - bb_middle``) rather than the band *level*, because the ddof
    change moves the width by ~2.5% but that is diluted to ~0.05% against the
    price-dominated band level — and it is the width that ``bb_reversion`` trades.
    """

    label: str
    engine_id: str
    engine_params: dict[str, float]
    engine_value: Callable[[dict[str, float]], float | None]
    legacy: Callable[[_LegacyShim, list[Candle]], float | None]
    expected: str  # documented prior: "safe" | "gate"


def _closes(candles: list[Candle]) -> list[float]:
    return [c.close for c in candles]


def _comparisons() -> list[Comparison]:
    return [
        Comparison(
            "rsi",
            "rsi",
            {"period": RSI_PERIOD},
            lambda f: f.get("rsi"),
            lambda s, c: s._calc_rsi(_closes(c)),
            "safe",
        ),
        Comparison(
            "adx",
            "adx",
            {"period": ADX_PERIOD},
            lambda f: f.get("adx"),
            lambda _s, c: IndicatorCalculationMixin._calc_adx(c, ADX_PERIOD),
            "safe",
        ),
        Comparison(
            "atr",
            "atr",
            {"period": ATR_PERIOD},
            lambda f: f.get("atr"),
            lambda _s, c: IndicatorCalculationMixin._calc_atr_raw(c, ATR_PERIOD),
            "gate",
        ),
        Comparison(
            "bb_middle",
            "bollinger",
            {"period": BB_PERIOD, "std": BB_STD},
            lambda f: f.get("bb_middle"),
            lambda s, c: s._calc_bb(_closes(c))[1],
            "safe",
        ),
        Comparison(
            # band half-width (upper - middle): isolates the ddof=1->0 change
            # that price-level dilution hides on the raw band level.
            "bb_width",
            "bollinger",
            {"period": BB_PERIOD, "std": BB_STD},
            lambda f: (
                None
                if f.get("bb_upper") is None or f.get("bb_middle") is None
                else f["bb_upper"] - f["bb_middle"]
            ),
            lambda s, c: (lambda bb: bb[2] - bb[1])(s._calc_bb(_closes(c))),
            "gate",
        ),
        Comparison(
            "stoch_k",
            "stochastic",
            {"k_period": STOCH_PERIOD, "d_period": STOCH_SMOOTH},
            lambda f: f.get("stoch_k"),
            lambda _s, c: IndicatorCalculationMixin._calc_stochastic(
                c, STOCH_PERIOD, STOCH_SMOOTH
            )[0],
            "gate",
        ),
        Comparison(
            "mfi",
            "mfi",
            {"period": MFI_PERIOD},
            lambda f: f.get("mfi"),
            lambda s, c: s._calc_mfi(c, MFI_PERIOD),
            "safe",
        ),
        Comparison(
            "rvol",
            "rvol",
            {"short_window": RVOL_SHORT, "long_window": RVOL_LONG},
            lambda f: f.get("rvol"),
            lambda s, c: s._calc_rvol(c),
            "safe",
        ),
    ]


def _candles_from_frame(df: Any) -> list[Candle]:
    """Turn a market-data frame (code, datetime, ohlcv) into Candle objects."""
    out: list[Candle] = []
    for row in df.itertuples(index=False):
        ts = row.datetime
        minute = int(getattr(ts, "hour", 0)) * 100 + int(getattr(ts, "minute", 0))
        out.append(
            Candle(
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
                minute=minute,
            )
        )
    return out


def _symbols(store: ParquetMarketDataStore, limit: int | None) -> list[str]:
    """Enumerate minute-bar symbols from the store's own root (no duplicated path)."""
    base = Path(store.root) / store.asset_class / "minute"
    codes = sorted(p.name.split("=", 1)[1] for p in base.glob("code=*") if p.is_dir())
    return codes[:limit] if limit else codes


def _finite(x: float | None) -> bool:
    return x is not None and np.isfinite(x)


def _percentile(values: list[float], q: float) -> float:
    return float(np.percentile(values, q)) if values else float("nan")


def run(
    asset: str,
    *,
    symbol_limit: int | None,
    window: int,
    samples: int,
) -> dict[str, Any]:
    # Fail loudly if the TA-Lib wheel is absent: default_engine() would silently
    # degrade to NumPy-only, every TA-Lib id would raise UnsupportedIndicatorError,
    # and the report would show n=0 for 7/8 indicators with no error surfaced.
    if not TALibBackend.available():
        raise SystemExit(
            'TA-Lib wheel not importable — run `pip install -e ".[dev]"`. '
            "Without it this harness would emit a misleadingly-empty report."
        )

    store = ParquetMarketDataStore("data/market", asset_class=asset)  # type: ignore[arg-type]
    symbols = _symbols(store, symbol_limit)
    engine = default_engine()
    shim = _LegacyShim()
    comparisons = _comparisons()

    # Each engine spec is computed once per window and shared across the
    # comparisons that read it (bb_middle + bb_width share one Bollinger pass).
    specs: dict[str, IndicatorSpec] = {}
    comp_spec_key: dict[str, str] = {}
    for comp in comparisons:
        spec = IndicatorSpec.create(comp.engine_id, comp.engine_params)
        specs.setdefault(spec.key, spec)
        comp_spec_key[comp.label] = spec.key

    deltas: dict[str, list[ShadowDelta]] = {c.label: [] for c in comparisons}
    symbols_used = 0
    bars_total = 0

    for symbol in symbols:
        df = store.get_minute_bars(symbol)
        if df is None or len(df) < window + 1:
            continue
        candles = _candles_from_frame(df)
        if len(candles) < window + 1:
            continue
        symbols_used += 1
        bars_total += len(candles)

        # even-spaced endpoints from the first fully-warmed bar to the last
        endpoints = np.unique(
            np.linspace(window - 1, len(candles) - 1, num=samples).astype(int)
        )
        for e in endpoints:
            win_candles = candles[e - window + 1 : e + 1]
            engine_window = window_from_bars(win_candles)
            # compute each unique spec once for this window
            flats: dict[str, dict[str, float]] = {}
            for key, spec in specs.items():
                try:
                    flats[key] = engine.compute(spec, engine_window).flat_latest()
                except IndicatorComputationError:
                    continue  # skip a degenerate window; UnsupportedIndicator propagates
            for comp in comparisons:
                flat = flats.get(comp_spec_key[comp.label])
                if flat is None:
                    continue
                new = comp.engine_value(flat)
                old = comp.legacy(shim, win_candles)
                if not _finite(new) or not _finite(old):
                    continue
                deltas[comp.label].append(
                    ShadowDelta(comp.label, float(new), float(old))
                )

    results: dict[str, Any] = {
        "asset": asset,
        "symbols_used": symbols_used,
        "bars_total": bars_total,
        "window": window,
        "samples_per_symbol": samples,
        "indicators": {},
    }
    for comp in comparisons:
        ds = deltas[comp.label]
        # rel_delta is inf when legacy ~= 0 (flat/degenerate window): those windows
        # drop out of the rel-based stats, so report their count separately rather
        # than hide them behind the total pair count.
        rels = [d.rel_delta for d in ds if np.isfinite(d.rel_delta)]
        absd = [d.abs_delta for d in ds]
        n_pairs = len(ds)
        n_rel = len(rels)
        median_rel = _percentile(rels, 50)
        # Rate of gross (>=50%) disagreement. For value-convention indicators this
        # is ~0; for RSI/MFI it captures the flat/halted-window sentinel tail
        # (legacy returns neutral 50.0, TA-Lib returns 0.0) — a delegation
        # contract issue, not a value change.
        large_div_rate = (
            sum(1 for r in rels if r >= 0.5) / n_rel if rels else float("nan")
        )
        # Classify on the *robust median*, not p95/p99: a real convention change
        # (Wilder vs SMA, ddof, fast vs slow) is present on ~every window, so it
        # moves the median. The median tolerates up to 50% contamination, so it is
        # immune to the RSI/MFI sentinel tail (a minority of flat windows); p95
        # would flip to gate-required once that tail exceeded 5%.
        classification = (
            "delegate-safe"
            if np.isfinite(median_rel) and median_rel <= 0.01
            else "gate-required"
        )
        results["indicators"][comp.label] = {
            "n": n_rel,  # denominator of the rel-based stats below
            "n_pairs": n_pairs,
            "n_zero_legacy": n_pairs - n_rel,  # dropped inf (legacy ~= 0) windows
            "expected": comp.expected,
            "median_abs": _percentile(absd, 50),
            "median_rel": median_rel,
            "p95_rel": _percentile(rels, 95),
            "p99_rel": _percentile(rels, 99),
            "max_rel": max(rels) if rels else float("nan"),
            "large_div_rate": large_div_rate,
            "classification": classification,
            "agrees_with_prior": classification.startswith("delegate")
            == (comp.expected == "safe"),
        }
    return results


def _fmt_pct(x: float) -> str:
    return "n/a" if not np.isfinite(x) else f"{x * 100:.3f}%"


def _json_safe(obj: Any) -> Any:
    """Recursively replace non-finite floats with None for standard JSON."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def render_markdown(all_results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# Real-data shadow parity — engine vs legacy `_calc_*`")
    lines.append("")
    lines.append(
        "Engine (TA-Lib / NumPy) vs streaming `IndicatorCalculationMixin._calc_*` "
        "measured on identical bounded windows (runtime `candle_maxlen`) across "
        "real Parquet minute bars. `rel` = |engine − legacy| / |legacy|; `n` is the "
        "count of finite-rel comparisons (windows where legacy ~= 0 are excluded "
        "from the rel stats). **Classification is on the robust median** — a genuine "
        "convention change (Wilder vs SMA, ddof, fast vs slow) is present on ~every "
        "window, so it moves the median; a divergence confined to a minority tail "
        "(`≥50% div` column) is a degenerate-window artifact, not a value change. "
        "**delegate-safe** = median rel ≤ 1% (no backtest gate); **gate-required** = "
        "systematic value change, needs a Setup-A/C / bb_reversion / stochastic "
        "backtest gate before delegation."
    )
    lines.append("")
    for res in all_results:
        lines.append(
            f"## {res['asset']} — {res['symbols_used']} symbols, "
            f"{res['bars_total']:,} bars, window={res['window']}, "
            f"{res['samples_per_symbol']} samples/symbol"
        )
        lines.append("")
        lines.append(
            "| indicator | n | median rel | p95 rel | p99 rel | max rel | "
            "≥50% div | prior | classification |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|---|---|")
        for label, m in res["indicators"].items():
            flag = "" if m["agrees_with_prior"] else " ⚠️"
            lines.append(
                f"| `{label}` | {m['n']:,} | {_fmt_pct(m['median_rel'])} | "
                f"{_fmt_pct(m['p95_rel'])} | {_fmt_pct(m['p99_rel'])} | "
                f"{_fmt_pct(m['max_rel'])} | {_fmt_pct(m['large_div_rate'])} | "
                f"{m['expected']} | **{m['classification']}**{flag} |"
            )
        lines.append("")
    lines.extend(_interpretation_lines(all_results))
    lines.append("_Generated by `scripts/analysis/shadow_parity_realdata.py`._")
    lines.append("")
    return "\n".join(lines)


# Per-indicator gate rationale, rendered only when that indicator actually
# classifies gate-required in the measured results (so the prose can never
# contradict the tables).
_GATE_NOTES: dict[str, str] = {
    "rsi": (
        "- `rsi` — bit-identical to legacy only at long windows (~200+ bars). "
        "TA-Lib seeds Wilder with an SMA of the first `period` deltas; the streaming "
        "`_calc_rsi` seeds on the first delta, so on the SHORT windows the runtime "
        "actually uses early in a session (len≥20) they diverge by **up to ~17 RSI "
        "points**. A live delegation would change early-session RSI-gated entries → "
        "backtest gate required."
    ),
    "adx": (
        "- `adx` — warmup contract differs: TA-Lib needs ~2×period bars to emit a "
        "finite value, while `_calc_adx` returns a value at period+1 (partial-DX "
        "average). On short windows the engine is still `None` where legacy gives a "
        "number, so delegation changes early-session ADX availability → gate."
    ),
    "atr": (
        "- `atr` — legacy is SMA-of-TR, engine is Wilder; median ~6% (stock) / ~8% "
        "(futures), tails far higher on quiet minutes. Drives Setup A/C stops + "
        "edge filters and ATR exits → needs a Setup-A/C backtest gate. (Note: "
        "`#571` evaluated the standalone-consumer ATR and chose **keep SMA**; the "
        "engine ATR would need an SMA mode, or the gate must justify the switch.)"
    ),
    "bb_width": (
        "- `bb_width` — legacy sample std (ddof=1) vs engine population std "
        "(ddof=0): a constant band-half-width shift of **2.53%** (= 1 − √(19/20)). "
        "Drives `bb_reversion` band touches → bb_reversion backtest gate."
    ),
    "stoch_k": (
        "- `stoch_k` — legacy fast %K vs engine slow %K (STOCH): median 17–25%. "
        "Either gate the fast→slow change or switch the backend to `STOCHF` to "
        "preserve the fast convention."
    ),
}


def _interpretation_lines(all_results: list[dict[str, Any]]) -> list[str]:
    """Interpretation derived from the results, classified by the WORST window.

    An indicator is delegate-safe only if it is delegate-safe at EVERY tested
    window — the shortest window (the runtime's early-session case) is the binding
    constraint. Classifying off a single long window overstated the safe set: RSI
    and ADX are bit-parity at ~200+ bars but diverge on the short windows the
    runtime actually uses (Wilder seeding / ADX warmup).
    """
    windows = sorted({int(res.get("window", 0)) for res in all_results})
    labels: list[str] = []
    for res in all_results:
        for label in res["indicators"]:
            if label not in labels:
                labels.append(label)

    def safe_everywhere(label: str) -> bool:
        seen = False
        for res in all_results:
            m = res["indicators"].get(label)
            if m is None:
                continue
            seen = True
            if m["classification"] != "delegate-safe":
                return False
        return seen

    # Warmup-sensitive: safe at the longest window but NOT at the shortest.
    def warmup_sensitive(label: str) -> bool:
        long_w, short_w = max(windows), min(windows)
        safe_long = any(
            res.get("window", 0) == long_w
            and res["indicators"].get(label, {}).get("classification")
            == "delegate-safe"
            for res in all_results
        )
        gate_short = any(
            res.get("window", 0) == short_w
            and res["indicators"].get(label, {}).get("classification")
            == "gate-required"
            for res in all_results
        )
        return safe_long and gate_short

    safe = [x for x in labels if safe_everywhere(x)]
    gate = [x for x in labels if not safe_everywhere(x)]
    warmup = [x for x in gate if warmup_sensitive(x)]

    lines = ["## Interpretation → Phase 2 delegation", ""]
    lines.append(
        f"Windows tested: {', '.join(str(w) for w in windows)} bars. **Classified by "
        "the shortest window** — the runtime fires `get_indicators` from `len ≥ "
        "bb_period` (20), so early-session parity is what a live delegation must hold."
    )
    lines.append("")
    safe_str = ", ".join(f"`{s}`" for s in safe) or "—"
    lines.append(
        f"**Delegate-safe at every window (drop-in, no gate):** {safe_str}. Only "
        "these are bit-identical to the legacy streaming calc across the runtime's "
        "variable window lengths."
    )
    lines.append("")
    if warmup:
        warm_str = ", ".join(f"`{w}`" for w in warmup)
        lines.append(
            f"**⚠️ Warmup-sensitive (safe ONLY at long windows — NOT drop-in):** "
            f"{warm_str}. Bit-parity at ~200+ bars but divergent on the short windows "
            "the runtime uses early in a session. Classifying these off a single long "
            "window (as the first cut of this report did) is misleading — they are "
            "**gated value changes**, not free swaps."
        )
        lines.append("")
    lines.append("**Gate-required (value change — backtest before delegating):**")
    for label in gate:
        lines.append(_GATE_NOTES.get(label, f"- `{label}` — value change (see table)."))
    lines.append("")
    lines.append(
        "**RSI/MFI sentinel-contract note:** the `≥50% div` tail is flat/halted-window "
        "disagreement — legacy returns the neutral sentinel **50.0**, TA-Lib **0.0** — "
        "on illiquid constant-price names. Any RSI/MFI delegation must preserve the "
        "neutral fallback on degenerate windows or a 0.0 reads as extreme oversold."
    )
    lines.append("")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--asset", choices=["stock", "futures", "both"], default="both")
    ap.add_argument("--symbol-limit", type=int, default=None)
    ap.add_argument(
        "--windows",
        type=str,
        default="30,240",
        help="Comma-separated window lengths. Short windows expose the "
        "early-session warmup/seeding divergence (RSI/ADX) that a single long "
        "window hides; the runtime fires get_indicators from len>=bb_period (20).",
    )
    ap.add_argument("--samples", type=int, default=60)
    ap.add_argument("--out", type=str, default=None, help="Markdown report path")
    ap.add_argument("--json-out", type=str, default=None, help="Raw stats JSON path")
    args = ap.parse_args()

    windows = [int(w) for w in str(args.windows).split(",") if w.strip()]
    assets = ["stock", "futures"] if args.asset == "both" else [args.asset]
    all_results = [
        run(a, symbol_limit=args.symbol_limit, window=w, samples=args.samples)
        for a in assets
        for w in windows
    ]

    md = render_markdown(all_results)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(md)
    if args.json_out:
        # Standard JSON has no NaN/Infinity: emit null instead so strict parsers
        # (jq, JSON.parse, serde_json) accept the file.
        Path(args.json_out).write_text(
            json.dumps(_json_safe(all_results), indent=2, allow_nan=False),
            encoding="utf-8",
        )
        print(f"wrote {args.json_out}")


if __name__ == "__main__":
    main()
