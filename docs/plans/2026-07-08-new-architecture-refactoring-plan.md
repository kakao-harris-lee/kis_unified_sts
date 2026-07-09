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
- [ ] vectorbt CI 레인: `.[backtest]` extra 설치 + import smoke 테스트 (P3 준비).
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
  stateless 프리미티브 6종(ema/sma/rolling_return_std/rvol_last/swing_low/window_extremes,
  #608 — resolver/IndicatorBackend 밖에 있어 shadow-parity가 자동 커버하지 않음)과
  `backtest_backend.py`·compat 백엔드들의 중복 `_ema/_sma` 계열을 엔진 단일 구현으로 통합.

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
- 레거시 경로의 `StreamingIndicatorResolver`(flat scalar)와 builder 경로의
  `IndicatorContext`(DataFrame)를 `IndicatorSpec`/`flat_key` 기준으로 정렬 —
  지시서의 "Indicator Context" 단일화. 캐시(`IndicatorCacheEngine`)로 중복 계산 제거.
- 후보(P2-a 리뷰 follow-up): `StrategyFactory.create`의 builder_v1 특례 블록
  (스트리밍 가드/게이트 주입/exit 프리미티브 조합)을 별도 builder-브릿지 모듈로 추출.

### P2-c. 활성 전략 파일럿 마이그레이션 (신호 동등성 게이트)
- 순서: `williams_r`(순수 조건) → `pattern_pullback`/`momentum_breakout`(조건+쿨다운) →
  Setup A/C/D(조건 그래프 + context 필드; 어휘 밖 조건은 P2-a 확장으로 수용).
- 전략별 게이트: 구현 old vs new를 동일 기간 백테스트해 **신호 시퀀스 동일** 확인 후
  YAML 교체. 표현 불가 판정이 나면 레거시 컴포넌트로 존치하고 사유를 카탈로그에 기록
  (하이브리드 최종 상태 허용 — 단 신규 전략은 선언형 기본).

### P2-d. Builder UI 정합
- 신규 스키마 필드(방향/exit 프리미티브/게이트)를 UI 카탈로그·`/capabilities`에 노출.
- `config/strategies/built/golden_cross.yaml`의 stale "cross 스트리밍 불가" 주석 정리.

**게이트**: 파일럿 전략 신호 동등성 + 기존 builder E2E(등록→paper) 회귀 + UI lint/build.

## 5. Phase 3 — vectorbt 백테스트 엔진 (지시서 §5, WS-A4 승격)

**목표**: 커스텀 이벤트 루프·성과지표 3중 중복을 vectorbt로 대체. 소비자 API는 계약 유지.

### P3-a. 주식 경로 (본체)
- 신규 `VectorbtRunner`: (P1의) TA-Lib 지표 시리즈 + (P2의) 선언형 조건 →
  entries/exits boolean 배열 → `vbt.Portfolio.from_signals`.
  비용 모델은 한국 매도세/수수료/슬리피지를 vbt fees/slippage 파라미터로 매핑
  (ats_simulator 경로는 옵션 유지).
- `BacktestResult`/`BacktestTrade`/`to_metrics_dict()`는 **어댑터로 유지** —
  `Portfolio.stats()`/`trades.records`에서 채운다. 소비자(experiment_runner, optimizer,
  CLI :132/:180/:451/:826, dashboard `/experiments`)는 무수정이 목표.
- 심볼별 독립 백테스트 + 등가중 집계 및 리포트 스키마
  `{experiment, data_coverage, summaries[], equity_curves{}, trades[]}` 보존 (하드 계약).
- `LookaheadGuard` 의미 보존: 시리즈 사전계산은 shift 규율로 look-ahead 차단, 계약 테스트 추가.

### P3-b. Parity 게이트 (WS-A4 게이트 그대로)
- 활성 주식 3전략 × 신뢰 데이터 윈도우에서 기존 `BacktestEngine` 대비
  총수익/샤프/MDD/트레이드 수 일치(허용오차 문서화) + Optuna 스윕 속도 개선 측정.
- 통과 후 `engine.py` 이벤트 루프·수제 성과지표(§3.2의 3벌)를 제거하고
  experiment_runner/optimizer 백엔드 교체. 미통과 항목은 원인 규명 전 교체 금지.

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
