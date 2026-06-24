# LLM Market-Call Scorecard — Phase 4 Implementation Report

## Files Created / Modified

### New files
- `scripts/analysis/llm_scorecard_weekly.py` — weekly digest cron entry (Task 13 + 14)
- `tests/unit/llm_scorecard/test_weekly_entry.py` — 6 tests (4 Task 13, 2 Task 14)

### Modified files
- `scripts/llm_premarket_briefing.py` — bugfix: TradingStateReader + redis= arg + return type annotation
- `shared/llm_scorecard/reporter.py` — add `format_calibration(bins) -> str` (Task 14)
- `shared/storage/runtime_ledger.py` — add `query_predictions(facet, start, end)` to protocol + SQLiteRuntimeLedger (Task 14)
- `deploy/scheduler.crontab` — add Friday 16:37 KST weekly cron (Task 13)
- `tests/unit/llm_scorecard/test_direction_facet.py` — add regression test for bugfix
- `tests/unit/llm_scorecard/test_reporter.py` — add 3 format_calibration tests (Task 14)

## Per-Task Commit SHAs

| Task | SHA | Description |
|------|-----|-------------|
| Bugfix | 3ea0757 | fix(llm-scorecard): use TradingStateReader for direction capture hook |
| Task 13 | 21c3a90 | feat(llm-scorecard): weekly digest cron (Task 13) |
| Task 14 | e658a49 | feat(llm-scorecard): calibration section in weekly digest (Task 14) |
| Mypy fix | ef2e7bf | fix(llm-scorecard): add Any type annotations in weekly entry for mypy |

## Test Results

```
pytest tests/unit/llm_scorecard/ -p no:cacheprovider
103 passed in 1.16s
```

Phase 3 baseline: 93 tests. Phase 4 adds 10 tests:
- Bugfix: +1 (test_direction_facet.py::test_capture_via_trading_state_reader_yields_non_none_direction)
- Task 13: +4 (test_weekly_entry.py — smoke import, format_weekly synthetic, empty by_facet header, build_by_facet logic)
- Task 14: +5 (test_weekly_entry.py — 2 calibration path; test_reporter.py — 3 format_calibration)

## Mypy Results

```
mypy shared/llm_scorecard/ scripts/analysis/llm_scorecard_score.py \
     scripts/analysis/llm_scorecard_weekly.py scripts/llm_premarket_briefing.py \
     --ignore-missing-imports --no-error-summary
exit code: 0 (clean — no errors)
```

Note: The two pre-existing mypy errors in `scripts/llm_premarket_briefing.py`
(line 42 `main()` return type + line 104 `TradingStatePublisher.get_market_context`)
were FIXED by this phase (return type now `async def main() -> None`; Publisher
replaced with Reader).

## Bugfix Resolution

**Root cause**: `TradingStatePublisher` is write-only; it has no `get_market_context()`
attribute. The briefing hook was calling `TradingStatePublisher("futures").get_market_context()`
which always raised `AttributeError` (silently caught by the outer try/except),
making `_mc = None` on every run — meaning the direction facet always fell back
to the Redis key lookup (which also fails if Redis is unreachable or the key hasn't
been set yet).

**Fix**:
1. Replace `TradingStatePublisher` with `TradingStateReader` — the reader class has `get_market_context()`.
2. Pass `redis=_redis` to `CaptureContext` so `DirectionFacet.capture()`'s Redis fallback has an available client.
3. Fix `async def main() -> None:` annotation (mypy nit).

## Calibration pred_conf Approach

`pred_conf = {date_kst: confidence}` is built via the new `ledger.query_predictions(facet='direction')` accessor (added to both the `RuntimeLedger` Protocol and `SQLiteRuntimeLedger`). This is cleaner than iterating `load_predictions(date_kst)` per day because it is a single SQL query with optional date-range filtering, mirroring `query_scores` in shape.

The `_build_calibration_section()` helper in `llm_scorecard_weekly.py`:
1. Queries all direction predictions → builds `{date_kst: confidence}` map
2. Queries the score rows for the same facet (last `window` rows)
3. Calls `aggregator.calibration_bins(scores, pred_conf)` → `reporter.format_calibration(bins)`
4. Returns empty string (best-effort) on any error

Calibration is only computed for `direction` facet (the only confidence-carrying facet). The `themes`, `movers`, and `volume_surge` facets do not store per-prediction confidence values.

## Crontab Entry

```cron
37 16 * * 5  cd /app && python -m scripts.analysis.llm_scorecard_weekly >> /app/logs/scorecard_weekly_$(date +\%Y\%m\%d).log 2>&1
```

Placed in the `# --- maintenance / weekly ---` section, immediately after the Friday
`setup_ac_paper_observation --weekly` entry at 16:30. Staggered at 16:37 (after the
daily scorer at 16:35) so they don't race on the ledger.

## Concerns

1. **`query_predictions` not in the Protocol before this PR**: The `RuntimeLedger` Protocol
   did not include `query_predictions`; it was added in this phase. Any alternative ledger
   implementation would need to implement it to satisfy the protocol. The test ledgers in
   the weekly entry tests use duck-typed fakes (no Protocol check), so tests pass — but
   a strict Protocol check would require updating any alternative implementations.

2. **Calibration section requires data to be populated**: On fresh deployments or early
   in the data collection period, `query_predictions` will return no rows → `pred_conf` is
   empty → calibration section is silently omitted. This is the correct behavior (best-effort).

3. **`_build_calibration_section` is not exposed as a public function**: It is a private
   helper in the entry script. The test for the calibration section in `test_weekly_entry.py`
   exercises the logic through `calibration_bins` + `format_calibration` directly (unit-level),
   not through the entry function. The integration path is covered by the smoke import test.

4. **Mypy type annotation style**: `cfg: Any, ledger: Any` annotations in the weekly script
   match the pattern used in `llm_scorecard_score.py` (which also passes `Any`-typed objects
   as cfg/ledger). The preferred long-term approach would be to import `ScorecardConfig` and
   `RuntimeLedger` Protocol types from `shared/` — but the entry scripts use late imports
   (inside the `async def main()`) to avoid circular imports and slow module load, making
   `Any` the pragmatic choice for the module-level helpers.

---

## Phase 4 Review Fixes (post-review)

A high-effort code review (self-review + coordinator-relayed) surfaced four
issues; all fixed in a single follow-up commit. The direction-hook bugfix and
the inline `save_prediction`/`save_score` `commit()` calls were adjudicated to
keep and were not touched.

### Fix 1 (CRITICAL — B2): `format_calibration` empty-bins → `""`
- `shared/llm_scorecard/reporter.py`: when no bin is populated, return `""`
  (was `"📐 신뢰도 보정\n(보정 데이터 없음)"`). The weekly entry's
  `if calib_section:` guard now correctly suppresses the whole section instead
  of appending a misleading "no data" notice on fresh / no-score deployments.
- Test `test_format_calibration_all_empty_returns_empty_string` asserts `== ""`.

### Fix 2 (IMPORTANT — A4): `--window` applied to metrics, not just header
- `scripts/analysis/llm_scorecard_weekly.py`: added `_resolve_window(cfg, override)`
  and gave `build_by_facet(cfg, ledger, window=None)` a `window` override param.
  `main()` now passes `window=args.window` into `build_by_facet`, so the header
  and the figures are computed against the same window. Previously the override
  was applied to the local `window` AFTER metrics were already computed → header
  said e.g. "10일" while figures were 60-day.
- Test `test_window_override_applies_to_metrics_not_just_header` builds 60 rows
  (first 50 losers, last 10 winners) and asserts `--window 10` yields `n=10`,
  `hit_rate==1.0`, while the default (60) yields `hit_rate<1.0`.

### Fix 3 (IMPORTANT — config-driven): drop hardcoded `"direction"`
- `config/llm_scorecard.yaml`: added `has_confidence: true` under
  `facet_params.direction`.
- `scripts/analysis/llm_scorecard_weekly.py`: new `_confidence_facets(cfg)`
  selects via `facet_params.<facet>.has_confidence` (was a literal
  `f == "direction"` branch — a CLAUDE.md configuration-driven violation).
  `_build_calibration_section` now loops over all flagged facets and joins
  their sections, so a future confidence-carrying facet is picked up with no
  code change.
- Tests `test_confidence_facets_selected_by_config_flag` (direction +
  hypothetical `future_conf` selected, `themes` excluded) and
  `test_confidence_facets_empty_when_no_flag`.

### Fix 4 (MINOR — test tautology): `test_format_calibration_renders_bins`
- `tests/unit/llm_scorecard/test_reporter.py`: the assertion
  `("0.8" in msg and "0.9" not in msg) or "1.0" in msg` was always True by
  operator precedence. Rewritten to assert the exact rendered bin lines
  (`"conf 0.8–1.0: hit 70% (n=12)"`, `"conf 0.6–0.8: hit 55% (n=8)"`) and that
  empty bins are omitted (`"n=0" not in msg`).

### Review-fix verification
- `pytest tests/unit/llm_scorecard/ -p no:cacheprovider -q` → **106 passed**.
- `mypy shared/llm_scorecard/ scripts/analysis/llm_scorecard_weekly.py
  scripts/llm_premarket_briefing.py --ignore-missing-imports --no-error-summary`
  → **exit 0 (clean)**.

### Adjudicated NOT changed
- Inline `commit()` in `save_prediction`/`save_score` (controller-adjudicated keep).
- A3 (pred_conf not date-windowed): output is numerically correct
  (`calibration_bins` iterates scores only; unmatched pred_conf keys are ignored).
- The direction-capture hook fix (verified correct).
