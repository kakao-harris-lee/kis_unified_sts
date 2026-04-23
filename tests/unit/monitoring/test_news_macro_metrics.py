"""Tests for Phase 1 news/macro Prometheus metrics."""

from prometheus_client import REGISTRY

from services.monitoring.metrics import (
    record_macro_collected,
    record_news_collected,
    record_news_duplicate,
    record_news_error,
    record_news_publish_lag,
)


def _sample(name: str, labels: dict) -> float | None:
    """Find a sample by its full sample name (e.g. 'news_collected_total') and labels."""
    for metric in REGISTRY.collect():
        for s in metric.samples:
            if s.name != name:
                continue
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
