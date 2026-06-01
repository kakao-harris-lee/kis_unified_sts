# Stock Approximation-Template Seeds — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4 explicitly-labeled "approximation" stock strategy templates to the builder's preset list so users can start NEW builder_v1 strategies from the expressible indicator subset of the running coded strategies.

**Architecture:** Data + tiny UI. Add 4 presets to `config/strategy_builder/kis_presets.yaml` (each a camelCase `builder_state` using only catalog indicators, conditions designed so each forces a disjoint series → passes the existing all-presets-must-BUY test). Add an amber "근사" badge in the builder preset list for `category === "근사 템플릿"`. No backend logic change.

**Tech Stack:** YAML config; Python (Pydantic `BuilderState`, pytest via `.venv/bin/pytest`); Next.js/React/TS (verify via `npx tsc --noEmit` + `npm run build`).

**Spec:** `docs/superpowers/specs/2026-06-01-builder-stock-approx-templates-design.md`
**Branch:** `feat/builder-stock-approx-templates` (off `main`).

---

## Key facts (verified)
- Presets live in `config/strategy_builder/kis_presets.yaml` under `strategy_builder_kis.presets[]`. Each: `{id, name, description, category, params, builder_state}`. Loaded by `list_kis_strategy_infos()` → `GET /api/kis-builder/strategies`; selecting one calls `builder.loadState(builder_state)` in `page.tsx`.
- builder_state is **camelCase** (`indicatorId`, `indicatorAlias`, `indicatorOutput`, `stopLoss`); operands: `{type: indicator, indicatorAlias, indicatorOutput}` / `{type: value, value}` / `{type: price, priceField}`; operators: `greater_than|less_than|greater_equal|less_equal|cross_above|cross_below|equals`.
- Indicators referenced exist in the frontend catalog `constants.ts`: `williams_r`(param period; output value), `bollinger`(params period,std; outputs upper/middle/lower), `rsi`(period; value), `macd`(fast,slow,signal; outputs value/signal/histogram), `sma`(period; value), `vwap`(period; value).
- **CRITICAL test constraint:** `tests/unit/strategy_builder/test_kis_compat.py::test_kis_builder_states_convert_and_generate_sample_buy_signals` iterates **every** preset and asserts it generates a BUY on a synthetic series from `build_sample_series_for_state`, whose `_force_condition_pass` processes entry conditions independently and **overwrites shared series**. ⇒ each entry condition in a template MUST force a **disjoint** series. The 4 templates below satisfy this.
- `test_kis_presets_include_readme_strategy_set` uses `{...} <= strategy_ids` (subset) → adding presets does NOT break it.
- Preset render in `page.tsx` (~lines 337-356): a `<button>` per preset showing `{preset.name}` + `{preset.category}`. `BackendPresetStrategy` already carries `category`.

---

## Task 1: Add the 4 approximation presets + parse/label test

**Files:**
- Modify: `config/strategy_builder/kis_presets.yaml` (append 4 presets under `presets:`)
- Test: `tests/unit/strategy_builder/test_kis_compat.py` (append one test)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/strategy_builder/test_kis_compat.py`:

```python
def test_approx_templates_present_parse_and_labeled():
    """The 4 stock approximation templates exist, are labeled '근사 템플릿',
    target stock, and their builder_state parses as a BuilderState."""
    from shared.strategy_builder.schema import BuilderState

    infos = {s["id"]: s for s in list_kis_strategy_infos()}
    approx_ids = {
        "approx_williams_r",
        "approx_technical_consensus",
        "approx_trend_vwap",
        "approx_pattern_pullback",
    }
    assert approx_ids <= set(infos), f"missing: {approx_ids - set(infos)}"

    for aid in approx_ids:
        preset = get_kis_preset(aid)
        assert preset is not None
        assert preset["category"] == "근사 템플릿", aid
        assert "동일" in preset["description"], aid  # "동일하게 동작하지 않음" warning
        state = BuilderState.model_validate(preset["builder_state"])
        assert state.asset_class == "stock", aid
        assert len(state.entry.conditions) >= 2, aid
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/unit/strategy_builder/test_kis_compat.py::test_approx_templates_present_parse_and_labeled -v`
Expected: FAIL (`missing: {...}` — presets not added yet).

- [ ] **Step 3: Append the 4 presets to `config/strategy_builder/kis_presets.yaml`**

Add these as new list items under `strategy_builder_kis.presets:` (match existing 2-space list indentation). Each entry's conditions force disjoint series (see comments):

```yaml
    - id: approx_williams_r
      name: Williams %R 반전 (근사)
      description: "⚠️ 실제 williams_r 전략의 표현가능 지표 조건만 근사한 시작 템플릿입니다. 실제 전략과 동일하게 동작하지 않습니다(2-bar 반전 상태·종목별 cooldown·confidence 스케일 제외). 빌더에서 자유롭게 수정하세요."
      category: 근사 템플릿
      params: []
      builder_state:
        metadata:
          id: approx_williams_r
          name: Williams %R 반전 (근사)
          description: "williams_r 근사 — 실제 전략과 동일하지 않음"
          category: custom
          tags: [approx, williams_r, oscillator]
          author: STS
        asset_class: stock
        indicators:
          - id: wr_1
            indicatorId: williams_r
            alias: wr
            params: {period: 14}
            output: value
          - id: bb_1
            indicatorId: bollinger
            alias: bb
            params: {period: 20, std: 2}
            output: middle
        entry:
          logic: AND
          conditions:
            - id: e1   # forces: wr.value
              left: {type: indicator, indicatorAlias: wr, indicatorOutput: value}
              operator: cross_above
              right: {type: value, value: -80}
            - id: e2   # forces: close, bb.middle
              left: {type: price, priceField: close}
              operator: greater_than
              right: {type: indicator, indicatorAlias: bb, indicatorOutput: middle}
        exit:
          logic: AND
          conditions: []
        risk:
          stopLoss: {enabled: true, percent: 5}
          takeProfit: {enabled: false, percent: 10}
          trailingStop: {enabled: false, percent: 3}

    - id: approx_technical_consensus
      name: 기술적 합의 (근사)
      description: "⚠️ 실제 technical_consensus 전략의 표현가능 지표 조건만 근사한 시작 템플릿입니다. 실제 전략과 동일하게 동작하지 않습니다(N-of-M 가중 투표·종목별 cooldown 제외). 빌더에서 자유롭게 수정하세요."
      category: 근사 템플릿
      params: []
      builder_state:
        metadata:
          id: approx_technical_consensus
          name: 기술적 합의 (근사)
          description: "technical_consensus 근사 — 실제 전략과 동일하지 않음"
          category: custom
          tags: [approx, consensus, rsi, macd, williams_r]
          author: STS
        asset_class: stock
        indicators:
          - id: rsi_1
            indicatorId: rsi
            alias: rsi
            params: {period: 14}
            output: value
          - id: macd_1
            indicatorId: macd
            alias: macd
            params: {fast: 12, slow: 26, signal: 9}
            output: histogram
          - id: wr_1
            indicatorId: williams_r
            alias: wr
            params: {period: 14}
            output: value
        entry:
          logic: AND
          conditions:
            - id: e1   # forces: rsi.value
              left: {type: indicator, indicatorAlias: rsi, indicatorOutput: value}
              operator: greater_than
              right: {type: value, value: 35}
            - id: e2   # forces: macd.histogram
              left: {type: indicator, indicatorAlias: macd, indicatorOutput: histogram}
              operator: greater_than
              right: {type: value, value: 0}
            - id: e3   # forces: wr.value
              left: {type: indicator, indicatorAlias: wr, indicatorOutput: value}
              operator: greater_than
              right: {type: value, value: -80}
        exit:
          logic: AND
          conditions: []
        risk:
          stopLoss: {enabled: true, percent: 5}
          takeProfit: {enabled: false, percent: 10}
          trailingStop: {enabled: false, percent: 3}

    - id: approx_trend_vwap
      name: VWAP 추세 지속 (근사)
      description: "⚠️ 실제 trend_continuation_vwap 전략의 표현가능 지표 조건만 근사한 시작 템플릿입니다. 실제 전략과 동일하게 동작하지 않습니다(regime 게이트·KST 시간창·RVOL·종목별 cooldown 제외). 빌더에서 자유롭게 수정하세요."
      category: 근사 템플릿
      params: []
      builder_state:
        metadata:
          id: approx_trend_vwap
          name: VWAP 추세 지속 (근사)
          description: "trend_continuation_vwap 근사 — 실제 전략과 동일하지 않음"
          category: custom
          tags: [approx, vwap, trend, sma]
          author: STS
        asset_class: stock
        indicators:
          - id: sma_20
            indicatorId: sma
            alias: sma_20
            params: {period: 20}
            output: value
          - id: sma_60
            indicatorId: sma
            alias: sma_60
            params: {period: 60}
            output: value
          - id: vwap_1
            indicatorId: vwap
            alias: vwap
            params: {period: 14}
            output: value
        entry:
          logic: AND
          conditions:
            - id: e1   # forces: sma_20.value, sma_60.value
              left: {type: indicator, indicatorAlias: sma_20, indicatorOutput: value}
              operator: greater_than
              right: {type: indicator, indicatorAlias: sma_60, indicatorOutput: value}
            - id: e2   # forces: close, vwap.value
              left: {type: price, priceField: close}
              operator: greater_than
              right: {type: indicator, indicatorAlias: vwap, indicatorOutput: value}
        exit:
          logic: AND
          conditions: []
        risk:
          stopLoss: {enabled: true, percent: 5}
          takeProfit: {enabled: false, percent: 10}
          trailingStop: {enabled: false, percent: 3}

    - id: approx_pattern_pullback
      name: 추세 내 눌림목 (근사)
      description: "⚠️ 실제 pattern_pullback 전략의 표현가능 지표 조건만 근사한 시작 템플릿입니다. 실제 전략과 동일하게 동작하지 않습니다(다중 패턴 랭킹·60일 수익률·ATR%·종목별 cooldown 제외). 빌더에서 자유롭게 수정하세요."
      category: 근사 템플릿
      params: []
      builder_state:
        metadata:
          id: approx_pattern_pullback
          name: 추세 내 눌림목 (근사)
          description: "pattern_pullback 근사 — 실제 전략과 동일하지 않음"
          category: custom
          tags: [approx, pullback, sma, rsi]
          author: STS
        asset_class: stock
        indicators:
          - id: sma_200
            indicatorId: sma
            alias: sma_200
            params: {period: 200}
            output: value
          - id: rsi_1
            indicatorId: rsi
            alias: rsi
            params: {period: 14}
            output: value
        entry:
          logic: AND
          conditions:
            - id: e1   # forces: close, sma_200.value
              left: {type: price, priceField: close}
              operator: greater_than
              right: {type: indicator, indicatorAlias: sma_200, indicatorOutput: value}
            - id: e2   # forces: rsi.value
              left: {type: indicator, indicatorAlias: rsi, indicatorOutput: value}
              operator: less_than
              right: {type: value, value: 45}
        exit:
          logic: AND
          conditions: []
        risk:
          stopLoss: {enabled: true, percent: 5}
          takeProfit: {enabled: false, percent: 10}
          trailingStop: {enabled: false, percent: 3}
```

- [ ] **Step 4: Run the new test + the existing all-presets-BUY test**

Run: `.venv/bin/pytest tests/unit/strategy_builder/test_kis_compat.py -v`
Expected: ALL pass — including `test_approx_templates_present_parse_and_labeled` AND `test_kis_builder_states_convert_and_generate_sample_buy_signals` (the 4 new presets each generate a sample BUY because each entry condition forces a disjoint series). If a new preset fails the BUY test, the most likely cause is two conditions touching the same series — re-check the `# forces:` comments are disjoint.

- [ ] **Step 5: Commit**

```bash
git add config/strategy_builder/kis_presets.yaml tests/unit/strategy_builder/test_kis_compat.py
git commit -m "feat(builder): add 4 stock approximation-template presets

williams_r / technical_consensus / trend_continuation_vwap / pattern_pullback
approximations (expressible indicator subset only), labeled '근사 템플릿' with a
not-identical warning. Conditions force disjoint series so each passes the
all-presets-must-BUY sample test.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 2: Amber "근사" badge in the preset list

**Files:**
- Modify: `strategy-builder-ui/src/app/builder/page.tsx`

- [ ] **Step 1: Add the badge to the preset name row**

In the preset `.map((preset) => (...))` block (the `<button>` ~lines 337-356), replace the name `<div>`:
```tsx
                      <div className="font-medium text-sm text-slate-900 dark:text-white truncate">
                        {preset.name}
                      </div>
```
with a version that appends an amber badge for approximation templates:
```tsx
                      <div className="font-medium text-sm text-slate-900 dark:text-white truncate flex items-center gap-1.5">
                        <span className="truncate">{preset.name}</span>
                        {preset.category === "근사 템플릿" && (
                          <span
                            className="px-1.5 py-0.5 text-[10px] font-medium bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 rounded whitespace-nowrap flex-shrink-0"
                            title="실제 전략의 근사 — 동일하게 동작하지 않음"
                          >
                            근사
                          </span>
                        )}
                      </div>
```
(`BackendPresetStrategy` already carries `category` from the API mapping in the `loadStrategies` effect.)

- [ ] **Step 2: Typecheck + build**

Run: `cd strategy-builder-ui && npx tsc --noEmit && npm run build`
Expected: build succeeds, no new errors.

- [ ] **Step 3: Commit**

```bash
git add strategy-builder-ui/src/app/builder/page.tsx
git commit -m "feat(builder-ui): amber '근사' badge for approximation-template presets

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 3: Verify + PR

- [ ] **Step 1: Backend suite**

Run: `.venv/bin/pytest tests/unit/strategy_builder/ -v`
Expected: PASS (kis_compat incl. new test + sample-BUY; schema; yaml/evaluator).

- [ ] **Step 2: Lint/format**

Run: `cd strategy-builder-ui && npm run lint` (no new issues) and from repo root `.venv/bin/ruff check tests/unit/strategy_builder/test_kis_compat.py` (clean).

- [ ] **Step 3: Manual smoke (optional, dashboard running)**

Open `/builder` (stock mode). The "기본 전략" list shows the 4 "(근사)" templates with an amber "근사" badge. Selecting one loads its indicators/conditions into the canvas (asset_class stock). Saving/registering produces a builder_v1 strategy.

- [ ] **Step 4: Push & open PR**

```bash
git push -u origin feat/builder-stock-approx-templates
gh pr create --base main --title "feat(builder): stock approximation-template seeds" \
  --body "Adds 4 explicitly-labeled '근사' stock templates (williams_r / technical_consensus / trend_continuation_vwap / pattern_pullback) to the builder presets so users can start new builder_v1 strategies from the expressible indicator subset. Generation aid, not sync — labeled not-identical (name + category + warning + amber badge). No backend logic change. Spec: docs/superpowers/specs/2026-06-01-builder-stock-approx-templates-design.md"
```

---

## Acceptance criteria mapping (from spec §5)
| Spec criterion | Task |
|---|---|
| 4 templates visible with amber "근사" badge | 1 (presets), 2 (badge) |
| Selecting loads indicators/conditions (asset_class=stock) | 1 (builder_state) |
| description states "동일하지 않음" + exclusions | 1 (description text) |
| momentum_breakout NOT a template | (not added) |
| 4 builder_states parse as BuilderState | 1 (test) |
| existing presets unregressed; build green | 1 (subset test), 2, 3 |

## Notes
- The conditions are deliberately a **conflict-free starting subset** (each forces a disjoint series so the all-presets-BUY test passes); the spec §3 documents which real-strategy conditions were dropped and why. Users are expected to tune in the canvas.
- Runtime indicator availability at paper time (e.g. williams_r for stock) is handled by the orchestrator's IndicatorEngine for stock strategies; out of scope here (same as any builder strategy).
