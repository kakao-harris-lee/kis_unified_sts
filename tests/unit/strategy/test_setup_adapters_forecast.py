"""Tests for forecast_integration config blocks on Setup A/C."""
import pytest

from shared.strategy.entry.setup_adapters import (
    SetupAEntryConfig,
    SetupCEntryConfig,
)


def test_setup_a_forecast_defaults_disabled():
    cfg = SetupAEntryConfig()
    assert cfg.forecast_integration.enabled is False
    assert cfg.forecast_integration.gap_threshold_vol_mult == 1.0


def test_setup_c_forecast_defaults_disabled():
    cfg = SetupCEntryConfig()
    assert cfg.forecast_integration.enabled is False
    assert cfg.forecast_integration.buffer_vol_mult == 0.5
    assert cfg.forecast_integration.target_vol_mult == 2.5


def test_setup_c_forecast_enabled_loads():
    cfg = SetupCEntryConfig(
        forecast_integration={
            "enabled": True,
            "buffer_vol_mult": 0.7,
            "target_vol_mult": 3.0,
            "min_event_impact_score": 70,
            "vol_baseline_window_days": 30,
            "stale_forecast_fallback": "atr",
            "inverse_vol_position_size": True,
        }
    )
    assert cfg.forecast_integration.enabled is True
    assert cfg.forecast_integration.buffer_vol_mult == 0.7


def test_invalid_min_event_impact_rejected():
    with pytest.raises(Exception):
        SetupCEntryConfig(
            forecast_integration={"enabled": True, "min_event_impact_score": 150}
        )
