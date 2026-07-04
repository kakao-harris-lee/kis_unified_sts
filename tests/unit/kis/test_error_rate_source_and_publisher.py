"""Per-source key suffix + publish-loop lifecycle helpers.

Covers the decoupled-pipeline fix: each publisher (screener, order_router)
writes its own ``kill_switch:metrics:api_error_rate_5min:<source>`` key so the
kill-switch provider can aggregate them, and the shared start/stop helpers used
by both daemons.
"""

from unittest.mock import AsyncMock, patch

import pytest

from shared.kis.error_rate import (
    ErrorRateConfig,
    KISApiErrorRateTracker,
    start_error_rate_publisher,
    stop_error_rate_publisher,
)

_BASE = "kill_switch:metrics:api_error_rate_5min"


def test_source_suffix_appended_when_env_set(monkeypatch):
    monkeypatch.setenv("KIS_ERROR_RATE_SOURCE", "order_router")
    with patch("shared.kis.error_rate._load_config", return_value={}):
        cfg = ErrorRateConfig.from_yaml()
    assert cfg.redis_key == f"{_BASE}:order_router"


def test_no_suffix_when_env_absent(monkeypatch):
    monkeypatch.delenv("KIS_ERROR_RATE_SOURCE", raising=False)
    with patch("shared.kis.error_rate._load_config", return_value={}):
        cfg = ErrorRateConfig.from_yaml()
    assert cfg.redis_key == _BASE


def test_source_suffix_whitespace_ignored(monkeypatch):
    monkeypatch.setenv("KIS_ERROR_RATE_SOURCE", "   ")
    with patch("shared.kis.error_rate._load_config", return_value={}):
        cfg = ErrorRateConfig.from_yaml()
    assert cfg.redis_key == _BASE


@pytest.mark.asyncio
async def test_start_publisher_disabled_returns_none():
    result = await start_error_rate_publisher(enabled=False)
    assert result is None


@pytest.mark.asyncio
async def test_start_stop_publisher_enabled():
    fake = AsyncMock()
    with patch.object(KISApiErrorRateTracker, "get_instance", return_value=fake):
        tracker = await start_error_rate_publisher(enabled=True)
    assert tracker is fake
    fake.start.assert_awaited_once()

    await stop_error_rate_publisher(tracker)
    fake.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_publisher_none_is_noop():
    # Must not raise when nothing was started.
    await stop_error_rate_publisher(None)


@pytest.mark.asyncio
async def test_start_publisher_swallows_errors():
    with patch.object(
        KISApiErrorRateTracker, "get_instance", side_effect=RuntimeError("boom")
    ):
        tracker = await start_error_rate_publisher(enabled=True)
    assert tracker is None
