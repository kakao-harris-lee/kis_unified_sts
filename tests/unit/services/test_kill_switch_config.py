"""Tests for services/kill_switch/config.py — KillSwitchConfig loader."""

import textwrap

import pytest

from services.kill_switch.config import KillSwitchConfig


def test_loads_default_yaml():
    """Live ``config/kill_switch.yaml`` should round-trip into a config object."""
    cfg = KillSwitchConfig.from_yaml()
    assert cfg.enabled is True
    assert cfg.check_interval_seconds == 30.0
    assert cfg.sentinel_path == "/var/run/kis_kill_switch.tripped"
    assert cfg.conditions.daily_loss.limit_pct == 0.03
    assert cfg.conditions.weekly_loss.limit_pct == 0.07
    assert cfg.conditions.consecutive_losses.threshold == 6
    assert cfg.conditions.api_error_rate_5min.threshold == 0.2
    assert cfg.conditions.news_pipeline_lag_seconds.threshold == 300
    assert cfg.conditions.clickhouse_insert_fail_rate.threshold == 0.1


def test_loads_custom_yaml(tmp_path):
    custom = tmp_path / "kill_switch.yaml"
    custom.write_text(textwrap.dedent("""
            kill_switch:
              enabled: false
              check_interval_seconds: 60
              sentinel_path: "/tmp/test.tripped"
              conditions:
                daily_loss:
                  enabled: true
                  limit_pct: 0.05
                weekly_loss:
                  enabled: false
                  limit_pct: 0.10
                consecutive_losses:
                  enabled: true
                  threshold: 4
            """).strip())
    cfg = KillSwitchConfig.from_yaml(str(custom))
    assert cfg.enabled is False
    assert cfg.check_interval_seconds == 60.0
    assert cfg.sentinel_path == "/tmp/test.tripped"
    assert cfg.conditions.daily_loss.limit_pct == 0.05
    assert cfg.conditions.weekly_loss.enabled is False
    assert cfg.conditions.consecutive_losses.threshold == 4


def test_check_interval_must_be_positive():
    with pytest.raises(Exception):
        KillSwitchConfig(check_interval_seconds=0)
