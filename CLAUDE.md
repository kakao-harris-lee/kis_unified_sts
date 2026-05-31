# CLAUDE.md - KIS Unified Trading Platform

## 🎯 프로젝트 핵심 목표

**"진입/청산 타이밍 최적화"** - 모든 설계와 구현은 이 목표에 집중한다.

```
전략 구성 → 백테스트 → MLflow 추적 → 파라미터 최적화 → 실전 적용
    ↑                                                      │
    └──────────────── 피드백 루프 ─────────────────────────┘
```

---

## 📋 프로젝트 개요

### 트레이딩 목표

#### 선물 (Futures)

- **대상 종목**: KOSPI200 선물, KOSPI200 mini 선물
- **주요 목표**: KOSPI200 mini futures로 안정적인 전략을 구사하는 것이 목표
- **운용 구조**: KOSPI200 선물(kospi200f_1m)로 전략 개발/백테스트/최적화 → KOSPI200 미니로 실거래
  - KOSPI200 선물: 유동성 충분, 14개월 1분봉 데이터 확보 (101S6000, ~100K bars)
  - KOSPI200 미니: 계약 단위 1/5로 리스크 관리에 유리
  - 비율 기반 지표(BB, RSI, BB bandwidth)는 두 상품 간 전이 가능 확인 완료
  - 미니의 낮은 유동성(F200 대비 1/9~1/42)은 인지하고 수용
- **현재 운용 전략**:
  - **Setup A (gap reversion) + Setup C (volatility breakout)** — primary, paper-only (Phase 5 Gate 3 진입 전까지). `services/decision_engine/`, `services/risk_filter/`, `services/order_router/` 파이프라인. 활성화 게이트는 `docs/runbooks/phase5-verification.md` 참조.
  - **향후**: Williams %R / RSI / MACD 등 명시적 기술 지표 기반 신규 전략 추가 예정 (2026-05-15 운영 결정).
  - **`rl_mppo` — DEPRECATED 2026-05-15** (`enabled: false`, shadow logging 종료). 사유 정정(v4.11): "매 cycle 0 signals → HOLD bias"는 **오독** — 실제 entry action 55%/conf~0.56, "0 signals"는 shadow_mode 설계상 억제. 유효 사유는 **counterfactual EOD-proxy PnL 음수**(5/11–15 9 trades -1.35M) + Setup A/C 채택. 캐시버그 #252와 무관(`get_rl_features` 캐시 없음). 코드 경로(`RLMPPOEntry/RLMPPOExit/rl_model_helpers`)는 retraining 옵션 보존. 상세: master plan v4.11.
- **계약 명세**: `config/execution.yaml ::futures_contract_spec` (multiplier 50_000 KRW/pt, tick 0.02pt, tick_value 1_000 KRW)
- **운용 경로 표준**: `TradingOrchestrator` 경로를 사용한다 (Setup A/C). Phase 5 paradigm은 systemd 단위로 분리 (`kis-decision-engine`, `kis-risk-filter`, `kis-order-router`, `kis-kill-switch`).
- **Phase 5 운영 런북**:
  - `docs/runbooks/futures-paradigm-operations.md` — 일일 운영 체크리스트
  - `docs/runbooks/futures-paradigm-rollback.md` — 비상 롤백 절차
  - `docs/runbooks/phase5-verification.md` — Gate 1–4 검증 게이트
  - `docs/runbooks/futures-legal-review.md` — Gate 2 법무/세무 검토
  - `docs/runbooks/futures-paradigm-failure-modes.md` — Phase 4부터 유지 중인 실패 모드 매트릭스
- **Live-mode 게이트**: `config/futures_live.yaml::enabled` (기본 `false`) + Redis 플래그 `futures:live:suspended`. `shared/execution/live_mode_guard.py` 참조. order_router는 매 시그널 처리 전 두 조건을 검사하고 suspended 면 XACK skip한다.
- **핵심 합의 사항**
  - 진입/청산 방향은 `signal_direction` 기준으로 처리한다.
  - 선물 paper/live 모두 숏 진입 및 숏 청산(BUY to cover)을 지원해야 한다.
  - ~~RL 입력은 학습 스펙과 동일해야 한다(31차원 obs, scaler 적용, code->dict market_data + OHLCV 기반 피처 복원).~~ (RL_mppo DEPRECATED 2026-05-15)
  - 선물 청산은 Setup A/C 전략 자체의 청산 로직을 사용한다. ~~`rl_mppo_exit`~~ DEPRECATED. 규칙 기반 `three_stage`는 주식 전용이다.
  - **Phase 5 Setup A/C 활성화는 Gate 1-3 통과 + 운영자 서면 승인이 선행되어야 한다**. 코드는 사전 작성 완료(PR #142–#149) 상태이며, 실거래 전환 시점에만 `futures_live.enabled: true` + `redis-cli -n 1 del futures:live:suspended` 절차를 거친다.

#### 주식 (Stock)

- Screener 기반 종목 선정 + bb_reversion / opening_volume_surge 전략
- Paper trading 운용 중
- **EOD 전량 청산 금지**: Intraday trading이 아님. 장 마감 시 무조건 전량 청산하지 않는다
- **슬리피지 반영 필수**: 백테스트 및 페이퍼 트레이딩 모두 슬리피지를 반드시 고려한다
- **상승 여력 종목 보유 유지**: 3-Stage Exit(SURVIVAL→BREAKEVEN→MAXIMIZE) 상태가 MAXIMIZE이고 추세가 유효한 종목은 EOD라는 이유만으로 매도하지 않는다. 청산 판단은 전략 시그널 기반이어야 한다

### 핵심 원칙

1. **DRY (Don't Repeat Yourself)**: 중복 코드 절대 금지 → `shared/`에 집중
2. **No Hardcoding**: 모든 값은 YAML 설정 파일에서 로드
3. **Strategy Pattern**: 진입/청산 로직의 완전한 추상화 + 레지스트리
4. **Configuration-Driven**: 코드 수정 없이 설정만으로 전략 변경 가능

---

## 🏗️ 아키텍처 원칙

### 1. 설정 기반 아키텍처 (Configuration-Driven)

**절대 규칙**: 코드에 숫자, 문자열 리터럴 직접 작성 금지

```python
# ❌ 금지
if pnl_pct >= 2.0:
    state = "BREAKEVEN"

# ✅ 권장
if pnl_pct >= self.config.exit.breakeven_threshold:
    state = PositionState.BREAKEVEN
```

### 2. 전략 추상화 계층

진입/청산/포지션 사이징은 **독립적인 컴포넌트**로 분리 → 레지스트리로 조합:

| 추상 클래스 | 역할 | 위치 |
|-----------|------|------|
| `EntrySignalGenerator` | 진입 시그널 생성 | `shared/strategy/base.py` |
| `ExitSignalGenerator` | 청산 시그널 생성 | `shared/strategy/base.py` |
| `PositionSizer` | 포지션 크기 계산 | `shared/strategy/base.py` |
| `TradingStrategy` | 위 3개 조합 (Composition) | `shared/strategy/base.py` |

### 3. 런타임 트레이딩 계층

| 컴포넌트 | 역할 | 위치 |
|---------|------|------|
| `TradingOrchestrator` | 트레이딩 전체 수명주기 및 메인 루프 관리 | `services/trading/orchestrator.py` |
| `StrategyManager` | 다중 전략 관리, 진입/청산 시그널 집계 | `services/trading/strategy_manager.py` |
| `MarketDataProvider` | 시장 데이터 수집/제공 (WebSocket 전용, REST polling 제거됨) | `services/trading/data_provider.py` |
| `IndicatorEngine` | 지표 계산/캐싱 (VWAP, RVOL, volume 가속도 포함) | `services/trading/indicator_engine.py` |
| `PositionTracker` | 포지션 추적 + Redis 기반 재시작 복구 | `services/trading/position_tracker.py` |
| `HolidayCache` | 장 휴일/거래일 캐시 | `services/trading/holiday_cache.py` |
| `TradingPipeline` | 데이터 파이프라인 + Pre-market ClickHouse warmup | `services/trading/pipeline.py` |

#### 운영 대시보드 (Dashboard)

React 프론트엔드 (host port 8001, FastAPI 정적 호스팅) — 실시간 운영 모니터링 단일 화면.
KIS Unified STS의 사용자-facing 웹 포트는 8001뿐이다. host 3000은 별도 `bid-vector` 프로젝트용이므로 이 repo에서 사용하지 않는다. 별도 웹서비스/API가 생기기 전까지 추가 host port를 예약하지 않는다.

- `/` — Cockpit (HeaderBar + Positions + Signals/Fills + Quick Actions)
- `/positions`, `/signals`, `/trades` — drill-down 페이지 (모바일 카드/sheet 패턴)
- **자산군 탭** (선물/주식/통합): URL `?asset=` + localStorage 동기화, 모든 페이지 공통
- **모바일 KILL SWITCH**: slide-to-confirm (90% threshold). STOP 버튼은 데스크탑 전용 (오작동 방지)
- **백테스트/MLflow는 CLI 전용** (UI 제거됨 — Phase 5)
- **레거시 ops 대시보드 제거됨** — 운영 모니터링은 React Cockpit 단일 화면 + Prometheus/Telegram 경로를 사용

설계 + 구현 plan: `docs/superpowers/specs/2026-05-12-dashboard-redesign-design.md`, `docs/superpowers/plans/2026-05-12-dashboard-redesign.md`.

#### RL 선물 운용 규칙 — **DEPRECATED 2026-05-15**

> RL_mppo는 **2026-05-15 deprecate**됨 (`enabled: false`). 사유 정정(v4.11): "매 cycle 0 signals → HOLD bias"는 오독이었고(shadow_mode 설계상 Signal 억제, 실제 entry 55%/conf~0.56), 유효 사유는 counterfactual EOD-proxy PnL 음수 + Setup A/C 채택. 아래 규칙은 retraining/복귀 옵션을 위해 보존하지만 운영 경로에서는 사용하지 않는다. 선물 시그널은 Setup A/C 및 향후 지표 기반(Williams %R / RSI / MACD) 전략으로 처리한다. 상세: `docs/plans/2026-05-03-llm-primary-rl-minimization.md` v4.11.

- ~~`sts rl paper` 명령은 `TradingOrchestrator`를 사용한다.~~ Setup A/C도 동일 orchestrator 경로 사용 (`sts trade start --asset futures`).
- `rl_mppo` 전략의 모델 경로 오버라이드는 `RL_MPPO_MODEL_PATH` 환경변수를 사용한다. (retraining 시 참조용)
- 오케스트레이터는 RL 전략에 대해 `IndicatorEngine`의 최근 분봉(OHLCV)을 주입하여 피처 계산을 보조한다.
- **진입/청산 모두 RL 모델**: entry(`RLMPPOEntry`) + exit(`RLMPPOExit`)가 동일 모델의 5개 액션(LONG_ENTRY=0, LONG_EXIT=1, SHORT_ENTRY=2, SHORT_EXIT=3, HOLD=4)을 사용한다.
- **공유 헬퍼**: `shared/strategy/rl_model_helpers.py` — 모델 캐시, obs 빌더, confidence 계산을 entry/exit이 공유. 모듈 레벨 캐시로 ~50MB 메모리 절약.
- **선물 BEAR regime 면제**: 양방향(long/short) 거래이므로 BEAR regime blocking이 적용되지 않는다.
- **RL 청산 안전장치**: hard stop(-3%) + EOD close(15:15)가 모델 예측보다 우선한다.
- **데이터 정책(고정)**: RL 학습/평가는 `kospi200f_1m`의 `101S6000`(KOSPI200 선물 연결선물) 기준으로 수행하고, 실거래 종목은 KOSPI200 mini 근월물(`A05xxx`, 자동 감지)로 운용한다.

#### 계층적 RL (Hierarchical RL)

**아키텍처**: 전문 트레이더처럼 멀티 타임프레임 의사결정 — 상위 타임프레임에서 전략 방향, 하위 타임프레임에서 정밀 실행.

- **High-level Agent (15분봉)**: 시장 상태 분석 → 전략 방향 설정
- **Low-level Agent (1분봉)**: High-level의 방향 제약 하에 정밀 진입/청산 실행

**운용 모드 (2가지)**:

| 모드 | High-level 출력 | Low-level 제약 | 용도 |
|------|----------------|---------------|------|
| `risk_budget` | AGGRESSIVE / NEUTRAL / DEFENSIVE | 포지션 크기 제약 | 리스크 관리 기반 운용 |
| `directional` | LONG_BIAS / SHORT_BIAS / FLAT | 진입 방향 제약 (action mask) | 트렌드 추종/역추세 전략 |

**Directional Mode 동작**:

- `LONG_BIAS` → Low-level의 SHORT_ENTRY 차단 (롱 진입만 허용)
- `SHORT_BIAS` → Low-level의 LONG_ENTRY 차단 (숏 진입만 허용)
- `FLAT` → 양방향 진입 모두 허용 (관망 모드)

**학습 전략 (2가지)**:

| 전략 | 방법 | 장점 | 단점 |
|------|------|------|------|
| `sequential` | Low-level 완전 학습 → High-level 학습 | 안정적, 디버깅 용이 | 시간 소요 큼 |
| `joint` | High/Low-level 동시 학습, 교대 업데이트 (15:1 비율) | 빠른 수렴, 긴밀한 협력 | 학습 불안정 가능 |

**CLI 명령어**:

```bash
# 학습 - Directional mode, Sequential training (권장)
sts rl train-hierarchical --mode directional --training sequential

# 학습 - Risk budget mode, Joint training
sts rl train-hierarchical --mode risk_budget --training joint

# 평가 - Hierarchical vs Flat RL 비교
sts rl evaluate-hierarchical

# 평가 - Joint 학습 모델 비교
sts rl evaluate-hierarchical \
    --high-model hierarchical/high_level_joint \
    --low-model hierarchical/low_level_joint
```

**성능 기대치**:

- Sharpe ratio 향상: flat rl_mppo 대비 10-30% 개선 예상
- 승률 개선: 멀티 타임프레임 필터링으로 거짓 신호 감소
- 레이턴시 제약: 추론 시간 p99 < 60초 (1분봉 제약 준수)

**구현 위치**:

- `shared/ml/rl/hierarchical/` — High-level env, Low-level env, Trainer, Evaluator
- `config/ml/rl_mppo.yaml` — `hierarchical` 섹션 (directional_bias, training_mode, joint_timesteps)
- `tests/unit/ml/rl/test_hierarchical*.py` — 포괄적 테스트 (51개 테스트 메서드)

---

## 📁 디렉토리 구조

```
kis-unified-trading/
├── CLAUDE.md                        # 이 파일
├── pyproject.toml                   # 프로젝트 설정
├── docker-compose.yml / .dev.yml    # Docker 오케스트레이션
│
- **C1: Look-ahead Bias 방지**: 모든 시계열/배열 데이터는 반드시 현재 context.timestamp 이하만 참조해야 하며, 미래 데이터(look-ahead bias) 참조 시 경고 또는 실패 처리된다. 백테스트/최적화 시에는 LookaheadGuard가 강제 적용되며, 엔진/지표/전략 컨텍스트는 아래와 같이 사용한다.

  - 구현: `shared/backtest/lookahead_guard.py` (`LookaheadGuard`)
  - 설정: `BacktestConfig.lookahead_guard_mode` (off/warn/assert, 기본 assert)
  - wiring: `BacktestEngine`, `IndicatorEngine`, 모든 주요 indicator/지표 계산 함수
  - 테스트: `tests/unit/backtest/test_lookahead_guard.py` (미래 데이터 참조 시 경고/실패 검증)
  - 사용 예시:
    ```python
    # 지표/엔진 내부
    lookahead_guard.check(arr, timestamps, ctx.timestamp, context_info="SMA")
    # 타임스탬프 없는 배열은 check_fingerprint 사용
    lookahead_guard.check_fingerprint(arr, prev_fp, context_info="custom_array")
    ```
  - 스펙: "C1: Look-ahead bias 방지" (모든 전략/지표/엔진은 미래 데이터 참조 금지, 위반 시 경고 또는 실패)

│   ├── monitoring.yaml, market_schedule.yaml
│   ├── strategies/                  # 전략별 설정
│   │   ├── stock/                   # bb_reversion, opening_volume_surge, volume_accumulation
│   │   └── futures/                 # bb_reversion_15m (WF backup), rl_mppo
│   ├── exit/                        # 청산: three_stage (주식), rl_mppo_exit (선물)
│   ├── kis/                         # KIS API 인증
│   └── ml/                          # ML 모델: rl_mppo
│
├── shared/                          # 📁 공유 모듈 (핵심)
│   ├── config/                      # ConfigLoader + Pydantic 스키마
│   ├── strategy/                    # 전략 프레임워크
│   │   ├── base.py                  # ABC 정의
│   │   ├── registry.py              # 레지스트리 + StrategyFactory
│   │   ├── rl_model_helpers.py      # RL entry/exit 공유 로직 (모델 캐시, obs 빌더)
│   │   ├── entry/                   # 진입 전략 7개
│   │   ├── exit/                    # 청산 전략 4개 (three_stage, momentum_decay, rl_mppo_exit, trix_golden_exit)
│   │   └── position/sizers.py       # 포지션 사이저
│   ├── backtest/                    # 백테스트 엔진 + MLflow + Optuna
│   ├── models/                      # Signal, Position, ExitReason 등
│   ├── indicators/                  # 기술적 지표 (technical, orderbook, volume, composite)
│   ├── llm/                         # LLM 시장 분석 (14개 모듈)
│   ├── ml/rl/                       # RL 구현
│   │   ├── hierarchical/            # 계층적 RL (High-level 15m + Low-level 1m)
│   │   ├── env.py                   # Flat RL 환경
│   │   ├── trainer.py               # RL 학습기
│   │   └── evaluator.py             # RL 평가기
│   ├── paper/                       # 모의투자 엔진
│   ├── kis/                         # KIS API 어댑터
│   ├── notification/telegram.py     # Telegram 알림
│   ├── resilience/                  # circuit_breaker, retry
│   ├── streaming/                   # 실시간 스트리밍
│   ├── execution/                   # 주문 실행
│   └── ensemble/                    # 앙상블 모델
│
├── domains/                         # 📁 도메인별 구현 (대부분 shared/로 수렴)
│   ├── stock/                       # strategies/ 비어있음 → shared/ 사용
│   └── futures/
│       └── strategies/              # (레거시 코드 삭제됨, RL은 shared/ml/rl/)
│
├── services/                        # 📁 애플리케이션 서비스
│   ├── trading/                     # 런타임 트레이딩 엔진 (7개 모듈)
│   ├── backtest/, dashboard/, monitoring/
│
├── cli/main.py                      # Click 기반 CLI (~1700 lines)
│
├── scripts/analysis/                # LLM 분석 cron 스크립트
└── tests/
```

---

## 🔧 핵심 구현 패턴

### 전략 레지스트리 패턴

`shared/strategy/registry.py`에 `ComponentRegistry` → `EntryRegistry` / `ExitRegistry` / `SizerRegistry` + `StrategyFactory`가 모두 포함.

- 데코레이터 등록: `@EntryRegistry.register("name")` 또는 `register_builtin_components()`에서 일괄 등록
- 팩토리 생성: `StrategyFactory.create_from_file("stock", "bb_reversion")`
- `CONFIG_CLASS` 속성으로 params dict → 타입 config 자동 변환

### 등록된 진입 전략

| 등록명 | 클래스 | 설명 |
|--------|--------|------|
| `mean_reversion` | `MeanReversionEntry` | BB + RSI + MACD 필터 |
| `breakout` | `BreakoutEntry` | 브레이크아웃 |
| `opening_volume_surge` | `OpeningVolumeSurgeEntry` | 장 초반 거래량 폭증 |
| `stochrsi_trend` | `StochRSITrendEntry` | StochRSI 추세 |
| `volume_accumulation` | `VolumeAccumulationBreakoutEntry` | 거래량 축적 기반 돌파 |
| `trix_golden` | `TrixGoldenEntry` | TRIX 5분봉 황금신호 |
| `rl_mppo` | `RLMPPOEntry` | RL Maskable PPO 진입 (선물) |
| `llm_directed_indicator` | `LLMDirectedIndicatorEntry` | **DEPRECATED 2026-05-17** — LLM 주기 방향 마스크 + 3지표군 앙상블 (선물). 평가 완료: 강건한 단독 엣지 없음, 재정의된 §6 게이트 FAIL. `enabled=false` 영구, 튜닝 파라미터 미적용. 사유: spec §8 + `reports/optuna/FINDINGS.md` (PR #320). 코드는 참조용 보존, 활성화 경로 아님 |

### 등록된 청산 전략

| 등록명 | 클래스 | 설명 |
|--------|--------|------|
| `three_stage` | `ThreeStageExit` | SURVIVAL→BREAKEVEN→MAXIMIZE 상태 머신 (주식) |
| `momentum_decay` | `MomentumDecayExit` | 모멘텀 소진 기반 스윙 청산 |
| `rl_mppo_exit` | `RLMPPOExit` | RL 학습된 청산 정책 (선물) — hard stop + EOD 안전장치 |
| `trix_golden_exit` | `TrixGoldenExit` | TRIX 5분봉 황금신호 청산 |
| `llm_directed_indicator_exit` | `LLMDirectedIndicatorExit` | **DEPRECATED 2026-05-17** — ATR-dynamic + momentum_decay 합성 (선물). `llm_directed_indicator` 진입과 함께 deprecate (spec §8) |

### 설정 파일 구조

전략 YAML 파일은 `strategy.entry.type`으로 레지스트리 이름을 참조:

```yaml
strategy:
  name: bb_reversion
  asset_class: stock
  enabled: true
  entry:
    type: mean_reversion      # ← EntryRegistry에 등록된 이름
    params: { ... }
  exit:
    type: three_stage          # ← ExitRegistry에 등록된 이름
    params: { ... }
  position:
    type: fixed                # ← SizerRegistry에 등록된 이름
    params: { ... }
```

### ServiceConfigBase 패턴

**모든 서비스 설정은 `ServiceConfigBase`를 상속한다** — 중복 코드 제거 및 일관성 보장.

`shared/config/base.py` — Pydantic BaseModel 기반 통합 설정 베이스 클래스.

**핵심 기능:**

- `from_yaml()`: YAML 파일에서 로드 (ConfigLoader 통합, 섹션 추출 지원)
- `from_env()`: 환경변수에서 로드 (prefix 매핑, 타입 자동 변환)
- 환경변수 우선순위: YAML + env override 조합 가능
- 데이터베이스 이름 검증: SQL injection 자동 방지 (alphanumeric + underscore만 허용)

**사용 예시:**

```python
from pydantic import Field
from shared.config.base import ServiceConfigBase

class MyServiceConfig(ServiceConfigBase):
    _default_config_file: ClassVar[str] = "my_service.yaml"
    _env_prefix: ClassVar[str] = "MY_SERVICE_"

    threshold: float = Field(default=0.5, description="Detection threshold")
    enabled: bool = Field(default=True, description="Service enabled")
    database: str = Field(default="market", description="Database name")

# YAML에서 로드
config = MyServiceConfig.from_yaml()

# 환경변수에서 로드
config = MyServiceConfig.from_env()  # MY_SERVICE_THRESHOLD, MY_SERVICE_ENABLED

# YAML + 환경변수 오버라이드
config = MyServiceConfig.from_yaml(apply_env_overrides=True)
```

**마이그레이션 완료:** 7개 서비스 설정이 ServiceConfigBase 사용 (DailyScannerConfig, FusionRankerConfig, TelegramConfig, TickStreamPublisherConfig, LLMConfig, ScreenerConfig, ClickHouseConfig) — ~385줄 boilerplate 제거.

**상세 문서:** `docs/config_patterns.md` — 고급 패턴, 마이그레이션 가이드, 테스트 예시 포함.

### ConfigLoader

`shared/config/loader.py` — 싱글톤, 스레드 안전, `${VAR_NAME}` / `${VAR_NAME:default}` 환경변수 해석, 경로 순회 보호, 캐싱.

주요 메서드:

- `ConfigLoader.load(path, schema=None)` → dict 또는 Pydantic 모델
- `ConfigLoader.load_strategy(asset_class, strategy_name)` → 전략 설정 dict
- `ConfigLoader.load_all_strategies(asset_class=None)` → 활성 전략 목록

### MarketClassifier

`shared/strategy/market_classifier.py` — MFI/ADX 기반 시장 상태 분류기.
`ThreeStageExit` 및 오케스트레이터에서 사용.

### 데이터 피드 아키텍처

- **WebSocket 전용**: REST polling 제거됨. 주식(`H0STCNT0`), 선물(`H0IFASP0`) 모두 WebSocket으로 실시간 수신.
- **Pre-market ClickHouse warmup**: 장 시작 전 ClickHouse에서 최근 분봉을 로드하여 지표 웜업 시간 단축.
- **Redis 기반 포지션 복구**: 프로세스 재시작 시 `trading:{asset}:positions` Redis 키에서 오픈 포지션을 복원.
- **Redis DB 1 전용**: DB 0은 다른 프로젝트가 사용. 모든 Redis 접속은 DB 1을 명시해야 한다.
- **Graceful shutdown**: CLI에서 SIGTERM/SIGINT → `orchestrator.stop(timeout=10s)` → Redis force flush. Cron은 SIGTERM → 5초 대기 → `kill -0` 확인 → SIGKILL.
- **KIS Rate Limiter**: `_RateLimiter`는 EGW00201 시 exponential backoff (cap 30s). 10회 consecutive 후 5분 cooldown auto-reset으로 death spiral 방지.

### ATS Routing (Korean Alternative Trading System)

**개요**: 2025년 3월 출범한 한국 대체거래소(넥스트레이드) 지원. 주식 주문을 KRX와 ATS 간 최적 실행 경로로 라우팅하여 가격 개선 기회 및 유동성 확보.

**핵심 컴포넌트**:

| 컴포넌트 | 역할 | 위치 |
|---------|------|------|
| `VenueRouter` | KRX vs ATS 실행 거래소 선택 로직 | `shared/execution/venue_router.py` |
| `ATSRoutingConfig` | 라우팅 규칙 설정 (Pydantic 모델) | `shared/execution/config.py` |
| `OrderExecutor` | 거래소별 주문 실행 (KIS API 라우팅) | `shared/execution/executor.py` |
| `ATSSimulator` | 백테스트용 ATS 시뮬레이션 | `shared/backtest/ats_simulator.py` |

**라우팅 규칙 (6가지)**:

1. **가격 개선 임계값** (`price_improvement_threshold_bps`): ATS 선택을 위한 최소 가격 개선 (기본값: 5 bps = 0.05%)
2. **유동성 요구사항** (`min_liquidity_depth`, `min_depth_multiplier`): 최소 호가 잔량 및 주문 크기 대비 배수 검증
3. **스프레드 제한** (`max_spread_bps`, `spread_comparison_enabled`): ATS 사용 최대 스프레드 및 KRX 대비 비교
4. **체결 확률 모델** (`ats_fill_rate_threshold`): 최소 체결 확률 기반 필터링 (기본값: 70%)
5. **시간대별 선호도** (`time_of_day_preferences`): 장 초반/마감 시 KRX 선호, 중간 시간대 자동 라우팅
6. **종목 필터** (`min_market_cap`, `excluded_sectors`): 최소 시가총액 및 섹터 제외 기준

**운용 정책**:

- **주식 전용**: 선물은 ATS 미지원 (KRX only)
- **기본값 비활성화**: `config/execution.yaml`에서 `ats_routing.enabled: false` (opt-in)
- **거래소 추적**: 모든 주문의 실행 거래소(`execution_venue`)를 ClickHouse에 기록 (`rl_trades`, `swing_positions`)
- **백테스트 시뮬레이션**: ATS는 평균 3 bps 가격 개선, 65% 체결률로 모델링 (KRX 대비)
- **모니터링**: React Cockpit 및 ClickHouse/Prometheus 지표에서 거래소별 분포 및 가격 개선 추적

**설정 예시** (`config/execution.yaml`):

```yaml
ats_routing:
  enabled: false                             # 기본값: 비활성
  default_venue: KRX                         # 기본 실행 거래소
  price_improvement_threshold_bps: 5.0       # 최소 가격 개선 (5 bps)
  min_liquidity_depth: 100.0                 # 최소 호가 잔량
  min_depth_multiplier: 2.0                  # 주문 크기 대비 최소 잔량 배수
  max_spread_bps: 30.0                       # ATS 사용 최대 스프레드
  ats_fill_rate_threshold: 0.7               # 최소 체결 확률 (70%)
  time_of_day_preferences:
    "09:00-09:30": KRX                       # 장 초반: KRX 선호
    "09:30-15:00": AUTO                      # 중간: 자동 라우팅
    "15:00-15:30": KRX                       # 장 마감: KRX 선호
  min_market_cap: 1000000000000              # 최소 시가총액 (1조원)
```

**CLI 사용법**:

```bash
# ATS 활성화하여 백테스트 실행
sts backtest run --strategy bb_reversion --asset stock --data ./data.csv --ats-enabled

# ATS 활성화하여 모의투자 실행 (config/execution.yaml에서 enabled: true 설정 후)
sts paper start --strategy bb_reversion --asset stock
```

### 3-Stage Exit 상태 머신

`shared/strategy/exit/three_stage.py` — `ThreeStageExit` + `ThreeStageExitConfig`

1. **SURVIVAL** — Hard stop loss 보호
2. **BREAKEVEN** — 임계 수익 도달 시 본전 스탑 설정
3. **MAXIMIZE** — 트레일링 스탑 (동적 폭: 일반/타이트)

### 백테스트 & MLflow

- `shared/backtest/engine.py` — 이벤트 루프 기반 백테스트 엔진
- `shared/backtest/mlflow_tracker.py` — MLflow 통합 (선택적 의존성)
- `shared/backtest/optimizer.py` — Optuna 기반 파라미터 최적화

---

## 📈 LLM 시장 분석 모듈

`shared/llm/` — KRX Open API + OpenAI 기반 통합 시장 분석 (14개 모듈)

| 컴포넌트 | 설명 |
|---------|------|
| `LLMConfig` | YAML/환경변수 기반 설정 (`config/llm.yaml`) |
| `KRXOpenAPIClient` | KRX Open API 클라이언트 (지수/ETF/선물/옵션/채권) |
| `UnifiedMarketAnalyzer` | 통합 시장 분석 오케스트레이터 |
| `LLMAnalyzer` / `UnifiedTradingAnalyzer` | LLM 기반 종목 분석 |
| `ETFFlowAnalyzer` / `FuturesAnalyzer` / `OptionsAnalyzer` | 시장별 분석기 |

공개 API: `run_unified_analysis()`, `get_stock_detail_briefing()`

### Cron 스크립트

| 스크립트 | 시간 | 설명 |
|--------|------|------|
| `scripts/analysis/llm_nightly_analysis.py` | 21:00 | 익일 트레이딩 분석 |
| `scripts/llm_premarket_briefing.py` | 06:30 | 장전 최종 브리핑 (분석 ~1.5h, 08:00–08:30 완료) |
| `scripts/analysis/llm_market_close_briefing.py` | 15:30 | 장 마감 요약 |

---

## 🤖 에이전트 하네스 (멀티 에이전트 팀)

도메인 전문 에이전트 팀이 `.claude/agents/`(24개 정의)와 `.claude/skills/`(오케스트레이터 6개)에 정의되어 있다. 진입점은 `trading-harness` 스킬(전문가 풀 라우터)이며, 요청 키워드로 적절한 에이전트/파이프라인에 위임한다.

| 팀 | 에이전트 |
|----|---------|
| 전략 개발 | `strategy-architect`, `indicator-specialist`, `regime-gate-analyst`, `strategy-builder`, `backtest-engineer` |
| 전략/모델 승격 | `model-evaluator`, `model-deployer` |
| 코드 유지보수 | `code-reviewer`, `test-engineer`, `refactorer` |
| 운영/모니터링 | `ops-monitor`, `incident-responder`, `alert-manager` |
| 데이터·실행·분석 | `data-engineer`(수집/백필/품질), `execution-specialist`(주문/KIS/ATS), `llm-analyst`(LLM 분석 **콘텐츠**) |
| 종합 코드 감사 | `architecture-auditor`, `security-auditor`, `performance-auditor`, `style-auditor`, `review-synthesizer` |
| 프론트엔드 (Next.js 단일 앱) | `frontend-architect`, `ui-engineer`, `frontend-realtime-engineer` |

**오케스트레이터 스킬**:

- `trading-harness` — 전체 라우터 (전문가 풀)
- `strategy-lab` — 1차 전략 개발 파이프라인 (설계→백테스트→게이트→평가→승격)
- `ops-harness` — 운영/모니터링
- `code-audit` — 종합 코드 감사 (아키텍처·보안·성능·스타일 4개 감사관 **병렬** → `review-synthesizer` **통합 리포트**)
- `frontend-lab` — Next.js 단일 앱(`strategy-builder-ui/`) 화면/기능 개발
- `rl-pipeline` — **DEPRECATED** (RL 재학습 전용, 운영 경로 아님)

상세 역할/트리거/협업은 각 `.claude/agents/*.md` 및 `.claude/skills/*/skill.md` 참조. 새 에이전트/스킬은 `harness` 메타 스킬로 생성·점검한다.

---

## ⚠️ 개발 규칙

### 0. 브랜치 워크플로우 필수

**main 브랜치에 직접 커밋 금지.** 모든 작업은 feature branch를 생성한 후 진행하고, PR을 통해 main에 머지한다.

```bash
# 작업 시작
git checkout -b feat/작업-설명

# 작업 완료 후
git push -u origin feat/작업-설명
gh pr create --title "..." --body "..."
```

### 1. 하드코딩 금지

모든 임계값, 기간, 비율은 YAML config에서 로드. 코드에 매직넘버 절대 금지.

### 2. 중복 코드 금지

공통 로직은 반드시 `shared/` 모듈로 추출. `domains/`간 동일 로직 반복 금지.

### 3. 새 전략 추가 절차

1. `config/strategies/{asset}/{name}.yaml` 작성
2. 필요시 새 Entry/Exit 클래스 구현 (`shared/strategy/entry/` 또는 `exit/`)
3. 레지스트리에 등록 (`@EntryRegistry.register("name")` 또는 `register_builtin_components()`에 추가)
4. 테스트 작성
5. **설정 파일의 `enabled: true`로 활성화 — 추가 코드 수정 불필요**

### 4. 테스트 필수

모든 PR 전 `.venv/bin/pytest tests/ -v` 실행 (시스템 pytest 아님 — **venv 필수**).

**CI 인프라 & 테스트 안정성 (2026-05-30 정리, `.github/workflows/test.yml`):**

- **CI는 Redis(6379) + ClickHouse(native 9000) 서비스를 띄운다.** 인프라에 접속하는 테스트는 CI에서 실제로 연결된다. ClickHouse 이미지는 **빈 비밀번호 `default` 로그인을 거부(`Code 516`)**하므로 CI는 `CLICKHOUSE_PASSWORD`를 서비스/클라이언트 양쪽에 설정한다.
- **선택적 의존성 import는 가드한다.** 모듈 레벨 `import optuna`(또는 다른 optional extra)는 collection 단계에서 `ModuleNotFoundError`를 던져 **전체 스위트를 abort**(exit 2)시킨다 → `main()` 내부 lazy import 또는 `pytest.importorskip("...")`를 사용한다.
- **싱글톤은 conftest에서 리셋한다.** `ClickHouseClient`/`ConfigLoader`는 **첫 config로 고정되는 싱글톤**이라 cross-test 오염을 일으킨다(격리 실행은 통과, 풀 스위트는 실패). `tests/conftest.py`의 autouse fixture가 매 테스트 후 리셋한다 (`ClickHouseClient.reset_singleton()` 등).
- **성능 회귀 체크** (`scripts/performance/check_regression.py`)는 baseline 대비 wall-clock 비교다. baseline(`tests/performance/baselines.json`)은 **CI와 동일 하드웨어(ubuntu-latest)에서 재생성**해야 하며(다른 하드웨어 baseline은 false regression 유발), 러너 variance를 위해 `--min-duration 0.05`(50ms 미만 면제) + `--error-threshold 2.0`(≥2배만 실패) + warning non-fatal로 운용한다.

### 5. 타임존 규칙 — KST 필수

**`context.timestamp`는 UTC-aware (`datetime.now(UTC)`)이다** (PR #159 이후). 시간 필터를 비교하기 전에 반드시 KST로 변환해야 한다.

```python
# ❌ 금지 — UTC 시각을 한국 장시간 설정과 직접 비교
if now < datetime.combine(now.date(), time(9, 0), tzinfo=now.tzinfo):
    return None  # 09:00 UTC = 18:00 KST → 한국 장중에 항상 차단됨

# ✅ 권장 — KST로 변환 후 비교
from zoneinfo import ZoneInfo
_KST = ZoneInfo("Asia/Seoul")

now_kst = now.astimezone(_KST) if now.tzinfo is not None else now.replace(tzinfo=_KST)
open_dt = datetime.combine(now_kst.date(), time(9, 0), tzinfo=_KST)
if now_kst < open_dt:
    return None
```

**한국 장시간**: 09:00–15:30 KST = **00:00–06:30 UTC**. UTC 기준 `time(9, 0)`은 18:00 KST로 장 종료 후이므로 장중 진입이 전부 차단된다.

레퍼런스 구현: `shared/strategy/entry/opening_volume_surge.py`, `shared/strategy/entry/momentum_breakout.py`

#### Cron entries: 항상 KST native로 작성

운영 서버 crontab은 `CRON_TZ=Asia/Seoul`이 선언되어 있어 모든 entry가 **KST로 해석된다**. UTC 시각을 그대로 쓰면 9시간 어긋난다.

```cron
# ❌ 금지 — UTC를 KST로 해석되는 환경에 그대로 쓰기
55 23 * * 0-4   # 의도: Sun-Thu 23:55 UTC = Mon-Fri 08:55 KST
                # 실제: Sun-Thu 23:55 KST (전혀 다른 시점)

# ✅ 권장 — KST native
55 8 * * 1-5    # 08:55 KST Mon-Fri (장 시작 5분 전)
2-57/5 9-15 * * 1-5   # 매 5분 09:00-15:55 KST (장중)
0 18 * * 0      # Sun 18:00 KST (주간 다이제스트)
```

**확인 방법**: `crontab -l | grep CRON_TZ` — `Asia/Seoul` 선언이 있는 줄 아래의 entry는 KST. 한국 시장만 거래하는 이 프로젝트에서는 KST가 canonical이며 `CRON_TZ=UTC`로 바꾸지 않는다.

---

## 📝 코드 스타일

- Python 3.11+, Type hints 필수, Docstring (Google style)
- `black .` + `ruff check --fix .` + `mypy shared/ domains/`
- `pytest tests/ -v --cov=shared`

---

## 🔑 환경 변수

| 변수 | 용도 |
|------|------|
| `KIS_STOCK_APP_KEY`, `KIS_STOCK_APP_SECRET`, `KIS_STOCK_ACCOUNT_NO` | 주식 KIS API 인증 |
| `KIS_FUTURES_APP_KEY`, `KIS_FUTURES_APP_SECRET`, `KIS_FUTURES_ACCOUNT_NO` | 선물 KIS API 인증 |
| `KIS_STOCK_MARKET`, `KIS_FUTURES_MARKET` | 실전/모의 설정 (`real`/`mock`) |
| `KIS_CONFIG_DIR` | 설정 디렉토리 오버라이드 |
| `CLICKHOUSE_*`, `REDIS_*`, `MLFLOW_TRACKING_URI` | 인프라 설정 |
| `OPENAI_API_KEY`, `KRX_API_KEY`, `DART_API_KEY` | LLM/데이터 API |
| `TELEGRAM_STOCK_*`, `TELEGRAM_FUTURES_*`, `TELEGRAM_BRIEFING_*` | Telegram 알림 |
| `API_KEY`, `PROMETHEUS_PORT` | API/모니터링 |
| `KIS_APP_KEY`, `KIS_APP_SECRET` | 레거시 단일 계좌 호환 |

Config YAML에서 `${VAR_NAME}` / `${VAR_NAME:default}` 문법으로 참조 가능.

---

## 🚀 CLI 명령어

```bash
# 백테스트
sts backtest run --strategy bb_reversion --asset stock --data ./data.csv
sts backtest best --strategy bb_reversion --asset stock
sts backtest list --asset stock

# 파라미터 최적화
sts optimize --strategy bb_reversion --asset stock --data ./data.csv --trials 100

# MLflow
sts mlflow ui
sts mlflow list

# 수집/백필
sts collect start -s 005930
sts backfill today
sts stock-backfill run --days 7

# 트레이딩/모의
sts trade start --strategy bb_reversion --asset stock --paper
sts paper start --strategy bb_reversion --asset stock

# RL
sts rl train --algo mppo
sts rl evaluate --model mppo_best

# 계층적 RL (Hierarchical RL)
sts rl train-hierarchical --mode directional --training sequential
sts rl train-hierarchical --mode risk_budget --training joint
sts rl evaluate-hierarchical
sts rl evaluate-hierarchical --high-model hierarchical/high_level_joint --low-model hierarchical/low_level_joint

# 포맷팅 & 테스트
black . && ruff check --fix .
pytest tests/ -v --cov=shared
```
