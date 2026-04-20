# Phase 1 — 데이터 인프라 (Week 1-2)

**Status:** Draft (needs user review)
**Parent:** `docs/plans/2026-04-20-futures-paradigm-master.md`
**Target branch:** `feat/futures-paradigm-phase1`
**Depends on:** 마스터 spec의 Q1-Q4 답변 확정
**Blocks:** Phase 2, 3

---

## 1. 목표

원본 지침서 §2 ~ §4, §6, §10의 **수집/저장 레이어** 만 구현한다. 스코어링/시그널 생성/주문은 건드리지 않는다. Phase 1 완료 시 신규 시스템은 "읽기 전용 데이터 수집기"로만 동작한다.

**완료 정의:**
- 4개 신규 서비스 데몬이 24시간 무중단으로 동작
- 6개 ClickHouse 테이블에 실데이터 적재 (스코어 전 raw만)
- 5개 Redis stream이 publish/consumer group 준비 완료
- 기존 `rl_mppo` 운용은 **영향 없음** (사이드카 방식)

---

## 2. Redis Streams — 확정 스키마

### 2.1 신규 스트림 목록

| Stream | Publisher | Consumer (Phase 2+) | Maxlen | Approx Volume |
|--------|-----------|---------------------|--------|---------------|
| `stream:news.raw` | `news_collector` | `news_scorer` | 100,000 | 500-2,000/일 |
| `stream:foreign.flow.raw` | `foreign_flow_collector` | `foreign_flow_aggregator` | 50,000 | 50-100/일 (10분 단위) |
| `stream:macro.overnight` | `macro_overnight_collector` | `decision_engine` | 5,000 | 20-50/일 |
| `stream:signal.candidate` | (Phase 3) | (Phase 3) | 10,000 | TBD |
| `stream:signal.final` | (Phase 3) | (Phase 3) | 10,000 | TBD |

**정의만 하고 publish는 Phase 3에서 시작하는 스트림**: `stream:signal.*`, `stream:order.*`, `stream:risk.event`. Phase 1은 타입/스키마만 확정.

### 2.2 `stream:news.raw` 메시지 스키마 (확정)

```python
{
    "news_id": str,              # "{source}_{yyyymmdd}_{seq}" — 전역 유일
    "source": str,               # LowCardinality: dart|yonhap|hankyung|reuters|naver|investing|mk
    "published_at_ms": int,      # UTC milliseconds
    "received_at_ms": int,
    "title": str,
    "body": str,                 # 500자 이상일 경우 본문 앞 2000자만
    "url": str,
    "source_version": str,       # 수집기 버전 ("dart-v1", "yonhap-v1")
    "lang": str,                 # "ko"|"en"
    "_json_keywords": str,       # JSON 배열 직렬화 (RSS tag 등 선택적)
}
```

**생성 규칙:**
- `news_id` 중복 방지: `LRUCache(maxsize=20_000)` 메모리 + Redis Set `news:seen:v1` (7일 TTL)
- 본문 길이 제한: UTF-8 2,000자 초과 시 절단 + `...[truncated]` 추가
- 결측 필드: `published_at_ms`는 `received_at_ms`로 폴백, 로그에 기록

### 2.3 `stream:foreign.flow.raw` 메시지 스키마 (확정)

**마스터 Q1 결정 전제: KRX Open API 기반 10분 지연 허용.**

```python
{
    "ts_ms": int,                         # 데이터 시점 (예: 09:00~09:09 구간의 09:10 발표)
    "received_at_ms": int,
    "source": str,                        # "krx_openapi_v1"|"kiwoom_v1"
    "asset_class": str,                   # "futures"|"stocks_aggregate"
    "symbol": str,                        # "101S6000" (선물) 또는 "KOSPI200_INDEX"
    "foreign_net_contracts": int,         # 순매수 (+=매수 우위)
    "institution_net_contracts": int,
    "individual_net_contracts": int,
    "cumulative_foreign_today": int,
    "bucket_minutes": int,                # 10 (KRX) | 1 (키움)
}
```

**금지:** KIS `H0STCNT0` 틱을 쪼개 투자자별을 추정하지 않는다 (데이터 부재 — 마스터 §Q1).

### 2.4 `stream:macro.overnight` 메시지 스키마 (확정)

```python
{
    "ts_ms": int,
    "session": str,                       # "overnight_us_close" | "overnight_eurex_close"
    "indices": {                          # 지표 일괄
        "sp500_close": float,
        "sp500_change_pct": float,
        "nasdaq_close": float,
        "nasdaq_change_pct": float,
        "eurex_kospi_night_close": float | None,
        "eurex_kospi_night_change_pct": float | None,
    },
    "fx": {
        "usdkrw": float,
        "usdkrw_change_pct": float,
        "dxy": float | None,
    },
    "treasury": {
        "us10y_yield": float | None,
        "vix": float | None,
    },
    "collected_from": list[str],          # ["yahoo_finance", "ecos", ...]
}
```

**수집 타이밍:**
- `overnight_us_close`: 매일 06:30 KST (미국장 마감 06:00 EDT + 여유)
- `overnight_eurex_close`: 매일 06:00 KST (Eurex KOSPI 야간 05:00 KST 마감)

### 2.5 Consumer Group 규약

- Group 이름: `"{service}-v1"` (예: `"news_scorer-v1"`). 버전 업 시 `-v2`로 신규 생성 (offset 리셋).
- Consumer 이름: `"{service}-{hostname}-{pid}"` — 재시작 시 재사용 가능.
- Idle timeout: 60s (이상 시 XPENDING 후 XCLAIM으로 회수).
- Ack: 메시지 처리 + ClickHouse 적재 성공 **후** `XACK`.

---

## 3. ClickHouse 마이그레이션

### 3.1 마이그레이션 인프라 신설

`infra/clickhouse/migrations/` 디렉터리 신설.
- `V1__create_futures_paradigm_tables.sql` — Phase 1 테이블 (본 문서)
- `V2__create_news_scored.sql` — Phase 2에서 추가 (예약)
- `V3__create_order_fills.sql` — Phase 4 (예약)

**적용 도구:** 신규 스크립트 `scripts/migrations/apply_clickhouse_migrations.py`. 적용 이력은 `kospi.schema_migrations` 테이블에 기록.

### 3.2 Phase 1 테이블 (모두 `kospi` 데이터베이스)

```sql
-- 1. 뉴스 원본 (Phase 1에서 채움 시작)
CREATE TABLE IF NOT EXISTS kospi.news_raw (
    news_id String,
    source LowCardinality(String),
    published_at DateTime64(3, 'UTC'),
    received_at DateTime64(3, 'UTC'),
    title String,
    body String,
    url String,
    source_version LowCardinality(String),
    lang LowCardinality(String),
    keywords Array(String)
) ENGINE = MergeTree()
ORDER BY (published_at, news_id)
PARTITION BY toYYYYMM(published_at)
TTL toDateTime(published_at) + INTERVAL 2 YEAR;

-- 2. 외국인/기관/개인 수급 (10분 단위 또는 소스별)
CREATE TABLE IF NOT EXISTS kospi.investor_flow_raw (
    ts DateTime64(3, 'UTC'),
    received_at DateTime64(3, 'UTC'),
    source LowCardinality(String),
    asset_class LowCardinality(String),
    symbol LowCardinality(String),
    foreign_net_contracts Int32,
    institution_net_contracts Int32,
    individual_net_contracts Int32,
    cumulative_foreign_today Int32,
    bucket_minutes UInt8
) ENGINE = MergeTree()
ORDER BY (symbol, ts)
PARTITION BY toYYYYMM(ts)
TTL toDateTime(ts) + INTERVAL 1 YEAR;

-- 3. 매크로 야간 스냅샷
CREATE TABLE IF NOT EXISTS kospi.macro_overnight (
    ts DateTime64(3, 'UTC'),
    session LowCardinality(String),
    sp500_close Float64,
    sp500_change_pct Float32,
    nasdaq_close Float64,
    nasdaq_change_pct Float32,
    eurex_kospi_close Nullable(Float64),
    eurex_kospi_change_pct Nullable(Float32),
    usdkrw Float64,
    usdkrw_change_pct Float32,
    dxy Nullable(Float64),
    us10y_yield Nullable(Float32),
    vix Nullable(Float32),
    collected_from Array(String)
) ENGINE = ReplacingMergeTree(ts)
ORDER BY (session, toDate(ts))
PARTITION BY toYYYYMM(ts)
TTL toDateTime(ts) + INTERVAL 5 YEAR;

-- 4. 마이그레이션 이력
CREATE TABLE IF NOT EXISTS kospi.schema_migrations (
    version String,
    applied_at DateTime DEFAULT now(),
    checksum String
) ENGINE = MergeTree() ORDER BY version;

-- 5. (스키마 예약) 시그널 전체 이력 — Phase 3에서 채움 시작
CREATE TABLE IF NOT EXISTS kospi.signals_all (
    signal_id String,
    generated_at DateTime64(3, 'UTC'),
    setup_type LowCardinality(String),
    direction LowCardinality(String),
    entry_price Float64,
    stop_loss Float64,
    take_profit Float64,
    confidence Float32,
    executed UInt8,
    skip_reason String,
    reason_tags Array(String)
) ENGINE = MergeTree()
ORDER BY (generated_at, signal_id)
PARTITION BY toYYYYMM(generated_at)
TTL toDateTime(generated_at) + INTERVAL 5 YEAR;

-- 6. (스키마 예약) 일일 성과 — Phase 4에서 채움 시작
CREATE TABLE IF NOT EXISTS kospi.daily_performance (
    trade_date Date,
    n_signals UInt16,
    n_executed UInt16,
    n_wins UInt16,
    n_losses UInt16,
    gross_pnl Float64,
    slippage_cost Float64,
    commission_cost Float64,
    net_pnl Float64,
    max_drawdown Float32,
    ending_equity Float64
) ENGINE = ReplacingMergeTree(trade_date)
ORDER BY trade_date;
```

**참고:** 원본 §3의 `order_fills`, `news_scored`는 Phase 2/4 spec에서 정의.

### 3.3 TTL 정책 (CLAUDE.md 규칙 준수)

| 테이블 | TTL | 이유 |
|--------|-----|------|
| `news_raw` | 2년 | 과거 이벤트 분석 |
| `investor_flow_raw` | 1년 | 백테스트 충분 |
| `macro_overnight` | 5년 | 저용량, 장기 상관 분석 |
| `signals_all` | 5년 | Edge 추적 |
| `daily_performance` | 무기한 | 연간 P&L |

---

## 4. 서비스 구현 — 4개 신규 데몬

### 4.1 디렉터리 구조 (신규)

```
kis_unified_sts/
├── services/
│   ├── news_collector/
│   │   ├── __init__.py
│   │   └── main.py                 # 데몬 엔트리포인트
│   ├── foreign_flow_collector/
│   │   └── main.py
│   └── macro_overnight_collector/
│       └── main.py
├── shared/
│   ├── news/                       # 신규 모듈
│   │   ├── __init__.py
│   │   ├── base.py                 # NewsSource ABC + NewsItem dataclass
│   │   ├── dedupe.py               # LRU + Redis Set 중복 제거
│   │   ├── publisher.py            # stream:news.raw 발행
│   │   └── sources/
│   │       ├── dart.py             # DART 공시 Open API (기존 DARTDataCollector 재활용)
│   │       ├── yonhap.py           # 연합뉴스 RSS
│   │       ├── reuters.py          # Reuters Korea RSS
│   │       ├── investing.py        # Investing.com API
│   │       └── mk_adapter.py       # 기존 MKStockNewsCollector를 NewsSource 인터페이스로 어댑트
│   ├── flow/                       # 신규 모듈
│   │   ├── __init__.py
│   │   ├── base.py                 # FlowSource ABC
│   │   └── sources/
│   │       └── krx_openapi.py      # KRX 투자자별 매매동향 (10분 지연)
│   └── macro/                      # 신규 모듈
│       ├── __init__.py
│       └── sources/
│           ├── yahoo.py            # yfinance 활용 (기존 사용 중)
│           └── ecos.py             # 한국은행 ECOS API (USDKRW)
└── config/
    ├── news_sources.yaml           # 신규
    ├── flow_sources.yaml           # 신규
    └── macro_sources.yaml          # 신규
```

### 4.2 Source 인터페이스 (계약)

`shared/news/base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass(frozen=True)
class NewsItem:
    news_id: str
    source: str
    published_at_ms: int
    received_at_ms: int
    title: str
    body: str
    url: str
    source_version: str
    lang: str
    keywords: list[str]

class NewsSource(ABC):
    """Pluggable source. Yields dedup-naive items; dedupe handled by framework."""
    name: str
    poll_interval_seconds: int      # 최소 10초 (rate limit)
    version: str

    @abstractmethod
    async def fetch(self) -> AsyncIterator[NewsItem]: ...

    async def healthcheck(self) -> bool:
        return True
```

`shared/flow/base.py`, `shared/macro/base.py`도 동일 패턴.

### 4.3 중복 제거 (정합성)

```python
# shared/news/dedupe.py — 2단계 dedupe
class NewsDedupe:
    def __init__(self, redis, memory_size: int = 20_000, ttl_days: int = 7):
        self.redis = redis
        self.memory = LRUCache(memory_size)
        self.ttl = ttl_days * 86400

    async def is_duplicate(self, news_id: str) -> bool:
        if news_id in self.memory:
            return True
        exists = await self.redis.exists(f"news:seen:v1:{news_id}")
        if exists:
            self.memory[news_id] = True
            return True
        return False

    async def mark_seen(self, news_id: str):
        self.memory[news_id] = True
        await self.redis.setex(f"news:seen:v1:{news_id}", self.ttl, "1")
```

**`news_id` 생성 정책 (소스별 결정):**
- DART: `dart_{rcept_no}` (공시번호)
- Yonhap: `yonhap_{sha256(url)[:16]}`
- Reuters: `reuters_{sha256(url)[:16]}`
- Investing: `investing_{api_article_id}`
- MK: 기존 MK 자체 ID 활용, 없으면 `mk_{sha256(url)[:16]}`

### 4.4 수집 루프 (장애 격리)

```python
# services/news_collector/main.py
class NewsCollectorDaemon:
    def __init__(self, config, redis):
        self.sources: list[NewsSource] = load_sources(config)
        self.dedupe = NewsDedupe(redis)
        self.publisher = NewsStreamPublisher(redis)
        self.ch_writer = ClickHouseNewsWriter()  # batched 10s flush
        self.metrics = MetricsCollector("news_collector")

    async def run(self):
        tasks = [self._source_loop(s) for s in self.sources]
        await asyncio.gather(*tasks, return_exceptions=False)

    async def _source_loop(self, source: NewsSource):
        while not self._stopping:
            try:
                async for item in source.fetch():
                    if await self.dedupe.is_duplicate(item.news_id):
                        continue
                    await self.dedupe.mark_seen(item.news_id)
                    await self.publisher.publish(item)
                    await self.ch_writer.enqueue(item)
                    self.metrics.inc_collected(source.name)
            except Exception as e:
                self.metrics.inc_error(source.name)
                logger.exception("source=%s failed", source.name)
                await asyncio.sleep(source.poll_interval_seconds)
                continue
            await asyncio.sleep(source.poll_interval_seconds)
```

**원칙:** 한 소스 실패가 다른 소스를 막지 않는다. 각 소스는 자체 poll loop.

### 4.5 소스별 구현 노트

| 소스 | 방식 | 주요 이슈 | 기존 자산 |
|------|------|-----------|----------|
| DART | `DARTDataCollector` 재활용 + 공시 뉴스 매핑 | 30초 polling, rcept_no 중복 제거 | `shared/llm/collectors.py:585` |
| Yonhap | RSS `https://www.yna.co.kr/rss/economy.xml` | robots.txt 준수, 10초 간격 | 신규 |
| Reuters | RSS `https://kr.reuters.com/rss/businessNews` | 영어/한국어 혼재, `lang` 태깅 | 신규 |
| Investing | Investing.com API (계약 필요) | API key 필수, Q4 결정 | 신규 |
| MK | `MKStockNewsCollector` 어댑트 | 기존 keyword-sentiment 제거, raw만 발행 | `collectors.py:798` |

**한국경제 / Naver Finance는 Phase 1에서 제외** (마스터 §Q3) — Phase 2 이후 재고.

### 4.6 Foreign Flow Collector

**KRX Open API 전용, 10분 지연 허용.**

```python
# shared/flow/sources/krx_openapi.py
class KRXInvestorFlowSource(FlowSource):
    name = "krx_openapi"
    poll_interval_seconds = 60     # 1분마다 갱신 체크, 실제 데이터는 10분 단위
    version = "v1"

    async def fetch(self) -> AsyncIterator[FlowItem]:
        # KRX 투자자별 매매동향 API 호출
        # endpoint: http://data.krx.co.kr/...
        # 응답에서 외국인 순매수 파싱 후 yield
        ...
```

**Phase 1에서는 KOSPI200 지수 대리지표 먼저 수집**, 선물 체결기준 투자자별 데이터는 Phase 2에서 추가 검토 (API 가용성 확인 필요).

### 4.7 Macro Overnight Collector

**Cron 방식** (데몬보다 단순). 기존 `scripts/cron/` 패턴 재사용.

```bash
# scripts/cron/macro_overnight.sh
06 00 * * 1-5 ... run collect_overnight_eurex.py
30 06 * * 1-5 ... run collect_overnight_us.py
```

Python 스크립트는 `shared/macro/sources/*`를 호출하고 stream + ClickHouse 적재.

---

## 5. 설정 파일 (신규)

### 5.1 `config/news_sources.yaml`

```yaml
news_collector:
  redis_stream: "stream:news.raw"
  redis_maxlen: 100000
  clickhouse_batch_size: 50
  clickhouse_flush_interval_seconds: 10
  dedupe:
    memory_size: 20000
    redis_ttl_days: 7
  sources:
    dart:
      enabled: true
      poll_interval_seconds: 30
      api_key_env: "DART_API_KEY"
    yonhap:
      enabled: true
      poll_interval_seconds: 60
      rss_url: "https://www.yna.co.kr/rss/economy.xml"
    reuters:
      enabled: true
      poll_interval_seconds: 120
      rss_url: "https://kr.reuters.com/rss/businessNews"
    investing:
      enabled: false          # Q4 결정 후 활성
      poll_interval_seconds: 30
      api_key_env: "INVESTING_API_KEY"
    mk:
      enabled: true
      poll_interval_seconds: 180
      mode: "adapter"         # 기존 MKStockNewsCollector 어댑트
```

### 5.2 `config/flow_sources.yaml`

```yaml
foreign_flow_collector:
  redis_stream: "stream:foreign.flow.raw"
  redis_maxlen: 50000
  sources:
    krx_openapi:
      enabled: true
      poll_interval_seconds: 60
      api_key_env: "KRX_API_KEY"
      symbols: ["KOSPI200_INDEX"]
      bucket_minutes: 10
```

### 5.3 `config/macro_sources.yaml`

```yaml
macro_overnight_collector:
  redis_stream: "stream:macro.overnight"
  redis_maxlen: 5000
  sessions:
    overnight_us_close:
      cron: "30 6 * * 1-5"
      indices: ["sp500", "nasdaq", "vix", "dxy", "us10y"]
      provider: "yahoo"
    overnight_eurex_close:
      cron: "0 6 * * 1-5"
      indices: ["eurex_kospi_night"]
      provider: "eurex_scrape"       # TBD
    fx:
      cron: "*/15 * * * 1-5"
      indices: ["usdkrw"]
      provider: "ecos"
```

### 5.4 `ServiceConfigBase` 적용

세 파일 모두 `shared/config/base.py`의 `ServiceConfigBase`를 상속한 Pydantic 모델로 로드. YAML 키 + env override 조합.

---

## 6. 통합 — 기존 시스템과의 관계

**절대 원칙:** Phase 1은 **쓰기 전용 관찰 시스템**. 기존 트레이딩 루프에 영향 주지 않는다.

| 기존 컴포넌트 | Phase 1 상호작용 |
|--------------|-----------------|
| `TradingOrchestrator` | 영향 없음. 신규 데이터 참조 없음. |
| `rl_mppo` 운용 | 영향 없음. 계속 동작. |
| 기존 `shared/llm/collectors.py` | MK 수집기만 어댑트 경유로 재사용 (원본 유지). Phase 2 이후 통합 검토. |
| `llm_premarket_briefing` cron | 영향 없음. Phase 1은 배치/실시간 병행. |
| Redis DB | 기존 DB 1 유지. 새 키 prefix: `news:*`, `flow:*`, `stream:news.*` |
| ClickHouse | 새 테이블만 추가. 기존 테이블 수정 없음. |

---

## 7. 모니터링 (Phase 1 한정)

### 7.1 Prometheus 메트릭 신설

`shared/monitoring/news_metrics.py` (또는 기존 `services/monitoring/metrics.py` 확장):

```
news_collected_total{source}        Counter
news_duplicates_total{source}       Counter
news_errors_total{source, kind}     Counter
news_publish_lag_seconds{source}    Histogram
news_stream_length{stream}          Gauge
flow_collected_total{source}        Counter
macro_collected_total{session}      Counter
```

### 7.2 Grafana 패널 (기존 `system-health` 확장)

- 소스별 수집량 (1h rolling)
- 각 스트림 `XLEN`
- 에러율 by source
- Dedupe hit rate (메모리 vs Redis)

---

## 8. 테스트 전략

### 8.1 단위 테스트

- `tests/unit/news/test_dedupe.py`
- `tests/unit/news/test_sources/test_dart.py` (mock 공시 응답)
- `tests/unit/news/test_sources/test_yonhap.py` (mock RSS)
- `tests/unit/flow/test_krx_source.py`
- `tests/unit/macro/test_yahoo.py`

### 8.2 통합 테스트

- `tests/integration/test_news_collector_e2e.py` — fakeredis + fakeclickhouse로 종단
- `tests/integration/test_flow_collector_e2e.py`

### 8.3 장기 연속 테스트

- **24시간 dry-run** — 실제 Redis + ClickHouse + 실 소스 연결, publish만 확인 (Phase 2가 consumer group 붙이기 전까지 XACK 없이 대기)
- 검증 지표: 각 소스 최소 기대 수집량 (예: Yonhap > 50 items/day), 에러율 < 1%

---

## 9. 운영 & 배포

### 9.1 systemd unit (신규 3개)

```
/etc/systemd/system/kis-news-collector.service
/etc/systemd/system/kis-foreign-flow.service
/etc/systemd/system/kis-macro-overnight.service      # oneshot + timer
```

**Graceful shutdown** 필수 — SIGTERM → 현재 배치 flush → exit (기존 `TradingOrchestrator` 패턴 재사용).

### 9.2 cron (신규)

```
# scripts/cron/macro_overnight.sh
0 6 * * 1-5   scripts/cron/macro_overnight.sh eurex
30 6 * * 1-5  scripts/cron/macro_overnight.sh us
*/15 * * * 1-5 scripts/cron/macro_overnight.sh fx
```

### 9.3 Telegram 알림 (최소)

- 소스별 수집 0건 상태가 30분 지속 시 경고
- 스트림 maxlen 80% 도달 시 경고
- ClickHouse 적재 실패율 > 5% 시 경고

기존 `TELEGRAM_BRIEFING_*` 채널 재사용, tag: `[PHASE1]`.

---

## 10. Phase 1 완료 게이트 (엄격)

아래 **모두** 만족해야 Phase 2 착수:

- [ ] 마이그레이션 `V1` 적용, 6개 테이블 존재
- [ ] 3개 서비스 데몬 48시간 연속 가동 (systemd restart 카운트 0)
- [ ] 각 스트림 실데이터 적재 확인:
  - `stream:news.raw`: 최소 500건/영업일
  - `stream:foreign.flow.raw`: 최소 20건/영업일
  - `stream:macro.overnight`: 매일 2건 (US + Eurex)
- [ ] ClickHouse `news_raw`, `investor_flow_raw`, `macro_overnight` 적재 count 스트림 XADD와 ±1% 일치
- [ ] 단위 테스트 커버리지 ≥ 80% (신규 모듈 한정)
- [ ] 기존 `rl_mppo` 운용 지표 변화 없음 (P&L, latency 확인)

---

## 11. 미결정 사항 (Phase 1 내 결정 필요)

1. **Investing.com API 계약 체결 여부** (Q3 연계) — 없으면 `enabled: false` 출시.
2. **Eurex KOSPI 야간 데이터 소스** — EUREX 공식 웹은 스크래핑 부담. 대안: KRX 야간 세션 재개 시점 확인.
3. **KRX Open API key 재발급** — 기존 `KRX_API_KEY`가 장중 투자자별 매매동향 엔드포인트 지원 여부 검증.
4. **systemd vs docker-compose** — 기존 서비스가 어느 쪽인지 확인 후 통일.

---

## 12. 작업 분해 (구현 단계에서 `writing-plans`로 상세화)

하이 레벨:

1. ClickHouse 마이그레이션 시스템 구축 (V1 포함)
2. `shared/streaming/` 재활용하여 stream publisher wrappers
3. `shared/news/base.py` + `dedupe.py` + `publisher.py` 골격
4. DART source 어댑터 (기존 재활용)
5. Yonhap + Reuters RSS sources
6. MK 어댑터 (기존 reuse)
7. `services/news_collector/main.py` 데몬
8. `shared/flow/base.py` + KRX source
9. `services/foreign_flow_collector/main.py` 데몬
10. `shared/macro/` + Yahoo/ECOS sources
11. `scripts/cron/macro_overnight.sh`
12. Prometheus 메트릭 + Grafana 패널
13. systemd units + 배포
14. 24h 연속 검증
15. Phase 1 완료 게이트 체크

각 단계는 별도 PR로 분리 (작은 단위, 리뷰 가능).

---

## 13. 명시적 비범위

이 Phase 1 spec에는 **포함되지 않는다**:

- 뉴스 감성 분류기 (Phase 2)
- 수급 trend 집계 (Phase 2 — buffer_5m/30m 로직)
- Setup A/B/C 엔진 (Phase 3)
- 리스크 필터, 포지션 사이저 (Phase 3)
- 주문 라우팅, OCO, 슬리피지 로깅 (Phase 4)
- RL 재학습 (RL spec)
- 계약 승수 하드코딩 제거 (Phase 3 포지션 사이저에서 처리)
