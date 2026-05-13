"""Tests for Setup A/C forecast consumer client."""
import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from shared.forecasting.client import ForecastClient
from shared.forecasting.models import EventScore, VolForecast


@pytest.fixture
def redis_mock():
    r = MagicMock()
    return r


def _vf_json(asof: datetime) -> str:
    return VolForecast(
        asof=asof,
        horizon_minutes=15,
        forecast_pct=18.0,
        forecast_atr_equivalent=3.0,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    ).to_json()


def test_get_latest_vol_forecast_returns_fresh(redis_mock):
    asof = datetime.now(UTC)
    redis_mock.get.return_value = _vf_json(asof)
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_vol_forecast()

    vf = asyncio.run(_run())
    assert vf is not None
    assert vf.forecast_pct == 18.0


def test_get_latest_vol_forecast_returns_none_when_missing(redis_mock):
    redis_mock.get.return_value = None
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_vol_forecast()

    assert asyncio.run(_run()) is None


def test_get_latest_vol_forecast_returns_none_when_stale(redis_mock):
    old_asof = datetime.now(UTC) - timedelta(seconds=200)
    redis_mock.get.return_value = _vf_json(old_asof)
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_vol_forecast()

    assert asyncio.run(_run()) is None


def test_get_latest_vol_forecast_handles_malformed_json(redis_mock):
    redis_mock.get.return_value = "{not valid json"
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_vol_forecast()

    assert asyncio.run(_run()) is None


def test_get_latest_event_score_falls_back_to_redis_get(redis_mock):
    es = EventScore(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    redis_mock.get.return_value = es.to_json()
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_event_score()

    out = asyncio.run(_run())
    assert out is not None
    assert out.event_type == "FOMC"
    assert out.impact_score == 85


def test_get_latest_event_score_returns_none_when_expired(redis_mock):
    es = EventScore(
        asof=datetime.now(UTC) - timedelta(minutes=60),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    redis_mock.get.return_value = es.to_json()
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_event_score()

    assert asyncio.run(_run()) is None
