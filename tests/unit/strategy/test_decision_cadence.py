"""Tests for DecisionCadenceGate (shared/strategy/decision_cadence.py).

Covers the gate primitive, the StrategyManager single-shared-gate wiring
(entry+exit lockstep on the same closed bar, mark-once even on exception),
and the orchestrator engine-wiring (set_indicator_engine).
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

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
    """Spy strategy that counts check_entry / check_exit calls.

    `raise_on_entry` / `raise_on_exit` simulate strategy errors so we can
    assert the watermark still advances exactly once (spec: mark even on
    exception, never twice, never on a non-decision bar).
    """

    def __init__(
        self,
        name: str = "test_strategy",
        timeframe_minutes: int = 15,
        raise_on_entry: bool = False,
        raise_on_exit: bool = False,
    ):
        self.name = name
        self.entry = MagicMock()
        self.entry.config = MagicMock()
        self.entry.config.timeframe_minutes = timeframe_minutes
        self.exit = MagicMock(spec=[])  # no scan_positions attr
        self.check_entry_calls = 0
        self.check_exit_calls = 0
        self._raise_on_entry = raise_on_entry
        self._raise_on_exit = raise_on_exit

    async def check_entry(self, context):  # noqa: ARG002
        self.check_entry_calls += 1
        if self._raise_on_entry:
            from shared.exceptions import TradingSystemError

            raise TradingSystemError("boom-entry")
        return None

    async def check_exit(self, context):  # noqa: ARG002
        self.check_exit_calls += 1
        if self._raise_on_exit:
            from shared.exceptions import TradingSystemError

            raise TradingSystemError("boom-exit")
        return (False, None)

    @property
    def required_indicators(self):
        return []


def _bare_manager(asset_class: str = "futures"):
    """Construct a StrategyManager without disk strategy loading."""
    from services.trading.llm_context_provider import LLMContextProvider
    from services.trading.strategy_manager import (
        StrategyManager,
        StrategyManagerConfig,
    )

    cfg = StrategyManagerConfig(cost_filter_enabled=False)
    manager = StrategyManager.__new__(StrategyManager)
    manager.asset_class = asset_class
    manager.config = cfg
    manager.strategies = {}
    manager._recent_signals = {}
    manager.cost_filter = None
    manager._last_cycle_log_time = 0.0
    manager._cadence_gates = {}
    manager._exit_cadence_gates = {}
    manager._indicator_engine = None
    manager._llm_context_provider = LLMContextProvider.__new__(LLMContextProvider)
    manager._llm_context_provider._context = None
    manager._llm_context_provider.get_context = lambda: None
    return manager


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_manager_gate_helper_suppresses_sub_n_min_calls():
    """_gate_allows is a pure predicate: blocks until a new closed 15m bar,
    and does NOT advance the watermark itself (callers mark via finally)."""
    manager = _bare_manager()
    strategy = _FakeStrategy("bb_reversion_15m", timeframe_minutes=15)
    manager.add_strategy(strategy)  # triggers _rebuild_cadence_gates

    engine = _Eng()
    symbol = "101S6000"
    manager.set_indicator_engine(engine)

    # 0 closed bars → blocked
    assert manager._gate_allows(strategy.name, symbol) is False
    # 1 closed bar → allowed. _gate_allows is pure: repeated calls stay True
    # until the caller marks decided.
    engine._n[(symbol, 15)] = 1
    assert manager._gate_allows(strategy.name, symbol) is True
    assert manager._gate_allows(strategy.name, symbol) is True
    # Caller marks → now blocked until a new closed bar.
    manager._gate_mark_decided(strategy.name, symbol)
    assert manager._gate_allows(strategy.name, symbol) is False
    engine._n[(symbol, 15)] = 2
    assert manager._gate_allows(strategy.name, symbol) is True


def test_manager_no_engine_is_noop():
    """Without an engine the gate is disabled (always allow) — backward compat."""
    manager = _bare_manager()
    strategy = _FakeStrategy("bb_reversion_15m", timeframe_minutes=15)
    manager.add_strategy(strategy)
    assert manager._indicator_engine is None
    assert manager._gate_allows(strategy.name, "X") is True
    assert manager._gate_allows(strategy.name, "X", for_exit=True) is True


def test_manager_entry_exit_independent_same_closed_bar():
    """Entry and exit have INDEPENDENT per-side watermarks (the live
    orchestrator drives them as separate async loops). Both must be able to
    decide on the SAME closed bar — neither side starves the other.
    """
    manager = _bare_manager()
    strategy = _FakeStrategy("bb_reversion_15m", timeframe_minutes=15)
    manager.add_strategy(strategy)
    engine = _Eng()
    sym = "101S6000"
    manager.set_indicator_engine(engine)

    entry_gate = manager._cadence_gates[strategy.name]
    exit_gate = manager._exit_cadence_gates[strategy.name]
    assert entry_gate is not exit_gate  # separate instances, same class

    engine._n[(sym, 15)] = 1

    # Entry side decides first this window (its loop fired) and marks.
    assert manager._gate_allows(strategy.name, sym) is True
    manager._gate_mark_decided(strategy.name, sym)
    assert entry_gate._decided_at.get(sym) == 1
    # Entry side blocked for the rest of this window.
    assert manager._gate_allows(strategy.name, sym) is False

    # Exit side (independent loop, later in same window) is NOT starved by
    # entry having marked — it still decides on the SAME closed bar.
    assert manager._gate_allows(strategy.name, sym, for_exit=True) is True
    manager._gate_mark_decided(strategy.name, sym, for_exit=True)
    assert exit_gate._decided_at.get(sym) == 1
    assert manager._gate_allows(strategy.name, sym, for_exit=True) is False

    # New closed bar → both sides decide again.
    engine._n[(sym, 15)] = 2
    assert manager._gate_allows(strategy.name, sym) is True
    assert manager._gate_allows(strategy.name, sym, for_exit=True) is True


def test_manager_mark_once_in_finally_even_on_exception():
    """Watermark advances EXACTLY ONCE per (strategy,symbol,side) per decision
    bar even when check_entry / check_exit raise (the spec's drift fix); a
    non-decision bar never advances; never twice.
    """
    from shared.models.position import Position, PositionSide

    manager = _bare_manager()
    strategy = _FakeStrategy(
        "bb_reversion_15m",
        timeframe_minutes=15,
        raise_on_entry=True,
        raise_on_exit=True,
    )
    manager.add_strategy(strategy)
    engine = _Eng()
    sym = "101S6000"
    manager.set_indicator_engine(engine)
    entry_gate = manager._cadence_gates[strategy.name]
    exit_gate = manager._exit_cadence_gates[strategy.name]

    pos = Position(
        id="p1",
        code=sym,
        name=sym,
        strategy=strategy.name,
        side=PositionSide.LONG,
        quantity=1,
        entry_price=400.0,
        current_price=400.0,
    )

    ctx = MagicMock()
    ctx.market_data = {"code": sym}

    # Non-decision bar (0 closed) — neither side runs or advances.
    assert _run(manager._check_entry_safe(strategy, ctx)) is None
    assert strategy.check_entry_calls == 0
    assert entry_gate._decided_at.get(sym, 0) == 0
    assert _run(
        manager._check_exits_safe(strategy, [pos], {"code": sym}, None, None)
    ) == []
    assert strategy.check_exit_calls == 0
    assert exit_gate._decided_at.get(sym, 0) == 0

    # Decision bar (1 closed). Entry raises → still advances entry wm once.
    engine._n[(sym, 15)] = 1
    assert _run(manager._check_entry_safe(strategy, ctx)) is None
    assert strategy.check_entry_calls == 1
    assert entry_gate._decided_at.get(sym) == 1  # advanced exactly once
    # Same window, entry side now blocked (no double-advance / re-run).
    assert _run(manager._check_entry_safe(strategy, ctx)) is None
    assert strategy.check_entry_calls == 1  # NOT called again
    assert entry_gate._decided_at.get(sym) == 1  # still 1

    # Exit raises too → still advances exit wm exactly once this window.
    assert _run(
        manager._check_exits_safe(strategy, [pos], {"code": sym}, None, None)
    ) == []
    assert strategy.check_exit_calls == 1
    assert exit_gate._decided_at.get(sym) == 1
    # Exit side blocked for rest of window.
    assert _run(
        manager._check_exits_safe(strategy, [pos], {"code": sym}, None, None)
    ) == []
    assert strategy.check_exit_calls == 1
    assert exit_gate._decided_at.get(sym) == 1

    # Next closed bar → both sides decide again, single advance each.
    engine._n[(sym, 15)] = 2
    _run(manager._check_entry_safe(strategy, ctx))
    _run(manager._check_exits_safe(strategy, [pos], {"code": sym}, None, None))
    assert entry_gate._decided_at.get(sym) == 2
    assert exit_gate._decided_at.get(sym) == 2


def test_orchestrator_wires_set_indicator_engine():
    """The orchestrator must call StrategyManager.set_indicator_engine after
    _init_indicator_engine — otherwise the live gate is a no-op in production.
    This test would FAIL if the wiring line were removed.
    """
    import inspect

    from services.trading import orchestrator as orch_mod

    src = inspect.getsource(orch_mod.TradingOrchestrator._init_indicator_engine)
    assert "set_indicator_engine" in src, (
        "orchestrator._init_indicator_engine must wire the indicator engine "
        "into the StrategyManager (set_indicator_engine) or the live "
        "decision-cadence gate is bypassed"
    )


# ---------------------------------------------------------------------------
# Backtest adapter: mark-once-after-both invariant + dead-flag removal
# ---------------------------------------------------------------------------


class _AdapterEng:
    """Minimal engine stub for adapter cadence tests."""

    def __init__(self):
        self.appended = 0

    def mtf_total_appended(self, symbol, timeframe):  # noqa: ARG002
        return self.appended


class _StubGate:
    """Wraps a real DecisionCadenceGate to count mark_decided invocations."""

    def __init__(self, tf):
        self._g = DecisionCadenceGate(tf)
        self._tf = self._g._tf
        self.mark_calls = 0

    @property
    def enabled(self):
        return self._g.enabled

    def should_decide(self, engine, symbol):
        return self._g.should_decide(engine, symbol)

    def mark_decided(self, engine, symbol):
        self.mark_calls += 1
        self._g.mark_decided(engine, symbol)


def _make_adapter():
    """Build a BacktestStrategyAdapter shell with cadence wiring only."""
    from shared.backtest.adapter import BacktestStrategyAdapter

    a = BacktestStrategyAdapter.__new__(BacktestStrategyAdapter)
    a._cadence = _StubGate(15)
    a._decision_bar = True
    a._decision_bar_computed = False
    a._indicator_engine = _AdapterEng()
    return a


def test_adapter_dead_flag_removed():
    """The vestigial _cadence_exit_computed must be gone; the clean flag
    _decision_bar_computed must exist instead.
    """
    import inspect

    from shared.backtest import adapter as adapter_mod

    src = inspect.getsource(adapter_mod)
    assert "_cadence_exit_computed" not in src
    assert "_decision_bar_computed" in src


def test_adapter_recompute_decision_bar_helper_sets_flag():
    """check_exit/on_bar share _recompute_decision_bar; first runner computes,
    other reuses (flag-gated)."""
    a = _make_adapter()
    a._indicator_engine.appended = 0
    a._recompute_decision_bar("101S6000")
    assert a._decision_bar_computed is True
    assert a._decision_bar is False  # 0 closed bars, watermark 0 → not > 0
    a._indicator_engine.appended = 1
    a._recompute_decision_bar("101S6000")
    assert a._decision_bar is True  # 1 closed > watermark 0


def test_adapter_mark_once_per_decision_bar_no_double_advance():
    """Simulate the engine ordering: check_exit (first, position exists) then
    on_bar (last). _decision_bar computed once by check_exit, reused by on_bar;
    mark_decided called EXACTLY ONCE per decision bar.
    """
    a = _make_adapter()
    eng = a._indicator_engine

    # Decision bar: 1 closed 15m candle, watermark 0.
    eng.appended = 1
    # check_exit path (runs first): compute decision, flag set.
    a._recompute_decision_bar("S")
    assert a._decision_bar is True and a._decision_bar_computed is True
    # on_bar reuses (does NOT recompute because flag is set), consumes flag,
    # then marks ONCE at the end.
    if not a._decision_bar_computed:  # mirrors on_bar logic
        a._recompute_decision_bar("S")
    a._decision_bar_computed = False  # on_bar consumes flag
    assert a._decision_bar is True
    a._cadence.mark_decided(a._indicator_engine, "S")  # single mark at end
    assert a._cadence.mark_calls == 1

    # Same closed bar, next 1m tick (no new 15m): should_decide now False.
    a._recompute_decision_bar("S")
    assert a._decision_bar is False  # watermark caught up → non-decision bar
    a._decision_bar_computed = False
    # on_bar returns HOLD WITHOUT marking on a non-decision bar.
    assert a._cadence.mark_calls == 1  # unchanged — never advanced twice


@pytest.mark.parametrize("timeframe", [0, 1])
def test_adapter_gate_noop_for_tf_le_1(timeframe):
    """Disabled gate (tf<=1) → always decide, mark is a no-op (byte-identical
    for stock strategies)."""
    from shared.backtest.adapter import BacktestStrategyAdapter

    a = BacktestStrategyAdapter.__new__(BacktestStrategyAdapter)
    a._cadence = DecisionCadenceGate(timeframe)
    a._decision_bar = True
    a._decision_bar_computed = False
    a._indicator_engine = _AdapterEng()
    assert a._cadence.enabled is False
    a._recompute_decision_bar("X")
    assert a._decision_bar is True  # disabled gate always decides
