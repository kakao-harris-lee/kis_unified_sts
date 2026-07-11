# 신규 아키텍처 Gap Analysis (2026-07-08)

> 대상 지시서: [docs/2026-07-08_new_architencture.md](../2026-07-08_new_architencture.md)
> 후속 계획: [2026-07-08-new-architecture-refactoring-plan.md](2026-07-08-new-architecture-refactoring-plan.md)
> 조사 기준: main `78c94fd1` (2026-07-08), 6개 병렬 코드 조사 결과 종합.

## 0. 결론 요약

지시서의 목표 아키텍처(TA-Lib + vectorbt + 선언형 YAML + Registry/Adapter 계층)는
**제로베이스 재설계가 아니라, 이미 절반쯤 진행된 마이그레이션의 완성**에 가깝다.

| 목표 컴포넌트 | 현재 상태 | Gap 크기 |
|---|---|---|
| Indicator Registry + TA-Lib Adapter | **구축 완료, 채택 미완** — `shared/indicators/engine/`에 TA-Lib 백엔드(~45지표+57캔들패턴), Spec/Registry/캐시/섀도 게이트 실재. 단 실제 TA-Lib 경로 소비자는 노코드 빌더 1개뿐 | 중간 (전환 게이트 flip + 수제 사이트 ~50개 흡수) |
| Indicator Context | **부분** — resolver/`IndicatorContract`/`flat_key`가 수렴 seam. 주입 경로 3개(라이브/백테스트/빌더)의 parity는 수작업 유지 | 중간 |
| Strategy Compiler (선언형 YAML) | **아키텍처 완성, 커버리지 미완** — builder_v1이 목표 파이프라인을 그대로 구현·출하 중(110개 지표 카탈로그, 선언형 조건 평가기). 레거시 전략 13+12개는 "컴포넌트명+파라미터" YAML(조건식은 Python 안) | 중간~큼 (승격+표현력 확장) |
| Signal Generator (조건만 평가) | **부분** — 전략 코드는 백테스트/라이브 간 이미 공유. 단 일부 entry/exit에 지표 계산 내장 | 중간 |
| vectorbt Engine | **미착수** — pyproject `backtest` extra로 선언만, import 0건 (WS-A4). 커스텀 엔진 2개 + 성과지표 3중 중복 수제 구현 | 큼 |
| Portfolio / Position Engine | **백테스트측은 vectorbt로 대체 가능** — 라이브 포지션/렛저와 이미 완전 격리 | 큼(백테스트) / 0(라이브: 유지) |
| Risk Engine | **존재하나 이중화·산재** — 병렬 2세계(모놀리식/디커플), daily-loss·연속손실 3중 중복, 스탑/트레일링 14곳 산재, 레버리지 제한 부재 | 큼 |
| Hedge Engine | **v1 실재(advisory-only, 일일 구동)** — β 순노출·권고 숏계약 계산. v2 부분헤지는 dormant 의존성 때문에 무력 | 작음~중간 |
| Futures Context Engine | **프리미티브 완비, 조합 dormant** — basis/OI/외인선물/증거금 원시데이터는 라이브 수집 중, 조합 서비스 3개는 미스케줄 | 중간 |
| KIS Adapter + 실행 계층 분리 | **대부분 충족** — 주문 경계는 duck-typed `kis_client` seam으로 교체 준비 완료. "동일 전략, 실행계층만 교체" 불변식은 이미 성립 | 작음 |

**한 줄 판정**: 지시서가 요구하는 것의 상당수는 "새로 만들기"가 아니라
(1) 이미 있는 TA-Lib 엔진으로 **수렴 완료시키기**, (2) vectorbt로 백테스트 스택 **교체하기**,
(3) 산재한 리스크/스탑 로직 **한 곳으로 모으기**다. 이 구분이 리팩토링 계획의 뼈대다.

## 1. 지표 계산 (지시서 §2·§3: Indicator Engine / Registry)

### 1.1 이미 있는 것 — Track A 지표 엔진

`shared/indicators/engine/` (~1,900 LOC, 15모듈; PR #576/#578/#579/#580/#581):

- `spec.py` — `IndicatorSpec`(frozen/hashable, dedup 키) + `flat_key()` 카탈로그
  (`bollinger.upper → bb_upper` 등 flat 런타임 키 단일 테이블). **지시서의 "IndicatorSpec"이 이미 존재.**
- `talib_backend.py`(547 LOC) — data-driven `_TABLE`(:441)로 ~45개 표준지표
  (RSI/EMA/SMA/ATR/ADX/CCI/BBANDS/MACD/STOCH/StochRSI/MFI/OBV/ROC/TRIX/SAR/Aroon/…)
  **+ 57개 캔들패턴 전체**. repo에서 talib을 import하는 유일한 지점. **지시서의 "TA-Lib Adapter"가 이미 존재.**
- `numpy_backend.py`(264) — TA-Lib 밖 8개(vwap/rvol/ichimoku/donchian/keltner/vwma/hma/volume_accel).
  단 내부에 keltner/hma용 자체 `_ema/_atr/_wma`(:43,58,72) 보유 → TA-Lib 조합으로 대체 가능.
- `registry.py` — `IndicatorEngine` 파사드 + 5개 flavor. 핵심은
  `runtime_indicator_engine()`의 **convention gate**(`STS_INDICATOR_CONVENTION`, :168-196):
  기본 `streaming`(수제 관례와 bit-identical), 수렴 게이트 통과 후 `talib`로 flip하는 온램프.
- `cache.py` — `IndicatorCacheEngine`+`PanelStore` ("10전략×RSI(14)=심볼당 1계산").
- `shadow.py` — `ShadowDelta` 위임 분류 게이트. 실데이터 분류(PR #581):
  safe={rsi, adx, mfi, bb_middle, rvol} / gated={atr, bb_width(~2.53%), stoch_k}.
- `stateful.py`(393) — 세션 VWAP·틱초 VolumeAccel. TA-Lib 매핑 불가한 **정당한 예외**.

### 1.2 Gap ① — TA-Lib이 실제 계산 경로인 곳은 빌더뿐

- 실 TA-Lib 경로(`default_engine()`)의 소비자는 **노코드 빌더 1개**.
- 라이브 런타임·momentum·daily·regime 경로는 엔진 인터페이스 뒤로 funnel은 됐지만
  Compat 백엔드 3개(streaming/momentum/daily)가 기존 수제 관례를 그대로 보유
  (first-delta Wilder RSI, ddof=1 BB, lenient ADX 등). **캡슐화만 됐고 위임은 안 됨.**

### 1.3 Gap ② — 병렬 수제 SoT `reference.py`

`shared/indicators/reference.py`(689 LOC)가 명시적 "no TA-Lib" 수제 표준 레이어로 존재:
`wilder_rma`/`wilder_rsi`/`ADXCalculator`/`StochRSICalculator`(stochrsi_k/d 유일 생산자)/
`ATRCalculator`(sma|wilder 모드 노브 — "ATR 7중 분열·24% gap" 교정의 산물)/`MFICalculator`.
volume_ratio·regime detector·런타임 ATR이 여기로 위임 중 → **엔진과 경쟁하는 2번째 SoT**.
TA-Lib 어댑터로 흡수하되 sma-vs-wilder ATR 관례와 warmup/flat-window sentinel(RSI/MFI 50 vs 0)
계약을 게이트로 보존해야 함.

### 1.4 Gap ③ — 패키지 밖 수제 계산 사이트 약 50개

| 클러스터 | 대표 사이트 | 내용 |
|---|---|---|
| `shared/backtest/` (~11, 최대) | `daily_adapter.py:261-388`, `adapter.py:187-228`, `market_context_replay.py:49-75` | SMA/ATR/RSI/Donchian/RVOL/VWAP 수제 (백테스트-라이브 지표 괴리의 원천) |
| `shared/llm/` (~10) | `analyzers.py:42-86,282-309`, `market_analyzers.py:336-450`, `stock_screening.py:137-158` | RSI/MACD/BB/MA rolling·ewm |
| `shared/trend/` (5, 위임 0) | `technical_calculator.py:69-165` | EMA/ATR/SMA/Ichimoku — 단 **런타임 미사용(폐기 후보)** |
| `shared/scanner/` (5) | `accumulation.py:73-279` | ATR/OBV slope/RVOL/ROC |
| `shared/strategy/` (7) | `technical_consensus.py:238-243`, `macd_ema_crossover.py:244-274`, `trix_golden.py:346-449` | 전략 내장 지표 계산 (지시서 §4 위반) |
| `services/` (6) | `daily_scanner.py:154-215`, `services/trading/indicator_calculations.py:144-213` | Wilder RSI/ATR 수동 루프, 잔존 daily-EMA/high-N |
| `shared/regime/` (3) | `adaptive_detector.py:203-205`, `detector.py:46-66` | SMA+수익률 σ (MFI/ADX/ATR은 reference로 위임 완료) |

일반 통계 성격(OFI z-score, HAR-RV, OLS β 등)은 지표가 아니므로 대상 외.

### 1.5 지표 주입 경로 3개 (parity seam)

1. **라이브**: `StreamingIndicatorEngine` → `StreamingIndicatorResolver`(`resolver.py`)가
   전략별 `IndicatorContract`(`contracts.py`) 요구 키(momentum_5m/mtf_base_15m/last_15min_high)를 조립.
2. **백테스트**: `adapter.py` `_BarEnricher` — 기술지표는 라이브와 동일 엔진 경유(parity),
   volume/VWAP/Donchian만 로컬 수제.
3. **빌더**: `default_engine()`(TA-Lib) → 캐시 → flat panel. **유일한 end-to-end TA-Lib.**

`flat_key` 테이블 + `IndicatorContract`가 세 경로의 수렴 지점이며, 지시서의 "Indicator Context"에 해당.

## 2. 전략 정의/실행 (지시서 §1·§4: Strategy Compiler / Signal Generator)

### 2.1 현재 — 전략 모델이 2개 병행

**레거시 모델 (주식 YAML 14개 중 13개 + 선물 전체):**
```yaml
strategy:
  name / asset_class / enabled
  entry:    {type: <Python 컴포넌트명>, params: {…flat 임계값…}}
  exit:     {type: …, params: …}
  position: {type: …, params: …}
  indicators: {…}   # 사실상 advisory, 컴파일러를 구동하지 않음
```
`entry.type`이 Python 클래스를 지명하고, **조건식 자체는 클래스 안에 하드코딩**
(예: williams_r YAML엔 `oversold_threshold:-85`만 있고 "W%R이 -80 상향 돌파 + 추세 상방"
로직은 `WilliamsREntry.generate()` 안). 새 규칙 추가 = Python 수정. 지시서가 말하는
선언형의 정반대 극단.

**선언형 모델 (builder_v1) — 이미 출하 중:**
`shared/strategy_builder/`(~1,660 LOC)의 자체 docstring이 지시서의 파이프라인을 그대로 명명:
"YAML → IndicatorSpec → TA-Lib Registry → TA-Lib Adapter → Indicator Context (DataFrame)
→ Condition Evaluator → Strategy Engine" (`indicator_context.py:1-19`).

- `schema.py` — `BuilderState` = `indicators:[{indicator_id, alias, params, output}]` +
  entry/exit `BuilderConditionGroup{logic: AND|OR, conditions:[{left, operator, right}]}` + risk.
  피연산자는 indicator|value|price(:139), 연산자는 greater_than/…/cross_above/cross_below(:39).
  **"RSI < 30", "EMA20 > EMA60"이 이미 데이터로 존재.**
- `indicator_context.py:79` — `BuilderIndicator` → `IndicatorSpec.create` → 엔진(TA-Lib) 계산
  → alias.output 컬럼 DataFrame (풀 시리즈라 cross 연산 가능).
- `evaluator.py` — `evaluate_group/evaluate_condition/_compare`(:78/:97/:171)는
  선언형 비교만 수행, 지표 계산 0. **지시서 §4의 Signal Generator 그 자체.**
- 지표 카탈로그 `config/strategy_builder/indicators.yaml` — **110개 지표 정의**
  (params/outputs/backtest_supported/runtime_supported 플래그 포함).
- 런타임 브리지: `entry/builder_strategy.py::BuilderStrategyEntry`(registry명 `builder_v1`)가
  `required_indicators=["ohlcv"]`로 캔들 윈도우를 받아 엔진으로 컨텍스트 계산 후 선언형 평가.
  cross 연산의 스트리밍 제약은 해소됨(`runtime_support.py` unsupported set 비어 있음).
- 실체화 경로 가동 중: UI → `POST /api/kis-builder/register-paper`(`kis_builder.py:261`) →
  `config/strategies/built/<id>.yaml`(`entry.type: builder_v1` + `params.builder_state`).
  실례: `config/strategies/built/golden_cross.yaml`(SMA cross, 완전 선언형).
  단 이 파일의 "cross는 스트리밍 불가" 주석은 stale.

**결론: 지시서의 Strategy Compiler는 신규 구축 대상이 아니라 builder_v1의 승격 문제.**

### 2.2 레지스트리/조합 메커니즘 (유지 대상)

- `registry.py` — `EntryRegistry`(:174)/`ExitRegistry`(:188)/`SizerRegistry`(:202),
  `@register` 데코레이터, `CONFIG_CLASS.from_dict` 파라미터 변환(:140-146).
- `builtin_components.py` — 컴포넌트명→모듈·클래스 정적 테이블(:13/:110/:178). 공식 인벤토리.
- `factory.py::StrategyFactory.create`(:21)가 YAML→레지스트리 조회→`TradingStrategy` 조합.
- `base.py::TradingStrategy`(:311)는 entry/exit/sizer의 얇은 조합체 —
  지시서의 "asset-specific code thin" 원칙과 이미 부합.

### 2.3 entry/exit 생성기 인벤토리 (~30개, 분류)

| 분류 | 컴포넌트 | 판정 |
|---|---|---|
| **지표계산 내장 (§4 위반)** | entry: `macd_ema_crossover`(:244-274 ewm/rolling), `trix_golden`(:347-356), `vr_composite`(:174-197, disabled), `opening_volume_surge`(:273-304) · exit: `vr_composite_exit`, `trix_golden_exit`(:580 swing-low/divergence), `track_a_exit`(:67-105 rolling max-adverse) | 엔진 위임 또는 선언형 재작성 대상 |
| **순수 조건 (목표형)** | `stochrsi_trend`, `breakout`(무상태), Setup A/C/D 어댑터(`Setup*.check()` 위임), `setup_target_exit` | 이미 목표 형태 |
| **선언형 (목표 그 자체)** | `builder_v1`/`builder_v1_exit` — 엔진 경유 계산 + 선언 평가 | 승격 대상 |
| **순수조건+쿨다운 상태** | `mean_reversion`, `momentum_breakout`, `pattern_pullback`, `trend_pullback`, `daily_pullback`, `volume_accumulation`, `technical_consensus` 등 대부분 | 조건은 선언형 표현 가능; 쿨다운은 프레임워크 공통화 후보 |
| **상태머신 exit** | `three_stage`(807 LOC, stage machine), `momentum_decay`(701, 8-check ladder), `atr_dynamic`, `chandelier` | 선언형으로 환원 불가 — 별도 exit 프리미티브로 존치 |

### 2.4 builder_v1 → 1차 포맷 승격의 실질 Gap

1. **표현력**: 활성 6전략 중 선언형으로 즉시 환원 가능한 것과 불가한 것이 갈림.
   Setup D의 ATR-percentile 변동성 게이트처럼 현 operand/operator 어휘 밖의 조건 존재.
2. **방향성**: builder entry는 Phase 1 long-only(`builder_strategy.py:8`) —
   선물 long/short 대칭 불변식과 충돌. `signal_direction` 산출이 스키마에 필요.
3. **Exit 어휘**: builder risk/exit은 stop/target/trailing % 뿐 — three_stage·momentum_decay 같은
   상태머신 exit 미지원 (이들은 선언형 밖의 exit 프리미티브 라이브러리로 유지해야 함).
4. **게이트 훅 부재**: regime gate/LLM context/veto가 선언형 스키마에 없음.
5. 관련 선행 계획: `2026-07-05-declarative-talib-builder.md`, `2026-07-06-talib-builder-alignment.md`,
   `2026-07-04-indicator-coverage-builder-catalog-roadmap.md`.

### 2.5 LOC

`shared/strategy` 16,984 (최대 단일 패키지; 대부분이 ~30개 명령형 생성기 —
three_stage 807, momentum_decay 701, trix_golden_exit 646, momentum_breakout 523) vs
`shared/strategy_builder` 1,660. **선언형 전환의 LOC 레버리지가 가장 큰 곳.**

## 3. 백테스트/포트폴리오 (지시서 §5: vectorbt)

### 3.1 현재 — 커스텀 엔진이 2개

| 엔진 | 파일 | 내용 |
|---|---|---|
| 주식/범용 | `shared/backtest/engine.py`(931) + `adapter.py`(789) + `daily_adapter.py`(620) | bar 단위 Python 이벤트 루프. Position 상태머신, 비용모델(수수료/슬리피지/한국 매도세/선물 point_value), ATR·고정 스탑/TP/트레일링/강제청산 내장 |
| 선물 | `decision_harness.py`(474) + `market_context_replay.py`(357) | Setup A/C/D 신호 → RiskFilterLayer → 자체 fill 시뮬(다음 바 시가±0.3틱), 틱 단위 PnL. `BacktestEngine` 미사용 |

### 3.2 성과지표 수제 구현 3벌 (지시서 "직접 구현 금지" 직접 위반)

1. `engine.py:771-882` — win_rate/profit_factor/MDD/Sharpe(√252, rf=0.03)/Sortino
2. `experiment_runner.py:169-200` — 포트폴리오 레벨 재계산 + 멀티심볼 NAV 수제 결합
3. `decision_harness.py:66-73` — 선물 틱 기반 SetupStats

### 3.3 vectorbt 현황: 선언만, 코드 0

- `pyproject.toml:152-154` optional extra `backtest = ["vectorbt>=0.26"]` — **import 0건**.
- 유일한 계획 근거: `docs/plans/2026-07-05-indicator-engine-and-stream-schema-roadmap.md` §WS-A4
  ("기존 adapter.py 경로와 수익/샤프/MDD parity 확인 후 교체"). 후순위로 배치돼 있었음 →
  이번 지시서가 이를 최우선으로 승격.

### 3.4 vectorbt가 대체 가능한 것 / 못 하는 것

**대체 대상**: position/order 상태머신, 비용/PnL 회계, equity curve,
3중 중복 Sharpe/Sortino/MDD/승률/profit factor/트레이드 로그.

**보존·재배선 필요**:
- registry 전략 → 신호 어댑터 (look-ahead 안전 지표 주입; `LookaheadGuard` 유지)
- 심볼별 독립 백테스트 + 등가중 집계 및 대시보드 리포트 스키마
  `{experiment, data_coverage, summaries[], equity_curves{}, trades[]}` (하드 계약)
- ATS venue/한국 세제 비용 특수성, 선물 틱-PnL 컨텍스트 replay
- walk-forward fold 스크립트(`scripts/walk_forward_*.py` — 선물 harness 경로)

**소비자 API surface (parity 게이트 대상)**:
`BacktestEngine(strategy, config).run(df) -> BacktestResult`(+`to_metrics_dict()`),
`experiment_runner.run_stock_experiment(spec)`, `optimizer.StrategyOptimizer`/`ParamSpec`,
`cli/main.py`(:132,:180,:451,:826), `services/dashboard/routes/experiments.py:104-127`.

### 3.5 라이브 경계 — vectorbt가 건드리면 안 되는 것

`shared/backtest/`는 라이브 position/ledger 코드를 전혀 import하지 않음(역도 성립).
LIVE 유지: `services/trading/position_tracker.py`(~2,300), `shared/paper/broker.py` VirtualBroker(~650),
`shared/storage/runtime_ledger*.py`(~1,500), `shared/portfolio/`(advisory), `shared/execution/`.
고아 발견: `shared/position/`(~694 LOC)은 **test-only** — PositionTracker로 대체된 잔재.

## 4. 리스크 (지시서 §8: Risk Engine)

### 4.1 목표 기능별 현황

| 목표 기능 | 상태 | 위치 |
|---|---|---|
| ATR 기반 Stop | 리스크 모듈에 **없음** — exit 생성기 6곳에 산재 (ATR 배수 2.0/2.5/3.0/6.0/1.5로 제각각) | `exit/atr_dynamic.py:215,348` 외 |
| Trailing Stop | 8개 구현 산재 | `atr_dynamic.py:251`, `three_stage.py:581` 등 |
| Max Drawdown | 있음, **2중** (디커플 filters vs 모놀리식 models/manager) + kill_switch 별도 | `filters/daily_mdd.py:80` 등 |
| Position Size | 부분/산재 — 주문층 계약 캡 + risk-fraction sizer, `max_position_size_pct`는 검증만 되고 미집행 | `live_mode_guard.py:42`, `position/sizers.py:340` |
| 일 최대 손실 | 있음, **3중** (manager/filters/kill_switch) | `manager.py:175,213` 등 |
| 동시 진입 제한 | 부분 분열 — World A는 총량+자산별, World B는 심볼당 1개만 | `manager.py:228,240`, `filters/open_position.py:87` |
| 레버리지 제한 | **완전 부재** (repo 전체 grep 0건) | — |
| 증거금 체크 | 있으나 **dormant·고립** — advisory 발행기, 진입 게이트 미연결 | `shared/risk/futures_margin.py:175-198` |

### 4.2 구조 문제 — "두 세계"

- `RiskState` 클래스 2개: `risk/models.py:222`(in-process KRW dataclass) vs
  `risk/state.py`(Redis HASH) — #600 혼동의 원천. **P4-h1(#624)에서 후자를
  `RiskStateStore`로 개명해 이름충돌 해소**(전자는 orchestrator 전용, P6 소멸 예정).
- 오케스트레이터 2개: `RiskManager.can_open_position`(모놀리식 전용) vs
  `RiskFilterLayer.evaluate`(디커플 전용) — 필터 로직 미공유.
- 설정 스키마 2벌: dataclass `RiskConfig` vs pydantic `FuturesRiskConfig`/`StockRiskConfig`
  (`max_consecutive_losses` vs `consecutive_loss_hard_threshold` 등 유사 키 중복).
- 3-stage exit 상태머신 2벌: `exit/three_stage.py`(807) vs `shared/position/exit_checker.py`(218, 단위 상이).
  `shared/position/monitor.py:137`은 항상 False인 dead stub.
- `services/kill_switch`는 daily/weekly/monthly/연속손실 체크를 **재구현**.
- 사이드 인지 PnL 헬퍼 `_calc_profit_pct`가 ~9개 파일에 복붙.

## 5. 헤지/선물 컨텍스트 (지시서 §6·§7)

### 5.1 Hedge Engine — v1이 이미 있다

- `shared/portfolio/hedge.py`(943 LOC): β 추정(:338), 순β노출(:521), 권고 숏 계약수(:559),
  HedgeAdvisorV2 밴드별 부분/전체 헤지(LOW 0 / ELEVATED 0.25 / HIGH 0.50 / CRITICAL 0.75, :164-198).
  I/O-free, import-graph 가드로 주문 경로와 격리.
- `services/portfolio_monitor`가 일일(08:50/19:00) 구동, `portfolio:hedge:latest` 발행. **advisory-only.**
- Gap: v2 부분헤지 실현가능성 판정이 dormant 발행기(`futures:contract:latest`, `futures:risk:latest`)에
  의존해 프로덕션에서 no-op. 지시서의 "동시 운용 지원"은 advisory → (운영자 게이트 하의) 실행 연결이 필요.

### 5.2 Futures Context Engine — 프리미티브 완비, 조합 dormant

- `shared/models/futures_context.py`(335): `FuturesMarketContextV2` — 계약/롤, basis+
  `classify_basis_regime`(deep_backwardation→deep_contango), OI, 외인 flow regime, 증거금, tick_value_krw.
- 원시데이터는 **라이브 수집 중**: `market_structure_collector`가 `fut_foreign_net_qty`/`fut_oi_qty`/
  `basis` → `market:structure:latest`, `night_futures_collector`(05:48)가 야간 OI+basis.
- Gap: 조합 서비스 3개(`futures_context`/`futures_contract`/`futures_margin_risk`)가
  `deploy/scheduler.crontab` 미등록 → dormant. 외인선물 전용 수집기는 stub
  (`shared/llm/futures_flow_collector.py:38-39`).
- 계약 스펙(틱가치/승수/증거금율)은 `config/execution.yaml::futures_contract_spec`
  (`shared/execution/contract_spec.py::ContractSpecRegistry`) — 이미 config-driven.
- 구식 프로토타입 `shared/arbitrage/`(332 LOC, basis z-score)는 미배선(tests only) → 정리 대상.

## 6. KIS Adapter / 실행 계층 (지시서 §9)

### 6.1 이미 충족 — "동일 전략, 실행계층만 교체"

- 전략 코드는 백테스트/라이브 간 **바이트 단위 공유**: 선물 `Setup.check()`
  (`decision_harness.py:253` = 라이브 decision_engine 동일 클래스), 주식 `TradingStrategy.check_entry()`
  (`backtest/adapter.py` = `stock_strategy` 데몬 동일 registry 전략).
- 주문 경계는 이미 교체형: 디커플 선물의 duck-typed `kis_client` 인터페이스
  (get_futures_orderbook/place_futures_order/await_fill/cancel_order)에
  `KISFuturesAdapter`(라이브)/`PaperKISFuturesAdapter`(페이퍼) 2구현이 플러그인
  (`order_router/main.py:458-486`). **vectorbt 실행층은 이 duck-type의 세 번째 구현이 아니라,
  백테스트 전용 스택으로 이미 격리된 자리에 들어간다.**
- `OrderExecutor`(`executor.py:90`)가 유일한 KIS REST 주문 클래스 (PAPER/MOCK/REAL 분기 :250).

### 6.2 잔여 Gap

- **KIS 데이터 클라이언트에는 파사드 없음**: `KISClient`를 10개 모듈이 직접 import.
  주문측과 달리 데이터측은 단일 인터페이스 교체 불가 (지시서 "의존성은 Adapter 계층 통해서만" 미충족).
- **컨텍스트 필드 parity가 수작업 유지**: `last_15min_high/low` 함정(#533/#537) 재발 가능 구조.
  라이브(`FuturesContextProvider`)와 백테스트(`MarketContextReplay`)가 같은
  `build_market_context`를 쓰지만 공유 call-site 강제가 없음.
- **체결 모델 3벌**: 백테스트(다음 바 시가±0.3틱) vs 라이브(PassiveMaker 지정가+PseudoOCO 폴링)
  vs 페이퍼(실호가+시뮬 passive fill). 백테스트 Sharpe는 passive-limit 미체결을 모름.
- 디커플 주식 파이프라인에는 **라이브 KIS 주문 경로 미배선** (VirtualBroker만).
- 모놀리식 오케스트레이터(`services/trading` 17,043 LOC)는 paper/live 분기가 산재 — 현재도
  선물 paper/live 1차 경로라 존치 필요하나, 신 아키텍처의 최종 정리 대상.

## 7. 정량 인벤토리 / 즉시 정리 가능 항목

- LOC: `shared/` 96.4K · `services/` 49.8K · `tests/` 151.4K(638파일) · UI 32.0K(TS/TSX) · `cli/` 2.7K.
- 테스트 보호막: strategy 105 · risk 43 · indicator 39 · backtest 20 · execution 27 파일 —
  이번 리팩토링 5대 영역 모두 두껍게 커버. 얇은 곳은 runtime ledger(5).
- **Dead/dormant (조기 제거 예산 ~2,600 LOC)**:
  - `shared/ml` — 소스 0, `__pycache__` 44개만 잔존 → 즉시 삭제
  - `shared/trend`(880) — 런타임 importer 0 (trend 전략 전부 disabled, tests-only)
  - `shared/ensemble`(435) — importer 0, RL 시대 잔재
  - `shared/arbitrage`(332) — 유일 소비자가 compose 미등록 서비스
  - `shared/position`(~694) — test-only 고아 (PositionTracker로 대체됨)
  - `domains/` — 이미 제거됨(`336df723`, 2026-06-25) — CLAUDE.md의 참조(`--cov=domains` 등)만 vestigial
  - 주의: `market_structure_collector`/`market_risk_engine`은 통합투자시스템 P0/P1 소속으로
    scheduler 이미지 리빌드 대기 상태 — dormant로 오판하고 삭제하면 안 됨.
- 활성 전략: 주식 3/16(momentum_breakout, pattern_pullback, williams_r),
  선물 3/12(setup_a/c/d) — 선언형 마이그레이션의 1차 대상은 이 6개.

## 8. 지시서 제약과의 충돌/주의 사항

1. **"직접 구현 금지" vs 검증된 수제 관례**: 라이브 지표 값은 수제 관례와 bit-identical해야
   운영 연속성이 보장됨. 전환은 shadow-parity 게이트(이미 존재) 경유가 필수 —
   ATR 등 gated 지표는 무단 flip 금지.
2. **vectorbt는 백테스트 전용**: 라이브 position/ledger는 vectorbt로 대체 불가(§3.5).
   지시서의 "Portfolio/Position Engine" 상자는 백테스트 문맥으로 해석해야 함.
3. **TA-Lib 미설치 함정**: 배포 호스트 .venv에 TA-Lib 미설치 시 shadow-parity가 조용히
   스킵되는 기존 함정 — CI/배포 게이트에 설치 검증 필요.
4. **기존 YAML 호환**: 활성 6전략의 YAML + builder_v1 산출물이 무중단으로 실행돼야 함.
5. **운영 불변식 유지**: KST-only, Redis DB1+TTL, config-driven, 선물 long/short 대칭,
   주식 EOD 일괄청산 금지, live 게이트(`futures_live.enabled`+Redis suspended).
