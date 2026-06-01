# 빌더 — 주식 전략 근사 템플릿 시드 (Approximation Template Seeds)

- **작성일**: 2026-06-01
- **상태**: 설계 승인됨 (구현 계획 대기)
- **관련**: `docs/superpowers/specs/2026-06-01-builder-readonly-strategy-panel-design.md` (읽기전용 패널, PR #386), `docs/STRATEGY_BUILDER_UI.md`

---

## 1. 배경 & 목표

현재 운용 중인 주식 전략(`config/strategies/stock/`)은 전부 **코드 기반 entry 클래스**이며 빌더의
`BuilderState`(선언적 조건 모델)로 **충실히 표현·편집할 수 없다**(다중-bar 상태, N-of-M 투표, regime
메타데이터, 스크리너 watchlist, lookback 피처 등). 따라서 편집형 동기화는 비목표다.

대신, 운용 중인 표현 가능한 전략들의 **표현 가능한 지표 조각**(RSI/SMA/VWAP/교차/오실레이터 조건)을
**"근사 템플릿"** 으로 빌더에 시드하여, 사용자가 그걸 시작점으로 **신규 builder_v1 주식 전략을 생성**할 수
있게 한다. 이는 **생성 보조이지 동기화가 아니며**, 실제 전략과 동일하게 동작하지 않음을 **명시적으로
라벨링**한다.

### 핵심 사실 (조사 결과)
- 빌더 "기본 전략" 프리셋은 `GET /api/kis-builder/strategies` → `list_kis_strategy_infos()` → `config/strategy_builder/kis_presets.yaml`(`strategy_builder_kis.presets[]`)에서 온다. 각 entry: `{id, name, description, category, params, builder_state(camelCase)}`. 선택 시 `builder.loadState(preset.state)`로 캔버스에 로드된다(`page.tsx` handleSelectPreset).
- 프리셋은 현재 자산군 토글로 필터되지 않는다(모든 모드에서 보임).
- 빌더 UI(`/builder`)는 프론트 카탈로그 `strategy-builder-ui/src/lib/builder/constants.ts`(80개)로 지표를 렌더한다. `williams_r`(line 264), rsi/sma/macd/bollinger/vwap/atr 모두 존재. (백엔드 `indicators.yaml`은 10개로 더 작고 williams_r 없음 — 그러나 프리셋 렌더는 프론트 카탈로그 기준이므로 무관.)
- builder_state 형식(예: golden_cross): `indicators: [{id, indicatorId, alias, params, output}]`, `entry/exit: {logic, conditions: [{id, left, operator, right}]}`. 오퍼랜드: `{type: indicator, indicatorAlias, indicatorOutput}` / `{type: value, value}` / `{type: price, priceField}`. 연산자: greater_than/less_than/greater_equal/less_equal/cross_above/cross_below/equals.

→ **사실상 config(kis_presets.yaml) 추가 + 작은 프론트 배지 1건.** 백엔드 로직 변경 없음.

---

## 2. 스코프 & 비목표

### 대상 (In Scope)
- `config/strategy_builder/kis_presets.yaml`에 **주식 근사 템플릿 4개** 추가 — 현재 enabled & 표현가능한 전략 기준: `williams_r`, `technical_consensus`, `trend_continuation_vwap`, `pattern_pullback`.
- 각 템플릿: 표현 가능한 지표 조건만 담은 `builder_state`(asset_class=stock) + **"근사·비동일" 라벨**(이름 "(근사)" + `category: 근사 템플릿` + 경고성 description).
- 프론트 작은 변경: `category === "근사 템플릿"` 프리셋에 앰버 **"근사" 배지** 표시.

### 비목표 (Out of Scope)
- ❌ 코드 전략을 BuilderState로 충실히 변환/동기화 (표현 불가).
- ❌ `momentum_breakout` 템플릿 (스크리너·N일 고가·regime 의존 → 표현 불가, 제외).
- ❌ 프리셋 자산군 필터링(별도 기능; 템플릿은 라벨 + asset_class=stock로 충분).
- ❌ 백엔드 엔드포인트/로직 변경 (kis_presets.yaml 데이터만).
- ❌ 선물 근사 템플릿(이번 범위는 주식).

---

## 3. 설계

### A. 템플릿 정의 (표현 가능한 조각만)
모든 조건은 빌더 카탈로그 지표 + 선언적 조건으로 표현. 코드 전략의 **표현 불가 계층(상태/투표/regime/시간/스크리너/lookback)은 의도적으로 제외**하며 description에 명시.

| 템플릿 (id) | 이름 | 지표 | 진입 조건 (logic) | 제외(비동일) |
|---|---|---|---|---|
| `approx_williams_r` | Williams %R 반전 (근사) | williams_r(14), bollinger(20,2) | AND: `williams_r cross_above -80`, `close > bb.middle` | 2-bar momentum 번들, 종목별 cooldown, confidence 스케일 |
| `approx_technical_consensus` | 기술적 합의 (근사) | rsi(14), macd(12,26,9), williams_r(14) | AND: `rsi > 35`, `macd.histogram > 0`, `williams_r > -80` | N-of-M 가중 투표, cooldown |
| `approx_trend_vwap` | VWAP 추세 지속 (근사) | sma(20), sma(60), vwap | AND: `close > sma_20`, `sma_20 > sma_60`, `close > vwap` | regime 게이트, KST 시간창, RVOL, cooldown |
| `approx_pattern_pullback` | 추세 내 눌림목 (근사) | sma(200), sma(20), rsi(14) | AND: `close > sma_200`, `close <= sma_20`, `rsi < 45` | 다중 패턴 랭킹, 60일 수익률, ATR%, cooldown |

- exit: 각 템플릿은 사용자가 risk 단계에서 SL/TP를 설정하도록 빈 exit 조건 그룹 + 합리적 risk 기본값(예: stop_loss 5%) 제공. (선물 안전장치는 stock이라 무관.)
- 진입 조건은 **합리적 시작점**일 뿐 — 사용자가 캔버스에서 수정/확장하는 것을 전제.

### B. 라벨링 (명시적 "근사·비동일")
- `name`: "… (근사)".
- `category: 근사 템플릿`.
- `description`: "⚠️ 실제 <전략> 전략의 표현가능 지표 조건만 근사한 시작 템플릿입니다. 실제 전략과 동일하게 동작하지 않습니다(regime·상태·투표·스크리너 등 제외). 빌더에서 자유롭게 수정하세요."
- builder_state.metadata.tags에 `approx` 포함.
- **프론트 배지**: `page.tsx`의 프리셋 렌더에서 `preset.category === "근사 템플릿"`이면 앰버 "근사" 배지(`bg-amber-100 text-amber-600`)를 이름 옆에 표시. (BackendPresetStrategy에 category가 이미 매핑됨.)

### C. 데이터 흐름 (백엔드 로직 변경 없음)
```
kis_presets.yaml (+4 presets, category="근사 템플릿")
  → GET /api/kis-builder/strategies (list_kis_strategy_infos)
  → 빌더 "기본 전략" 목록에 표시 (근사 배지)
  → 선택 → builder.loadState(builder_state) → 캔버스 시드
  → 사용자가 편집/저장(localStorage) 또는 register-paper(builder_v1, paper, enabled:false 기본)
```

### D. 컴포넌트 경계
- `config/strategy_builder/kis_presets.yaml`: 4개 preset 데이터(유일한 백엔드 변경, 데이터만).
- `strategy-builder-ui/src/app/builder/page.tsx`: 프리셋 행에 category 기반 "근사" 배지 추가(작은 JSX). `BackendPresetStrategy`에 `category` 보존(이미 매핑).

---

## 4. 테스트
- **백엔드**: `load_kis_presets()`가 4개 신규 preset을 로드하고 각 `builder_state`가 `BuilderState.model_validate`(camelCase alias)로 파싱되는지 — 신규 단위 테스트(`tests/unit/strategy_builder/` 또는 기존 kis_compat 테스트 보강). 조건 오퍼랜드/연산자가 스키마 유효한지 검증.
- **프론트**: 배지 렌더(category="근사 템플릿" → 배지 표시, 그 외 미표시) + `npx tsc --noEmit` + `npm run build`.
- **회귀**: 기존 프리셋(golden_cross 등) 로딩/표시 불변.

---

## 5. 수용 기준
- [ ] 빌더 "기본 전략"에 근사 템플릿 4개가 보이고 **앰버 "근사" 배지**가 붙는다.
- [ ] 각 템플릿 선택 시 해당 지표·조건이 캔버스에 로드된다(asset_class=stock).
- [ ] 각 템플릿 description에 "실제 전략과 동일하지 않음 + 제외 항목"이 명시된다.
- [ ] `momentum_breakout`은 템플릿에 없다(표현 불가).
- [ ] 4개 builder_state가 모두 `BuilderState`로 파싱된다(테스트로 증명).
- [ ] 기존 프리셋 동작 회귀 없음. `npm run build` 그린.

---

## 6. 리스크
| 리스크 | 완화 |
|--------|------|
| 사용자가 근사 템플릿을 실제 전략과 동일하다고 오인 | 이름 "(근사)" + category + 경고 description + 앰버 배지(3중 라벨) |
| 템플릿 지표가 빌더 카탈로그에 없어 렌더 실패 | 모든 지표를 `constants.ts`에 존재하는 것(williams_r/rsi/sma/macd/bollinger/vwap)으로 한정 |
| builder_state 스키마 오류(camelCase) | 신규 파싱 테스트로 4개 전부 검증; 기존 golden_cross 형식 준수 |
| 근사 진입 조건이 너무 엄격/느슨해 안 fire | "시작 템플릿"임을 명시 — 사용자 튜닝 전제. 합리적 기본값 제공 |
