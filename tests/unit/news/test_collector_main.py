"""CLI glue coverage for services.news_collector.main.

The integration test covers NewsCollectorDaemon business logic; these
tests cover the CLI wiring (_build_and_run_from_config + main) and the
source-fetch exception path in the daemon loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

from services.news_collector.main import (
    NewsCollectorDaemon,
    _build_and_run_from_config,
    main,
)
from shared.news.base import NewsItem, NewsSource


class _FailingSource(NewsSource):
    name = "fail"
    version = "fail-v1"
    poll_interval_seconds = 1

    def __init__(self):
        self.calls = 0

    async def fetch(self) -> AsyncIterator[NewsItem]:
        self.calls += 1
        raise RuntimeError("simulated fetch failure")
        yield  # make this a generator for typing


@pytest.mark.asyncio
async def test_loop_records_error_and_keeps_running_on_fetch_exception():
    redis = fakeredis.aioredis.FakeRedis()
    ch = AsyncMock()
    source = _FailingSource()

    daemon = NewsCollectorDaemon(
        redis=redis,
        ch_client=ch,
        sources=[source],
        stream="stream:news.raw",
        stream_maxlen=100,
        dedupe_memory=100,
        dedupe_ttl_days=1,
        ch_batch_size=10,
        ch_flush_interval=60,
        body_truncate_chars=500,
    )

    with patch("services.news_collector.main.record_news_error") as rec_err:
        task = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.2)
        await daemon.stop()
        await task

    assert source.calls >= 1
    rec_err.assert_called_with("fail", "fetch_cycle")


def _make_cfg(**source_enables):
    defaults = {
        "yonhap": True,
        "reuters": True,
        "marketaux": False,
        "naver_search": False,
        "gdelt": False,
        "dart": True,
        "mk": True,
    }
    defaults.update(source_enables)
    cfg = MagicMock()
    cfg.redis_stream = "stream:news.raw"
    cfg.redis_maxlen = 100
    cfg.clickhouse_batch_size = 10
    cfg.clickhouse_flush_interval_seconds = 60
    cfg.body_truncate_chars = 500
    cfg.dedupe.memory_size = 100
    cfg.dedupe.redis_ttl_days = 1
    for name, enabled in defaults.items():
        section = getattr(cfg.sources, name)
        section.enabled = enabled
        if name in {"yonhap", "reuters"}:
            section.rss_url = f"https://example.com/{name}.rss"
    cfg.sources.marketaux.poll_interval_seconds = 600
    cfg.sources.marketaux.api_token = "test-token"
    cfg.sources.marketaux.endpoint = "https://api.marketaux.com/v1/news/all"
    cfg.sources.marketaux.limit = 10
    cfg.sources.marketaux.language = "en"
    cfg.sources.marketaux.countries = "us,kr"
    cfg.sources.marketaux.symbols = ""
    cfg.sources.marketaux.entity_types = "equity,index"
    cfg.sources.marketaux.industries = ""
    cfg.sources.marketaux.search = ""
    cfg.sources.marketaux.domains = ""
    cfg.sources.marketaux.exclude_domains = ""
    cfg.sources.marketaux.filter_entities = True
    cfg.sources.marketaux.must_have_entities = False
    cfg.sources.marketaux.group_similar = True
    cfg.sources.marketaux.published_after_minutes = 720
    cfg.sources.marketaux.timeout_seconds = 20
    cfg.sources.naver_search.poll_interval_seconds = 300
    cfg.sources.naver_search.client_id = "naver-client"
    cfg.sources.naver_search.client_secret = "naver-secret"
    cfg.sources.naver_search.endpoint = "https://openapi.naver.com/v1/search/news.json"
    cfg.sources.naver_search.queries = ["인포스탁 개장전 주요이슈 점검"]
    cfg.sources.naver_search.display = 10
    cfg.sources.naver_search.sort = "date"
    cfg.sources.naver_search.timeout_seconds = 10
    cfg.sources.gdelt.poll_interval_seconds = 600
    cfg.sources.gdelt.query = '("Federal Reserve" OR "bond yields")'
    cfg.sources.gdelt.max_records = 10
    cfg.sources.gdelt.timespan = "6h"
    cfg.sources.gdelt.sort = "datedesc"
    cfg.sources.gdelt.timeout_seconds = 20
    cfg.sources.rss_feeds = []
    return cfg


class _NoopSource(NewsSource):
    name = "noop"
    version = "noop-v1"
    poll_interval_seconds = 60

    async def fetch(self) -> AsyncIterator[NewsItem]:
        return
        yield  # pragma: no cover


@pytest.mark.asyncio
async def test_build_and_run_all_sources_enabled(monkeypatch):
    """Exercises the full construction path when every source is enabled."""
    cfg = _make_cfg()
    cfg.sources.marketaux.enabled = True
    cfg.sources.naver_search.enabled = True
    cfg.sources.gdelt.enabled = True
    cfg.sources.rss_feeds = [
        SimpleNamespace(
            enabled=True,
            name="newsis_economy",
            rss_url="https://example.com/newsis.rss",
            lang="ko",
            version=None,
            poll_interval_seconds=240,
            timeout_seconds=10,
        )
    ]

    monkeypatch.setattr(
        "shared.news.config.NewsCollectorConfig.from_yaml",
        classmethod(lambda _cls, *_a, **_kw: cfg),
    )
    monkeypatch.setattr(
        "redis.asyncio.from_url",
        lambda *_a, **_kw: fakeredis.aioredis.FakeRedis(),
    )
    fake_ch = AsyncMock()
    monkeypatch.setattr(
        "shared.db.client.AsyncClickHouseClient",
        lambda *_a, **_kw: fake_ch,
    )
    monkeypatch.setattr(
        "shared.db.config.ClickHouseConfig.from_env",
        classmethod(lambda _cls, database=None: MagicMock()),  # noqa: ARG005
    )

    # Real aiohttp.ClientSession is fine — we never issue requests because
    # we immediately stop the daemon. Make session.close() a no-op safe net.
    fake_session = AsyncMock()
    monkeypatch.setattr("aiohttp.ClientSession", lambda *_a, **_kw: fake_session)

    # Source classes: return a _NoopSource instance regardless of kwargs.
    monkeypatch.setattr(
        "shared.news.sources.yonhap.YonhapRSSSource",
        lambda *_a, **_kw: _NoopSource(),
    )
    monkeypatch.setattr(
        "shared.news.sources.reuters.ReutersRSSSource",
        lambda *_a, **_kw: _NoopSource(),
    )
    monkeypatch.setattr(
        "shared.news.sources.marketaux.MarketauxNewsSource",
        lambda *_a, **_kw: _NoopSource(),
    )
    monkeypatch.setattr(
        "shared.news.sources.naver_search.NaverNewsSearchSource",
        lambda *_a, **_kw: _NoopSource(),
    )
    monkeypatch.setattr(
        "shared.news.sources.gdelt.GDELTNewsSource",
        lambda *_a, **_kw: _NoopSource(),
    )
    monkeypatch.setattr(
        "shared.news.sources.rss.GenericRSSSource",
        lambda *_a, **_kw: _NoopSource(),
    )
    # DART + MK import paths must exist (shared.llm.collectors is real).
    # Patch the adapters to _NoopSource.
    monkeypatch.setattr(
        "shared.news.sources.dart.DARTNewsSource",
        lambda *_a, **_kw: _NoopSource(),
    )
    monkeypatch.setattr(
        "shared.news.sources.mk_adapter.MKNewsSourceAdapter",
        lambda *_a, **_kw: _NoopSource(),
    )
    # Prevent real collector construction side effects.
    monkeypatch.setattr(
        "shared.llm.collectors.DARTDataCollector",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.llm.collectors.MKStockNewsCollector",
        lambda *_a, **_kw: MagicMock(),
    )

    # Short-circuit the actual run loop.
    async def fast_run(self):
        self._stop.set()

    monkeypatch.setattr(NewsCollectorDaemon, "run", fast_run)

    rc = await _build_and_run_from_config()
    assert rc == 0
    fake_ch.connect.assert_awaited()
    fake_ch.close.assert_awaited()
    fake_session.close.assert_awaited()


@pytest.mark.asyncio
async def test_build_and_run_skips_naver_search_without_credentials(monkeypatch):
    cfg = _make_cfg(
        yonhap=False,
        reuters=False,
        marketaux=False,
        naver_search=True,
        gdelt=False,
        dart=False,
        mk=False,
    )
    cfg.sources.naver_search.client_id = ""
    cfg.sources.naver_search.client_secret = ""

    monkeypatch.setattr(
        "shared.news.config.NewsCollectorConfig.from_yaml",
        classmethod(lambda _cls, *_a, **_kw: cfg),
    )
    monkeypatch.setattr(
        "redis.asyncio.from_url",
        lambda *_a, **_kw: fakeredis.aioredis.FakeRedis(),
    )
    fake_ch = AsyncMock()
    monkeypatch.setattr(
        "shared.db.client.AsyncClickHouseClient",
        lambda *_a, **_kw: fake_ch,
    )
    monkeypatch.setattr(
        "shared.db.config.ClickHouseConfig.from_env",
        classmethod(lambda _cls, database=None: MagicMock()),  # noqa: ARG005
    )
    fake_session = AsyncMock()
    monkeypatch.setattr("aiohttp.ClientSession", lambda *_a, **_kw: fake_session)

    captured = {}

    async def fast_run(self):
        captured["sources"] = self.sources
        self._stop.set()

    monkeypatch.setattr(NewsCollectorDaemon, "run", fast_run)

    rc = await _build_and_run_from_config()
    assert rc == 0
    assert captured["sources"] == []


@pytest.mark.asyncio
async def test_build_and_run_dart_mk_import_error(monkeypatch):
    """Verifies the except-ImportError branches when optional collectors are missing."""
    cfg = _make_cfg(yonhap=False, reuters=False, dart=True, mk=True)

    monkeypatch.setattr(
        "shared.news.config.NewsCollectorConfig.from_yaml",
        classmethod(lambda _cls, *_a, **_kw: cfg),
    )
    monkeypatch.setattr(
        "redis.asyncio.from_url",
        lambda *_a, **_kw: fakeredis.aioredis.FakeRedis(),
    )
    fake_ch = AsyncMock()
    monkeypatch.setattr(
        "shared.db.client.AsyncClickHouseClient",
        lambda *_a, **_kw: fake_ch,
    )
    monkeypatch.setattr(
        "shared.db.config.ClickHouseConfig.from_env",
        classmethod(lambda _cls, database=None: MagicMock()),  # noqa: ARG005
    )

    fake_session = AsyncMock()
    monkeypatch.setattr("aiohttp.ClientSession", lambda *_a, **_kw: fake_session)

    # Force ImportError on DART + MK imports. Patch the submodules so the
    # `from shared.llm.collectors import DARTDataCollector` line raises.
    import builtins

    real_import = builtins.__import__

    def boom_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "shared.llm.collectors" and fromlist:
            raise ImportError("forced for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", boom_import)

    async def fast_run(self):
        self._stop.set()

    monkeypatch.setattr(NewsCollectorDaemon, "run", fast_run)

    rc = await _build_and_run_from_config()
    assert rc == 0


def test_main_wrapper_invokes_build_and_run(monkeypatch):
    """main() wraps asyncio.run(_build_and_run_from_config)."""
    called = {}

    async def fake_build():
        called["invoked"] = True
        return 0

    monkeypatch.setattr(
        "services.news_collector.main._build_and_run_from_config", fake_build
    )
    rc = main()
    assert rc == 0
    assert called["invoked"] is True
