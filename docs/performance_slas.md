# Performance Service Level Agreements (SLAs)

**Version:** 2.0
**Last Updated:** 2026-10-02
**Status:** Current

This document tracks current runtime performance targets for the KIS Unified STS
stack. RL/TFT runtime paths and ClickHouse are retired; their old SLA reference
is archived at
[`archive/performance_slas-rl-era.md`](archive/performance_slas-rl-era.md).

## Component SLAs

| Component | Target | Warning | Critical | Notes |
|-----------|--------|---------|----------|-------|
| WebSocket market-data ingest | p95 processing latency below measured baseline x 1.2 | p95 > baseline x 1.2 for 5 min | p99 > baseline x 1.5 for 2 min | Applies to stock and futures feeds. |
| Redis runtime streams/state | DB 1 only; p99 ops latency below measured baseline x 1.2 | p99 > baseline x 1.2 | write/read failure or DB mismatch | New Redis keys require TTLs unless explicitly persistent. |
| Parquet/DuckDB market data | 1-day query p95 < 500 ms; 30-day query p95 < 1000 ms | 1-day > 600 ms or 30-day > 1200 ms | 1-day > 750 ms or 30-day > 1500 ms | Applies to warmup, backtest, and research reads. |
| Runtime ledger SQLite WAL | reads/writes complete within dashboard refresh budget | repeated lock contention | write failure or WAL unavailable | Used for order/fill/position/trade evidence. |
| Trading orchestrator cycle | cycle time below measured baseline x 1.2 | cycle > baseline x 1.2 | cycle > baseline x 1.5 or missed session window | Futures monolith remains active unless F9 cutover is complete. |
| Decoupled stock pipeline | ingest -> strategy -> risk -> order path remains fresh within operator dashboard freshness windows | stale stage warning | missing stage data or blocked stream | Standard stock paper path is Compose `stock-ingest` + `stock-pipeline`. |
| Dashboard API | operator endpoints respond within 10 s timeout | repeated 5xx or timeout warning | `/health` failure | Caddy host port defaults to `5081` for paper/local; dashboard `8001` is internal. |
| Scheduler one-shot jobs | scheduled KST jobs complete before dependent next step | delayed or missing report | job failure affecting next session readiness | Source of truth: `deploy/scheduler.crontab`. |

## Regression Checks

Frontend and smoke gates:

```bash
npm --prefix strategy-builder-ui run build
npm --prefix strategy-builder-ui run lint
```

### The CI `performance` job

`.github/workflows/test.yml::performance` runs on PRs to `main` and weekly. It
measures `tests/performance/` **`PERF_ROUNDS` times (default 5)**, one pytest
process per round, and compares the **median** of each benchmark against the
median of the baseline's rounds.

```bash
# What CI runs (the measure step also sets, see "What CI measures" below:
#   KIS_RUN_LIVE_INFRA_TESTS=1
#   REDIS_HOST=localhost REDIS_PORT=6379 REDIS_DB=1)
for round in $(seq 1 5); do
  pytest tests/performance/ -q -s --json-report \
    --json-report-file="tests/performance/rounds/round-$round.json"
done

python scripts/performance/check_regression.py \
  --baseline tests/performance/baselines.json \
  --current tests/performance/rounds/round-*.json \
  --write-samples tests/performance/current.json \
  --markdown-summary "$GITHUB_STEP_SUMMARY" \
  --warning-threshold "$PERF_WARNING_THRESHOLD" \
  --error-threshold "$PERF_ERROR_THRESHOLD" \
  --min-duration "$PERF_MIN_DURATION"
```

`PERF_ROUNDS`, the three thresholds and `PERF_COMMIT_SHA` are job-level `env`
in `test.yml::performance`, and `performance-baseline.yml` reads the same three
thresholds. The minimum round count for a baseline is defined once, as
`check_regression.py --min-baseline-rounds`'s default.

A round that FAILS a test does not stop the loop, and does not by itself fail
the job. Running N rounds multiplies the chance of hitting a flaky assertion by
N, and a failure in round 3 must not throw away the measurement from the other
four. The checker counts outcomes per benchmark instead:

| failing rounds | verdict |
| --- | --- |
| minority (1 of 5) | ⚠️ warning, job stays green |
| majority (3 of 5) | 🔴 error, job red |
| skipped in every round | 🔴 error — `NOT MEASURED`, unless the baseline excludes it |

The reason is the same one the whole check is about. A benchmark assertion like
`test_exit_path_50_symbols`'s `improvement_pct >= -40` is itself a
single-sample timing comparison: on run 36954483251 it produced −41.8% in one
round of five and passed in the other four. Failing the build on that
reproduces #768 one level down. A test that fails in most rounds is a test
failure and does fail the build.

Thresholds are unchanged: `>=2x` fails, `1.5x-2x` is a non-fatal warning, and
benchmarks whose baseline median is under 50 ms are exempt because their
wall-clock ratios are noise. Exit codes: `0` pass, `1` warning (not fatal unless
`--fail-on-warning`), `2` regression or invalid measurement.

### A session that never ran is an error, not a pass

`pytest-json-report` writes a report even when collection aborts, so the file
existing proves nothing. The checker reads each round report's own `exitcode`
and `collectors`:

| round report | verdict |
| --- | --- |
| exit 0 or 1 | session completed (1 = some test failed, judged by the table below) |
| exit 2/3/4/5, or a failed collector | 🔴 measurement invalid, exit 2 |
| zero benchmarks with a passing sample | 🔴 measurement invalid, exit 2 |
| file missing entirely | the workflow fails the measure step |

Without this, an `ImportError` in one performance module would abort collection
in all five rounds, turn all 25 baseline entries into non-fatal
`Test not found` warnings, and report green having measured nothing. Before the
N-round loop the single `pytest` invocation's non-zero exit failed the step; the
loop swallows that exit, so the property had to move into the checker.

**The job is not a required check.** A red `performance` does not block a merge;
`test` is the only real gate (see `CLAUDE.md`).

### What CI measures, and what it does not

**All 25 benchmarks are measured.** The job runs a `redis:7-alpine` service
container and the measure step sets:

| variable | value | why |
| --- | --- | --- |
| `KIS_RUN_LIVE_INFRA_TESTS` | `1` | opts the 12 Redis benchmarks in |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` | `localhost` / `6379` / `1` | what `RedisClient` actually reads |
| `REDIS_URL` | `redis://localhost:6379/1` | not read on this path; kept correct for anything that does |

Until 2026-10 the job measured **13 of 25**. `test_redis_load.py` and
`test_websocket_load.py` skip unless `KIS_RUN_LIVE_INFRA_TESTS` is set and the
job did not set it, so their 12 benchmarks produced 12 non-fatal
`Test not found` warnings per run and the check went green having measured half
the suite. Two details made that hard to see:

- Their skip reason said *"Redis not available (start with: docker-compose up -d
  redis)"*. The Redis service container was up the whole time. The reason was a
  guess, not a check, and it was wrong every time.
- The workflow set only `REDIS_URL`, which
  `shared/streaming/client.py::RedisClient` does not read — it reads
  `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB`. Correcting `REDIS_URL` alone would
  have changed nothing.

The opt-in exists because the deploy host's paper runtime and the suite share
Redis DB 1, and these tests write runtime-shaped keys
(`trading:{asset}:positions`). It stays off by default everywhere else; a CI
runner's throwaway service container is the one place it is safe. Neither
module reaches a KIS endpoint — `test_websocket_load.py` is named for what the
Redis Streams it measures carry, not for a KIS WebSocket connection.

**Redis unreachable is now loud.** With the flag set, `tests/support/live_infra.py`
raises during collection instead of skipping, pytest exits 2, and the checker
reports the round as an invalid measurement. A skip would leave the baseline's
Redis entries unmeasured and the job green, which is the defect, not the
fallback.

### Measured, excluded, or an error

A baseline entry has exactly two legitimate states in a run:

| state | verdict |
| --- | --- |
| produced samples | compared against the baseline median |
| listed in the baseline's `excluded` map, no samples | no comparison, no warning; listed in the report with its reason |
| neither | 🔴 `NOT MEASURED` — error, exit 2 |
| listed in `excluded` **and** produced samples | 🔴 stale exclusion — error, exit 2 |

The third row is what the twelve warnings used to be. Making it an error is
what gives the exclusion list teeth: with `excluded` empty, all 25 benchmarks
have to run or the check fails.

The fourth row is the anti-rot rule. An exclusion whose reason has stopped
being true would otherwise go on suppressing a benchmark that is running again,
and a regression in it would be invisible for as long as nobody rereads the
file.

```json
"excluded": {
  "tests/performance/test_x.py::TestX::test_y": "why this is not measured here"
}
```

An entry without a written reason is rejected at load, as is a name that
appears in both `excluded` and `benchmarks`. **`excluded` is currently empty**:
every benchmark in `tests/performance/` runs on a CI runner with a Redis
service container, measured 2026-10-02. Nothing in the suite needs a live KIS
endpoint.

To regenerate a baseline while keeping its exclusions, pass
`--exclusions-from <the current baseline>`; `performance-baseline.yml` does
this. A comparison takes its exclusions from the baseline it is comparing
against.

### Why medians of N rounds (#768, #796)

The check used to compare one sample against one committed sample. Re-running
the job 10x on a fixed head, with byte-identical code, gave
`test_entry_path_100_symbols`:

| | value |
| --- | ---: |
| n (usable) | 7 |
| min | 0.1217 s |
| median | 0.2755 s |
| max | 0.3800 s |
| sd (sample) | 0.0842 s |
| committed baseline (2026-05-30) | 0.1329 s |

That is a 3.1x spread and 3 of 10 jobs red for no reason. Two things are wrong,
and they are not the same thing:

1. The *current* value was one draw, and that draw always carried the cold first
   round (see below) — so the verdict was a coin flip. Medians of N rounds fix
   this, measurably: on this change's own CI run the same benchmark reads −4.7%
   against the unchanged baseline and the job is green.
2. The *baseline* is still one draw with no recorded spread, so whatever offset
   it carries is arbitrary. That is why the checker warns on it, why the format
   carries n and provenance, and why the regeneration workflow exists.

It was predicted that keeping (2) would turn the intermittent red into a
**permanent** red once medians were compared. **The measurement refuted that**,
and the mistake is worth recording: the ten #768 values were ten single
cold-inclusive samples from ten different jobs, not ten rounds within one job.
Treating one distribution as the other is the same over-reach #768's own
comment history records twice.

### What the spread actually was

Measured on this change's own CI run (36953158113), five rounds in one job, per
phase, for `test_entry_path_100_symbols`:

| round | setup | call | total |
| --- | ---: | ---: | ---: |
| 1 (cold) | **0.2138 s** | 0.1102 s | 0.3241 s |
| 2 | 0.0182 s | 0.1087 s | 0.1271 s |
| 3 | 0.0180 s | 0.1085 s | 0.1266 s |
| 4 | 0.0180 s | 0.1072 s | 0.1254 s |
| 5 | 0.0182 s | 0.1063 s | 0.1248 s |
| baseline 2026-05-30 | 0.0315 s | 0.1012 s | 0.1329 s |

`call` — the part that runs the benchmark — spans 3.7%. The entire spread is in
`setup`, 12x between the first round and the rest. This test is the first of the
session, so it absorbs one-time process warm-up in its own setup phase, and the
checker sums setup + call + teardown. The old check ran pytest once, so it
bought that cold setup every time; how expensive it is varies by runner (0.0315 s
on the baseline runner, 0.2138 s here). **#768's 3.1x was cold-start variance,
not benchmark variance.**

Medians push the cold round to 1-in-N and drop it. Against the same 2026-05-30
single-sample baseline, the median of 5 rounds reads −4.7% and the job is green.
Comparing `call` only would remove the component at its source; that is a
candidate follow-up, deliberately not bundled here because it would invalidate
every existing baseline entry at the same time as everything else changed.

It also settles the regression question numerically: `call` alone is 0.1085 s
today versus 0.1012 s on 2026-05-30, **+7.2%** across four months and a runner
generation.

The mechanism is not averaging-down of noise. The within-job distribution is
bimodal — one cold round and N−1 warm ones — and the median of N simply
**excludes the cold round** as long as fewer than half the rounds are cold. That
is why N=5 suffices and why raising N further buys almost nothing: round 2 is
already warm. It is not a `sqrt(N)` effect; that law is for the *mean* of
independent samples and describes neither the median nor this distribution.

Between-runner variance is untouched: all N rounds share one runner, so a
globally slow runner still shifts them together. That component is what the
runner-speed factor targets.

### Runner-speed normalization and its measured limit

`runner_speed_factor()` (#397) divides every ratio by the median
current/baseline ratio across all comparable benchmarks, so a uniformly slow
runner does not read as a per-test regression. The direction is right. The
magnitude is not reliable at n=1, because the factor is estimated from the same
noisy samples it corrects. Measured 2026-10-01, two runs with nearly identical
raw values landed 63 points apart after correction:

| run | raw | runner factor | after correction |
| --- | ---: | ---: | ---: |
| 36868546962 | +152.3% | x1.12 | +126.0% |
| 36876551928 | +153.9% | x0.88 | +189.6% |

It is kept because the common-mode effect is real; medians are what damp the
estimator's own variance.

### Baseline format and provenance

`tests/performance/baselines.json` is either a legacy pytest-json-report (read
as n=1, and the report then prints a `SINGLE-SAMPLE BASELINE` warning) or a
`kis-perf-samples/v1` document:

```json
{
  "schema": "kis-perf-samples/v1",
  "provenance": {
    "generated_at": "2026-10-02T11:00:00+09:00",
    "role": "baseline",
    "rounds": 7,
    "runner": "github-actions-ubuntu24-X64",
    "python": "3.11.9",
    "commit": "...",
    "workflow_run": "https://github.com/.../actions/runs/..."
  },
  "excluded": {},
  "benchmarks": {
    "tests/performance/...::test_x": {
      "n": 7, "median": 0.27, "min": 0.12, "max": 0.38,
      "mean": 0.25, "sd": 0.08, "samples": [0.27, 0.17, ...]
    }
  }
}
```

Provenance names the machine that **measured**, not the one that wrote the file.
When a CI samples file is re-aggregated on a laptop, the runner/commit/python
fields are inherited from it and the laptop is recorded under `aggregated_on`.

### Regenerating the baseline

A baseline must come from **>= 5 rounds on the hardware the check runs on**.
`check_regression.py` refuses fewer (`--force-baseline` overrides and stamps
`UNDER-SAMPLED` into the file's note).

1. Run the **`performance-baseline`** workflow
   (`.github/workflows/performance-baseline.yml`) from the Actions tab,
   `rounds` >= 5, with a note saying why.
2. Download the `performance-baseline-candidate` artifact.
3. Commit it in a PR:

   ```bash
   cp baselines.candidate.json tests/performance/baselines.json
   ```

4. Quote the artifact's `provenance` block and the per-benchmark
   `n / median / min / max / sd` in the PR body. A baseline whose origin is not
   written down is how #768 went four months undiagnosed.

To build a candidate from samples you already have:

```bash
python scripts/performance/check_regression.py \
  --current tests/performance/current.json \
  --exclusions-from tests/performance/baselines.json \
  --write-baseline tests/performance/baselines.json
```

Leave `--exclusions-from` out and the new baseline declares nothing excluded,
so every previously excluded benchmark becomes a `NOT MEASURED` error on the
next run. The checker refuses to write a baseline whose carried exclusions name
a benchmark its own samples contain; `--force-baseline` does not override that,
because the result would be rejected on the next read anyway.

**Order matters.** Do not regenerate a baseline to silence a red check before
ruling out a real regression — once absorbed, a genuine slowdown is invisible
forever. For `test_entry_path_100_symbols` the ruling-out is structural: it
times only `_simulate_*` helpers defined inside its own test module, and every
change to that file since the baseline commit (`f68c2c3a`) is outside the timed
region (an unused import, and f-strings in `print` calls). The benchmarked code
is byte-identical, so no code regression is possible there. Benchmarks that do
import `shared/` (`test_orchestrator_scalability.py`, `test_redis_load.py`,
`test_websocket_load.py`) carry no such guarantee and need the question asked
separately. For the twelve Redis benchmarks there is no "before" to compare
against yet: the committed 2026-05-30 baseline does contain them, but they have
not been measured in CI since, so their first regenerated values are a fresh
starting point, not evidence of stability.

## Monitoring Notes

- Prometheus metrics should focus on websocket throughput/latency, Redis ops,
  dashboard route latency, orchestrator cycle time, stream freshness, and
  scheduler job success.
- ClickHouse metrics are historical only.
- RL/TFT inference latency metrics are historical only and must not be used as
  live runtime acceptance criteria.

## Maintenance

Update this document when active runtime surfaces change. Keep historical,
point-in-time SLA snapshots in `docs/archive/`.
