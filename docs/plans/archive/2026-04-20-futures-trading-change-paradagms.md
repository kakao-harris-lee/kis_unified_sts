# KOSPI200 선물 자동매매 시스템 전환 지침서

> **ARCHIVED 2026-06-22:** Original futures paradigm-change brief. It predates
> the current Setup A/C + LLM-context runtime, RL/TFT removal, and ClickHouse
> removal. Use [ROADMAP.md](../../ROADMAP.md),
> [2026-06-03-ml-rl-removal-llm-indicator-futures.md](../2026-06-03-ml-rl-removal-llm-indicator-futures.md),
> and [2026-04-20-futures-paradigm-phase5-rollout.md](../2026-04-20-futures-paradigm-phase5-rollout.md)
> for current decisions and live rollout gates.

**버전:** 1.0
**대상:** Claude Code 또는 개발자가 직접 구현 시 참고
**목표:** RL 중심 당일매매 → 뉴스 + 수급 + 규칙 기반 하이브리드 시스템
**핵심 원칙:** 소액 생존 → 슬리피지 최소화 → EV 양수 → 점진적 확장

---

## 0. 전환 철학

### 유지할 것

- ✅ Redis Streams 이벤트 버스 구조
- ✅ ClickHouse 데이터 웨어하우스
- ✅ 기존 OHLCV 수집 파이프라인
- ✅ 백테스터 엔진 (일부 수정)
- ✅ RL 학습 파이프라인 (용도 변경)

### 버릴 것

- ❌ RL을 **메인 의사결정자**로 사용하는 구조
- ❌ 합성(generated) 데이터로 학습된 정책
- ❌ "모든 시그널에 진입" 방식의 거래 빈도

### 새로 구축할 것

- 🆕 뉴스 수집 + 감성 분류 파이프라인
- 🆕 외국인 선물 수급 실시간 집계
- 🆕 규칙 기반 Decision Engine (Setup A/B/C)
- 🆕 리스크 관리 레이어 (포지션 사이징, MDD)
- 🆕 슬리피지 측정 및 피드백 루프

---

## 1. 마이그레이션 로드맵 (8주)

```
Week 1-2: 데이터 인프라 확장 (뉴스/수급 수집)
Week 3-4: 감성 분류기 + 수급 집계기 구현
Week 5:   Decision Engine + 리스크 레이어 구현
Week 6:   Paper Trading 검증
Week 7:   소액 실전 (1계약) 시작
Week 8+:  주간 Edge 검증 + 파라미터 조정
```

각 Phase는 **이전 Phase가 검증되기 전까지 다음으로 넘어가지 않습니다.**

---

## 2. Redis Streams 스키마 (신규/변경)

### 기존 스트림 (유지)

```
stream:market.tick          # 실시간 체결 (기존)
stream:market.ohlcv.1m      # 1분봉 (기존)
stream:market.orderbook     # 호가 (기존)
```

### 신규 스트림

```
stream:news.raw             # 원본 뉴스 수집
stream:news.scored          # 감성 분류 결과
stream:foreign.flow         # 외국인 선물 수급
stream:macro.overnight      # 야간 해외 지수/환율
stream:signal.candidate     # 후보 시그널 (필터 전)
stream:signal.final         # 최종 진입 시그널
stream:order.request        # 주문 요청
stream:order.fill           # 체결 결과
stream:risk.event           # 리스크 이벤트 (MDD 초과 등)
```

### 메시지 포맷 예시

**`stream:news.raw`**

```json
{
  "news_id": "yh_20260419_001234",
  "source": "yonhap|hankyung|dart|reuters",
  "published_at": 1713513600000,
  "received_at": 1713513602145,
  "title": "FOMC, 기준금리 25bp 인하...",
  "body": "연방준비제도는 ...",
  "url": "https://..."
}
```

**`stream:news.scored`**

```json
{
  "news_id": "yh_20260419_001234",
  "category": "macro_us|geopolitics|samsung|hynix|korea_policy|other",
  "sentiment": 0.73,              // [-1.0, 1.0]
  "impact_score": 0.85,           // [0.0, 1.0]
  "direction_bias": "long|short|neutral",
  "confidence": 0.82,
  "keywords": ["FOMC", "금리인하"],
  "scored_at": 1713513603200
}
```

**`stream:foreign.flow`**

```json
{
  "ts": 1713513660000,
  "cumulative_net_contracts": 1547,    // 당일 누적
  "last_1min_net": 123,
  "last_5min_net": 456,
  "last_30min_net": 1204,
  "trend": "accumulating|distributing|neutral"
}
```

**`stream:signal.final`**

```json
{
  "signal_id": "sig_20260419_093012_001",
  "setup_type": "A_gap_reversion|B_foreign_flow|C_event_reaction",
  "direction": "long|short",
  "entry_price": 385.25,
  "stop_loss": 383.75,
  "take_profit": 388.25,
  "position_size": 1,
  "confidence": 0.78,
  "reason_tags": ["us_gap_0.8%", "foreign_net_+1500", "vwap_breakout"],
  "valid_until": 1713515000000
}
```

---

## 3. ClickHouse 테이블 스키마 (신규)

```sql
-- 뉴스 원본
CREATE TABLE news_raw (
    news_id String,
    source LowCardinality(String),
    published_at DateTime64(3),
    received_at DateTime64(3),
    title String,
    body String,
    url String
) ENGINE = MergeTree()
ORDER BY (published_at, news_id)
TTL toDateTime(published_at) + INTERVAL 2 YEAR;

-- 뉴스 스코어링 결과
CREATE TABLE news_scored (
    news_id String,
    category LowCardinality(String),
    sentiment Float32,
    impact_score Float32,
    direction_bias LowCardinality(String),
    confidence Float32,
    keywords Array(String),
    scored_at DateTime64(3),
    scorer_version LowCardinality(String)
) ENGINE = MergeTree()
ORDER BY (scored_at, news_id);

-- 외국인 수급 스냅샷 (1분마다)
CREATE TABLE foreign_flow_1m (
    ts DateTime,
    cumulative_net_contracts Int32,
    last_1min_net Int32,
    last_5min_net Int32,
    last_30min_net Int32,
    trend LowCardinality(String)
) ENGINE = MergeTree()
ORDER BY ts;

-- 시그널 이력 (전부 기록, 진입 여부와 무관)
CREATE TABLE signals_all (
    signal_id String,
    generated_at DateTime64(3),
    setup_type LowCardinality(String),
    direction LowCardinality(String),
    entry_price Float64,
    stop_loss Float64,
    take_profit Float64,
    confidence Float32,
    executed UInt8,                    -- 실제 진입 여부
    skip_reason String,                -- 스킵 이유 (리스크 한도 등)
    reason_tags Array(String)
) ENGINE = MergeTree()
ORDER BY (generated_at, signal_id);

-- 체결 및 슬리피지 기록 (핵심)
CREATE TABLE order_fills (
    signal_id String,
    order_id String,
    side LowCardinality(String),
    requested_price Float64,
    filled_price Float64,
    slippage_ticks Float32,           -- (filled - requested) / tick_size
    quantity UInt32,
    requested_at DateTime64(3),
    filled_at DateTime64(3),
    latency_ms UInt32,
    order_type LowCardinality(String)  -- market|limit_passive|limit_aggressive
) ENGINE = MergeTree()
ORDER BY (filled_at, order_id);

-- 일일 성과 요약
CREATE TABLE daily_performance (
    trade_date Date,
    n_signals UInt16,
    n_executed UInt16,
    n_wins UInt16,
    n_losses UInt16,
    gross_pnl Float64,
    slippage_cost Float64,
    commission_cost Float64,
    net_pnl Float64,
    max_drawdown Float64,
    ending_equity Float64
) ENGINE = MergeTree()
ORDER BY trade_date;
```

---

## 4. 뉴스 수집 파이프라인

### 4.1 수집 소스 (우선순위)

| 우선순위 | 소스 | 방식 | 지연시간 |
|---------|------|------|----------|
| 1 | DART 공시 | Open API | ~30초 |
| 2 | 연합뉴스 경제 | RSS + 크롤링 | ~1분 |
| 3 | 한국경제 증권 | RSS | ~2분 |
| 4 | Reuters 한국 | RSS | ~1분 |
| 5 | Investing.com | API | ~30초 |
| 6 | 네이버 뉴스 속보 | RSS | ~3분 |

### 4.2 수집 워커 구조

```python
# services/news_collector/main.py
import asyncio
import redis.asyncio as redis
from typing import List

class NewsCollector:
    def __init__(self, redis_client, sources: List[NewsSource]):
        self.redis = redis_client
        self.sources = sources
        self.seen_ids = LRUCache(maxsize=10000)  # 중복 제거

    async def collect_loop(self, source: NewsSource):
        while True:
            try:
                items = await source.fetch()
                for item in items:
                    if item.news_id in self.seen_ids:
                        continue
                    self.seen_ids[item.news_id] = True
                    await self.redis.xadd(
                        "stream:news.raw",
                        item.to_dict(),
                        maxlen=100000  # 최대 10만건 유지
                    )
            except Exception as e:
                logger.error(f"Collection error {source.name}: {e}")
            await asyncio.sleep(source.poll_interval)

    async def run(self):
        tasks = [self.collect_loop(s) for s in self.sources]
        await asyncio.gather(*tasks)
```

### 4.3 주요 고려사항

- **중복 제거:** URL 해시 또는 title SHA256
- **Rate Limiting:** 소스별 최소 10초 간격
- **장애 격리:** 한 소스 장애가 다른 소스에 영향 없도록
- **시간 동기화:** 모든 타임스탬프는 UTC 밀리초

---

## 5. 뉴스 감성 분류기

### 5.1 모델 선택 (단계별)

**Phase 1 (빠른 구축):** OpenAI GPT-4o-mini API

- 장점: 구현 1일, 한국어 성능 우수, 분류 + 감성 + 카테고리 동시 처리
- 단점: API 비용 (뉴스당 약 $0.001), 외부 의존성

**Phase 2 (안정화):** FinBERT-Korean 파인튜닝 또는 KLUE-BERT

- 장점: 자체 호스팅, 지연시간 낮음
- 단점: 학습 데이터 수집 필요 (최소 5천건 라벨)

**Phase 3 (최적화):** Phase 1 + Phase 2 앙상블

### 5.2 분류 프롬프트 (GPT-4o-mini 기준)

```python
SCORING_PROMPT = """
다음 뉴스가 코스피200 선물 가격에 미칠 영향을 분석하세요.

뉴스 제목: {title}
뉴스 본문: {body_first_500_chars}

다음 JSON 형식으로만 응답하세요 (설명 없이):
{{
  "category": "macro_us|macro_kr|geopolitics|samsung|hynix|
               korea_policy|sector_event|corporate|other",
  "sentiment": <-1.0 ~ 1.0 실수. 코스피 선물에 대한 영향>,
  "impact_score": <0.0 ~ 1.0 실수. 가격 이동 유발 가능성>,
  "direction_bias": "long|short|neutral",
  "confidence": <0.0 ~ 1.0. 판단 확신도>,
  "keywords": [<핵심 키워드 최대 5개>],
  "reasoning": "<한 줄 요약>"
}}

중요 판단 기준:
- FOMC/CPI/고용지표: impact 0.8+, direction 명확
- 북한/지정학 리스크: sentiment 음수, impact 0.6+
- 삼성/SK하이닉스 단일 기업 이슈: impact 0.4~0.6
- 일반 기업 실적: impact 0.2 이하
- 반복되는 루머: impact 0.1 이하
"""
```

### 5.3 스코어링 워커

```python
# services/news_scorer/main.py
class NewsScorer:
    async def process_loop(self):
        # Consumer group으로 읽기 (재시작 복구)
        while True:
            messages = await self.redis.xreadgroup(
                groupname="scorer",
                consumername=self.worker_id,
                streams={"stream:news.raw": ">"},
                count=10,
                block=5000
            )

            for stream, msgs in messages:
                for msg_id, data in msgs:
                    scored = await self.score(data)
                    await self.redis.xadd("stream:news.scored", scored)
                    await self.save_to_clickhouse(scored)
                    await self.redis.xack("stream:news.raw", "scorer", msg_id)

    async def score(self, news_data):
        # GPT-4o-mini API 호출 + 결과 파싱
        # 실패 시 retry 3회, 그래도 실패면 neutral로 기본값
        ...
```

### 5.4 엣지 케이스

- **JSON 파싱 실패:** 3회 재시도 → neutral (0.0) 기본값
- **API 타임아웃:** 5초 제한, 타임아웃 시 스킵
- **중복 뉴스:** 동일 title 10분 내 재등장 시 스코어 재사용
- **극단값:** sentiment/impact > 0.95 시 사람 검토 알림 (Slack)

---

## 6. 외국인 수급 실시간 집계기

### 6.1 데이터 소스

국내 브로커 API를 통한 투자자별 매매동향:

- **한국투자증권 Open API:** 실시간 투자자별 체결 (5초 간격)
- **키움증권 OpenAPI+:** 투자자별 누적 매매량
- **KRX 공식:** 장 중 10분 지연 (백업용)

### 6.2 집계 로직

```python
# services/foreign_flow/aggregator.py
class ForeignFlowAggregator:
    def __init__(self):
        self.daily_cumulative = 0
        self.buffer_1m = deque(maxlen=60)   # 최근 1분
        self.buffer_5m = deque(maxlen=300)  # 최근 5분
        self.buffer_30m = deque(maxlen=1800)

    async def on_tick(self, tick):
        # 외국인 순매수 델타 계산
        delta = tick.foreign_buy_volume - tick.foreign_sell_volume
        self.daily_cumulative += delta

        now = tick.timestamp
        self.buffer_1m.append((now, delta))
        self.buffer_5m.append((now, delta))
        self.buffer_30m.append((now, delta))

        # 매 1분마다 스트림에 발행
        if now.second == 0:
            await self.publish_snapshot(now)

    def compute_trend(self):
        # 최근 5분 누적 vs 30분 평균
        recent = sum(d for _, d in self.buffer_5m)
        window_30m = sum(d for _, d in self.buffer_30m)
        avg_5m_rate = window_30m / 6

        if recent > avg_5m_rate * 1.5 and recent > 500:
            return "accumulating"
        elif recent < avg_5m_rate * 1.5 and recent < -500:
            return "distributing"
        return "neutral"
```

### 6.3 임계값 (초기 기준, 백테스트로 보정)

```python
FOREIGN_FLOW_THRESHOLDS = {
    "strong_buy": 1500,      # 계약 수, 30분 누적
    "moderate_buy": 800,
    "neutral_upper": 300,
    "neutral_lower": -300,
    "moderate_sell": -800,
    "strong_sell": -1500,
}
```

---

## 7. Decision Engine (핵심)

### 7.1 구조

```
┌──────────────────────────────────────┐
│  Signal Generator                    │
│  ├─ Setup A: Gap Reversion           │
│  ├─ Setup B: Foreign Flow            │
│  └─ Setup C: Event Reaction          │
└──────────────┬───────────────────────┘
               ↓ Candidate Signal
┌──────────────────────────────────────┐
│  Risk Filter Layer (순차 적용)       │
│  1. 시간대 필터                      │
│  2. 일일 MDD 한도                    │
│  3. 연속 손실 체크                   │
│  4. 변동성 필터 (ATR 극단)           │
│  5. 유동성 필터 (호가 스프레드)      │
└──────────────┬───────────────────────┘
               ↓ Pass
┌──────────────────────────────────────┐
│  (Optional) RL Auxiliary Filter      │
│  → 진입 적합 확률 ≥ 0.6              │
└──────────────┬───────────────────────┘
               ↓ Final Signal
         Order Router
```

### 7.2 Setup A: 야간 갭 리버전

```python
# engines/setup_a_gap_reversion.py

class SetupAGapReversion:
    """
    전일 야간 해외 지수 변동 → 코스피 갭 → 되돌림 진입
    """

    async def check(self, context) -> Optional[Signal]:
        # 1. 전제조건: 장 시작 후 10~90분 사이만
        if not self.is_valid_time(context.now):
            return None

        # 2. 야간 갭 크기 확인
        overnight = context.macro_overnight
        if abs(overnight.sp500_change_pct) < 0.5:
            return None  # 갭 너무 작음

        # 3. 코스피 야간선물(Eurex) 방향 일치 확인
        if sign(overnight.kospi_night) != sign(overnight.sp500_change_pct):
            return None

        # 4. 당일 시가 갭 확인
        open_price = context.today_open
        prev_close = context.prev_close
        gap_pct = (open_price - prev_close) / prev_close * 100

        if abs(gap_pct) < 0.3:
            return None

        # 5. 되돌림 확인 (갭의 30~50%)
        current = context.current_price
        retrace_pct = (open_price - current) / (open_price - prev_close)

        if not (0.30 <= retrace_pct <= 0.55):
            return None

        # 6. 시그널 생성
        direction = "long" if gap_pct > 0 else "short"
        atr = context.atr_14
        entry = current
        stop = current - (1.5 * atr) if direction == "long" else current + (1.5 * atr)
        target = prev_close + (open_price - prev_close) * 0.9

        return Signal(
            setup_type="A_gap_reversion",
            direction=direction,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=self.calculate_confidence(context),
            reason_tags=[
                f"sp500_gap_{overnight.sp500_change_pct:+.2f}%",
                f"kr_gap_{gap_pct:+.2f}%",
                f"retrace_{retrace_pct:.2%}"
            ],
            valid_until=context.now + timedelta(minutes=10)
        )

    def is_valid_time(self, now):
        market_open = now.replace(hour=9, minute=0)
        return timedelta(minutes=10) <= (now - market_open) <= timedelta(minutes=90)
```

### 7.3 Setup B: 외국인 수급 + 뉴스 일치

```python
class SetupBForeignFlow:
    """
    장 초반 30분 외국인 수급 + 매크로 뉴스 방향 일치
    """

    async def check(self, context) -> Optional[Signal]:
        # 1. 시간대: 10:00 ~ 14:00
        if not self.is_valid_time(context.now):
            return None

        # 2. 외국인 수급 방향
        flow = context.foreign_flow
        if abs(flow.cumulative_net_contracts) < 1500:
            return None

        flow_dir = "long" if flow.cumulative_net_contracts > 0 else "short"

        # 3. 최근 2시간 내 매크로 뉴스 확인
        recent_news = await self.get_recent_impactful_news(
            context.now, hours=2,
            categories=["macro_us", "macro_kr", "geopolitics", "korea_policy"],
            min_impact=0.6
        )

        if not recent_news:
            return None

        # 4. 뉴스 방향과 수급 방향 일치
        news_direction = self.aggregate_direction(recent_news)
        if news_direction != flow_dir:
            return None

        # 5. VWAP 필터
        if flow_dir == "long" and context.current_price < context.vwap:
            return None
        if flow_dir == "short" and context.current_price > context.vwap:
            return None

        # 6. 시그널 생성
        atr = context.atr_14
        entry = context.current_price
        stop = entry - 1.5 * atr if flow_dir == "long" else entry + 1.5 * atr
        target = entry + 3.0 * atr if flow_dir == "long" else entry - 3.0 * atr

        return Signal(
            setup_type="B_foreign_flow",
            direction=flow_dir,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=self.calculate_confidence(flow, recent_news),
            reason_tags=[
                f"foreign_net_{flow.cumulative_net_contracts:+d}",
                f"news_impact_{max(n.impact_score for n in recent_news):.2f}",
                "vwap_aligned"
            ],
            valid_until=context.now + timedelta(minutes=20)
        )
```

### 7.4 Setup C: 이벤트 리액션

```python
class SetupCEventReaction:
    """
    예정된 매크로 이벤트 발표 직후 15분 방향 확인 후 순응
    """

    SCHEDULED_EVENTS = [
        "FOMC_rate_decision",
        "BOK_rate_decision",
        "US_CPI", "US_NFP",
        "KR_export_data",
    ]

    async def check(self, context) -> Optional[Signal]:
        # 1. 예정 이벤트 직후인지 확인
        recent_event = await self.get_recent_scheduled_event(
            context.now, minutes=15
        )
        if not recent_event:
            return None

        # 2. 발표 후 15분 고저점 확인
        high_15m = context.last_15min_high
        low_15m = context.last_15min_low
        current = context.current_price

        # 3. 브레이크아웃만 진입 (역방향 금지)
        atr = context.atr_14
        if current > high_15m and (current - high_15m) < 0.5 * atr:
            direction = "long"
            entry = current
        elif current < low_15m and (low_15m - current) < 0.5 * atr:
            direction = "short"
            entry = current
        else:
            return None

        # 4. 이벤트당 최대 1회 진입 보장
        if await self.already_traded_this_event(recent_event.event_id):
            return None

        stop = low_15m if direction == "long" else high_15m
        target = entry + 2.5 * atr if direction == "long" else entry - 2.5 * atr

        return Signal(
            setup_type="C_event_reaction",
            direction=direction,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=0.70,  # 이벤트 반응은 평균적 신뢰도
            reason_tags=[
                f"event_{recent_event.event_type}",
                f"breakout_15m"
            ],
            valid_until=context.now + timedelta(minutes=30)
        )
```

---

## 8. 리스크 필터 레이어

### 8.1 순차 필터 적용

```python
class RiskFilterLayer:
    def __init__(self, config, state_tracker):
        self.config = config
        self.state = state_tracker

    async def filter(self, signal: Signal) -> FilterResult:
        # 1. 시간대 필터
        if not self.is_tradable_time(signal.timestamp):
            return FilterResult.REJECT("outside_trading_hours")

        # 2. 일일 MDD 한도
        if self.state.daily_pnl_pct < -self.config.daily_mdd_limit:
            return FilterResult.REJECT("daily_mdd_exceeded")

        # 3. 주간 MDD 한도
        if self.state.weekly_pnl_pct < -self.config.weekly_mdd_limit:
            return FilterResult.REJECT("weekly_mdd_exceeded")

        # 4. 연속 손실 체크
        if self.state.consecutive_losses >= 4:
            # 포지션 사이즈 50% 축소
            signal.position_size = max(1, signal.position_size // 2)

        # 5. 일일 거래 횟수 한도
        if self.state.daily_trade_count >= self.config.max_daily_trades:
            return FilterResult.REJECT("max_daily_trades")

        # 6. 변동성 필터 (ATR 극단)
        if self.state.current_atr > self.state.atr_90th_percentile:
            return FilterResult.REJECT("volatility_too_high")

        # 7. 유동성 필터 (호가 스프레드)
        spread_ticks = self.state.current_spread_ticks
        if spread_ticks > 2:
            return FilterResult.REJECT("spread_too_wide")

        # 8. 포지션 중복 방지
        if self.state.has_open_position():
            return FilterResult.REJECT("position_already_open")

        return FilterResult.PASS(signal)

    def is_tradable_time(self, ts) -> bool:
        """
        거래 허용 시간대:
        - 09:00 ~ 10:30 (변동성 + 유동성)
        - 14:30 ~ 15:30 (종가 베팅)

        거래 금지 시간대:
        - 11:30 ~ 13:30 (점심 유동성 고갈)
        - 15:30 이후 (청산 임박)
        """
        t = ts.time()
        if time(9, 0) <= t <= time(10, 30):
            return True
        if time(14, 30) <= t <= time(15, 20):
            return True
        return False
```

### 8.2 설정값 (초기)

```python
# config/risk.yaml
risk:
  account_equity: 5_000_000
  daily_mdd_limit: 0.03          # 3%
  weekly_mdd_limit: 0.07         # 7%
  max_position_risk_pct: 0.015   # 1.5%
  max_daily_trades: 3
  max_position_size: 2           # 계약

slippage:
  target_avg_ticks: 0.2
  alert_threshold_ticks: 0.5
  review_threshold_weekly: 1.0
```

### 8.3 포지션 사이징

```python
def calculate_position_size(signal, account_equity, config) -> int:
    """
    Fixed Fractional Sizing
    - 1 tick = 0.05 point, 1 point = 50,000원 (미니선물 기준 가정, 실제 계약 명세 확인 필수)
    """
    stop_distance = abs(signal.entry_price - signal.stop_loss)
    risk_krw = account_equity * config.max_position_risk_pct

    # 1계약당 손절 금액
    krw_per_contract = stop_distance * 50_000  # 계약 승수 확인 필수

    raw_size = risk_krw / krw_per_contract
    size = max(1, min(int(raw_size), config.max_position_size))

    # 연속 손실 시 축소
    if state.consecutive_losses >= 4:
        size = max(1, size // 2)

    return size
```

---

## 9. 주문 실행 (슬리피지 최소화)

### 9.1 Passive Maker 전략

```python
class PassiveOrderRouter:
    """
    시장가 주문 금지. 지정가 + Passive Maker만 사용.
    """

    async def execute(self, signal: Signal) -> OrderResult:
        # 1. 현재 호가 확인
        orderbook = await self.get_orderbook()

        # 2. 지정가 결정 (매수: 최우선 매수호가, 매도: 최우선 매도호가)
        if signal.direction == "long":
            limit_price = orderbook.bid[0].price  # 매수 1호가에 걸기
        else:
            limit_price = orderbook.ask[0].price

        # 3. 주문 제출
        order_id = await self.broker.place_limit_order(
            symbol=signal.symbol,
            side=signal.direction,
            quantity=signal.position_size,
            price=limit_price,
            time_in_force="IOC_THEN_CANCEL"  # 즉시 체결 못하면 취소 아님
        )

        # 4. 최대 대기 시간 (30초)
        filled = await self.wait_for_fill(order_id, timeout=30)

        # 5. 체결 안 되면 포기 (쫓아가지 않음)
        if not filled:
            await self.broker.cancel_order(order_id)
            return OrderResult.MISSED("passive_not_filled")

        # 6. 슬리피지 기록
        slippage = (filled.price - signal.entry_price) / 0.05  # tick 단위
        if signal.direction == "short":
            slippage = -slippage

        await self.record_fill(signal, filled, slippage)
        return OrderResult.FILLED(filled)
```

### 9.2 손절/익절 주문

```python
# 진입 체결 즉시 손절과 익절을 OCO로 자동 등록
async def register_exit_orders(filled_entry, signal):
    # OCO (One-Cancels-Other) 주문
    await broker.place_oco(
        stop_loss_price=signal.stop_loss,
        take_profit_price=signal.take_profit,
        quantity=filled_entry.quantity,
        parent_order_id=filled_entry.order_id
    )

    # 강제 청산 타이머 설정 (14:50)
    await schedule_force_close(
        signal_id=signal.signal_id,
        close_time=signal.valid_until
    )
```

---

## 10. 슬리피지 모니터링

### 10.1 일일 측정

```sql
-- 일일 슬리피지 리포트
SELECT
    toDate(filled_at) AS date,
    count() AS n_fills,
    avg(slippage_ticks) AS avg_slippage,
    quantile(0.95)(slippage_ticks) AS p95_slippage,
    sum(slippage_ticks * 0.05 * 50000) AS total_slippage_cost_krw
FROM order_fills
WHERE filled_at >= today() - 7
GROUP BY date
ORDER BY date DESC;
```

### 10.2 주간 피드백 루프

```python
# jobs/weekly_edge_review.py
async def weekly_review():
    """
    매주 월요일 새벽 실행.
    - 지난주 실거래 vs 백테스트 결과 비교
    - 슬리피지가 임계값 초과 시 알림
    - Setup별 승률 및 EV 검증
    """
    results = await query_clickhouse("""
        SELECT
            s.setup_type,
            count() AS n_trades,
            sum(if(o.filled_price < s.stop_loss, 0, 1)) * 1.0 / count() AS win_rate,
            avg(o.slippage_ticks) AS avg_slippage,
            sum(o.realized_pnl) AS total_pnl
        FROM signals_all s
        JOIN order_fills o ON s.signal_id = o.signal_id
        WHERE s.generated_at >= now() - INTERVAL 7 DAY
        GROUP BY s.setup_type
    """)

    for r in results:
        # EV 계산
        ev = r.win_rate * r.avg_win - (1 - r.win_rate) * r.avg_loss - r.avg_slippage
        if ev < 0:
            await send_alert(f"⚠️ Setup {r.setup_type} EV 음수: {ev:.2f}")
        if r.avg_slippage > 0.5:
            await send_alert(f"⚠️ Setup {r.setup_type} 슬리피지 과다: {r.avg_slippage:.2f} ticks")
```

---

## 11. RL 파이프라인 재활용

### 11.1 용도 변경: 메인 → 보조 필터

기존 RL 모델을 버리지 말고, **진입 적합성 판단 보조기**로 재학습합니다.

```python
# RL의 새 역할
# State:  [규칙 기반 시그널의 특징 + 현재 시장 상태]
# Action: {PASS, SKIP}  (진입 여부만 결정)
# Reward: 진입 결정 후 실제 PnL
```

### 11.2 새 학습 데이터 구성

```python
# 학습 샘플 생성
{
    "state": {
        "setup_type": "B_foreign_flow",
        "signal_confidence": 0.78,
        "foreign_flow_strength": 1547,
        "news_impact": 0.85,
        "current_vol_pct": 0.4,
        "time_of_day": 0.45,        # 0~1 normalized
        "recent_5d_winrate": 0.53,
        "current_drawdown": 0.02,
    },
    "action": "PASS",
    "reward": 2.3,  # 실제 ticks
}
```

### 11.3 전환 조건

RL 필터는 **규칙 시스템이 3개월 이상 안정적으로 EV 양수**를 기록한 이후에만 활성화합니다. 초기에는 RL 추천을 로깅만 하고 실제 의사결정에는 반영하지 않습니다.

---

## 12. 검증 및 롤아웃 계획

### Phase 1: 데이터 준비 (Week 1~2)

- [ ] 뉴스 수집기 배포, 24시간 연속 운영 확인
- [ ] 감성 분류기 배포, 누적 1,000건 스코어링
- [ ] 외국인 수급 집계기 배포, 실제 KRX 공시 데이터와 비교
- [ ] ClickHouse 신규 테이블 생성 및 적재 확인

### Phase 2: 시뮬레이션 (Week 3~4)

- [ ] 최근 6개월 과거 데이터로 Setup A/B/C 백테스트
- [ ] 슬리피지 0.3 tick 가정 시 Setup별 EV 계산
- [ ] EV 음수인 Setup은 파라미터 재조정 또는 비활성화
- [ ] 목표: Setup당 거래 30회 이상, EV > 0.5 tick

### Phase 3: Paper Trading (Week 5~6)

- [ ] 실시간 신호 생성, 실제 주문은 모의
- [ ] 최소 100회 신호 누적 관찰
- [ ] 백테스트와 실시간의 신호 발생 일치도 > 95%
- [ ] 목표: 2주간 기록 승률 및 EV가 백테스트의 ±20% 이내

### Phase 4: 소액 실전 (Week 7~8)

- [ ] 1계약 고정, 일일 최대 2회 거래
- [ ] 2주 기간 중 다음 조건 모두 충족 시 계속:
  - 일일 MDD -3% 초과 없음
  - 누적 수익 > 슬리피지 + 수수료
  - 실거래 슬리피지 ≤ 0.4 tick 평균

### Phase 5: 확장 (Week 9+)

- 위 조건 충족 시 1→2계약 증량
- 각 증량 단계에서 2주 검증 기간 유지
- 2계약 안정화 후 RL 보조 필터 도입 검토

---

## 13. 모니터링 대시보드 (operational dashboard)

### 필수 패널

```
패널 1: 실시간 P&L
  - 당일 PnL 곡선 (분 단위)
  - 현재 포지션 및 미실현 손익

패널 2: 시그널 발생 이력
  - Setup별 시그널 카운트
  - 실행/스킵 비율

패널 3: 슬리피지 추이
  - 일별 평균 슬리피지 (tick)
  - 주문 타입별 비교

패널 4: 시스템 건강성
  - Redis Streams lag
  - 뉴스 수집 지연시간
  - API 에러율

패널 5: 리스크 지표
  - 연속 손실 카운터
  - 일일/주간 MDD 대비 한도 사용률
  - VaR (95%)
```

---

## 14. 실패 조건 및 Kill Switch

다음 조건 중 하나라도 충족되면 **시스템 자동 정지**:

```python
KILL_CONDITIONS = [
    "daily_loss >= account * 0.03",
    "weekly_loss >= account * 0.07",
    "consecutive_losses >= 6",
    "api_error_rate_5m >= 0.2",
    "news_pipeline_lag_seconds >= 300",
    "clickhouse_insert_fail_rate >= 0.1",
]
```

자동 정지 시:

1. 모든 오픈 포지션 즉시 시장가 청산
2. 신규 주문 차단
3. Slack/Telegram 알림
4. 다음 거래일 시작 전 수동 재개 승인 필요

---

## 15. 디렉터리 구조 (제안)

```
kospi200-trading/
├── services/
│   ├── news_collector/          # 뉴스 수집
│   ├── news_scorer/             # 감성 분류
│   ├── foreign_flow/            # 외국인 수급 집계
│   ├── macro_overnight/         # 야간 해외 지수
│   ├── signal_generator/        # Setup A/B/C
│   ├── risk_filter/             # 리스크 필터
│   ├── order_router/            # Passive Maker
│   └── monitor/                 # 모니터링
├── engines/
│   ├── setup_a_gap_reversion.py
│   ├── setup_b_foreign_flow.py
│   └── setup_c_event_reaction.py
├── backtesting/
│   ├── engine.py                # 기존 엔진 확장
│   └── slippage_model.py        # 현실적 슬리피지
├── jobs/
│   ├── weekly_edge_review.py
│   └── daily_performance_report.py
├── config/
│   ├── risk.yaml
│   ├── setups.yaml
│   └── news_sources.yaml
├── infra/
│   ├── clickhouse/migrations/
│   ├── redis/
│   └── docker-compose.yml
└── tests/
    ├── test_setups/
    ├── test_risk/
    └── test_integration/
```

---

## 16. 최종 체크리스트

구현 전 반드시 확인:

- [ ] 미니선물 계약 명세 정확 반영 (1틱 가치, 증거금, 수수료율)
- [ ] 브로커 API 초당 호출 한도 확인
- [ ] ClickHouse 디스크 용량 (뉴스 + 틱 데이터 최소 1TB 예상)
- [ ] Redis 메모리 용량 (Streams maxlen 기준 계산)
- [ ] 장애 복구 시나리오 (재시작 시 오픈 포지션 인식)
- [ ] 법적 검토: 자동매매 관련 브로커 약관
- [ ] 세무: 파생상품 양도세 계산 로직

---

## 부록 A: 초기 파라미터 튜닝 범위

백테스트로 최적화할 파라미터와 초기 탐색 범위:

| 파라미터 | 초기값 | 탐색 범위 |
|---------|-------|-----------|
| Setup A 갭 최소치 | 0.3% | 0.2% ~ 0.6% |
| Setup A 되돌림 범위 | 0.30~0.55 | 0.25~0.60 |
| Setup B 수급 임계값 | 1500계약 | 1000~2500 |
| Setup B 뉴스 impact | 0.6 | 0.4~0.8 |
| Setup C 브레이크 버퍼 | 0.5 ATR | 0.3~1.0 |
| 손절 ATR 배수 | 1.5 | 1.0~2.5 |
| 익절 ATR 배수 | 3.0 | 2.0~4.0 |
| 일일 MDD 한도 | 3% | 2%~5% |

**중요:** Walk-Forward Analysis 필수. In-sample 최적화 후 Out-of-sample에서 성능 50% 이상 유지되어야 채택.

---

## 부록 B: 긴급 연락 및 롤백 절차

1. 시스템 이상 감지 → Kill Switch 자동 작동
2. 모든 포지션 청산 확인
3. 로그 수집 (ClickHouse + Redis + 애플리케이션 로그)
4. 24시간 내 근본 원인 분석 완료 전까지 재개 금지
5. 문제 해결 후 Paper Trading 최소 3일 검증 후 재개

---

**이 문서는 살아있는 문서입니다. 실제 운영 결과를 바탕으로 주간 단위로 업데이트하세요.**
