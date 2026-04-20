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
    dart:
      enabled: false
      poll_interval_seconds: 30
    mk:
      enabled: false
      poll_interval_seconds: 180
      mode: "adapter"
        """.strip())
    cfg = NewsCollectorConfig.from_yaml_path(str(yaml))
    assert cfg.redis_stream == "stream:news.raw"
    assert cfg.sources.yonhap.enabled is True
    assert cfg.sources.reuters.enabled is False
    assert cfg.dedupe.memory_size == 10


def test_missing_required_key_raises(tmp_path):
    from pydantic import ValidationError

    yaml = tmp_path / "bad.yaml"
    yaml.write_text("news_collector:\n  redis_stream: x\n")
    with pytest.raises(ValidationError):
        NewsCollectorConfig.from_yaml_path(str(yaml))
