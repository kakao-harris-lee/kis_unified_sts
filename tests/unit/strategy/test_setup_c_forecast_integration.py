"""Tests for Setup C adapter consuming ForecastClient."""
from datetime import UTC, datetime

import pytest

from shared.forecasting.models import EventScore, VolForecast
from shared.strategy.entry.setup_adapters import (
    SetupCEntryAdapter,
    SetupCEntryConfig,
    SetupCForecastIntegrationConfig,
)


def _vf(forecast_atr_eq=3.0):
    return VolForecast(
        asof=datetime.now(UTC),
        horizon_minutes=15,
        forecast_pct=18.0,
        forecast_atr_equivalent=forecast_atr_eq,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )


def test_buffer_scales_with_forecast_when_enabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, buffer_vol_mult=0.5, target_vol_mult=2.5
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    # When forecast_atr_eq = 6 (2x normal), buffer = 0.5 * 6 = 3
    buffer, target = adapter._derive_thresholds(
        forecast=_vf(forecast_atr_eq=6.0), atr=3.0
    )
    assert buffer == pytest.approx(3.0)
    assert target == pytest.approx(15.0)


def test_buffer_falls_back_to_atr_when_disabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=False, buffer_vol_mult=0.5, target_vol_mult=2.5
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    buffer, target = adapter._derive_thresholds(forecast=None, atr=3.0)
    # ATR-based with existing params (defaults breakout_buffer_atr_mult=0.5, target=2.5)
    assert buffer == pytest.approx(3.0 * 0.5)
    assert target == pytest.approx(3.0 * 2.5)


def test_buffer_falls_back_to_atr_when_forecast_stale():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, buffer_vol_mult=0.5, target_vol_mult=2.5
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    # forecast=None simulates stale (client returned None)
    buffer, target = adapter._derive_thresholds(forecast=None, atr=3.0)
    assert buffer == pytest.approx(3.0 * 0.5)
    assert target == pytest.approx(3.0 * 2.5)


def test_event_filter_uses_impact_score_when_enabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, min_event_impact_score=70
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    weak = EventScore(
        asof=datetime.now(UTC),
        impact_score=50,
        event_type="X",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    strong = EventScore(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    assert adapter._event_passes_filter(weak) is False
    assert adapter._event_passes_filter(strong) is True


def test_event_filter_uses_tier_fallback_when_forecast_disabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(enabled=False)
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    # When forecast disabled, all events pass the new filter (legacy tier filter
    # remains the gate)
    assert adapter._event_passes_filter(None) is True


def test_event_filter_blocks_when_event_missing_but_forecast_enabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, min_event_impact_score=70
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    # No event score → no filter applied (lets tier filter handle it)
    assert adapter._event_passes_filter(None) is True
