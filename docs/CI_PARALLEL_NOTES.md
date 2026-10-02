# CI Parallel Test Execution — Notes

**Status**: **ENABLED in CI (2026-06-03)** via a two-pass split — `-n auto -m "not serial"`
parallel pass + a serial pass for `serial`-marked tests. Previously local-only
(2026-05-09) pending the parallel-unsafe-test fixes described below.

## Update 2026-06-03 — enabled via parallel + serial split

The `test` job's "Run tests" step now runs:

```bash
pytest tests/ --ignore=tests/performance -n auto -m "not serial" --cov=... --cov-report= && \
pytest tests/ --ignore=tests/performance -m serial --cov=... --cov-append --cov-report=xml ...
```

Rather than fix every parallel-unsafe test for in-process worker isolation, the
genuinely-unsafe tests are marked `@pytest.mark.serial` (registered in
`pyproject.toml`) and run in a second, non-parallel pass where there is no
concurrent worker to race them. xdist workers are separate **processes**, so
in-process singletons are already isolated; the only cross-worker hazards are
*external* shared state, which the serial pass removes:

- `tests/integration/test_graceful_shutdown.py` — shared Redis DB 1 keys
- `tests/integration/test_redis_tls.py` — real Redis, short socket timeouts
- `tests/unit/kis/test_rate_limiter.py::...test_acquire_respects_penalty` — wall-clock timing
- `tests/unit/dashboard/routes/test_health.py::...test_caches_response_1s` — 1s cache window

Hypothesis' shared example DB is isolated per worker via
`HYPOTHESIS_STORAGE_DIRECTORY` in `tests/conftest.py` (parallel pass).

`tests/performance/` is excluded from both passes and runs in its own
`performance` job, which measures each benchmark over several rounds and
compares medians. That job, its thresholds, and how to regenerate its baseline
are documented in [`performance_slas.md`](performance_slas.md#the-ci-performance-job).

Validated: full suite at `-n auto` (16 workers, the worst-case contention,
≥ CI's 2–4) — parallel pass 0 failures, serial pass 0 failures.

## Update 2026-10-02 — the session is hermetic by construction (#698)

A pytest process must never reach a real `.env`, a real broker credential or a
real token cache. On 2026-09-15 it did: a unit run inside a worktree under
`<repo>/.claude/worktrees/<name>/` loaded the **primary** checkout's `.env` and
had a real KIS token issued and written to `.kis_token_real`. The mechanism was
python-dotenv's `find_dotenv()`, which walks from the calling file up to the
filesystem root, reached by an argument-less `load_dotenv()` in
`cli/commands/common.py` that ran during collection.

### The rules

- **Entrypoints never walk.** Every `.env` load in `cli/` and `scripts/` goes
  through `shared.config.dotenv_guard.load_project_dotenv()`, which reads at
  most `<checkout>/.env` and then `<cwd>/.env`. No ancestor directory is ever
  consulted, so a nested worktree cannot reach the checkout above it. Do not
  call `load_dotenv()` directly from a module an entrypoint imports.
- **`KIS_TEST_HERMETIC` switches the loader off.** `tests/conftest.py` sets it
  at import time, before collection. It is the only knob this adds, it is a
  test switch rather than a configuration surface, and the paper/live runtime
  never sets it — with it unset the entrypoints behave exactly as before.
- **The credential namespace is emptied.** The whole `KIS_*` and `TELEGRAM_*`
  space is removed from `os.environ`, whatever its source — a `.env` already
  loaded, or variables exported in the operator's shell. Only the test switches
  survive (`KIS_TEST_HERMETIC`, `KIS_RUN_LIVE_INFRA_TESTS`,
  `KIS_TEST_IMAGE_NO_GIT_METADATA`). This also keeps local runs honest: CI sets
  none of these, so a test that quietly depended on one used to pass locally
  and fail in CI.
- **Config and token caches are pinned.** `KIS_CONFIG_DIR` points at *this*
  checkout's `config/`, and `KIS_TOKEN_CACHE_DIR` at a per-process temp
  directory, so a `.kis_token_*` can no longer land in a repository root (the
  default is `Path.cwd()`).
- **A leftover `.env` read fails loudly.** `dotenv.load_dotenv` is wrapped for
  the session: an argument-less call is refused outright, and an explicit path
  that *exists* outside the temp sandbox is refused by name. A path that does
  not exist passes through, so CI — which has no `.env` anywhere — is
  unaffected and the guard only speaks when there is something real to read.

### Opting out

`KIS_RUN_LIVE_INFRA_TESTS=1` — the switch that un-skips the `live_infra` tests
— makes the session non-hermetic and loads this checkout's `.env`, the
pre-#698 behavior. `TELEGRAM_*` stays scrubbed even then, so a live-infra run
still cannot message the operator from a test.

`tests/unit/config/test_dotenv_hermeticity.py` asserts all of the above, and
proves the loader half in subprocesses with the switch *off*, so it still
catches a regression in the entrypoints if the session guard is ever removed.

### Original (2026-05-09) analysis below

## TL;DR

Developers can speed up local test runs with:

```bash
pytest tests/ --ignore=tests/performance -n auto
```

`pytest-xdist` is in dev dependencies (`pip install -e ".[dev]"`).
**Do not enable `-n auto` in `.github/workflows/test.yml` without first
fixing the parallel-unsafe tests below.**

## Why CI keeps serial execution

Measured 2026-05-09 against main @ `5799213`:

| Mode | Time | Result |
|------|------|--------|
| Serial (CI default) | 8m 38s | 4304 pass, 0 fail |
| `-n auto` (16 workers) | 5m 28s | 4302–4303 pass, **1–2 random fail** |
| `-n auto --dist=loadfile` | 5m 28s | Still flaky |

The 36% time savings is meaningful but the random failures undermine
the recently-restored CI signal (PR #191–#195).  Verdict: **safe local
opt-in, not CI default**.

## Parallel-unsafe tests (need fixing before CI parallel)

Each of these passed serially and as a single-file parallel run, but
random-failed when run alongside the full suite under `-n auto`:

1. `tests/unit/resilience/test_circuit_breaker_properties.py::TestCircuitBreakerProperties::test_config_round_trip`
   - Hypothesis property test.  Likely Hypothesis database race
     between workers — the example database is shared by default
     so multiple workers compete on the same SQLite file.
   - Fix: configure per-worker `HYPOTHESIS_STORAGE_DIRECTORY` in
     `conftest.py` (e.g., `os.environ.setdefault("HYPOTHESIS_STORAGE_DIRECTORY", f"/tmp/hyp-{os.environ.get('PYTEST_XDIST_WORKER', 'master')}")`).

2. `tests/integration/test_graceful_shutdown.py::test_sigterm_during_trading`
   - Uses real Redis + signal handlers.  Two workers running this
     test simultaneously share the same Redis DB and the same
     `signal.signal()` global table.
   - Fix: either mark the test serial-only with a custom xdist
     group, or have it use a per-worker Redis DB / sentinel file.

3. Suspected (not confirmed in this audit): any test using the
   `MetricsCollector` or `CircuitBreaker` singletons concurrently.

## Recommended path forward

1. Phase 2 cutover stabilises (next 2 weeks).
2. After stable, fix the 2–3 confirmed parallel-unsafe tests above
   (Hypothesis per-worker DB + Redis worker isolation).
3. Smoke-run the full suite under `-n auto` for 5 consecutive runs
   without flakiness, then enable in CI by editing
   `.github/workflows/test.yml` to add `-n auto`.

## Local usage tips

- `pytest tests/unit/strategy/ -n auto` — for small directories the
  worker startup cost dominates and serial is faster.  Use parallel
  for the full suite.
- `pytest -n auto --dist=loadfile` — keeps tests from the same file
  on the same worker.  Slightly safer for tests that share file-level
  state but didn't help our flakiness.
- `pytest -n 4` — manually set worker count (default `auto` = CPU count
  which is overkill on most laptops).
