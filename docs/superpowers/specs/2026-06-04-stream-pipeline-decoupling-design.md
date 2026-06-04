# Stream Pipeline Decoupling — Design

- Date: 2026-06-04
- Status: Design (pending implementation plan)
- Goal: Isolate inter-module performance so indicator/strategy/LLM/order work can never delay the WebSocket ingest hot-path, by decomposing the trading runtime into per-asset, Redis-stream-connected daemons (the pub/sub structure originally intended but not realized).

## 1. Goal & success criterion

**진짜 목표 = 모듈 간 성능 격리.** WS ingest 레이턴시가 downstream(지표/전략/LLM/주문) 부하와 **무관**해야 한다. 이를 위해 단일 프로세스 asyncio 모놀리식을 **자산별 stream-connected 데몬**으로 분해한다(원래 의도했으나 미실현된 Redis-stream pub/sub).

**SLO (success invariant):** ingest 레이턴시 ⊥ compute 부하. 구체적으로 tick→stream(XADD) p99와 market-data staleness p99가 indicator/strategy/LLM/order backlog가 쌓여도 상승하지 않을 것. (절대 수치는 라이브 메트릭으로 보정하되 불변식이 합격 기준.)

비목표(out of scope): ClickHouse runtime 사용, ML/RL, 완전 per-symbol 샤딩, dashboard 재설계, 실전 주문 로직 대규모 변경.

## 2. Current state (감사 + Stage 0 측정 결과)

- **활성 트레이딩(주식+선물 paper) = 모놀리식 in-process orchestrator** (`services/trading/orchestrator.py`): WS 콜백이 같은 이벤트루프에서 `indicator_engine.on_tick` 동기 호출 → 전략 사이클(+KIS 주문 I/O) → in-proc `OrderExecutor`. 스크린 종목·LLM 컨텍스트·지표는 Redis KEY / in-memory(스트림 소비 아님).
- **선물 Phase 5 tail은 스트림 기반(존재, 일부 비활성)**: `decision_engine → stream:signal.candidate → risk_filter(XREADGROUP) → stream:signal.final → order_router(XREADGROUP) → stream:order.fill`. 단 decision_engine의 시장데이터 입력이 **stub(`context_provider`가 None 반환, "Task 17")** → 현재 실시그널 미생성.
- **news/LLM 파이프라인은 이미 스트림 consumer-group 병렬**: news_collector→`stream:news.raw`→news_scorer(XREADGROUP)→`stream:news.scored`. macro, kill_switch도 스트림.
- **tick 스트림은 관측 사이드채널**: orchestrator가 in-proc 소비 **후** `market:ticks`(주식)/`raw_data`(선물)에 XADD. 소비자는 stream_exporter(Prometheus)·LLM collectors뿐. **트레이딩은 이 스트림을 XREAD하지 않음.**

**Stage 0 측정:**
- per-tick `indicator_engine.on_tick` = O(1) 순수 Python 캔들 누적, **I/O·pandas 없음**. 지표(BB/RSI/VWAP)는 캔들 완성 시 lazy+캐시.
- 전략 decision 마이크로벤치: 100종목 entry ~52μs, 20포지션 cycle 0.04ms (SLA 5s 대비 PASS).
- → **per-tick·전략 비용은 싸다.** 병목은 "지표 계산 자체"가 아니라 **단일 이벤트루프(GIL) 경합**: WS reader + on_tick + 전략 사이클 + LLM 분석 루프(OpenAI 호출) + Redis publish + ClickHouse flush/warmup이 한 프로세스. 무거운/블로킹 형제 작업이 이벤트루프를 잡으면 WS reader가 프레임을 못 읽어 tick 지연.
- 계측 존재(라이브 검증): `market_data_staleness_hist`, `trading_signal_latency_ms`, `trading_order_latency_ms`, tick→XADD seconds.

## 3. Locked decisions (브레인스토밍 2026-06-04)

| 결정 | 선택 |
|---|---|
| 분리 범위 | **전체 다단 분리** (ingest → indicator → decision → risk_filter → order_router) |
| 주식/선물 구조 | **공유 단계 프레임워크 + 자산별 인스턴스** (코드 1벌, 런타임 자산별 데몬) |
| per-stage 병렬도 | **단계별 단일 ordered consumer** (fan-out 없음; symbol 샤딩은 future option) |
| 지표 warmup | **parquet** (`MARKET_DATA_SOURCE=parquet`) — **ClickHouse 배제** |
| 영구 기록 | **SQLite runtime ledger** — ClickHouse는 optional async mirror(범위 밖) |
| tick back-pressure | `MAXLEN ~ N` drop-oldest (최신 우선) |
| 배포 | systemd 데몬(자산×단계), paper/live 별도 clone + per-env Redis(6381/6382) 정합 |
| 컷오버 | strangler, 자산별 flag, 측정 게이트, 롤백가능 |

## 4. Target architecture

### 4.1 Stage topology (자산별 독립 데몬, Redis 스트림 연결)
```
[Ingest]   KIS WS (stock H0STCNT0 / futures H0IFCNT0+H0IFASP0)
           유일 임무: frame → 정규화 → XADD(MAXLEN~) market:ticks | raw_data
              │  (지표/전략/블로킹 I/O 없음 — 레이턴시 격리의 핵심 프로세스)
              ▼
[Indicator] XREADGROUP(tick stream) → 1분봉 누적 + 지표 계산 → XADD stream:indicators.{asset}
              │  (시작 시 parquet warmup; per-symbol 상태 보유)
              ▼
[Decision]  XREADGROUP(indicators) + (universe·LLM-context·regime gate = Redis KEY read)
              → 전략 진입/청산 → XADD stream:signal.candidate.{asset}
              ▼
[RiskFilter] XREADGROUP(candidate) → 리스크 체크 → XADD stream:signal.final     (기존 데몬 일반화)
              ▼
[OrderRouter] XREADGROUP(final) → KIS 실행(주식 ATS 포함) → XADD stream:order.fill (기존 데몬 일반화)
```

스트림 = **자산별 스트림(asset-suffixed)** 으로 완전 격리(자산별 인스턴스 + per-env Redis와 정합). 각 데몬이 자기 스트림만 소유:
- `market:ticks`(주식)/`raw_data`(선물) — **이미 존재**, 지금은 관측용. 본 설계가 이를 **load-bearing ingest 스트림**으로 승격(자산별로 이미 분리됨).
- `stream:indicators.{asset}` — 신규.
- `stream:signal.candidate.{asset}` / `stream:signal.final.{asset}` / `stream:order.fill.{asset}` — **기존 선물 contract 스키마 재사용**. 선물 기존 `stream:signal.candidate`(무접미사)는 `…candidate.futures`로 일반화(M4에서 마이그레이션, 기존 동작 보존).

### 4.2 공유 단계 프레임워크 (DRY 핵심)
`shared/streaming/stage.py`에 `StreamStage` 베이스 클래스 추출:
- consumer-group 생성(mkstream), XREADGROUP(block/batch) 루프, XACK, 에러정책(parse 오류 → XACK poison-pill drop / 처리 실패 → NO-XACK retry / 발행 실패 → NO-XACK), graceful shutdown, 메트릭/heartbeat.
- 이 패턴은 `services/news_scorer/main.py`, `risk_filter/main.py`, `order_router/main.py`에 **이미 거의 동일하게 반복** → 추출하여 단일 소스화(DRY 원칙).
- 각 단계(Indicator/Decision/…)는 `StreamStage`를 상속하고 **asset config 주입으로 stock/futures 인스턴스화**. ingest 데몬은 producer-only(별도 베이스 또는 thin).

각 단계의 단일 책임/인터페이스:
- **Ingest**: WS frame → normalized tick dict → XADD. 의존: KIS WS adapter, Redis. 상태 없음.
- **Indicator**: tick → candle/indicator snapshot. 의존: tick stream, parquet warmup, Redis. 상태: per-symbol rolling.
- **Decision**: indicators(+context keys) → signal candidate. 의존: indicators stream, universe/LLM/regime keys, strategy registry. 상태: 경량.
- **RiskFilter/OrderRouter**: 기존 책임 유지, 자산 일반화.

### 4.3 핵심 엔지니어링 결정
- **per-symbol 순서**: 단계별 단일 consumer → 스트림 순서 보존. Stage0(μs·적은 종목수: 주식 universe 수십, 선물 1–2)로 정당화. 확장 필요 시 symbol-hash 샤딩(문서화된 future option, YAGNI).
- **warmup = parquet**: Indicator 데몬 콜드스타트 시 parquet에서 최근 분봉 시드(현 `indicator_engine.seed_daily_candles`의 ClickHouse 경로를 parquet로 대체). ClickHouse 미사용.
- **영구 기록 = SQLite ledger**: risk/order 감사(signals_all/order_fills/trades/positions)는 SQLite runtime ledger. ClickHouse mirror는 optional, 본 설계 의존성 아님.
- **back-pressure**: tick 스트림 `MAXLEN ~ N`(drop-oldest); 느린 indicator consumer가 ingest 차단·메모리 무한증가 불가. signal 스트림은 큰 maxlen(시그널 드롭 금지).
- **선물 stub 해소**: decision_engine의 `context_provider` stub을 **indicators 스트림 + context key 소비**로 대체 → 실시그널 생성(파이프라인 head 완성).

### 4.4 배포 & 환경 정합
- 운용 = systemd 데몬(Phase 5 패턴 확장): 자산 × 단계. 주식도 cron 모놀리식 → 데몬 모델로 이동.
- **paper/live 분리 정합**: 방금 도입된 별도 clone(`kis_unified_sts` / `_live`) + per-env Redis(paper 6381 / live 6382)에 그대로 적재 — 각 env 데몬이 해당 env Redis/스트림에 접속. 스트림 격리는 Redis 인스턴스 격리로 자동.
- **CH→SQLite 전환과 정합**: indicator warmup의 parquet 의존은 진행 중인 parquet market-data store(예: PR #404/#407)에 의존 → M2는 parquet store 완성 후 착수.

## 5. Migration (strangler, 측정 게이트, 자산별 flag, 롤백가능)

| M | 내용 | 산출/게이트 |
|---|---|---|
| **M0** | `shared/streaming/stage.py` `StreamStage` 추출 + news_scorer/risk_filter/order_router 리팩터(동작 보존) | 기존 테스트 green, 회귀 없음 |
| **M1** | **Ingest 데몬** 추출(WS reader → tick stream). orchestrator는 WS 직접 콜백 대신 tick stream을 XREADGROUP 소비. 자산별 flag(`STREAM_INGEST_{ASSET}`) | **Stage0 SLO 달성**(staleness/tick-lag 전후 비교) — 최고 ROI |
| **M2** | **Indicator 데몬** 추출(tick→indicators stream, parquet warmup). orchestrator는 indicators stream 소비 | 지표 CPU 프로세스 격리. parquet store 의존 |
| **M3** | **Decision 데몬** 추출→signal.candidate. 선물 decision_engine 입력을 indicators stream으로 배선(stub 제거) | 전략 격리 + 선물 head 완성 |
| **M4** | risk_filter+order_router **주식 일반화**(ATS·three_stage exit·EOD는 자산별 order_router 인스턴스) | 실행 격리. 가장 복잡 — 주식 실행 특성 보존 |
| **M5** | 모놀리식 orchestrator 컷오버(supervisor/health로 축소) | 최종 pub/sub 완성 |

각 M = 독립 PR, 자산별 flag로 점진 전환, 롤백가능, Stage0 SLO + 기존 perf 벤치마크로 검증. M1만으로도 명시한 레이턴시 문제는 해결.

**구현은 increment별 plan으로 분해한다(big-bang 아님).** 첫 implementation plan은 **M0(StreamStage 추출) + M1(Ingest 데몬)** 만 다룬다 — 이것이 SLO를 달성하는 최소·최고-ROI 단위. M2~M5는 각각 후속 spec/plan 사이클(measurement 게이트 통과 후).

## 6. Testing

- **단계별 단위**: consumer-group 생성/XREADGROUP/XACK 의미, poison-pill drop, NO-XACK retry, 단일 consumer 순서 보존, parquet warmup 시드.
- **End-to-end 통합**: 합성 tick 주입 → ingest→indicator→decision→candidate 통과 + 페이로드 정합.
- **Back-pressure 불변식(핵심)**: indicator/decision consumer를 인위적으로 지연시켜도 **ingest XADD 레이턴시 p99가 상승하지 않음** = Stage0 SLO. (느린 consumer + 부하 주입 하에서 ingest 레이턴시 측정.)
- 기존 `tests/performance/*` 재사용 + ingest 격리 회귀 벤치 추가.

## 7. Risks & mitigations

| 리스크 | 완화 |
|---|---|
| per-symbol 순서 깨짐 | 단계별 단일 consumer(현 종목수에 충분) |
| warmup 콜드스타트(재시작 시 지표 미성숙) | parquet 시드 + warmup guard(기존 패턴) |
| 주식 실행 일반화 복잡(ATS/three_stage/EOD) | 공유 프레임워크 + 자산별 order_router 인스턴스, M4를 마지막에 |
| CH→SQLite 전환과 충돌 | indicator warmup을 parquet로 정렬, M2를 parquet store 후 착수 |
| strangler 이중 실행(모놀리식+데몬 동시 주문 위험) | 자산별 flag 상호배제, 한쪽만 실행 보장, kill-switch 유지 |
| 데몬 수 증가(자산×단계×env) | 공유 프레임워크 + systemd 템플릿 + paper/live Redis 격리 |

## 8. Acceptance criteria

- [ ] `StreamStage` 단일 소스로 news_scorer/risk_filter/order_router가 동작 보존 리팩터됨.
- [ ] Ingest 데몬이 WS frame→XADD만 수행, orchestrator가 tick stream을 소비(M1).
- [ ] Back-pressure 테스트: 느린 downstream에도 ingest XADD p99 불변(Stage0 SLO).
- [ ] Indicator/Decision 데몬이 자산별 인스턴스로 동작, 선물 decision stub 제거.
- [ ] warmup·영구기록 경로에 **ClickHouse 없음**(parquet+SQLite).
- [ ] 자산별 flag로 모놀리식↔데몬 롤백 가능, 동시 주문 없음.
- [ ] DRY: 단계 코드 1벌(자산 config 주입), 스트림 contract 재사용.

## 9. Open questions (구현 계획에서 확정)

- `stream:indicators.{asset}` 페이로드 스키마(전체 지표 스냅샷 vs 델타) 및 maxlen.
- Decision 데몬의 strategy registry 재사용 방식(기존 StrategyManager 로직을 데몬으로 이식 vs 호출).
- M4 주식 order_router의 ATS VenueRouter·three_stage exit·EOD 규칙 배치.
- ingest 데몬과 기존 data_provider failover(REST fallback) 정책의 통합/폐기.
