# Declarative TA-Lib Strategy Builder — Phase 1 (done) + Phase 2 (gated)

- 날짜: 2026-07-05
- 목표: Strategy Builder를 TA-Lib에 완전히 의존하는 선언형(Declarative) 구조로.
- 관련: `docs/plans/2026-07-05-indicator-engine-and-stream-schema-roadmap.md`
  (엔진/캐시/스트림 로드맵), 커밋 `#576`(엔진 기반), 본 작업 브랜치
  `feat/declarative-talib-builder`.

파이프라인:

```
YAML(BuilderState.indicators)
  → IndicatorSpec (shared/indicators/engine/spec.py)
  → TA-Lib Registry (TALibBackend._TABLE + IndicatorEngine)
  → TA-Lib Adapter (TALibBackend.compute / NumpyBackend.compute)
  → Indicator Context (DataFrame, shared/strategy_builder/indicator_context.py)
  → Condition Evaluator (StrategyBuilderEvaluator — 계산 안 함)
  → Strategy Engine (builder_v1 entry/exit)
```

---

## Phase 1 — 선언형 TA-Lib 빌더 (완료, 브랜치)

빌더가 자체 계산 코드를 갖지 않고 TA-Lib 엔진으로 위임하도록 배선. **라이브
계산 경로(`_calc_*`)는 미변경** — 빌더를 공유 flat 패널에서 떼어냈을 뿐.

- **엔진 커버리지 완성:** `ichimoku`, `volume_acceleration`를 `NumpyBackend`에 추가
  (Registry 등록만). 카탈로그 18종 전부 엔진이 계산. `flat_key` 다출력 충돌 수정.
- **Indicator Context 생산자** (`shared/strategy_builder/indicator_context.py`):
  `BuilderState.indicators` → `IndicatorSpec` → `engine.compute` → `alias.output`
  컬럼 DataFrame(전체 시리즈). `to_symbol_series`로 Evaluator에 연결. **Evaluator 무변경.**
- **builder_v1 entry/exit 재배선:** `required_indicators=["ohlcv"]` 선언 →
  resolver가 `context.indicators["ohlcv"]`(완결 캔들) 공급 →
  `window_from_records` → `build_indicator_context`. 어댑터는 지표 수학 없음.
- **cross 연산자 부활:** 전체 시리즈 context로 `cross_above/cross_below`가 실제 발화.
  `runtime_support`의 unsupported 집합을 비워 factory/dashboard가 cross 전략을
  더는 스킵/거부하지 않음(단일 지점 변경).
- **검증:** builder/engine/dashboard 유닛 그린, cross e2e 발화 증명, ruff/black/mypy(신규).

**요구사항 대응**
- 빌더는 지표 계산 안 함 ✓ / 모든 지표 TA-Lib(+비-TA-Lib은 NumpyBackend) ✓ /
  Registry 기반, 신규 지표=등록만 ✓ / 동일 인터페이스(IndicatorBackend) ✓ /
  YAML은 지표명·파라미터·출력 alias만 ✓ / Evaluator는 context만 참조 ✓.
- **부분 충족(요구 7):** "기존 사용자 정의 지표 계산 코드 모두 제거" — 빌더 경로에서는
  제거(공유 패널 미참조)했으나, `_calc_*` 자체 삭제는 Phase 2(라이브 값 변경 게이트).

---

## Phase 2 — 전역 `_calc_*` → TA-Lib Adapter 통합 (게이트, 미착수)

요구 7의 완전 이행. **라이브 트레이딩 값 변경**이므로 지표별 백테스트 게이트 필수.

### 왜 게이트인가 (shadow harness 측정)
`tests/unit/indicators/engine/test_shadow_parity.py`로 신 엔진 vs 런타임 `_calc_*` 대조:
- **ADX** = Δ≈0.002 (둘 다 Wilder) → **위임 안전, 무게이트**.
- **ATR** = 런타임 `_calc_atr_raw`가 SMA-of-TR(`ATRCalculator(mode="sma")`) vs TA-Lib
  Wilder → 발산 → **백테스트 게이트**(스톱/엣지 필터 영향).
- **Stochastic** = 런타임 fast %K vs TA-Lib slow STOCH → 발산 → **게이트**(또는 backend를
  `STOCHF`로).
- **Bollinger** = 런타임 sample std(ddof=1) vs TA-Lib population(ddof=0) → 밴드폭 변경 → **게이트**.
- **RSI** = 이미 Wilder 수렴됨(런타임 `_calc_rsi`) → 위임 안전(단 momentum.RSICalculator는
  warmup을 50으로 채움 vs TA-Lib NaN → 규약 확인).

### 블라스트 반경 (inventory)
- **플랫폼 크리티컬(게이트 필수):** `indicator_calculations._calc_{bb,atr_raw,mfi,stochastic,...}`
  + `indicator_queries.get_indicators/get_indicator_features`가 Setup A/C(`atr`/`vwap`),
  3-stage/ATR 이그짓, screener, risk filter를 구동. `momentum.calculate_all_momentum`(momentum_5m
  번들: TRIX/Williams/MACD/CCI/Stoch/OBV). `daily.calculate_daily_indicators`,
  `volume_ratio.VolumeRatioCalculator`, `volume.VWAP/VolumeAcceleration/OBV`,
  `reference.{ATR,ADX,StochRSI,wilder_rsi}`, regime detectors(`adaptive_detector._calc_mfi`는
  아직 손구현).
- **고아/광고성(무게이트 삭제 가능, 소비자 0):** `shared/indicators/technical.py::TechnicalCalculator`,
  `shared/indicators/composite.py::CompositeScoreCalculator`, `shared/trend/*`(only trend/config.py),
  `orderbook.OrderBookAnalyzer`는 LLM-flow 광고성.

### 엔진 커버리지 갭 (Phase 2 선결)
TA-Lib/현 NumpyBackend에 없는 것 → NumpyBackend/`@njit` 확장 필요: `stochrsi`,
volume velocity, VR(volume ratio), `daily_ema_aligned`, `high_n`, basis/z-score,
composite score, orderbook imbalance. (ichimoku/volume_acceleration는 Phase 1에서 추가됨.)

### 단계
1. **P2-0 (무게이트, 즉시):** 고아 계산기 삭제 — `technical.py`, `composite.py`,
   `shared/trend/*`(소비자 0 확인). ADX를 canonical/TA-Lib로 위임(shadow 안전).
2. **P2-1 커버리지:** NumpyBackend에 갭 지표 추가(Registry 등록). parity 하네스로 대조.
3. **P2-2 값-변경 위임(게이트):** ATR(SMA→Wilder), Stochastic(fast→slow 또는 STOCHF),
   Bollinger(ddof) 등을 지표별로 어댑터 위임. **배포호스트 Parquet 데이터로 백테스트 게이트**
   (Setup A/C·regime·exit 수익/샤프/MDD 델타), 통과 시 머지.
3. **P2-3 정리:** 위임 완료 지표의 손구현 삭제, DRY 단일 SoT 확정.

### 게이트 규약 (재사용)
`test_shadow_parity.py`의 `ShadowDelta`로 신 엔진 vs 레거시 델타를 지표별 측정, "위임 안전
(무게이트) / 값-변경(백테스트 게이트)"으로 분류. 규약 이동(BB ddof, ATR SMA→Wilder,
RSI warmup)은 각기 별도 게이트 항목.

---

## 후속(Phase 1 잔여, 저위험)
- 카탈로그(`indicators.yaml`)↔Registry SoT 일관성: 카탈로그가 등록 지표의 부분집합임을
  테스트로 고정(추가 완료). 장기적으로 카탈로그를 Registry에서 파생 검토.
- builder 값 변경(공유 패널 ATR SMA → 엔진 Wilder 등)은 paper/experimental이라 게이트가
  가볍지만, builder 프리셋 백테스트/paper 검증 권장.
