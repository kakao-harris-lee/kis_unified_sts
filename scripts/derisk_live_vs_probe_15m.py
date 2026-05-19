#!/usr/bin/env python3
"""De-risking checkpoint: do LIVE 15m bars == the probe's offline 15m bars?

The entire bb_reversion_15m productionizing effort (and the robust-gate
result that motivates it) rests on ONE unproven assumption: the 15-minute
bars produced by the *live* orchestrator path
(`MultiTimeframeCandleAccumulator`, services/trading/indicator_engine.py)
are equivalent to the offline 1m→15m pandas resample the probe used
(`scripts/probe_bb_reversion_15m_gate.py::_resample_15m`) — the bars that
actually passed the re-scoped robust gate.

If they match: live == backtest == probe holds → the gate result
transfers → the Option-B build is sound. If they diverge (esp. at
session open / intraday gaps): the edge is *unvalidated on live bars* and
we caught it for ~½ day instead of after an L-sized build + 3–4 months
of paper.

This feeds the 101S6000 1m CSV bar-by-bar through the exact live
accumulator class and diffs the resulting closed 15m candles,
sequence-aligned, against `_resample_15m`. Read-only analysis; writes
nothing but a stdout report.

Usage:
    python scripts/derisk_live_vs_probe_15m.py \
        --data data/kospi200f_1m_ch_101S6000.csv
"""

from __future__ import annotations

# ruff: noqa: E402 — sys.path is set before the sibling/shared imports.
import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_SCRIPTS.parent))

import pandas as pd
from optimize_llm_directed_indicator import _CSV_KW
from probe_bb_reversion_15m_gate import _resample_15m

from services.trading.indicator_engine import (
    Candle,
    MultiTimeframeCandleAccumulator,
)
from shared.validation.cli_validators import validate_csv_file

_TOL = 1e-6  # OHLCV float-equality tolerance


def _live_15m(df1: pd.DataFrame) -> list[tuple]:
    """Feed the 1m CSV through the EXACT live MTF accumulator and collect
    closed 15m candles (in order), then flush the final partial bucket —
    mirroring orchestrator `_feed_mtf_candle` + session-end flush."""
    acc = MultiTimeframeCandleAccumulator(timeframe_minutes=15, maxlen=10**9)
    out: list[tuple] = []
    dt = pd.to_datetime(df1["datetime"])
    o = df1["open"].astype(float).to_numpy()
    h = df1["high"].astype(float).to_numpy()
    lo = df1["low"].astype(float).to_numpy()
    c = df1["close"].astype(float).to_numpy()
    v = df1["volume"].astype(float).to_numpy()
    for i in range(len(df1)):
        ts = dt.iloc[i]
        minute = ts.hour * 100 + ts.minute
        done = acc.on_1m_candle(
            Candle(open=o[i], high=h[i], low=lo[i], close=c[i],
                   volume=v[i], minute=minute)
        )
        if done is not None:
            out.append((done.minute, done.open, done.high, done.low,
                        done.close, done.volume))
    tail = acc.flush()
    if tail is not None:
        out.append((tail.minute, tail.open, tail.high, tail.low,
                    tail.close, tail.volume))
    return out


def _probe_15m(df1: pd.DataFrame) -> list[tuple]:
    r = _resample_15m(df1)
    return [
        (
            int(row.datetime.hour) * 100 + int(row.datetime.minute),
            float(row.open), float(row.high), float(row.low),
            float(row.close), float(row.volume),
            row.datetime,  # for reporting only
        )
        for row in r.itertuples(index=False)
    ]


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= _TOL + 1e-9 * max(abs(a), abs(b))


def main():
    ap = argparse.ArgumentParser(description="live vs probe 15m bar diff")
    ap.add_argument("--data", "-d",
                    default="data/kospi200f_1m_ch_101S6000.csv")
    a = ap.parse_args()

    print(f"\n{'=' * 70}\nDE-RISK: live MTF 15m  vs  probe _resample_15m"
          f"\n{'=' * 70}")
    df1 = validate_csv_file(a.data, **_CSV_KW)
    live = _live_15m(df1)
    probe = _probe_15m(df1)
    print(f"1m bars: {len(df1)}")
    print(f"live 15m candles : {len(live)}")
    print(f"probe 15m candles: {len(probe)}")

    n = min(len(live), len(probe))
    mism = []  # (idx, field, live, probe, probe_dt, live_minute)
    for i in range(n):
        lm, lo_, lh, ll, lc, lv = live[i]
        pm, po, ph, pl, pc, pv, pdt = probe[i]
        for fld, x, y in (("minute", lm, pm), ("open", lo_, po),
                          ("high", lh, ph), ("low", ll, pl),
                          ("close", lc, pc), ("volume", lv, pv)):
            ok = (x == y) if fld == "minute" else _close(x, y)
            if not ok:
                mism.append((i, fld, x, y, pdt, lm))
                break

    matched = n - len({m[0] for m in mism})
    cnt_ok = len(live) == len(probe)
    print(f"\ncount match : {'YES' if cnt_ok else f'NO (Δ={len(live) - len(probe)})'}")
    print(f"aligned bars: {n}  |  fully-matching: {matched}  "
          f"({matched / n * 100:.3f}% of aligned)" if n else "no overlap")

    if mism:
        print("\nfirst 8 divergences (idx · field · live · probe · "
              "probe_dt · live_minute):")
        for i, fld, x, y, pdt, lm in mism[:8]:
            print(f"  #{i:<5} {fld:<6} live={x!s:<14} probe={y!s:<14} "
                  f"@{pdt}  liveHHMM={lm}")
        # classify: how many at the FIRST bin of a session/day?
        sess_open = sum(
            1 for _, _, _, _, pdt, _ in mism
            if (pdt.hour, pdt.minute) <= (9, 15)
        )
        print(f"\n  divergences total: {len(mism)}  |  at session-open "
              f"(≤09:15): {sess_open}")

    verdict_ok = cnt_ok and not mism
    print(f"\n{'=' * 70}")
    if verdict_ok:
        print(">>> MATCH ✅ — live MTF 15m bars are bar-for-bar identical "
              "to the\n    probe's resample. live == backtest == probe "
              "holds: the robust-\n    gate result transfers. Option-B "
              "build is sound to proceed.")
    else:
        print(">>> DIVERGE ❌ — live 15m bars are NOT identical to the "
              "bars that\n    passed the robust gate. The edge is "
              "UNVALIDATED on live bars.\n    Risk #1 confirmed — fix the "
              "bucketing to match (or treat the\n    probe result as not "
              "transferable) BEFORE the Option-B build.\n    (Caught for "
              "~½ day instead of after an L-build + 3–4mo paper.)")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
