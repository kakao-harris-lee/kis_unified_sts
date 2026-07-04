# Forecast-Aware Paradigm — Design Spec

**Date**: 2026-05-13
**Status**: Design approved, pending implementation plan
**Topic**: 선물 거래 전략 방향 전환 — RL 중심에서 변동성 예측 + 이벤트 임팩트 + 기술적 지표 보조로 재설계. RL은 shadow baseline으로 3-4주 비교 후 폐지 판단.
**Related branch**: `feat/forecast-aware-paradigm-spec` (this doc); implementation will land across multiple PRs (Phase A–G).

---

## 1. Decisions Summary

5 brainstorming Q&A 결과로 다음 기반 결정이 확정됨.

| # | 결정 | 채택 |
|---|------|------|
| Q1 | 통합 방식 | **Setup A/C 유지 + 새 시스템이 보조** — 기존 entry 로직 그대로, 새 컴포넌트가 threshold/size 조정 |
| Q2 | 신호 종류 | **변동성 예측 + 이벤트 임팩트 magnitude** — 2개 신호 제공 |
| Q3 | 변동성 모델 | **HAR-RV** (Corsi 2009; 5m/30m/daily multi-frequency RV components) |
| Q4 | 이벤트 스코어링 | **Hybrid: rule-based 1차 + LLM 보강** — taxonomy YAML로 known events, LLM은 unknown fallback |
| Q5 | 성공 기준 (3-4주 후 RL 폐지) | **Safety margin**: `Sharpe_new ≥ Sharpe_rl × 0.9 AND MDD_new ≤ MDD_rl × 1.1` |

**예상 소요**: ~16 영업일 + 3-4주 validation (Phase F)

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  INPUTS (기존 인프라 재활용)                                       │
│  • 1m bars → kospi.kospi200f_1m + resample to 5m/30m/daily        │
│  • News raw text → services/news_collector → kospi.news_scored    │
│  • Macro events → shared/llm/krx_api_client (KRX Open API)        │
│  • Live tick → Redis stream raw_data (선물 H0IFASP0)              │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  NEW: shared/forecasting/  (~1,540 LOC total)                     │
│  ├── volatility_har_rv.py    HAR-RV (Corsi 2009), daily refit     │
│  ├── realized_variance.py    5m/30m/daily RV component computation │
│  ├── event_impact_scorer.py  Hybrid (rule + LLM) score 0-100      │
│  ├── event_taxonomy.py       Known event types + weight table     │
│  ├── llm_event_scorer.py     LLM fallback (재활용 shared/llm/*)   │
│  ├── forecast_publisher.py   Redis pub/sub broadcaster            │
│  ├── client.py                Setup A/C consumer wrapper          │
│  ├── models.py                VolForecast, EventScore dataclasses │
│  └── config.py                ForecastingConfig (ServiceConfigBase) │
│                                                                    │
│  services/forecasting/main.py — asyncio loop (1m forecast + event) │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  Setup A/C (기존 코드 + thin adapter)                              │
│  shared/strategy/entry/setup_adapters.py                          │
│  • breakout_buffer = base × vol_forecast / vol_baseline           │
│  • target = base × vol_forecast / vol_baseline                    │
│  • position_size = base × (vol_baseline / vol_forecast)           │
│  • event_filter = event_impact_score >= threshold                 │
│  • feature flag: forecast_integration.enabled (default false)     │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  Validation (3-4주, Phase F)                                       │
│  scripts/analysis/forecast_vs_rl_comparison.py                    │
│  • Setup A/C new system vs RL shadow counterfactual               │
│  • Q5 기준 평가: Sharpe ≥ RL×0.9 AND MDD ≤ RL×1.1                  │
│  • Weekly Telegram report (Sun 23:00 KST)                         │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  Existing (변경 없음)                                              │
│  • TradingOrchestrator + StrategyManager                          │
│  • RL shadow (baseline) — 3-4주간 보존                             │
│  • Phase 2 daily verification cron — new gate 5/6/7 추가          │
│  • Dashboard /api/health/* + Cockpit                              │
│                                                                    │
│  Phase G (Q5 충족 시): RL 완전 제거 (~5000 LOC)                    │
└──────────────────────────────────────────────────────────────────┘
```

**핵심 변화 3가지:**

1. **신규 `shared/forecasting/` 모듈** — HAR-RV vol forecaster + hybrid event scorer + Redis publisher (~900 LOC)
2. **Setup A/C YAML/adapter thin integration** — ATR 기반 thresholds를 vol forecast 기반으로 교체 (~170 LOC). 기존 entry logic은 그대로.
3. **Validation framework + Phase G RL deprecation gate** — 3-4주 후 RL 폐지 자동 권고. 미충족 시 Phase 4 (3개월) 자연 합류.

**Fail-safe 원칙**: 모든 forecast 실패 → ATR fallback. **Setup A/C 거래는 절대 중단되지 않음.** 새 시스템 위험 ≤ 기존 시스템.

---

## 3. Component Decomposition

### 신규 모듈 `shared/forecasting/`

| 파일 | 책임 | LOC |
|------|------|----|
| `__init__.py` | exports: `VolatilityForecaster`, `EventImpactScorer`, `ForecastPublisher`, `ForecastClient` | ~20 |
| `config.py` | `ForecastingConfig(ServiceConfigBase)` — YAML/env 로드 | ~80 |
| `volatility_har_rv.py` | HAR-RV 모델 (refit + forecast) | ~250 |
| `realized_variance.py` | 5m/30m/daily realized variance 계산 | ~120 |
| `event_impact_scorer.py` | 통합 scorer (rule + LLM fallback 조합) | ~150 |
| `event_taxonomy.py` | rule-based event types + weights loader | ~100 |
| `llm_event_scorer.py` | LLM 호출 wrapper (재활용 `shared/llm/llm_analyzer.py`) | ~120 |
| `forecast_publisher.py` | Redis pub/sub broadcaster (1m periodic + event-driven) | ~80 |
| `client.py` | Setup A/C consumer wrapper (pull + push) | ~50 |
| `models.py` | dataclass: `VolForecast`, `EventScore`, `ForecastSnapshot` | ~60 |

### 핵심 인터페이스

```python
# shared/forecasting/models.py
@dataclass
class VolForecast:
    asof: datetime              # UTC tz-aware
    horizon_minutes: int        # 15 (default, matches Setup C event window)
    forecast_pct: float         # annualized % (e.g. 18.5)
    forecast_atr_equivalent: float  # ATR-unit 환산 (Setup A/C 호환)
    regime_percentile: float    # historical 변동성 분포 위치 0-100
    model_version: str          # "har_rv_v1"
    confidence: float           # 0-1 (OOS R² 기반)

    def is_fresh(self, now: datetime, max_age_s: int = 120) -> bool: ...

@dataclass
class EventScore:
    asof: datetime
    impact_score: float         # 0-100
    event_type: str             # "FOMC" | "BOK" | "CPI" | "UNKNOWN_LLM_SCORED"
    source: Literal["rule", "llm"]
    raw_text: str | None        # LLM source일 때만
    ttl_minutes: int            # default 30

    def is_expired(self, now: datetime) -> bool: ...
```

```python
# shared/forecasting/volatility_har_rv.py
class VolatilityForecaster:
    """Corsi (2009) HAR-RV on 5m/30m/daily RV components."""

    def fit(self, history: pd.DataFrame) -> None:
        """OLS fit on past 60d realized variance. Refits daily at 15:35 KST."""

    def forecast(self, asof: datetime) -> VolForecast:
        """Return 15-min forward forecast using current RV components."""

    def is_fit_stale(self) -> bool: ...
```

```python
# shared/forecasting/event_impact_scorer.py
class EventImpactScorer:
    """Hybrid: rule-based first, LLM fallback for unknown event types."""

    async def score(self, event_text: str, event_type: str | None) -> EventScore:
        """Returns 0-100 impact score. Rule-based if taxonomy match,
        else LLM. Falls back to 50 (neutral) on both fail."""

    def score_macro_event_calendar(self, asof: datetime) -> list[EventScore]: ...
```

### Setup A/C 통합 (thin adapter 변경)

`shared/strategy/entry/setup_adapters.py` 수정 — entry logic 그대로, params만 forecast로 교체. ~170 LOC 추가/변경.

### 신규 service `services/forecasting/`

| 파일 | 책임 | LOC |
|------|------|----|
| `services/forecasting/main.py` | asyncio loop, daily refit at 15:35 KST + 1m forecast publish | ~150 |

cron 등록:
```
55 8 * * 1-5 $KIS_PROJECT/scripts/cron/forecasting.sh start    # 장 시작 5분 전
35 15 * * 1-5 $KIS_PROJECT/scripts/cron/forecasting.sh refit   # 장 마감 5분 후
```

Docker compose 단위(`kis-forecasting`) — Phase 5 paradigm 다른 services와 일관성.

### 신규 validation script

| 파일 | 책임 |
|------|------|
| `scripts/analysis/forecast_vs_rl_comparison.py` | 주간 cron — Setup A/C 신규 vs RL shadow counterfactual Sharpe/MDD 비교 |
| `scripts/cron/forecast_weekly_report.sh` | Mon 07:00 KST Telegram briefing wrapper |

### 코드 영향 추정

| 영역 | 추가 LOC | 변경 LOC |
|------|----------|---------|
| `shared/forecasting/` 신규 모듈 | ~900 | — |
| `services/forecasting/` 신규 service | ~150 | — |
| `shared/strategy/entry/setup_adapters.py` 통합 | ~75 | ~30 (기존) |
| Setup A/C YAML `forecast_integration` blocks | ~22 | — |
| `shared/strategy/position/llm_adaptive_sizer.py` forecast hook | +25 | — |
| `shared/forecasting/client.py` consumer wrapper | ~50 | — |
| `config/forecasting.yaml` 신규 | ~50 | — |
| `scripts/analysis/forecast_vs_rl_comparison.py` 신규 | ~250 | — |
| `scripts/cron/forecasting.sh` + `forecast_weekly_report.sh` | ~60 | — |
| ClickHouse migration V6 (3 tables SQL) | ~20 | — |
| **합계** | **~1,602 LOC** | **~30 LOC** |

**기존 RL 코드 보존** until Phase G: `shared/ml/rl/*` 그대로. 비교 baseline + 후속 폐지 결정용 데이터 누적.

---

## 4. Setup A/C Integration Details

### 변환 규칙: ATR → Vol-forecast

핵심 원리: **`vol_forecast.forecast_atr_equivalent`가 현재 ATR 자리를 대체**.

`forecast_atr_equivalent` 변환 공식:
```
forecast_atr_equivalent = vol_forecast_pct × close × √(15/(252×390)) / 100
```
(annualized vol → 15-min vol, KOSPI 거래시간 390분 기반)

### Setup C — Event Reaction 매핑

**기존 YAML:**
```yaml
entry:
  params:
    window_minutes: 15
    breakout_buffer_atr_mult: 0.5
    target_atr_mult: 2.5
    signal_ttl_minutes: 30
    min_impact_tier: 2
```

**새 YAML 추가 (opt-in, 기본 false):**
```yaml
entry:
  params:
    # 기존 params 그대로 (ATR fallback)
    forecast_integration:
      enabled: false                    # ⚠️ feature flag
      buffer_vol_mult: 0.5
      target_vol_mult: 2.5
      min_event_impact_score: 60        # 0-100 (replaces discrete tier)
      vol_baseline_window_days: 30
      stale_forecast_fallback: "atr"
```

**런타임 동작:**

| 조건 | breakout_buffer | target | event filter |
|------|-----------------|--------|--------------|
| forecast 활성 + fresh | `buffer_vol_mult × forecast_atr_eq` | `target_vol_mult × forecast_atr_eq` | `event.impact_score ≥ min_event_impact_score` |
| forecast 활성 + stale (>120s) | ATR fallback | ATR fallback | tier fallback |
| forecast 비활성 (flag off) | 기존 ATR | 기존 ATR | 기존 tier |

**예시 (KOSPI200 선물 ATR ~3pt):**

| 시나리오 | ATR | forecast_atr_eq | buffer |
|---------|-----|----------------|--------|
| 평시 (P50) | 3pt | 3pt | 0.5 × 3 = **1.5pt** |
| 고변동성 (P90, FOMC 후) | 3pt | 6pt | 0.5 × 6 = **3pt** (보수적) |
| 저변동성 (P10) | 3pt | 1.5pt | 0.5 × 1.5 = **0.75pt** (sensitive) |

### Setup A — Gap Reversion 매핑

```yaml
forecast_integration:
  enabled: false
  gap_threshold_vol_mult: 1.0       # gap 임계: 일일 예상 변동성의 N배
  retracement_buffer_vol_mult: 0.3
  max_gap_for_reversion_vol_mult: 4.0  # >4σ gap이면 추세 — skip
  use_event_impact_for_size: true   # event 동반 gap → size 축소
```

### Position Sizing 통합

기존 multi-tier LLM sizer (PR #168) × forecast vol scaling = 최종 size:

```python
final_size = base × llm_tier_multiplier × forecast_size_multiplier

# forecast_size_multiplier = clip(vol_baseline / forecast_atr_equivalent, 0.3, 1.5)
# 고변동성 → 축소, 저변동성 → 평소
```

두 시스템 직교 — LLM tier (검증된) + forecast vol (신규)을 곱셈 결합.

### Rollback 시나리오

| Flag | 효과 |
|------|------|
| `setup_c.forecast_integration.enabled: false` | Setup C ATR 복원 (< 5분) |
| `setup_a.forecast_integration.enabled: false` | Setup A 동일 |
| `forecasting.publisher.enabled: false` | forecast service 중단, Setup A/C 자동 ATR fallback |
| `inverse_vol_position_size: false` | size scaling 비활성, LLM tier만 적용 |

부분 rollout: Setup C → 1주 관찰 → Setup A 활성화.

---

## 5. Data Flow + Storage Schema

### 데이터 소스 (재활용)

| 소스 | 위치 | 용도 |
|------|------|------|
| 1m bars | `kospi.kospi200f_1m` | 5m/30m/daily RV 컴포넌트 |
| Daily bars | resampled from 1m | HAR-RV daily 컴포넌트 |
| News raw | `services/news_collector/` → `kospi.news_raw` | 이벤트 감지 + LLM 입력 |
| News scored | `kospi.news_scored` | 1차 rule-based event matching |
| Macro calendar | `shared/llm/krx_api_client.py` | known events (FOMC/BOK/CPI) |
| Live tick | Redis stream `raw_data` (H0IFASP0) | RV component 실시간 update |

### Pipeline 1: HAR-RV 일일 refit (15:35 KST)

```
kospi.kospi200f_1m (60d) → resample → RV_5m, RV_30m, RV_daily
                       ↓ OLS regression
RV_t = β0 + β_d × RV_t-1 + β_w × mean(RV_t-1..t-5) + β_m × mean(RV_t-1..t-22)
                       ↓ persist
ClickHouse kospi.har_rv_fits + Redis SET forecast:vol:model
```

OOS R² = 마지막 7거래일 hold-out → `confidence`.

### Pipeline 2: 1m forecast loop

```python
while not stopped:
    asof = datetime.now(UTC)
    rv_5m, rv_30m, rv_daily = await compute_recent_rv(asof)
    forecast = model.predict(...) if model.is_loaded() else VolForecast.fallback_atr(...)
    redis.set("forecast:vol:current", forecast.to_json(), ex=120)
    await ch_insert("kospi.vol_forecasts", forecast.to_row())
    await asyncio.sleep(60)
```

### Pipeline 3: Event scorer loop

```python
pubsub.subscribe("news:raw")
async for msg in pubsub.listen():
    event_type = match_taxonomy(news_event)
    if event_type:
        score = rule_scorer.score(event_type, news_event)
    else:
        score = await llm_scorer.score(news_event.text)
    redis.publish("forecasting:events", es.to_json())
    redis.set("forecast:event:latest", es.to_json(), ex=es.ttl_minutes * 60)
    await ch_insert("kospi.event_scores", es.to_row())
```

### Setup A/C consumer

```python
class ForecastClient:
    async def get_latest_vol_forecast(self) -> VolForecast | None:
        """Pull-based (Redis SET with TTL). Returns None when stale → ATR fallback."""

    async def get_latest_event_score(self) -> EventScore | None:
        """Push-based (pubsub cached). Returns None when expired."""
```

### Redis schema

| Key / channel | 타입 | TTL | Publisher | Consumer |
|--------------|------|-----|-----------|----------|
| `forecast:vol:current` | string JSON | 120s | forecasting service | ForecastClient (Setup A/C) |
| `forecast:vol:model` | string JSON | none | forecasting service (daily refit) | service startup recovery |
| `forecast:event:latest` | string JSON | event TTL × 60 | forecasting service | ForecastClient fallback |
| `forecasting:events` | pubsub | n/a | forecasting service | ForecastClient subscriber |
| `news:raw` | pubsub | n/a | news_collector (기존) | forecasting event_scorer_loop |

**모두 Redis DB 1** (CLAUDE.md 규칙).

### ClickHouse 신규 테이블 (migration V6)

```sql
CREATE TABLE IF NOT EXISTS kospi.har_rv_fits (
    fit_date Date,
    beta_0 Float64, beta_d Float64, beta_w Float64, beta_m Float64,
    r2_in_sample Float64, r2_oos Float64,
    n_obs_used UInt32, confidence Float32,
    model_version LowCardinality(String),
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY fit_date
TTL fit_date + INTERVAL 12 MONTH;

CREATE TABLE IF NOT EXISTS kospi.vol_forecasts (
    asof DateTime64(3, 'UTC'),
    horizon_minutes UInt16,
    forecast_pct Float32, forecast_atr_equivalent Float32,
    regime_percentile Float32,
    realized_15m_after Float32 DEFAULT 0,  -- backfilled for evaluation
    model_version LowCardinality(String)
) ENGINE = MergeTree()
ORDER BY asof
TTL asof + INTERVAL 90 DAY;

CREATE TABLE IF NOT EXISTS kospi.event_scores (
    asof DateTime64(3, 'UTC'),
    event_type LowCardinality(String),
    impact_score UInt8,
    source Enum8('rule' = 1, 'llm' = 2),
    ttl_minutes UInt16,
    raw_text_hash FixedString(16) DEFAULT '',
    setup_consumed Array(LowCardinality(String))
) ENGINE = MergeTree()
ORDER BY asof
TTL asof + INTERVAL 6 MONTH;
```

저장 부하: vol_forecasts ~24KB/day, event_scores ~1KB/day, har_rv_fits ~6KB/year. Minimal.

### Timing diagram

```
08:50  systemd start kis-forecasting (load model from Redis)
09:00  KRX open → forecast loop tick #1 publish
09:01–15:30  trading session (forecast × 390, events × ~10)
15:35  Daily refit (60d data → OLS → persist)
15:40+ Backfill realized_15m_after (validation 데이터)
17:00  service stop / sleep
```

---

## 6. Error Handling + Observability

### 에러 처리 매트릭스

| 실패 | 즉시 동작 | 복구 |
|------|----------|------|
| HAR-RV refit fails (R²<0.1) | 기존 모델 유지, Telegram alert | 익일 자동 재시도. 7d 연속 실패 → `model_disabled` (ATR 영구 fallback) |
| HAR-RV forecast NaN/Inf | publish skip + counter ++ | 10회 연속 → service self-restart |
| Forecast service crash | systemd auto-restart | 30s 내 복구 |
| Redis disconnect | log warning + retry. Setup A/C ATR fallback (자동) | Redis 복귀 시 정상화 |
| ClickHouse insert fail | 기존 retry queue (`ch_insert_fail_tracker`) | ClickHouse 복귀 후 backfill |
| News pubsub miss | ClickHouse polling fallback (1m 주기 backup) | 자동 |
| LLM API outage | rule-only mode. Unknown event → score=50 | LLM 복귀 후 자동 |
| Forecast stale > 120s | adapter ATR fallback (silent). Counter ++ | 다음 publish 사이클 |
| Event score expired | event filter disabled, ATR-only entry | 다음 이벤트 발생 시 갱신 |
| vol_baseline 계산 실패 | adapter ATR fallback. Telegram 1회 alert | ClickHouse data 누적 후 자동 |

**Fail-safe 원칙**: 모든 forecast 실패 → ATR fallback. **Setup A/C 거래는 절대 중단되지 않음.**

### Prometheus metrics

```python
forecast_rmse_15m              # 7d rolling RMSE
forecast_r2_oos                # latest HAR-RV OOS R²
forecast_publish_total{status}  # ok | nan | redis_fail
forecast_stale_total{setup}    # setup_a | setup_c
event_scorer_calls_total{source, result}  # rule|llm  ok|fail|neutral
event_scorer_latency_seconds{source}
har_rv_refit_duration_seconds
har_rv_refit_total{status}     # ok | fail | r2_below_threshold
forecast_vs_atr_threshold_ratio
```

### Alert rules

```yaml
- alert: ForecastingServiceDown (5m → critical)
- alert: HARRefitFailed (24h → warning)
- alert: HARRefitConsecutiveFailures (5+ in 7d → critical)
- alert: ForecastStalenessHigh (>50% for 10m → warning)
- alert: ForecastAccuracyDegraded (R²<0.15 for 24h → warning)
- alert: EventScorerLLMFallbackHigh (>30% fail for 30m → warning)
```

### Health endpoint

`GET /api/health/forecasting`:
```json
{
  "service_alive": true,
  "forecast_fresh": true,
  "forecast_age_s": 23,
  "model_loaded": true,
  "model_last_refit": "2026-05-13",
  "model_r2_oos": 0.31,
  "model_disabled": false
}
```

### Phase 2 daily verification gates (16:00 KST cron 확장: 4 → 7)

5. ✅ **HAR-RV refit success today**
6. ✅ **Forecast publish active during session** (> 100 rows)
7. ✅ **Event scorer healthy** (LLM fallback rate < 50%)

Q5 성공 기준 충족 여부는 weekly Telegram report에 표시.

---

## 7. Migration Plan + RL Deprecation Gate

### 원칙

1. 각 phase = 1 PR (atomic, 독립 revertible)
2. 운영 무중단 (Phase 2 cutover LIVE 유지)
3. Fail-safe defaults — `forecast_integration.enabled: false` 가 기본
4. RL 보존 until Phase G — 3-4주 비교 데이터 누적 전까지

### 7개 phase 순서

| Phase | 작업 | 위험 | 소요 |
|-------|------|------|------|
| **A. 기반 모듈** | `shared/forecasting/` + tests + ClickHouse V6 migration | 🟢 zero | 5d |
| **B. Service daemon + cron** | `services/forecasting/main.py` + Docker + Prometheus + 6 alerts + health endpoint | 🟢 low (no consumer) | 3d |
| **C. Setup A/C adapter integration** | `client.py` + `setup_adapters.py` hook + YAML `forecast_integration` block (flag off) + 새 verification gates | 🟢 low (flag off) | 4d |
| **D. Canary: Setup C only** | `setup_c.forecast_integration.enabled: true` | 🟡 medium | 0.5d + **7d 관찰** |
| **E. Setup A 활성화** | `setup_a.forecast_integration.enabled: true` + inverse-vol sizing | 🟡 medium | 0.5d + **3d 관찰** |
| **F. Validation period** | Weekly `forecast_vs_rl_comparison.py` 리포트 | 🟢 관찰만 | **3-4 wk** |
| **G. RL deprecation execution** | Q5 충족 시 RL 폐지 (~5000 LOC 삭제). 미충족 시 보류 + Phase 4 (3개월) 자연 합류 | 🟡 medium (deletion) | 2d (충족 시) |

**총 ~16 영업일 + 3-4주 validation**.

### Phase G: RL deprecation 대상

Q5 충족 시 삭제 (PR 분리):

1. `chore(rl): deprecate cron + service` — cron 중단, code 보존
2. `chore(rl): remove entry/exit strategies` — registry에서 rl_mppo 제거
3. `chore(rl): remove shared/ml/rl/ module` — ~5000 LOC 코드 삭제
4. `chore(rl): clean up CLI + dashboard refs`
5. `chore(rl): archive ClickHouse tables` (6개월 후)
6. `docs(plan): RL deprecation complete + lessons learned`

| 삭제 대상 |
|----------|
| `shared/ml/rl/` 디렉토리 전체 (hierarchical/, trainer.py, evaluator.py, retraining_pipeline.py, multi_agent.py, decision_transformer/, baseline_snapshot.py, champion_challenger.py, model_registry.py 등) |
| `shared/strategy/entry/rl_mppo.py` |
| `shared/strategy/exit/rl_mppo_exit.py` |
| `shared/strategy/rl_model_helpers.py` |
| `config/strategies/futures/rl_mppo*.yaml` × 12개 |
| `scripts/cron/rl_paper.sh` |
| `cli/main.py::sts rl ...` 모든 subcommand |
| `services/dashboard/routes/trades.py::/api/trades/rl` (제거 또는 generic 이름) |
| `kospi.rl_trades`, `kospi.rl_shadow_predictions` (DROP after 6mo archive) |
| MLflow `rl_mppo` 실험 (archive, delete X — history 보존) |
| Tests: `tests/unit/ml/rl/`, `tests/integration/test_rl_*` |
| CLAUDE.md, README, runbooks RL 섹션 |

### Phase G 분기 — Q5 미충족

- 데이터 부족 (trades < 30): Phase F 6-8주 확장
- 새 시스템 underperform: forecast_integration 비활성. RL shadow 유지. Phase 4 (3개월) 재평가
- 결과 모호: hybrid 유지. 새 시스템 + RL shadow 둘 다. 자연 합류 Phase 4

### Phase 의존성 그래프

```
A ──► B ──► C ──┬──► D ──► E ──► F ──► G
```

### 운영자 영향 (배포 윈도)

| Phase | 윈도 | 영향 |
|-------|------|------|
| A, B, C | 평시 가능 | zero |
| **D, E** | **장 마감 후 (15:30+ KST) 또는 주말** | Setup A/C 동작 변화 |
| F | n/a | 관찰 |
| G | 단계적, 평시 가능 (RL cron 중단은 주말 권장) | RL 폐지 |

### Plan v4.9 → v5.0 갱신

`docs/plans/archive/2026-05-03-llm-primary-rl-minimization.md`:
- §1 결정 배경: RL 추가 축소 (운영자 §7-4)
- §2 목표 상태: forecast-aware paradigm + RL deprecation gate
- §4 Phase 5 신설 (forecasting integration)
- §7 운영자 결정: §7-4 신설
- §10 후속: Phase G cleanup

---

## 8. Testing Strategy

### Phase A — 단위 테스트 (~34개)

| 파일 | 테스트 수 |
|------|----------|
| `tests/unit/forecasting/test_har_rv.py` | ~12 (RV 계산, OLS fit, OOS R², singular matrix, NaN handling, unit conversion) |
| `tests/unit/forecasting/test_event_scorer.py` | ~10 (rule taxonomy match, LLM fallback, hybrid logic, TTL expiration, malformed response) |
| `tests/unit/forecasting/test_forecast_publisher.py` | ~6 (Redis TTL, pubsub, ClickHouse insert, NaN skip, idempotency) |
| `tests/unit/forecasting/test_forecast_client.py` | ~6 (fresh/stale, pubsub subscriber, GET fallback, race condition) |

### Phase B — 통합 테스트 (~8개)

`tests/integration/test_forecast_pipeline.py`:
- Service start loads model, fallback if missing
- Forecast loop publishes every 60s (mock time)
- Daily refit at 15:35 KST
- Refit fail retains previous model
- Event scorer subscribes to `news:raw`
- ClickHouse persist + graceful shutdown

### Phase C — Setup A/C adapter 테스트 (~10개)

기존 `test_setup_adapters.py` 확장:
- forecast fresh/stale/disabled paths
- event filter via impact score
- inverse-vol position size
- LLM tier × forecast multiplier 조합
- forecaster_client None fallback

### Phase F — Validation 자동 리포트

`scripts/analysis/forecast_vs_rl_comparison.py`:
- Setup A/C with-forecast Sharpe/MDD/EV
- RL shadow counterfactual Sharpe/MDD/EV
- Q5 ratio (Sharpe ≥ 0.9, MDD ≤ 1.1) → PASS/FAIL
- Weekly Telegram report Mon 07:00 KST

### Offline 백테스트 (Phase F 보강)

`scripts/analysis/forecast_backtest.py`:
- 과거 3개월 1m bars + macro events
- HAR-RV walk-forward (매일 refit, 15분 forecast)
- 통과 기준: RMSE < 5%-points, R² > 0.2

Setup A/C 비교 백테스트 — 동일 historical period에서 ATR vs forecast 모드. MLflow에 저장.

### 회귀 가드 (Phase G)

```bash
# scripts/dev/check_no_rl_imports.sh (Phase G PR에 포함)
DELETED_PATTERNS=(
  "from shared.ml.rl"
  "shared/strategy/entry/rl_mppo"
  "shared/strategy/exit/rl_mppo_exit"
  "sts rl "
  "RLMPPOEntry"
  ...
)
```

### 테스트 부담 추정

| 영역 | 신규 | 시간 |
|------|------|------|
| Phase A 단위 | ~34개 | 2.5d |
| Phase B 통합 | ~8개 | 1.5d |
| Phase C adapter | ~10개 | 1d |
| Phase F validation | ~5개 | 0.5d |
| 백테스트 script | 수동 | 0.5d |
| **합계** | **~57개** | **~6d** |

---

## 9. Out of Scope (YAGNI)

이번 작업에서 의도적으로 **제외**한 항목.

### 변동성 모델 확장
- ❌ GARCH(1,1) — Q3에서 HAR-RV 선택, EWMA보다 우월
- ❌ Implied volatility (KOSPI200 옵션) — Q3 옵션 D, 옵션 파이프라인 신규 필요 (~2주)
- ❌ Jump detection (Lee & Mykland) — KOSPI200 jump 빈도 검증 후
- ❌ Asymmetric HAR-RV (HAR-RV-J) — 1차 검증 후
- ❌ Realized kernel / pre-averaging — 5m bars로 충분
- ❌ Multivariate (KOSPI vs S&P) — cross-asset, 별도 spec

### 이벤트 스코어링 확장
- ❌ Sentiment (positive/negative) — magnitude만, 방향은 Setup A/C가 결정
- ❌ Multi-language news — 한국 macro 중심
- ❌ Twitter/SNS — 노이즈 비율 높음
- ❌ Pre-event prediction — reactive scoring으로 충분
- ❌ Event clustering — most recent event single

### Setup A/C 자체 변경
- ❌ 새 entry 로직 — params만 forecast로 조정
- ❌ Setup B 부활 — plan deprecated
- ❌ Multi-timeframe Setup A/C — 별도 spec

### RL 처리 범위
- ❌ RL 점진적 retraining — 폐지 방향
- ❌ RL ↔ forecast hybrid — 복잡도, deprecation 모순
- ❌ Hierarchical RL 활성화 — 폐지 대상

### 인프라
- ❌ Tick-level forecast — 1m로 충분
- ❌ GPU 추론 — OLS, CPU로 충분
- ❌ Multi-region / Kubernetes — docker-compose 충분
- ❌ Stream processing (Flink/Kafka) — Redis pub/sub 충분

### 관측성
- ❌ Distributed tracing — 단일 서비스
- ❌ Custom React Dashboard 대시보드 — Cockpit indicator 1개 추가 (별도 follow-up)
- ❌ A/B testing framework — Phase D canary로 충분

### 비교/검증 확장
- ❌ 다른 baseline 비교 — RL shadow 1개만
- ❌ Walk-forward bias 보정 — 6개월+ data 후
- ❌ Bootstrap confidence intervals — 단순 ratio로 충분

### 운영자 도구
- ❌ Forecast 수동 override UI — YAML flag 변경
- ❌ Event taxonomy 편집 UI — YAML 직접
- ❌ HAR-RV 튜닝 dashboard — refit auto

### 향후 후속 작업 (참고)

1. KOSPI200 옵션 implied vol 통합 (Q3 옵션 D) — 정확도 한계 시
2. Asymmetric HAR-RV — leverage effect 명확 시
3. Forecast Cockpit indicator — vol regime traffic light
4. 이벤트 클러스터 스코어링
5. Cross-asset volatility (KOSPI ↔ S&P) — overnight gap 강화
6. Setup D 신규 — pure volatility-breakout

---

## 10. References

- 브레인스토밍 5 Q&A 결정 (Q1–Q5): 본 문서 §1
- 관련 운영 컨텍스트:
  - `docs/plans/archive/2026-05-03-llm-primary-rl-minimization.md` (Phase 2 cutover LIVE, v4.9)
  - `docs/investigations/2026-05-12-stock-signals-regression.md` (PR #233, 5/6 이후 stock 0-signals)
  - Phase 5 paradigm services: `services/decision_engine/`, `services/risk_filter/`, `services/order_router/`
- Setup A/C 기존 구현: `shared/strategy/entry/setup_adapters.py`, `config/strategies/futures/setup_{a,c}_*.yaml`
- RL 기존 구현 (Phase G 폐지 대상): `shared/ml/rl/`, `shared/strategy/entry/rl_mppo.py`, `shared/strategy/exit/rl_mppo_exit.py`
- LLM 분석 (event scorer LLM fallback 재활용): `shared/llm/llm_analyzer.py`, `shared/llm/krx_api_client.py`
- News pipeline (event source): `services/news_collector/`
- Phase 2 daily verification (gate 추가): `scripts/analysis/phase2_daily_verification.py`
- 학술 참고:
  - Corsi, F. (2009). "A Simple Approximate Long-Memory Model of Realized Volatility." *Journal of Financial Econometrics*, 7(2), 174-196.
  - Andersen, T. G., Bollerslev, T., Diebold, F. X., & Labys, P. (2003). "Modeling and Forecasting Realized Volatility." *Econometrica*, 71(2), 579-625.

---

**다음 단계**: 본 spec 사용자 검토 → 승인 시 `writing-plans` skill로 phase별 상세 구현 plan 작성.
