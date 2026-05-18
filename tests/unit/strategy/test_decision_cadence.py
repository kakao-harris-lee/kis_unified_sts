"""Tests for DecisionCadenceGate (shared/strategy/decision_cadence.py)."""

from __future__ import annotations

from unittest.mock import MagicMock

from shared.strategy.decision_cadence import DecisionCadenceGate


class _Eng:
    def __init__(self):
        self._n = {}

    def mtf_total_appended(self, symbol, timeframe):
        return self._n.get((symbol, timeframe), 0)


def test_noop_when_timeframe_le_1():
    g = DecisionCadenceGate(timeframe_minutes=0)
    e = _Eng()
    assert g.should_decide(e, "X") is True
    g.mark_decided(e, "X")
    assert g.should_decide(e, "X") is True
    assert DecisionCadenceGate(1).should_decide(e, "X") is True


def test_fires_once_per_closed_bar_increment():
    g = DecisionCadenceGate(timeframe_minutes=15)
    e = _Eng()
    assert g.should_decide(e, "S") is False
    e._n[("S", 15)] = 1
    assert g.should_decide(e, "S") is True
    assert g.should_decide(e, "S") is True
    g.mark_decided(e, "S")
    assert g.should_decide(e, "S") is False
    e._n[("S", 15)] = 2
    assert g.should_decide(e, "S") is True
    g.mark_decided(e, "S")
    assert g.should_decide(e, "S") is False


def test_per_symbol_independent_watermarks():
    g = DecisionCadenceGate(timeframe_minutes=15)
    e = _Eng()
    e._n[("A", 15)] = 1
    assert g.should_decide(e, "A") is True
    assert g.should_decide(e, "B") is False
    g.mark_decided(e, "A")
    assert g.should_decide(e, "A") is False
    e._n[("B", 15)] = 1
    assert g.should_decide(e, "B") is True


# ---------------------------------------------------------------------------
# Live StrategyManager wiring test — verifies gate consulted via helper
# ---------------------------------------------------------------------------


class _FakeStrategy:
    """Spy strategy that counts check_entry calls."""

    def __init__(self, name: str = "test_strategy", timeframe_minutes: int = 15):
        self.name = name
        self.entry = MagicMock()
        self.entry.config = MagicMock()
        self.entry.config.timeframe_minutes = timeframe_minutes
        self.check_entry_calls = 0

    async def check_entry(self, context):  # noqa: ARG002
        self.check_entry_calls += 1
        return None

    async def check_exit(self, context):  # noqa: ARG002
        return (False, None)

    @property
    def required_indicators(self):
        return []


def test_manager_gate_helper_suppresses_sub_n_min_calls():
    """Verify the StrategyManager._gate_allows helper suppresses calls
    when no new closed N-min bar has appeared, and fires them when one has.
    Uses __new__ to bypass strategy loading from disk.
    """
    from services.trading.strategy_manager import StrategyManager, StrategyManagerConfig

    cfg = StrategyManagerConfig(cost_filter_enabled=False)
    # Construct with no strategies loaded from disk
    manager = StrategyManager.__new__(StrategyManager)
    manager.asset_class = "futures"
    manager.config = cfg
    manager.strategies = {}
    manager._recent_signals = {}
    manager.cost_filter = None
    manager._last_cycle_log_time = 0.0
    manager._cadence_gates = {}
    manager._exit_cadence_gates = {}
    manager._indicator_engine = None
    from services.trading.llm_context_provider import LLMContextProvider
    manager._llm_context_provider = LLMContextProvider.__new__(LLMContextProvider)
    manager._llm_context_provider._context = None
    manager._llm_context_provider.get_context = lambda: None

    # Add a 15m strategy manually (triggers _rebuild_cadence_gates)
    strategy = _FakeStrategy("bb_reversion_15m", timeframe_minutes=15)
    manager.add_strategy(strategy)

    # Engine fake: 0 closed bars → gate suppresses
    engine = _Eng()
    symbol = "101S6000"
    manager.set_indicator_engine(engine)

    # Should NOT decide (0 closed bars → gate blocks)
    assert manager._gate_allows(strategy.name, symbol) is False

    # Simulate 1 closed 15m bar
    engine._n[(symbol, 15)] = 1
    assert manager._gate_allows(strategy.name, symbol) is True

    # Mark decided
    manager._gate_mark_decided(strategy.name, symbol)
    assert manager._gate_allows(strategy.name, symbol) is False

    # New bar: should fire again
    engine._n[(symbol, 15)] = 2
    assert manager._gate_allows(strategy.name, symbol) is True

    # Exit gate is independent — should also fire on same bar boundary
    assert manager._gate_allows(strategy.name, symbol, for_exit=True) is True
    manager._gate_mark_decided(strategy.name, symbol, for_exit=True)
    assert manager._gate_allows(strategy.name, symbol, for_exit=True) is False
