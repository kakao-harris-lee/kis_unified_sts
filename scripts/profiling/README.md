# Hot-path profiling

Reusable profiling for the indicator + forecasting compute paths.

## `profile_hotpath.py`

Non-intrusive `line_profiler`-based profiler. It imports the real
`shared/indicators` and `shared/forecasting` code (no source edits) and drives
it with synthetic OHLCV / realized-variance inputs, so it measures **compute
cost**, not data-dependent behaviour.

```bash
pip install -e ".[dev]"          # provides line_profiler
python scripts/profiling/profile_hotpath.py
```

Output is two passes:

1. **Wall-clock** (no profiler overhead) — real `us/ms per call` for each
   momentum calculator, the full `calculate_all_momentum`, and the HAR-RV
   forecasting path. Use these numbers for magnitude.
2. **line_profiler** — per-line attribution inside the hottest functions. Use
   the `% Time` column to find the dominant line(s); ignore the inflated
   absolute per-hit times (deterministic tracing adds fixed per-line overhead).

## Interpreting results

- The live real-time path recomputes momentum only when a timeframe bar closes
  (`services/trading/indicator_engine.py` momentum cache, keyed by candle
  count) — **not per tick**. So indicator cost mainly bites **uncached** paths:
  backtests / Optuna sweeps and warmup/seed bursts.
- Look for Python-level `.apply(lambda ...)` callbacks and chains of pandas
  `Series` ops (`.clip`, `.where`, `.replace`, `.fillna`) — those vectorize
  well. Leave `.ewm()` and `.rolling().min()/max()` in pandas: they are C-level
  and pandas' deque rolling-min/max (O(n)) beats a strided view (O(n·w)).

## For live services (not this script)

`line_profiler` is for the offline/uncached compute paths above. To find where a
**running** service spends time, use `py-spy` (sampling, attach by PID, no code
change): `py-spy record --pid <PID> -o flame.svg` (macOS needs `sudo`; in Docker
add `--cap-add SYS_PTRACE`).

## Optimization history

`calculate_all_momentum` on a 250-bar window (wall-clock, this harness):

| Stage | us/call | Cumulative |
| --- | ---: | ---: |
| baseline | 3212 | — |
| + CCI vectorized (`_rolling_mad`) | 2310 | −28% |
| + RSI numpy 1-pass | 1686 | −47% |
| + Stochastic / Williams %R / TRIX arithmetic in numpy | 1448 | **−55% (2.2×)** |

Per-calculator, before → after (in-pipeline):

| Calculator | before | after | note |
| --- | ---: | ---: | --- |
| CCI | 1145 | 248 | `rolling().apply` mean-abs-dev → strided view |
| RSI | 686 | 107 | `.clip`/`.where`/`.fillna` → one numpy pass; `.ewm` kept |
| Stochastic | 253 | 155 | raw-%K arithmetic → numpy; rolling kept |
| TRIX | 230 | 144 | ROC ratio → numpy; triple `.ewm` kept |
| Williams %R | 178 | 86 | %R arithmetic → numpy; rolling kept |
| MACD | 152 | 152 | left as-is (numpy tightening was ~2%, not worth it) |

All changes are bit-exact vs the prior implementation (`max|Δ| = 0.00e+00`
across random / flat / monotonic / edge inputs) and covered by the existing
momentum / indicator-engine / technical-consensus unit tests.
