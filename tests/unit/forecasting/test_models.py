"""Tests for forecasting dataclasses."""
from datetime import UTC, datetime, timedelta

import pytest

from shared.forecasting.models import EventScore, VolForecast


def test_vol_forecast_is_fresh_within_max_age():
    f = VolForecast(
        asof=datetime.now(UTC) - timedelta(seconds=60),
        horizon_minutes=15,
        forecast_pct=18.0,
        forecast_atr_equivalent=3.0,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )
    assert f.is_fresh(datetime.now(UTC), max_age_s=120) is True


def test_vol_forecast_is_stale_when_old():
    f = VolForecast(
        asof=datetime.now(UTC) - timedelta(seconds=200),
        horizon_minutes=15,
        forecast_pct=18.0,
        forecast_atr_equivalent=3.0,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )
    assert f.is_fresh(datetime.now(UTC), max_age_s=120) is False


def test_vol_forecast_to_json_roundtrip():
    f = VolForecast(
        asof=datetime(2026, 5, 13, 9, 0, 0, tzinfo=UTC),
        horizon_minutes=15,
        forecast_pct=18.5,
        forecast_atr_equivalent=3.2,
        regime_percentile=72.0,
        model_version="har_rv_v1",
        confidence=0.31,
    )
    blob = f.to_json()
    f2 = VolForecast.from_json(blob)
    assert f2.asof == f.asof
    assert f2.forecast_pct == pytest.approx(f.forecast_pct)
    assert f2.confidence == pytest.approx(f.confidence)


def test_event_score_is_expired_after_ttl():
    e = EventScore(
        asof=datetime.now(UTC) - timedelta(minutes=31),
        impact_score=85.0,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    assert e.is_expired(datetime.now(UTC)) is True


def test_event_score_not_expired_within_ttl():
    e = EventScore(
        asof=datetime.now(UTC) - timedelta(minutes=10),
        impact_score=85.0,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    assert e.is_expired(datetime.now(UTC)) is False


def test_event_score_to_json_roundtrip():
    e = EventScore(
        asof=datetime(2026, 5, 13, 9, 0, 0, tzinfo=UTC),
        impact_score=70.0,
        event_type="CPI",
        source="llm",
        raw_text="CPI prints hot at 3.5%",
        ttl_minutes=30,
    )
    blob = e.to_json()
    e2 = EventScore.from_json(blob)
    assert e2.event_type == e.event_type
    assert e2.impact_score == e.impact_score
    assert e2.source == e.source
    assert e2.raw_text == e.raw_text
