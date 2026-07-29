"""The interleaving re-injection driver + the global yield-order counter (design #33 §3.4/§4.1).

This module is the design's load-bearing content. Three things live here and nothing else does.

**1. The driver-owned global monotone yield-order counter (design #33 §3.4, MAJOR-1).**

The engine's causal gate does **not** compare an event against its triggering tick: it holds a
single global ``_last_reference`` (``core.py:246``), compares every incoming event against it
(``core.py:280``), and updates it for **every** non-``REVERSED`` event (``core.py:301``) — including
a tick that goes on to halt at the capacity stage, because line 301 runs *before* the handler.

So a coordinate scheme bound to ``bar_index`` is broken. With ``2i / 2i+1``, a next-bar settlement
is processed as ``tick_0(0), tick_1(2), egress_0(1)`` — and ``compare_order(1, 2)`` is ``BEFORE``,
so the re-injected result is refused as a **false ``REVERSED``** halt (``core.py:281``). The fix is
structural: the driver stamps **every** event it yields — tick or egress alike — with the next value
of one global counter at yield time. Because the driver's yield order *is* the core's processing
order, the coordinates are strictly increasing by construction, and the admission is always
``MONOTONE`` regardless of same-bar or next-bar settlement. The coordinate is therefore
**decoupled** from ``bar_index``, which is recorded separately for settlement lookup and oracle
alignment (design #33 §3.4/§4.3/§6).

There is deliberately **no reset / rewind method**: a counter that could go backwards is the defect
the design removed.

**2. The interleaving ``EventSource`` generator (design #33 §4.1 B3).**

``EngineCore.run`` consumes its argument **lazily** (``core.py:262`` — a generator expression over
``events``), which is what makes the re-injection model work at all: the driver yields a tick, the
core processes it to completion (the sequencer calls ``transmit``, the fill model *stages*), and
only then does the core pull the next event — at which point the driver can yield the staged fill as
an ``EGRESS_RESULT``. Same core, same sequencer, same ledger lifetime.

Two rejected alternatives, both from the design: re-authoring ``run`` to apply fills inline (forbidden
core re-authoring, and it destroys the re-injection model that paper shares), and pre-building a
static ``EventBatch`` (impossible — a fill depends on what the core decided). The stateful generator
is the only consistent shape.

**3. The core re-instantiation prohibition (design #33 §2.4 — a hard constraint).**

Rebuilding an ``EngineCore`` per bar would reset the ``ProvisionalReservationLedger`` and make the
scope look free every bar, so repeated sends would appear to work. It is forbidden twice over: it
destroys the single-core backtest/paper parity that is the whole point (design #31 §2.1/§12), and it
forges capacity headroom that does not exist in the real system — the harness-layer form of
RFC-002 §9.1:558's "producer-local counters SHALL NOT create headroom". The no-release constraint is
an honest reflection of the RCL runtime's absence, not something to route around.

Two independent seals enforce it: :class:`BacktestDriver` binds the first core it is run against and
refuses a different one, and the package's own sources construct no ``EngineCore`` at all (an AST
canary asserts it — design #33 §9).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No clock, no RNG, no network.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from tos.backtest._base import BacktestIntegrityError
from tos.backtest.bars import Bar, BarStream, validate_bar_stream
from tos.backtest.converter import CausalBarConverter
from tos.backtest.fills import DeterministicFillModel
from tos.backtest.records import HaltRecord, TraceEntry, WiringTrace
from tos.backtest.results import BacktestRun
from tos.backtest.vocabulary import ScenarioId
from tos.engine import (
    EgressResultPayload,
    EngineCore,
    EngineEvent,
    EventKind,
    EventResult,
    InstrumentKey,
)
from tos.ordering import OrderingEvent

__all__ = ["BacktestDriver", "CoreReinstantiationError", "YieldOrderCounter"]


class CoreReinstantiationError(BacktestIntegrityError):
    """A driver was asked to run against a second, different :class:`~tos.engine.EngineCore`.

    Raised — never tolerated. Per-bar re-instantiation resets the reservation projection, forging
    capacity headroom the real system does not have and destroying single-core backtest/paper
    parity (design #33 §2.4; RFC-002 §9.1:558).
    """


class YieldOrderCounter:
    """The driver-owned global monotone yield-order counter (design #33 §3.4, MAJOR-1).

    One counter for the whole run, across **both** event kinds. Its invariant is stated as an
    identity rather than a hope: *coordinate order ≡ processing order*, because the only way to
    obtain a coordinate is to be the next event yielded.

    It emits :class:`~tos.ordering.OrderingEvent` coordinates on a single continuity, so
    :func:`~tos.ordering.compare_order` resolves them by ``source_native_sequence``
    (``ordering/_ordering.py:112-127``) — the same-continuity branch, never a cross-continuity
    subtraction and never a wall clock. ``time_lo`` / ``time_hi`` are deliberately left unset:
    trustworthy-time intervals do not participate in this ordering (design #33 §3.4 정직), and
    freshness travels separately on ``TimeAdmissionInputs``.
    """

    def __init__(self, *, continuity_id: str) -> None:
        """Create the counter.

        Args:
            continuity_id: The single stream continuity every coordinate is issued on.

        Raises:
            BacktestIntegrityError: If the continuity id is not concrete — coordinates are only
                comparable within a named continuity.
        """
        if not continuity_id.strip():
            raise BacktestIntegrityError(
                "YieldOrderCounter.continuity_id must be concrete — source-native sequences are "
                "compared only within the same continuity (ordering/_ordering.py:112-127)"
            )
        self._continuity_id = continuity_id
        self._issued = 0

    @property
    def continuity_id(self) -> str:
        """The stream continuity every issued coordinate carries."""
        return self._continuity_id

    @property
    def issued(self) -> int:
        """How many coordinates have been issued so far."""
        return self._issued

    def next_reference(self) -> OrderingEvent:
        """Issue the next strictly-greater coordinate (design #33 §3.4).

        Returns:
            The :class:`~tos.ordering.OrderingEvent` for the event about to be yielded. There is no
            way to obtain a coordinate without advancing the counter, and no method rewinds it.
        """
        self._issued += 1
        sequence = self._issued
        return OrderingEvent(
            event_id=f"{self._continuity_id}-{sequence}",
            source_continuity_id=self._continuity_id,
            source_native_sequence=sequence,
        )


class BacktestDriver:
    """Drives one bar stream through **one** engine core, interleaving re-injected fills (§4.1).

    The driver owns: the yield-order counter (§3.4), the settlement-context binding the fill model
    cannot derive from an ``AttemptRequest`` (§4.1), the interleaving of ticks and re-injected
    egress results, and the assembly of the run's D-E3-local artifacts.

    It owns **nothing** of the engine: it constructs no core, injects no stage, and re-authors no
    sequencer step (design #33 §0.2-1).
    """

    def __init__(
        self,
        *,
        converter: CausalBarConverter,
        fill_model: DeterministicFillModel,
        continuity_id: str,
        scenario_id: ScenarioId | None = None,
    ) -> None:
        """Wire the driver.

        Args:
            converter: The causal bar → tick converter (§3.1).
            fill_model: The deterministic synthetic ``Transmit`` band (§4).
            continuity_id: The stream continuity for the yield-order coordinates (§3.4).
            scenario_id: The mandated scenario this run realizes, recorded on the result.
        """
        self._converter = converter
        self._fill_model = fill_model
        self._counter = YieldOrderCounter(continuity_id=continuity_id)
        self._scenario_id = scenario_id
        self._bound_core: EngineCore | None = None
        self._yielded: list[tuple[EngineEvent, int | None]] = []
        self._bars_consumed = 0

    @property
    def instrument_key(self) -> InstrumentKey:
        """The single scope this driver replays."""
        return self._converter.instrument_key

    @property
    def counter(self) -> YieldOrderCounter:
        """The driver-owned yield-order counter (observation only)."""
        return self._counter

    @property
    def bound_core(self) -> EngineCore | None:
        """The core this driver has been bound to, if it has run (design #33 §2.4)."""
        return self._bound_core

    # -- the interleaving EventSource ----------------------------------------

    def events(self, bars: Iterable[Bar]) -> Iterator[EngineEvent]:
        """Yield ``DECISION_TICK`` / ``EGRESS_RESULT`` events in causal processing order (§4.1).

        The generator's shape *is* the re-injection contract:

        1. bind the current bar as the fill model's settlement context — synchronously, **before**
           the tick is yielded, because the model cannot read a settlement bar off an economics-free
           ``AttemptRequest`` (design #33 §4.1);
        2. yield the tick, stamped with the next yield-order coordinate;
        3. the core processes it to completion — the sequencer's step-14 hand-off calls the fill
           model, which *stages* a pending fill;
        4. when the core pulls again, settle every fill whose settlement bar has now arrived and
           yield each as an ``EGRESS_RESULT``, each stamped with the next coordinate.

        With ``NEXT_BAR`` settlement this produces ``tick_0, tick_1, egress_0`` — coordinates
        ``1, 2, 3`` — and every admission is ``MONOTONE``. Under the rejected ``2i / 2i+1`` scheme
        the same sequence would be ``0, 2, 1`` and the re-injected result would be refused as a
        false ``REVERSED`` (design #33 §3.4 MAJOR-1).

        Args:
            bars: The validated bar stream.

        Yields:
            The interleaved engine events.
        """
        for tick in self._converter.stream(bars):
            self._bars_consumed += 1
            self._fill_model.bind_settlement_context(tick.bar)
            payload = tick.payload.model_copy(
                update={"reference": self._counter.next_reference()}
            )
            event = EngineEvent(kind=EventKind.DECISION_TICK, decision_tick=payload)
            self._yielded.append((event, tick.bar.bar_index))
            yield event

            for settled in self._fill_model.settle_due(tick.bar):
                egress: EgressResultPayload = settled.payload.model_copy(
                    update={"reference": self._counter.next_reference()}
                )
                egress_event = EngineEvent(
                    kind=EventKind.EGRESS_RESULT, egress_result=egress
                )
                self._yielded.append((egress_event, tick.bar.bar_index))
                yield egress_event

    # -- the run -------------------------------------------------------------

    def run(self, core: EngineCore, bars: Iterable[Bar] | None) -> BacktestRun:
        """Replay ``bars`` through ``core`` and assemble the run's D-E3-local artifacts.

        Args:
            core: The **single** engine core for the whole run. The same core must be reused across
                every bar and across repeated runs of this driver — see :class:`CoreReinstantiationError`.
            bars: The injected bar stream. ``None`` is fail-closed; ``()`` is a defined empty run
                (design #33 §13 ∅ 양방향).

        Returns:
            The :class:`~tos.backtest.results.BacktestRun`.

        Raises:
            CoreReinstantiationError: If a *different* core is supplied after the driver has already
                run — the harness-layer seal against per-bar ledger resets (design #33 §2.4).
            BacktestIntegrityError: If the bar stream is missing or not causally ordered.
        """
        if self._bound_core is not None and self._bound_core is not core:
            raise CoreReinstantiationError(
                "this driver is already bound to an EngineCore and was handed a different one — "
                "re-instantiating the core resets the ProvisionalReservationLedger, which forges "
                "capacity headroom the real system does not have (RFC-002 §9.1:558) and destroys "
                "the single-core backtest/paper parity the slice exists to demonstrate "
                "(design #33 §2.4). The at-most-one constraint is an honest reflection of the "
                "absent RCL release path (state.py:22), not something to route around."
            )
        self._bound_core = core

        stream: BarStream = validate_bar_stream(bars)
        start = len(self._yielded)
        results: tuple[EventResult, ...] = core.run(self.events(stream))
        yielded = self._yielded[start:]

        entries: list[TraceEntry] = []
        halts: list[HaltRecord] = []
        for offset, ((event, bar_index), result) in enumerate(zip(yielded, results), start=1):
            sequence = start + offset
            entry = self._trace_entry(
                sequence=sequence, event=event, bar_index=bar_index, result=result
            )
            entries.append(entry)
            if result.halt_reason is not None:
                halts.append(
                    HaltRecord(
                        yield_sequence=sequence,
                        event_kind=entry.event_kind,
                        bar_index=bar_index,
                        instrument_key=entry.instrument_key,
                        halt_reason=result.halt_reason,
                        halt_step=entry.halt_step,
                        detail=result.detail,
                    )
                )

        return BacktestRun(
            instrument_key=self.instrument_key,
            scenario_id=self._scenario_id,
            bars_consumed=len(stream),
            events_yielded=len(yielded),
            event_results=results,
            trace=WiringTrace(
                continuity_id=self._counter.continuity_id, entries=tuple(entries)
            ),
            halts=tuple(halts),
            fill_records=self._fill_model.records,
            unsettled_fill_records=self._fill_model.unsettled_records(),
            handoff_count=len(self._fill_model.handoffs),
        )

    @staticmethod
    def _trace_entry(
        *,
        sequence: int,
        event: EngineEvent,
        bar_index: int | None,
        result: EventResult,
    ) -> TraceEntry:
        """Build one wiring-trace entry from the core's own result (design #33 §6.1).

        Everything recorded is read off the engine's :class:`~tos.engine.EventResult` and the event
        itself — the harness restates no verdict of its own, so the trace cannot disagree with what
        the core actually did.
        """
        flow = result.flow
        reservation = result.reservation
        egress = event.egress_result
        return TraceEntry(
            yield_sequence=sequence,
            event_kind=result.kind,
            bar_index=bar_index,
            instrument_key=result.instrument_key,
            ordering_admission=result.ordering,
            reference=event.reference(),
            halt_reason=result.halt_reason,
            halt_step=None if flow is None else flow.halt_step,
            handed_off=False if flow is None else flow.handed_off,
            attempt_id=(
                egress.attempt_id
                if egress is not None
                else (None if flow is None or flow.attempt is None else flow.attempt.attempt_id)
            ),
            egress_result_kind=None if egress is None else egress.kind,
            capacity_state=None if reservation is None else reservation.capacity_state,
            knowledge=None if reservation is None else reservation.knowledge,
            proposal_digest=(
                None
                if result.pipeline is None or result.pipeline.proposal is None
                else result.pipeline.proposal.canonical_digest
            ),
            outcome_digest=(
                None if result.pipeline is None else result.pipeline.outcome_digest
            ),
        )
