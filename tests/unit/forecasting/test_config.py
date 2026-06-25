"""Tests for ForecastingConfig YAML loading."""

from pathlib import Path

from shared.forecasting.config import ForecastingConfig


def test_loads_defaults_from_yaml(tmp_path: Path, monkeypatch):
    yaml_path = tmp_path / "forecasting.yaml"
    yaml_path.write_text("""
forecasting:
  publisher_enabled: true
  forecast_loop_interval_seconds: 60
  forecast_redis_ttl_seconds: 120
  har_rv:
    refit_hour_kst: 15
    refit_minute_kst: 35
    history_days: 60
    holdout_days: 7
    min_r2_oos: 0.10
  event_scorer:
    default_ttl_minutes: 30
    rule_first: true
    llm_fallback_enabled: true
    neutral_score_on_failure: 50
""")
    cfg = ForecastingConfig.from_yaml(yaml_path)
    assert cfg.publisher_enabled is True
    assert cfg.forecast_loop_interval_seconds == 60
    assert cfg.forecast_redis_ttl_seconds == 120
    assert cfg.har_rv.refit_hour_kst == 15
    assert cfg.har_rv.history_days == 60
    assert cfg.har_rv.rv_target == "raw"
    assert cfg.event_scorer.default_ttl_minutes == 30
    assert cfg.event_scorer.neutral_score_on_failure == 50


def test_har_rv_accepts_log_rv_target_from_yaml(tmp_path: Path):
    yaml_path = tmp_path / "forecasting.yaml"
    yaml_path.write_text("""
forecasting:
  har_rv:
    rv_target: log
""")
    cfg = ForecastingConfig.from_yaml(yaml_path)
    assert cfg.har_rv.rv_target == "log"


def test_env_overrides_apply(monkeypatch, tmp_path):
    yaml_path = tmp_path / "forecasting.yaml"
    yaml_path.write_text("""
forecasting:
  publisher_enabled: true
  forecast_loop_interval_seconds: 60
""")
    monkeypatch.setenv("FORECASTING_FORECAST_LOOP_INTERVAL_SECONDS", "30")
    cfg = ForecastingConfig.from_yaml(yaml_path, apply_env_overrides=True)
    assert cfg.forecast_loop_interval_seconds == 30
