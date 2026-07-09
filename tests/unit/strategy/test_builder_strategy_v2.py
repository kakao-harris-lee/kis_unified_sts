"""Schema v2 runtime-bridge tests: signal direction, side-aware exits,
gate hooks (regime/cooldown), and named exit-primitive composition."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from shared.exceptions import ConfigurationError
from shared.models.signal import ExitReason
from shared.strategy.base import EntryContext, ExitContext
from shared.strategy.entry.builder_strategy import (
    BuilderStrategyConfig,
    BuilderStrategyEntry,
)
from shared.strategy.exit.builder_strategy_exit import (
    BuilderStrategyExit,
    BuilderStrategyExitConfig,
)
from shared.strategy.exit.composite import FirstTriggerExit


def _ohlcv(closes: list[float]) -> list[dict[str, float]]:
    return [
        {"open": c, "high": c + 1.0, "low": c - 1.0, "close": c, "volume": 1000.0}
        for c in closes
    ]


# Monotonic rise -> RSI ~100; monotonic fall -> RSI ~0.
_UPTREND = _ohlcv([100.0 + i for i in range(40)])
_DOWNTREND = _ohlcv([100.0 - i for i in range(40)])


def _rsi_condition(operator: str, threshold: float) -> dict:
    return {
        "left": {
            "type": "indicator",
            "indicator_alias": "rsi",
            "indicator_output": "value",
        },
        "operator": operator,
        "right": {"type": "value", "value": threshold},
    }


def _symmetric_state(**extra) -> dict:
    """Futures state: long when RSI < 30 (dip), short when RSI > 70 (rip)."""
    state = {
        "metadata": {"id": "sym_v2", "name": "Symmetric V2"},
        "asset_class": "futures",
        "indicators": [
            {"indicator_id": "rsi", "alias": "rsi", "params": {}, "output": "value"}
        ],
        "entry": {
            "logic": "AND",
            "conditions": [_rsi_condition("less_than", 30.0)],
        },
        "entry_short": {
            "logic": "AND",
            "conditions": [_rsi_condition("greater_than", 70.0)],
        },
        "exit": {"logic": "AND", "conditions": []},
    }
    state.update(extra)
    return state


def _entry_ctx(rows: list[dict], code: str = "101S6000", **kwargs) -> EntryContext:
    return EntryContext(
        market_data={"code": code, "close": 400.0},
        indicators={"ohlcv": rows},
        timestamp=kwargs.pop("timestamp", datetime(2026, 7, 8, 1, 0, tzinfo=UTC)),
        **kwargs,
    )


# --- entry direction (futures long/short symmetry) ------------------------


@pytest.mark.asyncio
async def test_entry_emits_short_signal_from_entry_short_group() -> None:
    entry = BuilderStrategyEntry(
        BuilderStrategyConfig(builder_state=_symmetric_state())
    )
    signal = await entry.generate(_entry_ctx(_UPTREND))  # RSI high -> short
    assert signal is not None
    assert signal.metadata["signal_direction"] == "short"
    assert signal.metadata["matched_group"] == "entry_short"


@pytest.mark.asyncio
async def test_entry_emits_long_signal_from_entry_group() -> None:
    entry = BuilderStrategyEntry(
        BuilderStrategyConfig(builder_state=_symmetric_state())
    )
    signal = await entry.generate(_entry_ctx(_DOWNTREND))  # RSI low -> long
    assert signal is not None
    assert signal.metadata["signal_direction"] == "long"
    assert signal.metadata["matched_group"] == "entry"


@pytest.mark.asyncio
async def test_entry_no_signal_when_neither_group_matches() -> None:
    entry = BuilderStrategyEntry(
        BuilderStrategyConfig(builder_state=_symmetric_state())
    )
    # Alternating closes keep RSI mid-range: neither <30 nor >70.
    flat = _ohlcv([100.0 + (1.0 if i % 2 else -1.0) for i in range(40)])
    assert await entry.generate(_entry_ctx(flat)) is None


@pytest.mark.asyncio
async def test_entry_long_group_wins_when_both_pass() -> None:
    # Long: RSI > 10 (passes in an uptrend), short: RSI > 70 (also passes).
    state = _symmetric_state(
        entry={"logic": "AND", "conditions": [_rsi_condition("greater_than", 10.0)]}
    )
    entry = BuilderStrategyEntry(BuilderStrategyConfig(builder_state=state))
    signal = await entry.generate(_entry_ctx(_UPTREND))
    assert signal is not None
    assert signal.metadata["signal_direction"] == "long"
    assert signal.metadata["matched_group"] == "entry"


@pytest.mark.asyncio
async def test_entry_without_entry_short_stays_long_only() -> None:
    state = _symmetric_state()
    state.pop("entry_short")
    entry = BuilderStrategyEntry(BuilderStrategyConfig(builder_state=state))
    assert await entry.generate(_entry_ctx(_UPTREND)) is None  # no short group
    signal = await entry.generate(_entry_ctx(_DOWNTREND))
    assert signal is not None
    assert signal.metadata["signal_direction"] == "long"


# --- schema cooldown gate -------------------------------------------------


@pytest.mark.asyncio
async def test_schema_cooldown_blocks_reentry() -> None:
    state = _symmetric_state(gates={"cooldown_seconds": 1800})
    entry = BuilderStrategyEntry(
        BuilderStrategyConfig(builder_state=state, cooldown_seconds=0)
    )
    assert entry.effective_cooldown_seconds == 1800
    first_ts = datetime(2026, 7, 8, 1, 0, tzinfo=UTC)
    signal = await entry.generate(_entry_ctx(_DOWNTREND, timestamp=first_ts))
    assert signal is not None
    # 10 minutes later: still inside the 30-minute schema cooldown.
    blocked = await entry.generate(
        _entry_ctx(_DOWNTREND, timestamp=first_ts + timedelta(minutes=10))
    )
    assert blocked is None
    # 31 minutes later: cooldown expired.
    allowed = await entry.generate(
        _entry_ctx(_DOWNTREND, timestamp=first_ts + timedelta(minutes=31))
    )
    assert allowed is not None


def test_effective_cooldown_takes_the_maximum() -> None:
    state = _symmetric_state(gates={"cooldown_seconds": 60})
    entry = BuilderStrategyEntry(
        BuilderStrategyConfig(builder_state=state, cooldown_seconds=600)
    )
    # Deploy-time param (600) is larger than the schema gate (60) -> 600 wins.
    assert entry.effective_cooldown_seconds == 600


# --- regime gate hook -------------------------------------------------------


@pytest.mark.asyncio
async def test_regime_gate_blocks_signal(monkeypatch) -> None:
    from shared.strategy.entry import builder_strategy as module
    from shared.strategy.gates.regime_gate import GateConfig

    entry = BuilderStrategyEntry(
        BuilderStrategyConfig(builder_state=_symmetric_state()),
        gate_cfg=GateConfig(),
    )
    monkeypatch.setattr(module, "acquire_infra_clients", lambda: (object(), None))
    seen: dict = {}

    def _fake_gate(**kwargs):
        seen.update(kwargs)
        return True  # blocked

    monkeypatch.setattr(module, "apply_regime_gate", _fake_gate)
    assert await entry.generate(_entry_ctx(_UPTREND)) is None
    # Direction must flow into the gate (short candidate here).
    assert seen["decision_signal"].metadata["signal_direction"] == "short"


@pytest.mark.asyncio
async def test_regime_gate_permissive_without_infra(monkeypatch) -> None:
    from shared.strategy.entry import builder_strategy as module
    from shared.strategy.gates.regime_gate import GateConfig

    entry = BuilderStrategyEntry(
        BuilderStrategyConfig(builder_state=_symmetric_state()),
        gate_cfg=GateConfig(),
    )
    monkeypatch.setattr(module, "acquire_infra_clients", lambda: (None, None))
    signal = await entry.generate(_entry_ctx(_UPTREND))
    assert signal is not None  # PERMISSIVE on missing infra


def test_factory_attaches_schema_declared_regime_gate() -> None:
    from shared.strategy.registry import StrategyFactory, register_builtin_components

    register_builtin_components()
    state = _symmetric_state(
        gates={"regime_gate": {"enabled": True, "regime_percentile_max": 55.0}}
    )
    strategy = StrategyFactory.create(
        {
            "strategy": {
                "name": "sym_v2",
                "asset_class": "futures",
                "entry": {"type": "builder_v1", "params": {"builder_state": state}},
                "exit": {
                    "type": "builder_v1_exit",
                    "params": {"builder_state": state},
                },
                "position": {"type": "fixed", "params": {}},
            }
        }
    )
    gate_cfg = strategy.entry._gate_cfg
    assert gate_cfg is not None
    assert gate_cfg.regime_percentile_max == 55.0


def test_factory_entry_params_regime_gate_overrides_schema_gate() -> None:
    from shared.strategy.registry import StrategyFactory, register_builtin_components

    register_builtin_components()
    state = _symmetric_state(
        gates={"regime_gate": {"enabled": True, "regime_percentile_max": 55.0}}
    )
    strategy = StrategyFactory.create(
        {
            "strategy": {
                "name": "sym_v2",
                "asset_class": "futures",
                "entry": {
                    "type": "builder_v1",
                    "params": {
                        "builder_state": state,
                        "regime_gate": {"enabled": True, "regime_percentile_max": 42.0},
                    },
                },
                "exit": {
                    "type": "builder_v1_exit",
                    "params": {"builder_state": state},
                },
                "position": {"type": "fixed", "params": {}},
            }
        }
    )
    assert strategy.entry._gate_cfg is not None
    assert strategy.entry._gate_cfg.regime_percentile_max == 42.0


def test_factory_disabled_schema_gate_attaches_nothing() -> None:
    from shared.strategy.registry import StrategyFactory, register_builtin_components

    register_builtin_components()
    state = _symmetric_state(gates={"regime_gate": {"enabled": False}})
    strategy = StrategyFactory.create(
        {
            "strategy": {
                "name": "sym_v2",
                "asset_class": "futures",
                "entry": {"type": "builder_v1", "params": {"builder_state": state}},
                "exit": {
                    "type": "builder_v1_exit",
                    "params": {"builder_state": state},
                },
                "position": {"type": "fixed", "params": {}},
            }
        }
    )
    assert strategy.entry._gate_cfg is None


# --- side-aware exit (sign symmetry) ---------------------------------------


class _Pos:
    """Minimal Position-like stub with a direction."""

    def __init__(
        self,
        code: str,
        entry_price: float,
        quantity: int = 1,
        side: str = "long",
    ):
        self.code = code
        self.name = ""
        self.id = "pos_1"
        self.entry_price = entry_price
        self.current_price = entry_price
        self.quantity = quantity
        self.side = side


def _stock_state() -> dict:
    return {
        "metadata": {"id": "exit_v2", "name": "Exit V2"},
        "asset_class": "stock",
        "indicators": [],
        "entry": {"logic": "AND", "conditions": []},
        "exit": {"logic": "AND", "conditions": []},
    }


def _exit(**config) -> BuilderStrategyExit:
    defaults = {
        "builder_state": _stock_state(),
        "stop_loss_pct": 0.0,
        "take_profit_pct": 0.0,
        "trailing_stop_pct": 0.0,
    }
    defaults.update(config)
    return BuilderStrategyExit(BuilderStrategyExitConfig(**defaults))


async def _step(exit_strat: BuilderStrategyExit, pos: _Pos, price: float):
    ctx = ExitContext(
        position=pos,
        market_data={"close": price},
        indicators={},
        timestamp=datetime(2026, 7, 8, 1, 0, tzinfo=UTC),
    )
    return await exit_strat.should_exit(ctx)


@pytest.mark.asyncio
async def test_short_stop_loss_fires_when_price_rises() -> None:
    exit_strat = _exit(stop_loss_pct=5.0)
    pos = _Pos("005930", entry_price=10000.0, side="short")
    triggered, signal = await _step(exit_strat, pos, 10600.0)  # -6% for a short
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.profit_pct == pytest.approx(-0.06)
    assert signal.profit_amount == pytest.approx(-600.0)


@pytest.mark.asyncio
async def test_short_take_profit_fires_when_price_falls() -> None:
    exit_strat = _exit(take_profit_pct=10.0)
    pos = _Pos("005930", entry_price=10000.0, side="short")
    triggered, signal = await _step(exit_strat, pos, 8900.0)  # +11% for a short
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.TARGET_REACHED
    assert signal.profit_pct == pytest.approx(0.11)
    assert signal.profit_amount == pytest.approx(1100.0)


@pytest.mark.asyncio
async def test_short_and_long_pnl_are_sign_symmetric() -> None:
    # The same 5% adverse move triggers the stop for both directions.
    for side, adverse_price in (("long", 9400.0), ("short", 10600.0)):
        exit_strat = _exit(stop_loss_pct=5.0)
        pos = _Pos("005930", entry_price=10000.0, side=side)
        triggered, signal = await _step(exit_strat, pos, adverse_price)
        assert triggered, side
        assert signal is not None
        assert signal.profit_pct == pytest.approx(-0.06)


@pytest.mark.asyncio
async def test_short_trailing_stop_tracks_trough_and_fires_on_retrace() -> None:
    exit_strat = _exit(trailing_stop_pct=3.0)
    pos = _Pos("005930", entry_price=10000.0, side="short")
    # Fall to 9000 (trough; 3% ceiling = 9270) -> hold.
    triggered, _ = await _step(exit_strat, pos, 9000.0)
    assert not triggered
    # Retrace up to 9300 (>= 9270) -> trailing stop fires, still in profit.
    triggered, signal = await _step(exit_strat, pos, 9300.0)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.TRAILING_STOP
    assert signal.profit_pct == pytest.approx(0.07)


@pytest.mark.asyncio
async def test_short_trailing_stop_holds_within_band() -> None:
    exit_strat = _exit(trailing_stop_pct=3.0)
    pos = _Pos("005930", entry_price=10000.0, side="short")
    await _step(exit_strat, pos, 9000.0)  # trough=9000, ceiling=9270
    triggered, signal = await _step(exit_strat, pos, 9200.0)  # inside the band
    assert not triggered
    assert signal is None


@pytest.mark.asyncio
async def test_short_trailing_stop_not_armed_before_profit() -> None:
    # Price never falls below entry -> trailing must not fire (stop-loss's job).
    exit_strat = _exit(trailing_stop_pct=3.0)
    pos = _Pos("005930", entry_price=10000.0, side="short")
    triggered, signal = await _step(exit_strat, pos, 10400.0)  # -4%, SL off
    assert not triggered
    assert signal is None


@pytest.mark.asyncio
async def test_short_trailing_stop_seeds_from_position_lowest_price() -> None:
    # Restart recovery, mirrored: lowest_price restored below entry arms the
    # trailing stop immediately for a short.
    exit_strat = _exit(trailing_stop_pct=3.0)
    pos = _Pos("005930", entry_price=10000.0, side="short")
    pos.lowest_price = 9000.0  # trough before restart; ceiling = 9270
    triggered, signal = await _step(exit_strat, pos, 9300.0)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.TRAILING_STOP


@pytest.mark.asyncio
async def test_long_position_with_enum_side_behaves_as_before() -> None:
    from shared.models.position import PositionSide

    exit_strat = _exit(stop_loss_pct=5.0)
    pos = _Pos("005930", entry_price=10000.0, side=PositionSide.LONG)
    triggered, signal = await _step(exit_strat, pos, 9400.0)  # -6% long
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.profit_pct == pytest.approx(-0.06)


@pytest.mark.asyncio
async def test_futures_hard_stop_cap_is_side_symmetric() -> None:
    # Futures cap (3%) must fire for a SHORT when price RISES beyond the cap.
    state = _stock_state()
    state["asset_class"] = "futures"
    exit_strat = _exit(builder_state=state, stop_loss_pct=10.0)
    pos = _Pos("101S6000", entry_price=400.0, side="short")
    ctx = ExitContext(
        position=pos,
        market_data={"close": 416.0},  # +4% price -> -4% for the short
        indicators={},
        timestamp=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),  # 10:00 KST intraday
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.metadata["note"] == "futures_hard_stop"


# --- named exit primitive composition ---------------------------------------


def _factory_config(state: dict) -> dict:
    return {
        "strategy": {
            "name": state["metadata"]["id"],
            "asset_class": state["asset_class"],
            "entry": {"type": "builder_v1", "params": {"builder_state": state}},
            "exit": {"type": "builder_v1_exit", "params": {"builder_state": state}},
            "position": {"type": "fixed", "params": {}},
        }
    }


def test_factory_composes_named_exit_primitive() -> None:
    from shared.strategy.registry import StrategyFactory, register_builtin_components

    register_builtin_components()
    state = _stock_state()
    state["exit_primitive"] = {
        "primitive": "atr_dynamic",
        "params": {"atr_period": 10},
    }
    strategy = StrategyFactory.create(_factory_config(state))
    assert isinstance(strategy.exit, FirstTriggerExit)
    children = strategy.exit.children
    assert len(children) == 2
    assert isinstance(children[0], BuilderStrategyExit)  # declarative first
    assert children[1].__class__.__name__ == "ATRDynamicExit"
    assert children[1].config.atr_period == 10


def test_factory_rejects_unknown_exit_primitive() -> None:
    from shared.strategy.registry import StrategyFactory, register_builtin_components

    register_builtin_components()
    state = _stock_state()
    state["exit_primitive"] = {"primitive": "not_a_real_exit", "params": {}}
    with pytest.raises(ConfigurationError, match="Available"):
        StrategyFactory.create(_factory_config(state))


def test_factory_rejects_asset_restricted_exit_primitive() -> None:
    from shared.strategy.registry import StrategyFactory, register_builtin_components

    register_builtin_components()
    state = _symmetric_state()
    state["exit_primitive"] = {"primitive": "three_stage", "params": {}}
    with pytest.raises(ConfigurationError, match="three_stage"):
        StrategyFactory.create(_factory_config(state))


@pytest.mark.asyncio
async def test_composite_exit_first_trigger_wins() -> None:
    exit_a = _exit(stop_loss_pct=5.0)
    exit_b = _exit(stop_loss_pct=2.0)
    composite = FirstTriggerExit([exit_a, exit_b])
    pos = _Pos("005930", entry_price=10000.0)
    ctx = ExitContext(
        position=pos,
        market_data={"close": 9700.0},  # -3%: only exit_b's stop trips
        indicators={},
        timestamp=datetime(2026, 7, 8, 1, 0, tzinfo=UTC),
    )
    triggered, signal = await composite.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS

    # -6%: exit_a (first child) triggers and wins the ordering.
    pos2 = _Pos("000660", entry_price=10000.0)
    ctx2 = ExitContext(
        position=pos2,
        market_data={"close": 9400.0},
        indicators={},
        timestamp=datetime(2026, 7, 8, 1, 0, tzinfo=UTC),
    )
    triggered2, signal2 = await composite.should_exit(ctx2)
    assert triggered2
    assert signal2 is not None
    assert signal2.strategy == exit_a.name


# --- composite per-position state cleanup (leak prevention) -----------------


class _StubExit:
    """Duck-typed child exit that optionally always triggers."""

    def __init__(self, trigger: bool):
        self.trigger = trigger
        self.closed_keys: list[str] = []

    @property
    def name(self) -> str:
        return "stub_exit"

    async def should_exit(self, context):
        from shared.models.signal import ExitSignal

        if not self.trigger:
            return False, None
        position = context.position
        return True, ExitSignal(
            code=position.code,
            position_id=str(getattr(position, "id", "") or ""),
            reason=ExitReason.STRATEGY_EXIT,
            strategy=self.name,
        )

    async def scan_positions(self, positions, market_data, market_state=None):
        signals = []
        for position in positions:
            ctx = ExitContext(
                position=position,
                market_data=market_data.get(position.code, {}),
                indicators={},
                timestamp=datetime(2026, 7, 8, 1, 0, tzinfo=UTC),
            )
            triggered, signal = await self.should_exit(ctx)
            if triggered and signal is not None:
                signals.append(signal)
        return signals

    def update_state(self, context) -> None:
        return None

    def on_position_closed(self, pos_key: str) -> None:
        self.closed_keys.append(pos_key)


@pytest.mark.asyncio
async def test_composite_cleans_trailing_state_when_other_child_wins() -> None:
    # The declarative trailing exit arms its per-position extreme but the stub
    # primitive closes the position — without the cleanup hook the extreme
    # would leak onto a future position that reuses the same key.
    declarative = _exit(trailing_stop_pct=3.0)
    stub = _StubExit(trigger=True)
    composite = FirstTriggerExit([declarative, stub])
    pos = _Pos("005930", entry_price=10000.0)
    ctx = ExitContext(
        position=pos,
        market_data={"close": 11000.0},  # arms trailing (extreme=11000), no trigger
        indicators={},
        timestamp=datetime(2026, 7, 8, 1, 0, tzinfo=UTC),
    )
    triggered, signal = await composite.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.strategy == "stub_exit"
    assert declarative._extreme == {}  # no leaked per-position state


@pytest.mark.asyncio
async def test_composite_notifies_all_children_when_declarative_wins() -> None:
    declarative = _exit(stop_loss_pct=5.0)
    stub = _StubExit(trigger=False)
    composite = FirstTriggerExit([declarative, stub])
    pos = _Pos("005930", entry_price=10000.0)
    ctx = ExitContext(
        position=pos,
        market_data={"close": 9400.0},  # -6% -> declarative stop fires
        indicators={},
        timestamp=datetime(2026, 7, 8, 1, 0, tzinfo=UTC),
    )
    triggered, _signal = await composite.should_exit(ctx)
    assert triggered
    assert stub.closed_keys == ["pos_1"]


@pytest.mark.asyncio
async def test_composite_scan_positions_cleans_state_per_signal() -> None:
    declarative = _exit(trailing_stop_pct=3.0)
    stub = _StubExit(trigger=True)
    composite = FirstTriggerExit([declarative, stub])
    pos = _Pos("005930", entry_price=10000.0)
    # Arm the trailing extreme via the scan path (declarative sees the cycle
    # first, records the peak, does not trigger; stub then closes).
    signals = await composite.scan_positions([pos], {"005930": {"close": 11000.0}})
    assert len(signals) == 1
    assert signals[0].strategy == "stub_exit"
    assert declarative._extreme == {}
    assert stub.closed_keys == ["pos_1"]
