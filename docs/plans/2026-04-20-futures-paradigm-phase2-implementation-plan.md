# Futures Paradigm — Phase 2 News Scoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** consume `stream:news.raw` via Redis consumer-group, score each news item with GPT-4o-mini into a structured label (category / sentiment / impact / direction / confidence / keywords), and publish to `stream:news.scored` + `kospi.news_scored`. Close the data pipeline from raw collection (Phase 1) to actionable labeled signals (Phase 3 Setup engines).

**Architecture:** `NewsScorerDaemon` reads from `stream:news.raw` as consumer-group `news_scorer-v1`. For each message, it resolves a `Scorer` implementation (LLM by default, fallback on budget/timeout/JSON error), passes `NewsItem → ScoredItem`, and writes to Redis stream + ClickHouse batch. Budget guard (daily USD cap) intercepts before LLM calls; JSON schema validator ensures output sanity. Prompt version is embedded in `scorer_version` so historical audits stay stable when the prompt evolves.

**Tech Stack:** Python 3.11+, asyncio, `redis.asyncio` (consumer-group: `XREADGROUP`/`XACK`/`XPENDING`), `openai>=1.0` (async client, JSON mode), `aiochclient`, `pydantic v2`, `pytest` + `pytest-asyncio` + `fakeredis` + `aioresponses`. Reuses `shared/news/base.py::NewsItem` and `shared/db/client.py::AsyncClickHouseClient` from Phase 1.

**Parent spec:** `docs/plans/2026-04-20-futures-paradigm-phase2-scoring.md`
**Depends on:** `feat/futures-paradigm-phase1` merged to main (Phase 1 48h gate passed).

---

## File Structure

**Create (new files):**

```
infra/clickhouse/migrations/
└── V2__create_news_scored.sql                 # news_scored table (+ minmax index)

shared/scoring/
├── __init__.py
├── base.py                                    # ScoredItem dataclass + Scorer ABC
├── llm_scorer.py                              # OpenAI GPT-4o-mini scorer
├── fallback.py                                # FallbackScorer (neutral defaults)
├── validators.py                              # ScoredItem JSON-schema validator
├── budget.py                                  # daily USD cap via Redis INCRBYFLOAT
├── publisher.py                               # stream:news.scored + CH writer
└── prompt.py                                  # versioned prompt template

services/news_scorer/
├── __init__.py
└── main.py                                    # NewsScorerDaemon (consumer-group)

config/
└── news_scoring.yaml                          # NewsScorerConfig

deploy/systemd/
└── kis-news-scorer.service                    # systemd unit

tests/unit/scoring/
├── __init__.py
├── test_base.py                               # ScoredItem invariants
├── test_llm_scorer.py                         # mocked OpenAI client
├── test_fallback.py                           # neutral defaults
├── test_validators.py                         # malformed JSON rejection
├── test_budget.py                             # cap tripped / reset at midnight KST
├── test_publisher.py                          # stream + CH fan-out
└── test_prompt.py                             # prompt-version stability

tests/unit/services/
└── test_news_scorer_main.py                   # CLI glue coverage

tests/integration/
├── test_news_scorer_e2e.py                    # fakeredis + AsyncMock CH end-to-end
└── test_news_scorer_golden.py                 # 100-item golden-set agreement

tests/fixtures/
└── news_scoring_golden.json                   # 100 human-labeled items (placeholder seeded, filled in ops)

docs/runbooks/
└── phase2-verification.md                     # 48h gate checklist
```

**Modify (existing files):**

- `services/monitoring/metrics.py` — add 6 scorer metric families (see Task 11)
- `pyproject.toml` — verify `openai>=1.0` is present (Phase 1 already uses it indirectly via `shared/llm/`); add `pytest-httpx` to dev-deps if needed for OpenAI async mocking
- `CLAUDE.md` — no change this phase (Phase 5 documentation pass)

---

## Conventions Reminder (applies to all tasks)

- **Feature branch:** work on `feat/futures-paradigm-phase2` (never commit to main). Rebase onto main once Phase 1 PR #125 merges.
- **Test runner:** `source .venv/bin/activate && pytest` — NOT system pytest.
- **Redis DB:** always `REDIS_DB=1`.
- **Test isolation:** `fakeredis` for Redis, mock the OpenAI client for unit tests, `AsyncMock()` for CH client.
- **Formatting:** `black . && ruff check --fix .` on **modified files only** before every commit (never `black .` on the whole tree — it touches hundreds of unrelated files).
- **Commit message style:** `feat(scoring): ...`, `test(scoring): ...`, `chore(infra): ...`.
- **No mass rewrites:** Phase 2 is additive. Do NOT modify `shared/news/` or `services/news_collector/` — only read their exports.
- **Prompt stability:** Any edit to `shared/scoring/prompt.py` MUST bump `scorer_version` in the YAML config. Never back-fill old rows with new scorer_version (audit trail).

---

## Task 1: Scaffold feature branch + dependency check

**Files:**
- Modify: `pyproject.toml` (only if `openai` or `pytest-httpx` absent)

- [ ] **Step 1: Confirm Phase 1 is merged; create feature branch**

```bash
git fetch origin
git checkout main
git pull
# Verify Phase 1 PR merged
gh pr view 125 --json state     # expect state=MERGED
git checkout -b feat/futures-paradigm-phase2
```

If Phase 1 is not yet merged, branch from `feat/futures-paradigm-phase1` instead and plan a rebase after merge:

```bash
git checkout feat/futures-paradigm-phase1
git checkout -b feat/futures-paradigm-phase2
```

- [ ] **Step 2: Verify dependencies**

```bash
source .venv/bin/activate
python -c "import openai; print(openai.__version__)"  # expect >=1.0
python -c "import pytest_httpx" || pip install pytest-httpx
```

If `openai` absent: `pip install "openai>=1.0"` and add to `pyproject.toml` `[project.dependencies]`.

- [ ] **Step 3: Commit (only if pyproject.toml changed)**

```bash
git add pyproject.toml
git commit -m "chore(deps): add scoring test fixtures"
```

---

## Task 2: V2 ClickHouse migration — `news_scored` table

**Files:**
- Create: `infra/clickhouse/migrations/V2__create_news_scored.sql`

- [ ] **Step 1: Write failing test**

Create `tests/unit/migrations/test_v2_migration.py`:

```python
"""V2 migration creates news_scored with the right schema."""

from pathlib import Path

V2_PATH = Path("infra/clickhouse/migrations/V2__create_news_scored.sql")


def test_v2_file_exists():
    assert V2_PATH.is_file(), "V2 migration file missing"


def test_v2_declares_required_columns():
    sql = V2_PATH.read_text()
    for column in (
        "news_id",
        "scorer_version",
        "scored_at",
        "category",
        "sentiment",
        "impact_score",
        "direction_bias",
        "confidence",
        "keywords",
        "reasoning",
    ):
        assert column in sql, f"V2 missing column: {column}"


def test_v2_declares_ttl_and_partition():
    sql = V2_PATH.read_text()
    assert "PARTITION BY toYYYYMM(scored_at)" in sql
    assert "INTERVAL 2 YEAR" in sql
    assert "MergeTree" in sql
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/unit/migrations/test_v2_migration.py -v
```

- [ ] **Step 3: Write V2 SQL**

```sql
-- V2__create_news_scored.sql
-- Phase 2: per-news structured score table.
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

- [ ] **Step 4: Apply in local ClickHouse + verify**

```bash
source .venv/bin/activate
set -a && source .env && set +a
python scripts/migrations/apply_clickhouse_migrations.py
curl -s "http://localhost:8123/?query=DESC+kospi.news_scored" \
  --user "default:${CLICKHOUSE_PASSWORD}"
```

Expected: 10 columns listed.

- [ ] **Step 5: Run test — expect PASS & Commit**

```bash
pytest tests/unit/migrations/test_v2_migration.py -v
git add infra/clickhouse/migrations/V2__create_news_scored.sql tests/unit/migrations/test_v2_migration.py
git commit -m "feat(infra): V2 migration — kospi.news_scored table"
```

---

## Task 3: `shared/scoring/base.py` — ScoredItem + Scorer ABC

**Files:**
- Create: `shared/scoring/__init__.py`, `shared/scoring/base.py`
- Create: `tests/unit/scoring/__init__.py`, `tests/unit/scoring/test_base.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/scoring/test_base.py
from dataclasses import FrozenInstanceError
import pytest

from shared.scoring.base import ScoredItem


def _valid_kwargs():
    return dict(
        news_id="n1",
        scorer_version="gpt-4o-mini-v1",
        scored_at_ms=1_700_000_000_000,
        category="macro_us",
        sentiment=0.4,
        impact_score=0.8,
        direction_bias="long",
        confidence=0.85,
        keywords=["fomc", "rate"],
        reasoning="FOMC statement hawkish-neutral",
        raw_ref="1700000000000-0",
    )


def test_scored_item_accepts_valid_input():
    item = ScoredItem(**_valid_kwargs())
    assert item.category == "macro_us"
    assert item.direction_bias == "long"


def test_scored_item_is_frozen():
    item = ScoredItem(**_valid_kwargs())
    with pytest.raises(FrozenInstanceError):
        item.sentiment = 0.1  # type: ignore[misc]


@pytest.mark.parametrize("field, bad", [
    ("sentiment", 1.5),
    ("sentiment", -1.5),
    ("impact_score", -0.1),
    ("impact_score", 1.1),
    ("confidence", 2.0),
])
def test_scored_item_rejects_out_of_range(field, bad):
    kwargs = _valid_kwargs()
    kwargs[field] = bad
    with pytest.raises(ValueError):
        ScoredItem(**kwargs)


def test_scored_item_rejects_unknown_direction_bias():
    kwargs = _valid_kwargs()
    kwargs["direction_bias"] = "up"
    with pytest.raises(ValueError):
        ScoredItem(**kwargs)


def test_scored_item_keywords_clipped_to_five():
    kwargs = _valid_kwargs()
    kwargs["keywords"] = [f"kw{i}" for i in range(20)]
    item = ScoredItem(**kwargs)
    assert len(item.keywords) == 5
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `shared/scoring/base.py`**

```python
"""Phase 2 scoring primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from shared.news.base import NewsItem

VALID_CATEGORIES: frozenset[str] = frozenset({
    "macro_us", "macro_kr", "geopolitics",
    "samsung", "hynix", "korea_policy",
    "sector_event", "corporate", "other",
})
VALID_DIRECTIONS: frozenset[str] = frozenset({"long", "short", "neutral"})


@dataclass(frozen=True)
class ScoredItem:
    news_id: str
    scorer_version: str
    scored_at_ms: int
    category: str
    sentiment: float
    impact_score: float
    direction_bias: str
    confidence: float
    keywords: list[str] = field(default_factory=list)
    reasoning: str = ""
    raw_ref: str = ""

    MAX_KEYWORDS: ClassVar[int] = 5

    def __post_init__(self) -> None:
        if self.category not in VALID_CATEGORIES:
            raise ValueError(f"invalid category: {self.category}")
        if self.direction_bias not in VALID_DIRECTIONS:
            raise ValueError(f"invalid direction_bias: {self.direction_bias}")
        if not -1.0 <= self.sentiment <= 1.0:
            raise ValueError(f"sentiment out of range: {self.sentiment}")
        if not 0.0 <= self.impact_score <= 1.0:
            raise ValueError(f"impact_score out of range: {self.impact_score}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {self.confidence}")
        # Clip keywords to MAX_KEYWORDS without mutating caller's list.
        if len(self.keywords) > self.MAX_KEYWORDS:
            object.__setattr__(self, "keywords", list(self.keywords[: self.MAX_KEYWORDS]))


class Scorer(ABC):
    """Contract for any implementation that turns NewsItem → ScoredItem."""

    version: str

    @abstractmethod
    async def score(self, news: NewsItem) -> ScoredItem:
        """Produce a ScoredItem, or raise on unrecoverable failure."""
        raise NotImplementedError
```

- [ ] **Step 4: Run — expect PASS & Commit**

```bash
pytest tests/unit/scoring/test_base.py -v
black shared/scoring/base.py tests/unit/scoring/test_base.py
ruff check --fix shared/scoring/base.py tests/unit/scoring/test_base.py
git add shared/scoring/__init__.py shared/scoring/base.py tests/unit/scoring/
git commit -m "feat(scoring): ScoredItem dataclass + Scorer ABC"
```

---

## Task 4: `shared/scoring/validators.py` — JSON schema validation

**Files:**
- Create: `shared/scoring/validators.py`
- Create: `tests/unit/scoring/test_validators.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/scoring/test_validators.py
import json

import pytest

from shared.scoring.validators import (
    ScoringValidationError,
    parse_llm_json,
)


VALID_JSON = json.dumps({
    "category": "macro_us",
    "sentiment": 0.5,
    "impact_score": 0.9,
    "direction_bias": "long",
    "confidence": 0.8,
    "keywords": ["fomc"],
    "reasoning": "ok",
})


def test_parse_valid_json_produces_dict():
    result = parse_llm_json(VALID_JSON)
    assert result["category"] == "macro_us"
    assert result["direction_bias"] == "long"


def test_parse_rejects_missing_field():
    bad = json.dumps({"category": "macro_us"})
    with pytest.raises(ScoringValidationError):
        parse_llm_json(bad)


def test_parse_rejects_unknown_category():
    payload = json.loads(VALID_JSON)
    payload["category"] = "unicorn"
    with pytest.raises(ScoringValidationError):
        parse_llm_json(json.dumps(payload))


def test_parse_rejects_malformed_json():
    with pytest.raises(ScoringValidationError):
        parse_llm_json("not-json")


def test_parse_coerces_numeric_strings():
    payload = json.loads(VALID_JSON)
    payload["sentiment"] = "0.3"  # LLM sometimes quotes floats
    result = parse_llm_json(json.dumps(payload))
    assert result["sentiment"] == pytest.approx(0.3)
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# shared/scoring/validators.py
"""LLM output parsing + schema validation."""

from __future__ import annotations

import json
from typing import Any

from shared.scoring.base import VALID_CATEGORIES, VALID_DIRECTIONS

_REQUIRED_FIELDS = (
    "category",
    "sentiment",
    "impact_score",
    "direction_bias",
    "confidence",
)
_NUMERIC_FIELDS = ("sentiment", "impact_score", "confidence")


class ScoringValidationError(ValueError):
    """LLM output failed schema validation."""


def parse_llm_json(raw: str) -> dict[str, Any]:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScoringValidationError(f"malformed json: {exc}") from exc

    if not isinstance(obj, dict):
        raise ScoringValidationError("top-level must be object")

    for field in _REQUIRED_FIELDS:
        if field not in obj:
            raise ScoringValidationError(f"missing required field: {field}")

    for field in _NUMERIC_FIELDS:
        try:
            obj[field] = float(obj[field])
        except (TypeError, ValueError) as exc:
            raise ScoringValidationError(
                f"field {field} must be numeric"
            ) from exc

    if obj["category"] not in VALID_CATEGORIES:
        raise ScoringValidationError(
            f"invalid category: {obj['category']!r}"
        )
    if obj["direction_bias"] not in VALID_DIRECTIONS:
        raise ScoringValidationError(
            f"invalid direction_bias: {obj['direction_bias']!r}"
        )

    obj.setdefault("keywords", [])
    obj.setdefault("reasoning", "")
    return obj
```

- [ ] **Step 4: Run — expect PASS & Commit**

```bash
pytest tests/unit/scoring/test_validators.py -v
git add shared/scoring/validators.py tests/unit/scoring/test_validators.py
git commit -m "feat(scoring): JSON schema validator for LLM output"
```

---

## Task 5: `shared/scoring/fallback.py` — neutral defaults

**Files:**
- Create: `shared/scoring/fallback.py`, `tests/unit/scoring/test_fallback.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/scoring/test_fallback.py
from shared.news.base import NewsItem
from shared.scoring.fallback import FallbackScorer


def _news(news_id: str = "n1") -> NewsItem:
    return NewsItem(
        news_id=news_id,
        source="yonhap",
        published_at_ms=1_700_000_000_000,
        received_at_ms=1_700_000_000_500,
        title="t",
        body="b",
        url="u",
        source_version="yonhap-v1",
        lang="ko",
        keywords=[],
    )


async def test_fallback_produces_neutral():
    fb = FallbackScorer(version="fallback-neutral-v1")
    item = await fb.score(_news("n1"))
    assert item.category == "other"
    assert item.sentiment == 0.0
    assert item.impact_score == 0.0
    assert item.direction_bias == "neutral"
    assert item.confidence == 0.0
    assert item.scorer_version == "fallback-neutral-v1"
    assert item.news_id == "n1"


async def test_fallback_preserves_raw_ref():
    fb = FallbackScorer(version="fallback-neutral-v1")
    item = await fb.score(_news("n1"))
    assert item.reasoning.startswith("fallback:")
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# shared/scoring/fallback.py
"""Neutral-defaults scorer used when LLM fails."""

from __future__ import annotations

import time

from shared.news.base import NewsItem
from shared.scoring.base import Scorer, ScoredItem


class FallbackScorer(Scorer):
    def __init__(self, version: str = "fallback-neutral-v1"):
        self.version = version

    async def score(self, news: NewsItem) -> ScoredItem:
        return ScoredItem(
            news_id=news.news_id,
            scorer_version=self.version,
            scored_at_ms=int(time.time() * 1000),
            category="other",
            sentiment=0.0,
            impact_score=0.0,
            direction_bias="neutral",
            confidence=0.0,
            keywords=[],
            reasoning=f"fallback: {self.version}",
        )
```

- [ ] **Step 4: Run — expect PASS & Commit**

---

## Task 6: `shared/scoring/budget.py` — daily USD cap

**Files:**
- Create: `shared/scoring/budget.py`, `tests/unit/scoring/test_budget.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/scoring/test_budget.py
import fakeredis.aioredis
import pytest

from shared.scoring.budget import BudgetExceeded, DailyBudget


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis()


async def test_add_below_limit_does_not_raise(redis):
    b = DailyBudget(redis, daily_usd_limit=5.0, key_prefix="test:scorer:cost")
    await b.charge(0.001, date="20260422")  # tiny per-call cost
    assert await b.used_today(date="20260422") == pytest.approx(0.001)


async def test_add_exceeding_limit_raises(redis):
    b = DailyBudget(redis, daily_usd_limit=0.002, key_prefix="test:scorer:cost")
    await b.charge(0.001, date="20260422")
    with pytest.raises(BudgetExceeded):
        await b.charge(0.002, date="20260422")  # pushes over 0.002


async def test_per_day_isolation(redis):
    b = DailyBudget(redis, daily_usd_limit=0.005, key_prefix="test:scorer:cost")
    await b.charge(0.004, date="20260422")
    # New day: budget resets.
    await b.charge(0.004, date="20260423")
    assert await b.used_today(date="20260422") == pytest.approx(0.004)
    assert await b.used_today(date="20260423") == pytest.approx(0.004)


async def test_ttl_set_on_key(redis):
    b = DailyBudget(redis, daily_usd_limit=1.0, key_prefix="test:scorer:cost")
    await b.charge(0.001, date="20260422")
    ttl = await redis.ttl("test:scorer:cost:20260422")
    assert 0 < ttl <= 86400 * 2  # up to 48h retention
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# shared/scoring/budget.py
"""Redis-backed daily USD cap for scoring costs."""

from __future__ import annotations

from datetime import datetime
from typing import Any


class BudgetExceeded(Exception):
    pass


class DailyBudget:
    """Tracks cumulative USD spend per day. Keys expire after 48h."""

    def __init__(
        self,
        redis: Any,
        *,
        daily_usd_limit: float,
        key_prefix: str = "scorer:cost",
        ttl_seconds: int = 172800,  # 48h
    ):
        self.redis = redis
        self.limit = daily_usd_limit
        self.prefix = key_prefix
        self.ttl = ttl_seconds

    def _key(self, date: str | None = None) -> str:
        if date is None:
            date = datetime.utcnow().strftime("%Y%m%d")
        return f"{self.prefix}:{date}"

    async def used_today(self, *, date: str | None = None) -> float:
        raw = await self.redis.get(self._key(date))
        return float(raw or 0.0)

    async def charge(self, cost_usd: float, *, date: str | None = None) -> float:
        """Increment the counter. Raise BudgetExceeded if this push crosses cap."""
        key = self._key(date)
        new_total = float(await self.redis.incrbyfloat(key, cost_usd))
        await self.redis.expire(key, self.ttl)
        if new_total > self.limit:
            raise BudgetExceeded(
                f"daily cap {self.limit} USD exceeded (used={new_total:.4f})"
            )
        return new_total
```

- [ ] **Step 4: Run — expect PASS & Commit**

---

## Task 7: `shared/scoring/prompt.py` — versioned prompt template

**Files:**
- Create: `shared/scoring/prompt.py`, `tests/unit/scoring/test_prompt.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/scoring/test_prompt.py
from shared.scoring.prompt import PROMPT_V1, render


def test_prompt_v1_has_all_schema_fields():
    for field in (
        "category",
        "sentiment",
        "impact_score",
        "direction_bias",
        "confidence",
        "keywords",
        "reasoning",
    ):
        assert field in PROMPT_V1


def test_render_interpolates_title_and_body():
    text = render(PROMPT_V1, title="FOMC holds rates", body="Powell remarks...")
    assert "FOMC holds rates" in text
    assert "Powell remarks" in text


def test_render_truncates_long_body():
    long_body = "x" * 5000
    text = render(PROMPT_V1, title="t", body=long_body, body_max_chars=2000)
    # The rendered prompt must not contain the full 5000-char body.
    assert "x" * 3000 not in text
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# shared/scoring/prompt.py
"""Prompt templates. Any edit REQUIRES bumping scorer_version in YAML."""

from __future__ import annotations

PROMPT_V1 = """당신은 KOSPI200 지수선물 가격 영향을 판단하는 정량 분석 AI 입니다.
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
- FOMC/CPI/고용지표/FED 인사 발언: impact >= 0.8
- 북한/지정학 군사 리스크: sentiment 음수, impact >= 0.6
- 삼성/SK하이닉스 단일 실적/CAPEX: impact 0.4~0.6
- 일반 기업 실적: impact <= 0.2
- 반복 루머/이미 반영된 이슈: impact <= 0.1
- 한국어/영어 혼재 허용, lang 관계없이 동일 기준.
"""


def render(template: str, *, title: str, body: str, body_max_chars: int = 2000) -> str:
    body_trim = body[:body_max_chars]
    return template.format(title=title, body=body_trim)
```

- [ ] **Step 4: Run — expect PASS & Commit**

---

## Task 8: `shared/scoring/llm_scorer.py` — OpenAI GPT-4o-mini

**Files:**
- Create: `shared/scoring/llm_scorer.py`, `tests/unit/scoring/test_llm_scorer.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/scoring/test_llm_scorer.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.news.base import NewsItem
from shared.scoring.budget import BudgetExceeded
from shared.scoring.llm_scorer import LLMScorer
from shared.scoring.validators import ScoringValidationError


def _news() -> NewsItem:
    return NewsItem(
        news_id="n1",
        source="yonhap",
        published_at_ms=1_700_000_000_000,
        received_at_ms=1_700_000_000_500,
        title="FOMC holds rates",
        body="Powell pushes back on cut expectations.",
        url="u",
        source_version="yonhap-v1",
        lang="en",
        keywords=[],
    )


def _fake_openai_response(content: dict) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=json.dumps(content)))]
    resp.usage = MagicMock(prompt_tokens=500, completion_tokens=100)
    return resp


@pytest.fixture
def client():
    c = MagicMock()
    c.chat.completions.create = AsyncMock()
    return c


@pytest.fixture
def budget():
    b = MagicMock()
    b.charge = AsyncMock(return_value=0.001)
    return b


async def test_happy_path(client, budget):
    client.chat.completions.create.return_value = _fake_openai_response({
        "category": "macro_us",
        "sentiment": 0.5,
        "impact_score": 0.9,
        "direction_bias": "long",
        "confidence": 0.85,
        "keywords": ["fomc"],
        "reasoning": "hawkish",
    })
    scorer = LLMScorer(
        client=client, budget=budget, model="gpt-4o-mini",
        version="gpt-4o-mini-v1",
    )
    item = await scorer.score(_news())
    assert item.category == "macro_us"
    assert item.scorer_version == "gpt-4o-mini-v1"
    budget.charge.assert_awaited_once()


async def test_retries_on_json_error_then_raises(client, budget):
    # First call returns garbage, no retry in single-shot; scorer should raise
    client.chat.completions.create.return_value = _fake_openai_response({
        "category": "macro_us"  # missing required fields
    })
    scorer = LLMScorer(
        client=client, budget=budget, model="gpt-4o-mini",
        version="gpt-4o-mini-v1", retries=0,
    )
    with pytest.raises(ScoringValidationError):
        await scorer.score(_news())


async def test_budget_exceeded_raises_before_api_call(client, budget):
    budget.charge.side_effect = BudgetExceeded("cap")
    scorer = LLMScorer(
        client=client, budget=budget, model="gpt-4o-mini",
        version="gpt-4o-mini-v1",
    )
    # We pre-charge with the estimated cost, so the API call is skipped.
    with pytest.raises(BudgetExceeded):
        await scorer.score(_news())
    client.chat.completions.create.assert_not_awaited()


async def test_timeout_raises_validation_error(client, budget):
    client.chat.completions.create.side_effect = TimeoutError("slow")
    scorer = LLMScorer(
        client=client, budget=budget, model="gpt-4o-mini",
        version="gpt-4o-mini-v1", retries=1,
    )
    with pytest.raises(TimeoutError):
        await scorer.score(_news())
    assert client.chat.completions.create.await_count == 2  # initial + 1 retry
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# shared/scoring/llm_scorer.py
"""OpenAI GPT-4o-mini scorer with budget guard + retries."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from shared.news.base import NewsItem
from shared.scoring.base import Scorer, ScoredItem
from shared.scoring.budget import DailyBudget
from shared.scoring.prompt import PROMPT_V1, render
from shared.scoring.validators import parse_llm_json

# Rough cost model for gpt-4o-mini: $0.15 / 1M input, $0.60 / 1M output (2026-04 rates).
_COST_PER_INPUT_TOKEN_USD = 0.15 / 1_000_000
_COST_PER_OUTPUT_TOKEN_USD = 0.60 / 1_000_000
_ESTIMATED_PROMPT_COST_USD = 0.0005  # pre-charge estimate


class LLMScorer(Scorer):
    def __init__(
        self,
        *,
        client: Any,                 # openai.AsyncOpenAI
        budget: DailyBudget,
        model: str,
        version: str,
        temperature: float = 0.0,
        max_tokens: int = 250,
        timeout_seconds: float = 5.0,
        retries: int = 2,
        prompt_template: str = PROMPT_V1,
        body_max_chars: int = 2000,
    ):
        self.client = client
        self.budget = budget
        self.model = model
        self.version = version
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.prompt_template = prompt_template
        self.body_max_chars = body_max_chars

    async def score(self, news: NewsItem) -> ScoredItem:
        # Pre-charge the estimated cost so a tripped budget stops us BEFORE
        # spending more API dollars. A real response that exceeds the estimate
        # gets an adjustment charge after parsing.
        await self.budget.charge(_ESTIMATED_PROMPT_COST_USD)

        prompt = render(
            self.prompt_template,
            title=news.title,
            body=news.body,
            body_max_chars=self.body_max_chars,
        )

        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        response_format={"type": "json_object"},
                    ),
                    timeout=self.timeout_seconds,
                )
                raw = resp.choices[0].message.content or ""
                payload = parse_llm_json(raw)
                actual_cost = self._estimate_actual_cost(resp)
                delta = actual_cost - _ESTIMATED_PROMPT_COST_USD
                if delta > 0:
                    await self.budget.charge(delta)
                return ScoredItem(
                    news_id=news.news_id,
                    scorer_version=self.version,
                    scored_at_ms=int(time.time() * 1000),
                    category=payload["category"],
                    sentiment=float(payload["sentiment"]),
                    impact_score=float(payload["impact_score"]),
                    direction_bias=payload["direction_bias"],
                    confidence=float(payload["confidence"]),
                    keywords=list(payload.get("keywords", []))[:ScoredItem.MAX_KEYWORDS],
                    reasoning=str(payload.get("reasoning", ""))[:200],
                )
            except TimeoutError as exc:
                last_exc = exc
                continue
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _estimate_actual_cost(resp: Any) -> float:
        usage = getattr(resp, "usage", None)
        if usage is None:
            return _ESTIMATED_PROMPT_COST_USD
        return (
            usage.prompt_tokens * _COST_PER_INPUT_TOKEN_USD
            + usage.completion_tokens * _COST_PER_OUTPUT_TOKEN_USD
        )
```

- [ ] **Step 4: Run — expect PASS & Commit**

---

## Task 9: `shared/scoring/publisher.py` — stream + CH fan-out

**Files:**
- Create: `shared/scoring/publisher.py`, `tests/unit/scoring/test_publisher.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/scoring/test_publisher.py
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from shared.scoring.base import ScoredItem
from shared.scoring.publisher import ScoredPublisher


def _item(news_id: str = "n1") -> ScoredItem:
    return ScoredItem(
        news_id=news_id,
        scorer_version="gpt-4o-mini-v1",
        scored_at_ms=1_700_000_000_000,
        category="macro_us",
        sentiment=0.5,
        impact_score=0.8,
        direction_bias="long",
        confidence=0.85,
        keywords=["fomc"],
        reasoning="hawkish",
    )


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis()


async def test_publish_writes_to_stream(redis):
    ch = AsyncMock()
    pub = ScoredPublisher(
        redis=redis, ch_client=ch, stream="stream:news.scored", maxlen=100,
    )
    await pub.publish(_item("a"))
    entries = await redis.xrange("stream:news.scored")
    assert len(entries) == 1
    assert entries[0][1][b"news_id"] == b"a"
    assert entries[0][1][b"category"] == b"macro_us"


async def test_publish_batches_ch_writes(redis):
    ch = AsyncMock()
    pub = ScoredPublisher(
        redis=redis, ch_client=ch, stream="stream:news.scored",
        maxlen=100, ch_batch_size=2,
    )
    await pub.publish(_item("a"))
    ch.execute.assert_not_awaited()
    await pub.publish(_item("b"))
    ch.execute.assert_awaited_once()


async def test_publish_flush_on_stop(redis):
    ch = AsyncMock()
    pub = ScoredPublisher(
        redis=redis, ch_client=ch, stream="stream:news.scored",
        maxlen=100, ch_batch_size=10,
    )
    await pub.publish(_item("a"))
    await pub.flush()
    ch.execute.assert_awaited_once()
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# shared/scoring/publisher.py
"""Fan-out ScoredItem → Redis stream + ClickHouse batch."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from shared.scoring.base import ScoredItem

logger = logging.getLogger(__name__)

_CH_INSERT = (
    "INSERT INTO kospi.news_scored "
    "(news_id, scorer_version, scored_at, category, sentiment, impact_score, "
    "direction_bias, confidence, keywords, reasoning) VALUES"
)


class ScoredPublisher:
    def __init__(
        self,
        *,
        redis: Any,
        ch_client: Any,
        stream: str,
        maxlen: int,
        ch_batch_size: int = 20,
    ):
        self.redis = redis
        self.ch = ch_client
        self.stream = stream
        self.maxlen = maxlen
        self.ch_batch_size = ch_batch_size
        self._buffer: list[tuple] = []
        self._lock = asyncio.Lock()

    async def publish(self, item: ScoredItem) -> None:
        fields = {
            "news_id": item.news_id,
            "scorer_version": item.scorer_version,
            "scored_at_ms": str(item.scored_at_ms),
            "category": item.category,
            "sentiment": str(item.sentiment),
            "impact_score": str(item.impact_score),
            "direction_bias": item.direction_bias,
            "confidence": str(item.confidence),
            "keywords_json": json.dumps(item.keywords),
            "reasoning": item.reasoning,
        }
        await self.redis.xadd(self.stream, fields, maxlen=self.maxlen, approximate=True)

        row = (
            item.news_id,
            item.scorer_version,
            datetime.fromtimestamp(item.scored_at_ms / 1000, tz=UTC).replace(tzinfo=None),
            item.category,
            item.sentiment,
            item.impact_score,
            item.direction_bias,
            item.confidence,
            item.keywords,
            item.reasoning,
        )
        async with self._lock:
            self._buffer.append(row)
            should_flush = len(self._buffer) >= self.ch_batch_size
        if should_flush:
            await self.flush()

    async def flush(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            rows = self._buffer
            self._buffer = []
        try:
            await self.ch.execute(_CH_INSERT, rows)
        except Exception:
            logger.exception("news_scored flush failed; dropping %d rows", len(rows))
```

- [ ] **Step 4: Run — expect PASS & Commit**

---

## Task 10: Config model + YAML

**Files:**
- Create: `config/news_scoring.yaml`
- Modify: `shared/scoring/__init__.py` — add `NewsScorerConfig`
- Create: `tests/unit/scoring/test_config.py`

- [ ] **Step 1: Write YAML**

```yaml
# config/news_scoring.yaml
news_scorer:
  consumer_group: "news_scorer-v1"
  worker_id_prefix: "scorer"
  batch_size: 10
  xread_block_ms: 5000
  input_stream: "stream:news.raw"
  output_stream: "stream:news.scored"
  output_stream_maxlen: 100000
  ch_batch_size: 20
  ch_flush_interval_seconds: 10

  scorer:
    provider: "openai"
    model: "gpt-4o-mini"
    version: "gpt-4o-mini-v1"
    temperature: 0.0
    max_tokens: 250
    timeout_seconds: 5.0
    retries: 2
    api_key_env: "OPENAI_API_KEY"

  budget:
    daily_usd_limit: 5.0
    alert_threshold_pct: 0.8

  fallback:
    on_timeout: "neutral"        # neutral | skip
    on_json_error: "neutral"
    on_budget_exceeded: "skip"

  body_truncate_chars: 2000
```

- [ ] **Step 2: Write Pydantic config + failing test**

```python
# shared/scoring/config.py
from __future__ import annotations

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase


class _ScorerSection(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    version: str = "gpt-4o-mini-v1"
    temperature: float = 0.0
    max_tokens: int = 250
    timeout_seconds: float = 5.0
    retries: int = 2
    api_key_env: str = "OPENAI_API_KEY"


class _BudgetSection(BaseModel):
    daily_usd_limit: float = 5.0
    alert_threshold_pct: float = 0.8


class _FallbackSection(BaseModel):
    on_timeout: str = "neutral"
    on_json_error: "neutral"
    on_budget_exceeded: "skip"


class NewsScorerConfig(ServiceConfigBase):
    _default_config_file = "news_scoring.yaml"
    _env_prefix = "NEWS_SCORER_"
    _section = "news_scorer"

    consumer_group: str = "news_scorer-v1"
    worker_id_prefix: str = "scorer"
    batch_size: int = 10
    xread_block_ms: int = 5000
    input_stream: str = "stream:news.raw"
    output_stream: str = "stream:news.scored"
    output_stream_maxlen: int = 100_000
    ch_batch_size: int = 20
    ch_flush_interval_seconds: int = 10
    body_truncate_chars: int = 2000
    scorer: _ScorerSection = Field(default_factory=_ScorerSection)
    budget: _BudgetSection = Field(default_factory=_BudgetSection)
    fallback: _FallbackSection = Field(default_factory=_FallbackSection)
```

Test:

```python
# tests/unit/scoring/test_config.py
from shared.scoring.config import NewsScorerConfig


def test_config_defaults():
    c = NewsScorerConfig()
    assert c.consumer_group == "news_scorer-v1"
    assert c.scorer.model == "gpt-4o-mini"
    assert c.budget.daily_usd_limit == 5.0


def test_config_from_yaml(tmp_path, monkeypatch):
    p = tmp_path / "news_scoring.yaml"
    p.write_text(
        "news_scorer:\n"
        "  batch_size: 25\n"
        "  scorer:\n"
        "    version: gpt-4o-mini-v2\n"
    )
    c = NewsScorerConfig.from_yaml(config_file=str(p))
    assert c.batch_size == 25
    assert c.scorer.version == "gpt-4o-mini-v2"
```

- [ ] **Step 3: Run — expect FAIL → implement → PASS & Commit**

---

## Task 11: `services/news_scorer/main.py` — consumer-group daemon

**Files:**
- Create: `services/news_scorer/__init__.py`, `services/news_scorer/main.py`
- Create: `tests/integration/test_news_scorer_e2e.py`

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_news_scorer_e2e.py
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest

from services.news_scorer.main import NewsScorerDaemon
from shared.scoring.base import Scorer, ScoredItem
from shared.news.base import NewsItem


class _FakeScorer(Scorer):
    version = "fake-v1"

    def __init__(self, outcomes: list[str | Exception] | None = None):
        self._outcomes = outcomes or ["ok"]
        self._idx = 0

    async def score(self, news: NewsItem) -> ScoredItem:
        outcome = self._outcomes[min(self._idx, len(self._outcomes) - 1)]
        self._idx += 1
        if isinstance(outcome, Exception):
            raise outcome
        return ScoredItem(
            news_id=news.news_id,
            scorer_version=self.version,
            scored_at_ms=1_700_000_000_000,
            category="macro_us",
            sentiment=0.4,
            impact_score=0.8,
            direction_bias="long",
            confidence=0.85,
            keywords=["k"],
            reasoning="r",
            raw_ref="",
        )


async def _seed_raw(redis, news_id: str = "n1") -> None:
    await redis.xadd("stream:news.raw", {
        "news_id": news_id, "source": "yonhap",
        "published_at_ms": "1700000000000",
        "received_at_ms": "1700000000500",
        "title": "t", "body": "b", "url": "u",
        "source_version": "yonhap-v1", "lang": "ko",
        "keywords_json": json.dumps([]),
    })


@pytest.mark.asyncio
async def test_daemon_scores_and_acks():
    redis = fakeredis.aioredis.FakeRedis()
    ch = AsyncMock()
    await _seed_raw(redis, "n1")

    scorer = _FakeScorer(outcomes=["ok"])
    fallback = _FakeScorer(outcomes=["ok"])
    fallback.version = "fallback-neutral-v1"

    daemon = NewsScorerDaemon(
        redis=redis, ch_client=ch,
        scorer=scorer, fallback=fallback,
        input_stream="stream:news.raw",
        output_stream="stream:news.scored",
        consumer_group="news_scorer-v1",
        worker_id="worker-1",
        output_maxlen=100, ch_batch_size=1,
        xread_block_ms=100, batch_size=10,
    )
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.6)
    await daemon.stop()
    await task

    # scored stream has the entry
    entries = await redis.xrange("stream:news.scored")
    assert len(entries) == 1
    # raw stream has no pending messages for the group (XACK succeeded)
    pending = await redis.xpending("stream:news.raw", "news_scorer-v1")
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_daemon_falls_back_on_scorer_failure():
    from shared.scoring.validators import ScoringValidationError

    redis = fakeredis.aioredis.FakeRedis()
    ch = AsyncMock()
    await _seed_raw(redis, "n1")

    scorer = _FakeScorer(outcomes=[ScoringValidationError("bad")])
    fallback = _FakeScorer(outcomes=["ok"])
    fallback.version = "fallback-neutral-v1"

    daemon = NewsScorerDaemon(
        redis=redis, ch_client=ch,
        scorer=scorer, fallback=fallback,
        input_stream="stream:news.raw",
        output_stream="stream:news.scored",
        consumer_group="news_scorer-v1",
        worker_id="worker-1",
        output_maxlen=100, ch_batch_size=1,
        xread_block_ms=100, batch_size=10,
    )
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.6)
    await daemon.stop()
    await task

    entries = await redis.xrange("stream:news.scored")
    assert len(entries) == 1
    assert entries[0][1][b"scorer_version"] == b"fallback-neutral-v1"
```

- [ ] **Step 2: Implement**

```python
# services/news_scorer/main.py
"""News scoring consumer-group daemon."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from typing import Any

from services.monitoring.metrics import (
    record_news_scored,
    record_news_scoring_duration,
    record_news_scoring_error,
    record_news_scoring_fallback,
    record_news_scorer_backlog,
)
from shared.news.base import NewsItem
from shared.scoring.base import Scorer
from shared.scoring.budget import BudgetExceeded
from shared.scoring.publisher import ScoredPublisher
from shared.scoring.validators import ScoringValidationError

logger = logging.getLogger(__name__)


def _news_from_stream_fields(fields: dict[bytes, bytes]) -> NewsItem:
    def _s(key: str, default: str = "") -> str:
        raw = fields.get(key.encode(), b"")
        return raw.decode() if isinstance(raw, bytes) else str(raw or default)

    return NewsItem(
        news_id=_s("news_id"),
        source=_s("source"),
        published_at_ms=int(_s("published_at_ms", "0") or 0),
        received_at_ms=int(_s("received_at_ms", "0") or 0),
        title=_s("title"),
        body=_s("body"),
        url=_s("url"),
        source_version=_s("source_version"),
        lang=_s("lang"),
        keywords=json.loads(_s("keywords_json", "[]") or "[]"),
    )


class NewsScorerDaemon:
    def __init__(
        self,
        *,
        redis: Any,
        ch_client: Any,
        scorer: Scorer,
        fallback: Scorer,
        input_stream: str,
        output_stream: str,
        consumer_group: str,
        worker_id: str,
        output_maxlen: int,
        ch_batch_size: int,
        xread_block_ms: int,
        batch_size: int,
    ):
        self.redis = redis
        self.scorer = scorer
        self.fallback = fallback
        self.input_stream = input_stream
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.batch_size = batch_size
        self.xread_block_ms = xread_block_ms
        self.publisher = ScoredPublisher(
            redis=redis,
            ch_client=ch_client,
            stream=output_stream,
            maxlen=output_maxlen,
            ch_batch_size=ch_batch_size,
        )
        self._stop = asyncio.Event()

    async def run(self) -> None:
        try:
            await self.redis.xgroup_create(
                self.input_stream, self.consumer_group, id="0", mkstream=True
            )
        except Exception:
            # group already exists
            pass

        try:
            while not self._stop.is_set():
                try:
                    messages = await self.redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.worker_id,
                        streams={self.input_stream: ">"},
                        count=self.batch_size,
                        block=self.xread_block_ms,
                    )
                except Exception:
                    logger.exception("xreadgroup failed")
                    await asyncio.sleep(1.0)
                    continue

                await self._update_backlog_metric()

                if not messages:
                    continue

                for _stream, msgs in messages:
                    for msg_id, data in msgs:
                        await self._process(msg_id, data)
        finally:
            await self.publisher.flush()

    async def stop(self) -> None:
        self._stop.set()

    async def _process(self, msg_id: bytes, fields: dict[bytes, bytes]) -> None:
        try:
            news = _news_from_stream_fields(fields)
        except Exception:
            record_news_scoring_error("parse_error")
            logger.exception("failed to parse news fields")
            # ACK — message is structurally broken; dropping is better than infinite retry
            await self.redis.xack(self.input_stream, self.consumer_group, msg_id)
            return

        start = asyncio.get_event_loop().time()
        try:
            item = await self.scorer.score(news)
            record_news_scored(self.scorer.version, item.category)
        except BudgetExceeded:
            item = await self.fallback.score(news)
            record_news_scoring_fallback("budget")
        except ScoringValidationError:
            item = await self.fallback.score(news)
            record_news_scoring_fallback("json_error")
        except TimeoutError:
            item = await self.fallback.score(news)
            record_news_scoring_fallback("timeout")
        except Exception:
            record_news_scoring_error("scorer_unknown")
            logger.exception("unknown scorer error news_id=%s", news.news_id)
            # Don't ACK; leave message pending for retry.
            return

        record_news_scoring_duration(
            self.scorer.version, asyncio.get_event_loop().time() - start
        )

        try:
            await self.publisher.publish(item)
        except Exception:
            record_news_scoring_error("publish_error")
            logger.exception("publisher failed news_id=%s", news.news_id)
            return

        await self.redis.xack(self.input_stream, self.consumer_group, msg_id)

    async def _update_backlog_metric(self) -> None:
        try:
            info = await self.redis.xpending(self.input_stream, self.consumer_group)
            # redis-py returns dict{"pending": int, ...} or a tuple depending on version
            if isinstance(info, dict):
                count = int(info.get("pending", 0))
            else:
                count = int(info[0]) if info else 0
            record_news_scorer_backlog(count)
        except Exception:
            logger.debug("backlog query failed", exc_info=True)
```

- [ ] **Step 3: Build-and-run wrapper (CLI entry)**

Add at the bottom of `services/news_scorer/main.py`:

```python
async def _build_and_run() -> int:
    import os
    import socket

    import aioredis
    from openai import AsyncOpenAI

    from shared.db.client import AsyncClickHouseClient
    from shared.db.config import ClickHouseConfig
    from shared.scoring.budget import DailyBudget
    from shared.scoring.config import NewsScorerConfig
    from shared.scoring.fallback import FallbackScorer
    from shared.scoring.llm_scorer import LLMScorer

    cfg = NewsScorerConfig.from_yaml()
    redis = aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/1"))
    ch = AsyncClickHouseClient(ClickHouseConfig.from_env(database="kospi"))
    await ch.connect()

    openai_client = AsyncOpenAI(api_key=os.environ[cfg.scorer.api_key_env])
    budget = DailyBudget(redis, daily_usd_limit=cfg.budget.daily_usd_limit)
    llm = LLMScorer(
        client=openai_client, budget=budget,
        model=cfg.scorer.model, version=cfg.scorer.version,
        temperature=cfg.scorer.temperature,
        max_tokens=cfg.scorer.max_tokens,
        timeout_seconds=cfg.scorer.timeout_seconds,
        retries=cfg.scorer.retries,
        body_max_chars=cfg.body_truncate_chars,
    )
    fallback = FallbackScorer()

    worker_id = f"{cfg.worker_id_prefix}-{socket.gethostname()}-{os.getpid()}"
    daemon = NewsScorerDaemon(
        redis=redis, ch_client=ch,
        scorer=llm, fallback=fallback,
        input_stream=cfg.input_stream,
        output_stream=cfg.output_stream,
        consumer_group=cfg.consumer_group,
        worker_id=worker_id,
        output_maxlen=cfg.output_stream_maxlen,
        ch_batch_size=cfg.ch_batch_size,
        xread_block_ms=cfg.xread_block_ms,
        batch_size=cfg.batch_size,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await openai_client.close()
        await redis.aclose()
        await ch.close()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

- [ ] **Step 4: Run tests — expect PASS & Commit**

---

## Task 12: Prometheus metrics

**Files:**
- Modify: `services/monitoring/metrics.py` — add 6 scorer families
- Create: `tests/unit/monitoring/test_scorer_metrics.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/monitoring/test_scorer_metrics.py
from services.monitoring.metrics import (
    news_scored_total,
    news_scoring_duration_seconds,
    news_scoring_errors_total,
    news_scoring_fallback_total,
    news_scoring_cost_usd_today,
    news_scorer_backlog,
    record_news_scored,
    record_news_scoring_duration,
    record_news_scoring_error,
    record_news_scoring_fallback,
    record_news_scoring_cost,
    record_news_scorer_backlog,
)


def test_metric_families_exist():
    assert news_scored_total is not None
    assert news_scoring_duration_seconds is not None


def test_record_helpers_do_not_raise():
    record_news_scored("gpt-4o-mini-v1", "macro_us")
    record_news_scoring_duration("gpt-4o-mini-v1", 0.5)
    record_news_scoring_error("timeout")
    record_news_scoring_fallback("budget")
    record_news_scoring_cost(3.5)
    record_news_scorer_backlog(42)
```

- [ ] **Step 2: Implement — extend `services/monitoring/metrics.py`**

```python
news_scored_total = Counter(
    "news_scored_total",
    "Total news items scored",
    ["version", "category"],
    registry=REGISTRY,
)
news_scoring_duration_seconds = Histogram(
    "news_scoring_duration_seconds",
    "Scoring latency per item",
    ["version"],
    buckets=(0.1, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0),
    registry=REGISTRY,
)
news_scoring_errors_total = Counter(
    "news_scoring_errors_total",
    "Scoring errors by kind",
    ["kind"],
    registry=REGISTRY,
)
news_scoring_fallback_total = Counter(
    "news_scoring_fallback_total",
    "Fallback invocations by reason",
    ["reason"],
    registry=REGISTRY,
)
news_scoring_cost_usd_today = Gauge(
    "news_scoring_cost_usd_today",
    "Cumulative LLM cost in USD for the current day",
    registry=REGISTRY,
)
news_scorer_backlog = Gauge(
    "news_scorer_backlog",
    "Consumer-group pending (XPENDING) count",
    registry=REGISTRY,
)


def record_news_scored(version: str, category: str) -> None:
    news_scored_total.labels(version=version, category=category).inc()


def record_news_scoring_duration(version: str, seconds: float) -> None:
    news_scoring_duration_seconds.labels(version=version).observe(seconds)


def record_news_scoring_error(kind: str) -> None:
    news_scoring_errors_total.labels(kind=kind).inc()


def record_news_scoring_fallback(reason: str) -> None:
    news_scoring_fallback_total.labels(reason=reason).inc()


def record_news_scoring_cost(usd: float) -> None:
    news_scoring_cost_usd_today.set(usd)


def record_news_scorer_backlog(count: int) -> None:
    news_scorer_backlog.set(count)
```

- [ ] **Step 3: Run tests — expect PASS & Commit**

---

## Task 13: systemd unit + deployment

**Files:**
- Create: `deploy/systemd/kis-news-scorer.service`
- Modify: `docs/runbooks/phase2-verification.md` (Task 14)

- [ ] **Step 1: Write unit file**

```ini
[Unit]
Description=KIS News Scorer (Phase 2, consumer group)
After=network-online.target redis-server.service kis-news-collector.service
Wants=network-online.target
Requires=kis-news-collector.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/project/kis_unified_sts
EnvironmentFile=/home/deploy/project/kis_unified_sts/.env
ExecStart=/home/deploy/project/kis_unified_sts/.venv/bin/python -m services.news_scorer.main
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Commit**

```bash
git add deploy/systemd/kis-news-scorer.service
git commit -m "chore(deploy): systemd unit for Phase 2 news scorer"
```

---

## Task 14: CLI glue coverage (mirror Phase 1 pattern)

**Files:**
- Create: `tests/unit/services/test_news_scorer_main.py`

- [ ] **Step 1: Write tests using monkeypatch pattern**

Follow the pattern established in `tests/unit/news/test_collector_main.py` (Phase 1):
- Patch `aioredis.from_url`, `AsyncClickHouseClient`, `ClickHouseConfig.from_env`, `AsyncOpenAI`
- Patch `NewsScorerConfig.from_yaml`
- Replace `NewsScorerDaemon.run` with a fast-run that sets `_stop` immediately
- Assert cleanup (`openai_client.close`, `redis.aclose`, `ch.close`) is awaited
- Separate test for `main()` wrapper

Aim for ≥80% coverage on `services/news_scorer/main.py`.

- [ ] **Step 2: Run + Commit**

---

## Task 15: Golden-set agreement harness

**Files:**
- Create: `tests/integration/test_news_scorer_golden.py`
- Create: `tests/fixtures/news_scoring_golden.json` (empty array placeholder initially)

- [ ] **Step 1: Placeholder fixture**

```json
[
  {
    "news_id": "example-001",
    "title": "FOMC holds rates; Powell hawkish",
    "body": "...",
    "human_label": {
      "category": "macro_us",
      "direction_bias": "long"
    }
  }
]
```

Document: during 48h gate, pull 100 random items from `stream:news.raw`, hand-label, overwrite this file.

- [ ] **Step 2: Write agreement test**

```python
# tests/integration/test_news_scorer_golden.py
"""Golden-set regression — run whenever scorer_version changes."""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.news.base import NewsItem
from shared.scoring.llm_scorer import LLMScorer

GOLDEN = Path("tests/fixtures/news_scoring_golden.json")


@pytest.mark.skipif(
    not os.environ.get("RUN_GOLDEN"),
    reason="requires RUN_GOLDEN=1 and network + OPENAI_API_KEY",
)
def test_category_agreement_at_least_70_percent():
    items = json.loads(GOLDEN.read_text())
    if not items:
        pytest.skip("golden set empty — populate during 48h gate")

    # This test intentionally hits real OpenAI. Kept out of default CI.
    from openai import AsyncOpenAI
    import asyncio

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    budget = MagicMock(charge=AsyncMock(return_value=0.0))
    scorer = LLMScorer(
        client=client, budget=budget,
        model="gpt-4o-mini", version="gpt-4o-mini-v1",
    )

    async def _run():
        hits = 0
        for row in items:
            news = NewsItem(
                news_id=row["news_id"],
                source="golden",
                published_at_ms=0, received_at_ms=0,
                title=row["title"], body=row.get("body", ""),
                url="", source_version="", lang="ko", keywords=[],
            )
            item = await scorer.score(news)
            if item.category == row["human_label"]["category"]:
                hits += 1
        return hits / len(items)

    agreement = asyncio.run(_run())
    assert agreement >= 0.70, f"category agreement {agreement:.2%} < 70%"
```

- [ ] **Step 3: Commit**

---

## Task 16: Full test sweep + runbook

**Files:**
- Create: `docs/runbooks/phase2-verification.md`

- [ ] **Step 1: Full sweep**

```bash
source .venv/bin/activate
pytest tests/unit/scoring/ tests/unit/services/test_news_scorer_main.py \
       tests/unit/monitoring/test_scorer_metrics.py \
       tests/integration/test_news_scorer_e2e.py \
       tests/unit/migrations/test_v2_migration.py \
       --cov=shared/scoring --cov=services/news_scorer \
       --cov-report=term-missing
```

Expected: coverage ≥ 80% on both modules.

- [ ] **Step 2: Write `docs/runbooks/phase2-verification.md`**

```markdown
# Phase 2 Completion Gate — 48h Verification

Target spec: `docs/plans/2026-04-20-futures-paradigm-phase2-scoring.md` §10.
Implementation plan: `docs/plans/2026-04-20-futures-paradigm-phase2-implementation-plan.md`.
Branch: `feat/futures-paradigm-phase2`.

## 1. ClickHouse schema
- [ ] V2 migration applied (idempotent):
      `python scripts/migrations/apply_clickhouse_migrations.py`
- [ ] `kospi.news_scored` has 10 columns (see DESC)

## 2. Scorer daemon uptime
- [ ] systemd unit installed and running 48h, NRestarts=0
      `systemctl show kis-news-scorer -p NRestarts`
- [ ] journalctl has no repeated errors in last 48h

## 3. Consumer-group lag
- [ ] XPENDING for news_scorer-v1 < 100 continuously
      `redis-cli -n 1 XPENDING stream:news.raw news_scorer-v1`

## 4. Scoring volume & cost
- [ ] ≥ 1,000 scored rows in CH:
      `SELECT count() FROM kospi.news_scored WHERE scored_at >= now() - INTERVAL 2 DAY`
- [ ] Daily LLM cost < $5 per day (Prometheus gauge)

## 5. Agreement
- [ ] 100 random items hand-labeled into `tests/fixtures/news_scoring_golden.json`
- [ ] `RUN_GOLDEN=1 pytest tests/integration/test_news_scorer_golden.py -v`
- [ ] Category agreement ≥ 70%; direction agreement ≥ 75%

## 6. Fallback ratio
- [ ] `news_scoring_fallback_total / news_scored_total` < 0.05 over 48h

## 7. `rl_mppo` unaffected
- [ ] Same latency + PnL operational dashboard comparison as Phase 1

## 8. Prometheus spot-check
- [ ] `curl -s :9091/metrics | grep -E "news_scored_total|news_scoring_duration_seconds"`

## 9. Rollback
- `sudo systemctl stop kis-news-scorer && sudo systemctl disable kis-news-scorer`
- Delete systemd file, `daemon-reload`
- News scoring stops; raw stream continues (Phase 1 unaffected)
- V2 table left in place (empty rows don't harm)
```

- [ ] **Step 3: Open draft PR**

```bash
git push -u origin feat/futures-paradigm-phase2
gh pr create --draft \
  --title "feat: Phase 2 — news scoring consumer group" \
  --body "Implements docs/plans/2026-04-20-futures-paradigm-phase2-scoring.md.
Ready for review but NOT ready to merge — awaiting 48h gate verification
per docs/runbooks/phase2-verification.md."
```

---

## Self-Review

**1. Spec coverage (phase2-scoring.md §2–§10):**

| Spec item | Tasks |
|-----------|-------|
| V2 migration | 2 |
| ScoredItem + Scorer ABC | 3 |
| JSON validator | 4 |
| Fallback | 5 |
| Budget tracker | 6 |
| Prompt (versioned) | 7 |
| LLM scorer with retries | 8 |
| Publisher (stream + CH) | 9 |
| Pydantic config + YAML | 10 |
| Consumer-group daemon | 11 |
| Prometheus metrics | 12 |
| Systemd unit | 13 |
| CLI coverage | 14 |
| Golden-set harness | 15 |
| Runbook | 16 |

**2. Type consistency:** `NewsItem` (from Phase 1) and `ScoredItem` are the only cross-task types. `ScoredPublisher.publish(item: ScoredItem)` matches the daemon caller. `Scorer.score(news: NewsItem) → ScoredItem` is consistent across `LLMScorer` and `FallbackScorer`.

**3. Placeholder scan:** `tests/fixtures/news_scoring_golden.json` is deliberately empty on merge — populated during the 48h gate. Golden test is skipped unless `RUN_GOLDEN=1` + `OPENAI_API_KEY` are set, so CI is not blocked. Everything else is concrete.

**4. Risks flagged in spec §6 addressed:**
- LLM cost: daily budget cap + alert (Task 6)
- Prompt drift: scorer_version bump + golden regression test (Tasks 7, 15)
- Consumer-group lag: XPENDING metric + Prometheus alert (Tasks 11, 12)
- RL unaffected: no modifications to Phase 1 modules or RL pipeline (convention reminder)

---

## Execution Handoff

**Two execution options (same as Phase 1):**

1. **Subagent-Driven (recommended):** one fresh subagent per task. Each task has its own test-first boundary, minimal shared state.
2. **Inline:** execute tasks in-session with `superpowers:executing-plans`; checkpoint after every 3 tasks.

Run `/review docs/plans/2026-04-20-futures-paradigm-phase2-implementation-plan.md` with Momus before starting if you want a critic pass.
