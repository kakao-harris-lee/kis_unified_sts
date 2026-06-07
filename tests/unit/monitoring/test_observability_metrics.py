"""Increment-1 observability metrics: definitions + record methods."""

from __future__ import annotations

from services.monitoring.metrics import MetricsCollector


def _c() -> MetricsCollector:
    return MetricsCollector()


def test_record_pipeline_stage_latency_does_not_raise() -> None:
    c = _c()
    c.record_pipeline_stage_latency("entry", 12.5)  # must not raise (best-effort)


def test_record_ws_reconnect_and_disconnect() -> None:
    c = _c()
    c.record_ws_reconnect("stock")
    c.record_ws_disconnect("futures")  # must not raise


def test_record_rate_limit_penalty() -> None:
    c = _c()
    c.record_rate_limit_penalty()  # must not raise


def test_record_order_latency_observes() -> None:
    c = _c()
    c.record_order_latency(42.0)  # already exists; smoke that it runs
