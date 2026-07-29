"""The causal bar → ``DECISION_TICK`` streaming converter (design #33 §3.1/§3.6).

**Look-ahead is made structurally impossible, not forbidden by convention.** The converter is a
generator over the bar iterator: it pulls one bar, emits that bar's tick, and pulls the next only
when the consumer asks for it. It keeps **no reference to any bar** — not the current one, not a
window, not the stream — so composing bar *t*'s decision input from bar *t+1* is not something the
code declines to do, it is something the code cannot express (design #33 §3.6). ADR-DEV-010
BTE-INV-004:137-139 ("every indicator and input SHALL be bounded by the current context timestamp")
is therefore realized structurally, and look-ahead — an ADR-DEV-010 §8:182-184 disqualifier — is
avoided by construction.

Two things this converter deliberately does **not** own:

* **the causal coordinate.** ``reference`` stays at the engine default here; the driver stamps every
  yielded event with its global monotone yield-order coordinate (design #33 §3.4 MAJOR-1). Binding
  the coordinate to ``bar_index`` is precisely the defect the design's v1.1 revision removed: with a
  ``2i / 2i+1`` scheme a next-bar settlement sequence (``tick_0, tick_1, egress_0``) makes the
  engine's single global ``_last_reference`` gate (``core.py:246``/``:280``/``:301``) read a false
  ``REVERSED`` halt.
* **the value surface.** The injected :class:`~tos.engine.DecisionContextResolver` owns it, and
  slice #1 injects the provisional one (design #33 §3.5).

⚠ **Decision vs settlement.** The converter is the *decision* side and is prefix-bounded. Fill
settlement legitimately uses the settlement bar (design #33 §3.6/§12.2-4) — that is execution
realism, not look-ahead — and lives in :mod:`tos.backtest.fills`.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from tos.backtest._base import BacktestIntegrityError
from tos.backtest.bars import Bar
from tos.backtest.resolver import BarTimeProjection
from tos.capsule import DecisionContextCapsule
from tos.engine import DecisionContextResolver, DecisionTickPayload, InstrumentKey

__all__ = ["CausalBarConverter", "ConvertedTick"]

#: ``(bar) -> DecisionContextCapsule`` — the injected Capsule source for one bar. Capsule issuance
#: belongs to the Critical Input pipeline (D-E2 / out-of-tree), never to the harness: minting a
#: Capsule inside the converter would let the harness author its own decision context.
CapsuleSource = Callable[[Bar], DecisionContextCapsule]


@dataclass(frozen=True)
class ConvertedTick:
    """One bar's converted tick — the bar and the payload it produced (design #33 §3.2).

    The bar travels alongside the payload because the *driver* needs it for the fill model's
    settlement context (design #33 §4.1); the payload itself carries no bar, so nothing downstream
    of the engine can read bar data out of an event.
    """

    bar: Bar
    payload: DecisionTickPayload


class CausalBarConverter:
    """Converts a bar stream into ``DECISION_TICK`` payloads, one bar at a time (design #33 §3.1).

    The converter holds the injected plugs (key, resolver, capsule source, time projection) and
    **no bar state at all**. :meth:`stream` is a generator; the ``for bar in bars`` loop is what
    makes the consumption a prefix — a mutation that materialises ``tuple(bars)`` first, or that
    peeks at the next bar, is detected by the prefix-consumption property test (design #33 §8-5).
    """

    def __init__(
        self,
        *,
        instrument_key: InstrumentKey,
        resolver: DecisionContextResolver,
        capsule_source: CapsuleSource,
        time_projection: BarTimeProjection,
    ) -> None:
        """Wire the converter.

        Args:
            instrument_key: The single dispatch scope this slice replays.
            resolver: The injected D-E2 value-surface plug (provisional in slice #1, §3.5).
            capsule_source: The injected per-bar Decision Context Capsule source.
            time_projection: The injected bar → time-coordinate projection (§3.3).
        """
        self._instrument_key = instrument_key
        self._resolver = resolver
        self._capsule_source = capsule_source
        self._time_projection = time_projection

    @property
    def instrument_key(self) -> InstrumentKey:
        """The scope this converter replays."""
        return self._instrument_key

    def stream(self, bars: Iterable[Bar]) -> Iterator[ConvertedTick]:
        """Yield exactly one converted tick per bar, in stream order (design #33 §3.1).

        Args:
            bars: The bar stream (consumed lazily, one bar at a time).

        Yields:
            One :class:`ConvertedTick` per bar.

        Raises:
            BacktestIntegrityError: If the injected capsule source produces nothing for a bar —
                a missing Decision Context is a fail-closed stop, never an implied empty one
                (RFC-003 §7:201-204; the ∅ discipline in its restrictive direction).
        """
        for bar in bars:
            capsule = self._capsule_source(bar)
            if capsule is None:
                raise BacktestIntegrityError(
                    f"the injected capsule source produced no Decision Context for bar "
                    f"{bar.bar_index} — a missing Capsule forbids a decision and is recorded as a "
                    "stop, never treated as an empty context (RFC-003 §7:201-204)"
                )
            payload = self._resolver(capsule, instrument_key=self._instrument_key)
            # The bar-derived time coordinates are D-E3's (§3.3); the causal coordinate is the
            # driver's (§3.4) and is deliberately left at its engine default here.
            yield ConvertedTick(
                bar=bar,
                payload=payload.model_copy(
                    update={"time": self._time_projection.project(bar)}
                ),
            )
