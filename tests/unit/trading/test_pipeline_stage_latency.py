"""Pipeline stage-latency observe helper: slow-stage WARN + best-effort safety."""

from __future__ import annotations

import logging

from services.trading.pipeline import _observe_stage_latency


def test_slow_stage_logs_warning(caplog) -> None:
    """A stage exec far over its interval logs a WARNING and does not raise."""
    with caplog.at_level(logging.WARNING, logger="services.trading.pipeline"):
        _observe_stage_latency("entry", 9999.0, 1.0)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("slow" in r.getMessage() for r in warnings)


def test_fast_stage_logs_no_warning(caplog) -> None:
    """A fast stage exec logs no WARNING and does not raise."""
    with caplog.at_level(logging.WARNING, logger="services.trading.pipeline"):
        _observe_stage_latency("entry", 5.0, 1.0)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert not warnings
