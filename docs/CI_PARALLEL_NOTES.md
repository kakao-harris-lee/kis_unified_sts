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

- **Entrypoints never walk.** Every `.env` load goes through
  `shared.config.dotenv_guard.load_project_dotenv()`, which reads at most
  `<cwd>/.env` and then `<checkout>/.env`. No ancestor directory is ever
  consulted, so a nested worktree cannot reach the checkout above it. Both
  orders existed before #698, chosen by invocation style, and every real
  invocation runs from the checkout root, where the two candidates are the
  same file.
- **The rule is enforced, not just written here.**
  `tests/unit/config/test_dotenv_call_gate.py` walks the AST of every `.py`
  file in the repository and rejects a call to or import of `load_dotenv`,
  `dotenv_values` or `find_dotenv` outside a four-entry allowlist. The runtime
  guard below only fires for modules a test imports, which is almost no script
  under `scripts/analysis/`; the gate covers the rest. Three helpers parse
  `.env` with their own line loop where no dotenv-shaped check can see them —
  each is registered in the same file with a reason, and the gate verifies
  each still consults `hermetic_mode_enabled`.
- **`KIS_TEST_HERMETIC` switches the loader off.** `tests/conftest.py` sets it
  at import time, before collection. It is the only knob this adds, it is a
  test switch rather than a configuration surface, and the paper/live runtime
  never sets it — with it unset the entrypoints behave exactly as before. The
  name and its truthy values live in `dotenv_guard` and are imported by the
  test-side helper, so the two halves of the switch cannot drift apart.
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
  default is `Path.cwd()`). Both pins, the scrub and the switch are written by
  one `_apply_hermetic_pins()` called from the import-time block and again
  from the session fixture, so a pin added to one is never missing from the
  other.
- **A stray token cache is detected by comparison, not by absence.** The
  session snapshots size and mtime of every place a token can land — the
  checkout root, the working directory, and `~/.cache/kis_token_*.json`, which
  two collectors hardcode — and the guard test fails only on a file this
  session created or rewrote. An absence check would fail forever on the
  primary checkout, which legitimately holds `.kis_token_real` (2026-07-08)
  and `.kis_token_mock` (2026-06-09) from ordinary host `sts` runs.
- **A leftover `.env` read fails loudly.** All three python-dotenv readers
  (`load_dotenv`, `dotenv_values`, `find_dotenv`) are wrapped for the session:
  an argument-less call is refused outright, a path that *exists* outside the
  temp sandbox is refused by name, and `find_dotenv` may walk but may not hand
  back a real file from outside it. A path that does not exist passes through,
  so CI — which has no `.env` anywhere — is unaffected and the guard only
  speaks when there is something real to read. Installing the guard also
  sweeps `sys.modules` to rebind names a plugin or `sitecustomize` imported
  with `from dotenv import load_dotenv` before `tests/conftest.py` ran.

### Opting out

`KIS_RUN_LIVE_INFRA_TESTS=1` — the switch that un-skips the `live_infra` tests
— makes the session non-hermetic and loads this checkout's `.env`, the
pre-#698 behavior. `TELEGRAM_*` stays scrubbed even then, so a live-infra run
still cannot message the operator from a test.

`tests/unit/config/test_dotenv_hermeticity.py` asserts all of the above, and
proves the loader half in subprocesses with the switch *off*, so it still
catches a regression in the entrypoints if the session guard is ever removed.
`tests/unit/test_cli_commands.py` covers the ordering the loader depends on:
`.env` must be read before the command modules capture `DEFAULT_DASHBOARD_URL`
as a Click default.

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
