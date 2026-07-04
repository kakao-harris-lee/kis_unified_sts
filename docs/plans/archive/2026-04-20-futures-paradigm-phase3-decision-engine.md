# Phase 3 — Decision Engine (Week 5)

**Status:** Draft
**Parent:** `docs/plans/archive/2026-04-20-futures-paradigm-master.md` (archived 2026-06-20)
**Target branch:** `feat/futures-paradigm-phase3`
**Depends on:** Phase 1, Phase 2 완료 게이트 통과
**Blocks:** Phase 4

---

## 1. 목표

규칙 기반 진입 시그널 2종(Setup A 갭 리버전 + Setup C 이벤트 리액션) + 다층 리스크 필터 + 계약 정확한 포지션 사이저를 구현한다.

**Phase 3 완료 시:** 시스템이 `signal.candidate` → `signal.final` 파이프라인을 돌리며 `signals_all` 테이블에 채움. **주문 전송은 Phase 4.** 백테스트로 EV 검증만 수행.

**Setup B (외국인 수급)는 Q1-D 결정으로 전면 drop.** 본 spec에 등장하지 않는다.

**완료 정의:**
- Setup A + C 엔진 구현 + 단위 테스트 커버 ≥ 90%
- RiskFilterLayer 8개 필터 구현
- 계약 명세 기반 fixed-fractional 포지션 사이저
- 과거 6개월 백테스트: Setup당 ≥ 30 trades, EV > 0.5 tick
- Walk-Forward Analysis: OOS 성능이 IS의 50% 이상
- `signals_all` 테이블 채움 시작 (executed=0, 백테스트 전용)

---

## 2. 시그널 파이프라인

```
┌──────────────┐    ┌────────────────┐    ┌────────────────┐    ┌──────────────────┐
│ MarketContext│ →  │SignalGenerator │ →  │RiskFilterLayer │ →  │signal.final      │
│ (live data)  │    │ Setup A / C    │    │  8 filters     │    │ (Phase 4 consumes)│
└──────────────┘    └────────────────┘    └────────────────┘    └──────────────────┘
                           ↓                      ↓
                   signal.candidate       signal.rejected (log)
                   (XADD + CH)            (CH: skip_reason)
```

- **생성:** Setup 엔진은 `Signal` 후보를 `stream:signal.candidate`로 발행
- **필터:** `RiskFilterLayer`가 consumer group으로 읽어 pass/reject 결정
- **최종:** pass면 `stream:signal.final`로 발행, 양쪽 다 `signals_all`에 기록 (executed=0)

**이 구조의 이점:** 필터 로직 장애가 시그널 생성을 막지 않고, 과거 시그널을 필터만 리플레이해 튜닝 가능.

---

## 3. MarketContext — 시그널 엔진의 입력

### 3.1 구성

```python
@dataclass
class MarketContext:
    now: datetime                        # KST
    symbol: str                          # "A05603" 등 미니 front-month
    current_price: float
    prev_close: float
    today_open: float
    vwap: float
    atr_14: float
    atr_90th_percentile: float           # 최근 60일 분포 (백테스트 웜업)
    last_15min_high: float
    last_15min_low: float
    current_spread_ticks: float
    macro_overnight: MacroSnapshot | None    # stream:macro.overnight 최신
    scheduled_events: list[ScheduledEvent]   # 최근/예정 매크로 이벤트 (Setup C)
```

### 3.2 소스

- `current_price`, OHLCV: 기존 `IndicatorEngine` (orchestrator가 보유)
- `vwap`, `atr_14`: 기존 `shared/indicators/` 재사용
- `atr_90th_percentile`: Phase 3 신규 — 60일 rolling (startup 시 ClickHouse에서 로드)
- `macro_overnight`: `stream:macro.overnight` consumer or Redis `macro:latest` 캐시
- `scheduled_events`: 신규 `config/scheduled_events.yaml` + Phase 3 간단 cron (FOMC/CPI/NFP 일정 하드코딩 방식 지양 → YAML 기반)

### 3.3 `scheduled_events.yaml` 스키마

```yaml
events:
  - event_id: "fomc_2026_may"
    event_type: "FOMC_rate_decision"
    scheduled_at: "2026-05-01T03:00:00Z"   # UTC, KST 12:00
    impact_tier: 1                          # 1=top tier, 3=minor
  - event_id: "us_cpi_2026_05"
    event_type: "US_CPI"
    scheduled_at: "2026-05-13T12:30:00Z"
    impact_tier: 1
  - event_id: "bok_2026_may"
    event_type: "BOK_rate_decision"
    scheduled_at: "2026-05-23T00:00:00Z"
    impact_tier: 1
```

**운영:** 매 월 1일 수동 또는 자동 크롤러로 갱신 (Phase 3 범위는 수동 관리).

---

## 4. Setup A — 갭 리버전

### 4.1 로직 (원본 §7.2 기반, 파라미터 YAML화)

```python
class SetupAGapReversion:
    CONFIG_CLASS = SetupAConfig

    def check(self, ctx: MarketContext) -> Signal | None:
        c = self.config

        # 1. 시간대 (장 시작 후 N~M 분)
        minutes_since_open = (ctx.now - ctx.market_open_time()).total_seconds() / 60
        if not (c.valid_minutes_min <= minutes_since_open <= c.valid_minutes_max):
            return None

        # 2. 매크로 야간 갭
        if ctx.macro_overnight is None:
            return None
        sp500_pct = ctx.macro_overnight.sp500_change_pct
        if abs(sp500_pct) < c.min_sp500_gap_pct:
            return None

        # 3. 코스피 시가 갭 vs 전일 종가
        gap_pct = (ctx.today_open - ctx.prev_close) / ctx.prev_close * 100
        if abs(gap_pct) < c.min_kr_gap_pct:
            return None

        # 4. 야간 방향과 시가 갭 방향 일치
        if sign(sp500_pct) != sign(gap_pct):
            return None

        # 5. 되돌림 비율 (gap의 X%~Y%)
        if gap_pct > 0:
            retrace = (ctx.today_open - ctx.current_price) / (ctx.today_open - ctx.prev_close)
            direction = "long"
        else:
            retrace = (ctx.current_price - ctx.today_open) / (ctx.prev_close - ctx.today_open)
            direction = "short"
        if not (c.retrace_min <= retrace <= c.retrace_max):
            return None

        # 6. Signal 생성
        atr = ctx.atr_14
        entry = ctx.current_price
        stop = entry - c.stop_atr_mult * atr if direction == "long" else entry + c.stop_atr_mult * atr
        target = ctx.prev_close + (ctx.today_open - ctx.prev_close) * c.target_gap_fill_ratio

        return Signal(
            setup_type="A_gap_reversion",
            direction=direction,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=self._compute_confidence(ctx, retrace, sp500_pct),
            reason_tags=[
                f"sp500_gap_{sp500_pct:+.2f}%",
                f"kr_gap_{gap_pct:+.2f}%",
                f"retrace_{retrace:.2%}",
            ],
            valid_until=ctx.now + timedelta(minutes=c.signal_ttl_minutes),
        )
```

### 4.2 파라미터 (`config/decision_engine.yaml`)

```yaml
setup_a_gap_reversion:
  enabled: true
  valid_minutes_min: 10
  valid_minutes_max: 90
  min_sp500_gap_pct: 0.5         # %
  min_kr_gap_pct: 0.3
  retrace_min: 0.30
  retrace_max: 0.55
  stop_atr_mult: 1.5
  target_gap_fill_ratio: 0.9
  signal_ttl_minutes: 10
```

**튜닝 범위 (부록 A):** `min_kr_gap_pct 0.2~0.6`, `retrace 0.25~0.60`, `stop_atr_mult 1.0~2.5`.

### 4.3 confidence 계산

```python
def _compute_confidence(self, ctx, retrace, sp500_pct) -> float:
    # 0.5 기본 + 갭 강도 + 되돌림 중앙 근접도
    base = 0.5
    gap_strength = min(abs(sp500_pct) / 1.5, 0.3)       # 최대 +0.3
    retrace_centrality = 0.2 * (1 - abs(retrace - 0.425) / 0.125)  # 최대 +0.2
    return min(1.0, base + gap_strength + retrace_centrality)
```

---

## 5. Setup C — 이벤트 리액션

### 5.1 로직 (원본 §7.4 기반)

```python
class SetupCEventReaction:
    CONFIG_CLASS = SetupCConfig

    def check(self, ctx: MarketContext) -> Signal | None:
        c = self.config

        # 1. 최근 N분 내 예정 이벤트 발표
        recent_event = self._find_recent_event(ctx.scheduled_events, ctx.now, c.window_minutes)
        if recent_event is None:
            return None

        # 2. 중복 진입 방지 (event_id 당 1회)
        if self.state_tracker.already_traded(recent_event.event_id):
            return None

        # 3. 발표 후 15분 고저점 브레이크아웃
        atr = ctx.atr_14
        buffer = c.breakout_buffer_atr_mult * atr

        if ctx.current_price > ctx.last_15min_high and (ctx.current_price - ctx.last_15min_high) < buffer:
            direction = "long"
            entry = ctx.current_price
            stop = ctx.last_15min_low
        elif ctx.current_price < ctx.last_15min_low and (ctx.last_15min_low - ctx.current_price) < buffer:
            direction = "short"
            entry = ctx.current_price
            stop = ctx.last_15min_high
        else:
            return None

        # 4. target
        target = entry + c.target_atr_mult * atr if direction == "long" else entry - c.target_atr_mult * atr

        return Signal(
            setup_type="C_event_reaction",
            direction=direction,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=0.65 + 0.1 * (3 - recent_event.impact_tier) / 2,   # tier 1=0.75
            reason_tags=[
                f"event_{recent_event.event_type}",
                f"tier_{recent_event.impact_tier}",
                "breakout_15m",
            ],
            valid_until=ctx.now + timedelta(minutes=c.signal_ttl_minutes),
        )
```

### 5.2 파라미터

```yaml
setup_c_event_reaction:
  enabled: true
  window_minutes: 15                # 발표 후 N분
  breakout_buffer_atr_mult: 0.5     # ATR 이내 브레이크만 유효
  target_atr_mult: 2.5
  signal_ttl_minutes: 30
  min_impact_tier: 2                # tier 2 이하는 무시
```

### 5.3 `signal.scored_news` 보강 (선택)

Setup C가 Phase 2 `news_scored`를 참조해 confidence를 높일 수 있다 — tier 1 이벤트 + impact_score 0.8+ 뉴스 동반 시 `+0.1` 가산. 구현은 Phase 3 말 선택적 추가.

---

## 6. RiskFilterLayer — 8개 순차 필터

`shared/risk/filters/` 신설. 각 필터는 `RiskFilter` ABC 상속:

```python
class RiskFilter(ABC):
    name: str
    @abstractmethod
    def check(self, signal: Signal, state: RiskState) -> FilterResult: ...
```

### 6.1 필터 목록 (순서대로 적용)

| # | 필터 | 거부 사유 태그 | 비고 |
|---|------|---------------|------|
| 1 | `TradingHoursFilter` | `outside_trading_hours` | `config.trading_windows` (09:00-10:30, 14:30-15:20) |
| 2 | `DailyMDDFilter` | `daily_mdd_exceeded` | `risk.daily_mdd_limit_pct` |
| 3 | `WeeklyMDDFilter` | `weekly_mdd_exceeded` | 신규 — 5영업일 rolling |
| 4 | `ConsecutiveLossFilter` | `consecutive_losses_cooldown` | 4연속 손실 → 포지션 50% 축소 (거부 아님), 6연속 → 거부 |
| 5 | `DailyTradeCountFilter` | `max_daily_trades` | `risk.max_daily_trades` |
| 6 | `VolatilityFilter` | `volatility_too_high` | `ctx.atr_14 > atr_90th_percentile` |
| 7 | `SpreadFilter` | `spread_too_wide` | `ctx.current_spread_ticks > max_spread_ticks` |
| 8 | `OpenPositionFilter` | `position_already_open` | 기존 오픈 포지션 있으면 거부 |

### 6.2 설정 (`config/risk.yaml` — 신규 또는 기존 확장)

```yaml
risk:
  account_equity_krw: 5000000
  daily_mdd_limit_pct: 0.03
  weekly_mdd_limit_pct: 0.07
  max_position_risk_pct: 0.015
  max_daily_trades: 3
  max_position_size_contracts: 2
  consecutive_loss_soft_threshold: 4    # 사이즈 축소
  consecutive_loss_hard_threshold: 6    # 거래 중단
  max_spread_ticks: 2

trading_windows:
  - "09:00-10:30"
  - "14:30-15:20"
```

### 6.3 RiskState

`shared/risk/state.py` — 일일/주간 PnL, 연속 손실, 일일 거래 횟수, ATR 90th percentile 캐시. Redis `risk:state:futures` HASH에 persist. 오케스트레이터 재시작 시 복원.

---

## 7. 포지션 사이저 — Mini 계약 정확

### 7.1 신규 sizer 등록

```python
# shared/strategy/position/sizers.py 확장
@SizerRegistry.register("fixed_fractional_futures")
class FixedFractionalFuturesSizer(PositionSizer):
    CONFIG_CLASS = FixedFractionalFuturesConfig

    def size(self, signal: Signal, account_equity: float) -> int:
        spec = self.config.contract_spec           # from config/execution.yaml
        stop_distance_points = abs(signal.entry_price - signal.stop_loss)
        # KRW risk per contract = points × multiplier
        krw_per_contract = stop_distance_points * spec.multiplier_krw_per_point
        target_risk_krw = account_equity * self.config.max_position_risk_pct
        raw_size = target_risk_krw / max(krw_per_contract, 1.0)
        size = max(1, min(int(raw_size), self.config.max_position_size))
        # 연속 손실 축소 (리스크 상태가 주입되어야 함)
        if self.state.consecutive_losses >= self.config.soft_reduce_threshold:
            size = max(1, size // 2)
        return size
```

### 7.2 계약 명세 — `config/execution.yaml` (신규 섹션)

```yaml
futures_contract_spec:
  kospi200_mini:
    multiplier_krw_per_point: 50000
    tick_size_points: 0.02
    tick_value_krw: 1000
    commission_rate: 0.00003
    symbol_prefix: "A05"
  kospi200_full:
    multiplier_krw_per_point: 250000
    tick_size_points: 0.05
    tick_value_krw: 12500
    commission_rate: 0.00003
    symbol_prefix: "101"
```

**하드코딩 제거 대상 (본 Phase에서 처리):**
- `shared/arbitrage/config.py`: `multiplier: int = 50000` → 설정 로드
- `shared/trend/config.py`: 동일
- `shared/ml/rl/env.py` / `shared/strategy/entry/rl_mppo.py`: `env_cfg.contract_multiplier` 기본값 → 본 설정 참조

**심볼 → 계약 스펙 매핑:**

```python
def resolve_contract_spec(symbol: str, specs: dict) -> ContractSpec:
    for name, spec in specs.items():
        if symbol.startswith(spec.symbol_prefix):
            return spec
    raise ValueError(f"no contract spec for symbol={symbol}")
```

---

## 8. 백테스트 (본 Phase의 핵심 검증)

### 8.1 대상 & 데이터

- **학습/평가 데이터:** `data/kospi200f_1m_clean.csv` (`101S6000`) — 기존 RL 데이터 재사용
- **매크로 데이터:** Phase 1에서 2주 수집 못 했으므로 **백테스트 시에는 Yahoo Finance 과거 데이터 retroactive 로드** (`yfinance` history API)
- **이벤트 데이터:** 공개 경제 캘린더에서 수동 CSV export (FOMC, CPI, NFP, BOK 1년치)

### 8.2 백테스트 엔진 확장

기존 `shared/backtest/engine.py` 확장:
- `MarketContext` 재생성 헬퍼 (역사적 replay)
- Setup 엔진 `check()` 매 1분마다 호출
- 리스크 필터 적용
- 슬리피지 고정값 `0.3 tick` 가정 (Phase 4에서 실측치로 교체)

### 8.3 성능 목표 (Setup별)

| 지표 | 목표 |
|------|------|
| Trades / 6개월 | ≥ 30 |
| Win rate | ≥ 45% |
| Avg R:R | ≥ 1.5 |
| EV per trade (tick) | > 0.5 (슬리피지 0.3 차감 후) |
| Max consecutive losses | ≤ 5 |

목표 미달 Setup은 파라미터 재튜닝 → Optuna TPE 30-100 trials (기존 `scripts/optimize_strategies.py` 패턴 재사용).

### 8.4 Walk-Forward Analysis

- **In-sample:** 직전 4개월
- **Out-of-sample:** 이후 2개월
- **채택 기준:** OOS Sharpe ≥ 0.5 × IS Sharpe, OOS EV 부호 보존

---

## 9. 시그널 저장

`V1` 마이그레이션에 포함된 `signals_all` 사용. Phase 3에서 다음 필드 채움 시작:
- `executed = 0` (Phase 3는 백테스트 전용)
- `skip_reason` = 필터 거부 사유 또는 빈 문자열
- `reason_tags` = Setup 엔진이 생성한 태그 배열

Phase 4에서 `executed = 1` 분기 추가.

---

## 10. 모니터링

### 10.1 Prometheus

```
signal_candidate_total{setup}                    Counter
signal_final_total{setup}                        Counter
signal_rejected_total{setup, filter}             Counter
signal_generator_duration_seconds{setup}         Histogram
risk_state_daily_pnl_pct                         Gauge
risk_state_consecutive_losses                    Gauge
risk_state_daily_trade_count                     Gauge
```

### 10.2 operational dashboard (신규 대시보드: `futures-decision-engine`)

- Setup별 시그널 발생 빈도 (24h)
- 필터별 거부율 (pie)
- 리스크 state 시계열
- 실시간 MarketContext 품질 (매크로 데이터 최신성, ATR 이상치)

---

## 11. 기존 시스템과의 관계

| 기존 컴포넌트 | Phase 3 상호작용 |
|--------------|-----------------|
| `StrategyManager` | 영향 없음. 신 시스템은 별도 `services/decision_engine/` 데몬으로 구동 |
| `rl_mppo` | 영향 없음. 같은 심볼에서 paper 병행하지 않음 (다른 계정 or 단순 관찰) |
| `shared/risk/manager.py` | 일부 로직 `RiskFilterLayer`로 이관, 기존 manager는 유지 (주식 paper 사용) |
| `shared/strategy/position/sizers.py` | 신규 sizer 등록만, 기존 sizer 영향 없음 |
| `config/execution.yaml` | `futures_contract_spec` 섹션 추가만 |

---

## 12. Phase 3 완료 게이트

- [ ] Setup A / C 엔진 구현 + 커버리지 ≥ 90%
- [ ] RiskFilterLayer 8개 필터 구현 + 커버리지 ≥ 85%
- [ ] `FixedFractionalFuturesSizer` 구현 + 계약 명세 설정 로드
- [ ] 하드코딩 `50000` 제거 (arbitrage, trend 모듈)
- [ ] 6개월 백테스트: Setup당 ≥ 30 trades, EV > 0.5 tick (슬리피지 0.3 차감)
- [ ] Walk-Forward OOS Sharpe ≥ 0.5 × IS
- [ ] `signals_all` 적재 확인 (백테스트 run당 수십~수백 rows)
- [ ] `config/decision_engine.yaml`, `config/risk.yaml`, `config/scheduled_events.yaml` 확정
- [ ] 운영 대시보드 신설
- [ ] `rl_mppo` 운용 영향 없음

---

## 13. 명시적 비범위

- 주문 전송 및 체결 (Phase 4)
- Passive Maker / OCO (Phase 4)
- Kill switch (Phase 4)
- Live paper trading 배포 (Phase 5)
- 실시간 consumer group 기반 `stream:signal.*` 발행 데몬 — **본 Phase는 백테스트에서만 in-process 호출**. 실시간 파이프라인은 Phase 4에서 Paper 전환.
- Setup B (Q1-D로 영구 제외)
- 기존 `rl_mppo` 아키텍처 변경 (RL spec)
