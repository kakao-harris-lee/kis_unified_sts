"""The causal bar → ``DECISION_TICK`` streaming converter (design #33 §3.1/§3.6)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from tos.backtest._base import BacktestIntegrityError
from tos.backtest.bars import Bar
from tos.backtest.resolver import BarTimeProjection
from tos.capsule import DecisionContextCapsule
from tos.engine import DecisionContextResolver, DecisionTickPayload, InstrumentKey

__all__ = ["CausalBarConverter", "ConvertedTick"]

CapsuleSource = Callable[[Bar], DecisionContextCapsule]


@dataclass(frozen=True)
class ConvertedTick:
    """One bar's converted tick — the bar and the payload it produced (design #33 §3.2)."""

    bar: Bar
    payload: DecisionTickPayload


class CausalBarConverter:
    """Converts a bar stream into ``DECISION_TICK`` payloads, one bar at a time (design #33 §3.1)."""

    def __init__(
        self,
        *,
        instrument_key: InstrumentKey,
        resolver: DecisionContextResolver,
        capsule_source: CapsuleSource,
        time_projection: BarTimeProjection,
    ) -> None:
        """Wire the converter."""
        self._instrument_key = instrument_key
        self._resolver = resolver
        self._capsule_source = capsule_source
        self._time_projection = time_projection

    @property
    def instrument_key(self) -> InstrumentKey:
        """The scope this converter replays."""
        return self._instrument_key

    def stream(self, bars: Iterable[Bar]) -> Iterator[ConvertedTick]:
        """Yield exactly one converted tick per bar, in stream order (design #33 §3.1)."""
        for bar in bars:
            capsule = self._capsule_source(bar)
            if capsule is None:
                raise BacktestIntegrityError(
                    f"the injected capsule source produced no Decision Context for bar "
                    f"{bar.bar_index} — a missing Capsule forbids a decision and is recorded as a "
                    "stop, never treated as an empty context (RFC-003 §7:201-204)"
                )
            payload = self._resolver(capsule, instrument_key=self._instrument_key)
            yield ConvertedTick(
                bar=bar,
                payload=payload.model_copy(
                    update={"time": self._time_projection.project(bar)}
                ),
            )
