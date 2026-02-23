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
- **현재 운용 전략**: `rl_mppo` (Maskable PPO, long/short intraday)
- **운용 경로 표준**: `TradingOrchestrator` 경로를 기본으로 사용한다. `shared/ml/rl/paper_trader.py`는 레거시/검증용 보조 경로다.
- **핵심 합의 사항**
  - 진입/청산 방향은 `signal_direction` 기준으로 처리한다.
  - 선물 paper/live 모두 숏 진입 및 숏 청산(BUY to cover)을 지원해야 한다.
  - RL 입력은 학습 스펙과 동일해야 한다(31차원 obs, scaler 적용, code->dict market_data + OHLCV 기반 피처 복원).
  - 선물 청산은 **학습된 RL 정책**(`rl_mppo_exit`)을 사용한다. 규칙 기반 `three_stage`는 주식 전용이다.

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

#### RL 선물 운용 규칙

- `sts rl paper` 기본 엔진은 `orchestrator`다. 레거시 엔진은 `--engine legacy`로만 사용한다.
- `rl_mppo` 전략의 모델 경로 오버라이드는 `RL_MPPO_MODEL_PATH` 환경변수를 사용한다.
- 오케스트레이터는 RL 전략에 대해 `IndicatorEngine`의 최근 분봉(OHLCV)을 주입하여 피처 계산을 보조한다.
- **진입/청산 모두 RL 모델**: entry(`RLMPPOEntry`) + exit(`RLMPPOExit`)가 동일 모델의 5개 액션(LONG_ENTRY=0, LONG_EXIT=1, SHORT_ENTRY=2, SHORT_EXIT=3, HOLD=4)을 사용한다.
- **공유 헬퍼**: `shared/strategy/rl_model_helpers.py` — 모델 캐시, obs 빌더, confidence 계산을 entry/exit이 공유. 모듈 레벨 캐시로 ~50MB 메모리 절약.
- **선물 BEAR regime 면제**: 양방향(long/short) 거래이므로 BEAR regime blocking이 적용되지 않는다.
- **RL 청산 안전장치**: hard stop(-3%) + EOD close(15:15)가 모델 예측보다 우선한다.

---

## 📁 디렉토리 구조

```
kis-unified-trading/
├── CLAUDE.md                        # 이 파일
├── pyproject.toml                   # 프로젝트 설정
├── docker-compose.yml / .dev.yml    # Docker 오케스트레이션
│
├── config/                          # 📁 모든 설정 파일 (YAML)
│   ├── api.yaml, llm.yaml, streaming.yaml, execution.yaml
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

### 등록된 청산 전략

| 등록명 | 클래스 | 설명 |
|--------|--------|------|
| `three_stage` | `ThreeStageExit` | SURVIVAL→BREAKEVEN→MAXIMIZE 상태 머신 (주식) |
| `momentum_decay` | `MomentumDecayExit` | 모멘텀 소진 기반 스윙 청산 |
| `rl_mppo_exit` | `RLMPPOExit` | RL 학습된 청산 정책 (선물) — hard stop + EOD 안전장치 |
| `trix_golden_exit` | `TrixGoldenExit` | TRIX 5분봉 황금신호 청산 |

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
| `scripts/analysis/llm_premarket_briefing.py` | 08:30 | 장전 최종 브리핑 |
| `scripts/analysis/llm_market_close_briefing.py` | 15:30 | 장 마감 요약 |

---

## ⚠️ 개발 규칙

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

모든 PR 전 `pytest tests/ -v` 실행.

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
| `API_KEY`, `GRAFANA_*`, `PROMETHEUS_PORT` | API/모니터링 |
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

# 포맷팅 & 테스트
black . && ruff check --fix .
pytest tests/ -v --cov=shared
```
