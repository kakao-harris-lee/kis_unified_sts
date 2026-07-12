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
  `shared/ensemble`(435),
  `shared/position`(~694, test-only 고아 — PositionTracker로 대체됨),
  CLAUDE.md의 vestigial `domains/` 참조 정리(디렉토리 자체는 `336df723`에서 이미 제거됨).
  각 삭제 전 cron/CLI 참조 재확인.
  ⚠️ `market_structure_collector`/`market_risk_engine`은 통합투자시스템 P0/P1 소속 — 삭제 금지.
  ⚠️ `shared/arbitrage`(332)도 **삭제 금지** — `market_structure_collector`가
  `BasisCalculator`를 소비 중(이전의 "소비자 미배선" 판정은 사실 오류, §7 참조).
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
- [x] **`legacy_exit: true` 명시 플래그** (experiment_runner seam) —
  `strategy.backtest.legacy_exit: true` 면 `engine: vectorbt` 여도 러너를 아예
  시도하지 않고 legacy 를 강제한다 (상태머신 exit 전략의 operator escape hatch /
  명시 마커). `shared.utils.coercion.to_bool` tri-state 강제(bool / "true"/"1"/
  "yes" …); 해석 불가 값은 조용히 True 로 오인하지 않고 **경고 후 무시**
  (unknown-engine 키 처리와 동일 정책; 빈 키 `legacy_exit:`=None 은 미설정으로
  경고 없이 무시). 강제 시 info 로그 1줄로 사유를 남긴다.
  ⚠️ **잠재 리스크(이연)**: 이 게이트는 현재 experiment seam 에만 산다 —
  향후 다른 vbt 소비자(optimizer/CLI 백테스트/P3-d)가 생기면 반드시
  `backtest.legacy_exit` 를 동일하게 존중해야 한다(또는 그 시점에 게이트를
  `_ensure_supported` 로 이동).
- [x] **허용목록 확장 (parity 증거 수반)** — `EXPRESSIBLE_EXIT_GENERATORS` 에
  `atr_dynamic`, `chandelier_exit` 등재. 실제 exit 클래스(ATRDynamicExit /
  ChandelierExit) 인스턴스를 legacy `BacktestEngine` vs `VectorbtRunner` 이중
  구동으로 합성 시나리오(trend_up / trend_down / chop) × 리스크(default /
  tight_sl_tp) 매트릭스에서 검증 — 트레이드 시퀀스 **가격 포함 완전 일치**
  (러너가 트레이드 가격을 resolver 이벤트의 bar 종가 원본에서 채우도록 교정;
  vbt 레코드 value/size 재구성 ULP 잔차는 계약에 새지 않고 `_cross_check` 가
  레코드↔이벤트 일치를 별도 강제). exit 생성기가 실제로 청산을 구동함을
  non-vacuity 가드(`trailing_stop`/`momentum_decay` 사유 존재)로 고정.
  배포 momentum_breakout 의 exit 설정(momentum_decay_exit=true, max_hold_days)
  그대로의 `atr_dynamic_decay` 변형까지 매트릭스에 포함(decay 분기 발화 검증).
  `tests/unit/backtest/test_vbt_runner.py::TestRealExitParity` (합성 18 케이스 +
  non-vacuity 3; 매트릭스는 P3-b `_SCENARIOS`/`_RISK_VARIANTS` 에서 파생).
  `scripts/vbt_parity_report.py` 도 동일 픽스처를 import 해 실 exit 매트릭스를
  리포트/exit-code 판정에 포함(운영자 flip 게이트 커버). → **활성 3전략
  (williams_r / momentum_breakout / pattern_pullback) exit 전부 허용목록 통과**:
  williams_r_exit(P3-b) + atr_dynamic + chandelier_exit. 러너는 어댑터를 legacy
  순서로 재생성하므로 상태머신 exit 도 기계적으로 지원 — 허용목록은 **표현가능성
  제한이 아니라 parity 증거 게이트**임을 docstring/주석에 명시.
  ⚠️ **일봉 어댑터 경로는 별도 게이트**: `DailyBacktestAdapter` 는 parity
  미검증이라 `_ensure_supported` 가 정적으로 거부한다(legacy 폴백) — daily
  전략(pattern_pullback)은 exit 가 허용목록에 있어도 legacy 로 돈다.
  chandelier_exit 의 vbt 적격성은 분봉 어댑터 경로 한정.
- [x] **cross-check 폴백 배선** — 러너 내부 resolver↔vbt 원장 cross-check
  불일치는 전용 `VectorbtParityError`(RuntimeError) 로 승격, experiment seam 이
  이를 잡아 legacy 폴백한다(fresh adapter 재생성). 과거엔 per-symbol except 로
  떨어져 심볼이 등가중 집계에서 조용히 탈락했다 — 이제 결과 보존 + 조사용 경고.
- [x] **three_stage 영구 제외** — 스테이지별 *부분* 청산이라 `from_orders`
  풀포지션 원장으로 구조적 표현 불가 → 허용목록 미등재 유지(2차 vbt custom order
  func 트랙에서 재검토; 이번 범위 밖). seam 폴백 계약을 three_stage
  (`opening_volume_surge`)로 재고정(`test_unsupported_exit_falls_back_to_legacy`;
  chandelier/atr 이 허용되면서 기존 pattern_pullback 예시가 무효화됨), 게이트 거부
  는 실 클래스 name 으로 핀(`test_stateful_exit_generator_denied`).
  **parity 불가 전략을 억지로 vbt 에 밀어넣지 않는다** 원칙 준수 — 이번 확장은
  atr_dynamic / chandelier 둘 다 parity 통과라 강제 배제 사례 없음(불통과 시
  허용목록 제외 + 원인 기록 규약).

### P3-d. 선물 트랙 (from_orders 컴포지션 래퍼)
- [x] **`from_orders` 매핑 완료** — `decision_harness`의 틱-PnL·컨텍스트 replay·
  다음바 시가 체결을 `vbt.Portfolio.from_orders` 원장으로 매핑하는 검토가
  끝나 `shared/backtest/vbt_harness_runner.py::VbtHarnessRunner` 로 구현됐다.
- [x] **컴포지션 래퍼 (resolve-pass 복제 아님)** — 주식
  `VectorbtRunner`(전 원장을 vbt `Portfolio` 로 재도출)와 달리, 이 클래스는 fill/
  exit 세맨틱을 재구현하지 않는다. `BacktestDecisionHarness` 가 **유일 SoT**로
  남고 `run` 은 실제 harness 를 그대로 실행해 `HarnessResult` 를 **무변형 반환**
  한다. vbt 층은 harness 자체 트레이드 레코드로 *독립* `from_orders` 원장을 세워
  harness 의 tick 회계를 재현하는지만 대조한다(리던던트 계산 parity).
- [x] **cross-check 스펙** — 멀티바 트레이드(`exit_bar_index > fill_bar_index`)는
  각 `vbt.Portfolio.from_orders` 컬럼 1개로 인코딩(진입 `dir×size` / 청산
  `-dir×size`), entry/exit idx·price·direction·size·pnl 을 행별 대조한다
  (`pnl = ticks_net × tick_size × size_contracts`). 슬리피지는 `fill_price` 에
  내재하므로 vbt `slippage=0`(이중계상 금지), 비용은 `fees=0`.
- [x] **same-bar carve-out** — fill==exit bar 트레이드(세션 경계 EOD-on-fill /
  last-bar fallback)는 `from_orders`(컬럼/bar 당 1주문)로 표현 불가라 컬럼에서
  제외하고 **해석적으로** 검증한다: (1) `exit_price == close[fill_bar_index]`
  확인(harness 가 이들 청산을 체결 bar 종가로 마킹) + (2) tick P&L 을 fill/exit
  가격에서 **독립 재계산**(`ticks_net == (exit-fill)/tick` long / `(fill-exit)/tick`
  short)해 대조한다. 헤드라인 tick 합 불변식(`from_orders pnl 합 + samebar tick 합
  == 전체 tick 합`)은 같은-bar 항이 양변에서 상쇄돼 **대수적으로 공허**하므로,
  같은-bar tick 회계를 실제로 검증하는 것은 이 독립 재계산이다.
- [x] **`legacy_exit` N/A 근거** — P3-c 의 `backtest.legacy_exit` escape hatch 는
  여기 해당 없음. harness 는 strategy-config exit 생성기가 없다 — 모든 Signal 이
  자체 `stop_loss`/`take_profit`/`valid_until` 를 들고 fill 시뮬레이터가 직접
  해소한다. "opt-in" = `BacktestDecisionHarness` 대신 이 클래스를 고르는 것,
  escape hatch = harness 를 직접 쓰는 것 — 존중할 per-strategy 플래그가 없다.
- [x] **테스트/리포트 배선** — `tests/unit/backtest/test_vbt_harness_runner.py`
  (import 격리 / 정적 게이트 / `_build_order_arrays` 인코딩 / harness bar-index
  채움 = vectorbt 불필요, + 대칭 매트릭스 parity·사이저 스케일·음성 tamper =
  `importorskip`). `scripts/vbt_parity_report.py` 가 동일 픽스처를 import 해
  선물 매트릭스를 리포트/exit-code 판정에 포함(주식 **및** 선물 동시 PASS 요구).
- [x] **walk-forward/optimizer 스크립트 `--engine` opt-in 배선 완료** (P3-d 후속) —
  공유 chokepoint `shared/backtest/harness_engine.py::run_futures_backtest`
  (`(setups, filter_layer, state, tick_size_points, replay, *, engine, sizer,
  account_equity_krw) -> (HarnessResult, 사용엔진라벨)`) 를 신설하고, 5개 스크립트
  (`walk_forward_phase3` / `walk_forward_bootstrap` / `walk_forward_sensitivity` /
  `walk_forward_paper_foldin` / `optimize_decision_engine`) 전부에
  `--engine {harness,vectorbt}` (기본 `harness`) 를 추가했다. 위임 체인
  (bootstrap→phase3 `_run_on_window`, sensitivity→phase3, paper_foldin→bootstrap
  Namespace 재구성)에 engine 인자를 전파. **엔진 시맨틱**: `harness`=현행 그대로,
  `vectorbt`=`VbtHarnessRunner`(미설치 `VbtHarnessNotSupportedError` 는 폴백 없이
  전파 — 명시 opt-in 수동 스크립트라 조용한 폴백보다 명시 실패가 안전),
  `VbtHarnessParityError` 는 warning 로그 후 순수 harness 재실행으로 SoT 결과 복원
  (라벨 `vectorbt_parity_failed`, vbt_parity_report.py 패턴 — 결과 정확성 불변,
  파리티 실패는 조사 신호). 출력 JSON 에 사용 엔진 라벨 + 파리티 실패 창 개수 기록.
  테스트 `tests/unit/backtest/test_harness_engine.py` (라우팅 fake 4계약 + 실
  harness/vectorbt 경로 + 5스크립트 `--help` 스모크). **메모리 실측**: dense
  from_orders 행렬 피크 RSS — 41k분봉×500트레이드=1.2GB, ×1000=2.1GB (호스트 가용
  대비 안전, 폴드 단위 창은 훨씬 작음). 기본값이 `harness` 이므로 2중 체제
  (harness=SoT, vectorbt=opt-in 대조)는 그대로 유지된다.
- 📝 **정직한 가치 노트**: 이 래퍼는 harness 의 per-trade tick P&L·진입/청산 bar·
  가격·방향·size 를 **구조적으로 다른 두 번째 계산**으로 재확인하는 opt-in 독립
  검증 도구다. harness 를 대체하지 않으며(equity curve/Sharpe/MDD 이관 대상
  자체가 없음 — 소비자는 tick 합과 per-setup 통계만 읽음), harness 가 여전히
  기본값이자 SoT 다. 아무것도 기본적으로 이 클래스로 라우팅되지 않는다.

**게이트**: harness↔from_orders parity(대칭 매트릭스, 멀티바/같은-bar 커버리지 +
non-vacuity) + `_build_order_arrays`/bar-index 단위 테스트 + CI green (parity 층은
vectorbt 필요 → 머지 게이트는 정적 층만, 전 매트릭스는 배포 호스트 스크립트).

## 6. Phase 4 — Risk Engine 통합 (지시서 §8)

**목표**: "두 세계" 통일 + 산재 stop/trailing 프리미티브화 + 누락 기능 신설.

- [x] **프리미티브 라이브러리** (`shared/risk/primitives/`): 단일 ATR 소스(P1 엔진),
  side-aware PnL 유틸(×9 복붙 `_calc_profit_pct` 대체), stop(abs/ATR/pct)·trailing(HWM 플러그형)
  프리미티브 — **P4-a 라이브러리 신설 완료(소비자 0, exit 생성기 치환은 P4-b 후속)**.
  랜딩 노트(P4-a): `pnl`/`extremes`/`stops`/`atr_read` 4모듈 + 9개 exit 클래스
  read-only differential 격자 테스트로 동등성 고정.
  (1) `entry_price <= 0 → 0.0` 가드 통일 — 근거는 `Position.profit_rate` 모델 관례
  (가드 있는 3곳 atr_dynamic/technical_consensus/trix_golden과 동일; 무가드 6곳은
  ZeroDivisionError → 의도된 통일로 테스트에 명시 고정).
  (2) 트레일링은 stateless — HWM/극값은 인자로 받고 소스는
  `Position.highest_price`/`lowest_price`(`_get_extreme_since_entry` 5곳 복붙 동등);
  자체 dict 극값 2곳(builder_strategy_exit/trix_golden_exit)은 대상 아님(docstring 명기).
  (3) ATR은 계산 재구현 없이 정규화 인자화만(`normalize_atr`, 임계값 사이트별 인자:
  atr_dynamic·mean_reversion=0.5, track_a=None) — 계산 SoT는 P1 엔진 유지.
- [x] **exit 생성기 프리미티브 델리게이터 치환 (P4-b)**: 9개 exit 생성기의 복붙 유틸
  본문을 프리미티브 호출 1줄로 축소(메서드 이름·시그니처 보존 → 기존 exit 테스트가 이 사이트를
  직접 호출하므로 콜사이트 유지). 치환한 사이트: **profit_pct 9/9, profit_amount 9/9,
  extreme_since_entry 5/5**(atr_dynamic·mean_reversion·momentum_decay·three_stage·williams_r);
  **stop/trailing**: `abs_stop_hit` 4(three_stage·momentum_decay `_stop_hit`, setup_target
  `_price_crossed(stop)`, track_a `catastrophic_stop_hit`), `atr_stop_level` 3(atr_dynamic
  트레일 레벨, track_a `trail_stop_price`, catastrophic 레벨), `pct_trailing_stop_level`
  2(three_stage·momentum_decay 트레일 레벨; `position.stop_price` 클램프는 call-site 유지).
  **제외**: technical_consensus `_get_high_since_entry`(SHORT 분기에 `inf→entry` 폴백 없는
  변종 → `lowest_price==inf & price>entry`에서 프리미티브와 상이, P4-a differential이 "5곳
  계약 대상 외"로 판정) → 델리게이트하지 않음. **behavior-0 근거**: 모든 치환은 realistic
  path(entry>0, inclusive stop) 동등 — P4-a differential 격자 + 기존 exit 테스트 **무수정**
  3357 green. `entry<=0 → 0.0` 가드 통일은 P4-a에서 이미 의도·문서화된 unification이며
  production 도달 불가(진입가 항상 >0); 유일한 테스트 갱신은 P4-a가 P4-b 전환 마커로 심어둔
  `test_zero_entry_unguarded_legacy_raises`→`..._now_guarded` 1건.
- [x] **exit ATR 정규화 프리미티브 소비 (P4-c, 항목(a) 3단계)**: 인라인
  `if atr < THRESHOLD: atr *= ref` 정규화를 `normalize_atr`(P4-a)로 치환. P4-c는
  원래 디스코프 후보였으나 실익이 확실한 2사이트만 최소 진행 — no-op/부재 사이트는
  프리미티브가 main에 있어 향후 개별 흡수 가능. **치환 2사이트**: (1) atr_dynamic
  `_get_atr` = 단일 소스+임계 0.5+ref current_price → 정규화 블록을 `normalize_atr`
  호출 1개로 **완전 표현**; (2) mean_reversion_exit `_get_atr` = 2중 소스 폴백
  (indicators→market_data atr, market_data→indicators close)은 콜사이트에 잔존,
  **정규화 산술만** `normalize_atr(atr, close, normalized_below=0.5)`로 이동.
  **제외 2사이트(근거)**: track_a_exit `_get_atr`=정규화 없음(`normalized_below=None`
  no-op)+다중키 폴백 체인이 본질 → DRY 이득 0, import만 순손실; chandelier_exit=정규화
  로직 자체 부재(`_get_atr` 메서드 없음). **doc-drift 해소**: mean_reversion docstring
  "< 1.0"이 코드 실제값 0.5와 불일치했던 drift를 "< 0.5"로 정정(정규화 임계값이 이제
  primitive 인자 `normalized_below=0.5`로 자기문서화). **behavior-0 근거**: 두 사이트
  모두 `normalized_below=0.5` 정확히 지정(track_a/chandelier에 0.5 주입 시 behavior 변경
  → 미변경). P4-a가 선재한 특성화/differential 격자 테스트(`test_atr_read.py`
  `TestDifferentialAtrDynamic`/`TestDifferentialMeanReversion`)가 두 `_get_atr`를 직접
  호출해 무수정 green — 치환 전/후 동일 입력→동일 출력 고정. 기존 exit 테스트 869 green
  (`tests/unit/strategy/`, 무수정).
- [ ] **오케스트레이터 단일화**: `RiskFilterLayer`(디커플)를 유일한 평가기로,
  모놀리식 `RiskManager`는 그 어댑터로 축소. `RiskState` 2벌(models.py vs state.py) 단일화,
  config 스키마 pydantic으로 통일 (`max_consecutive_losses` 등 유사 키 정리).
  - [x] **(P4-h1) `state.RiskState` → `RiskStateStore` 개명 (이름충돌 해소, behavior-0)**:
    `shared/risk/state.py`의 `RiskState`는 실체가 **Redis HASH writer/store**(데이터는
    `RiskStateSnapshot`)인데 `models.py:222`에도 동명 `RiskState`(orchestrator 전용
    포트폴리오 dataclass)가 존재 → 순수 rename으로 "state가 아니라 store"임을 교정하고
    충돌 해소. **`models.py::RiskState`는 무변경** — `shared/risk/__init__.py`가 이것만
    export, P6에서 orchestrator와 함께 소멸 예정. state.RiskState는 `__init__` 미export라
    외부 API 아님 → 하위호환 alias 불요. **소비자 4곳 갱신**: `state.py`(정의+docstring),
    `runtime_state.py`(import+생성자 `self._risk_state`+docstring), `tests/unit/risk/
    test_risk_state.py`, `tests/unit/risk/test_runtime_state_period.py`(migration 시드
    `legacy = RiskStateStore(...)`). **behavior-0**: 기존 risk 스위트 로직/단언 무변경 green
    (1360 passed / 13 skipped), ruff·black clean, mypy 델타 0(state.py:77 · runtime_state.py:258
    선재 에러 동일). 서비스/스크립트 소비자 없음(예상 밖 광범위 소비자 부재).
  - [x] **(P4-h2, 항목(b) / 설계 2.9) World-A `RiskManager` 중복계산 breaker 위임 (behavior-0)**:
    모놀리식 `RiskManager.can_open_position`이 다른 곳과 **중복인 산술만** P4-d 프리미티브
    (`shared/risk/primitives/breakers.py`)에 위임. **제어흐름·게이트·액션·순서 무변경** — 이건
    계산 DRY화이지 P6의 `RiskFilterLayer` 재배선이 아니다. **`RiskManager`/`models.RiskState`
    무삭제**(P6에서 orchestrator와 함께 소멸).
    - **위임한 계산(1건)**: consecutive-loss `>=` 비교 → `consecutive_exceeds(consecutive_losses,
      max_consecutive_losses)`(inclusive=True 기본, 정수 경계 정확 → behavior-0). breaker 술어의
      **4번째 인라인 copy** 해소(kill `ConsecutiveLossesCondition` + filter hard/soft가 나머지 3).
      **`max_consecutive_losses > 0` 활성화 게이트와 `block_trading(CONSECUTIVE_LOSSES)` 액션은
      manager에 잔존**(활성화 조건·액션은 술어 아님). **census 정직성**: consecutive `>=` 술어의
      **5번째 인라인 copy가 `shared/strategy/position/sizers.py:356`**(선물 포지션 사이저의
      soft-reduce tier, `consecutive_losses >= soft_reduce_threshold`)에 **잔존** — P4-h2 범위 밖
      (position-sizer 경로는 별도)이라 이번엔 미해소, **후속/P6 정리 대상**으로 남긴다.
    - **위임 안 함 = 보존(#600 불변 + behavior-0 우선)**:
      · **daily-loss(fraction) 검사** — manager는 *percent-space*(`daily_pnl_pct=(pnl/capital)*100`
        을 percent limit `-daily_loss_limit_pct`와 비교)인데 `loss_fraction_exceeds`는 *fraction-space*
        (`pnl/equity` vs fraction limit). limit `/100` 라우팅은 IEEE-754 라운딩 경로를 바꾸고,
        production 브랜치는 **선(先)파생 저장 `state.daily_pnl_pct`**를 소비(Redis 역직렬화가
        `daily_pnl`과 독립 복원 가능 — 골든마스터 케이스 `E4`)라 프리미티브가 재파생 없이는 표현
        불가 → 억지 위임 금지, **inline 보존**(코드에 근거 주석). *daily-loss 판정 결과: 검사는
        fraction-of-equity지만 percent-space + stored-pct라 breaker 미대응.*
      · **daily_loss_limit_points**(선물 points-native `daily_realized_pnl <= -points`) — breaker 대응
        없음. · 총/자산별 포지션 제한(`>=`), DrawdownLevel.CRITICAL enum 판정, force-flatten/
        block_trading 액션, `record_realized_pnl` streak 상태변경 — 전부 보존.
    - **골든마스터 behavior-0 증명**: `tests/shared/risk/test_manager_golden_master.py` 신설(위임
      *전에* 작성·green) — `can_open_position`의 **결정면**(반환 bool + 래치된 `is_blocked`/
      `block_reason`)을 38 파라미트라이즈 케이스로 고정(각 게이트 경계 ±1 + 게이트 순서 precedence,
      기대값 전부 손계산). 위임 후 **무수정 green**(#600 파국 consecutive 차단 + 소프트 비차단 포함).
    - **테스트**: 기존 risk 스위트 **무수정** green — `tests/shared/risk/` + `tests/unit/risk/` +
      `test_kill_switch_main.py` 1426 passed / 13 skipped(Redis 부재 persistence). ruff·black clean,
      mypy 델타 0(선재 no-untyped-def만). 제어흐름 병합·RiskManager 삭제는 **P6**.
- [ ] `services/kill_switch`의 자체 재구현(KillCondition)을 공유 필터 소비로 전환 —
  **kill-switch 동작 의미(파국-only 임계값 #600)는 절대 변경하지 않는다.**
  - [x] **(c) breaker 술어 공유 (P4-d)**: kill_switch 조건과 MDD/consecutive 필터가
    3중 중복 구현하던 loss-fraction / consecutive-count **불리언 술어 수학**을
    `shared/risk/primitives/breakers.py`(신설, 순수·무상태)로 통합. **결정이 아니라
    술어만 공유** — kill 조건이 필터를 호출하거나 그 반대는 없다.
    - **공유한 것**: `loss_fraction_exceeds(pnl, equity, limit, *, inclusive,
      equity_nonpositive)` (경계 연산자·equity<=0 처리를 인자화) + `consecutive_exceeds(
      count, threshold, *, inclusive=True)` (raw `>=` 비교만).
    - **공유 안 한 것**: kill의 force-flatten/sentinel latch 액션, 필터의 소프트
      size_multiplier=0.5 / KST 영속 감축 윈도우(`size_reduce_until_kst`) /
      `reduce_blocks_at_floor` floor 정책 — 전부 소비자 고유 로직으로 잔존.
    - **behavior-0 근거**: kill은 `inclusive=True`(경계 `>=`, "at-or-beyond")+
      `equity_nonpositive="safe"`(equity<=0→False 가드 보존), 필터는
      `inclusive=False`(strict `<`, 경계 통과)+`equity_nonpositive="raise"`(무가드
      나눗셈 보존 — equity==0 ZeroDivisionError, equity<0 계산). `-pnl/eq >= limit`
      ⟺ `pnl/eq < -limit`은 경계 제외 동일 크기, IEEE-754 부호반전 정확 → 각 브랜치가
      기존 표현과 비트동일. 배선 사이트 7개(kill daily/weekly/**monthly**/consecutive
      4 + filter daily_mdd/weekly_mdd/consecutive hard·soft 3). monthly는 동일 술어
      수학이라 함께 dedup(임계 15%·래치·액션 무변경).
    - **테스트**: 기존 risk/kill_switch 스위트 **무수정** 1280 green(behavior-0 증명) +
      `tests/unit/risk/primitives/test_breakers.py`(술어 단위: inclusive 경계·equity<=0
      safe/raise·부호·consecutive 경계) + `tests/unit/risk/test_p600_breaker_separation.py`
      (#600 회귀 pin: soft4<hard6<catastrophic10 3-tier 분리 + inclusive/strict 경계
      분리를 실소비자로 고정 — 미래 리팩터가 소프트를 파국에 병합하면 fail).
- [x] **(g) 레버리지 제한 필터 신설 (P4-g)**: repo **최초 레버리지 제한**(이전엔 World-A
  YAML 주석 1건만, 코드 0건)을 생존 세계 World-B(`RiskFilterLayer`)에 진입 게이트로 신설.
  - **신설**: `shared/risk/filters/leverage.py::LeverageFilter`
    (`mode`=shadow|enforce + `max_gross_leverage` + `snapshot_provider` +
    `product_specs` + 선택 `stale_max_age_seconds`).
  - **정의**: `gross_leverage = Σ|quantity·price·multiplier| / equity`. gross(**abs**)라
    long/short 대칭 자동 보존(필터는 side를 절대 읽지 않음 → 선물 대칭 non-negotiable 무료 충족).
    거절 = `gross_leverage > max_gross_leverage` **AND** enforce (`skip_reason=max_gross_leverage`).
  - **multiplier DRY**: 계약 승수는 `shared/risk/futures_margin.py::spec_for_symbol`(증거금
    읽기모델과 동일 `MarginProductSpec` 맵)로 해석 — 하드코딩 상수 0. 미해석 심볼/`product_specs`
    None(주식 현금 = 승수 1)이면 1.0 폴백(선물 승수 미해석은 레버리지 **과소**계상 → 결코
    과잉거절 불가 = fail-open-safe).
  - **양자산 적용**(증거금 게이트의 futures-only와 대비): 주식 체인은 현금계좌 캡 1.0(승수 1),
    선물 체인은 캡 예 3.0 + product_specs 승수. `from_config`는 asset 게이트 없이 양쪽에 구성.
  - **inert 착지(fail-open + shadow, P4-e/f 교훈 반영)**: config `leverage.enabled` 기본
    `false` ⇒ 필터 미구성. enabled여도 `mode` 기본 `shadow` ⇒ 관측 전용(모든 신호 통과).
    enforce여도 **snapshot provider 미배선**(현 착지는 어떤 데몬도 주입 안 함)/`max_gross_leverage`
    None/`equity<=0`(0 나눗셈 방지)/역직렬화 실패·비Mapping·손상 leg → **pass**. **모든 provider
    접촉면(호출·Mapping 타입체크·positions 순회·강제변환·나눗셈)을 단일 fail-open 가드
    (`_read_gross_leverage`) 안에** — 손상 스냅샷이 `evaluate()`로 raise 전파돼 데몬 fail-CLOSED
    (poison 미XACK·파이프 정체) 되는 것을 차단(P4-e F1). enabled+provider 미배선이면 build-time
    1회 unwired 경고(P4-e F5). **staleness 양성형**(`stale_max_age_seconds` 설정 시 asof_ts
    없음/파싱실패/초과 → stale → pass, #458). **신규 Redis 키 0**(provider가 읽기만).
  - **구조적 inert**: 어떤 데몬도 provider를 주입하지 않아 무동작. 실효 활성화 = 후속(P4-h2/P5:
    position+equity 스냅샷 provider 배선 + 선물 `leverage_product_specs`) + 운영자 `mode:enforce` flip.
  - **테스트**: 기존 risk 테스트 무수정 green(1288) + `test_filter_leverage.py`(provider 없음/캡
    없음/equity<=0/손상·비Mapping·비Sequence·손상 leg/mode≠enforce/gross>cap 거절/gross≤cap 통과/
    long·short 대칭/multiplier 반영(선물 승수 vs 주식 1)/경계 strict `>`/staleness 양성형 +
    settings 기본값) + **no-op 동등성**("enforce+provider 없음 필터 layer ≡ 필터 없는 layer" 동일
    verdict — inert 증명) + 양자산 구성 + 주식 core_correlation 후미 유지 통합.
- [x] **(d) 증거금 게이트 필터 신설 (P4-f)**: `shared/risk/futures_margin.py` 읽기모델
  (`futures:risk:latest`, `services/futures_margin_risk` 발행)을 생존 세계 World-B
  (`RiskFilterLayer`) **진입 게이트**로 배선. 기존 디커플 선물 체인은 증거금 인식이
  전무했음 — 계정 증거금사용률/청산버퍼/스트레스손실은 대시보드·헤지 레인이 읽는
  advisory 읽기모델로만 존재했다.
  - **신설**: `shared/risk/filters/margin_gate.py::MarginGateFilter`
    (`mode`=shadow|enforce + `latest_key` + `stale_max_age_seconds` +
    `snapshot_provider`). **임계값 재계산 0** — 발행측이 이미 분류한 `risk_level`을
    읽어 분기만 한다(모든 임계값은 발행측 `config/futures_margin.yaml`에만; 여기서 중복 0).
  - **소비 스냅샷 계약**: `futures:risk:latest` 해시의 `risk_level`(ok<watch<
    reduce_only<block_new_entries<critical, 발행측 `RISK_LEVELS` SoT) +
    `asof_ts`(KST-naive ISO, staleness) 두 필드만. `risk_level ∈
    {block_new_entries, critical}` **AND** enforce 모드일 때만 거절
    (`skip_reason=margin_gate_<level>`). `reduce_only`는 이 착지에서 **통과**(관측 전용
    — 소프트 size factor를 새로 만들면 하드코딩 임계값 도입이므로 P5/운영자로 이연;
    대시보드는 이미 reduce_only를 warn advisory로 노출).
  - **futures-only**: `from_config`는 `_asset_class == 'futures'`일 때만 필터를 만든다
    → `StockRiskConfig`가 `margin_gate` 블록을 상속해도 주식 체인은 이 필터를 만들지 않음
    (asset_class 게이트 + risk_stock 섹션 미기재 이중 방어).
  - **inert 착지(fail-open + shadow, P4-e 교훈 반영)**: config `margin_gate.enabled`
    기본 `false` ⇒ 필터 자체 미구성. enabled여도 `mode` 기본 `shadow` ⇒ 관측 전용
    (모든 신호 통과). enforce여도 스냅샷 없음(dormant 발행자)/stale/역직렬화 실패/미지
    risk_level → **pass**(fail-open, `PortfolioMddFilter`·`ConcurrentPositionsFilter`
    패턴). **모든 provider 접촉면(호출·Mapping 타입체크·str 강제변환)을 단일 fail-open
    가드(`_read_snapshot`) 안에** — 손상 스냅샷이 `evaluate()`로 raise 전파돼 데몬이
    fail-CLOSED(poison 미XACK·파이프 정체)되는 것을 차단. **staleness 양성형**
    (타임스탬프 없음/파싱실패 → stale로 간주 → pass, 메모리 #458 "bear NaN" 회귀 방지).
    **신규 Redis 키 0** — `futures:risk:latest`는 발행자가 만드는 기존 키를 **읽기만**
    (기본 provider는 `hgetall` 단독; 어떤 키도 쓰지 않음, TTL은 기존 키 것).
  - **발행자 dormant → 구조적 inert**: `services/futures_margin_risk`가 compose
    프로파일 부재로 dormant → `futures:risk:latest` 스냅샷이 없어 게이트 **무동작**.
    **게이트가 작동 중이라는 오해 방지 — P5 발행 전엔 무동작.** 실효 활성화 =
    **P5(발행자 기동) + 운영자 `mode:enforce` flip**. build-time 진단 로그로
    'armed(enforce)·발행자 의존' vs 'shadow 관측' 구분.
  - **테스트**: 기존 risk 테스트 무수정 green(기존 통과 동작 불변) +
    `test_filter_margin_gate.py`(없음/stale/손상/mode≠enforce/critical·block_new_entries
    거절/ok·watch·reduce_only 통과/미지 level/타임스탬프 없음 양성형 + settings 기본값) +
    **no-op 동등성**("enforce+스냅샷 없음 필터 layer ≡ 필터 없는 layer" 동일 verdict —
    inert 증명) + futures-only(stock 체인 미구성) 통합.
- [x] **(e) 동시진입 총량/자산별 필터 신설 (P4-e)**: World-A 모놀리식 `RiskManager`의
  `max_total_positions`(:228)와 자산별 `get_asset_limits().max_positions`(:236) 캡 능력을
  생존 세계 World-B(`RiskFilterLayer`)로 이식. 기존 World-B는 `OpenPositionFilter`(심볼당
  1개, bool provider)만 있었음 — 총량/자산별 동시진입 제한은 은퇴 대상 모놀리식에만 존재했다.
  - **신설**: `shared/risk/filters/concurrent_positions.py::ConcurrentPositionsFilter`
    (`asset_class` 바인딩 + `open_positions_count_provider: () -> Mapping[str,int]|None`
    count provider + `max_total_positions`/`max_positions_per_asset` 캡). 총량 =
    `sum(counts.values())`, 자산별 = `counts.get(asset_class, 0)`.
  - **경계 연산자 parity**: 거절 경계 `>=`(cap 도달 시 차단)로 manager.py와 비트동일
    (`total_positions >= max_total_positions` / `position_count >= asset_limits.max_positions`).
  - **관심사 분리**: `OpenPositionFilter`를 확장하지 않고 **별개 필터**로 신설 —
    bool(심볼당) provider와 count provider 시그니처 오염 방지(설계 2.8).
  - **스냅샷 스키마 불변**: `RiskStateSnapshot`엔 포지션 카운트가 없음(daily_trade_count만)
    → 스키마 확장 없이 provider로 주입(`OpenPositionFilter`/`PortfolioMddFilter`와 동일 seam).
  - **inert 착지(fail-open + shadow)**: config `concurrent_positions.enabled` 기본 `false`
    ⇒ 필터 자체를 구성하지 않음(구조적 무동작). enabled여도 count provider 미주입 /
    캡 미설정(None) / provider None·예외 → **pass**(fail-open, `PortfolioMddFilter` 패턴).
    두 shadow 데몬(risk_filter/stock_risk_filter)은 provider 미주입이라 이 PR에서 무영향 —
    데몬 배선은 후속(운영자 flip). config 캡 키명은 World-A와 정합
    (`max_total_positions`=risk_management.max_total_positions,
    `max_positions_per_asset`=asset_limits.{stock:15,futures:5}.max_positions) → P4-h2 통일 대비.
  - **테스트**: 기존 risk/데몬 스위트 **무수정** 1217 green(기존 통과 동작 불변 증명) +
    `test_filter_concurrent_positions.py`(fail-open×3·경계 `>=`·자산 스코프·캡 단독) +
    from_config no-op 동등성("enabled+provider없음 필터 layer ≡ 필터 없는 layer" 동일 결과).

**게이트**: 기존 risk 테스트 43파일 green + 프리미티브 단위 테스트 +
평균회귀 구조 충돌 회귀 테스트(#600의 streak-breaker 교훈 보존) + paper 관찰.

## 7. Phase 5 — Futures Context + Hedge Engine 가동 (지시서 §6·§7)

**목표**: 코드 신규가 아니라 **배선과 스케줄링**. 대부분 이미 구현돼 있음.

- [x] dormant 서비스 3개(`futures_context`/`futures_contract`/`futures_margin_risk`)를
  `deploy/scheduler.crontab`(KST) 등록. **랜딩 노트**: 세 서비스는 이미 구현·테스트
  완료(dormant)였고 스케줄만 부재했음. 등록 스케줄(KST, 의존성 정렬):
  `futures_contract` premarket 08:00 / close 18:40(roll-state는 캘린더 기반 일 1~2회
  + 48h TTL 폴백); `futures_margin_risk` `*/15 8-15`(15m TTL ⇒ 15분 카데스로 세션 내내
  신선 유지, 08:45 개장 커버); `futures_context` premarket 08:10 / `10,40 9-15` /
  close 18:50(상류 4개 해시 발행 이후 + 발행 분과 오프셋해 delete+hset 레이스 회피).
  스케줄러 이미지는 메인 `Dockerfile`(`COPY . .`)로 빌드 → 세 모듈 이미 포함,
  compose 변경 불필요(리빌드+recreate만). **무주문 불변식 유지**: 세 서비스는
  order_router/place_order/executor를 import하지 않는 read-model 발행 전용
  (import-graph 가드로 확인) — 스케줄 등록이 오더 경로를 건드리지 않음.
- [ ] 외인선물 수집 stub(`shared/llm/futures_flow_collector.py:38`) 해소 —
  market_structure_collector가 이미 수집하는 `fut_foreign_net_qty`를 정식 소스로 배선.
- [ ] `FuturesMarketContextV2`(basis/OI/외인/롤/증거금/틱가치 regime 분류)를
  Setup 컨텍스트·대시보드에 노출 (관측 전용 유지, 게이팅은 별도 결정).
- [ ] Hedge v2 부분헤지: 위 배선으로 의존성(`futures:contract:latest`, `futures:risk:latest`)
  충족 → advisory 완성. **주문 연결은 이 계획 범위 밖(운영자 결정).**
- [x] basis 계산 단일화 확인(정정): `shared/arbitrage`는 **존치**한다 —
  `market_structure_collector`가 `shared/arbitrage/basis_calculator.py`의
  `BasisCalculator`를 소비해 `fut_basis`를 산출하므로 삭제 금지 컴포넌트다(이전
  서술 "P0에서 제거됐으므로"는 사실 오류). basis 계산은 이미 이 단일 사이트로
  일원화돼 있고, futures_context는 그 결과(`market:structure:latest`)를 접어
  regime을 분류할 뿐 basis를 재계산하지 않는다.

**게이트**: read-model 검증 스크립트 + Redis 스냅샷 신선도 + advisory-only 불변식
(주문 경로 import-graph 가드) 유지 확인.

## 8. Phase 6 — 실행 계층 마감 (지시서 §9, 장기)

- [ ] **KIS 데이터 파사드**: `KISClient` 직접 import 10곳을 어댑터 인터페이스 뒤로 —
  지시서 "의존성은 Adapter 계층 통해서만"의 데이터측 마감.
  - **재판정 (2026-07-12, PR-0 정찰)**: 정찰이 제기한 "주문 경로 리스크"는 허구. 실사용
    `KISClient`는 **읽기 전용**(시세/잔고: `get_current_price`/`get_futures_balance`)이고,
    주문은 executor 스택(`OrderExecutor`→`KISFuturesAdapter`→`ForceCloseExecutor`)이 별도
    담당 — `KISClient.submit_ats_order`는 콜러 0(데드코드). 파사드가 주문 경로를 감싸야
    한다는 전제는 성립하지 않음.
  - **파사드(포트+팩토리)는 YAGNI로 대기**: 구현체 1개뿐이고 테스트는 이미 구조적 fake로
    구성됨(2nd 구현체 없는 Protocol = 콜러 없는 추상화). 값이 발생하는 시점 = F-9 라이브
    컷오버 / 디커플 주식 주문 경로 배선(둘 다 주입 seam을 실제로 건드림) — 그때 얹는다.
  - **PR-0 (완료, 이 항목의 선행 버그픽스)**: 깨진 실거래-인접 오퍼레이터 스크립트 2개
    (`scripts/trading/flatten_all.py`, `scripts/trading/recover_positions.py`)가
    `KISClient(config=..., auth_manager=...)`로 config-only 생성자에 존재하지 않는
    `auth_manager` kwarg를 넘겨 **실행 즉시 TypeError**(테스트 0 커버). config-only 생성으로
    교정(`KISClient`는 `KISAuthManager.get_instance(config)`로 auth를 내부 구성) + 생성 경로
    스모크 테스트 추가. behavior-0(동작 무변경, 크래시만 제거).
  - **잔여 finding (파사드 착수 시 정리)**: `KISAuthConfig`-from-env 구성이 ~10곳 중복(DRY
    대상)이나 사이트별 real/mock 자격증명 분기가 섞여 있어 behavior-0 지뢰 — 무분별한
    동질화 금지. 파사드 도입 시 팩토리로 통합.
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
