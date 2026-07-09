"""Signal-equivalence harness for legacy → declarative pilot migrations (P2-c).

Runs a legacy registry strategy and its declarative (``builder_v1``
BuilderState) counterpart over the SAME deterministic bar sequence through the
real backtest adapter path (``BacktestStrategyAdapter`` — the same indicator
resolver/engine wiring the live paper pipeline uses) and compares the emitted
entry-signal sequences.

The migration gate (plan §4 P2-c): a legacy strategy may only be replaced by
a declarative BuilderState YAML when the two produce IDENTICAL signal
sequences — same timestamps, same directions (and, where the two sides compute
comparable strengths, same confidences). Anything else is a deferral with the
missing vocabulary documented in the plan.

Usage sketch::

    legacy = collect_entry_signal_events(bars, strategy_config=legacy_yaml_doc)
    declarative = collect_entry_signal_events(bars, strategy_config=builder_doc)
    report = compare_signal_sequences(legacy, declarative)
    assert report.equivalent, report.summary()

Bars are plain dicts with KST tz-aware ``datetime`` plus OHLCV fields — the
exact shape ``BacktestEngine`` feeds the adapter.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from shared.backtest.adapter import BacktestStrategyAdapter
from shared.strategy import register_builtin_components
from shared.strategy.base import TradingStrategy
from shared.strategy.factory import StrategyFactory

KST = ZoneInfo("Asia/Seoul")

#: Default number of 1-minute bars in a KST stock session (09:00–15:19 here;
#: keeps synthetic days inside the 15:30 close without extra assumptions).
DEFAULT_SESSION_BARS = 380


@dataclass(frozen=True)
class SignalEvent:
    """One emitted entry signal, reduced to its equivalence-relevant fields."""

    timestamp: datetime
    direction: str
    price: float
    confidence: float
    strategy: str


@dataclass
class EquivalenceReport:
    """Comparison result between a legacy and a declarative signal sequence."""

    legacy_events: list[SignalEvent]
    declarative_events: list[SignalEvent]
    divergences: list[str] = field(default_factory=list)

    @property
    def equivalent(self) -> bool:
        return not self.divergences

    def summary(self) -> str:
        lines = [
            f"legacy signals: {len(self.legacy_events)}",
            f"declarative signals: {len(self.declarative_events)}",
        ]
        lines += [f"divergence: {item}" for item in self.divergences]
        return "\n".join(lines)


def collect_entry_signal_events(
    bars: list[dict[str, Any]],
    *,
    strategy_config: dict[str, Any] | None = None,
    strategy: TradingStrategy | None = None,
) -> list[SignalEvent]:
    """Run entry generation over ``bars`` via the backtest adapter path.

    Args:
        bars: Chronological bar dicts (``datetime`` tz-aware KST, OHLCV,
            ``code``). Each bar is copied before feeding (the adapter/enricher
            mutate bars in place).
        strategy_config: Full strategy YAML document (``{"strategy": {...}}``)
            built through ``StrategyFactory`` — the production path.
        strategy: Pre-assembled ``TradingStrategy`` (for harness self-checks
            with test-local reference generators). Mutually exclusive with
            ``strategy_config`` — provide exactly one. When given, a minimal
            config document is synthesized for the adapter.

    Returns:
        Entry-signal events in emission order (one per bar at most — the
        adapter runs ``check_entry`` once per warm decision bar).
    """
    if (strategy is None) == (strategy_config is None):
        raise ValueError("provide exactly one of strategy_config / strategy")

    register_builtin_components()
    if strategy is None:
        assert strategy_config is not None
        config = copy.deepcopy(strategy_config)
        strategy = StrategyFactory.create(config)
    else:
        config = {"strategy": {"name": strategy.name}}

    adapter = BacktestStrategyAdapter(strategy, config)

    events: list[SignalEvent] = []
    for bar in bars:
        adapter.on_bar(dict(bar))
        signal = adapter.last_entry_signal
        if signal is None:
            continue
        events.append(
            SignalEvent(
                timestamp=signal.timestamp,
                direction=str((signal.metadata or {}).get("signal_direction", "long")),
                price=float(signal.price),
                confidence=float(signal.confidence),
                strategy=str(signal.strategy),
            )
        )
    return events


def compare_signal_sequences(
    legacy: list[SignalEvent],
    declarative: list[SignalEvent],
    *,
    compare_price: bool = True,
    compare_confidence: bool = False,
) -> EquivalenceReport:
    """Compare two entry-signal sequences pairwise.

    Timestamps and directions are ALWAYS compared (the hard equivalence gate).
    Price is compared by default (both sides read the same bar close);
    confidence only on request — legacy strategies usually compute bespoke
    confidence formulas that the declarative score does not reproduce, which
    is an accepted, documented difference (mission: "where comparable").
    """
    report = EquivalenceReport(
        legacy_events=list(legacy), declarative_events=list(declarative)
    )

    for index, (lhs, rhs) in enumerate(zip(legacy, declarative)):
        if lhs.timestamp != rhs.timestamp:
            report.divergences.append(
                f"signal[{index}] timestamp: legacy={lhs.timestamp.isoformat()} "
                f"declarative={rhs.timestamp.isoformat()}"
            )
            # Timestamps disagree — later pairwise fields are not meaningful.
            break
        if lhs.direction != rhs.direction:
            report.divergences.append(
                f"signal[{index}] direction: legacy={lhs.direction} "
                f"declarative={rhs.direction}"
            )
        if compare_price and lhs.price != rhs.price:
            report.divergences.append(
                f"signal[{index}] price: legacy={lhs.price} " f"declarative={rhs.price}"
            )
        if compare_confidence and lhs.confidence != rhs.confidence:
            report.divergences.append(
                f"signal[{index}] confidence: legacy={lhs.confidence} "
                f"declarative={rhs.confidence}"
            )

    if len(legacy) != len(declarative):
        report.divergences.append(
            f"signal count: legacy={len(legacy)} declarative={len(declarative)}"
        )
    return report


def kst_session_bars(
    day: date,
    closes: list[float],
    *,
    code: str = "005930",
    volumes: list[float] | float = 1000.0,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    start: time = time(9, 0),
) -> list[dict[str, Any]]:
    """Build one KST session of deterministic 1-minute bars from closes.

    open = previous close (first bar: its own close); high/low default to the
    open/close envelope so the data stays exact-integer friendly. Explicit
    ``highs``/``lows`` let a scenario shape ranges (e.g. Williams %R depth)
    precisely.
    """
    if isinstance(volumes, (int, float)):
        volumes = [float(volumes)] * len(closes)
    if len(volumes) != len(closes):
        raise ValueError("volumes length must match closes")
    if highs is not None and len(highs) != len(closes):
        raise ValueError("highs length must match closes")
    if lows is not None and len(lows) != len(closes):
        raise ValueError("lows length must match closes")

    bars: list[dict[str, Any]] = []
    first = datetime.combine(day, start, tzinfo=KST)
    prev_close = closes[0]
    for i, close in enumerate(closes):
        open_ = prev_close
        high = highs[i] if highs is not None else max(open_, close)
        low = lows[i] if lows is not None else min(open_, close)
        bars.append(
            {
                "datetime": first + timedelta(minutes=i),
                "open": float(open_),
                "high": float(max(high, open_, close)),
                "low": float(min(low, open_, close)),
                "close": float(close),
                "volume": float(volumes[i]),
                "code": code,
            }
        )
        prev_close = close
    return bars
