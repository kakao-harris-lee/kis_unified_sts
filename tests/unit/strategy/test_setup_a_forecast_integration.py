"""Tests for Setup A adapter consuming ForecastClient."""
from datetime import UTC, datetime

import pytest

from shared.forecasting.models import EventScore, VolForecast
from shared.strategy.entry.setup_adapters import (
    SetupAEntryAdapter,
    SetupAEntryConfig,
    SetupAForecastIntegrationConfig,
)


def _vf(forecast_atr_eq=3.0, daily_vol_pct=18.0):
    return VolForecast(
        asof=datetime.now(UTC),
        horizon_minutes=15,
        forecast_pct=daily_vol_pct,
        forecast_atr_equivalent=forecast_atr_eq,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )


def test_gap_threshold_scales_with_vol_when_enabled():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=True, gap_threshold_vol_mult=1.0
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    # Daily vol = 18% — 1.0× = 18% as gap threshold in % units
    gap_threshold_pct = adapter._derive_gap_threshold_pct(
        forecast=_vf(daily_vol_pct=18.0)
    )
    assert gap_threshold_pct == pytest.approx(18.0)


def test_gap_threshold_falls_back_when_forecast_absent():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=True, gap_threshold_vol_mult=1.0
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    # No forecast → fall back to existing config min_kr_gap_pct (Korean open gap)
    threshold = adapter._derive_gap_threshold_pct(forecast=None)
    assert threshold == cfg.min_kr_gap_pct


def test_max_gap_filter_rejects_too_large_gap():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=True, max_gap_for_reversion_vol_mult=4.0
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    vf = _vf(daily_vol_pct=10.0)  # 10% daily vol
    # gap 30% > 4 * 10% = 40%? No, < threshold → accept
    assert adapter._gap_within_reversion_range(gap_pct=30.0, forecast=vf) is True
    # gap 50% > 40% → reject (extreme)
    assert adapter._gap_within_reversion_range(gap_pct=50.0, forecast=vf) is False


def test_event_size_reduction_when_event_strong():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=True, use_event_impact_for_size=True
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    strong = EventScore(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    # 1 / (1 + 0.85) ≈ 0.54
    mult = adapter._compute_event_size_mult(event_score=strong)
    assert mult == pytest.approx(1.0 / 1.85)


def test_event_size_mult_is_1_when_no_event():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=True, use_event_impact_for_size=True
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    mult = adapter._compute_event_size_mult(event_score=None)
    assert mult == 1.0


def test_event_size_mult_is_1_when_disabled():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=False, use_event_impact_for_size=True
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    strong = EventScore(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    mult = adapter._compute_event_size_mult(event_score=strong)
    assert mult == 1.0
