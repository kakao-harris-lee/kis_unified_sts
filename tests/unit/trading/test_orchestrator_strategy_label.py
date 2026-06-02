"""Tests for TradingOrchestrator._strategy_label() notification text.

Regression: the "Trading Started" Telegram message used the raw
``config.strategy_name`` which is ``None`` in multi-strategy mode (the default
for futures Setup A/C, where all enabled strategies are loaded). That rendered
a misleading "Strategy: None" line even though strategies were loaded fine.
The label must reflect the actually-loaded strategy names instead.
"""

from __future__ import annotations

from types import SimpleNamespace

from services.trading.orchestrator import TradingOrchestrator


def _bare_orchestrator(strategy_name, strategy_manager):
    """Build a TradingOrchestrator without running its heavy __init__."""
    o = TradingOrchestrator.__new__(TradingOrchestrator)
    o.config = SimpleNamespace(strategy_name=strategy_name)
    o._strategy_manager = strategy_manager
    return o


def test_label_uses_explicit_strategy_name():
    o = _bare_orchestrator("bb_reversion_15m", None)
    assert o._strategy_label() == "bb_reversion_15m"


def test_label_lists_loaded_names_in_multi_strategy_mode():
    mgr = SimpleNamespace(
        strategy_names=[
            "setup_a_gap_reversion",
            "setup_c_event_reaction",
            "bb_reversion_15m",
        ]
    )
    o = _bare_orchestrator(None, mgr)
    label = o._strategy_label()
    assert label != "None"
    assert "setup_a_gap_reversion" in label
    assert "setup_c_event_reaction" in label
    assert "bb_reversion_15m" in label


def test_label_all_enabled_before_manager_built():
    o = _bare_orchestrator(None, None)
    assert o._strategy_label() == "all enabled"


def test_label_none_loaded_when_manager_empty():
    o = _bare_orchestrator(None, SimpleNamespace(strategy_names=[]))
    assert o._strategy_label() == "none loaded"
