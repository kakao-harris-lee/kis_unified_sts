"""Tests for Phase 2 news-scoring Prometheus metric families.

Verifies:
- All 6 module-level metric objects are registered (not None).
- Each record_* helper can be called without raising.
- Prometheus REGISTRY reflects the increments/observations.
"""

from prometheus_client import REGISTRY

from services.monitoring.metrics import (
    news_scored_total,
    news_scorer_backlog,
    news_scoring_cost_usd_today,
    news_scoring_duration_seconds,
    news_scoring_errors_total,
    news_scoring_fallback_total,
    record_news_scored,
    record_news_scorer_backlog,
    record_news_scoring_cost,
    record_news_scoring_duration,
    record_news_scoring_error,
    record_news_scoring_fallback,
)


def _sample(name: str, labels: dict) -> float | None:
    """Return the current sample value for *name* with matching *labels*, or None."""
    for metric in REGISTRY.collect():
        for s in metric.samples:
            if s.name != name:
                continue
            if all(s.labels.get(k) == v for k, v in labels.items()):
                return s.value
    return None


# ---------------------------------------------------------------------------
# 1. Metric objects exist (not None)
# ---------------------------------------------------------------------------


def test_news_scored_total_is_registered():
    assert news_scored_total is not None


def test_news_scoring_duration_seconds_is_registered():
    assert news_scoring_duration_seconds is not None


def test_news_scoring_errors_total_is_registered():
    assert news_scoring_errors_total is not None


def test_news_scoring_fallback_total_is_registered():
    assert news_scoring_fallback_total is not None


def test_news_scoring_cost_usd_today_is_registered():
    assert news_scoring_cost_usd_today is not None


def test_news_scorer_backlog_is_registered():
    assert news_scorer_backlog is not None


# ---------------------------------------------------------------------------
# 2. record_* helpers do not raise and update the registry
# ---------------------------------------------------------------------------


def test_record_news_scored_increments_counter():
    before = _sample("news_scored_total", {"version": "v1", "category": "market"}) or 0
    record_news_scored(version="v1", category="market")
    after = _sample("news_scored_total", {"version": "v1", "category": "market"}) or 0
    assert after == before + 1


def test_record_news_scoring_duration_observes_histogram():
    record_news_scoring_duration(version="v1", seconds=1.5)
    cnt = _sample("news_scoring_duration_seconds_count", {"version": "v1"})
    assert (cnt or 0) >= 1


def test_record_news_scoring_error_increments_counter():
    before = _sample("news_scoring_errors_total", {"kind": "timeout"}) or 0
    record_news_scoring_error(kind="timeout")
    after = _sample("news_scoring_errors_total", {"kind": "timeout"}) or 0
    assert after == before + 1


def test_record_news_scoring_fallback_increments_counter():
    before = _sample("news_scoring_fallback_total", {"reason": "llm_unavailable"}) or 0
    record_news_scoring_fallback(reason="llm_unavailable")
    after = _sample("news_scoring_fallback_total", {"reason": "llm_unavailable"}) or 0
    assert after == before + 1


def test_record_news_scoring_cost_sets_gauge():
    record_news_scoring_cost(usd=0.042)
    val = _sample("news_scoring_cost_usd_today", {})
    assert val is not None
    assert abs(val - 0.042) < 1e-6


def test_record_news_scorer_backlog_sets_gauge():
    record_news_scorer_backlog(count=7)
    val = _sample("news_scorer_backlog", {})
    assert val is not None
    assert val == 7
