# TA-Lib 엔진 ↔ 전략 빌더 카탈로그 정합화 실행 계획

- 날짜: 2026-07-06
- 성격: 실행 계획 (엔진 배관 + 카탈로그 정합 + 엔진 수렴 + 정리)
- 선행 조사: 본 문서 §1 (3계층 카탈로그 × 4엔진 교차 대조, TA-Lib 0.6.8 커버리지 실측)
- 선행 계획:
  - `docs/plans/2026-07-04-indicator-coverage-builder-catalog-roadmap.md` (WS3 카탈로그·WS4 배지 — M1 머지됨)
  - `docs/plans/2026-07-05-indicator-engine-and-stream-schema-roadmap.md` (Track A 계산 SoT)
  - `docs/plans/2026-07-04-indicator-m2-handoff.md` (RSI/ADX Wilder 수렴 게이트 — 데이터 서버 실행)

---

## Context

TA-Lib 통합(#576~#590) 이후 지표 *계산*은 TA-Lib을 SoT로 삼도록 바뀌었으나, **전략 빌더가
사용자에게 노출하는 카탈로그**와 **엔진이 실제 계산하는 지표 집합**이 어긋나 있다. 조사 결과
불일치는 세 부류다.

1. **카탈로그 과다 노출 (P1)**: 프론트 `constants.ts`는 ~141종(캔들패턴 63 포함)을 노출하지만
   엔진은 17종만 계산한다. 나머지는 `backendUnsupported` amber 경고만 뜬 채 **선택 가능** →
   실행 시 `indicator_context.py` 에서 조용히 스킵되어 **신호가 절대 안 뜨는 조건**이 만들어진다.
   - **핵심 판단(사용자 결정):** TA-Lib을 택한 이유가 바로 "카탈로그 대부분을 커버"하기 때문이다.
     실측 결과 TA-Lib 0.6.8(158 함수)로 **~76종을 추가로 백킹 가능**(42 캔들패턴 + 34 비캔들).
     따라서 프론트를 잠그는 게 아니라 **백엔드에서 갭을 메운다**. 진짜 TA-Lib 부재분(~49종)만
     NumPy로 추가하거나 정직하게 표기한다.

2. **두 엔진 값 불일치 (P1)**: 빌더는 `default_engine()`(TA-Lib 표준), 실시간 런타임은
   `streaming_indicator_engine()`(손구현 규약: first-delta RSI seed, ddof=1 Bollinger, fast %K)을
   쓴다. 같은 심볼의 cockpit 표시 값과 빌더 계산 값이 다르다.
   - **핵심 판단(사용자 결정):** 손구현 `_calc_*`는 이미 전부 파기됐다. streaming 백엔드를
     **TA-Lib 표준으로 수렴**시켜 단일 규약으로 만든다. 라이브 시그널 값이 이동하므로
     **데이터 서버 A/B 백테스트 게이트**를 문서화하고 그 통과 전에는 live 머지 금지.

3. **정리 대상 (P2)**: 죽은 중복 API(`kis_builder_compat.list_indicators`), 낡은 YAML 주석
   (williams_r/cci/trix/obv/ichimoku "미배선" 주석이 사실과 불일치).

의도한 결과: 빌더가 노출하는 지표는 (거의) 전부 실제 계산 가능해지고, 런타임/빌더가 동일한
TA-Lib 표준 값을 쓰며, SoT 가드레일 테스트가 양방향으로 불일치를 차단한다.

---

## §1. 조사 결과 (실측)

**데이터 흐름**

```
[프론트] constants.ts (~141종 정적)  ─┐
                                     ├→ mergeIndicatorCatalog() → 빌더 UI 목록
[백엔드] /api/strategy-builder/capabilities → load_capabilities()
         → config/strategy_builder/indicators.yaml (18종, ★SoT, capabilities 승자)  ─┘

[실행] builder_v1 → build_indicator_context() → default_engine()  (프리뷰=페이퍼 동일)
       = TALibBackend + NumpyBackend(vwap/rvol/volume_acceleration/ichimoku)
[런타임 M4/M5] streaming_indicator_engine() = StreamingCompatBackend (비표준, 값 보존)
```

**TA-Lib 0.6.8 커버리지 (프론트 ~141종 대비)**

| 구간 | 개수 | 예시 |
|---|---|---|
| 엔진 배선 완료 | 17 | adx atr bollinger cci ema ichimoku macd mfi obv roc rsi sma stochastic stochrsi trix vwap williams_r |
| TA-Lib 백킹 가능·미배선 | ~76 | 캔들패턴 ~42(CDL*), 비캔들 ~34: ad/adosc, adxr, apo, aroon, beta, bop, cmo, dema/tema/trima/kama/t3/wma, sar, ppo, ultosc, natr, midpoint/midprice, ±di, min/max, stddev/var, linearreg계열(slope/intercept/tsf), mom |
| TA-Lib 부재 | ~49 | donchian, supertrend, keltner, vwma, hma, zlema, alma, vidya, cmf, kvo, vortex, chop, tsi, kst, coppock, schaff, fisher, rvi, mass_index, eom, force, dpo, pivot, ibs, 일부 복합 캔들 |

**확정 사실**
- `builder_strategy.py:72` 는 프리뷰·페이퍼 모두 `default_engine()` 사용 → 빌더 전략 자체는 TA-Lib 내부 일관. 불일치는 cockpit(streaming) 표시값과의 차이.
- 게이팅: `indicatorBadges.ts` 는 `implemented===false` 만 하드 차단. `backendUnsupported` 는 경고만.
- `kis_builder_compat.list_indicators`(하드코딩 10종)는 `/api/kis-builder/strategies/indicators` 에 마운트돼 있으나, 유일한 프론트 호출자 `strategies.ts:70 listIndicators()` 는 존재하지 않는 `/api/strategies/indicators` 를 호출하고 그 함수 자체가 어떤 컴포넌트에서도 호출되지 않음 → 사실상 죽은 코드.
- SoT 가드 테스트 존재: `tests/unit/strategy_builder/test_catalog_registry_sot.py` (단방향: runtime_supported → 엔진 지원).

---

## §2. 실행 단계

### Phase A — TA-Lib 백킹 가능 지표 엔진+카탈로그 배선 (P1 핵심)

패턴(반복): `talib_backend.py:_TABLE` 에 항목 1개 + `_xxx(mod, w, p)` compute fn 1개 →
`indicators.yaml` 에 블록 1개(id/name/name_ko/category/params/outputs/default_output/
implemented/backtest_supported/runtime_supported) → 필요 시 `spec.py:_OUTPUT_KEY_OVERRIDES`.

그룹 배치로 나눠 PR 단위를 작게 유지:

- **A1 Overlap/이동평균**: dema, tema, trima, kama, wma(+lwma alias), t3, midpoint, midprice, sar.
- **A2 Momentum/Oscillator**: adxr, apo, ppo, cmo, bop, ultosc, aroon(up/down 2-output), ±di, mom(momentum alias).
- **A3 Volatility/Stat**: natr, stddev(std alias), var(variance alias), beta, linearreg(regression/slope/intercept/tsf), min/max.
- **A4 Volume**: ad(adl alias), adosc(cho alias).
- **A5 캔들패턴(~42)**: `talib.CDL*` 는 -100/0/+100 정수 반환. **설계 결정 필요** — 아래 "열린 결정" 참조.

파일: `shared/indicators/engine/talib_backend.py`, `config/strategy_builder/indicators.yaml`,
(다출력 시) `shared/indicators/engine/spec.py`.
테스트: 각 그룹마다 `tests/unit/indicators/engine/` 에 계산 스모크 + SoT 가드 통과.
리스크: 낮음(순수 가법). 캔들패턴은 A5로 격리 — 연산자/출력 의미가 다르므로 결정 후 진행.

### Phase B — TA-Lib 부재 지표: NumPy 추가 또는 정직 표기 (P1)

패턴: `numpy_backend.py:_TABLE` 에 순수 NumPy 구현 추가(기존 vwap/rvol/ichimoku와 동형).
- **B1 저비용 추가**: donchian, keltner, vwma, hma(가중), zlema, dpo, ibs, pivot — 단순 롤링/가중.
- **B2 보류·표기**: supertrend, alma, vidya, frama, cmf, kvo, vortex, chop, tsi, kst, coppock,
  schaff, fisher, rvi, mass_index, eom, force, 복합 캔들 → 당장 미구현.
  `constants.ts` 에서 **`implemented: false`** 로 명시(하드 차단) → 사용자에게 정직하게 "지원 예정".
파일: `shared/indicators/engine/numpy_backend.py`, `strategy-builder-ui/src/lib/builder/constants.ts`.
리스크: 중(look-ahead 금지 — 롤링 윈도우는 현재 바까지만; `LookaheadGuard` 규약 준수).

### Phase C — 엔진 수렴: StreamingCompatBackend → TA-Lib 표준 (P1, live 게이트)

`streaming_backend.py` 의 rsi/bollinger/mfi/adx/stochastic 을 TA-Lib 표준 계산으로 교체
(또는 streaming 엔진 자체를 `default_engine` 위임으로 축소). 손구현은 이미 파기됐으므로
"값 보존" 명분이 사라짐.
파일: `shared/indicators/engine/streaming_backend.py`, `registry.py`(주석/도크스트링 갱신),
`tests/unit/indicators/engine/test_streaming_backend_golden.py`(골든값 재생성).
- **런타임 소비 경로 확인 필수**: streaming `_calc_*` 위임 지점(services/*)이 새 값으로 이동.
- **차단 조건**: Phase F 백테스트 게이트 PASS 전에는 **live 머지 금지**. shadow/paper 우선.
리스크: 높음(라이브 시그널 값 이동). 반드시 데이터 서버 A/B 통과 후 승격.

### Phase D — P2 정리

- D1: `kis_builder_compat.py:96 list_indicators` 및 죽은 프론트 `strategies.ts` 배관 제거
  (마운트/호출 없음 재확인 후). 파일: `services/dashboard/routes/kis_builder_compat.py`,
  `strategy-builder-ui/src/lib/api/strategies.ts`.
- D2: `indicators.yaml` 낡은 주석 정정(라인 ~278-296, ~453-461): williams_r/cci/trix/obv/ichimoku
  는 이제 TA-Lib 엔진이 계산 → "flat base 미배선/runtime false" 서술 삭제·갱신.
리스크: 낮음. D1은 삭제 전 grep 재확인.

### Phase E — SoT 가드레일 양방향화

`test_catalog_registry_sot.py` 강화: (기존) runtime_supported→엔진 지원에 더해,
(신규) **프론트 `implemented:true` 인데 엔진 미지원**을 차단하는 계약 테스트 추가
(constants.ts export를 픽스처로 읽거나 capabilities 병합 결과 대조). 카탈로그 드리프트 재발 방지.
파일: `tests/unit/strategy_builder/test_catalog_registry_sot.py`,
`strategy-builder-ui/src/lib/builder/indicatorCatalog.test.ts`.

### Phase F — 데이터 서버 백테스트 게이트 문서화 (Phase C 선행 조건)

`docs/runbooks/streaming-talib-convergence-gate.md` (작성 완료): streaming→TA-Lib 수렴 전후 A/B 백테스트 절차.
- 대상 전략: bb_reversion 등 streaming 지표 소비 전략.
- 절차: 수렴 전(baseline) vs 후(candidate) 동일 기간 백테스트 → Sharpe/MDD/승률/시그널 수 델타.
- 통과 기준·롤백·승격 경로 명시. `2026-07-04-indicator-m2-handoff.md` 형식 참고.
- **로컬 실행 금지**(데이터 없음) — 모의투자/데이터 서버에서 수행.

---

## §3. 열린 결정 (실행 전 확인)

1. **캔들패턴 연산자/출력(A5)** — ✅ 해결(2026-07-06): 옵션 (b) 채택. `CDL*` 정수(+100/
   -100/0)를 float로 캐스팅해 그대로 노출하고, 빌더는 기존 연산자로 방향 표현
   (`value greater_than 0` 강세 / `value less_than 0` 약세). 스키마 변경 불필요.
   57개 패턴 `_CDL_TABLE` 데이터-드리븐 등록 + YAML + 프론트 addable 전환 완료.
2. **streaming 엔진 처리(C)** — ✅ 해결(2026-07-06): 백엔드 삭제/값 교체 대신 **config
   게이트** 채택(StochRSI default-off 선례). `runtime_indicator_engine()` 셀렉터가
   env `STS_INDICATOR_CONVENTION`(기본 `streaming`)로 streaming/talib 엔진을 선택 —
   기본값이 현행 라이브 값 보존(영향 0), 데이터 서버 게이트 통과 후 `talib`로 플립.
   StreamingCompatBackend·골든 테스트는 그대로 유지(선례처럼 additive, main-safe).

---

## §4. 검증

- 단위: `.venv/bin/pytest tests/unit/indicators/ tests/unit/strategy_builder/ -v` (Phase A/B/E).
- 계약: `test_catalog_registry_sot.py` 양방향 통과.
- 프론트: `cd strategy-builder-ui && npm run build && npm run lint && npx vitest run src/lib/builder`.
- 게이트: `black . && ruff check . && mypy shared/ --ignore-missing-imports`.
- E2E(수동): 빌더에서 신규 배선 지표(예: sar, aroon)로 조건 생성 → capabilities 응답 확인 →
  preview-signals 로 값 산출 확인(신호 안 뜨는 조건이 사라졌는지).
- **Phase C 전용**: 데이터 서버 A/B 백테스트(§F) PASS 전 live 머지 차단.
