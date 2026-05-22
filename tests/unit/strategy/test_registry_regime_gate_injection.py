"""Tests for StrategyFactory regime_gate injection (spec 2026-05-22 P2-③ T7).

Verifies that StrategyFactory.create() reads entry.params.regime_gate from
the config dict, builds a GateConfig via regime_gate_cfg_from_yaml(), and
attaches it to the constructed adapter.  Missing section or enabled:false
→ None (adapter no-op branch).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _register_builtins():
    """Ensure builtin components are registered before each test."""
    from shared.strategy.registry import register_builtin_components
    register_builtin_components()


def _base_setup_a_cfg(regime_gate_section=None):
    """Minimal Setup A YAML cfg dict; optionally embed a regime_gate section."""
    cfg = {
        "strategy": {
            "name": "setup_a_gap_reversion",
            "asset_class": "futures",
            "enabled": True,
            "entry": {
                "type": "setup_a_gap_reversion",
                "params": {},
            },
            "exit": {"type": "rl_mppo_exit", "params": {}},
            "position": {"type": "fixed", "params": {"quantity": 1}},
        }
    }
    if regime_gate_section is not None:
        cfg["strategy"]["entry"]["params"]["regime_gate"] = regime_gate_section
    return cfg


def test_factory_injects_none_when_no_regime_gate_section():
    from shared.strategy.registry import StrategyFactory
    strat = StrategyFactory.create(_base_setup_a_cfg())
    assert strat.entry._gate_cfg is None


def test_factory_injects_none_when_section_disabled():
    from shared.strategy.registry import StrategyFactory
    strat = StrategyFactory.create(
        _base_setup_a_cfg({"enabled": False}))
    assert strat.entry._gate_cfg is None


def test_factory_injects_gate_cfg_when_enabled():
    from shared.strategy.gates.regime_gate import GateConfig
    from shared.strategy.registry import StrategyFactory
    strat = StrategyFactory.create(
        _base_setup_a_cfg({
            "enabled": True,
            "regime_percentile_max": 55.0,
        }))
    assert isinstance(strat.entry._gate_cfg, GateConfig)
    assert strat.entry._gate_cfg.regime_percentile_max == 55.0
