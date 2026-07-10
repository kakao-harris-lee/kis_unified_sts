# 신규 아키텍처 리팩토링 계획 (2026-07-08)

> 지시서: [docs/2026-07-08_new_architencture.md](../2026-07-08_new_architencture.md)
> 근거 분석: [2026-07-08-new-architecture-gap-analysis.md](2026-07-08-new-architecture-gap-analysis.md)

## 0. 계획 원칙

1. **단계마다 테스트 가능 상태 유지** (지시서 마지막 문단). 각 Phase는 독립 머지 가능한
   PR 묶음이며, 실패 시 해당 Phase만 롤백한다.
2. **기존 것을 완성시키는 방향 우선**: Gap 분석 결론대로 TA-Lib 엔진·builder_v1·
   실행계층 seam은 이미 존재한다. 신규 구축은 vectorbt 러너와 Risk 프리미티브 통합에 집중.
3. **Parity 게이트 없이는 어떤 계산 경로도 교체하지 않는다**: shadow-parity(지표),
   신호 동등성(전략), 성과지표 일치(백테스트)가 각 교체의 머지 조건.
4. **운영 불변식 유지**: KST-only, Redis DB1+TTL, config-driven(하드코딩 금지),
   선물 long/short 대칭, 주식 EOD 일괄청산 금지, live 게이트/kill-switch 무손상,
   paper 스택 무중단.
5. **Non-goals (지시서의 문맥적 해석)**:
   - 라이브 포지션 추적·RuntimeLedger·VirtualBroker는 vectorbt로 대체하지 **않는다**
     (vectorbt는 백테스트 전용; 라이브 경계는 이미 깔끔히 분리돼 있음 — Gap §3.5).
   - 상태머신 exit(three_stage, momentum_decay)는 선언형으로 강제 환원하지 않고
     "exit 프리미티브 라이브러리"로 존치한다 (지시서 "포지션 관리 로직 최소화"의 실용 해석).
   - 모놀리식 오케스트레이터 은퇴는 F-9 컷오버(운영자 게이트)와 연동되는 별도 트랙.

## 1. 지시서 요구 → Phase 매핑

| 지시서 요구 | Phase |
|---|---|
| 직접 구현한 기술지표 계산 제거 → TA-Lib | P1 |
| 새 지표 = Registry 등록만으로 추가 | P1 (이미 `_TABLE` data-driven — 카탈로그 정합만) |
| 전략 = YAML 선언만으로 실행 | P2 |
| 전략 엔진은 Indicator Context만 읽고 조건만 평가 | P1(내장 계산 제거) + P2 |
| Portfolio/Backtest/성과지표 → vectorbt | P3 |
| Risk Engine 분리 (stop/trailing/MDD/size/일손실/동시진입/레버리지/증거금) | P4 |
| Futures Context Engine (외인/OI/basis/롤오버/틱가치/증거금) | P5 |
| Hedge Engine (현물+선물, 부분/전체 헤지, 노출 계산) | P5 |
| 백테스트/실거래 동일 전략, 실행계층만 상이 | 이미 성립 — P3·P6에서 계약으로 강제 |
| 기존 YAML·Builder UI·KIS Adapter·실시간 주문/수신 유지 | 전 Phase 공통 제약 |

## 2. Phase 0 — 기반 정리 (선행, 소규모)

**목표**: 이후 Phase의 잡음 제거. 기능 변화 0.

- [ ] Dead code 제거 (~2,600 LOC + 고아):
  `shared/ml`(pycache만 잔존), `shared/trend`(880, 런타임 importer 0),
  `shared/ensemble`(435), `shared/arbitrage`(332, 소비자 미배선),
  `shared/position`(~694, test-only 고아 — PositionTracker로 대체됨),
  CLAUDE.md의 vestigial `domains/` 참조 정리(디렉토리 자체는 `336df723`에서 이미 제거됨).
  각 삭제 전 cron/CLI 참조 재확인.
  ⚠️ `market_structure_collector`/`market_risk_engine`은 통합투자시스템 P0/P1 소속 — 삭제 금지.
- [ ] `shared/position/monitor.py` dead stub(:137 항상 False) 및
  `exit_checker.py`(three_stage와 중복 상태머신) 정리 — 소비자 확인 후 three_stage로 단일화.
- [ ] **TA-Lib 설치 게이트**: CI와 배포 호스트 .venv에 TA-Lib 존재를 검증하는 체크 추가
  (미설치 시 shadow-parity가 조용히 스킵되는 기존 함정 차단).
- [x] vectorbt CI 레인: `.[backtest]` extra 설치 + import smoke 테스트 (P3 준비).
  P3-a 에서 VectorbtRunner parity 스위트 실행으로 확장됨 (advisory lane).
- [ ] stale worktree(~11개) prune (repo 위생, 커밋 대상 아님).

**게이트**: 전체 pytest green, 활성 6전략 paper 무영향.

## 3. Phase 1 — Indicator SoT 완성: TA-Lib 위임 (지시서 §2·§3)

**목표**: "직접 EMA/RSI 계산 코드 전부 제거"를 기존 Track A 온램프
(`STS_INDICATOR_CONVENTION` convention gate + shadow-parity)로 완성한다.
선행 로드맵 `2026-07-05-indicator-engine-and-stream-schema-roadmap.md`와 정합 — 본 계획이 우선순위를 승격.

### P1-a. 두 번째 수제 SoT(`reference.py`) 흡수
- `ATRCalculator`(sma|wilder)/`ADXCalculator`/`StochRSICalculator`/`MFICalculator`/`wilder_rsi`를
  엔진 어댑터 뒤로 이동. TA-Lib 네이티브와 수제 관례의 차이(warmup, flat-window sentinel
  RSI/MFI=50 vs 0, ATR sma-vs-wilder)는 **계약 테스트로 고정** 후 백엔드 선택으로 처리.
- `numpy_backend.py` 내부 수제 `_ema/_atr/_wma`(:43,58,72)를 TA-Lib 프리미티브 조합으로 교체.

### P1-b. 패키지 밖 수제 사이트(~50개) 엔진 배선 — 우선순위순
1. **`shared/backtest/`** (`daily_adapter.py:261-388`, `adapter.py:187-228`,
   `market_context_replay.py:49-75`) — 백테스트↔라이브 지표 parity의 원천이므로 최우선.
2. **`shared/strategy/` 내장 계산 7곳** (macd_ema_crossover, trix_golden, vr_composite,
   opening_volume_surge + 대응 exit 3곳) — 지시서 §4 위반 해소. `required_indicators`
   확장 + resolver 경유로 전환.
3. `services/daily_scanner`, `services/trading/indicator_calculations.py` 잔존
   (`_calc_daily_ema_aligned:144-178`, `_ema_series`, `_calc_high_n`).
4. `shared/scanner/accumulation.py`, `shared/llm/`(analyzers/market_analyzers/stock_screening),
   `shared/regime/` 잔존 — 신호 경로가 아니므로 후순위, 동일 패턴 적용.
- 제외(정당한 예외로 문서화): `stateful.py`(세션 VWAP/틱초 VolumeAccel), orderbook 불균형,
  VR-zone, HAR-RV·OFI·OLS β 등 일반 통계.

### P1-c. Convention flip
- shadow-parity를 gated 지표(atr, bb_width ~2.53%, stoch_k)까지 수렴시킨 뒤
  백테스트 재현 게이트(활성 6전략, 동일 기간 동일 트레이드) 통과 시
  `STS_INDICATOR_CONVENTION=talib` flip. **flip은 운영자 게이트** (paper 관찰 1주 권장).
- flip 후 Compat 백엔드(streaming/momentum/daily/backtest) 및 위임 shell 제거.
- **P1-b에서 추가된 인터림 사본도 이 단계에서 수렴**: `shared/indicators/series.py`의
  stateless 프리미티브(resolver/IndicatorBackend 밖에 있어 shadow-parity가 자동 커버하지
  않음) — #608의 6종(ema/sma/rolling_return_std/rvol_last/swing_low/window_extremes) +
  #610의 9종(rolling_std/rsi_sma[Cutler — daily_scanner 관례]/macd_lines[adjust=True
  레거시 포함]/trailing_max/trailing_change_pct/relative_strength_pct[diff-form ROC]/
  trailing_mean_ratio/normalized_slope/atr_series_padded[bar-0 padded]) — 과
  `backtest_backend.py`·compat 백엔드들의 중복 `_ema/_sma` 계열을 엔진 단일 구현으로 통합.
  trailing_max의 period<=0 경계(구 사이트별 상이 동작 → 현재 0.0 통일)도 이때 재검토.

**게이트**: shadow-parity 리포트(전 지표 safe 분류) + 백테스트 트레이드 동등성 + pytest green.
**산출 효과**: `reference.py`(689) + Compat 3개(~560) + 산재 사이트 수백 LOC 소멸,
지표 추가 = `_TABLE`/카탈로그 등록만.

## 4. Phase 2 — 선언형 전략 승격: builder_v1 → 1차 포맷 (지시서 §1·§4)

**목표**: "YAML만 작성하면 실행"을 builder_v1 승격으로 달성. 레거시 YAML은 계속 동작(호환 유지).

### P2-a. 스키마/어휘 확장 (선행 조건)
- [x] `signal_direction` 산출: 조건 그룹별 long/short 방향 — **선물 대칭 불변식 충족에 필수**
  (현재 builder entry는 Phase 1 long-only).
  — 완료: `BuilderState.entry_short` 그룹(선물 전용, 스키마 검증) + 브리지가
  `signal_direction`/`matched_group` 산출, exit 브리지 완전 sign-symmetric.
- [x] 연산자/피연산자 어휘 확장: percentile/rank(예: Setup D ATR-percentile 게이트),
  지표-대-지표 시계열 비교 확장, 시간 필터(no_entry_after 등 — KST).
  — 부분 완료: `percentile_rank_above/below`(+조건별 `window`) 출하(지표-대-지표
  비교는 기존 operand 모델로 이미 표현 가능); **잔여**: 시간 필터(no_entry_after,
  KST)는 P2-c 파일럿에서 필요 시 후속 PR.
- [x] exit 어휘: 선언형 stop/target/trailing에 더해 **명명된 exit 프리미티브 참조**
  (`exit: {primitive: three_stage, params: …}`) — 상태머신 exit를 스키마에서 조합 가능하게.
  — 완료: `BuilderState.exit_primitive` → factory가 `FirstTriggerExit`로 조합,
  ExitRegistry SoT 검증 + 카탈로그 asset-class 제한(three_stage=stock-only).
- [x] 게이트 훅: regime gate/LLM veto/쿨다운을 스키마 필드로 (쿨다운·재진입은
  개별 entry의 state dict에서 프레임워크 공통 게이트로 이동 — #601 재발 방지).
  — 완료(2/3): `gates.regime_gate`(기존 프레임워크 RegimeGate 재사용) +
  `gates.cooldown_seconds`(브리지 소비, deploy 파라미터와 max 병합); **LLM veto는
  보류** — 프레임워크 수준 attach 훅이 없어(Setup 어댑터 내부 전용) 신규 LLM
  배선 없이는 passthrough 필드가 무의미. 훅이 생기면 필드만 추가.

### P2-b. 파이프라인 통일
- [x] 레거시 경로의 `StreamingIndicatorResolver`(flat scalar)와 builder 경로의
  `IndicatorContext`(DataFrame)를 `IndicatorSpec`/`flat_key` 기준으로 정렬 —
  지시서의 "Indicator Context" 단일화.
  — 완료: 2026-07-09 드리프트 감사 결과 0(양 경로의 계산측은 이미
  `flat_latest()`→`flat_key` 경유). 잔여 수동 매핑이던 라이브 페이로드 조립
  (`services/trading/indicator_queries.py`)의 키 리터럴을 `flat_key` 유도
  상수로 교체(키/값 불변 — 페이로드 키셋 핀 + flat_key 카탈로그 골든 핀이
  tripwire). builder `alias.output` 컬럼은 사용자 별칭 스코프로 의도된 설계라
  유지; 의도된 분기(momentum 번들 HTS 키, feature 번들 정규화 atr)는 주석으로
  문서화. 추가로 `IndicatorContract.from_specs`(additive)로 typed 요청
  (IndicatorSpec+output→flat key)을 계약에서 선언 가능 — resolver 무변경 충족.
- [x] 캐시(`CachingIndicatorEngine`)로 중복 계산 제거.
  — 완료: builder 평가 경로는 전 시리즈가 필요해(cross/percentile 연산자)
  flat `PanelStore`로는 부족 → `cache.py`에 `CachingIndicatorEngine`
  (compute(spec, window)를 spec 동일성+window 내용 해시로 메모이즈, LRU) 추가,
  `cached_default_engine()` 프로세스 싱글턴을 builder_v1 entry/exit가 공유.
  같은 심볼/바에서 N개 전략이 공유하는 spec은 1회 계산(counting-backend
  compute-once 테스트), 값 불변은 Indicator Context 골든 값 핀으로 증명.
  Redis 교차프로세스 패널 공유는 P3+ 후속(in-process only, 신규 Redis 키 없음).
- [ ] 후보(P2-a 리뷰 follow-up): `StrategyFactory.create`의 builder_v1 특례 블록
  (스트리밍 가드/게이트 주입/exit 프리미티브 조합)을 별도 builder-브릿지 모듈로 추출.

### P2-c. 활성 전략 파일럿 마이그레이션 (신호 동등성 게이트)
- 순서: `williams_r`(순수 조건) → `pattern_pullback`/`momentum_breakout`(조건+쿨다운) →
  Setup A/C/D(조건 그래프 + context 필드; 어휘 밖 조건은 P2-a 확장으로 수용).
- 전략별 게이트: 구현 old vs new를 동일 기간 백테스트해 **신호 시퀀스 동일** 확인 후
  YAML 교체. 표현 불가 판정이 나면 레거시 컴포넌트로 존치하고 사유를 카탈로그에 기록
  (하이브리드 최종 상태 허용 — 단 신규 전략은 선언형 기본).

**파일럿 1차 결과 (2026-07-10, 활성 주식 3전략):**

- [x] **동등성 하네스 출하** — `tests/unit/strategy_builder/migration/harness.py`:
  레거시/선언형 양쪽을 동일 결정론 KST 바 시퀀스로 실 `BacktestStrategyAdapter`
  경로에 태워 진입 신호 시퀀스(타임스탬프/방향/가격, 비교 가능 시 confidence)를
  비교. 셀프체크가 PASS(명령형 SMA cross ≡ builder_v1 상태, 쿨다운 포함
  완전 동일)와 FAIL(규칙 다르면 divergence 보고) 양방향을 고정.
- [x] **선행 조건 수정** — resolver가 feature 번들 warm(≥26봉) 이후 `ohlcv`
  계약을 드롭해 builder_v1 전략이 라이브/백테스트 모두에서 영구 무신호였던
  버그 수정(`shared/indicators/resolver.py`). 이 수정 없이는 어떤 선언형
  마이그레이션도 어댑터 경로에서 검증 불가.
- [x] `williams_r` — **DEFERRED (표현 불가, 레거시 YAML 활성 유지)**.
  게이트 증거: `tests/unit/strategy_builder/migration/test_williams_r_migration_gate.py`
  (동일 시장 이벤트 2건에서 후보는 09:09 개장-스킵 창 안에서 발화, 레거시는
  5분봉 W%R로 13:45 발화 → 시퀀스 불일치). 부족 어휘:
  1. **진입 세션 시간 필터** (`skip_market_open/close_minutes`, KST) — P2-a 잔여
     항목과 동일.
  2. **지표 타임프레임** — 레거시는 `momentum_5m`(닫힌 5분봉) W%R,
     `BuilderIndicator`에는 timeframe 필드 없음(1분 OHLCV 윈도 고정).
  3. **market-state allow/block 리스트 게이트** — `gates.regime_gate`
     (percentile/impact)와 다른 메커니즘.
  4. **동적 사이징 메타데이터** (`position_size_multiplier` 과확장 축소).
- [x] `pattern_pullback` — **DEFERRED (후보 구성 자체가 불가)**. 부족 어휘:
  1. **중첩 조건 그룹(OR-of-AND)** — 패턴 리스트 10개 = OR, 패턴별 조건 = AND;
     `BuilderConditionGroup`은 평면 단일 logic.
  2. **일봉 타임프레임 지표 소싱** — sma_200/rsi_5/atr/highest_high가 daily 캔들
     기반(빌더 컨텍스트는 1분 윈도만).
  3. **피연산자 산술** — `atr/close` 비율, 60일 수익률, `sma_60 > sma_60_prev`
     (전일값 비교) 표현 불가.
  4. 패턴 순위 기반 `entry_priority`/confidence 사다리 메타데이터.
- [x] `momentum_breakout` — **DEFERRED (미션 예상대로 스키마 어휘 초과)**. 부족 어휘:
  1. **daily_watchlist/동적 스크리너 유니버스 게이트** (context metadata).
  2. **accumulation_score 게이트** (스크리너 메타데이터).
  3. **레짐 조건부 trend mode** — 모드 전환이 임계값·쿨다운·exit 오버라이드를
     동시에 바꿈(조건이 아니라 파라미터 세트 스위칭).
  4. 진입 세션 시간 필터(williams_r #1과 동일).
  5. ATR-엣지 피연산자 산술(`atr/close >= round_trip_cost × ratio`).
  6. intrabar reclaim OR-분기 + 모드별 이중 쿨다운.
- 종합: **마이그레이션 완료 0건 — 선언형 YAML은 출하하지 않음**(동등성 미증명
  버전 출하 금지 원칙). 다음 어휘 확장 우선순위(별도 PR, P2-a 후속):
  ① 세션 시간 필터 + ② 지표 타임프레임(이 둘이 williams_r을 언블록) →
  ③ 중첩 그룹/피연산자 산술(pattern_pullback) → ④ 메타데이터 게이트
  (momentum_breakout; watchlist·score는 스키마보다 프레임워크 게이트 후보).
  Setup A/C/D는 이번 파일럿 범위 밖(context 필드 의존).

### P2-d. Builder UI 정합
- 신규 스키마 필드(방향/exit 프리미티브/게이트)를 UI 카탈로그·`/capabilities`에 노출.
- `config/strategies/built/golden_cross.yaml`의 stale "cross 스트리밍 불가" 주석 정리.

**게이트**: 파일럿 전략 신호 동등성 + 기존 builder E2E(등록→paper) 회귀 + UI lint/build.

## 5. Phase 3 — vectorbt 백테스트 엔진 (지시서 §5, WS-A4 승격)

**목표**: 커스텀 이벤트 루프·성과지표 3중 중복을 vectorbt로 대체. 소비자 API는 계약 유지.

### P3-a. 주식 경로 (본체)
- [x] 신규 `VectorbtRunner`(`shared/backtest/vbt_runner.py`) — **1차 형태 완료**.
  시그널/체결 해석은 legacy 와 동일한 어댑터 순차 패스(신호 parity 구조 보장),
  포트폴리오 원장은 `vbt.Portfolio.from_orders`(2컬럼 cash-sharing 그룹).
  선언형 조건 → boolean 배열 사전계산으로의 전환(진짜 벡터화 가속)은 P1/P2
  결합 시 후속 — 그때 `from_signals` 경로 검토.
  비용 모델: 매도세 비대칭 때문에 vbt `fees` 비율 대신 주문별 절대 `fixed_fees`
  로 정확 매핑 (ats_simulator 경로는 미지원 → legacy 폴백).
- [x] `BacktestResult`/`BacktestTrade` 어댑터 유지 — `trades.records`/cash/assets
  에서 채움. 소비자 무수정 (experiment_runner 는 opt-in seam 만 추가,
  `strategy.backtest.engine: vectorbt`, 기본값 legacy).
- [x] 심볼별 독립 백테스트 전제 유지 (러너는 단일 심볼 프레임 전용; 멀티심볼은
  명시 거부 → legacy 폴백). 리포트 스키마 무변경.
- [x] `LookaheadGuard` 의미 보존 — 어댑터 순차 구동으로 결정 시점 t 에 bar ≤ t
  만 관측 (vbt_runner docstring §2 + parity 스위트).
- [x] 상태머신 exit 감지 → `NotImplementedError('legacy engine required')`
  (허용목록 `EXPRESSIBLE_EXIT_GENERATORS`, v1 = williams_r_exit).

### P3-b. Parity 게이트 (WS-A4 게이트 그대로)
- [x] Parity 스위트 (`tests/unit/backtest/test_vbt_runner.py` + `_realdata.py`):
  합성 5시나리오 × 7리스크 매트릭스 + 실데이터 williams_r(005930 분봉,
  2026-06-01~12, 11 trades) — 트레이드 시퀀스/총수익/샤프/MDD **완전 일치**.
  허용오차 정책·스윕 속도 측정: `docs/plans/2026-07-10-vbt-parity-report.md`
  (속도는 현 단계 개선 없음 — 어댑터 시그널 패스가 지배; 정직 기록).
  활성 3전략 전체 커버리지(momentum_breakout/pattern_pullback)는 exit
  허용목록 확장 후 후속.
  ⚠️ CI 한계: 머지 게이트 `test` 잡은 vectorbt 미설치라 vectorbt-의존
  parity 케이스를 skip 한다(마스킹/게이트/seam 계층만 강제). parity 스위트
  전체는 advisory `backtest-extra` 레인(continue-on-error)과 배포 호스트에서
  돈다 — **운영자 flip 전 `scripts/vbt_parity_report.py` 재실행이 필수 게이트**
  (exit code 가 실데이터 포함 전 셀 판정).
- [ ] 통과 후 `engine.py` 이벤트 루프·수제 성과지표(§3.2의 3벌)를 제거하고
  experiment_runner/optimizer 백엔드 교체 — **미착수** (운영자 flip 게이트;
  paper 관찰 + 허용목록 확장 선행). 미통과 항목은 원인 규명 전 교체 금지.

### P3-c. 상태머신 exit 처리
- three_stage 등 신호 사전계산으로 표현 불가한 exit는 1차로 기존 이벤트 루프 경로를
  `legacy_exit=true` 플래그로 존치, 2차로 vbt custom order func 이관 검토.
  **parity 불가 전략을 억지로 vbt에 밀어넣지 않는다.**

### P3-d. 선물 트랙 (후행)
- `decision_harness`의 틱-PnL·컨텍스트 replay·다음바 시가 체결은 특수성이 커서
  주식 경로 안정화 후 `vbt.Portfolio.from_orders` 매핑을 별도 검토.
- walk-forward 스크립트(`scripts/walk_forward_*.py`)는 harness 소비자이므로 그다음.
- 이관 전까지 선물 백테스트는 현행 harness 유지 (2중 체제 명시).

**게이트**: P3-b parity + 소비자 계약 테스트(experiment 리포트 스키마 golden test) + CI green.

## 6. Phase 4 — Risk Engine 통합 (지시서 §8)

**목표**: "두 세계" 통일 + 산재 stop/trailing 프리미티브화 + 누락 기능 신설.

- [ ] **프리미티브 라이브러리** (`shared/risk/primitives/`): 단일 ATR 소스(P1 엔진),
  side-aware PnL 유틸(×9 복붙 `_calc_profit_pct` 대체), stop(abs/ATR/pct)·trailing(HWM 플러그형)
  프리미티브 — exit 생성기 14곳/8곳이 이를 소비하도록 치환.
- [ ] **오케스트레이터 단일화**: `RiskFilterLayer`(디커플)를 유일한 평가기로,
  모놀리식 `RiskManager`는 그 어댑터로 축소. `RiskState` 2벌(models.py vs state.py) 단일화,
  config 스키마 pydantic으로 통일 (`max_consecutive_losses` 등 유사 키 정리).
- [ ] `services/kill_switch`의 자체 재구현(KillCondition)을 공유 필터 소비로 전환 —
  **kill-switch 동작 의미(파국-only 임계값 #600)는 절대 변경하지 않는다.**
- [ ] **신설**: 레버리지 제한(현재 repo 전체 부재) + 증거금 게이트
  (`shared/risk/futures_margin.py`를 진입 게이트에 배선 — shadow 모드 기본, 운영자 flip).
- [ ] 동시 진입 제한을 World B에 총량/자산별로 보강 (현재 심볼당 1개만).

**게이트**: 기존 risk 테스트 43파일 green + 프리미티브 단위 테스트 +
평균회귀 구조 충돌 회귀 테스트(#600의 streak-breaker 교훈 보존) + paper 관찰.

## 7. Phase 5 — Futures Context + Hedge Engine 가동 (지시서 §6·§7)

**목표**: 코드 신규가 아니라 **배선과 스케줄링**. 대부분 이미 구현돼 있음.

- [ ] dormant 서비스 3개(`futures_context`/`futures_contract`/`futures_margin_risk`)를
  `deploy/scheduler.crontab`(KST) 등록 + 스케줄러 이미지 리빌드 — **운영자 게이트**.
- [ ] 외인선물 수집 stub(`shared/llm/futures_flow_collector.py:38`) 해소 —
  market_structure_collector가 이미 수집하는 `fut_foreign_net_qty`를 정식 소스로 배선.
- [ ] `FuturesMarketContextV2`(basis/OI/외인/롤/증거금/틱가치 regime 분류)를
  Setup 컨텍스트·대시보드에 노출 (관측 전용 유지, 게이팅은 별도 결정).
- [ ] Hedge v2 부분헤지: 위 배선으로 의존성(`futures:contract:latest`, `futures:risk:latest`)
  충족 → advisory 완성. **주문 연결은 이 계획 범위 밖(운영자 결정).**
- [ ] `shared/arbitrage` 프로토타입은 P0에서 제거됐으므로 basis 로직은
  futures_context 경로로 일원화.

**게이트**: read-model 검증 스크립트 + Redis 스냅샷 신선도 + advisory-only 불변식
(주문 경로 import-graph 가드) 유지 확인.

## 8. Phase 6 — 실행 계층 마감 (지시서 §9, 장기)

- [ ] **KIS 데이터 파사드**: `KISClient` 직접 import 10곳을 어댑터 인터페이스 뒤로 —
  지시서 "의존성은 Adapter 계층 통해서만"의 데이터측 마감.
- [ ] **MarketContext 필드 parity 계약**: 라이브 producer와 backtest replay가 채우는 필드를
  스키마로 고정하고 계약 테스트로 강제 — `last_15min_high/low` 함정(#533/#537) 구조적 재발 방지.
- [ ] 체결 모델 문서화·정렬: 백테스트(다음바 시가±0.3틱) vs 라이브(passive limit) 괴리를
  vbt 슬리피지 파라미터로 보정하는 캘리브레이션 리포트(paper 체결 데이터 기반).
- [ ] 디커플 주식 파이프라인에 라이브 KIS 주문 경로 배선 (현재 VirtualBroker만) —
  주식 라이브 전환의 전제, 운영자 게이트.
- [ ] 모놀리식 오케스트레이터(17K LOC) 은퇴: F-9 선물 컷오버 러너북과 연동 — 본 계획의
  산출물이 아니라 후속 운영 결정.

## 9. 순서/의존성과 리스크

```
P0 ──▶ P1 ──▶ P2 ──▶ P3(주식) ──▶ P3-d(선물)
        │       ╲
        │        ╲ (P2-a 스키마 확장은 P3와 부분 병렬 가능)
        ├──────▶ P4 (P1의 ATR 프리미티브에만 의존, 나머지 독립)
        └──────▶ P5 (독립 — 언제든 착수 가능, 운영자 게이트)
P6: P3·P4 안정화 후 장기
```

| 리스크 | 완화 |
|---|---|
| TA-Lib 값 ≠ 수제 관례 값 (ATR 24% gap 전례) | shadow-parity + 계약 테스트 + convention gate 유지, gated 지표는 수렴 전 flip 금지 |
| vectorbt 체결 의미론 차이로 성과 왜곡 | P3-b parity 게이트 미통과 시 교체 중단; 상태머신 exit는 legacy 경로 존치 |
| 선언형 마이그레이션 중 신호 변화 | 전략별 신호 시퀀스 동등성 게이트; 하이브리드 최종 상태 허용 |
| paper 운영 중단 | 배포는 `scripts/deploy_paper.sh`만; 런타임 flip(convention/risk 게이트)은 운영자 게이트 |
| vectorbt 의존성 무게(numba/plotly) | `backtest` extra 격리 유지 — 런타임 이미지에 미포함 |
| 대형 삭제의 숨은 소비자 | P0 각 삭제 전 cron/CLI/compose 참조 스윕, 테스트 삭제 동반 |

## 10. 완료 정의 (지시서 "최종 목표" 대응)

- [ ] repo에 EMA/RSI/MACD/ATR/BB 수제 계산 0 (문서화된 예외: stateful VWAP·orderbook·일반통계)
- [ ] 새 지표 추가 = TA-Lib `_TABLE` + 카탈로그 YAML 등록만
- [ ] 새 전략 추가 = YAML(BuilderState) 작성만으로 백테스트+paper 실행
- [ ] 백테스트 성과지표는 vectorbt 단일 소스 (수제 Sharpe/MDD/trade-log 0)
- [ ] Risk Engine 단일 오케스트레이터 + 프리미티브 (RiskState/설정 1벌)
- [ ] Hedge/Futures Context read-model 가동 (advisory)
- [ ] 라이브·백테스트가 동일 전략 정의를 공유함을 계약 테스트가 강제
