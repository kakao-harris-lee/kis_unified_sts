# 지표 계산 엔진 재설계 + Redis 스트림 스키마 규격화 로드맵

- 날짜: 2026-07-05
- 성격: 아키텍처 방향 결정 + 실행 로드맵 (다중 워크스트림)
- 선행 조사: 본 문서 §1 (Strategy Builder 미완성 지표 e2e 추적 + 계산 SoT 중복 진단)
- 관련 문서:
  - `docs/plans/2026-07-04-indicator-coverage-builder-catalog-roadmap.md` (카탈로그/커버리지 선행 계획)
  - `docs/plans/2026-07-04-indicator-spike-pandas-ta-decision.md` (pandas-ta 스파이크 — 본 로드맵에서 오라클/폴백으로 재배치)
  - `docs/plans/2026-07-04-indicator-m2-handoff.md` (RSI/ADX Wilder 수렴 게이트)

---

## 0. TL;DR

두 개의 독립 트랙을 병렬로 진행한다.

**트랙 A — 지표 계산 엔진 단일화 (Single SoT).** 지금의 시간 낭비는 지표 *공식*이 아니라
**같은 지표를 5~7벌 손구현해 규약을 손으로 맞추는 이중 경로 구조**에서 나온다(§1). 이를
계층형 스택으로 붕괴시킨다:

| 계층 | 도구 | 역할 |
|---|---|---|
| 기본 지표 SoT | **TA-Lib** | 표준 basic 지표(RSI/ADX/ATR/BB/MACD/Stoch/OBV/WilliamsR/CCI…). 배치 + `talib.stream` 증분 |
| 대용량 컬럼 처리 | **Polars** | 다심볼 배치, lazy/멀티스레드, feature build, 캐시 엔진 팬아웃 |
| 커스텀/복합 지표 | **NumPy + Numba `@njit`** | TA-Lib 부재 지표(CVD/볼륨프로파일/regime feature/오더북) JIT 핫루프 |
| 벡터화 백테스트 | **vectorbt** | 지표 패널 위 포트폴리오 시뮬, Optuna 파라미터 스윕 가속 |

그 위에 **Indicator Cache Engine**(수천 종목 × 수백 지표, 중복 제거·증분·병렬)을 두어
런타임·백테스트·빌더가 **하나의 flat 패널**을 읽게 한다. 이 flat 패널이 §1에서 발견한
빌더 배관 갭(도달 불가 지표 7종·이름 불일치)까지 동시에 해소한다.

**트랙 B — Redis 스트림 스키마 규격화(Pydantic).** 한투 WebSocket→Redis→파이프라인이
자주 깨지는 원인은 **동적 타입(`payload.get("x") or payload.get("y")`)** 이다. 스트림당
Pydantic 모델 1장 + 인코더/디코더 코덱 + `schema_version`으로 규격을 고정해 스키마 단절
붕괴를 막는다. (트랙 B는 별도 에이전트 담당 — 본 브랜치 범위 밖.)

---

## 착수 상태 (2026-07-05, 브랜치 `feat/indicator-engine-track-a`)

트랙 A 기반 레이어가 **추가(additive)·인터페이스 우선**으로 착수됨. 런타임 핫패스·기존
`shared/indicators/*`·트랙 B 스트림 파일은 **미변경**(무충돌).

- **WS-A0 (부분):** `pyproject.toml`에 `TA-Lib>=0.5.1`·`polars>=1.0`(core),
  `performance=[numba]`·`backtest=[vectorbt]`(extra) 선언. 로컬 env는 TA-Lib 0.6.8 /
  numpy 2.4.0로 이미 wheel 해석 확인. (남은 것: Dockerfile 편입, numpy≥2.0 승격 스윕.)
- **WS-A1 (기반 착수):** 신규 `shared/indicators/engine/` 패키지 —
  `IndicatorBackend`(추상 인터페이스)·`IndicatorSpec`/`OHLCVWindow`/`IndicatorResult`(값
  객체)·`flat_key`(카탈로그 id/output→표준 flat 키 정규화, Gap D)·`TALibBackend`(16개
  표준 지표 데이터드리븐 테이블). RSI parity(vs 직접 talib), bollinger→`bb_*`,
  macd→`macd*`, stochastic→`stoch_*`, ema→`ema_20` 정규화 검증.
- **WS-A2 (씨앗):** `IndicatorEngine` 레지스트리가 `compute_many` 스펙 dedup +
  `flat_panel`(카탈로그 키 평탄화)까지 제공 — 캐시 엔진의 "중복 계산 제거 + flat 방출"
  계약 선반영.
- **검증:** unit 30개 green(TA-Lib 실제 계산 parity 포함), ruff/black/mypy(engine) clean.
- **미착수:** 캐시 엔진 증분·병렬(WS-A2 본체), 손구현 `_calc_*` 위임/삭제(WS-A1 후반),
  빌더 배관 배선(WS-A3), vectorbt/Numba(WS-A4/A5).

---

## 1. 문제 진단 (선행 조사 결과)

### 1.1 계산 SoT: 중복이 만드는 시간 싱크

- **동일 지표 다중 구현.** ATR 하나가 7군데에 존재:
  `services/trading/indicator_calculations.py:203`(`_calc_atr_raw`)·`:221`(`_calc_atr_normalized`),
  `shared/indicators/reference.py:586`(canonical),
  `shared/indicators/technical.py:219`, `shared/regime/adaptive_detector.py:422`,
  `shared/llm/unified_trading_analyzer.py:161`, `shared/strategy/entry/trix_golden.py:462`.
  RSI·ADX·BB·StochRSI도 같은 패턴.
- **이중 경로 + parity 세금.** 스트리밍 핫패스(`indicator_calculations.py`의 순수 파이썬
  `_calc_*`)와 배치/reference가 분리돼 있어, 규약이 어긋날 때마다 손으로 수렴시킨다. 지난
  한 달 PR 10여 개(#561 RSI Wilder 수렴, #562/#565 ADX/VR canonical 위임,
  #567~#569 ATR Phase 1a/1b canonical 통합, #571 ATR Phase 2)가 전부 이 통합 작업이다.
- **핵심 관찰: 핫패스는 이미 전체 재계산형이다.** `indicator_calculations.py:41-55`의
  `_calc_rsi`는 "Wilder-EMA over the FULL series … do NOT window" — tick 증분(stateful)이
  아니라 매 호출 전체 재계산이다. 따라서 "라이브러리는 전체 재계산이라 증분 핫패스에
  부적합"이라는 논거가 성립하지 않으며, **별도 손구현 핫패스를 유지할 이유가 없다.**

### 1.2 빌더 배관: 카탈로그 플래그가 현실을 과장

빌더 런타임 평가기 `BuilderStrategyEntry._build_series`
(`shared/strategy/entry/builder_strategy.py:206-223`)는 지표를 **`context.indicators`의
flat 최상위 키로만** 조회한다. 그런데 엔진이 방출하는 키와 카탈로그(18종)가 어긋나 있다.

| 상태 | 지표 | 근거 |
|---|---|---|
| ✅ 바로 사용 | rsi, atr, adx, vwap, mfi, rvol, volume_acceleration, volume_ma | `indicator_queries.py` flat 방출 |
| ⚠️ 정확한 키 별칭 필요 | ema(→`ema_20`), bollinger(→`bb_upper/…`) | 카탈로그 output id ↔ 런타임 키 불일치 |
| ❌ 미도달(카탈로그는 true) | **sma, macd, stochastic, williams_r, cci, trix, obv** | flat 키 없음 / `momentum_5m` 중첩 dict 안 |
| ⛔ 미배선 | **ichimoku** | 계산기(`technical.py`)는 있으나 어떤 엔진도 미호출 |

추가로 `cross_above/cross_below` 연산자는 스트리밍 런타임에서 절대 발화 불가
(`shared/strategy_builder/runtime_support.py`), 그런데 프론트는 경고 없이 노출하고
프리셋 `golden_cross/trend_filter`에 사용 중(가드 헬퍼 `CROSS_OPERATORS`는 죽은 코드).

**결론: 빌더 배관 갭은 계산 라이브러리와 직교한다.** 단, Indicator Cache Engine이 flat
패널을 표준 키로 방출하면 이 갭 대부분이 캐시 엔진의 부수효과로 해소된다(§4, WS3).

---

## 2. 목표 아키텍처

```
                         ┌─────────────────────────────────────────────┐
 Parquet/DuckDB (과거) ─▶│  Indicator Cache Engine (shared/indicators)  │
 Redis 5m/1m bars (실시간)│  · dedup: (symbol, id, params, tf)          │
                         │  · incremental: ring-buffer + talib.stream   │
                         │  · parallel: Polars group_by / TA-Lib pool   │
                         │  계산 계층:                                   │
                         │    TA-Lib(기본) · Numba@njit(커스텀)          │
                         └───────────────┬─────────────────────────────┘
                                         │ flat 패널 (카탈로그 id 키)
                    ┌────────────────────┼───────────────────────┐
                    ▼                    ▼                       ▼
        Redis DB1 flat 캐시        vectorbt 백테스트        builder evaluator
        (TTL, prev값 포함)         (Polars feature)         (flat 키 도달 → 갭 해소)
                    │
   decision_engine / stock_strategy / risk / order 소비자 (동일 패널 read)
```

원칙(CLAUDE.md 준수):
- **Config-driven:** 지표 파라미터·캐시 TTL·스트림 스키마 버전은 YAML/env.
- **DRY:** 계산 권한은 캐시 엔진 하나. `shared/`가 SoT, `services/`·`domains/`는 얇게.
- **Redis DB1 + TTL:** 캐시 키 24h(누적 48h) 기본.
- **KST-native, look-ahead 금지:** 패널은 bar-close causal로 생성 → vectorbt 인덱싱 시
  미래 봉 누수 없음.
- **ClickHouse 미도입 유지:** 배치는 Parquet/DuckDB + Polars.

---

## 3. 트랙 A 워크스트림

### WS-A0 — 의존성/빌드 기반

- **TA-Lib (검증된 wheel 설치 — 소스 빌드 불필요):** 레포 파이썬 이미지가 전부
  `python:3.11-slim`(Debian/glibc)이라 **ta-lib-python 0.5.x의 prebuilt manylinux wheel**이
  그대로 해석된다. 과거의 C 소스 빌드(apt `libta-lib` / configure-make) **불필요**,
  의존에 `TA-Lib`만 추가하고 `pip install TA-Lib`로 끝. 대상 파일(모두 이미 slim):
  `Dockerfile`, `Dockerfile.prod`, `Dockerfile.dashboard`, `Dockerfile.test`,
  `Dockerfile.forecasting`, `Dockerfile.stream_exporter`. devcontainer도 Debian 기반
  (`mcr.microsoft.com/devcontainers/python:3.11`) → 동일하게 wheel 해석.
  **제약:** Debian-slim/glibc 유지(현행 전부 충족), musl/**alpine 전환 금지**(musllinux
  wheel 미보장). Python 3.11 핀 유지 시 wheel 존재 확인만 하면 됨. → `container-engineer`.
- **Polars** 런타임 의존 추가(일부 이미 사용 중). **Numba**는 `[performance]` optional extra.
  **vectorbt**는 무거운 전이 의존(plotly/numba)을 격리하도록 `[backtest]` optional extra.
- **numpy>=2.0 승격 스윕:** TA-Lib/Polars/vectorbt 호환 위해 `shared/**`·`services/**`
  numpy 2.x 호환 확인 후 하한 상향. (선행 스파이크 §7 리스크 항목 재사용.)
- **게이트:** 3개 Dockerfile + devcontainer 빌드 성공, `import talib, polars, numba, vectorbt`
  스모크, CI 매트릭스 통과.

### WS-A1 — 기본 지표 SoT: TA-Lib 어댑터

- 신규 `shared/indicators/talib_adapter.py`: TA-Lib 함수 → **카탈로그 id/output 표준 키**
  정규화(§1.2 이름 불일치 해소, 예: `bollinger.upper→bb_upper`, `stochastic.k→stoch_k`).
  배치(`talib.RSI`)와 증분(`talib.stream.RSI`) 양쪽 래핑.
- **규약 확정(1회):** RSI=Wilder, BB=ddof0(TA-Lib 기본), ATR=Wilder, ADX=Wilder. 확정 후
  copy별 재조정 종료.
- 기존 손구현 `_calc_*`(ATR×7, RSI, ADX, RVOL 등)를 어댑터로 **위임 후 삭제**. ATR Phase 1이
  이미 이 방향 → 전 지표로 확장.
- **parity 오라클:** 기존 하네스 `tests/unit/indicators/test_calc_parity.py` 확장 —
  TA-Lib(정본) vs 기존 canonical vs pandas-ta-classic(교차검증) 허용오차 assert.
  pandas-ta-classic(선행 스파이크에서 채택 결정)은 **런타임에서 빠지고 test-only 오라클**로
  재배치.
- **게이트:** 값 변경분(RSI SMA→Wilder, BB ddof 이동 등)은 기존 백테스트 게이트 프로세스
  (`indicator-m2-handoff.md`) 재사용. Parquet 데이터 있는 배포호스트에서만 실행 가능.

### WS-A2 — Indicator Cache Engine (핵심)

- 신규 `shared/indicators/cache_engine.py` + 런타임 `services/indicator_cache/`.
- **중복 제거:** 활성 전략·빌더 상태에서 요청 지표를 `(symbol, indicator_id, params, tf)`로
  집계 → 유니크 계산만 수행(RSI(14)를 10개 전략이 써도 1회).
- **증분 업데이트:** 심볼별 bounded ring buffer(설정 가능한 창) 유지, bar-close마다
  `talib.stream`으로 최신값만 계산. cold start/backfill만 full 재계산.
- **병렬 처리:** 두 경로 벤치 후 택1 —
  (a) Polars long-format(`symbol,ts,ohlcv`) `group_by(symbol)` 벡터화,
  (b) TA-Lib per-symbol thread/process pool. 목표: 수천 종목 × 수백 지표 bar 주기 내 완료.
- **캐시 write:** **flat 최상위 키(카탈로그 id 명명) + `{id}_prev` 이전값**을 Redis DB1에
  TTL과 함께 기록. 소비자(빌더/전략/decision_engine/backtest)는 이 패널만 read → 이중 경로
  소멸.
- **게이트:** ① N 종목 × M 지표 per-bar 지연 벤치(유니버스 top_n≈20~30 현행 + 수천 스케일
  목표 둘 다), ② 증분값 == 배치값 parity, ③ 빌더 flat-key e2e 도달.

### WS-A3 — 빌더 배관 정합 (§1.2 갭 해소, 캐시 엔진 위)

- 캐시 엔진이 williams_r/cci/trix/obv/sma/macd/stochastic/ichimoku를 **flat 방출** →
  카탈로그 `runtime_supported` 플래그를 실측과 정합(현재 과장 상태 교정).
- 이름 정규화 맵을 `_build_series`(entry/exit)와 브리지 `kis_builder.py`가 공유.
- **cross 연산자:** 캐시가 `{id}_prev`를 제공하므로 스트리밍 cross 지원 가능
  (`runtime_support.py` 제약 재평가) — 우선은 프론트 "런타임 미지원" 경고 + 죽은
  `CROSS_OPERATORS` 헬퍼 배선/프리셋 라벨링(→ `strategy-builder`/`frontend` 팀).
- ichimoku 계산기 캐시 엔진 배선 후 카탈로그 플래그 true 전환.
- **게이트:** 빌더 전략 e2e(williams_r 조건 실발화), 프리셋 golden_cross 동작 확인.

### WS-A4 — 대용량 배치 & 벡터화 백테스트 (Polars + vectorbt)

- `market_data_store`(Parquet) → Polars lazy feature build로 백테스트 프리컴퓨트 전환.
- vectorbt로 지표 패널 위 포트폴리오 시뮬 + Optuna 스윕 가속. 기존 `shared/backtest/adapter.py`
  경로와 **결과 parity**(동일 전략·동일 기간 수익/샤프/MDD) 확인 후 교체.
- **look-ahead:** 패널은 bar-close causal → vectorbt 인덱싱 미래 봉 누수 없음을 `LookaheadGuard`
  회귀로 고정.
- **게이트:** 기존 백테스트 vs vectorbt 수치 일치 + 속도 개선 측정.

### WS-A5 — 커스텀/복합 지표 (NumPy + Numba `@njit`)

- TA-Lib 부재 지표: CVD, 볼륨 프로파일, regime feature, 오더북 파생. `@njit` 핫루프로
  구현, 캐시 엔진 플러그인 인터페이스(`register_indicator`)로 편입.
- **게이트:** numba 유/무 결과 동일, 벤치(가속 배수 기록).

---

## 4. 트랙 B — Redis 스트림 스키마 규격화 (Pydantic)

독립 트랙. 지표 스택과 병렬 진행 가능.

### 문제

producer는 raw dict를 `xadd`, consumer는
`_parse_float(payload.get("current_price")) or _parse_float(payload.get("close")) or …`
(`services/monitoring/tick_stream_publisher.py:292-294`)처럼 다중 키·방어적 코어션에 의존
→ 필드명/타입이 조금만 바뀌어도 조용히 깨진다(스키마 단절).

### WS-B1 — 스트림 메시지 모델 (한 스트림 = 한 스키마)

- 신규 `shared/models/stream_models.py` (사용자 예시의 `structures/`가 아니라 레포 DRY
  컨벤션 `shared/models/`에 배치). 스트림별 Pydantic 모델 1장 + `schema_version`.

```python
# shared/models/stream_models.py
from pydantic import BaseModel

class StreamMessage(BaseModel):
    schema_version: int = 1  # 스키마 단절 조기 탐지용

class KisTickData(StreamMessage):
    ticker: str
    price: int
    volume: int
    beta: float | None = None  # 헤지 계산용 포트폴리오 베타

class HedgeOrderMessage(StreamMessage):
    futures_ticker: str
    order_qty: int
    direction: str  # 'BUY' | 'SELL'

# 이하 각 스트림당 1모델: SignalMessage(stream:signal.final),
# RiskDecisionMessage, OrderMessage, KillSwitchEvent(kill_switch:events),
# NewsScoredMessage(stream:news.scored), HedgeMessage(stream:portfolio.hedge) …
```

### WS-B2 — 코덱 (인코딩/디코딩 단일 경로)

- 신규 `shared/streaming/codec.py`: Redis Stream 필드(flat str map) 제약을 흡수.
  - `encode(model) -> dict[str, str]`: 스칼라는 그대로, 중첩은 `data` 필드에
    `model.model_dump_json()`.
  - `decode(cls, fields) -> model`: `model_validate` — 실패 시 명시적 예외(조용한 통과 금지).
  - `schema_version` 불일치 시 거부/업그레이드 훅.
- 모든 producer/consumer를 코덱 경유로 마이그레이션. `.get()` 동적 접근 제거.

### WS-B3 — 점진 롤아웃 & 검증

- **양방향 호환 기간:** consumer는 신·구 포맷 모두 read, producer는 신 포맷 write →
  스트림별 순차 전환(무중단).
- 스트림 키는 이미 config-driven(`config/*.yaml`) → 목록화하고 스트림별 모델 매핑 등록.
- **게이트:** 스트림별 round-trip 계약 테스트, 잘못된 타입 주입 시 검증 거부(회귀),
  하위호환 시나리오, hermetic(fakeredis) 격리 → `test-reliability-engineer`.

---

## 5. 우선순위 / 시퀀싱

1. **WS-A0 → WS-A1 → WS-A2** (계산 SoT + 캐시 엔진): 시간 싱크의 근원 제거. 최우선.
2. **WS-A3** (빌더 갭 해소): 캐시 엔진 직후, 사용자 체감 가치 즉시(미도달 지표 7종 부활).
3. **WS-B1~B3** (스트림 스키마): 트랙 A와 **병렬**. 파이프라인 안정성 독립 개선.
4. **WS-A4 / WS-A5** (vectorbt / 커스텀): 배치·확장 단계.

빠른 승리(선행 스파이크에서 확인, 의존성 무관): 값 변경 없는 통합부터 — 핫패스 `_calc_*`를
canonical/어댑터로 위임(이중 경로 제거). 값 변경분(RSI/BB 규약 이동)은 백테스트 게이트 뒤.

---

## 6. 리스크 & 완화

| 리스크 | 영향 | 완화 |
|---|---|---|
| ~~TA-Lib C 빌드 의존~~ → **해소** | (선행 스파이크가 이 때문에 pandas-ta 선택했으나 무효화됨) | 기존 `python:3.11-slim`(Debian/glibc) 베이스 + ta-lib-python 0.5.x **manylinux wheel**로 소스 빌드 없이 `pip install TA-Lib` 성립. 유일 제약: **musl/alpine 전환 금지**. pandas-ta-classic은 이제 빌드 폴백이 아니라 **test-only parity 오라클**로만 잔존 |
| **numpy 2.0 / pandas 3.x 승격** | 전역 호환 드리프트 | 호환 스윕 후 하한 상향, pandas 상한(`<3`) 검토, CI 매트릭스 |
| **vectorbt 무거운 의존** | 런타임 footprint 오염 | `[backtest]` optional extra 격리, 런타임 미설치 |
| **값 규약 이동(RSI SMA→Wilder, BB ddof)** | 백테스트↔런타임 시그널 델타 | 기존 백테스트 게이트 + parity 하네스 허용오차 assert |
| **증분(talib.stream) vs 배치 값 불일치** | 캐시 신뢰성 | WS-A2 게이트에서 증분==배치 회귀 고정 |
| **수천 종목 스케일 지연** | bar 주기 초과 | Polars 벡터화/pool 벤치를 게이트로; 유니버스 현행 top_n 작음 → 여유 |
| **스트림 전환 중 포맷 혼재** | 소비자 붕괴 | 양방향 호환 기간 + 스트림별 순차 롤아웃 + 계약 테스트 |
| **Redis Stream flat 필드 제약** | 중첩 모델 직렬화 | 코덱이 `data=model_dump_json()`로 흡수 |

---

## 7. 완료 정의 (Definition of Done)

- 손구현 `_calc_*` 중복 제거(ATR×7 → 1), 계산 권한이 캐시 엔진 하나로 수렴.
- 카탈로그 18종 `runtime_supported` 플래그가 실측과 일치(과장 없음), 미도달 7종 부활,
  ichimoku 배선, cross 연산자 처리(지원 또는 명시 경고).
- 백테스트가 vectorbt로 동일 결과·더 빠른 스윕, look-ahead 회귀 통과.
- 모든 Redis 스트림이 Pydantic 모델+코덱 경유, 동적 `.get()` 제거, 계약 테스트 그린.
- CLAUDE.md 규칙 유지: config-driven, DRY, Redis DB1+TTL, KST-native, ClickHouse 미도입.

---

## 8. 오너/에이전트 매핑

- 계산 SoT/어댑터/커스텀 지표: `indicator-specialist`, `refactorer`
- 캐시 엔진 성능/병렬: `performance-auditor`, `execution-specialist`
- 빌더 배관: `strategy-builder`, `frontend-realtime-engineer`
- 백테스트(vectorbt)/검증: `backtest-engineer`, `model-evaluator`
- 의존성/빌드/CI: `container-engineer`, `ci-pipeline-engineer`, `devx-harness`
- 스트림 스키마/테스트: `data-engineer`, `test-reliability-engineer`, `architecture-auditor`
