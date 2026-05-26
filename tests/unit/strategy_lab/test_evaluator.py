"""Strategy Lab evaluator tests."""

import pytest

from shared.strategy_lab.evaluator import StrategyLabEvaluator
from shared.strategy_lab.order_bridge import StrategyLabOrderBridge
from shared.strategy_lab.schema import (
    ConditionOperator,
    ConditionSpec,
    MarketSnapshot,
    Operand,
    RuleGroup,
    SignalSide,
    StrategySpec,
)
from shared.strategy_lab.store import StrategyLabStore, reset_memory_store


def _spec() -> StrategySpec:
    return StrategySpec(
        name="RSI visual draft",
        asset_class="stock",
        entry=RuleGroup(
            conditions=[
                ConditionSpec(
                    left=Operand(kind="indicator", name="rsi"),
                    operator=ConditionOperator.LTE,
                    right=Operand(kind="literal", value=30),
                )
            ]
        ),
        exit=RuleGroup(
            conditions=[
                ConditionSpec(
                    left=Operand(kind="indicator", name="rsi"),
                    operator=ConditionOperator.GTE,
                    right=Operand(kind="literal", value=70),
                )
            ]
        ),
        risk={"order_amount": 1_000_000},
    )


def test_evaluator_generates_buy_sell_hold_signals():
    evaluator = StrategyLabEvaluator()
    signals = evaluator.generate_signals(
        _spec(),
        [
            MarketSnapshot(symbol="BUY", price=10_000, indicators={"rsi": 25}),
            MarketSnapshot(symbol="SELL", price=10_000, indicators={"rsi": 80}),
            MarketSnapshot(symbol="HOLD", price=10_000, indicators={"rsi": 50}),
        ],
    )

    assert [signal.side for signal in signals] == [
        SignalSide.BUY,
        SignalSide.SELL,
        SignalSide.HOLD,
    ]
    assert signals[0].orderability == "paper_orderable"
    assert signals[2].orderability == "not_actionable"
    assert signals[0].matched_rules[0].passed is True


def test_order_bridge_fills_buy_and_rejects_sell_without_position():
    reset_memory_store()
    store = StrategyLabStore(use_redis=False)
    evaluator = StrategyLabEvaluator()
    bridge = StrategyLabOrderBridge(store)

    buy_signal = evaluator.generate_signals(
        _spec(),
        [MarketSnapshot(symbol="005930", price=70_000, indicators={"rsi": 20})],
    )[0]
    store.store_signal(buy_signal)

    ticket = bridge.create_ticket(buy_signal)
    order = bridge.submit_paper_order(ticket)

    assert ticket.status == "ready"
    assert order.status == "filled"
    assert order.quantity == 14
    assert store.get_position(buy_signal.draft_id, "005930") is not None

    sell_signal = evaluator.generate_signals(
        _spec(),
        [MarketSnapshot(symbol="000660", price=150_000, indicators={"rsi": 80})],
    )[0]
    store.store_signal(sell_signal)

    rejected = bridge.create_ticket(sell_signal)
    assert rejected.status == "rejected"
    assert "No matching" in (rejected.reason or "")


@pytest.mark.parametrize("rsi", [None])
def test_missing_indicator_blocks_orderability(rsi):
    evaluator = StrategyLabEvaluator()
    signals = evaluator.generate_signals(
        _spec(),
        [MarketSnapshot(symbol="005930", price=70_000, indicators={})],
    )

    assert signals[0].side == SignalSide.HOLD
    assert signals[0].orderability == "missing_data"
    assert signals[0].matched_rules[0].missing == ["rsi"]
    assert rsi is None
