import pytest

from shared.news.config import NewsCollectorConfig


def test_loads_from_yaml(tmp_path):
    yaml = tmp_path / "news_sources.yaml"
    yaml.write_text("""
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
    marketaux:
      enabled: true
      poll_interval_seconds: 600
      api_token: "test-token"
      limit: 10
      language: "en"
      countries: "us,kr"
      symbols: "NVDA,005930"
      entity_types: "equity,index"
      filter_entities: true
      must_have_entities: true
      group_similar: true
      published_after_minutes: 360
      timeout_seconds: 20
    naver_search:
      enabled: true
      poll_interval_seconds: 300
      client_id: "naver-client"
      client_secret: "naver-secret"
      queries:
        - "인포스탁 개장전 주요이슈 점검"
        - "테마별 등락율 순위"
      display: 5
      sort: "date"
      timeout_seconds: 9
    dart:
      enabled: false
      poll_interval_seconds: 30
    mk:
      enabled: false
      poll_interval_seconds: 180
      mode: "adapter"
    gdelt:
      enabled: true
      poll_interval_seconds: 600
      query: '("Federal Reserve" OR "bond yields")'
      max_records: 10
      timespan: "6h"
      sort: "datedesc"
      timeout_seconds: 20
    rss_feeds:
      - name: "newsis_economy"
        enabled: true
        poll_interval_seconds: 240
        rss_url: "https://www.newsis.com/RSS/economy.xml"
        lang: "ko"
        timeout_seconds: 10
        """.strip())
    cfg = NewsCollectorConfig.from_yaml(str(yaml))
    assert cfg.redis_stream == "stream:news.raw"
    assert cfg.sources.yonhap.enabled is True
    assert cfg.sources.reuters.enabled is False
    assert cfg.sources.dart.lookback_days == 3
    assert cfg.sources.dart.page_count == 100
    assert cfg.sources.marketaux.api_token == "test-token"
    assert cfg.sources.marketaux.symbols == "NVDA,005930"
    assert cfg.sources.marketaux.must_have_entities is True
    assert cfg.sources.naver_search.enabled is True
    assert cfg.sources.naver_search.client_id == "naver-client"
    assert cfg.sources.naver_search.queries == [
        "인포스탁 개장전 주요이슈 점검",
        "테마별 등락율 순위",
    ]
    assert cfg.sources.naver_search.display == 5
    assert cfg.sources.gdelt.max_records == 10
    assert cfg.sources.rss_feeds[0].name == "newsis_economy"
    assert cfg.dedupe.memory_size == 10


def test_missing_required_key_raises(tmp_path):
    from pydantic import ValidationError

    yaml = tmp_path / "bad.yaml"
    yaml.write_text("news_collector:\n  redis_stream: x\n")
    with pytest.raises(ValidationError):
        NewsCollectorConfig.from_yaml(str(yaml))
