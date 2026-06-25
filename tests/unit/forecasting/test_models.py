"""Tests for forecasting dataclasses."""
import json
from datetime import UTC, datetime, timedelta

import pytest

from shared.forecasting.models import (
    EventScore,
    VolForecast,
    tier_for_impact_score,
)


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
    assert e2.impact_tier == e.impact_tier == 2  # 70 → tier 2 (default bands)


@pytest.mark.parametrize(
    ("score", "expected_tier"),
    [
        (100.0, 1),
        (75.0, 1),  # boundary inclusive
        (74.9, 2),
        (50.0, 2),  # boundary inclusive
        (49.9, 3),
        (0.0, 3),
    ],
)
def test_tier_for_impact_score_default_bands(score, expected_tier):
    assert tier_for_impact_score(score) == expected_tier


def test_tier_for_impact_score_custom_bands():
    # With tighter bands, a 60 score that is tier 2 under defaults becomes
    # tier 1 when tier1_min drops to 55.
    assert tier_for_impact_score(60.0, tier1_min=55, tier2_min=40) == 1
    assert tier_for_impact_score(45.0, tier1_min=55, tier2_min=40) == 2
    assert tier_for_impact_score(30.0, tier1_min=55, tier2_min=40) == 3


@pytest.mark.parametrize(
    ("score", "expected_tier"),
    [(90.0, 1), (60.0, 2), (20.0, 3)],
)
def test_event_score_derives_tier_when_omitted(score, expected_tier):
    e = EventScore(
        asof=datetime.now(UTC),
        impact_score=score,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    assert e.impact_tier == expected_tier


def test_event_score_respects_explicit_tier():
    # An explicit tier is NOT overridden by score-based derivation, so the
    # scorer's config-driven tier survives construction.
    e = EventScore(
        asof=datetime.now(UTC),
        impact_score=90.0,  # would derive tier 1
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
        impact_tier=2,
    )
    assert e.impact_tier == 2


def test_event_score_to_json_includes_impact_tier():
    e = EventScore(
        asof=datetime(2026, 5, 13, 9, 0, 0, tzinfo=UTC),
        impact_score=85.0,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    payload = json.loads(e.to_json())
    assert payload["impact_tier"] == 1


def test_event_score_from_json_backward_compat_derives_tier():
    # Pre-tier payloads (no impact_tier key) must load and derive the tier
    # from impact_score rather than raising.
    legacy = json.dumps(
        {
            "asof": datetime(2026, 5, 13, 9, 0, 0, tzinfo=UTC).isoformat(),
            "impact_score": 88.0,
            "event_type": "BOK_rate_decision",
            "source": "rule",
            "raw_text": None,
            "ttl_minutes": 30,
        }
    )
    e = EventScore.from_json(legacy)
    assert e.impact_tier == 1  # 88 → tier 1
