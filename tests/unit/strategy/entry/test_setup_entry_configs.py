"""Tests for extracted futures setup entry configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.strategy.entry.setup_entry_configs import (
    LLMTuningConfig,
    SetupAEntryConfig,
    SetupAForecastIntegrationConfig,
    SetupCEntryConfig,
    SetupCForecastIntegrationConfig,
    SetupDEntryConfig,
)


def test_llm_tuning_defaults_and_validation_bounds():
    cfg = LLMTuningConfig()

    assert cfg.model_dump() == {
        "enabled": False,
        "min_context_confidence": 0.3,
        "risk_off_threshold": 75.0,
        "risk_off_confidence_multiplier": 1.3,
        "bull_strong_regime": "BULL_STRONG",
        "atr_loose_factor": 0.8,
        "long_blocked_regimes": ["BEAR_STRONG", "BEAR_MODERATE"],
        "short_blocked_regimes": [],
        "min_signal_confidence": 0.0,
        "veto_enabled": True,
        "veto_min_confidence": 0.6,
        "veto_long_block_signal": "STRONG_BEARISH",
        "veto_short_block_signal": "STRONG_BULLISH",
    }

    with pytest.raises(ValidationError):
        LLMTuningConfig(min_signal_confidence=1.1)

    with pytest.raises(ValidationError):
        LLMTuningConfig(veto_min_confidence=-0.1)


def test_forecast_integration_defaults_and_validation_bounds():
    assert SetupAForecastIntegrationConfig().model_dump() == {
        "enabled": False,
        "gap_threshold_vol_mult": 1.0,
        "retracement_buffer_vol_mult": 0.3,
        "max_gap_for_reversion_vol_mult": 4.0,
        "use_event_impact_for_size": True,
        "min_event_impact_score": 50,
    }
    assert SetupCForecastIntegrationConfig().model_dump() == {
        "enabled": False,
        "buffer_vol_mult": 0.5,
        "target_vol_mult": 2.5,
        "min_event_impact_score": 60,
        "vol_baseline_window_days": 30,
        "stale_forecast_fallback": "atr",
        "inverse_vol_position_size": True,
    }

    with pytest.raises(ValidationError):
        SetupAForecastIntegrationConfig(gap_threshold_vol_mult=0.0)

    with pytest.raises(ValidationError):
        SetupCForecastIntegrationConfig(stale_forecast_fallback="hold")


def test_setup_a_entry_config_defaults_and_nested_parsing():
    cfg = SetupAEntryConfig(
        llm_tuning={"enabled": True, "min_context_confidence": 0.7},
        forecast_integration={"enabled": True, "gap_threshold_vol_mult": 1.8},
    )

    assert cfg._default_config_file == "strategies/futures/setup_a_gap_reversion.yaml"
    assert cfg._default_section == "strategy.entry.params"
    assert cfg.llm_tuning.enabled is True
    assert cfg.llm_tuning.min_context_confidence == 0.7
    assert cfg.forecast_integration.enabled is True
    assert cfg.forecast_integration.gap_threshold_vol_mult == 1.8

    assert SetupAEntryConfig().model_dump() == {
        "enabled": True,
        "valid_minutes_min": 10,
        "valid_minutes_max": 90,
        "min_sp500_gap_pct": 0.5,
        "min_kr_gap_pct": 0.3,
        "retrace_min": 0.3,
        "retrace_max": 0.55,
        "stop_atr_mult": 1.5,
        "target_gap_fill_ratio": 0.9,
        "signal_ttl_minutes": 10,
        "llm_tuning": LLMTuningConfig().model_dump(),
        "forecast_integration": SetupAForecastIntegrationConfig().model_dump(),
        "daily_bias_filter_enabled": True,
        "daily_bias_min_confidence": 0.5,
        "daily_bias_refresh_minutes": 60,
    }


def test_setup_d_entry_config_defaults():
    assert (
        SetupDEntryConfig._default_config_file
        == "strategies/futures/setup_d_vwap_reversion.yaml"
    )
    assert SetupDEntryConfig._default_section == "strategy.entry.params"
    assert SetupDEntryConfig().model_dump() == {
        "enabled": True,
        "valid_minutes_min": 15,
        "no_entry_after_minutes_since_open": 345,
        "min_atr_ratio": 0.9,
        "vol_window_bars": 780,
        "vol_warmup_bars": 120,
        "vol_percentile": 90.0,
        "extreme_atr_mult": 1.8,
        "stall_buffer_atr_mult": 1.0,
        "stop_atr_mult": 1.5,
        "min_reward_risk": 1.0,
        "signal_ttl_minutes": 10,
        "range_window_bars": 15,
        "range_warmup_bars": 5,
        "extension_conf_scale": 0.3,
        "vol_conf_scale": 0.3,
        "min_confidence": 0.0,
        "reversal_confirm_enabled": False,
        "reversal_confirm_atr_mult": 0.2,
        "reversal_confirm_requires_price_turn": True,
        "long_blocked_regimes": [],
        "short_blocked_regimes": [],
    }


def test_setup_c_entry_config_defaults_and_nested_parsing():
    cfg = SetupCEntryConfig(
        llm_tuning={"enabled": True, "atr_loose_factor": 0.75},
        forecast_integration={"enabled": True, "target_vol_mult": 3.0},
    )

    assert cfg._default_config_file == "strategies/futures/setup_c_event_reaction.yaml"
    assert cfg._default_section == "strategy.entry.params"
    assert cfg.llm_tuning.enabled is True
    assert cfg.llm_tuning.atr_loose_factor == 0.75
    assert cfg.forecast_integration.enabled is True
    assert cfg.forecast_integration.target_vol_mult == 3.0

    assert SetupCEntryConfig().model_dump() == {
        "enabled": True,
        "window_minutes": 15,
        "breakout_buffer_atr_mult": 0.5,
        "target_atr_mult": 2.5,
        "signal_ttl_minutes": 30,
        "min_impact_tier": 2,
        "stop_buffer_atr_mult": 0.5,
        "no_entry_after_minutes_since_open": 360,
        "llm_tuning": LLMTuningConfig().model_dump(),
        "forecast_integration": SetupCForecastIntegrationConfig().model_dump(),
        "daily_bias_filter_enabled": True,
        "daily_bias_min_confidence": 0.5,
        "daily_bias_refresh_minutes": 60,
    }
