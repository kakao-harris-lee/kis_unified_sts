# Phase 2 — 뉴스 감성 분류기 (Week 3-4)

**Status:** Draft
**Parent:** `docs/plans/2026-04-20-futures-paradigm-master.md`
**Target branch:** `feat/futures-paradigm-phase2`
**Depends on:** Phase 1 완료 게이트 통과
**Blocks:** Phase 3

---

## 1. 목표

`stream:news.raw`를 consumer group으로 읽어 **per-news 구조화 스코어** 를 산출하고 `stream:news.scored` 및 `kospi.news_scored` 테이블에 적재한다. Phase 2 완료 시 모든 신규 뉴스가 자동으로 카테고리/방향성/영향도 라벨을 획득한다.

**완료 정의:**
- `services/news_scorer/` 데몬 48시간 무중단 가동
- 누적 1,000건 스코어링 완료
- 샘플 100건 사람 라벨 대비 agreement ≥ 70% (category 일치율)
- API 평균 지연시간 < 3초/건
- LLM 일일 비용 < $2 (추정 2,000건 × $0.001)

---

## 2. 스코어링 스키마 확정

### 2.1 `stream:news.scored` 메시지

```python
{
    "news_id": str,                       # stream:news.raw와 동일 ID
    "scorer_version": str,                # "gpt-4o-mini-v1"
    "scored_at_ms": int,
    "category": str,                      # macro_us|macro_kr|geopolitics|samsung|hynix|korea_policy|sector_event|corporate|other
    "sentiment": float,                   # [-1.0, 1.0], KOSPI200 선물 관점
    "impact_score": float,                # [0.0, 1.0], 가격 이동 유발 확률
    "direction_bias": str,                # long|short|neutral
    "confidence": float,                  # [0.0, 1.0]
    "keywords": list[str],                # 최대 5개
    "reasoning": str,                     # LLM 한 줄 요약 (감사용)
    "raw_ref": str,                       # stream:news.raw의 XADD id (참조)
}
```

### 2.2 `kospi.news_scored` 테이블

```sql
CREATE TABLE IF NOT EXISTS kospi.news_scored (
    news_id String,
    scorer_version LowCardinality(String),
    scored_at DateTime64(3, 'UTC'),
    category LowCardinality(String),
    sentiment Float32,
    impact_score Float32,
    direction_bias LowCardinality(String),
    confidence Float32,
    keywords Array(String),
    reasoning String,
    INDEX idx_cat_impact (category, impact_score) TYPE minmax GRANULARITY 4
) ENGINE = MergeTree()
ORDER BY (scored_at, news_id)
PARTITION BY toYYYYMM(scored_at)
TTL toDateTime(scored_at) + INTERVAL 2 YEAR;
```

마이그레이션: `infra/clickhouse/migrations/V2__create_news_scored.sql`.

---

## 3. LLM 전략 (2단계)

### 3.1 Stage A (Phase 2 출시): GPT-4o-mini 단독

- 기존 `shared/llm/config.py`의 `openai` provider 재사용
- 프롬프트: 원본 §5.2 기반, JSON mode 강제 (`response_format={"type": "json_object"}`)
- 2회 재시도 → 3회째 실패 시 **neutral 기본값** + `scorer_version: "fallback-neutral-v1"` 태깅
- 비용 상한: 일 $5 (초과 시 Telegram 경고, 신규 스코어링 중단 → raw만 축적)

### 3.2 Stage B (옵션, 8주 이후): FinBERT-Korean 앙상블

Phase 2 일정 내 **구현하지 않는다.** 1,000건 스코어링 데이터 축적 후 Phase 5 기간에 별도 검토. 본 spec은 스키마만 앙상블 호환 (`scorer_version` 필드로 구분).

---

## 4. 프롬프트 (확정, 추후 수정은 `scorer_version` 증분)

```text
당신은 KOSPI200 지수선물 가격 영향을 판단하는 정량 분석 AI 입니다.
뉴스 1건을 읽고 아래 JSON 스키마로만 응답하세요. 설명 금지, JSON only.

뉴스 제목: {title}
뉴스 본문 (최대 2000자): {body}

{{
  "category": "macro_us|macro_kr|geopolitics|samsung|hynix|korea_policy|sector_event|corporate|other",
  "sentiment": <-1.0~1.0>,
  "impact_score": <0.0~1.0>,
  "direction_bias": "long|short|neutral",
  "confidence": <0.0~1.0>,
  "keywords": [<최대 5개 문자열>],
  "reasoning": "<한 줄 요약 60자 이내>"
}}

판단 기준:
- FOMC/CPI/고용지표/FED 인사 발언: impact ≥ 0.8
- 북한/지정학 군사 리스크: sentiment 음수, impact ≥ 0.6
- 삼성/SK하이닉스 단일 실적/CAPEX: impact 0.4~0.6
- 일반 기업 실적: impact ≤ 0.2
- 반복 루머/이미 반영된 이슈: impact ≤ 0.1
- 한국어/영어 혼재 허용, lang 관계없이 동일 기준.
```

**프롬프트 버전 관리:** 프롬프트 변경 시 `scorer_version` 반드시 증분 (예: `gpt-4o-mini-v2`). 과거 스코어 재계산 금지 (timestamped audit 유지).

---

## 5. 구현 구조

```
services/news_scorer/
├── __init__.py
└── main.py                      # consumer group 데몬
shared/scoring/
├── __init__.py
├── base.py                      # Scorer ABC + ScoredItem dataclass
├── llm_scorer.py                # OpenAI GPT-4o-mini 구현
├── fallback.py                  # neutral 기본값
├── validators.py                # JSON schema 검증
└── publisher.py                 # stream:news.scored + ClickHouse 발행
config/news_scoring.yaml         # 신규
```

### 5.1 Scorer 계약

```python
class Scorer(ABC):
    version: str
    @abstractmethod
    async def score(self, news: NewsItem) -> ScoredItem: ...
```

### 5.2 Consumer Group 데몬

```python
class NewsScorerDaemon:
    async def run(self):
        consumer_group = "news_scorer-v1"
        await self.redis.xgroup_create(
            "stream:news.raw", consumer_group, id="$", mkstream=True
        )
        while not self._stopping:
            messages = await self.redis.xreadgroup(
                groupname=consumer_group,
                consumername=self.worker_id,
                streams={"stream:news.raw": ">"},
                count=10, block=5000,
            )
            for stream_name, msgs in messages:
                for msg_id, data in msgs:
                    try:
                        news = NewsItem.from_stream(data)
                        scored = await self._score_with_retry(news)
                        await self.publisher.publish(scored)   # stream + CH
                        await self.redis.xack("stream:news.raw", consumer_group, msg_id)
                    except ValidationError as ve:
                        # JSON 파싱 실패 → fallback neutral + ack
                        await self.publisher.publish(self.fallback.neutral(news))
                        await self.redis.xack("stream:news.raw", consumer_group, msg_id)
                    except Exception:
                        # 일시 장애 → ack 하지 않음 (재처리)
                        logger.exception("scoring failed news_id=%s", news.news_id)
```

### 5.3 예산 상한

`shared/scoring/budget.py` — 일일 비용 카운터 (Redis `scorer:cost:{YYYYMMDD}` INCRBYFLOAT). 초과 시 `score()` 호출 전 예외 → fallback으로 강등.

---

## 6. 설정 파일

```yaml
# config/news_scoring.yaml
news_scorer:
  consumer_group: "news_scorer-v1"
  worker_id_prefix: "scorer"
  batch_size: 10
  xread_block_ms: 5000

  scorer:
    provider: "openai"
    model: "gpt-4o-mini"
    version: "gpt-4o-mini-v1"
    temperature: 0.0
    max_tokens: 250
    timeout_seconds: 5
    retries: 2
    api_key_env: "OPENAI_API_KEY"

  budget:
    daily_usd_limit: 5.0
    alert_threshold_pct: 0.8

  fallback:
    on_timeout: "neutral"         # neutral|skip
    on_json_error: "neutral"
    on_budget_exceeded: "skip"    # raw만 축적

  body_truncate_chars: 2000
```

---

## 7. 검증 — 사람 라벨 대비 Agreement

### 7.1 Golden set 구축

- 운영 48시간 축적 후 무작위 100건 추출
- 사용자가 직접 라벨링 (category + direction_bias만) — 15분 소요 예상
- 저장 위치: `tests/fixtures/news_scoring_golden.json`

### 7.2 측정 지표

- **Category agreement:** `> 70%` (9개 카테고리 중 일치)
- **Direction agreement:** `> 75%` (long/short/neutral)
- **Impact calibration:** 사람이 "high-impact"라 표시한 건의 impact_score 평균 > 0.6

미달 시: 프롬프트 수정 → `scorer_version` 증분 → 재평가.

### 7.3 CI 테스트

`tests/integration/test_news_scorer_golden.py` — golden set으로 회귀 테스트. `scorer_version` 변경 시 필수 재평가.

---

## 8. 모니터링

### 8.1 Prometheus 메트릭

```
news_scored_total{version, category}            Counter
news_scoring_duration_seconds{version}          Histogram
news_scoring_errors_total{kind}                 Counter (timeout|json_error|budget|other)
news_scoring_fallback_total{reason}             Counter
news_scoring_cost_usd_today                     Gauge
news_scorer_backlog                             Gauge (XPENDING count)
```

### 8.2 대시보드 패널 (Phase 1 대시보드 확장)

- 카테고리 분포 (파이)
- direction_bias 시계열 (stacked area)
- impact_score 히스토그램
- 처리 레이턴시 p50/p95/p99

### 8.3 알림

- fallback 비율 > 10% 30분 지속 → 경고
- 예산 80% 도달 → 알림
- XPENDING > 500 10분 지속 → 경고 (scorer lag)

---

## 9. 기존 배치 LLM 파이프라인과의 관계

**원칙:** 실시간 스코어링은 **추가** 될 뿐, 기존 `llm_premarket_briefing` / `llm_intraday_refresh` / `llm_market_close_briefing` cron은 **그대로 유지**. 중복 낭비처럼 보이지만:
- 배치는 **집계/요약** 목적 (종목별 추천)
- 실시간은 **이벤트 반응** 목적 (Setup C 트리거용)

Phase 5 이후 배치의 `news_sentiment` 필드를 실시간 `news_scored`로 대체 검토 — 본 Phase 범위 아님.

---

## 10. Phase 2 완료 게이트

- [ ] `V2__create_news_scored.sql` 적용
- [ ] `news_scorer` 데몬 48h 연속 가동
- [ ] 누적 스코어링 ≥ 1,000건
- [ ] Golden set 100건 agreement category ≥ 70%, direction ≥ 75%
- [ ] 일일 LLM 비용 < $5
- [ ] fallback 비율 < 5%
- [ ] 단위 테스트 + golden set 회귀 테스트 통과
- [ ] `rl_mppo` 운용 영향 없음

---

## 11. 명시적 비범위

- FinBERT 앙상블 (Stage B — Phase 5 이후)
- 종목별 점수 집계 (Phase 3 Setup 엔진에서 window query로 처리)
- 기존 배치 LLM 파이프라인 재설계 (Phase 5+)
- 뉴스 클러스터링/중복 의미 판정 (프롬프트로 간접 해결)
