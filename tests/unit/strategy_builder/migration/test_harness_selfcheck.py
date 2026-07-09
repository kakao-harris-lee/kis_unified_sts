"""Self-check for the P2-c signal-equivalence harness.

Proves the harness end-to-end on a rule that IS expressible in the builder
vocabulary: a test-local imperative reference entry (legacy style — computes
SMA(3)/SMA(8) by hand from the OHLCV window, tracks its own cooldown) against
the equivalent declarative BuilderState (``builder_v1`` + TA-Lib engine +
``gates.cooldown_seconds``), both run through the real backtest adapter path.

* PASS case: identical rule → identical signal sequences, including cooldown
  suppression and confidence (single AND condition → score 1.0).
* FAIL case: a deliberately different declarative rule (SMA(4) fast leg) →
  the harness must report the divergence. This is the property the migration
  gate relies on: it must be able to say NO.

Integer prices keep every SMA an exact float (integer sums are exact in
float64, and TA-Lib's rolling-sum SMA subtracts the same integers), so
cross comparisons cannot flicker on representation noise.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from shared.config.mixins import ConfigMixin
from shared.models.signal import ExitSignal, Signal, SignalType
from shared.strategy.base import (
    EntryContext,
    EntrySignalGenerator,
    ExitContext,
    ExitSignalGenerator,
    TradingStrategy,
)
from shared.strategy.position import FixedSizer, FixedSizerConfig
from tests.unit.strategy_builder.migration.harness import (
    collect_entry_signal_events,
    compare_signal_sequences,
    kst_session_bars,
)

_CODE = "005930"
_COOLDOWN_SECONDS = 1800


@dataclass
class _RefConfig(ConfigMixin):
    fast: int = 3
    slow: int = 8
    cooldown_seconds: int = _COOLDOWN_SECONDS


class _ReferenceSmaCrossEntry(EntrySignalGenerator[_RefConfig]):
    """Legacy-style imperative twin of the declarative SMA-cross state."""

    CONFIG_CLASS = _RefConfig

    def __init__(self, config: _RefConfig):
        super().__init__(config)
        self._last_signal_at: dict[str, datetime] = {}

    def _validate_config(self) -> None:
        assert 0 < self.config.fast < self.config.slow

    @property
    def name(self) -> str:
        return "reference_sma_cross"

    @property
    def required_indicators(self) -> list[str]:
        return ["ohlcv"]

    async def generate(self, context: EntryContext) -> Signal | None:
        data = context.market_data or {}
        code = str(data.get("code", "") or "")
        close = float(data.get("close", 0) or 0)
        if not code or close <= 0:
            return None

        now = context.timestamp
        last = self._last_signal_at.get(code)
        if last and (now - last).total_seconds() < self.config.cooldown_seconds:
            return None

        rows = (context.indicators or {}).get("ohlcv")
        if not isinstance(rows, list) or len(rows) < self.config.slow + 1:
            return None
        closes = [float(row["close"]) for row in rows]

        def sma(period: int, offset: int) -> float:
            window = closes[len(closes) - period - offset : len(closes) - offset]
            return sum(window) / period

        prev_fast = sma(self.config.fast, 1)
        prev_slow = sma(self.config.slow, 1)
        cur_fast = sma(self.config.fast, 0)
        cur_slow = sma(self.config.slow, 0)

        # Mirror of the evaluator's cross_above semantics.
        if not (prev_fast <= prev_slow and cur_fast > cur_slow):
            return None

        self._last_signal_at[code] = now
        return Signal(
            code=code,
            name=str(data.get("name", "") or ""),
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=now,
            strategy=self.name,
            confidence=1.0,
            metadata={"signal_direction": "long"},
        )


@dataclass
class _NoopExitConfig(ConfigMixin):
    pass


class _NoopExit(ExitSignalGenerator[_NoopExitConfig]):
    CONFIG_CLASS = _NoopExitConfig

    def _validate_config(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "noop_exit"

    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        return (False, None)

    async def scan_positions(self, positions, market_data, market_state=None):
        return []


def _reference_strategy() -> TradingStrategy:
    return TradingStrategy(
        name="reference_sma_cross",
        entry=_ReferenceSmaCrossEntry(_RefConfig()),
        exit=_NoopExit(_NoopExitConfig()),
        position_sizer=FixedSizer(FixedSizerConfig()),
    )


def _builder_state(fast_period: int) -> dict:
    return {
        "metadata": {
            "id": "sma_cross_selfcheck",
            "name": "SMA cross harness self-check",
        },
        "asset_class": "stock",
        "indicators": [
            {
                "id": "ind_fast",
                "indicator_id": "sma",
                "alias": "sma_fast",
                "params": {"period": fast_period},
                "output": "value",
            },
            {
                "id": "ind_slow",
                "indicator_id": "sma",
                "alias": "sma_slow",
                "params": {"period": 8},
                "output": "value",
            },
        ],
        "entry": {
            "logic": "AND",
            "conditions": [
                {
                    "id": "cond_cross",
                    "left": {"type": "indicator", "indicator_alias": "sma_fast"},
                    "operator": "cross_above",
                    "right": {"type": "indicator", "indicator_alias": "sma_slow"},
                }
            ],
        },
        "exit": {"logic": "AND", "conditions": []},
        "risk": {
            "order_amount": 1_000_000,
            "stop_loss": {"enabled": False, "percent": 5.0},
            "take_profit": {"enabled": False, "percent": 10.0},
            "trailing_stop": {"enabled": False, "percent": 3.0},
        },
        "gates": {"cooldown_seconds": _COOLDOWN_SECONDS},
    }


def _declarative_config(fast_period: int) -> dict:
    state = _builder_state(fast_period)
    return {
        "strategy": {
            "name": "sma_cross_selfcheck",
            "asset_class": "stock",
            "enabled": False,
            "entry": {
                "type": "builder_v1",
                "params": {"builder_state": state, "cooldown_seconds": 0},
            },
            "exit": {
                "type": "builder_v1_exit",
                "params": {"builder_state": state},
            },
            "position": {"type": "fixed", "params": {}},
        }
    }


def _triangle_wave_bars() -> list:
    """One KST session with several SMA(3)/SMA(8) crosses.

    Triangle wave (integer prices): 15 bars up (+2), 15 bars down (-2),
    repeated. Crosses land at the turns; the 1800s cooldown then suppresses a
    deterministic subset — exercising cooldown parity, not just the raw rule.
    """
    closes: list[float] = []
    level = 1000.0
    direction = 1.0
    for _ in range(8):  # 8 legs x 15 bars = 120 bars
        for _ in range(15):
            level += 2.0 * direction
            closes.append(level)
        direction = -direction
    return kst_session_bars(date(2026, 7, 6), closes, code=_CODE)


def test_equivalent_rule_produces_identical_signal_sequence() -> None:
    bars = _triangle_wave_bars()

    legacy_events = collect_entry_signal_events(bars, strategy=_reference_strategy())
    declarative_events = collect_entry_signal_events(
        bars, strategy_config=_declarative_config(fast_period=3)
    )

    report = compare_signal_sequences(
        legacy_events, declarative_events, compare_confidence=True
    )
    # The scenario must actually exercise both the rule and the cooldown:
    # 4 up-turns in 120 bars, cooldown 30 bars → at least 2 signals survive.
    assert len(legacy_events) >= 2, report.summary()
    assert report.equivalent, report.summary()


def test_divergent_rule_is_detected() -> None:
    bars = _triangle_wave_bars()

    legacy_events = collect_entry_signal_events(bars, strategy=_reference_strategy())
    declarative_events = collect_entry_signal_events(
        bars, strategy_config=_declarative_config(fast_period=5)
    )

    report = compare_signal_sequences(legacy_events, declarative_events)
    assert not report.equivalent, (
        "harness failed to flag a deliberately different rule\n" + report.summary()
    )
    assert report.divergences
