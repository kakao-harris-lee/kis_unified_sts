"""Backward-compat golden tests for the builder_v1 schema v2 extension (P2-a).

Pins the observable behavior of pre-v2 BuilderStates (fixtures captured from
main @ 3f760dc9, before the schema-v2 fields landed):

* ``state_hash`` / ``draft_id`` stay byte-identical — v2 fields must not leak
  into the hash of a state that does not use them.
* Evaluator signals (side/strength/reason/orderability/matched labels) over a
  deterministic series are unchanged.
* The runtime bridge still emits the same long entry signal for the
  operator-materialized ``golden_cross`` built YAML.

If any pinned value changes, an existing registered strategy would change
behavior on deploy — that is a regression, not a test to update casually.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from shared.strategy.base import EntryContext
from shared.strategy.entry.builder_strategy import (
    BuilderStrategyConfig,
    BuilderStrategyEntry,
)
from shared.strategy_builder.evaluator import StrategyBuilderEvaluator
from shared.strategy_builder.schema import BuilderState, SymbolSeries

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "builder"

# Pinned on main @ 3f760dc9 (pre-schema-v2).
_REP_STATE_HASH = "0b14246a4bdb3834757cb247bef5b43d657fdd6aeeddae5291d0009279d06912"
_REP_DRAFT_ID = "draft_0b14246a4bdb3834"
_GC_STATE_HASH = "5f07797ba5132c7187a92b686a2b268a1c9eba3a870655da398b61e60b8a0a9b"
_GC_DRAFT_ID = "draft_5f07797ba5132c71"


def _rep_state_raw() -> dict:
    return json.loads((_FIXTURES / "representative_state.json").read_text("utf-8"))


def _golden_cross_raw() -> dict:
    doc = yaml.safe_load((_FIXTURES / "golden_cross_built.yaml").read_text("utf-8"))
    return doc["strategy"]["entry"]["params"]["builder_state"]


def _series(symbol: str, closes: list[float], indicators: dict) -> SymbolSeries:
    return SymbolSeries(
        symbol=symbol,
        name=None,
        timestamps=[],
        fields={
            "close": closes,
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "volume": [1000.0] * len(closes),
        },
        indicators=indicators,
    )


def test_representative_state_hash_and_draft_id_are_stable() -> None:
    evaluator = StrategyBuilderEvaluator()
    state = BuilderState.model_validate(_rep_state_raw())
    assert evaluator.state_hash(state) == _REP_STATE_HASH
    assert evaluator.draft_id(state) == _REP_DRAFT_ID


def test_built_yaml_state_hash_and_draft_id_are_stable() -> None:
    evaluator = StrategyBuilderEvaluator()
    state = BuilderState.model_validate(_golden_cross_raw())
    assert evaluator.state_hash(state) == _GC_STATE_HASH
    assert evaluator.draft_id(state) == _GC_DRAFT_ID


def test_evaluator_signals_are_pinned() -> None:
    evaluator = StrategyBuilderEvaluator()
    state = BuilderState.model_validate(_rep_state_raw())

    entry_series = _series(
        "005930",
        [100.0, 101.0, 102.0],
        {
            "rsi.value": [45.0, 50.0, 55.0],
            "sma_fast.value": [99.0, 99.5, 101.5],
            "sma_slow.value": [100.0, 100.0, 100.5],
        },
    )
    exit_series = _series(
        "000660",
        [100.0, 101.0, 102.0],
        {
            "rsi.value": [65.0, 71.0, 75.0],
            "sma_fast.value": [101.0, 102.0, 103.0],
            "sma_slow.value": [100.0, 100.0, 100.0],
        },
    )
    hold_series = _series(
        "035420",
        [100.0, 100.0, 100.0],
        {
            "rsi.value": [50.0, 50.0, 50.0],
            "sma_fast.value": [99.0, 99.0, 99.0],
            "sma_slow.value": [100.0, 100.0, 100.0],
        },
    )

    signals = evaluator.generate_signals(
        state, [entry_series, exit_series, hold_series]
    )
    observed = [
        (
            sig.symbol,
            sig.side.value,
            sig.strength,
            sig.reason,
            sig.orderability,
            sig.draft_id,
            [(cond.label, cond.passed) for cond in sig.matched_conditions],
        )
        for sig in signals
    ]
    assert observed == [
        (
            "005930",
            "BUY",
            1.0,
            "Entry conditions matched",
            "paper_orderable",
            _REP_DRAFT_ID,
            [
                ("rsi.value greater_than 30.0", True),
                ("sma_fast.value cross_above sma_slow.value", True),
                ("close greater_equal sma_slow.value", True),
            ],
        ),
        (
            "000660",
            "SELL",
            0.5,
            "Exit conditions matched",
            "paper_orderable",
            _REP_DRAFT_ID,
            [
                ("rsi.value greater_than 70.0", True),
                ("sma_fast.value cross_below sma_slow.value", False),
            ],
        ),
        (
            "035420",
            "HOLD",
            0.6667,
            "No actionable condition group matched",
            "not_actionable",
            _REP_DRAFT_ID,
            [
                ("rsi.value greater_than 30.0", True),
                ("sma_fast.value cross_above sma_slow.value", False),
                ("close greater_equal sma_slow.value", True),
            ],
        ),
    ]


def test_bridge_emits_pinned_long_signal_for_built_golden_cross() -> None:
    entry = BuilderStrategyEntry(
        BuilderStrategyConfig(builder_state=_golden_cross_raw())
    )
    closes = [100.0 - 2 * i for i in range(24)] + [400.0]
    rows = [
        {"open": c, "high": c + 1.0, "low": c - 1.0, "close": c, "volume": 1000.0}
        for c in closes
    ]
    ctx = EntryContext(
        market_data={"code": "005930", "name": "삼성전자", "close": 70000.0},
        indicators={"ohlcv": rows},
        timestamp=datetime(2026, 7, 8, 1, 0, tzinfo=UTC),
    )
    signal = asyncio.run(entry.generate(ctx))
    assert signal is not None
    assert signal.code == "005930"
    assert signal.confidence == 1.0
    assert signal.metadata["signal_direction"] == "long"
    assert signal.strategy == "builder_v1::golden_cross"
