# Performance Service Level Agreements (SLAs)

**Version:** 2.0
**Last Updated:** 2026-10-04
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

Threshold values are unchanged at `1.5` warn / `2.0` error, but what they are
applied to is not (#857). A benchmark fails the build only when the **raw** and
the **runner-normalized** ratio are both at or over `2.0`; normalized alone is
a non-fatal `UNCONFIRMED REGRESSION` warning, raw alone falls through to the
normalized warn/pass ladder, and anything at or over `1.5` normalized is a
warning. The effective raw bar for an error is therefore `2.0 / runner factor`,
which the report prints on every run. Benchmarks whose baseline median is under
50 ms are exempt entirely, because their wall-clock ratios are noise; the
report names them rather than folding them into the "STABLE" count. Exit codes:
`0` pass, `1` warning (not fatal unless `--fail-on-warning`), `2` regression or
invalid measurement.

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

**Redis unreachable is now loud.** The gate lives in one place,
`tests/conftest.py`, which already owns the list of live-infra modules. Not
opted in, the item is skipped with a reason that names the flag. Opted in with
Redis unreachable, the item **fails at setup** — the twelve benchmarks error,
the other thirteen still run, and the checker turns the missing samples into
`NOT MEASURED` errors. A skip would leave those baseline entries unmeasured and
the job green, which is the defect, not the fallback. Failing per item rather
than raising at import time keeps the blast radius to the gated tests: an
import-time raise aborts collection and runs zero tests, and it would cover
only the two performance modules instead of all nine in
`_LIVE_INFRA_TEST_PATHS`.

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

### An error needs both ratios (2026-10-03)

A factor **below** 1.0 divides a raw change **up**. While the threshold was
applied to the normalized ratio alone, the normalizer could manufacture an
error out of a benchmark that was inside the threshold on the wall clock.

Measured on one commit — `586c7bc2`, where PR #851's diff is one config YAML
plus four docs files, none of them imported by anything in
`tests/performance/` — as the two
attempts of CI run `37101956657`, twelve minutes apart:

| attempt | runner | benchmark | raw | normalized | old verdict |
| ---: | ---: | --- | ---: | ---: | --- |
| 1 | x1.066 | `test_scalability_summary` | +177.8% | +160.5% | error |
| 1 | x1.066 | `test_memory_usage_scaling` | +159.1% | +143.0% | error |
| 2 | x0.533 | `test_memory_usage_scaling` | +10.2% | +106.6% | **error** |
| 2 | x0.533 | `test_scalability_summary` | +6.2% | +99.2% | warning |
| 2 | x0.533 | `test_end_to_end_latency_100_msgs` | **-3.5%** | **+81.0%** | warning |

Attempt 2's error is the defect in one line: +10.2% on the wall clock, failed
as a +106.6% regression because the divisor was 0.533.

And x0.533 was not a runner speed. The sixteen comparable raw ratios behind it
spanned x0.39–x1.10 in at least three clusters — redis x0.39–x0.49,
orchestrator hot path x0.53–x0.54, orchestrator scalability x1.06–x1.10 — and
the median landed on the middle one. A median over a multi-modal set is not a
common-mode estimate. The same shape is what turns a benchmark that ran 3.5%
**faster** into a "+81.0% slower" warning.

So the **error** verdict now requires the raw ratio **and** the normalized
ratio to breach the error threshold. Exactly one of the two disagreeing cases
gets a branch of its own:

| raw | normalized | verdict |
| --- | --- | --- |
| over | over | **error** |
| under | over | warning, `UNCONFIRMED REGRESSION` |
| over | under | no branch — falls through to the normalized warn/pass ladder |
| under | under | the ladder, as before |

Raw-alone is what a uniformly slow runner looks like, and acquitting that is
the whole reason normalization exists, so it is left to the ordinary ladder
and lands exactly where it did before this rule: at a uniform x2.5 every
normalized ratio is 1.0 and every benchmark **passes**. The normalizer keeps
the power it was added for and loses the power it was never meant to have. The
rule is a no-op whenever the run is not normalized — the factor within
`NORMALIZATION_EPSILON` (0.001) of 1.0 — because the two ratios are then the
same number and cannot disagree. One constant decides both the verdict and
whether the message mentions a runner, so a message cannot contradict the
verdict it explains.

The report header also prints the ratios behind the factor: their endpoints,
and the **median absolute deviation** from the factor as a fraction of it.
Endpoints alone do not say what the caption claims — attempt 1 spans x2.75 and
attempt 2 spans x2.80 — but the MAD does, because a couple of outliers cannot
move it: 3.5% on attempt 1 (one cluster plus two outliers) against 23.0% on
attempt 2 (three clusters).

**What this gives up, deliberately:** the raw ratio is now a *necessary*
condition, so the effective raw bar for an error is
`error threshold / runner factor` — **+275% at x0.533**, against the nominal
+100%. A genuine regression under that bar cannot fail the build however fast
the runner was: on a x0.5 runner a true 1.9x regression reads as a warning.
Accepted, because the alternative is convicting on an estimator whose own
dispersion inside a single run is the 23.0% MAD above. The report states the
effective bar on every run rather than leaving it to be derived. The
**warning** path is unchanged in both directions: it still fires off the
normalized ratio alone, so the "+81.0% slower" line above — a benchmark that
ran 3.5% faster — is still printed. Closing that is separate work.

### A timed region containing `gc.collect()` measures the process heap

`check_regression.py` compares pytest's **setup + call + teardown** wall time.
Everything a benchmark does lands in that number, so a benchmark that calls
`gc.collect()` inside itself is timing a full walk of the whole pytest
process's live object graph — set by what the session imported and what
earlier tests left allocated, and not by the code under test.

Measured 2026-10-03, deploy host, CPython 3.12.12 on
`Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39`. The allocation
is one `{"a": [1, 2, 3], "b": (4, 5)}` per unit, i.e. four tracked containers
each, held in a list for the duration:

```python
import gc, platform, time

def cost8():
    gc.collect()
    t = time.perf_counter()
    for _ in range(8):
        gc.collect()
    return (time.perf_counter() - t) * 1000

print(platform.python_version())
keep = []
print(0, cost8())
for add in (200_000, 400_000, 600_000):
    keep.extend({"a": [1, 2, 3], "b": (4, 5)} for _ in range(add))
    print(len(keep), cost8())
```

| extra allocations held | 8x `gc.collect()` |
| ---: | ---: |
| 0 (bare process) | 4.2 ms |
| 200,000 | 231.8 ms |
| 600,000 | 654.7 ms |
| 1,200,000 | 1251.7 ms |

(CI runs 3.11.16, so these are the shape of the effect, not CI timings.) It is
linear, and it is memory-latency bound rather than CPU bound, so it moves
**opposite** to the rest of the suite when the runner changes. In job
`111181087989` of run `37115379025` the **seven** pure-CPU hot-path benchmarks
ran **26% to 45% faster** in the same job where `test_scalability_summary` and
`test_memory_usage_scaling` read +248.5% and +228.8%. Those two took
**262–286 ms per round** there, of which their own timed loop — the per-cycle
figures they print, summed over 100 iterations and four position counts — was
**about 2 ms** (the printed figures are rounded to 0.01 ms, so 2–3 ms).

`_benchmark_orchestrator_cycle` called `gc.collect()` twice per call to bracket
a memory delta taken from `_get_process_memory_mb()`, which returned a
hardcoded `0.0`. The reading was always 0.00 MB and nothing asserted on it.
Both collections and the dead reading were removed in #857.

**The rule for a new benchmark:** nothing in the test body may have a cost
proportional to the whole process rather than to the work being measured —
`gc.collect()`, `gc.get_objects()`, a full `tracemalloc` snapshot, an
`importlib` sweep. Measure the work, and if a memory figure is genuinely
wanted, take it somewhere the checker does not time.

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

`provenance` may also carry `partial_regeneration`, written by hand when only
some entries were re-measured (see below). The top-level fields then describe
the **rest** of the file, not all of it:

```json
"partial_regeneration": {
  "regenerated": ["tests/performance/...::test_x", "..."],
  "reason": "why these entries alone no longer describe the code",
  "measured_at": "...", "runner": "...", "commit": "...",
  "rounds": 9, "workflow_run": "https://github.com/.../actions/runs/..."
}
```

The checker only reports it (a `PARTIAL BASELINE` line in the console report
and the step summary); the comparison itself is unaffected. A unit test
asserts every name under `regenerated` is a benchmark the file actually
contains, so a rename cannot leave the claim dangling.

Provenance names the machine that **measured**, not the one that wrote the file.
When a CI samples file is re-aggregated on a laptop, the runner/commit/python
fields are inherited from it and the laptop is recorded under `aggregated_on`.

### The baseline in force

| | |
| --- | --- |
| taken | 2026-10-02, `performance-baseline` run [36976948070](https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/36976948070) — 19 of 25 entries |
| re-measured | 2026-10-04 KST, run [37159332468](https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/37159332468) at `df430cc9` (PR #857) — the 6 entries of `test_orchestrator_scalability.py` |
| runner | `github-actions-ubuntu24-X64`, 4 vCPU, Python 3.11.16 (both runs) |
| commit | `16d7101e` (PR #845) for the 19, `df430cc9` (PR #857) for the 6 |
| rounds | 9 in both runs — all 25 benchmarks have n=9, no round failed |
| excluded | none |

**Why 6 entries were replaced and 19 were not.** PR #857 changed the measured
window of every benchmark in `test_orchestrator_scalability.py` twice over:
the `gc.collect()` calls came out of `_benchmark_orchestrator_cycle`, and the
fixed iteration count became a per-point `BENCHMARK_CYCLE_BUDGET` so that
every position count gets an equal-length measurement window. Their old
entries describe code that no longer runs. The other 19 were left on the
2026-10-02 anchor deliberately: re-anchoring them to one more runner adds an
offset this change has no reason to introduce.
`provenance.partial_regeneration` in the file records which entries moved,
from which run, and why, and the report prints a `PARTIAL BASELINE` line so
the split is visible without opening the file.

| benchmark | 2026-10-02 (gc, 100 iter) | gc removed, 100 iter | shipped (budget 20000) | sd (n=9) |
| --- | ---: | ---: | ---: | ---: |
| `test_cycle_time_1_position` | 0.0259s | 0.0008s | 0.0424s | 0.0006s |
| `test_cycle_time_5_positions` | 0.0202s | 0.0014s | 0.0315s | 0.0004s |
| `test_cycle_time_10_positions` | 0.0211s | 0.0021s | 0.0304s | 0.0008s |
| `test_cycle_time_20_positions` | 0.0223s | 0.0036s | 0.0293s | 0.0005s |
| `test_memory_usage_scaling` | 0.0803s | 0.0062s | 0.1309s | 0.0018s |
| `test_scalability_summary` | 0.0806s | 0.0063s | 0.1317s | 0.0017s |

The middle column is run
[37120153137](https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/37120153137)
and is kept as a measurement, not as a shipped state: at 100 iterations with
the collections gone, the two sweep benchmarks are 6.2–6.3 ms against
80.3–80.6 ms with them, so **`gc.collect()` was 92% of what those benchmarks
measured**. The four single-count entries now sit within 29–42 ms of each
other because the budget gives them equal windows, where before they ranged
over a factor of six.

**Two of the six are compared, four are exempt.** The sweeps at 131 ms are
over the 50 ms floor; the four single-count benchmarks at 29–42 ms are under
it, as they were before this PR. The comparable set is 16, the same as before.

**What guards a below-floor benchmark.** Not the baseline ratio — those four
are exempt from it. `test_cycle_time_1_position`, `_5_positions`,
`_10_positions` and `_20_positions` each assert their own entry in
`CYCLE_TIME_CEILINGS_MS` (100, 500, 5000 and 10000 ms per cycle), and a
majority of rounds failing such an assertion is an error in the checker's
round-outcome verdict, not a warning. `test_scalability_summary` used to be
the exception that proved the rule: it printed "SLA PASS"/"SLA FAIL" and ended
in `assert True`, so no timing could fail it. It now asserts all four ceilings
and the 1→20 `scaling_factor` against `MAX_SCALING_FACTOR` (20x) — the same
two things `test_memory_usage_scaling` checks — and both read those numbers
from the module constants rather than restating them, so the status the sweep
prints and the condition that fails it cannot drift apart.

That scaling assertion is only meaningful because the measurement windows are
equal. At a fixed 2000 iterations the 1-position point took ~4 ms against the
20-position point's ~47 ms, so one scheduler burst moved the ratio wholesale:
measured on the deploy host over twelve runs of the file, **8.83x to 29.88x**,
tripping the 20x bound. With `BENCHMARK_CYCLE_BUDGET` the same twelve runs
give **14.57x to 15.36x**. Taking the median rather than the mean of the
timed cycles was tried first and is kept — the mean takes the full weight of
one stall — but it does not fix this on its own, because the disturbance
covers the whole short window rather than a minority of cycles within it.

**Which candidate was used, and which was discarded.** Four
`performance-baseline` runs were taken (the measured window changed twice,
and one candidate was rejected on its runner). The shipped one is
[37159332468](https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/37159332468):
**x1.033** against the anchor on the 14 unchanged comparable benchmarks,
range x0.990–x1.085, MAD 2% — inside the x0.90–x1.10 band required above.
Run [37158999564](https://github.com/kakao-harris-lee/kis_unified_sts/actions/runs/37158999564)
measured the same commit at **x0.741** (range x0.628–x0.986, MAD 14%) and was
discarded: splicing from it would have left those six entries reading +35% on
every future run, with nothing wrong.

It replaces the 2026-05-30 single-sample file. Checked against that file
before replacing it: 0 errors, 0 warnings, 25 pass (runner factor x1.12), so
the regeneration is not absorbing a real slowdown. The twelve Redis benchmarks
have no "before" — they were last measured in CI on 2026-05-30 — so their
values are a starting point, not evidence of stability.

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

**When only some entries changed.** A benchmark whose measured window changed
makes its own entry stale and leaves the others correct. Regenerating the whole
file would re-anchor 19 correct entries to one more runner, which adds an
arbitrary offset for no reason — runner factors between x0.43 and x1.13 have
been observed within three days. So:

1. Run the workflow as above, **from the branch that contains the change**, so
   the candidate measures the new code.
2. Copy only the changed entries out of `baselines.candidate.json` into
   `tests/performance/baselines.json`, byte for byte.
3. Add or update `provenance.partial_regeneration` (schema above) naming them,
   the run, and why.
4. **Check the candidate's runner before splicing.** Compute the candidate's
   factor against the committed baseline over the *unchanged* comparable
   benchmarks only, and accept the candidate only if it lands within
   **x0.90–x1.10**:

   ```python
   median(cand[n]["median"] / base[n]["median"]
          for n in base
          if n not in regenerated and base[n]["median"] >= 0.05)
   ```

   A spliced entry carries its measuring runner's speed with it forever, and
   the runner-speed factor cannot remove it: the factor is a median over all
   comparable benchmarks, so it tracks the majority group and the spliced
   minority reads `1 / candidate factor` on *every* future run. Measured in
   #857: a x0.914 candidate leaves them +9%, a x0.741 candidate leaves them
   +35% — a third of the way to the warning threshold with nothing wrong. A
   whole-file regeneration does not have this failure mode, because a uniform
   offset is exactly what the factor removes; that is the trade the band
   protects. Discard an out-of-band candidate and run the workflow again.
5. Run the checker with the spliced baseline against that same run's
   `current.json` and quote the result in the PR.

`excluded` is **not** an alternative to this. A benchmark that still produces
samples and is listed as excluded is a stale exclusion, which the checker
reports as an error — correctly, since the alternative is a benchmark that is
measured and not checked.

**A later whole-file regeneration drops `partial_regeneration`**, because the
writer emits its own provenance and nothing carries that key across. That is
the right outcome — after a whole-file run every entry does come from that one
run — but it means the key is not a permanent record. Keep the reasoning in
this document, as above, not only in the JSON.

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
