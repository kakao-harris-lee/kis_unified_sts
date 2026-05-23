def test_yaml_enabled_false_returns_none():
    from shared.strategy.gates.regime_gate import regime_gate_cfg_from_yaml
    assert regime_gate_cfg_from_yaml({"enabled": False}) is None


def test_yaml_missing_section_returns_none():
    from shared.strategy.gates.regime_gate import regime_gate_cfg_from_yaml
    assert regime_gate_cfg_from_yaml(None) is None
    assert regime_gate_cfg_from_yaml({}) is None


def test_yaml_enabled_true_builds_cfg_with_defaults():
    from shared.strategy.gates.regime_gate import (
        GateConfig,
        regime_gate_cfg_from_yaml,
    )
    cfg = regime_gate_cfg_from_yaml({"enabled": True})
    assert isinstance(cfg, GateConfig)
    # Defaults match config/gates/regime_gate_default.yaml (T12: 80→60)
    assert cfg.regime_percentile_max == 60.0
    assert cfg.impact_score_max == 70
    assert cfg.event_window_minutes == 15
    assert cfg.require_overnight_us_direction is False
    assert cfg.permissive_on_missing is True


def test_yaml_overrides_defaults():
    from shared.strategy.gates.regime_gate import regime_gate_cfg_from_yaml
    cfg = regime_gate_cfg_from_yaml({
        "enabled": True,
        "regime_percentile_max": 50.0,
        "impact_score_max": 80,
        "event_window_minutes": 20,
        "require_overnight_us_direction": True,
        "permissive_on_missing": False,
    })
    assert cfg.regime_percentile_max == 50.0
    assert cfg.impact_score_max == 80
    assert cfg.event_window_minutes == 20
    assert cfg.require_overnight_us_direction is True
    assert cfg.permissive_on_missing is False
