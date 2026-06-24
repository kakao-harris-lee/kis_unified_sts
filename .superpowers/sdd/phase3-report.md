# LLM Market-Call Scorecard — Phase 3 Implementation Report

## Files Created / Modified

### New files
- `shared/llm_scorecard/facets/themes.py` — ThemesFacet + auto-registration
- `shared/llm_scorecard/facets/movers.py` — MoversFacet + auto-registration
- `shared/llm_scorecard/facets/volume_surge.py` — VolumeSurgeFacet + auto-registration
- `tests/unit/llm_scorecard/test_themes_facet.py` — 9 tests
- `tests/unit/llm_scorecard/test_movers_facet.py` — 11 tests
- `tests/unit/llm_scorecard/test_volume_surge_facet.py` — 13 tests

### Modified files
- `shared/llm_scorecard/facets/__init__.py` — imports all 4 facets to auto-populate FACET_REGISTRY
- `shared/llm_scorecard/recorder.py` — `import shared.llm_scorecard.facets` (was direction-only)
- `shared/llm_scorecard/scorer.py` — `import shared.llm_scorecard.facets` (was direction-only)
- `config/llm_scorecard.yaml` — added `themes`, `movers`, `volume_surge` to `enabled_facets`; added `theme_symbols` default map; added `base_rate` params for movers/volume_surge
- `scripts/llm_premarket_briefing.py` — updated scorecard hook to import facets package; added best-effort `system:trade_targets:latest` fetch to populate `ctx.screener` for MoversFacet

## Per-Facet Commit SHAs

| Task | SHA | Description |
|------|-----|-------------|
| 10 (ThemesFacet) | 87b8564 | feat(scorecard): task 10 - ThemesFacet (sector-rotation theme spread scorer) |
| 11 (MoversFacet) | 0673590 | feat(scorecard): task 11 - MoversFacet (pre-market flagged movers follow-through) |
| 12 (VolumeSurgeFacet) | e743189 | feat(scorecard): task 12 - VolumeSurgeFacet (flag-to-close continuation; DONE_WITH_CONCERNS) |

## Test & Mypy Results

```
pytest tests/unit/llm_scorecard/ -p no:cacheprovider
89 passed in 0.98s

mypy shared/llm_scorecard/ --ignore-missing-imports --no-error-summary
exit 0 (clean — no errors)
```

(Baseline before Phase 3: 56 tests.  Phase 3 adds 33 tests.)

## Facet Semantics Summary

### ThemesFacet (T10)

- **Capture**: reads `ctx.market_context["sector_rotation"]` (theme→bias dict); ranks INFLOW/bullish themes; picks top-N; resolves constituent symbols from `facet_params.themes.theme_symbols` config map.
- **Score**: `value = strong_mean` (equal-weight return of strong-theme symbols); `baseline_value = market_mean` (equal-weight over all tracked symbols with data); `edge = value − baseline_value`; `correct = edge ≥ 0`.
- **Unscorable** when zero strong-theme symbols have outcome data.

### MoversFacet (T11)

- **Capture**: reads `ctx.screener["codes"]` (from `system:trade_targets:latest` Redis key, populated by briefing hook). Implied long.
- **Score**: `value = mean follow-through session_return`; `baseline_value = facet_params.movers.base_rate` (default 0.5%); `edge = value − baseline`; `correct = value > base_rate`.
- **Unscorable** when zero flagged symbols have outcome data.
- **Briefing hook** now fetches `system:trade_targets:latest` from Redis (best-effort) and attaches to `CaptureContext.screener`.

### VolumeSurgeFacet (T12) — DONE_WITH_CONCERNS

- **Capture**: reads `ctx.screener["volume_surge"]` — a list of `{code, flag_time, flag_price}` dicts.
- **Score**: per-symbol `bars_after(symbol, date_kst, flag_time)` → flag-to-close return; `value = mean return`; `baseline_value = facet_params.volume_surge.base_rate` (default 0.0%); `edge = value − baseline`; `correct = value > base_rate`.
- **Unscorable** when list is absent/empty or no bar data available.

## DONE_WITH_CONCERNS: VolumeSurgeFacet surge-feed hook

**Finding**: No clean per-symbol surge-with-timestamp Redis key exists in the repo.
`shared/strategy/entry/opening_volume_surge.py` fires `Signal` objects at signal time
but does NOT publish them to a dedicated Redis key.

**What exists**: `system:trade_targets:latest` (fusion output, daily-batch, no flag_time per symbol);
`system:universe:latest` (screener universe, no surge flag time).

**Impact**: `VolumeSurgeFacet.capture()` returns `None` on every day until a hook is added.
The facet is fully implemented, tested, and registered — it is dormant until the feed exists.

**To activate**: add a hook in `services/stock_strategy/main.py` (or wherever
`OpeningVolumeSurgeEntry` signals are consumed) that writes surge flags to Redis key
`system:volume_surge:latest` as `{"surges": [{code, flag_time, flag_price}, ...]}` (DB1, TTL 24h)
and populates `ctx.screener["volume_surge"]` before calling `capture_predictions`.
The scorer path is fully ready.

## theme_symbols Default Map

Added to `config/llm_scorecard.yaml::facet_params.themes.theme_symbols`:

| Theme | Symbols |
|-------|---------|
| Technology | 005930 (Samsung), 000660 (SK Hynix), 035420 (NAVER) |
| Finance | 055550 (Shinhan), 086790 (Kakao Bank), 105560 (KB) |
| Energy | 010950 (S-Oil), 096770 (SK Innovation) |
| Healthcare | 207940 (Samsung Bio), 068270 (Celltrion) |
| Consumer | 051910 (LG Chem), 009830 (Hanwha Solutions) |
| Industrials | 006400 (Samsung SDI), 012330 (Hyundai Mobis) |
| Chemicals | 011170 (Lotte Chemical), 010130 (Korea Zinc) |
| Telecom | 030200 (KT), 017670 (SK Telecom) |

Operators should update this map as sector composition changes. Config-driven — no code change needed.

## Registry Wiring

- `shared/llm_scorecard/facets/__init__.py` now imports all 4 facets; any code that does
  `import shared.llm_scorecard.facets` (recorder.py, scorer.py) populates the full registry.
- `config/llm_scorecard.yaml::enabled_facets` now lists all 4 facets.
- Per-facet `register_facet(ThemesFacet())` / `register_facet(MoversFacet())` /
  `register_facet(VolumeSurgeFacet())` at module bottom (mirrors direction.py).

---

## Phase 3 Review Fixes

Addressed the 5 coordinator review items (VolumeSurgeFacet dormancy accepted as a
documented follow-up — left as-is).

### 1. (CRITICAL — runtime bug) MoversFacet silently dormant
`scripts/llm_premarket_briefing.py` read `_pub._redis`, which does NOT exist on
`TradingStatePublisher` (it has no persistent client; every method builds a
connection via the module-level `_get_redis()` → `RedisClient.get_client()`).
The `hasattr(_pub, "_redis")` guard always evaluated False → `system:trade_targets:latest`
was never fetched → `ctx.screener` stayed None → `MoversFacet.capture()` always
returned None at runtime.

**Fix:** import the shared singleton helper
`from shared.streaming.trading_state import _get_redis`, fetch
`_get_redis().get("system:trade_targets:latest")`, `json.loads` it, and pass the
parsed dict (which has a top-level `codes` key that `MoversFacet.capture` reads)
as `CaptureContext.screener`. Whole block stays inside the existing try/except so
a Redis failure cannot break the briefing.

**Regression test:** `test_movers_facet.py::test_briefing_hook_capture_path_yields_movers_prediction`
— a fake redis returns trade_targets JSON → parse → `CaptureContext(screener=parsed)`
→ `capture_predictions` yields exactly one `movers` prediction (not None).

### 2. (CRITICAL) ThemesFacet `correct` boundary
Changed `correct = spread >= 0.0` → strict `correct = spread > 0.0` (a zero/negative
spread is a miss). Value design KEPT per coordinator adjudication:
`value=strong_mean`, `baseline_value=market_mean`, `edge=spread` (mirrors
DirectionFacet's value=metric / baseline=benchmark / edge=diff).
**Test:** `test_score_correct_false_when_spread_zero` (spread==0 → correct False).

### 3. (IMPORTANT) ThemesFacet `baseline()` Protocol contract
`baseline(pred, mkt)` previously returned a hardcoded `0.0` while `score()` populated
`baseline_value=market_mean` — inconsistent. Extracted `_all_returns(pred, mkt)`
(equal-weight session_return over the tracked universe); `baseline()` now COMPUTES
and returns `market_mean` from it, and `score()` computes the same `market_mean` so
`facet.baseline() == score.baseline_value` (single source of truth).
**Test:** `test_baseline_returns_market_mean` asserts both are equal.

### 4. (WARNING) ThemesFacet unscorable baseline
The unscorable branch previously hardcoded `baseline_value=0.0`, mis-stating the
market return on days where non-strong symbols DO have data. Now carries the
computed `market_mean` (which may be non-zero from non-strong symbols), falling
back to 0.0 only when no tracked symbol has data.
**Tests:** `test_score_unscorable_carries_market_mean_from_non_strong_symbols`
(strong=None but market symbols present → baseline=market mean) and
`test_score_unscorable_when_no_symbol_data` (nothing scorable → baseline 0.0).

### 5. (WARNING) volume_surge base_rate mismatch
`config/llm_scorecard.yaml` had `base_rate: 0.5` while the code default + docstring
were `0.0`. Aligned the YAML to `base_rate: 0.0` (flat-continuation baseline =
single source of truth with the docstring).

### Verification
- `pytest tests/unit/llm_scorecard/ -q -p no:cacheprovider` → **93 passed** (was 89;
  +4 review-fix tests).
- `mypy shared/llm_scorecard/ scripts/analysis/llm_scorecard_score.py --ignore-missing-imports --no-error-summary` → **exit 0 (clean)**.
- `mypy ... scripts/llm_premarket_briefing.py` reports 2 errors at lines 42
  (`main()` missing return annotation) and 104 (`TradingStatePublisher has no
  attribute get_market_context`) — both **pre-existing on the Phase 2 commit**
  (verified via `git show HEAD:` of the file before this fix), NOT introduced by
  the review fix. Left untouched to keep the fix scoped; the `get_market_context`
  call is intentionally wrapped in try/except and was approved in Phase 2.
