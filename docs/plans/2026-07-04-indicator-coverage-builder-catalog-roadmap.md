# 지표/보조지표 커버리지 · 빌더 카탈로그 정합성 로드맵

- 작성일: 2026-07-04
- 상태: **Active** — 핵심 의사결정 확정(2026-07-04, §6), 구현 착수 승인 대기
- 소유 도메인: 지표 라이브러리(`shared/indicators`), 런타임 스트리밍 엔진(`services/trading`),
  노코드 빌더(`config/strategy_builder`, `shared/strategy_builder`, `strategy-builder-ui`)
- 관련 문서: [runtime-refactoring-roadmap](2026-07-04-runtime-refactoring-roadmap.md),
  [strategy-lab-extension-design](2026-05-26-strategy-lab-extension-design.md),
  [ml-rl-removal-llm-indicator-futures](2026-06-03-ml-rl-removal-llm-indicator-futures.md)

> 이 문서는 **"바로 구현"이 아니라 병렬 실행 가능한 워크스트림 + 검증 포인트 + 롤백**을
> 정의하는 계획서다. 각 워크스트림은 독립 에이전트/작업자에게 할당 가능하도록 경계와
> 의존성을 명시한다. 코드 변경은 이 계획 승인 이후에 착수한다.

---

## 1. 배경 — 조사로 확인된 사실 (Ground Truth)

2026-07-04 코드베이스 전수 조사 결과. 이 계획의 모든 판단은 아래 사실에 근거한다.

### 1.1 실제 구현된 지표는 충분하다 (~25종)
백엔드에서 실계산되는 지표: 추세/MA(SMA, EMA, Ichimoku, ADX, MA 배열), 모멘텀/오실레이터
(RSI, MACD, Stochastic, Williams %R, CCI, TRIX, MFI, Divergence), 변동성(ATR, Bollinger,
변동성 레짐), 거래량(VWAP, OBV, RVOL, Volume Acceleration, VR), 마이크로구조(호가 불균형),
복합(CompositeScore, technical_consensus, indicator-family scorers). → freqtrade/backtrader
실전 스택을 거의 전부 포함. **개수는 문제가 아니다.**

### 1.2 문제는 "노출·정합성·확장" — 4가지 구조적 결함

**(결함 A) StochRSI 유령 지표.** `shared/strategy/entry/stochrsi_trend.py:55`가
`stochrsi_k/d/k_prev`를 required로 선언하고 `registry.py:374`에 등록돼 있으나, 이 키를
**생산하는 코드가 어디에도 없음.** 존재하는 "stoch"는 전부 price 기반 Stochastic
(`_calc_stochastic` → `stoch_k`, `StochasticCalculator` → `sto_k`)이지 RSI 기반이 아니다.
→ 런타임에서 항상 기본값(50/50/50)만 받는 **사실상 dead 전략.**

**(결함 B) 지표 계산 5중 분산 (DRY 위반).** 계산 SoT가 5개 경로에 존재:
1. `services/trading/indicator_calculations.py` — 핫패스 순수 파이썬 (BB/RSI/Stochastic/ADX/MFI/ATR/EMA). **런타임 + 1분봉 백테스트가 공유** (parity 확보된 유일 지점).
2. `shared/indicators/momentum.py` — pandas/numpy (TRIX/CCI/MACD/Stochastic/Williams%R/RSI/OBV). momentum_5m 번들 + 일봉 백테스트가 재사용.
3. `shared/backtest/daily_adapter.py` — 일봉 전용 SMA 인라인 + 자체 `_compute_rsi`.
4. `core/indicator_engine.py` — polars BB/RSI/MACD (4번째 구현).
5. `shared/regime/adaptive_detector.py:389/346/434` — regime용 ADX/MFI/ATR 자체 구현.

중복 매트릭스: **RSI ×4 (2가지 알고리즘: rolling-SMA vs Wilder EMA), Stochastic ×2 (키 이름
다름 `stoch_` vs `sto_`), ADX ×2 (알고리즘 다름), Bollinger ×2, ATR·MFI ×2.** ADX·Bollinger는
`shared/indicators/`에 아예 없음(런타임 엔진에만 존재).

**(결함 C) 빌더 카탈로그 3중 불일치 + 죽은 배선.** "지표 목록"이 3개 존재하는데 서로 연결 안 됨:
- `config/strategy_builder/indicators.yaml` — **10개** (권위). `catalog.py:load_capabilities()`가
  로드 → `GET /api/strategy-builder/capabilities`로 노출.
- 레거시 `kis_builder.py:124` `/strategies/indicators` — **~20개 하드코딩** (다른 스키마).
- 프론트 `strategy-builder-ui/src/lib/builder/constants.ts` — **80개 + 캔들패턴 63개 하드코딩.**

> **결정적 사실:** 프론트 UI는 **오직 `constants.ts`(80+63)만 렌더**한다.
> capabilities API도(`getCapabilities`는 `src/lib/dashboard/strategyBuilder.ts:105`에 정의만 되고
> **호출 0회**), 레거시 라우트도(`listIndicators` 호출 0회) **둘 다 죽은 코드**다.
> → 즉 "프론트가 광고하는 80개"와 "백엔드가 계산 가능한 25개"와 "빌더 카탈로그 10개"가
> **완전히 단절**되어 있다. 사용자가 UI에서 고른 지표가 실제로 발화하지 않을 수 있다.

**(결함 D) 배지 게이팅 휴면 + 필드명 불일치.** `IndicatorSelector.tsx`에 "미구현(Lock)/백테스트
미지원(amber)/선물 권장 안 함" 배지 로직이 **구현돼 있으나**, `constants.ts`에서 `implemented`/
`leanUnsupported`가 **한 번도 설정되지 않아 전부 휴면.** 게다가 백엔드 플래그
(`backtest_supported`/`runtime_supported`)와 프론트 타입(`leanUnsupported`)의 **필드명이 달라서**
플래그가 end-to-end로 흐르지 못한다. 백엔드 `backtest_supported/runtime_supported`는 schema에만
있고 **코드 소비 0회.**

### 1.3 선물 마이크로구조는 절반만 채워짐
레퍼런스 퀀트(인트라데이 선물)의 핵심 4종: VWAP ✅ / 호가 불균형 ✅ / **누적 델타(CVD) ❌ /
볼륨 프로파일 ❌.** 호가 불균형 인프라(`orderbook.py`)가 이미 있어 CVD/볼륨 프로파일은 자연스러운
다음 확장이며 선물 차별화 지표다.

### 1.4 레퍼런스 벤치마크 (외부 조사)
- TA-Lib 150+, pandas-ta 193개/9카테고리(Momentum·Overlap·Trend·Volatility·Volume·Cycles·Candles·Statistics·Performance).
- 실전 봇(freqtrade/backtrader)이 실제로 쓰는 코어는 소수: RSI·EMA/SMA·BB·MACD·ADX·Stochastic·ATR·MFI·SAR → **우리는 SAR 빼고 전부 보유.**
- Qlib(AI 퀀트)는 지표를 손으로 고르지 않고 Alpha158/360 팩터 라이브러리를 ML 입력으로 사용 → 현재 룰기반과 무관하나 향후 ML 확장 시 방향성 참고.

---

## 2. 목표 / 비목표

### 목표
1. dead 전략 제거: StochRSI를 진짜 계산하거나 격리한다. (결함 A)
2. 지표 계산 SoT 확립: `shared/indicators/`를 **참조(reference) 구현**으로 삼고, 분산된 5경로를
   parity 계약으로 묶거나 수렴시킨다. ADX·Bollinger를 shared로 승격. (결함 B)
3. 빌더 카탈로그를 **단일 진실 소스**로 정리하고, 이미 구현된 지표를 노출한다. 프론트가
   백엔드 능력과 일치하도록 배선한다. (결함 C, D)
4. 선물 마이크로구조 확장: CVD + 볼륨 프로파일을 SoT 패턴으로 추가. (1.3)
5. 모든 변경에 대해 backtest↔runtime parity / no-lookahead / KST / TTL / long-short 대칭 /
   config-driven 검증을 강제한다.

### 비목표 (이번 스코프 아님)
- pandas-ta 193개 전량 이식. (필요한 것만 tiered로 추가)
- 캔들패턴 63종 백엔드 구현. (프론트에서 "미지원" 배지 처리로 한정)
- Qlib식 팩터 라이브러리/ML 파이프라인. (별도 로드맵)
- 핫패스 성능을 희생하는 무리한 단일화. (parity 계약으로 대체 — 2.WS2 참조)
- RL/TFT 재도입 (CLAUDE.md 금지).

---

## 2.5 계산 라이브러리 채택 평가 — TA-Lib vs pandas-ta vs 현행 hand-roll

> 2026-07-04 사용자 결정으로 추가된 평가 항목. **현재 의존성에 TA 라이브러리 없음**
> (`numpy>=1.26`, `pandas>=2.1`만 존재; 지표는 두 레거시 프로젝트에서 병합한 hand-roll).
> 이 평가는 WS2-a(참조 계산기)·WS3 Tier2·WS5(신규 지표)의 구현 방식을 결정한다.

### 핵심 구분: batch/vectorized vs incremental/streaming
성숙 라이브러리(TA-Lib, pandas-ta)는 **전체 배열을 한 번에 계산하는 batch** 방식이다.
반면 우리 런타임 핫패스는 **바 단위 incremental streaming**(1분봉 저지연)이다. 라이브러리를
핫루프에 넣으면 매 바마다 전체 윈도우를 재계산 → **오히려 느려진다.** 따라서 라이브러리는
**런타임 핫패스를 대체하지 않는다.** 라이브러리의 올바른 역할은 아래 3곳이다:
① 골든 **참조/스펙**(핫패스가 parity로 pin되는 기준), ② **배치 백테스트**(일봉·비저지연 경로),
③ **Tier2/신규 지표 수학의 출처**(SuperTrend/Donchian/Keltner/SAR/ROC 등).

### 비교

| 항목 | TA-Lib | pandas-ta | 현행 hand-roll |
|---|---|---|---|
| 지표 수 | 150+ | 130~193 (9카테고리) | ~25 |
| 설치 | **네이티브 C 라이브러리** — Docker/배포 마찰 | 순수 파이썬 pip (네이티브 의존 無) | 없음 |
| 속도(배치) | C-속도 (최고) | pandas 기반 (중간) | N/A(스트리밍) |
| 정확성/검증 | 업계 표준, battle-tested | 표준, 다만 원본 저장소 **유지보수 정체**(포크 pandas-ta-classic/remake 존재) | 자체 검증 필요, 이미 5중 분산 |
| Tier2 커버(SuperTrend/Donchian/Keltner/SAR/ROC) | 대부분 O(SuperTrend는 조합) | **전부 O** | 전부 X(신규 구현 필요) |
| 스트리밍 적합성 | X(배치) | X(배치) | O(incremental) |

### 권장 (계획 반영)
1. **pandas-ta(유지보수 포크)를 `shared/indicators`의 배치/참조 레이어로 채택.** 이유:
   네이티브 C 의존 회피(Docker 단순), Tier2 지표를 **hand-roll 없이 즉시 확보**,
   골든 참조로 활용. → **WS2-a·WS3 Tier2·WS5 구현 비용이 크게 감소**(직접 작성 → 래핑).
2. **런타임 핫패스(incremental)는 유지**하고, 라이브러리 참조에 **parity 테스트로 pin**(WS2-b).
   라이브러리를 핫루프에 강제하지 않는다(저지연 회귀 방지). 최근 벡터화 성과(`09b46247`) 보존.
3. **TA-Lib은 배치 백테스트가 pandas-ta로 너무 느릴 때만** 백테스트 전용으로 고려(네이티브 의존
   비용 감수). 기본은 pandas-ta.
4. **리스크: (a) 라이브러리 값 규약**(RSI=Wilder 등)이 현행과 달라 값이 바뀜 → WS2-d 값변경
   게이트로 흡수(백테스트 델타). **(b) 원본 pandas-ta 정체** → 반드시 유지보수 포크에 pin하고
   버전 고정, numpy 호환 확인.
5. **결정 스파이크(M1):** pandas-ta 포크 1개 선정 + 대표 지표(RSI/ADX/BB) 값을 현행과 대조,
   배치 백테스트 스케일에서 속도 측정 → 채택 확정. (이 스파이크가 WS2-a 착수 전 선행)

### 미지원(캔들패턴 63종 등) 처리 연계
사용자 결정 = **미지원 배지 유지**. 캔들패턴/exotic MA는 백엔드 hand-roll 대신 **pandas-ta에
있으면 배치 경로로 저비용 노출**을 검토(위 ③). 라이브러리 채택 시 "미지원" 목록 자체가 줄어든다.

---

## 3. 워크스트림 (병렬 실행 단위)

각 워크스트림(WS)은 독립 작업자에게 할당 가능. **문제 → 접근 → 건드릴 파일 → 검증 포인트 →
완료 기준(DoD)** 형식. 파일:라인은 2026-07-04 조사 시점 기준.

---

### WS1 — StochRSI 결함 수정 (결함 A)

**문제:** `stochrsi_trend` 전략이 존재하지 않는 키를 소비 → dead 전략.

**접근 (2단계):**
- **WS1-a (즉시/안전):** `stochrsi_trend`를 registry에서 비활성 플래그로 격리하거나, 활성 YAML
  프로파일에서 제외해 "발화하는 척하지만 안 하는" 상태를 명시적 disabled로 전환. (30분 작업, 위험 0)
- **WS1-b (정식):** `shared/indicators/momentum.py`에 `StochRSICalculator` 신설 —
  `RSICalculator`(:459)로 RSI 시리즈 생성 후 `StochasticCalculator`(:325)의 rolling %K/%D 패턴을
  RSI 시리즈에 적용. 런타임 노출은 **base 경로** `get_indicators`
  (`services/trading/indicator_queries.py:74` 부근)에 flat 키 `stochrsi_k`/`stochrsi_d` 추가
  (momentum 번들 아님 — 소비자가 flat 키를 읽음). `stochrsi_k_prev`는 직전 바 K 저장이 필요 →
  **엔진에 base 지표용 `*_prev` 상태 저장 메커니즘 신설** (추가 설계 포인트, Redis TTL 필요).

**건드릴 파일:**
- `shared/indicators/momentum.py` (StochRSICalculator 신설), `__init__.py` (export)
- `services/trading/indicator_queries.py:74±` (`get_indicators`에 flat 키), 상태 캐시 저장부
- `shared/strategy/entry/stochrsi_trend.py` (변경 불필요 — 이미 준비됨), `registry.py:374`

**검증 포인트:**
- 단위: `tests/unit/strategy/test_stochrsi.py`가 키 수동주입 대신 실제 엔진 산출을 검증하도록 확장.
- **no-lookahead**: RSI→Stoch 체인이 현재 바까지의 데이터만 사용 (LookaheadGuard).
- **Redis TTL**: `*_prev` 상태 키에 TTL(24h 기본) — CLAUDE.md 규칙.
- **백테스트 발화 확인**: WS1-b 후 `stochrsi_trend`를 실제로 백테스트해 신호가 생성되는지 확인
  (이전엔 항상 50 → 무신호). RegimeGate/Paper 승격 전 필수.

**DoD:** stochrsi_trend가 실데이터에서 신호를 생성하거나, 명시적으로 disabled로 문서화됨.
`stochrsi_k` 키를 생산하는 유일 SoT가 존재. 유령 required-key 0건.

---

### WS2 — 지표 계산 SoT 통합 (결함 B) · **최고 위험 · 기반 워크스트림**

**문제:** 5개 계산 경로, RSI ×4(알고리즘 2종)/Stochastic ×2(키 이름)/ADX ×2/BB ×2 중복.
값이 경로마다 다를 수 있어 백테스트↔런타임 신뢰성 훼손.

**접근 (additive-first, 4단계):** 핫패스 성능(최근 커밋 `09b46247` 벡터화 참조)을 깨지 않기 위해
**"단일 구현 강제"가 아니라 "참조 구현 + parity 계약"**을 채택한다.

- **WS2-a (additive, 저위험):** `shared/indicators/`에 배치/참조 레이어 확립 —
  **§2.5 결정에 따라 pandas-ta(유지보수 포크)를 래핑**해 ADX·Bollinger·StochRSI(WS1) 및 누락
  지표의 참조 구현을 확보(hand-roll 최소화). pandas-ta 부재 지표만 직접 작성. 기존 코드 변경 없음
  → 즉시 병렬 착수 가능. **선행: §2.5 M1 결정 스파이크(포크 선정 + 값 대조 + 속도 측정).**
- **WS2-b (parity 계약):** 모든 런타임/백테스트/regime 구현을 shared 참조에 대해 pin하는 골든
  parity 테스트 추가 (`tests/integration/test_bb_reversion_15m_parity.py` 패턴 확장). 이 단계가
  **RSI 알고리즘 분기(rolling-SMA vs Wilder)와 stoch 키 불일치를 표면화**시킴 — 값 차이를 수치로 고정.
- **WS2-c (안전 수렴):** perf 정당성 없는 중복부터 제거 — `core/indicator_engine.py`(polars BB/RSI/MACD
  4번째 구현), `adaptive_detector.py`의 자체 ADX/MFI/ATR를 shared 참조에 위임. 핫패스
  `indicator_calculations.py`는 **유지하되 parity 테스트로 shared에 pin** (delegate 여부는 프로파일링 결과로 결정).
- **WS2-d (정규화, 값 변경 — 게이트 필요):** `stoch_k`/`stoch_d` vs `sto_k`/`sto_d` 키 통일,
  RSI 알고리즘 단일화. **값이 바뀌므로 소비자 전수 grep + 백테스트 재실행(Sharpe/승률 델타) 검증 후에만 머지.**

**건드릴 파일:**
- 신설: `shared/indicators/` (ADX/BB/StochRSI calculator), `__init__.py:35-44,80-87` export
- 위임 전환: `services/trading/indicator_calculations.py:12/26/207/258`,
  `shared/regime/adaptive_detector.py:389/346/434`, `core/indicator_engine.py:79-84`,
  `shared/backtest/daily_adapter.py:377`
- 키/알고 정규화 소비자: `services/trading/indicator_queries.py`(momentum 번들 키 `sto_`),
  `shared/strategy/**`의 `required_indicators` 및 `data.get(...)` 참조 전수

**검증 포인트:**
- **backtest↔runtime parity (최우선)**: 1분봉은 이미 동일 엔진 → parity 유지 확인. **일봉
  (`daily_adapter.py`)은 별도 경로 → 신규 parity 테스트 필수.**
- **값 변경 게이트 (WS2-d)**: 키/알고 통일은 반드시 (1) 소비자 grep 0 누락, (2) 대표 전략
  백테스트 재실행으로 성과 델타 정량화, (3) code-reviewer 승인 후 머지.
- **기존 전략 회귀**: momentum_5m 번들 키(`sto_`) 변경 시 `technical_consensus`, `trix_golden`,
  `llm_directed_indicator`, `williams_r` 등 소비자 전부 회귀 테스트.
- mypy/ruff/black + 2-pass hermetic pytest.

**DoD:** ADX·Bollinger·StochRSI가 `shared/indicators`에 참조 구현으로 존재. 모든 중복 경로가
parity 테스트로 pin되거나 수렴됨. RSI 알고리즘/stoch 키가 문서화된 단일 규약을 따름.

---

### WS3 — 빌더 카탈로그 확장 (결함 C, 백엔드 측)

**문제:** 이미 구현된 지표가 카탈로그(YAML 10개)에 없어 빌더가 못 씀.

**접근 (tiered):**
- **Tier 1 (이미 계산됨 → 즉시 노출):** `williams_r, cci, trix, obv, rvol, mfi, ichimoku,
  orderbook_imbalance, volume_acceleration, vr, composite_score` + WS1 후 `stochrsi`. YAML에 항목
  추가만 하면 백엔드 검증/capabilities는 자동(코드 수정 불필요). **단 WS2-a 완료 전엔 backtest/runtime
  플래그를 실제 능력에 맞춰 정직하게 설정.**
- **Tier 2 (표준 갭 — 신규 구현 후 노출):** **사용자 확정 = 5종 전부** — `supertrend, donchian,
  keltner, parabolic_sar, roc/momentum`. **§2.5에 따라 pandas-ta에 전부 존재 → 배치/참조는 래핑으로
  즉시 확보**, 런타임 노출(incremental)만 추가 구현 + parity pin. 각 지표는 `shared/indicators` 참조
  + 런타임 노출 필요.
- **Tier 3 (노출 안 함 / 미지원 배지):** DEMA/TEMA/HMA/KAMA 등 MA 변형, 캔들패턴 63종 — WS4에서
  "미지원"으로 명시. **단 pandas-ta에 있는 것은 배치 경로로 저비용 노출 재검토(§2.5).**

**건드릴 파일:**
- `config/strategy_builder/indicators.yaml` (항목 추가 — `schema.py`가 `extra="forbid"`라 필드명 정확히)
- `shared/strategy_builder/schema.py` (필요 시 `IndicatorCategory`에 `microstructure` 등 카테고리 추가)
- Tier 2는 WS2/WS5와 동일한 신규-지표 절차

**검증 포인트:**
- capabilities 로딩 테스트 확장 (`tests/unit/dashboard/test_strategy_builder.py:59` — 현재 `"sma" in`만 검증).
- **플래그 정직성**: 각 지표의 `backtest_supported`/`runtime_supported`가 실제 런타임 엔진 산출과
  일치하는지 교차 검증 (WS4가 이 플래그를 소비하므로 거짓이면 UI가 거짓말).
- YAML `extra="forbid"` 회귀: 잘못된 필드명 시 로딩 실패 확인.

**DoD:** 이미 구현된 Tier 1 지표가 전부 카탈로그에 등재되고 플래그가 정직함. 카탈로그가 "백엔드가
실제 계산 가능한 것"의 정확한 반영.

---

### WS4 — 프론트↔백엔드 정합성 (결함 C·D, 프론트 측)

**문제:** 프론트 UI가 하드코딩 80개만 렌더하고 백엔드 능력과 단절. 배지 게이팅 휴면, 필드명 불일치.

**접근 — 사용자 확정 = 방향 1 (동적 배선):**
- **동적 배선:** `IndicatorSelector.tsx`/`useStrategyBuilder`가 정적 `constants.ts`
  대신 `strategyBuilder.getCapabilities()`(현재 미사용)를 fetch. YAML → capabilities API → 프론트가
  **단일 SoT.** 필드명 매핑(`backtest_supported`↔`leanUnsupported`, `runtime_supported`↔신규,
  `implemented`↔`implemented`) 정리.
- (참고) 급하면 방향 3(플래그만 채우기)로 선행 후 방향 1로 이행 가능하나, 확정 목표는 방향 1.
  → `constants.ts`는 최종적으로 fallback/초기 seed 역할로 축소하고 capabilities가 진실 소스가 됨.

**공통 필수 작업 (어느 방향이든):**
- 배지 게이팅 활성화: `IndicatorSelector.tsx:405/442/447/552/583/587` 분기가 실제 발화하도록.
- 필드명 규약 통일 (`src/types/builder.ts:34-47` ↔ 백엔드 `schema.py`).
- 죽은 코드 정리: 레거시 `kis_builder.py:/strategies/indicators`와 프론트 `listIndicators`
  deprecate/제거 (혼동 근원 제거).

**건드릴 파일:**
- `strategy-builder-ui/src/lib/builder/constants.ts`, `src/types/builder.ts`,
  `src/components/builder/IndicatorSelector.tsx`, `src/hooks/useStrategyBuilder.ts`,
  `src/lib/dashboard/strategyBuilder.ts:105`
- `services/dashboard/routes/kis_builder.py:124` (레거시 라우트 처리)

**검증 포인트:**
- **capabilities API 계약 테스트**: 프론트가 소비하는 응답 shape(필드명!) 고정. 필드명 매핑이 최대 함정.
- 프론트 vitest: `constants.ts`/레지스트리 검증 테스트 신설 (현재 전용 테스트 없음).
- `npm run build && npm run lint && npm run test` 그린.
- **UI 회귀**: 기존 빌더 플로우(지표 선택 → 조건 → YAML 직렬화)가 깨지지 않는지 —
  `yamlSerializer.test.ts`, `reducer.test.ts` 등.
- 실제 브라우저 검증: 빌더에서 신규 지표 선택 → 배지 표시 → paper 연결까지 end-to-end (verify).

**DoD:** UI에 뜨는 지표 목록이 백엔드 능력과 일치. "미구현/백테스트 미지원" 배지가 정확히 발화.
지표 목록 SoT가 하나. 죽은 카탈로그 경로 제거.

---

### WS5 — 선물 마이크로구조 확장: CVD + 볼륨 프로파일 (1.3)

**문제:** 인트라데이 선물 핵심 지표 CVD·볼륨 프로파일 부재.

**접근:** WS2 SoT 패턴으로 `shared/indicators/`에 신규 계산기 추가.
- `CumulativeVolumeDelta` — 체결 aggressor 방향(매수 at ask / 매도 at bid) 기반 누적 델타.
  호가 불균형 인프라(`orderbook.py`) 및 체결 스트림 재사용. KST 일중 리셋.
- `VolumeProfile` — 가격대별 거래량 분포(POC/VAH/VAL). 세션 단위 누적.
- 런타임 노출(선물 경로) + 카탈로그 등재(WS3 Tier 2와 동일 절차).

**건드릴 파일:**
- 신설: `shared/indicators/microstructure.py` 또는 `orderbook.py`/`volume.py` 확장, `__init__.py` export
- 런타임: `services/trading/indicator_*` 또는 futures 파이프라인 지표 산출부
- 카탈로그: `config/strategy_builder/indicators.yaml`
- 설정: CVD/프로파일 파라미터(윈도우, 버킷 크기)는 **YAML config-driven** (하드코딩 금지)

**검증 포인트:**
- **no-lookahead (LookaheadGuard)**: 누적 지표가 미래 체결을 참조하지 않음.
- **KST 일중 리셋**: CVD/프로파일 세션 경계가 KST 장 시간 기준 (CLAUDE.md 규칙).
- **long/short 대칭**: 선물이므로 CVD 부호 규약이 롱/숏 대칭 보존 (CLAUDE.md 규칙).
- **Redis TTL**: 누적 상태 키에 TTL (accumulation 48h) — CLAUDE.md 규칙.
- **config-driven**: 파라미터가 YAML에 존재, 하드코딩 분기 0.
- 백테스트 재현성: 체결 데이터 기반 CVD가 백테스트에서 재현 가능한지.

**DoD:** CVD·볼륨 프로파일이 shared에 존재하고 선물 런타임/백테스트에서 산출됨. 카탈로그 등재.
KST/대칭/TTL/lookahead 검증 통과.

---

## 4. 병렬화 계획 (Lanes & Dependencies)

### 4.1 레인 구성 (동시 실행 단위)

| 레인 | 담당 워크스트림 | 병렬성 |
|---|---|---|
| **Lane A — 백엔드 지표 SoT/계산기** | WS2-a(계산기 신설) → WS1-b(StochRSI 생산) / WS5(CVD·프로파일) → WS2-b/c/d | WS2-a·WS1-b·WS5의 **개별 지표 신설은 서로 독립** → 높은 병렬성 |
| **Lane B — 빌더 카탈로그(백엔드)** | WS3 Tier 1 (즉시), WS3 Tier 2 (Lane A 후) | Tier 1은 Lane A와 **완전 병렬 (지금 착수 가능)** |
| **Lane C — 프론트 정합성** | WS4 (배지/필드명/배선) | capabilities shape는 이미 존재 → **mock으로 Lane B와 병렬 착수** |
| **Lane D — 검증/가드레일** | parity 하네스, capabilities 계약 테스트, lookahead/KST/TTL/대칭 체크, 회귀 스위트 | **가장 먼저 시작해야 하는 교차 레인** |

### 4.2 의존성 그래프

```
Lane D (검증 하네스) ──먼저──┐
                            ▼
WS2-a (참조 계산기 신설) ──┬──▶ WS1-b (StochRSI)   ─┐
  [Lane A 루트, 독립]      ├──▶ WS5 (CVD/프로파일)  ─┤─▶ WS3 Tier2 (신규 노출)
                          └──▶ WS2-b (parity) ──▶ WS2-c (수렴) ──▶ WS2-d (정규화·값변경★)

WS3 Tier1 (이미 구현 노출) ──────────────────────────┐
  [Lane B, 지금 병렬 착수]                            ├──▶ WS4 (프론트 배선/배지)
Lane C 프론트 (mock으로 선행) ──────────────────────┘
```

### 4.3 실행 규칙
- **즉시 병렬 착수 가능 (WS2 완료 불필요):** Lane D 검증 하네스, WS1-a(격리), WS3 Tier 1
  (이미 계산되는 지표 노출), WS4 방향 결정 + 프론트 배지/필드명 정리(mock 기반).
- **WS2-a 이후 fan-out:** WS1-b·WS5·WS3 Tier 2 (신규 지표들) 동시 진행. 지표별 독립.
- **직렬 크리티컬 패스 (위험):** `Lane D parity 하네스 → WS2-b → WS2-c → WS2-d`. WS2-d는 값이
  바뀌므로 반드시 백테스트 게이트를 통과한 뒤 마지막에.
- **★ WS2-d는 다른 모든 것과 분리:** 키/알고 정규화는 소비자 전수 변경이라 마지막 독립 PR로.

---

## 5. 교차 검증 전략 (놓치면 안 되는 검증 포인트)

CLAUDE.md 비협상 규칙 + 백테스트 무결성. 모든 워크스트림 공통 게이트.

1. **backtest↔runtime parity** — 1분봉은 동일 엔진(유지 확인), **일봉은 별도 경로 → parity 테스트 신설.**
   지표 값이 두 경로에서 동일함을 골든값으로 고정.
2. **값 변경 게이트** — WS2-d(RSI 알고/stoch 키), WS5(신규) 등 값이 바뀌는 변경은 (a) 소비자 grep
   0 누락, (b) 대표 전략 **백테스트 재실행 성과 델타** 첨부, (c) code-reviewer 승인 후 머지.
3. **no-lookahead (LookaheadGuard)** — 신규/변경 지표가 현재 컨텍스트 타임스탬프까지만 사용.
4. **KST 타임존** — VWAP/CVD/볼륨프로파일 일중 리셋이 KST 장 시간 기준.
5. **Redis TTL** — 신규 상태 키(StochRSI prev-K, CVD 누적)에 TTL (기본 24h, accumulation 48h).
6. **long/short 대칭** — 선물 지표(CVD)가 롱/숏 대칭 보존.
7. **config-driven** — 신규 지표 파라미터가 YAML에, 하드코딩 분기 금지.
8. **capabilities API 계약** — 프론트 소비 shape(필드명) 고정 테스트. 필드명 매핑이 최대 함정.
9. **기존 전략 회귀** — momentum_5m 번들/base 키 소비자 전수 회귀.
10. **품질 게이트** — `ruff check` / `black --check` / `mypy shared/` / 2-pass hermetic `pytest`;
    프론트 `npm run build/lint/test`.
11. **저자·검증 분리** — 각 워크스트림은 작성 후 별도 패스(code-reviewer/verifier)로 승인. 자기 승인 금지.

---

## 6. 의사결정 (2026-07-04 확정 / 잔여)

**확정 (2026-07-04 사용자 결정):**
1. ✅ **WS4 방향 = 방향 1 (동적 fetch).** capabilities API를 프론트 단일 SoT로. (§WS4)
2. ✅ **프론트 미지원 처리 = (b) 미지원 배지 유지** + **TA-Lib/pandas-ta 라이브러리 채택 효율성
   검토 포함.** → §2.5 라이브러리 평가 신설, WS2-a·Tier2·WS5를 pandas-ta 래핑으로 재설계.
3. ✅ **WS3 Tier 2 = 5종 전부:** SuperTrend, Donchian, Keltner, Parabolic SAR, ROC/Momentum. (§WS3)

**잔여 (착수 중 확정):**
4. **WS2 핫패스:** `indicator_calculations.py`를 pandas-ta 참조에 delegate vs parity pin만?
   → §2.5 M1 스파이크 프로파일링 결과로 결정 (성능 저하 없으면 delegate, 있으면 pin).
5. **pandas-ta 포크 선정:** pandas-ta-classic vs pandas-ta-remake 등 유지보수 포크 중 택1
   → §2.5 M1 결정 스파이크에서 값 대조 + 버전 고정.
6. **실행 리소스:** 5개 레인을 몇 개 병렬 에이전트/작업자로? 크리티컬 패스(Lane D→WS2)에 우선 배치.

---

## 7. 마일스톤 (제안 순서)

| 단계 | 내용 | 병렬 레인 | 게이트 |
|---|---|---|---|
| **M0** | 계획 승인 + §6 의사결정 확정 | — | 사용자 승인 |
| **M1** | **§2.5 pandas-ta 결정 스파이크(포크 선정+값 대조+속도)** · Lane D 검증 하네스 착수 · WS1-a 격리 · WS3 Tier1 노출 · WS4 필드명/배지(mock) | B, C, D 병렬 | 스파이크 결론 + parity 하네스 그린 |
| **M2** | WS2-a 참조 계산기(ADX/BB/StochRSI) · WS1-b StochRSI 생산 · WS5 CVD/프로파일 | A fan-out | 단위 테스트 + no-lookahead |
| **M3** | WS2-b parity 계약 · WS2-c 안전 수렴 · WS3 Tier2 · WS4 배선 완료 | A, B, C | parity 테스트 + UI e2e |
| **M4** | WS2-d 정규화(값 변경) — 백테스트 게이트 후 최종 머지 | A (독립 PR) | 백테스트 성과 델타 + 리뷰 승인 |
| **M5** | 문서/INDEX 갱신 · dead code 제거 · 전략 재활성(StochRSI) paper 검증 | — | verifier 최종 |

---

## 8. 리스크 & 롤백

| 리스크 | 완화 |
|---|---|
| WS2-d 키/알고 통일이 기존 전략 신호를 바꿈 | 소비자 grep + 백테스트 델타 게이트, 독립 PR, feature-flag 가능 시 점진 전환 |
| 핫패스 성능 저하 (shared delegate 시) | 프로파일링 선행(§6.3), 저하 시 pin-only 유지 |
| 프론트 배선 변경이 빌더 플로우 회귀 | vitest + 브라우저 e2e, 방향3(최소침습)으로 단계적 이행 |
| StochRSI prev-K 상태가 재시작 시 유실 | Redis 저장 + TTL, 재시작 복구 테스트 |
| CVD 백테스트 재현 불가(체결 데이터 부족) | 데이터 가용성 선확인, 부족 시 WS5를 후순위로 |

**롤백:** 각 워크스트림은 독립 PR. WS2-d를 제외하면 전부 additive → revert 안전.
WS2-d는 값 변경이므로 머지 전 백테스트 스냅샷 보관, 이상 시 즉시 revert.

---

## 부록 A — 참고 파일 인덱스 (2026-07-04 조사 기준)

**백엔드 계산:** `services/trading/indicator_calculations.py`(핫패스 BB/RSI/Stoch/ADX/MFI/ATR),
`services/trading/indicator_queries.py`(get_indicators/features/momentum/daily),
`shared/indicators/momentum.py`(TRIX/CCI/MACD/Stoch/Williams/RSI/OBV),
`shared/indicators/{volume,volume_ratio,orderbook,composite,technical,daily}.py`,
`shared/indicators/{contracts,resolver}.py`(요청 라우팅 — 계산 아님),
`core/indicator_engine.py`(polars 중복), `shared/regime/adaptive_detector.py`(regime 중복),
`shared/backtest/{adapter,daily_adapter}.py`.

**빌더:** `config/strategy_builder/indicators.yaml`, `shared/strategy_builder/{catalog,schema,evaluator,runtime_support}.py`,
`services/dashboard/routes/{strategy_builder,kis_builder}.py`,
`strategy-builder-ui/src/lib/builder/constants.ts`, `src/types/builder.ts`,
`src/components/builder/IndicatorSelector.tsx`, `src/hooks/useStrategyBuilder.ts`,
`src/lib/dashboard/strategyBuilder.ts`(미사용 getCapabilities).

**테스트:** `tests/unit/trading/test_indicator_engine*.py`, `tests/unit/test_momentum_indicators.py`,
`tests/unit/indicators/test_{contracts,resolver}_mtf_base.py`, `tests/unit/strategy/test_stochrsi.py`,
`tests/unit/dashboard/test_strategy_builder.py`, `tests/integration/test_bb_reversion_15m_parity.py`,
`strategy-builder-ui/src/lib/builder/*.test.ts`.

## 부록 B — 지표 tier 분류 (WS3)

- **Tier 1 (구현됨, 노출만):** williams_r, cci, trix, obv, rvol, mfi, ichimoku, orderbook_imbalance,
  volume_acceleration, vr, composite_score, stochrsi(WS1 후).
- **Tier 2 (표준 갭, 신규 구현):** parabolic_sar, supertrend, donchian, keltner, roc, (+선물: cvd, volume_profile).
- **Tier 3 (미지원 배지):** DEMA/TEMA/HMA/KAMA 등 MA 변형, 캔들패턴 63종, Vortex/TSI/Ultimate 등 exotic.
