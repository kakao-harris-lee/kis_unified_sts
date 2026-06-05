# Futures Paradigm — Phase 1 Data Infrastructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 뉴스/매크로 수집 데몬 2종 + ClickHouse 마이그레이션 인프라 + Redis streams 스키마를 구축해 Phase 2 스코어링의 데이터 공급 레이어를 확보한다.

**Architecture:** 소스 불가지론적 `NewsSource` ABC를 정의하고, 어댑터(DART/Yonhap/Reuters/MK)를 pluggable로 구성. 각 소스는 독립 async loop에서 polling → dedupe → Redis XADD + ClickHouse batch insert. 매크로는 cron 기반 배치. 모든 서비스는 기존 `ServiceConfigBase` + `shared/streaming/publisher.py` + `shared/db/client.py` 재사용.

**Tech Stack:** Python 3.11+, asyncio, `redis.asyncio`, `aiohttp`, `feedparser`, `pydantic v2`, `pytest` + `pytest-asyncio` + `fakeredis` + `aioresponses`. 기존 `shared/config/base.py::ServiceConfigBase` 패턴 준수.

**Parent spec:** `docs/plans/2026-04-20-futures-paradigm-phase1-data-infra.md`

---

## File Structure

**Create (new files):**

```
infra/clickhouse/migrations/
├── __init__.py
└── V1__create_futures_paradigm_tables.sql     # 5 tables (news_raw, macro_overnight, schema_migrations, signals_all, daily_performance)

scripts/migrations/
└── apply_clickhouse_migrations.py              # idempotent migration runner

shared/news/
├── __init__.py
├── base.py                                     # NewsItem dataclass + NewsSource ABC
├── dedupe.py                                   # 2-tier LRU + Redis SET dedupe
├── publisher.py                                # stream:news.raw publisher wrapper + CH writer
└── sources/
    ├── __init__.py
    ├── dart.py                                 # wraps existing DARTDataCollector
    ├── yonhap.py                               # RSS adapter
    ├── reuters.py                              # RSS adapter
    └── mk_adapter.py                           # wraps existing MKStockNewsCollector

shared/macro/
├── __init__.py
├── base.py                                     # MacroSnapshot dataclass
└── sources/
    ├── __init__.py
    ├── yahoo.py                                # yfinance adapter (SP500/Nasdaq/VIX/DXY/US10Y)
    └── ecos.py                                 # 한국은행 ECOS adapter (USDKRW)

services/news_collector/
├── __init__.py
└── main.py                                     # long-running daemon

services/macro_overnight_collector/
├── __init__.py
└── main.py                                     # batch CLI entry point

config/
├── news_sources.yaml                           # NewsCollectorConfig
└── macro_sources.yaml                          # MacroCollectorConfig

scripts/cron/
└── macro_overnight.sh                          # cron wrapper

deploy/systemd/
├── kis-news-collector.service
└── kis-macro-overnight.service                 # oneshot

tests/unit/news/
├── __init__.py
├── test_base.py
├── test_dedupe.py
├── test_publisher.py
└── sources/
    ├── __init__.py
    ├── test_dart.py
    ├── test_yonhap.py
    ├── test_reuters.py
    └── test_mk_adapter.py

tests/unit/macro/
├── __init__.py
├── test_yahoo.py
└── test_ecos.py

tests/unit/migrations/
└── test_migration_runner.py

tests/integration/
├── test_news_collector_e2e.py
└── test_macro_overnight_e2e.py
```

**Modify (existing files):**

- `services/monitoring/metrics.py` — add news/macro Prometheus metrics
- `pyproject.toml` — add `feedparser`, `yfinance` (already present?), `aioresponses` to dev deps
- `CLAUDE.md` — no change in this phase (Phase 5 updates)

---

## Conventions Reminder (applies to all tasks)

- **Feature branch:** work on `feat/futures-paradigm-phase1` (never commit to main)
- **Test runner:** `source .venv/bin/activate && pytest` — NOT system pytest (memory: `pytest-mock` fixture conflict)
- **Redis DB:** always `REDIS_DB=1` (memory)
- **Test isolation:** use `fakeredis` for Redis, `aioresponses` for HTTP, `testcontainers[clickhouse]` or sqlite-backed mock for ClickHouse (avoid real CH in unit tests)
- **Formatting:** `black . && ruff check --fix .` before every commit
- **Commit message style:** `feat(news): ...`, `test(news): ...`, `chore(infra): ...`

---

## Task 1: Scaffold feature branch + dependency additions

**Files:**
- Modify: `pyproject.toml`
- No test (infra task)

- [ ] **Step 1: Create feature branch**

```bash
git checkout main
git pull
git checkout -b feat/futures-paradigm-phase1
```

- [ ] **Step 2: Add dependencies to pyproject.toml**

Add to the relevant dependency section (adjust grouping to match existing file):

```toml
# Core deps (if not already present)
feedparser = "^6.0.11"
yfinance = "^0.2.40"                # check if already present; if yes skip

# Dev deps
aioresponses = "^0.7.6"
fakeredis = "^2.23.0"                # check if already present
pytest-asyncio = "^0.23.0"           # check if already present
```

- [ ] **Step 3: Install & verify**

Run:
```bash
source .venv/bin/activate
pip install -e .
pip install feedparser aioresponses
python -c "import feedparser, yfinance, aioresponses; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore(phase1): add feedparser, aioresponses, yfinance deps"
```

---

## Task 2: ClickHouse migration runner

**Files:**
- Create: `scripts/migrations/__init__.py` (empty)
- Create: `scripts/migrations/apply_clickhouse_migrations.py`
- Test: `tests/unit/migrations/test_migration_runner.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/migrations/__init__.py` (empty) and `tests/unit/migrations/test_migration_runner.py`:

```python
import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.migrations.apply_clickhouse_migrations import (
    MigrationRunner,
    DiscoveredMigration,
)


def test_discover_migrations_orders_by_version(tmp_path):
    (tmp_path / "V2__later.sql").write_text("SELECT 1;")
    (tmp_path / "V1__first.sql").write_text("SELECT 2;")
    (tmp_path / "V10__tenth.sql").write_text("SELECT 3;")

    runner = MigrationRunner(client=MagicMock(), migrations_dir=tmp_path)
    result = runner.discover()

    assert [m.version for m in result] == ["V1", "V2", "V10"]


def test_apply_skips_already_applied(tmp_path):
    (tmp_path / "V1__first.sql").write_text("CREATE TABLE foo (x Int32) ENGINE = MergeTree() ORDER BY x;")
    client = MagicMock()
    # Return V1 as already applied
    client.execute.return_value = [("V1",)]
    runner = MigrationRunner(client=client, migrations_dir=tmp_path)
    applied = runner.apply_all()
    assert applied == []


def test_apply_executes_and_records(tmp_path):
    sql = "CREATE TABLE kospi.foo (x Int32) ENGINE = MergeTree() ORDER BY x;"
    (tmp_path / "V1__first.sql").write_text(sql)
    client = MagicMock()
    client.execute.return_value = []   # nothing applied yet
    runner = MigrationRunner(client=client, migrations_dir=tmp_path)
    applied = runner.apply_all()
    assert applied == ["V1"]

    # Verify execute called with the SQL and then INSERT into schema_migrations
    calls = [c.args[0] for c in client.execute.call_args_list]
    assert any("CREATE TABLE kospi.foo" in c for c in calls)
    assert any("INSERT INTO kospi.schema_migrations" in c for c in calls)


def test_checksum_stable(tmp_path):
    (tmp_path / "V1__first.sql").write_text("SELECT 1;")
    runner = MigrationRunner(client=MagicMock(), migrations_dir=tmp_path)
    migrations = runner.discover()
    expected = hashlib.sha256(b"SELECT 1;").hexdigest()
    assert migrations[0].checksum == expected
```

- [ ] **Step 2: Run test — expect FAIL (no module yet)**

```bash
source .venv/bin/activate
pytest tests/unit/migrations/test_migration_runner.py -v
```

Expected: ImportError / ModuleNotFoundError

- [ ] **Step 3: Implement migration runner**

Create `scripts/migrations/__init__.py` (empty).

Create `scripts/migrations/apply_clickhouse_migrations.py`:

```python
"""ClickHouse migration runner (idempotent, checksum-tracked)."""
from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

VERSION_RE = re.compile(r"^(V\d+)__.*\.sql$")


class CHClientProtocol(Protocol):
    def execute(self, query: str, *args, **kwargs): ...


@dataclass(frozen=True)
class DiscoveredMigration:
    version: str
    path: Path
    sql: str
    checksum: str


class MigrationRunner:
    """Applies .sql files in order, tracks in kospi.schema_migrations."""

    def __init__(self, client: CHClientProtocol, migrations_dir: Path):
        self.client = client
        self.migrations_dir = Path(migrations_dir)

    def discover(self) -> list[DiscoveredMigration]:
        found: list[DiscoveredMigration] = []
        for p in sorted(self.migrations_dir.glob("V*.sql")):
            m = VERSION_RE.match(p.name)
            if not m:
                continue
            sql = p.read_text(encoding="utf-8")
            cksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            found.append(DiscoveredMigration(version=m.group(1), path=p, sql=sql, checksum=cksum))
        found.sort(key=lambda mig: int(mig.version[1:]))
        return found

    def _ensure_tracking_table(self) -> None:
        self.client.execute(
            "CREATE TABLE IF NOT EXISTS kospi.schema_migrations ("
            " version String, applied_at DateTime DEFAULT now(), checksum String"
            ") ENGINE = MergeTree() ORDER BY version"
        )

    def _already_applied(self) -> set[str]:
        rows = self.client.execute("SELECT version FROM kospi.schema_migrations") or []
        return {r[0] for r in rows}

    def apply_all(self) -> list[str]:
        self._ensure_tracking_table()
        applied_now: list[str] = []
        already = self._already_applied()
        for mig in self.discover():
            if mig.version in already:
                logger.info("skip %s (already applied)", mig.version)
                continue
            logger.info("applying %s (%s)", mig.version, mig.checksum[:8])
            for stmt in _split_sql(mig.sql):
                self.client.execute(stmt)
            self.client.execute(
                "INSERT INTO kospi.schema_migrations (version, checksum) VALUES",
                [(mig.version, mig.checksum)],
            )
            applied_now.append(mig.version)
        return applied_now


def _split_sql(sql: str) -> list[str]:
    """Naive split on `;` at line end. Rejects nested statements (good enough for DDL)."""
    parts = [p.strip() for p in sql.split(";")]
    return [p for p in parts if p]


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrations-dir", default="infra/clickhouse/migrations")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from shared.db.client import ClickHouseClient  # type: ignore

    client = ClickHouseClient.get_instance().sync_client
    runner = MigrationRunner(client=client, migrations_dir=Path(args.migrations_dir))
    applied = runner.apply_all()
    print(f"applied: {applied}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/unit/migrations/test_migration_runner.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
black scripts/migrations/ tests/unit/migrations/ && ruff check --fix scripts/migrations/ tests/unit/migrations/
git add scripts/migrations/ tests/unit/migrations/
git commit -m "feat(infra): ClickHouse migration runner (idempotent, checksum-tracked)"
```

---

## Task 3: V1 migration — create 5 Phase-1 tables

**Files:**
- Create: `infra/clickhouse/migrations/__init__.py` (empty)
- Create: `infra/clickhouse/migrations/V1__create_futures_paradigm_tables.sql`

- [ ] **Step 1: Create directories**

```bash
mkdir -p infra/clickhouse/migrations
touch infra/clickhouse/migrations/__init__.py
```

- [ ] **Step 2: Write V1 SQL**

Create `infra/clickhouse/migrations/V1__create_futures_paradigm_tables.sql`:

```sql
-- Phase 1 tables for futures paradigm shift
-- Spec: docs/plans/2026-04-20-futures-paradigm-phase1-data-infra.md

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

Note: `schema_migrations` is created by the runner itself (Task 2). Not included here.

- [ ] **Step 3: Apply migration in a local ClickHouse test instance**

```bash
# Assume local ClickHouse is running (per memory: native on server)
source .venv/bin/activate
python scripts/migrations/apply_clickhouse_migrations.py
```

Expected output: `applied: ['V1']` (first run) or `applied: []` (subsequent).

- [ ] **Step 4: Verify tables via ClickHouse HTTP**

```bash
curl -s 'http://localhost:8123/?query=SHOW%20TABLES%20FROM%20kospi' \
  --user default:"$CLICKHOUSE_PASSWORD" \
  | grep -E 'news_raw|macro_overnight|signals_all|daily_performance|schema_migrations'
```

Expected: all 5 names appear.

- [ ] **Step 5: Commit**

```bash
git add infra/clickhouse/migrations/
git commit -m "feat(infra): V1 migration — 5 Phase-1 tables (news_raw, macro_overnight, signals_all, daily_performance, schema_migrations)"
```

---

## Task 4: `shared/news/base.py` — NewsItem + NewsSource ABC

**Files:**
- Create: `shared/news/__init__.py` (empty)
- Create: `shared/news/base.py`
- Test: `tests/unit/news/test_base.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/news/__init__.py` (empty). Create `tests/unit/news/test_base.py`:

```python
import pytest

from shared.news.base import NewsItem, NewsSource


def test_news_item_construction():
    item = NewsItem(
        news_id="dart_001",
        source="dart",
        published_at_ms=1_700_000_000_000,
        received_at_ms=1_700_000_001_000,
        title="title",
        body="body",
        url="https://example.com/1",
        source_version="dart-v1",
        lang="ko",
        keywords=["공시"],
    )
    assert item.news_id == "dart_001"
    assert item.keywords == ["공시"]


def test_news_item_is_frozen():
    item = NewsItem(
        news_id="x", source="y", published_at_ms=0, received_at_ms=0,
        title="", body="", url="", source_version="", lang="ko", keywords=[],
    )
    with pytest.raises(Exception):
        item.title = "changed"   # type: ignore[misc]


def test_news_item_to_stream_fields_are_strings():
    item = NewsItem(
        news_id="x", source="y", published_at_ms=1000, received_at_ms=2000,
        title="T", body="B" * 3000, url="u",
        source_version="v", lang="ko", keywords=["a", "b"],
    )
    d = item.to_stream_dict(max_body_chars=2000)
    assert d["news_id"] == "x"
    assert len(d["body"]) <= 2000 + len("...[truncated]")
    assert d["body"].endswith("...[truncated]")
    # published/received as ms integers (kept as-is; publisher converts to str)
    assert d["published_at_ms"] == 1000


def test_news_source_is_abstract():
    with pytest.raises(TypeError):
        NewsSource()   # type: ignore[abstract]
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/unit/news/test_base.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `shared/news/base.py`**

Create `shared/news/__init__.py` (empty). Create `shared/news/base.py`:

```python
"""Pluggable news source framework."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


_TRUNCATION_MARKER = "...[truncated]"


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
    keywords: list[str] = field(default_factory=list)

    def to_stream_dict(self, max_body_chars: int = 2000) -> dict:
        body = self.body
        if len(body) > max_body_chars:
            body = body[:max_body_chars] + _TRUNCATION_MARKER
        return {
            "news_id": self.news_id,
            "source": self.source,
            "published_at_ms": self.published_at_ms,
            "received_at_ms": self.received_at_ms,
            "title": self.title,
            "body": body,
            "url": self.url,
            "source_version": self.source_version,
            "lang": self.lang,
            "keywords": self.keywords,
        }


class NewsSource(ABC):
    """Async source. Framework handles dedupe, publish, logging.

    Subclasses:
      - set class attributes: name, version, poll_interval_seconds
      - implement fetch() yielding NewsItem instances (dedup-naive).
    """

    name: str
    version: str
    poll_interval_seconds: int

    @abstractmethod
    async def fetch(self) -> AsyncIterator[NewsItem]:
        """Yield NewsItems from one polling cycle. Must be side-effect-free."""
        raise NotImplementedError
        yield  # pragma: no cover — makes this an async generator

    async def healthcheck(self) -> bool:
        """Override if source has a cheap readiness check. Default: True."""
        return True
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/unit/news/test_base.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
black shared/news/ tests/unit/news/ && ruff check --fix shared/news/ tests/unit/news/
git add shared/news/ tests/unit/news/
git commit -m "feat(news): NewsItem dataclass + NewsSource ABC with body truncation"
```

---

## Task 5: `shared/news/dedupe.py` — 2-tier LRU + Redis SET

**Files:**
- Create: `shared/news/dedupe.py`
- Test: `tests/unit/news/test_dedupe.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/news/test_dedupe.py`:

```python
import pytest
import fakeredis.aioredis

from shared.news.dedupe import NewsDedupe


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis()


@pytest.mark.asyncio
async def test_new_id_is_not_duplicate(redis):
    d = NewsDedupe(redis, memory_size=10, ttl_days=1)
    assert await d.is_duplicate("dart_001") is False


@pytest.mark.asyncio
async def test_marked_id_is_duplicate_via_memory(redis):
    d = NewsDedupe(redis, memory_size=10, ttl_days=1)
    await d.mark_seen("dart_001")
    assert await d.is_duplicate("dart_001") is True


@pytest.mark.asyncio
async def test_duplicate_via_redis_when_memory_evicted(redis):
    d = NewsDedupe(redis, memory_size=2, ttl_days=1)
    await d.mark_seen("a")
    await d.mark_seen("b")
    await d.mark_seen("c")     # evicts "a" from memory
    assert "a" not in d.memory
    # Still duplicate because redis persists it
    assert await d.is_duplicate("a") is True


@pytest.mark.asyncio
async def test_ttl_set_on_redis_key(redis):
    d = NewsDedupe(redis, memory_size=10, ttl_days=7)
    await d.mark_seen("x")
    ttl = await redis.ttl("news:seen:v1:x")
    # ttl > 0 means expiration is set
    assert 0 < ttl <= 7 * 86400
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/unit/news/test_dedupe.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement**

Create `shared/news/dedupe.py`:

```python
"""Two-tier news ID dedupe: in-process LRU + Redis SET with TTL."""
from __future__ import annotations

from collections import OrderedDict
from typing import Any


class _LRU:
    def __init__(self, max_size: int):
        self.max_size = max_size
        self._d: OrderedDict[str, bool] = OrderedDict()

    def __contains__(self, key: str) -> bool:
        if key in self._d:
            self._d.move_to_end(key)
            return True
        return False

    def add(self, key: str) -> None:
        if key in self._d:
            self._d.move_to_end(key)
            return
        self._d[key] = True
        if len(self._d) > self.max_size:
            self._d.popitem(last=False)


class NewsDedupe:
    """Two-tier dedupe. Async-friendly (Redis async client)."""

    KEY_PREFIX = "news:seen:v1:"

    def __init__(self, redis: Any, memory_size: int = 20_000, ttl_days: int = 7):
        self.redis = redis
        self.memory = _LRU(memory_size)
        self.ttl_seconds = ttl_days * 86400

    async def is_duplicate(self, news_id: str) -> bool:
        if news_id in self.memory:
            return True
        exists = await self.redis.exists(self.KEY_PREFIX + news_id)
        if exists:
            self.memory.add(news_id)
            return True
        return False

    async def mark_seen(self, news_id: str) -> None:
        self.memory.add(news_id)
        await self.redis.set(self.KEY_PREFIX + news_id, "1", ex=self.ttl_seconds)
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/unit/news/test_dedupe.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
black shared/news/ tests/unit/news/ && ruff check --fix shared/news/ tests/unit/news/
git add shared/news/dedupe.py tests/unit/news/test_dedupe.py
git commit -m "feat(news): two-tier dedupe (LRU in-process + Redis SET with TTL)"
```

---

## Task 6: `shared/news/publisher.py` — stream XADD + CH batched writer

**Files:**
- Create: `shared/news/publisher.py`
- Test: `tests/unit/news/test_publisher.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/news/test_publisher.py`:

```python
import pytest
import fakeredis.aioredis
from unittest.mock import AsyncMock

from shared.news.base import NewsItem
from shared.news.publisher import NewsStreamPublisher, ClickHouseNewsWriter


def _item(news_id="x"):
    return NewsItem(
        news_id=news_id, source="yonhap",
        published_at_ms=1_000_000, received_at_ms=1_000_100,
        title="T", body="B", url="u",
        source_version="yonhap-v1", lang="ko", keywords=["kw1"],
    )


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis()


@pytest.mark.asyncio
async def test_publisher_xadd_produces_entry(redis):
    pub = NewsStreamPublisher(redis, stream="stream:news.raw", maxlen=100)
    await pub.publish(_item("a"))
    entries = await redis.xrange("stream:news.raw")
    assert len(entries) == 1
    msg_id, fields = entries[0]
    # Redis returns bytes by default
    assert fields[b"news_id"] == b"a"
    assert fields[b"source"] == b"yonhap"


@pytest.mark.asyncio
async def test_publisher_serializes_keywords_as_json(redis):
    pub = NewsStreamPublisher(redis, stream="stream:news.raw", maxlen=100)
    await pub.publish(_item("a"))
    entries = await redis.xrange("stream:news.raw")
    fields = entries[0][1]
    assert b"keywords_json" in fields
    assert fields[b"keywords_json"] == b'["kw1"]'


@pytest.mark.asyncio
async def test_publisher_respects_maxlen(redis):
    pub = NewsStreamPublisher(redis, stream="stream:news.raw", maxlen=2)
    for i in range(5):
        await pub.publish(_item(f"id_{i}"))
    entries = await redis.xrange("stream:news.raw")
    assert len(entries) <= 2


@pytest.mark.asyncio
async def test_ch_writer_batches_and_flushes_on_size():
    ch_client = AsyncMock()
    writer = ClickHouseNewsWriter(ch_client, batch_size=3, flush_interval_seconds=60)
    await writer.enqueue(_item("a"))
    await writer.enqueue(_item("b"))
    ch_client.execute.assert_not_awaited()
    await writer.enqueue(_item("c"))
    # 3 items triggered flush
    ch_client.execute.assert_awaited()


@pytest.mark.asyncio
async def test_ch_writer_flush_explicit():
    ch_client = AsyncMock()
    writer = ClickHouseNewsWriter(ch_client, batch_size=100, flush_interval_seconds=60)
    await writer.enqueue(_item("a"))
    await writer.flush()
    ch_client.execute.assert_awaited_once()
    call_sql = ch_client.execute.await_args.args[0]
    assert "INSERT INTO kospi.news_raw" in call_sql
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/unit/news/test_publisher.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement**

Create `shared/news/publisher.py`:

```python
"""News stream publisher (Redis XADD) + ClickHouse batched writer."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from shared.news.base import NewsItem

logger = logging.getLogger(__name__)


class NewsStreamPublisher:
    """Minimal publisher targeting stream:news.raw.

    Does NOT reuse shared.streaming.publisher.StreamPublisher because that
    one is sync and uses a global correlation-id tracer — not needed here.
    """

    def __init__(self, redis: Any, stream: str, maxlen: int):
        self.redis = redis
        self.stream = stream
        self.maxlen = maxlen

    async def publish(self, item: NewsItem, max_body_chars: int = 2000) -> str:
        payload = item.to_stream_dict(max_body_chars=max_body_chars)
        # Redis XADD requires scalar values; serialize lists as JSON
        fields: dict[str, str] = {}
        for k, v in payload.items():
            if isinstance(v, (list, dict)):
                fields[f"{k}_json"] = json.dumps(v, ensure_ascii=False)
            else:
                fields[k] = str(v) if v is not None else ""
        msg_id = await self.redis.xadd(
            self.stream, fields, maxlen=self.maxlen, approximate=True
        )
        return msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)


class ClickHouseNewsWriter:
    """Batches inserts into kospi.news_raw."""

    _INSERT_SQL = (
        "INSERT INTO kospi.news_raw "
        "(news_id, source, published_at, received_at, title, body, url, "
        "source_version, lang, keywords) VALUES"
    )

    def __init__(self, ch_client: Any, batch_size: int = 50, flush_interval_seconds: int = 10):
        self.ch = ch_client
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        self._buffer: list[tuple] = []
        self._lock = asyncio.Lock()

    async def enqueue(self, item: NewsItem) -> None:
        row = (
            item.news_id,
            item.source,
            datetime.fromtimestamp(item.published_at_ms / 1000, tz=timezone.utc),
            datetime.fromtimestamp(item.received_at_ms / 1000, tz=timezone.utc),
            item.title,
            item.body,
            item.url,
            item.source_version,
            item.lang,
            item.keywords,
        )
        async with self._lock:
            self._buffer.append(row)
            should_flush = len(self._buffer) >= self.batch_size
        if should_flush:
            await self.flush()

    async def flush(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            rows = self._buffer
            self._buffer = []
        try:
            await self.ch.execute(self._INSERT_SQL, rows)
        except Exception:
            logger.exception("CH flush failed; dropping %d rows", len(rows))

    async def run_periodic_flush(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.flush_interval)
            except asyncio.TimeoutError:
                await self.flush()
        await self.flush()
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/unit/news/test_publisher.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
black shared/news/publisher.py tests/unit/news/test_publisher.py
ruff check --fix shared/news/publisher.py tests/unit/news/test_publisher.py
git add shared/news/publisher.py tests/unit/news/test_publisher.py
git commit -m "feat(news): async Redis publisher + batched ClickHouse writer"
```

---

## Task 7: Yonhap RSS source

**Files:**
- Create: `shared/news/sources/__init__.py` (empty)
- Create: `shared/news/sources/yonhap.py`
- Test: `tests/unit/news/sources/__init__.py` (empty), `tests/unit/news/sources/test_yonhap.py`

- [ ] **Step 1: Fixture RSS sample**

Create `tests/fixtures/yonhap_sample.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>연합뉴스 경제</title>
  <item>
    <title>FOMC 기준금리 25bp 인하</title>
    <link>https://www.yna.co.kr/view/AKR20260420000001</link>
    <description>연방준비제도는 ...</description>
    <pubDate>Mon, 20 Apr 2026 12:00:00 +0900</pubDate>
  </item>
  <item>
    <title>코스피 2% 상승</title>
    <link>https://www.yna.co.kr/view/AKR20260420000002</link>
    <description>코스피 지수가 2% 상승 ...</description>
    <pubDate>Mon, 20 Apr 2026 13:30:00 +0900</pubDate>
  </item>
</channel>
</rss>
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/news/sources/test_yonhap.py`:

```python
import pytest
from aioresponses import aioresponses
import aiohttp

from shared.news.sources.yonhap import YonhapRSSSource


SAMPLE_XML_PATH = "tests/fixtures/yonhap_sample.xml"


@pytest.mark.asyncio
async def test_yonhap_parses_rss():
    with open(SAMPLE_XML_PATH, "rb") as f:
        body = f.read()

    with aioresponses() as m:
        m.get("https://www.yna.co.kr/rss/economy.xml", body=body)
        async with aiohttp.ClientSession() as session:
            src = YonhapRSSSource(
                session=session,
                rss_url="https://www.yna.co.kr/rss/economy.xml",
            )
            items = [it async for it in src.fetch()]

    assert len(items) == 2
    assert items[0].source == "yonhap"
    assert items[0].title.startswith("FOMC")
    # news_id is deterministic sha256[:16]
    assert items[0].news_id.startswith("yonhap_")
    assert items[0].lang == "ko"


@pytest.mark.asyncio
async def test_yonhap_swallows_http_errors():
    with aioresponses() as m:
        m.get("https://www.yna.co.kr/rss/economy.xml", status=500)
        async with aiohttp.ClientSession() as session:
            src = YonhapRSSSource(
                session=session,
                rss_url="https://www.yna.co.kr/rss/economy.xml",
            )
            items = [it async for it in src.fetch()]
    assert items == []


@pytest.mark.asyncio
async def test_yonhap_deterministic_news_id():
    with open(SAMPLE_XML_PATH, "rb") as f:
        body = f.read()

    with aioresponses() as m:
        m.get("https://www.yna.co.kr/rss/economy.xml", body=body, repeat=True)
        async with aiohttp.ClientSession() as session:
            src = YonhapRSSSource(
                session=session,
                rss_url="https://www.yna.co.kr/rss/economy.xml",
            )
            first = [it async for it in src.fetch()]
            second = [it async for it in src.fetch()]

    assert first[0].news_id == second[0].news_id
```

- [ ] **Step 3: Run — expect FAIL**

```bash
pytest tests/unit/news/sources/test_yonhap.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement**

Create `shared/news/sources/__init__.py` (empty). Create `shared/news/sources/yonhap.py`:

```python
"""Yonhap (연합뉴스) RSS source."""
from __future__ import annotations

import hashlib
import logging
import time
from email.utils import parsedate_to_datetime
from typing import AsyncIterator

import aiohttp
import feedparser

from shared.news.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)


class YonhapRSSSource(NewsSource):
    name = "yonhap"
    version = "yonhap-v1"
    poll_interval_seconds = 60

    def __init__(self, session: aiohttp.ClientSession, rss_url: str, timeout: float = 10.0):
        self._session = session
        self._rss_url = rss_url
        self._timeout = timeout

    async def fetch(self) -> AsyncIterator[NewsItem]:
        try:
            async with self._session.get(
                self._rss_url,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status != 200:
                    logger.warning("yonhap http %s", resp.status)
                    return
                body = await resp.read()
        except Exception:
            logger.exception("yonhap fetch failed")
            return

        parsed = feedparser.parse(body)
        for entry in parsed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            digest = hashlib.sha256(url.encode()).hexdigest()[:16]
            published_ts_s = _parse_rss_date(entry.get("published", ""))
            received_ts_ms = int(time.time() * 1000)
            yield NewsItem(
                news_id=f"yonhap_{digest}",
                source=self.name,
                published_at_ms=int(published_ts_s * 1000) if published_ts_s else received_ts_ms,
                received_at_ms=received_ts_ms,
                title=entry.get("title", ""),
                body=entry.get("description", ""),
                url=url,
                source_version=self.version,
                lang="ko",
                keywords=[],
            )


def _parse_rss_date(raw: str) -> float:
    if not raw:
        return 0.0
    try:
        return parsedate_to_datetime(raw).timestamp()
    except (TypeError, ValueError):
        return 0.0
```

- [ ] **Step 5: Run — expect PASS**

```bash
pytest tests/unit/news/sources/test_yonhap.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
black shared/news/sources/yonhap.py tests/unit/news/sources/
ruff check --fix shared/news/sources/yonhap.py tests/unit/news/sources/
git add shared/news/sources/ tests/unit/news/sources/ tests/fixtures/yonhap_sample.xml
git commit -m "feat(news): Yonhap RSS source with deterministic URL-hash news_id"
```

---

## Task 8: Reuters RSS source

**Files:**
- Create: `shared/news/sources/reuters.py`
- Create: `tests/fixtures/reuters_sample.xml`
- Test: `tests/unit/news/sources/test_reuters.py`

- [ ] **Step 1: Fixture**

Create `tests/fixtures/reuters_sample.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Reuters Korea Business</title>
  <item>
    <title>Samsung Q1 operating profit rises 30%</title>
    <link>https://kr.reuters.com/article/samsung-q1-20260420</link>
    <description>Samsung Electronics reported a 30% jump...</description>
    <pubDate>Mon, 20 Apr 2026 08:00:00 GMT</pubDate>
  </item>
</channel>
</rss>
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/news/sources/test_reuters.py`:

```python
import pytest
from aioresponses import aioresponses
import aiohttp

from shared.news.sources.reuters import ReutersRSSSource


@pytest.mark.asyncio
async def test_reuters_parses_rss_and_tags_lang_en():
    with open("tests/fixtures/reuters_sample.xml", "rb") as f:
        body = f.read()
    with aioresponses() as m:
        m.get("https://kr.reuters.com/rss/businessNews", body=body)
        async with aiohttp.ClientSession() as session:
            src = ReutersRSSSource(session=session, rss_url="https://kr.reuters.com/rss/businessNews")
            items = [it async for it in src.fetch()]
    assert len(items) == 1
    assert items[0].source == "reuters"
    assert items[0].lang == "en"
    assert items[0].news_id.startswith("reuters_")
```

- [ ] **Step 3: Run — expect FAIL**

```bash
pytest tests/unit/news/sources/test_reuters.py -v
```

- [ ] **Step 4: Implement**

Create `shared/news/sources/reuters.py`:

```python
"""Reuters Korea business RSS source (English content)."""
from __future__ import annotations

import hashlib
import logging
import time
from email.utils import parsedate_to_datetime
from typing import AsyncIterator

import aiohttp
import feedparser

from shared.news.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)


class ReutersRSSSource(NewsSource):
    name = "reuters"
    version = "reuters-v1"
    poll_interval_seconds = 120

    def __init__(self, session: aiohttp.ClientSession, rss_url: str, timeout: float = 10.0):
        self._session = session
        self._rss_url = rss_url
        self._timeout = timeout

    async def fetch(self) -> AsyncIterator[NewsItem]:
        try:
            async with self._session.get(
                self._rss_url,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status != 200:
                    logger.warning("reuters http %s", resp.status)
                    return
                body = await resp.read()
        except Exception:
            logger.exception("reuters fetch failed")
            return

        parsed = feedparser.parse(body)
        for entry in parsed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            digest = hashlib.sha256(url.encode()).hexdigest()[:16]
            published_ts_s = _parse_rss_date(entry.get("published", ""))
            received_ts_ms = int(time.time() * 1000)
            yield NewsItem(
                news_id=f"reuters_{digest}",
                source=self.name,
                published_at_ms=int(published_ts_s * 1000) if published_ts_s else received_ts_ms,
                received_at_ms=received_ts_ms,
                title=entry.get("title", ""),
                body=entry.get("description", ""),
                url=url,
                source_version=self.version,
                lang="en",
                keywords=[],
            )


def _parse_rss_date(raw: str) -> float:
    if not raw:
        return 0.0
    try:
        return parsedate_to_datetime(raw).timestamp()
    except (TypeError, ValueError):
        return 0.0
```

- [ ] **Step 5: Run — expect PASS & Commit**

```bash
pytest tests/unit/news/sources/test_reuters.py -v
black shared/news/sources/reuters.py tests/unit/news/sources/test_reuters.py
ruff check --fix shared/news/sources/reuters.py tests/unit/news/sources/test_reuters.py
git add shared/news/sources/reuters.py tests/unit/news/sources/test_reuters.py tests/fixtures/reuters_sample.xml
git commit -m "feat(news): Reuters Korea RSS source (English, lang=en tag)"
```

---

## Task 9: DART adapter (wraps existing DARTDataCollector)

**Files:**
- Create: `shared/news/sources/dart.py`
- Test: `tests/unit/news/sources/test_dart.py`

**Prerequisite reading:** `shared/llm/collectors.py` lines around 585 (`DARTDataCollector`). Understand its `fetch_recent_filings()` return shape. This task wraps that class in the `NewsSource` interface — DOES NOT reimplement DART polling.

- [ ] **Step 1: Write failing test**

Create `tests/unit/news/sources/test_dart.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.news.sources.dart import DARTNewsSource


@pytest.mark.asyncio
async def test_dart_adapter_converts_filings_to_news_items():
    collector = MagicMock()
    collector.fetch_recent_filings = AsyncMock(
        return_value=[
            {
                "rcept_no": "20260420000001",
                "corp_name": "삼성전자",
                "report_nm": "주요사항보고서(합병)",
                "rcept_dt": "20260420",
                "url": "https://dart.fss.or.kr/...",
            },
        ]
    )
    src = DARTNewsSource(collector=collector)
    items = [it async for it in src.fetch()]
    assert len(items) == 1
    item = items[0]
    assert item.source == "dart"
    assert item.news_id == "dart_20260420000001"
    assert item.lang == "ko"
    assert "삼성전자" in item.title


@pytest.mark.asyncio
async def test_dart_adapter_skips_filings_without_rcept_no():
    collector = MagicMock()
    collector.fetch_recent_filings = AsyncMock(return_value=[{"corp_name": "x"}])
    src = DARTNewsSource(collector=collector)
    items = [it async for it in src.fetch()]
    assert items == []
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/unit/news/sources/test_dart.py -v
```

- [ ] **Step 3: Implement**

Create `shared/news/sources/dart.py`:

```python
"""DART 공시 source — adapts existing DARTDataCollector."""
from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator

from shared.news.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)


class DARTNewsSource(NewsSource):
    """Wraps shared.llm.collectors.DARTDataCollector for the streaming pipeline."""

    name = "dart"
    version = "dart-v1"
    poll_interval_seconds = 30

    def __init__(self, collector: Any):
        # `collector` exposes an async fetch_recent_filings() -> list[dict]
        self._collector = collector

    async def fetch(self) -> AsyncIterator[NewsItem]:
        try:
            filings = await self._collector.fetch_recent_filings()
        except Exception:
            logger.exception("DART fetch failed")
            return

        now_ms = int(time.time() * 1000)
        for f in filings:
            rcept_no = f.get("rcept_no")
            if not rcept_no:
                continue
            corp = f.get("corp_name", "")
            report = f.get("report_nm", "")
            published_ms = _parse_rcept_dt(f.get("rcept_dt"), fallback_ms=now_ms)
            yield NewsItem(
                news_id=f"dart_{rcept_no}",
                source=self.name,
                published_at_ms=published_ms,
                received_at_ms=now_ms,
                title=f"[DART] {corp} — {report}".strip(),
                body=f.get("report_nm", ""),
                url=f.get("url", ""),
                source_version=self.version,
                lang="ko",
                keywords=[corp] if corp else [],
            )


def _parse_rcept_dt(raw: Any, fallback_ms: int) -> int:
    if not raw or not isinstance(raw, str) or len(raw) < 8:
        return fallback_ms
    # YYYYMMDD — use 00:00 UTC of that day
    try:
        from datetime import datetime, timezone
        dt = datetime.strptime(raw[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return fallback_ms
```

- [ ] **Step 4: Run — expect PASS & Commit**

```bash
pytest tests/unit/news/sources/test_dart.py -v
black shared/news/sources/dart.py tests/unit/news/sources/test_dart.py
ruff check --fix shared/news/sources/dart.py tests/unit/news/sources/test_dart.py
git add shared/news/sources/dart.py tests/unit/news/sources/test_dart.py
git commit -m "feat(news): DART adapter wrapping existing DARTDataCollector"
```

---

## Task 10: MK adapter (wraps existing MKStockNewsCollector)

**Files:**
- Create: `shared/news/sources/mk_adapter.py`
- Test: `tests/unit/news/sources/test_mk_adapter.py`

**Prerequisite reading:** `shared/llm/collectors.py` line 798 onwards (`MKStockNewsCollector`). Adapter strips the existing keyword-sentiment (we want raw only; scoring happens in Phase 2).

- [ ] **Step 1: Write failing test**

Create `tests/unit/news/sources/test_mk_adapter.py`:

```python
from unittest.mock import MagicMock, AsyncMock

import pytest

from shared.news.sources.mk_adapter import MKNewsSourceAdapter


@pytest.mark.asyncio
async def test_mk_adapter_yields_raw_items_without_sentiment():
    underlying = MagicMock()
    underlying.fetch_market_news = AsyncMock(
        return_value=[
            {
                "id": "mk_001",
                "title": "코스피 2% 상승",
                "content": "장중 2% 상승...",
                "url": "https://mk.co.kr/...1",
                "published_at_ms": 1_700_000_000_000,
                # should ignore these:
                "sentiment": "긍정",
                "sentiment_score": 0.7,
            },
            {
                "title": "no-id filtered",
                "content": "x",
                "url": "https://mk.co.kr/...2",
                "published_at_ms": 1_700_000_001_000,
            },
        ]
    )
    src = MKNewsSourceAdapter(underlying=underlying)
    items = [it async for it in src.fetch()]
    assert len(items) == 2
    assert items[0].source == "mk"
    assert items[0].news_id == "mk_mk_001"
    # URL-hashed fallback for no-id entry
    assert items[1].news_id.startswith("mk_")
    assert all("sentiment" not in i.keywords for i in items)
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/unit/news/sources/test_mk_adapter.py -v
```

- [ ] **Step 3: Implement**

Create `shared/news/sources/mk_adapter.py`:

```python
"""Adapter over existing MKStockNewsCollector.

Strips keyword-sentiment outputs — Phase 2 LLM scorer replaces them.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, AsyncIterator

from shared.news.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)


class MKNewsSourceAdapter(NewsSource):
    name = "mk"
    version = "mk-v1"
    poll_interval_seconds = 180

    def __init__(self, underlying: Any):
        self._underlying = underlying

    async def fetch(self) -> AsyncIterator[NewsItem]:
        try:
            raw_items = await self._underlying.fetch_market_news()
        except Exception:
            logger.exception("MK underlying failed")
            return

        now_ms = int(time.time() * 1000)
        for raw in raw_items:
            mk_id = raw.get("id")
            url = raw.get("url", "")
            if not mk_id and not url:
                continue
            news_id = (
                f"mk_{mk_id}" if mk_id else f"mk_{hashlib.sha256(url.encode()).hexdigest()[:16]}"
            )
            yield NewsItem(
                news_id=news_id,
                source=self.name,
                published_at_ms=raw.get("published_at_ms", now_ms),
                received_at_ms=now_ms,
                title=raw.get("title", ""),
                body=raw.get("content", ""),
                url=url,
                source_version=self.version,
                lang="ko",
                keywords=[],
            )
```

- [ ] **Step 4: Run — expect PASS & Commit**

```bash
pytest tests/unit/news/sources/test_mk_adapter.py -v
black shared/news/sources/mk_adapter.py tests/unit/news/sources/test_mk_adapter.py
ruff check --fix shared/news/sources/mk_adapter.py tests/unit/news/sources/test_mk_adapter.py
git add shared/news/sources/mk_adapter.py tests/unit/news/sources/test_mk_adapter.py
git commit -m "feat(news): MK adapter — raw only, strip legacy keyword sentiment"
```

---

## Task 11: News collector config (Pydantic / ServiceConfigBase)

**Files:**
- Create: `config/news_sources.yaml`
- Create: `shared/news/config.py`
- Test: `tests/unit/news/test_config.py`

- [ ] **Step 1: Write YAML**

Create `config/news_sources.yaml`:

```yaml
news_collector:
  redis_stream: "stream:news.raw"
  redis_maxlen: 100000
  clickhouse_batch_size: 50
  clickhouse_flush_interval_seconds: 10
  body_truncate_chars: 2000
  dedupe:
    memory_size: 20000
    redis_ttl_days: 7
  sources:
    dart:
      enabled: true
      poll_interval_seconds: 30
    yonhap:
      enabled: true
      poll_interval_seconds: 60
      rss_url: "https://www.yna.co.kr/rss/economy.xml"
    reuters:
      enabled: true
      poll_interval_seconds: 120
      rss_url: "https://kr.reuters.com/rss/businessNews"
    mk:
      enabled: true
      poll_interval_seconds: 180
      mode: "adapter"
```

- [ ] **Step 2: Write failing test**

Create `tests/unit/news/test_config.py`:

```python
import pytest

from shared.news.config import NewsCollectorConfig


def test_loads_from_yaml(tmp_path):
    yaml = tmp_path / "news_sources.yaml"
    yaml.write_text(
        """
news_collector:
  redis_stream: "stream:news.raw"
  redis_maxlen: 1000
  clickhouse_batch_size: 5
  clickhouse_flush_interval_seconds: 2
  body_truncate_chars: 100
  dedupe:
    memory_size: 10
    redis_ttl_days: 1
  sources:
    yonhap:
      enabled: true
      poll_interval_seconds: 60
      rss_url: "https://example.com/rss"
    reuters:
      enabled: false
      poll_interval_seconds: 120
      rss_url: "https://example.com/en"
    dart:
      enabled: false
      poll_interval_seconds: 30
    mk:
      enabled: false
      poll_interval_seconds: 180
      mode: "adapter"
        """.strip()
    )
    cfg = NewsCollectorConfig.from_yaml_path(str(yaml))
    assert cfg.redis_stream == "stream:news.raw"
    assert cfg.sources.yonhap.enabled is True
    assert cfg.sources.reuters.enabled is False
    assert cfg.dedupe.memory_size == 10


def test_missing_required_key_raises(tmp_path):
    yaml = tmp_path / "bad.yaml"
    yaml.write_text("news_collector:\n  redis_stream: x\n")
    with pytest.raises(Exception):
        NewsCollectorConfig.from_yaml_path(str(yaml))
```

- [ ] **Step 3: Run — expect FAIL**

```bash
pytest tests/unit/news/test_config.py -v
```

- [ ] **Step 4: Implement**

Create `shared/news/config.py`:

```python
"""Pydantic config models for news collector."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DedupeConfig(BaseModel):
    memory_size: int = Field(default=20000, gt=0)
    redis_ttl_days: int = Field(default=7, gt=0)


class SourceCommon(BaseModel):
    enabled: bool = True
    poll_interval_seconds: int = Field(default=60, gt=0)


class DartSourceConfig(SourceCommon):
    pass


class YonhapSourceConfig(SourceCommon):
    rss_url: str


class ReutersSourceConfig(SourceCommon):
    rss_url: str


class MKSourceConfig(SourceCommon):
    mode: str = "adapter"


class SourcesConfig(BaseModel):
    dart: DartSourceConfig
    yonhap: YonhapSourceConfig
    reuters: ReutersSourceConfig
    mk: MKSourceConfig


class NewsCollectorConfig(BaseModel):
    redis_stream: str
    redis_maxlen: int = Field(default=100000, gt=0)
    clickhouse_batch_size: int = Field(default=50, gt=0)
    clickhouse_flush_interval_seconds: int = Field(default=10, gt=0)
    body_truncate_chars: int = Field(default=2000, gt=0)
    dedupe: DedupeConfig
    sources: SourcesConfig

    @classmethod
    def from_yaml_path(cls, path: str) -> "NewsCollectorConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data["news_collector"])
```

- [ ] **Step 5: Run — expect PASS & Commit**

```bash
pytest tests/unit/news/test_config.py -v
black shared/news/config.py tests/unit/news/test_config.py
ruff check --fix shared/news/config.py tests/unit/news/test_config.py
git add shared/news/config.py tests/unit/news/test_config.py config/news_sources.yaml
git commit -m "feat(news): Pydantic config model + config/news_sources.yaml"
```

---

## Task 12: News collector daemon

**Files:**
- Create: `services/news_collector/__init__.py` (empty)
- Create: `services/news_collector/main.py`
- Test: `tests/integration/test_news_collector_e2e.py`

- [ ] **Step 1: Write failing integration test**

Create `tests/integration/test_news_collector_e2e.py`:

```python
"""End-to-end: inject a fake source → daemon publishes to Redis + CH."""
import asyncio
from unittest.mock import AsyncMock
from typing import AsyncIterator

import pytest
import fakeredis.aioredis

from shared.news.base import NewsItem, NewsSource
from services.news_collector.main import NewsCollectorDaemon


class _FakeSource(NewsSource):
    name = "fake"
    version = "fake-v1"
    poll_interval_seconds = 1

    def __init__(self, items: list[NewsItem]):
        self._items = items
        self._served = False

    async def fetch(self) -> AsyncIterator[NewsItem]:
        # serve once, then nothing (simulate empty poll cycles)
        if self._served:
            return
        self._served = True
        for it in self._items:
            yield it


def _item(news_id: str) -> NewsItem:
    return NewsItem(
        news_id=news_id, source="fake",
        published_at_ms=1_000_000, received_at_ms=1_000_100,
        title="t", body="b", url="u",
        source_version="fake-v1", lang="ko", keywords=[],
    )


@pytest.mark.asyncio
async def test_daemon_publishes_and_writes(tmp_path):
    redis = fakeredis.aioredis.FakeRedis()
    ch = AsyncMock()
    source = _FakeSource(items=[_item("a"), _item("b"), _item("a")])   # dup "a"

    daemon = NewsCollectorDaemon(
        redis=redis, ch_client=ch,
        sources=[source],
        stream="stream:news.raw",
        stream_maxlen=100,
        dedupe_memory=100, dedupe_ttl_days=1,
        ch_batch_size=2, ch_flush_interval=60,
        body_truncate_chars=1000,
    )

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.5)   # let one cycle run
    await daemon.stop()
    await task

    entries = await redis.xrange("stream:news.raw")
    ids_in_stream = [e[1][b"news_id"] for e in entries]
    assert b"a" in ids_in_stream
    assert b"b" in ids_in_stream
    # duplicate "a" should not appear twice
    assert ids_in_stream.count(b"a") == 1

    # CH batch flush triggered (2 rows = batch_size=2)
    assert ch.execute.await_count >= 1
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/integration/test_news_collector_e2e.py -v
```

- [ ] **Step 3: Implement daemon**

Create `services/news_collector/__init__.py` (empty). Create `services/news_collector/main.py`:

```python
"""News collector daemon — polls sources, dedups, publishes to Redis + CH."""
from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

from shared.news.base import NewsSource
from shared.news.dedupe import NewsDedupe
from shared.news.publisher import ClickHouseNewsWriter, NewsStreamPublisher

logger = logging.getLogger(__name__)


class NewsCollectorDaemon:
    """Orchestrates N sources. Each source runs in its own isolated loop."""

    def __init__(
        self,
        *,
        redis: Any,
        ch_client: Any,
        sources: list[NewsSource],
        stream: str,
        stream_maxlen: int,
        dedupe_memory: int,
        dedupe_ttl_days: int,
        ch_batch_size: int,
        ch_flush_interval: int,
        body_truncate_chars: int,
    ):
        self.redis = redis
        self.sources = sources
        self.publisher = NewsStreamPublisher(redis, stream=stream, maxlen=stream_maxlen)
        self.dedupe = NewsDedupe(redis, memory_size=dedupe_memory, ttl_days=dedupe_ttl_days)
        self.ch_writer = ClickHouseNewsWriter(
            ch_client, batch_size=ch_batch_size, flush_interval_seconds=ch_flush_interval
        )
        self.body_truncate_chars = body_truncate_chars
        self._stop = asyncio.Event()

    async def run(self) -> None:
        flush_task = asyncio.create_task(self.ch_writer.run_periodic_flush(self._stop))
        source_tasks = [asyncio.create_task(self._loop(s)) for s in self.sources]
        try:
            await self._stop.wait()
        finally:
            for t in source_tasks:
                t.cancel()
            await asyncio.gather(*source_tasks, return_exceptions=True)
            await flush_task   # triggers final flush

    async def stop(self) -> None:
        self._stop.set()

    async def _loop(self, source: NewsSource) -> None:
        while not self._stop.is_set():
            try:
                async for item in source.fetch():
                    if await self.dedupe.is_duplicate(item.news_id):
                        continue
                    await self.dedupe.mark_seen(item.news_id)
                    await self.publisher.publish(item, max_body_chars=self.body_truncate_chars)
                    await self.ch_writer.enqueue(item)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("source=%s fetch cycle failed", source.name)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=source.poll_interval_seconds)
            except asyncio.TimeoutError:
                pass


async def _build_and_run_from_config() -> int:
    """Production entry point. Resolves sources from YAML config."""
    import aiohttp
    import redis.asyncio as aioredis

    from shared.db.client import ClickHouseClient
    from shared.news.config import NewsCollectorConfig
    from shared.news.sources.dart import DARTNewsSource
    from shared.news.sources.mk_adapter import MKNewsSourceAdapter
    from shared.news.sources.reuters import ReutersRSSSource
    from shared.news.sources.yonhap import YonhapRSSSource
    import os

    cfg = NewsCollectorConfig.from_yaml_path("config/news_sources.yaml")
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis = aioredis.from_url(redis_url)
    ch = ClickHouseClient.get_instance().async_client

    session = aiohttp.ClientSession()
    sources: list[NewsSource] = []
    if cfg.sources.yonhap.enabled:
        sources.append(YonhapRSSSource(session=session, rss_url=cfg.sources.yonhap.rss_url))
    if cfg.sources.reuters.enabled:
        sources.append(ReutersRSSSource(session=session, rss_url=cfg.sources.reuters.rss_url))
    if cfg.sources.dart.enabled:
        from shared.llm.collectors import DARTDataCollector   # reuse existing
        sources.append(DARTNewsSource(collector=DARTDataCollector()))
    if cfg.sources.mk.enabled:
        from shared.llm.collectors import MKStockNewsCollector
        sources.append(MKNewsSourceAdapter(underlying=MKStockNewsCollector()))

    daemon = NewsCollectorDaemon(
        redis=redis, ch_client=ch,
        sources=sources,
        stream=cfg.redis_stream,
        stream_maxlen=cfg.redis_maxlen,
        dedupe_memory=cfg.dedupe.memory_size,
        dedupe_ttl_days=cfg.dedupe.redis_ttl_days,
        ch_batch_size=cfg.clickhouse_batch_size,
        ch_flush_interval=cfg.clickhouse_flush_interval_seconds,
        body_truncate_chars=cfg.body_truncate_chars,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await session.close()
        await redis.aclose()
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return asyncio.run(_build_and_run_from_config())


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/integration/test_news_collector_e2e.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
black services/news_collector/ tests/integration/
ruff check --fix services/news_collector/ tests/integration/
git add services/news_collector/ tests/integration/test_news_collector_e2e.py
git commit -m "feat(news): NewsCollectorDaemon with per-source isolation + graceful shutdown"
```

---

## Task 13: Macro Yahoo + ECOS sources

**Files:**
- Create: `shared/macro/__init__.py`, `shared/macro/base.py`, `shared/macro/sources/__init__.py`, `shared/macro/sources/yahoo.py`, `shared/macro/sources/ecos.py`
- Test: `tests/unit/macro/__init__.py`, `tests/unit/macro/test_yahoo.py`, `tests/unit/macro/test_ecos.py`

- [ ] **Step 1: Write base + tests**

Create `shared/macro/__init__.py` (empty). Create `shared/macro/base.py`:

```python
"""Macro snapshot dataclass used across sources."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MacroSnapshot:
    ts_ms: int
    session: str                    # "overnight_us_close" | "overnight_fx"
    sp500_close: float | None = None
    sp500_change_pct: float | None = None
    nasdaq_close: float | None = None
    nasdaq_change_pct: float | None = None
    eurex_kospi_close: float | None = None
    eurex_kospi_change_pct: float | None = None
    usdkrw: float | None = None
    usdkrw_change_pct: float | None = None
    dxy: float | None = None
    us10y_yield: float | None = None
    vix: float | None = None
    collected_from: list[str] = field(default_factory=list)
```

Create `tests/unit/macro/__init__.py` (empty). Create `tests/unit/macro/test_yahoo.py`:

```python
from unittest.mock import MagicMock, patch
import pytest

from shared.macro.sources.yahoo import YahooMacroSource


@patch("shared.macro.sources.yahoo.yf")
def test_yahoo_fetches_us_close_snapshot(mock_yf):
    # Mock yfinance Ticker().history() return: a tiny DataFrame-like
    mock_hist = MagicMock()
    # Act like a 2-row DataFrame: iloc[-1] and iloc[-2]
    mock_hist.empty = False
    mock_hist.__len__.return_value = 2
    mock_hist.iloc.__getitem__.side_effect = lambda idx: {
        -1: {"Close": 5100.0},
        -2: {"Close": 5050.0},
    }[idx]
    mock_yf.Ticker.return_value.history.return_value = mock_hist

    src = YahooMacroSource()
    snap = pytest.run(src.fetch_us_close_snapshot()) if False else None   # see below

    # Call synchronously since YahooMacroSource wraps sync yfinance
    import asyncio
    snap = asyncio.run(src.fetch_us_close_snapshot())
    assert snap.session == "overnight_us_close"
    assert snap.sp500_close == 5100.0
    assert abs(snap.sp500_change_pct - (5100 - 5050) / 5050 * 100) < 1e-6
    assert "yahoo" in snap.collected_from


@patch("shared.macro.sources.yahoo.yf")
def test_yahoo_returns_none_fields_on_empty_history(mock_yf):
    mock_hist = MagicMock()
    mock_hist.empty = True
    mock_yf.Ticker.return_value.history.return_value = mock_hist

    import asyncio
    src = YahooMacroSource()
    snap = asyncio.run(src.fetch_us_close_snapshot())
    assert snap.sp500_close is None
    assert snap.nasdaq_close is None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/unit/macro/test_yahoo.py -v
```

- [ ] **Step 3: Implement Yahoo**

Create `shared/macro/sources/__init__.py` (empty). Create `shared/macro/sources/yahoo.py`:

```python
"""Yahoo Finance macro source via yfinance."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import yfinance as yf  # noqa: F401 — re-exported for tests to monkey-patch

from shared.macro.base import MacroSnapshot

logger = logging.getLogger(__name__)


_TICKER_MAP = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "vix": "^VIX",
    "dxy": "DX-Y.NYB",
    "us10y": "^TNX",
}


def _fetch_close_and_change(ticker_symbol: str) -> tuple[float | None, float | None]:
    """Sync helper, run in a thread."""
    try:
        t = yf.Ticker(ticker_symbol)
        hist = t.history(period="5d")
        if getattr(hist, "empty", True) or len(hist) < 2:
            return None, None
        last = float(hist.iloc[-1]["Close"])
        prev = float(hist.iloc[-2]["Close"])
        if prev == 0:
            return last, None
        return last, (last - prev) / prev * 100.0
    except Exception:
        logger.exception("yfinance fetch failed ticker=%s", ticker_symbol)
        return None, None


class YahooMacroSource:
    async def fetch_us_close_snapshot(self) -> MacroSnapshot:
        # Fetch in thread pool (yfinance is sync)
        loop = asyncio.get_running_loop()
        async def _t(sym: str):
            return await loop.run_in_executor(None, _fetch_close_and_change, sym)

        sp500, sp500_pct = await _t(_TICKER_MAP["sp500"])
        nasdaq, nasdaq_pct = await _t(_TICKER_MAP["nasdaq"])
        vix, _ = await _t(_TICKER_MAP["vix"])
        dxy, _ = await _t(_TICKER_MAP["dxy"])
        us10y, _ = await _t(_TICKER_MAP["us10y"])

        return MacroSnapshot(
            ts_ms=int(time.time() * 1000),
            session="overnight_us_close",
            sp500_close=sp500, sp500_change_pct=sp500_pct,
            nasdaq_close=nasdaq, nasdaq_change_pct=nasdaq_pct,
            vix=vix, dxy=dxy, us10y_yield=us10y,
            collected_from=["yahoo"],
        )
```

- [ ] **Step 4: ECOS source**

Create `tests/unit/macro/test_ecos.py`:

```python
import pytest
from aioresponses import aioresponses
import aiohttp

from shared.macro.sources.ecos import ECOSSource


@pytest.mark.asyncio
async def test_ecos_parses_usdkrw():
    # Minimal ECOS response shape — real API is verbose; we only need row with DATA_VALUE
    payload = {
        "StatisticSearch": {
            "row": [
                {"TIME": "20260419", "DATA_VALUE": "1350.20"},
                {"TIME": "20260420", "DATA_VALUE": "1355.80"},
            ]
        }
    }
    with aioresponses() as m:
        m.get(
            url="https://ecos.bok.or.kr/api/StatisticSearch/TEST_KEY/json/kr/1/2/731Y001/D/20260418/20260420/0000001",
            payload=payload,
        )
        async with aiohttp.ClientSession() as session:
            src = ECOSSource(api_key="TEST_KEY", session=session)
            snap = await src.fetch_fx_snapshot()
    assert snap.session == "overnight_fx"
    assert snap.usdkrw == 1355.80
    assert abs(snap.usdkrw_change_pct - (1355.80 - 1350.20) / 1350.20 * 100) < 1e-6
    assert "ecos" in snap.collected_from
```

- [ ] **Step 5: Run — expect FAIL**

```bash
pytest tests/unit/macro/test_ecos.py -v
```

- [ ] **Step 6: Implement ECOS**

Create `shared/macro/sources/ecos.py`:

```python
"""한국은행 ECOS API — USD/KRW snapshot."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import aiohttp

from shared.macro.base import MacroSnapshot

logger = logging.getLogger(__name__)

# 731Y001 = 원/달러 환율, period D(daily)
_ECOS_URL = (
    "https://ecos.bok.or.kr/api/StatisticSearch/"
    "{api_key}/json/kr/1/2/731Y001/D/{start}/{end}/0000001"
)


class ECOSSource:
    def __init__(self, api_key: str, session: aiohttp.ClientSession, timeout: float = 10.0):
        self._api_key = api_key
        self._session = session
        self._timeout = timeout

    async def fetch_fx_snapshot(self) -> MacroSnapshot:
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=3)).strftime("%Y%m%d")
        end = now.strftime("%Y%m%d")
        url = _ECOS_URL.format(api_key=self._api_key, start=start, end=end)

        last = None
        prev = None
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=self._timeout)
            ) as resp:
                if resp.status != 200:
                    logger.warning("ecos http %s", resp.status)
                    return _empty_fx()
                data = await resp.json()
            rows = data.get("StatisticSearch", {}).get("row", [])
            if len(rows) >= 2:
                last = float(rows[-1]["DATA_VALUE"])
                prev = float(rows[-2]["DATA_VALUE"])
            elif len(rows) == 1:
                last = float(rows[-1]["DATA_VALUE"])
        except Exception:
            logger.exception("ecos fetch failed")
            return _empty_fx()

        pct = None
        if last is not None and prev not in (None, 0):
            pct = (last - prev) / prev * 100.0

        return MacroSnapshot(
            ts_ms=int(time.time() * 1000),
            session="overnight_fx",
            usdkrw=last, usdkrw_change_pct=pct,
            collected_from=["ecos"],
        )


def _empty_fx() -> MacroSnapshot:
    return MacroSnapshot(
        ts_ms=int(time.time() * 1000),
        session="overnight_fx",
        collected_from=["ecos"],
    )
```

- [ ] **Step 7: Run both tests — expect PASS**

```bash
pytest tests/unit/macro/ -v
```

- [ ] **Step 8: Commit**

```bash
black shared/macro/ tests/unit/macro/
ruff check --fix shared/macro/ tests/unit/macro/
git add shared/macro/ tests/unit/macro/
git commit -m "feat(macro): MacroSnapshot + Yahoo (SP500/Nasdaq/VIX/DXY/US10Y) + ECOS (USDKRW) sources"
```

---

## Task 14: Macro overnight batch entry point + cron

**Files:**
- Create: `services/macro_overnight_collector/__init__.py` (empty)
- Create: `services/macro_overnight_collector/main.py`
- Create: `scripts/cron/macro_overnight.sh`
- Test: `tests/integration/test_macro_overnight_e2e.py`

- [ ] **Step 1: Write integration test**

Create `tests/integration/test_macro_overnight_e2e.py`:

```python
from unittest.mock import AsyncMock, MagicMock
import asyncio

import pytest
import fakeredis.aioredis

from shared.macro.base import MacroSnapshot
from services.macro_overnight_collector.main import (
    collect_us_session,
    collect_fx_session,
)


@pytest.mark.asyncio
async def test_collect_us_session_publishes_and_writes():
    redis = fakeredis.aioredis.FakeRedis()
    ch = AsyncMock()
    yahoo = MagicMock()
    yahoo.fetch_us_close_snapshot = AsyncMock(
        return_value=MacroSnapshot(
            ts_ms=1_700_000_000_000,
            session="overnight_us_close",
            sp500_close=5100.0, sp500_change_pct=1.0,
            nasdaq_close=17000.0, nasdaq_change_pct=0.9,
            collected_from=["yahoo"],
        )
    )
    rc = await collect_us_session(
        redis=redis, ch_client=ch, yahoo_source=yahoo,
        stream="stream:macro.overnight", maxlen=1000,
    )
    assert rc == 0
    entries = await redis.xrange("stream:macro.overnight")
    assert len(entries) == 1
    assert entries[0][1][b"session"] == b"overnight_us_close"
    ch.execute.assert_awaited()


@pytest.mark.asyncio
async def test_collect_fx_session_publishes_and_writes():
    redis = fakeredis.aioredis.FakeRedis()
    ch = AsyncMock()
    ecos = MagicMock()
    ecos.fetch_fx_snapshot = AsyncMock(
        return_value=MacroSnapshot(
            ts_ms=1_700_000_100_000,
            session="overnight_fx",
            usdkrw=1355.8, usdkrw_change_pct=0.4,
            collected_from=["ecos"],
        )
    )
    rc = await collect_fx_session(
        redis=redis, ch_client=ch, ecos_source=ecos,
        stream="stream:macro.overnight", maxlen=1000,
    )
    assert rc == 0
    entries = await redis.xrange("stream:macro.overnight")
    assert len(entries) == 1
    assert entries[0][1][b"session"] == b"overnight_fx"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/integration/test_macro_overnight_e2e.py -v
```

- [ ] **Step 3: Implement**

Create `services/macro_overnight_collector/__init__.py` (empty). Create `services/macro_overnight_collector/main.py`:

```python
"""Macro overnight batch collector — run via cron."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def _publish_snapshot(redis: Any, stream: str, maxlen: int, snap) -> None:
    payload = {
        "ts_ms": snap.ts_ms,
        "session": snap.session,
        "sp500_close": snap.sp500_close,
        "sp500_change_pct": snap.sp500_change_pct,
        "nasdaq_close": snap.nasdaq_close,
        "nasdaq_change_pct": snap.nasdaq_change_pct,
        "eurex_kospi_close": snap.eurex_kospi_close,
        "eurex_kospi_change_pct": snap.eurex_kospi_change_pct,
        "usdkrw": snap.usdkrw,
        "usdkrw_change_pct": snap.usdkrw_change_pct,
        "dxy": snap.dxy,
        "us10y_yield": snap.us10y_yield,
        "vix": snap.vix,
        "collected_from_json": json.dumps(snap.collected_from),
    }
    fields = {k: ("" if v is None else str(v)) for k, v in payload.items()}
    await redis.xadd(stream, fields, maxlen=maxlen, approximate=True)


_CH_INSERT = (
    "INSERT INTO kospi.macro_overnight "
    "(ts, session, sp500_close, sp500_change_pct, nasdaq_close, nasdaq_change_pct, "
    "eurex_kospi_close, eurex_kospi_change_pct, usdkrw, usdkrw_change_pct, dxy, "
    "us10y_yield, vix, collected_from) VALUES"
)


async def _write_ch(ch_client: Any, snap) -> None:
    row = (
        datetime.fromtimestamp(snap.ts_ms / 1000, tz=timezone.utc),
        snap.session,
        snap.sp500_close or 0.0,
        snap.sp500_change_pct or 0.0,
        snap.nasdaq_close or 0.0,
        snap.nasdaq_change_pct or 0.0,
        snap.eurex_kospi_close,
        snap.eurex_kospi_change_pct,
        snap.usdkrw or 0.0,
        snap.usdkrw_change_pct or 0.0,
        snap.dxy,
        snap.us10y_yield,
        snap.vix,
        snap.collected_from,
    )
    await ch_client.execute(_CH_INSERT, [row])


async def collect_us_session(
    *, redis: Any, ch_client: Any, yahoo_source: Any,
    stream: str, maxlen: int,
) -> int:
    snap = await yahoo_source.fetch_us_close_snapshot()
    await _publish_snapshot(redis, stream, maxlen, snap)
    await _write_ch(ch_client, snap)
    return 0


async def collect_fx_session(
    *, redis: Any, ch_client: Any, ecos_source: Any,
    stream: str, maxlen: int,
) -> int:
    snap = await ecos_source.fetch_fx_snapshot()
    await _publish_snapshot(redis, stream, maxlen, snap)
    await _write_ch(ch_client, snap)
    return 0


async def _cli(session_kind: str) -> int:
    import aiohttp
    import redis.asyncio as aioredis
    from shared.db.client import ClickHouseClient
    from shared.macro.sources.yahoo import YahooMacroSource
    from shared.macro.sources.ecos import ECOSSource

    stream = "stream:macro.overnight"
    maxlen = 5000
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    r = aioredis.from_url(redis_url)
    ch = ClickHouseClient.get_instance().async_client

    try:
        if session_kind == "us":
            rc = await collect_us_session(
                redis=r, ch_client=ch, yahoo_source=YahooMacroSource(),
                stream=stream, maxlen=maxlen,
            )
        elif session_kind == "fx":
            ecos_key = os.environ["ECOS_API_KEY"]
            async with aiohttp.ClientSession() as session:
                rc = await collect_fx_session(
                    redis=r, ch_client=ch,
                    ecos_source=ECOSSource(api_key=ecos_key, session=session),
                    stream=stream, maxlen=maxlen,
                )
        else:
            print(f"unknown session: {session_kind}", file=sys.stderr)
            rc = 2
    finally:
        await r.aclose()
    return rc


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("session", choices=["us", "fx"])
    args = p.parse_args()
    return asyncio.run(_cli(args.session))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Cron wrapper**

Create `scripts/cron/macro_overnight.sh` (mode `+x`):

```bash
#!/usr/bin/env bash
# Macro overnight collector.
# Usage: macro_overnight.sh us|fx
set -euo pipefail

cd "$(dirname "$0")/../.."

if [ ! -d ".venv" ]; then
  echo "venv not found" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
if [ -f .env ]; then
  set -a && source .env && set +a
fi

exec python -m services.macro_overnight_collector.main "$@"
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
chmod +x scripts/cron/macro_overnight.sh
pytest tests/integration/test_macro_overnight_e2e.py -v
```

- [ ] **Step 6: Commit**

```bash
black services/macro_overnight_collector/ tests/integration/test_macro_overnight_e2e.py
ruff check --fix services/macro_overnight_collector/ tests/integration/test_macro_overnight_e2e.py
git add services/macro_overnight_collector/ scripts/cron/macro_overnight.sh tests/integration/test_macro_overnight_e2e.py
git commit -m "feat(macro): overnight batch collector (us/fx) + cron wrapper"
```

---

## Task 15: Prometheus metrics for news + macro

**Files:**
- Modify: `services/monitoring/metrics.py`
- Test: `tests/unit/monitoring/test_news_macro_metrics.py`

- [ ] **Step 1: Read existing metrics module**

```bash
head -60 services/monitoring/metrics.py
grep -n "class MetricsCollector\|def record_\|Counter(\|Gauge(\|Histogram(" services/monitoring/metrics.py | head -30
```

Follow the file's existing pattern (Counter/Gauge/Histogram creation + `record_*` methods).

- [ ] **Step 2: Write failing test**

Create `tests/unit/monitoring/test_news_macro_metrics.py`:

```python
from prometheus_client import REGISTRY
from services.monitoring.metrics import (
    record_news_collected, record_news_duplicate, record_news_error,
    record_news_publish_lag, record_macro_collected,
)


def _sample(name: str, labels: dict) -> float | None:
    for metric in REGISTRY.collect():
        if metric.name != name:
            continue
        for s in metric.samples:
            if all(s.labels.get(k) == v for k, v in labels.items()):
                return s.value
    return None


def test_news_collected_counter_increments():
    before = _sample("news_collected_total", {"source": "yonhap"}) or 0
    record_news_collected("yonhap")
    after = _sample("news_collected_total", {"source": "yonhap"}) or 0
    assert after == before + 1


def test_news_duplicate_counter_increments():
    before = _sample("news_duplicates_total", {"source": "yonhap"}) or 0
    record_news_duplicate("yonhap")
    after = _sample("news_duplicates_total", {"source": "yonhap"}) or 0
    assert after == before + 1


def test_news_error_counter_includes_kind_label():
    record_news_error("reuters", "http")
    val = _sample("news_errors_total", {"source": "reuters", "kind": "http"})
    assert (val or 0) >= 1


def test_news_publish_lag_histogram_observes():
    record_news_publish_lag("dart", seconds=2.5)
    # Histogram exposes _sum and _count — use _count to verify observation
    cnt = _sample("news_publish_lag_seconds_count", {"source": "dart"})
    assert (cnt or 0) >= 1


def test_macro_collected_counter_increments():
    before = _sample("macro_collected_total", {"session": "overnight_fx"}) or 0
    record_macro_collected("overnight_fx")
    after = _sample("macro_collected_total", {"session": "overnight_fx"}) or 0
    assert after == before + 1
```

- [ ] **Step 3: Run — expect FAIL**

```bash
pytest tests/unit/monitoring/test_news_macro_metrics.py -v
```

- [ ] **Step 4: Extend `services/monitoring/metrics.py`**

Append (exact style to match existing conventions — check the file first):

```python
# ---- Phase 1 (futures paradigm): news & macro metrics ----
from prometheus_client import Counter as _Counter, Gauge as _Gauge, Histogram as _Histogram

_news_collected = _Counter(
    "news_collected_total", "News items collected", ["source"]
)
_news_duplicates = _Counter(
    "news_duplicates_total", "News items skipped as duplicates", ["source"]
)
_news_errors = _Counter(
    "news_errors_total", "News collector errors", ["source", "kind"]
)
_news_publish_lag = _Histogram(
    "news_publish_lag_seconds",
    "Seconds between published_at and XADD",
    ["source"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)
_news_stream_len = _Gauge(
    "news_stream_length", "Current XLEN of news stream", ["stream"]
)
_macro_collected = _Counter(
    "macro_collected_total", "Macro snapshots collected", ["session"]
)


def record_news_collected(source: str) -> None:
    _news_collected.labels(source=source).inc()


def record_news_duplicate(source: str) -> None:
    _news_duplicates.labels(source=source).inc()


def record_news_error(source: str, kind: str) -> None:
    _news_errors.labels(source=source, kind=kind).inc()


def record_news_publish_lag(source: str, seconds: float) -> None:
    _news_publish_lag.labels(source=source).observe(seconds)


def record_news_stream_length(stream: str, length: int) -> None:
    _news_stream_len.labels(stream=stream).set(length)


def record_macro_collected(session: str) -> None:
    _macro_collected.labels(session=session).inc()
```

- [ ] **Step 5: Wire metrics into daemon + macro collector**

In `services/news_collector/main.py::_loop`:
- After successful publish: `record_news_collected(source.name)`
- On dedupe hit: `record_news_duplicate(source.name)`
- On exception in except: `record_news_error(source.name, "fetch_cycle")`

In `services/macro_overnight_collector/main.py::collect_us_session` and `collect_fx_session`, after `_write_ch`:
- `record_macro_collected(snap.session)`

Add `import` statements:

```python
# news_collector/main.py top
from services.monitoring.metrics import (
    record_news_collected, record_news_duplicate, record_news_error,
)

# macro_overnight_collector/main.py top
from services.monitoring.metrics import record_macro_collected
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/unit/monitoring/test_news_macro_metrics.py -v
pytest tests/integration/ -v    # existing should still pass
```

- [ ] **Step 7: Commit**

```bash
black services/ tests/unit/monitoring/
ruff check --fix services/ tests/unit/monitoring/
git add services/monitoring/metrics.py services/news_collector/main.py services/macro_overnight_collector/main.py tests/unit/monitoring/
git commit -m "feat(monitoring): Phase 1 news/macro Prometheus metrics + wiring"
```

---

## Task 16: Macro config + systemd units

**Files:**
- Create: `config/macro_sources.yaml`
- Create: `deploy/systemd/kis-news-collector.service`
- Create: `deploy/systemd/kis-macro-overnight.service`
- Create: `deploy/systemd/kis-macro-overnight.timer`
- No new tests (deployment config)

- [ ] **Step 1: Write `config/macro_sources.yaml`**

```yaml
macro_overnight_collector:
  redis_stream: "stream:macro.overnight"
  redis_maxlen: 5000
  sessions:
    overnight_us_close:
      cron: "30 6 * * 1-5"
      indices: ["sp500", "nasdaq", "vix", "dxy", "us10y"]
      provider: "yahoo"
    overnight_fx:
      cron: "*/15 * * * 1-5"
      indices: ["usdkrw"]
      provider: "ecos"
  # overnight_eurex_close deferred — see spec §11
```

- [ ] **Step 2: systemd news collector service**

Create `deploy/systemd/kis-news-collector.service`:

```ini
[Unit]
Description=KIS News Collector (Phase 1)
After=network-online.target redis-server.service
Wants=network-online.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/project/kis_unified_sts
EnvironmentFile=/home/deploy/project/kis_unified_sts/.env
ExecStart=/home/deploy/project/kis_unified_sts/.venv/bin/python -m services.news_collector.main
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: systemd macro oneshot + timer**

Create `deploy/systemd/kis-macro-overnight.service`:

```ini
[Unit]
Description=KIS Macro Overnight Collector
After=network-online.target

[Service]
Type=oneshot
User=deploy
WorkingDirectory=/home/deploy/project/kis_unified_sts
EnvironmentFile=/home/deploy/project/kis_unified_sts/.env
ExecStart=/home/deploy/project/kis_unified_sts/scripts/cron/macro_overnight.sh %i
```

Create `deploy/systemd/kis-macro-overnight.timer`:

```ini
[Unit]
Description=Run macro overnight collector
[Timer]
# Two invocations — us at 06:30 weekday, fx every 15 min weekday
OnCalendar=Mon..Fri 06:30
OnCalendar=Mon..Fri *:00/15
Persistent=true
Unit=kis-macro-overnight@us.service
[Install]
WantedBy=timers.target
```

Note: Since we want two different schedules (us 1x/day, fx 4x/hour), simpler is to use cron for this rather than systemd timers. Create instead a single cron-based approach:

Create `scripts/cron/install_phase1_crontab.sh`:

```bash
#!/usr/bin/env bash
# Idempotent install of Phase 1 cron entries.
set -euo pipefail
BASE="/home/deploy/project/kis_unified_sts"

TMP=$(mktemp)
crontab -l 2>/dev/null | grep -v "macro_overnight.sh" > "$TMP" || true
cat >> "$TMP" <<'EOF'
# --- Phase 1 Futures Paradigm macro ---
30 6 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/macro_overnight.sh us >> /var/log/kis-macro-us.log 2>&1
*/15 * * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/macro_overnight.sh fx >> /var/log/kis-macro-fx.log 2>&1
EOF
crontab "$TMP"
rm -f "$TMP"
echo "installed."
```

- [ ] **Step 4: Deploy documentation**

Append to `docs/runbooks/` a brief entry or create `deploy/README.md` (if `docs/runbooks/` doesn't exist):

```markdown
# Phase 1 Deployment

## News collector
1. `sudo cp deploy/systemd/kis-news-collector.service /etc/systemd/system/`
2. `sudo systemctl daemon-reload && sudo systemctl enable --now kis-news-collector`
3. Verify: `systemctl status kis-news-collector; journalctl -u kis-news-collector -f`

## Macro overnight
1. `bash scripts/cron/install_phase1_crontab.sh`
2. Verify: `crontab -l | grep macro_overnight`
```

- [ ] **Step 5: Commit**

```bash
chmod +x scripts/cron/install_phase1_crontab.sh
git add config/macro_sources.yaml deploy/ scripts/cron/install_phase1_crontab.sh
git commit -m "chore(deploy): systemd unit + cron installer for Phase 1"
```

---

## Task 17: Full test suite run + Phase 1 Gate checklist

**Files:**
- Create: `docs/runbooks/phase1-verification.md`

- [ ] **Step 1: Full test sweep**

```bash
source .venv/bin/activate
black . && ruff check --fix . && pytest tests/ -v --cov=shared/news --cov=shared/macro --cov=services/news_collector --cov=services/macro_overnight_collector --cov-report=term-missing
```

Expected:
- all tests pass
- coverage ≥ 80% for new modules (spec §10 completion gate)

If coverage < 80%, add missing test cases before proceeding.

- [ ] **Step 2: Dry-run against real infra (local)**

```bash
# 1. Apply migrations (idempotent)
python scripts/migrations/apply_clickhouse_migrations.py

# 2. Verify tables
curl -s "http://localhost:8123/?query=SHOW%20TABLES%20FROM%20kospi" \
  --user "default:${CLICKHOUSE_PASSWORD}" \
  | grep -E "news_raw|macro_overnight|schema_migrations|signals_all|daily_performance"

# 3. Run FX macro once
scripts/cron/macro_overnight.sh fx

# 4. Verify Redis + CH
redis-cli -n 1 XLEN stream:macro.overnight
curl -s "http://localhost:8123/?query=SELECT%20count()%20FROM%20kospi.macro_overnight" \
  --user "default:${CLICKHOUSE_PASSWORD}"
```

- [ ] **Step 3: Deploy news collector daemon (staging)**

```bash
sudo cp deploy/systemd/kis-news-collector.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kis-news-collector
journalctl -u kis-news-collector -f    # watch for 1-2 min
```

- [ ] **Step 4: 48h gate checklist — write to runbook**

Create `docs/runbooks/phase1-verification.md`:

```markdown
# Phase 1 Completion Gate — 48h Verification

Checklist (all must pass before Phase 2 starts):

- [ ] ClickHouse migration V1 applied — tables exist:
      news_raw, macro_overnight, schema_migrations, signals_all, daily_performance
- [ ] `kis-news-collector` systemd unit: running 48h, Restart count = 0
      `systemctl show kis-news-collector -p NRestarts`
- [ ] Macro cron fired: at least 1 US run (06:30 KST wkday) + FX runs every 15 min
      `grep macro /var/log/syslog | tail`
- [ ] Redis stream volume (weekday window):
      - `redis-cli -n 1 XLEN stream:news.raw` >= 500
      - `redis-cli -n 1 XLEN stream:macro.overnight` >= 20
- [ ] ClickHouse insert counts match Redis XADD within 1%:
      - `SELECT count() FROM kospi.news_raw WHERE received_at >= now() - INTERVAL 2 DAY`
      - `SELECT count() FROM kospi.macro_overnight WHERE ts >= now() - INTERVAL 2 DAY`
- [ ] Test coverage: shared/news, shared/macro >= 80%
- [ ] `rl_mppo` daily P&L and latency unchanged (compare before vs. after
      deployment from ClickHouse reports and Prometheus metrics)
```

- [ ] **Step 5: Push branch + open draft PR**

```bash
git push -u origin feat/futures-paradigm-phase1
# Open a draft PR for user review — do not merge until Step 4 gates pass
gh pr create --draft --title "feat: Phase 1 — news & macro data infrastructure" \
  --body "Implements docs/plans/2026-04-20-futures-paradigm-phase1-data-infra.md

Ready for review but NOT ready to merge — awaiting 48h gate verification
per docs/runbooks/phase1-verification.md.

Coverage: shared/news + shared/macro >= 80% (see CI output)."
```

- [ ] **Step 6: Final commit (runbook)**

```bash
git add docs/runbooks/phase1-verification.md
git commit -m "docs(runbook): Phase 1 48h verification checklist"
git push
```

---

## Self-Review

**1. Spec coverage (from `2026-04-20-futures-paradigm-phase1-data-infra.md` §12 work breakdown):**

| Spec item | Tasks implementing it |
|-----------|----------------------|
| ClickHouse migration infra (incl. V1) | Task 2, 3 |
| `shared/streaming/` publisher wrappers | Task 6 (deliberately standalone async publisher, not wrapping sync one) |
| `shared/news/base.py` + dedupe + publisher | Tasks 4, 5, 6 |
| DART adapter | Task 9 |
| Yonhap + Reuters RSS | Tasks 7, 8 |
| MK adapter | Task 10 |
| `services/news_collector/main.py` daemon | Task 12 |
| `shared/macro/` + Yahoo/ECOS | Task 13 |
| `scripts/cron/macro_overnight.sh` | Task 14 |
| Prometheus + dashboard | Task 15 (metrics); monitoring dashboard edits left for Phase 1 ops (low-risk config) |
| systemd units + deploy | Task 16 |
| 48h verification | Task 17 |

monitoring dashboard JSON is intentionally NOT in this plan — it's a downstream ops artifact with low code-risk and high churn. Metrics emission (Task 15) is the prerequisite; dashboard can be composed by the ops engineer during the 48h gate window.

**2. Placeholder scan:** No TBDs, no "add error handling", no "similar to Task N" — every step has concrete code or commands. ✓

**3. Type consistency:**
- `NewsItem` fields used across Tasks 4/5/6/7/8/9/10/12 are consistent: `news_id, source, published_at_ms, received_at_ms, title, body, url, source_version, lang, keywords`.
- `MacroSnapshot` used across Tasks 13/14 is consistent.
- `NewsSource.fetch()` signature (async generator yielding `NewsItem`) is identical in Tasks 4 (ABC), 7, 8, 9, 10.
- `NewsCollectorDaemon.__init__` kwargs (Task 12) match what Task 15 wires metrics into.
- `_CH_INSERT` column order in Task 14 matches `kospi.macro_overnight` DDL in Task 3.

✓ No type/name mismatches found.

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-04-20-futures-paradigm-phase1-implementation-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Each task has clear boundaries and test-first structure, well-suited to isolated subagent execution.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
