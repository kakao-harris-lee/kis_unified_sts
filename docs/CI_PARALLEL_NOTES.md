# CI Parallel Test Execution — Notes

**Status**: Available locally, NOT enabled in CI (2026-05-09).

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
